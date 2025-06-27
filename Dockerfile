# NADIA HITL Production Dockerfile
# Multi-stage build for optimized production image

# ====================================================================
# Stage 1: Build dependencies and prepare environment
# ====================================================================
FROM python:3.12-slim as builder

# Set build arguments
ARG BUILD_ENV=production
ARG BUILD_DATE
ARG BUILD_VERSION
ARG BUILD_COMMIT

# Add metadata labels
LABEL maintainer="NADIA HITL Team"
LABEL org.opencontainers.image.title="NADIA HITL Chatbot"
LABEL org.opencontainers.image.description="Human-in-the-Loop conversational AI for Telegram"
LABEL org.opencontainers.image.version="${BUILD_VERSION}"
LABEL org.opencontainers.image.created="${BUILD_DATE}"
LABEL org.opencontainers.image.revision="${BUILD_COMMIT}"
LABEL org.opencontainers.image.source="https://github.com/RobeHGC/chatbot_nadia"

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    build-essential \
    pkg-config \
    libffi-dev \
    libssl-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment for dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements first for better Docker layer caching
COPY requirements.txt /tmp/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r /tmp/requirements.txt

# ====================================================================
# Stage 2: Production runtime image
# ====================================================================
FROM python:3.12-slim as production

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/opt/venv/bin:$PATH"

# Install runtime system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get purge -y --auto-remove

# Create non-root user for security
RUN groupadd --gid 1000 nadia && \
    useradd --uid 1000 --gid nadia --shell /bin/bash --create-home nadia

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Create application directory and set ownership
WORKDIR /app
RUN chown -R nadia:nadia /app

# Switch to non-root user
USER nadia

# Copy application code with proper ownership
COPY --chown=nadia:nadia . .

# Create necessary directories
RUN mkdir -p logs data temp && \
    chmod 755 logs data temp

# Health check script
COPY --chown=nadia:nadia <<EOF /app/healthcheck.py
#!/usr/bin/env python3
import sys
import asyncio
import aiohttp
import os

async def check_health():
    """Health check for the NADIA HITL application."""
    try:
        # Check if API server is responding
        async with aiohttp.ClientSession() as session:
            async with session.get('http://localhost:8000/health', timeout=5) as resp:
                if resp.status == 200:
                    return True
        return False
    except Exception:
        return False

if __name__ == "__main__":
    result = asyncio.run(check_health())
    sys.exit(0 if result else 1)
EOF

RUN chmod +x /app/healthcheck.py

# Expose the application port
EXPOSE 8000

# Health check configuration
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python /app/healthcheck.py

# Default command (can be overridden in docker-compose)
CMD ["python", "-m", "api.server"]

# ====================================================================
# Stage 3: Development image (optional)
# ====================================================================
FROM production as development

USER root

# Install development tools
RUN apt-get update && apt-get install -y \
    vim \
    htop \
    net-tools \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install development Python packages
RUN pip install --no-cache-dir \
    ipython \
    jupyter \
    black \
    isort \
    mypy \
    pre-commit

USER nadia

# Development-specific environment
ENV FLASK_ENV=development \
    PYTHONPATH=/app

# Override CMD for development
CMD ["python", "-m", "api.server", "--reload"]