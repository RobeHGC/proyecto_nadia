# NADIA HITL - Human-in-the-Loop Conversational AI

[![Production Ready](https://img.shields.io/badge/status-production%20ready-green.svg)](https://github.com/RobeHGC/chatbot_nadia)
[![Build Status](https://github.com/RobeHGC/chatbot_nadia/workflows/CI%2FCD%20Pipeline/badge.svg)](https://github.com/RobeHGC/chatbot_nadia/actions)
[![Test Coverage](https://img.shields.io/badge/coverage-report-blue.svg)](https://codecov.io/gh/RobeHGC/chatbot_nadia)
[![Docker](https://img.shields.io/badge/docker-enabled-blue.svg)](https://www.docker.com/)
[![CI/CD](https://img.shields.io/badge/ci%2Fcd-github%20actions-orange.svg)](https://github.com/features/actions)
[![Monitoring](https://img.shields.io/badge/monitoring-prometheus%2Bgrafana-red.svg)](https://prometheus.io/)

A production-ready, human-in-the-loop conversational AI system for Telegram featuring advanced LLM orchestration, real-time review workflows, and comprehensive monitoring.

## 🚀 Quick Start

### Production Deployment

```bash
# Clone and setup
git clone https://github.com/RobeHGC/chatbot_nadia.git
cd chatbot_nadia

# Configure environment
cp .env.example .env
# Edit .env with your API keys and configuration

# Deploy to production
make deploy
```

### Development Setup

```bash
# Start development environment
make dev

# Access services:
# - Dashboard: http://localhost:3000
# - API: http://localhost:8000
# - Jupyter: http://localhost:8888
# - pgAdmin: http://localhost:8082
```

## 📊 System Overview

### Architecture

```
Telegram → UserBot → Redis WAL → Multi-LLM Pipeline → Human Review → Send
              ↓                        ↓                    ↓
           Recovery              Coherence System      Analytics Dashboard
           Agent                  Temporal Conflicts    Real-time Metrics
```

### Key Features

- **🤖 Multi-LLM Pipeline**: Gemini 2.0 Flash + GPT-4o-mini with 75% cost optimization
- **👥 Human-in-the-Loop**: Real-time review workflow with priority queuing
- **🔄 Zero Message Loss**: Comprehensive recovery system with "Sin Dejar a Nadie Atrás" philosophy
- **🧠 Coherence System**: Temporal conflict detection and auto-correction
- **🛡️ Protocol de Silencio**: Quarantine system for problematic users
- **📈 Advanced Monitoring**: Prometheus + Grafana with custom metrics
- **🐳 Production Ready**: Docker containerization with auto-scaling

## 💰 Cost Optimization

- **$0.000307/message** (70% cheaper than OpenAI-only)
- **Smart Caching**: 75% cache hit rate on GPT-4o-mini
- **Cost Tracking**: Real-time LLM expense monitoring
- **Efficient Routing**: Gemini for creativity, GPT for structure

## 🛠️ Technologies

### Core Stack
- **Python 3.12** - Main application language
- **FastAPI** - REST API framework
- **PostgreSQL 16** - Primary database with advanced features
- **Redis 7** - Caching and message queuing
- **Docker** - Containerization and orchestration

### AI & LLM
- **Google Gemini 2.0 Flash** - Primary creative AI (free tier)
- **OpenAI GPT-4o-mini** - Response refinement and analysis
- **Custom Prompt Caching** - 75% cost reduction on OpenAI calls
- **Tiktoken** - Token counting and cost estimation

### Monitoring & Operations
- **Prometheus** - Metrics collection
- **Grafana** - Dashboard and visualization
- **Nginx** - Load balancing and reverse proxy
- **Structured Logging** - JSON logs with correlation IDs

## 🏗️ Project Structure

```
chatbot_nadia/
├── agents/              # Core AI agents and orchestration
├── api/                 # FastAPI server and endpoints
├── dashboard/           # Web-based review interface
├── database/            # Models, migrations, and schema
├── llms/                # LLM clients and routing logic
├── memory/              # User conversation memory management
├── monitoring/          # Prometheus configs and alerts
├── nginx/               # Load balancer configuration
├── scripts/             # Deployment and maintenance scripts
├── tests/               # Comprehensive test suite
├── utils/               # Shared utilities and mixins
├── docker-compose.yml   # Production deployment
├── docker-compose.dev.yml # Development environment
└── Makefile            # Simplified command interface
```

## 🚦 Development Workflow

### Common Commands

```bash
# Development
make dev                 # Start development environment
make test               # Run test suite
make lint               # Code linting
make format             # Code formatting

# Production
make prod               # Start production environment
make deploy             # Full automated deployment
make backup             # Create system backup
make scale SERVICE=api REPLICAS=3  # Scale services

# Monitoring
make status             # Service status
make health             # Health checks
make logs               # View logs
```

## 🧪 Testing

### Running Tests

```bash
# All tests with coverage
make test

# Specific test categories
make test-unit          # Unit tests only
make test-integration   # Integration tests only
make test-e2e           # End-to-end tests
make test-coverage      # Generate coverage report

# Run specific test file
PYTHONPATH=/home/rober/projects/chatbot_nadia pytest tests/test_supervisor_core.py -v

# Run tests matching pattern
pytest tests/ -k "protocol" -v

# Run with specific markers
pytest -m "not slow" -v
```

### Test Structure

```
tests/
├── unit/                    # Fast, isolated unit tests
│   ├── test_supervisor_core.py
│   ├── test_memory_core.py
│   └── test_protocol_manager_unit.py
├── integration/             # Component integration tests
│   ├── test_coherence_integration.py
│   ├── test_protocol_api_integration.py
│   └── test_multi_llm_integration.py
├── e2e/                     # Full system tests
│   ├── automated_e2e_tester.py
│   └── test_wal_integration.py
├── conftest.py             # Shared fixtures and configuration
└── pytest.ini              # Pytest configuration
```

### Local Testing Setup

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov pytest-mock

# Set up test database
psql -U postgres -c "CREATE DATABASE nadia_hitl_test;"

# Run database migrations on test database
DATABASE_URL=postgresql://localhost/nadia_hitl_test python scripts/migrate.py

# Start Redis for testing
docker run -d -p 6379:6379 redis:7-alpine

# Set test environment variables
export PYTHONPATH=/home/rober/projects/chatbot_nadia
export DATABASE_URL=postgresql://localhost/nadia_hitl_test
export REDIS_URL=redis://localhost:6379/1
export OPENAI_API_KEY=sk-test-mock
export GEMINI_API_KEY=AIza-test-mock
```

### Writing Tests

#### Unit Test Example
```python
# tests/unit/test_new_feature.py
import pytest
from unittest.mock import AsyncMock, patch

class TestNewFeature:
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis connection."""
        redis_mock = AsyncMock()
        redis_mock.get.return_value = None
        return redis_mock
    
    @patch('module.RedisConnectionMixin._get_redis')
    async def test_feature_behavior(self, mock_get_redis, mock_redis):
        mock_get_redis.return_value = mock_redis
        # Test implementation
        assert result == expected
```

#### Integration Test Example
```python
# tests/integration/test_api_integration.py
import pytest
from httpx import AsyncClient
from api.server import app

@pytest.mark.asyncio
async def test_api_endpoint():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/health")
        assert response.status_code == 200
```

### Test Coverage

```bash
# Generate coverage report
make test-coverage

# View HTML coverage report
python -m http.server 8080 --directory htmlcov/
# Open http://localhost:8080 in browser

# Coverage thresholds (configured in pytest.ini)
# - Line coverage: 80% minimum
# - Branch coverage: 70% minimum
```

### CI/CD Testing Pipeline

The project uses GitHub Actions for continuous integration:

1. **Lint & Format** - Code quality checks with ruff and isort
2. **Unit & Integration Tests** - Full test suite with PostgreSQL and Redis
3. **Security Scan** - Secret detection with Trufflehog
4. **Coverage Report** - Automated upload to Codecov

```yaml
# .github/workflows/test.yml highlights
- PostgreSQL 14 test database
- Redis 7-alpine for caching
- Python 3.10 environment
- Parallel test execution
- Coverage reporting with Codecov
```

### Testing Best Practices

1. **Async Testing**
   - Use `pytest.mark.asyncio` for async tests
   - Properly mock async operations with `AsyncMock`
   - Clean up resources in fixtures

2. **Database Testing**
   - Use transactions for test isolation
   - Create test-specific database
   - Reset database state between tests

3. **Mocking Strategy**
   - Mock external services (Telegram, LLMs)
   - Use dependency injection for testability
   - Verify mock calls with assertions

4. **Performance Testing**
   ```bash
   # Run performance benchmarks
   pytest tests/performance/ --benchmark-only
   ```

### Test Categories and Markers

```python
# pytest.ini markers
@pytest.mark.slow        # Tests taking >1 second
@pytest.mark.integration # Tests requiring external services
@pytest.mark.unit       # Fast, isolated unit tests
@pytest.mark.e2e        # End-to-end system tests
```

## 📋 Configuration

### Environment Variables

```bash
# Core Configuration
API_ID=12345678                    # Telegram API ID
API_HASH=abcdef...                 # Telegram API Hash
PHONE_NUMBER=+1234567890           # Bot phone number

# LLM Configuration
OPENAI_API_KEY=sk-...              # OpenAI API key
GEMINI_API_KEY=AIza...             # Google Gemini API key

# Database
DATABASE_URL=postgresql://user:pass@host:5432/db
REDIS_URL=redis://localhost:6379/0

# Security
DASHBOARD_API_KEY=your-secure-key  # Dashboard authentication
```

### Advanced Features

```bash
# Performance Tuning
TYPING_DEBOUNCE_DELAY=60           # Message batching delay
MAX_CONTEXT_MESSAGES=50            # Memory per user

# Feature Flags
ENABLE_COHERENCE_SYSTEM=true       # Temporal conflict detection
ENABLE_RECOVERY_SYSTEM=true        # Zero message loss
ENABLE_QUARANTINE=true             # Problematic user management
```

## 📊 Monitoring and Alerting

### Available Dashboards

- **System Overview**: Service health, message throughput, response times
- **Business Metrics**: Review queue, user engagement, coherence violations
- **Infrastructure**: CPU, memory, database performance
- **Cost Analysis**: LLM usage and expenses by service

### Key Metrics

```
# Application Metrics
nadia_messages_processed_total      # Total messages processed
nadia_review_queue_size            # Pending reviews
nadia_llm_costs_total              # LLM API costs (USD)
nadia_coherence_violations_total   # Temporal conflicts detected

# Infrastructure Metrics
container_memory_usage_bytes       # Container memory usage
http_request_duration_seconds      # API response times
pg_stat_database_tup_returned      # Database query performance
```

## 🔐 Security

### Best Practices Implemented

- **🔑 Secrets Management**: Environment-based configuration
- **🛡️ Container Security**: Non-root users, minimal attack surface
- **🔒 Network Security**: Private networks, reverse proxy
- **📝 Audit Logging**: Comprehensive action tracking
- **🚫 Input Validation**: Pydantic models, SQL injection prevention

### Production Security Checklist

- [ ] Change default passwords
- [ ] Configure SSL/TLS certificates
- [ ] Set up firewall rules
- [ ] Enable audit logging
- [ ] Configure backup encryption
- [ ] Set up monitoring alerts

## 📈 Scaling Guide

### Horizontal Scaling

```bash
# Scale API servers
make scale SERVICE=api REPLICAS=3

# Scale background workers
make scale SERVICE=worker REPLICAS=2

# Database read replicas (manual setup)
# Configure in docker-compose.yml
```

### Performance Optimization

1. **Database Tuning**
   - Connection pooling with PgBouncer
   - Query optimization with EXPLAIN ANALYZE
   - Proper indexing strategy

2. **Redis Optimization**
   - Memory policies (allkeys-lru)
   - Persistence configuration
   - Clustering for high availability

3. **Application Tuning**
   - LLM prompt caching
   - Async request handling
   - Background task processing

## 🔧 Troubleshooting

### Common Issues

**Service won't start**
```bash
# Check logs
make logs

# Check health
make health

# Restart services
make prod-restart
```

**High memory usage**
```bash
# Check resource usage
make status

# Scale down if needed
docker-compose -f docker-compose.yml up -d --scale nadia-api=1
```

**Database connection issues**
```bash
# Check database status
make db-shell

# Reset database (DANGEROUS)
make db-reset
```

### Log Analysis

```bash
# View specific service logs
make logs-api          # API logs
make logs-bot          # Bot logs
make logs-db           # Database logs

# Real-time monitoring
docker-compose logs -f nadia-api
```

## 🤝 Contributing

### Development Setup

1. Fork the repository
2. Create a feature branch
3. Set up development environment: `make dev`
4. Make changes and add tests
5. Run test suite: `make test`
6. Submit pull request

### Branch Protection Rules

The `main` branch is protected with the following rules:

- **Required Checks**:
  - CI/CD Pipeline must pass (linting, tests, security)
  - Code coverage must meet minimum thresholds (80%)
  - At least one code review approval required
  
- **Restrictions**:
  - Direct pushes to main are disabled
  - Force pushes are disabled
  - Branch must be up to date before merging
  - Administrators are not exempt from rules

### Pull Request Process

1. **Before Opening PR**:
   ```bash
   # Run CI checks locally
   ./scripts/run_ci_checks.sh
   
   # Update from main
   git fetch origin
   git rebase origin/main
   ```

2. **PR Requirements**:
   - Descriptive title and description
   - Link to related issue (if applicable)
   - All tests passing
   - No decrease in code coverage
   - Documentation updated if needed

3. **Review Process**:
   - Automated checks run on every commit
   - Human review focuses on logic and design
   - Address all review comments
   - Squash commits before merging

### Code Style

- **Python**: Follow PEP 8, use `ruff` for linting
- **JavaScript**: Use Prettier for formatting
- **Docker**: Multi-stage builds, security best practices
- **Documentation**: Update README and inline comments
- **Tests**: Write tests for all new features

### Testing Guidelines

- **Test Coverage**: Aim for >90% on new code
- **Test Types**: Write unit, integration, and e2e tests as appropriate
- **Test Naming**: Use descriptive names that explain the scenario
- **Mock External Services**: Don't call real APIs in tests
- **See**: [Testing Guide](./docs/TESTING_GUIDE.md) for detailed information

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

### Documentation

- **[API Documentation](http://localhost:8000/docs)** - Interactive API docs
- **[Monitoring Guide](./docs/monitoring.md)** - Prometheus and Grafana setup
- **[Deployment Guide](./docs/deployment.md)** - Production deployment
- **[Troubleshooting](./docs/troubleshooting.md)** - Common issues and solutions

### Getting Help

1. **Check Issues**: Search existing [GitHub issues](https://github.com/RobeHGC/chatbot_nadia/issues)
2. **Create Issue**: Use our issue templates for bug reports or feature requests
3. **Discussions**: Join project discussions for questions and ideas

---

**Made with ❤️ by the NADIA Team**

*Human-in-the-Loop AI that scales with your needs while maintaining the personal touch.*