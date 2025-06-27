# NADIA HITL - Developer Setup Guide

Comprehensive setup guide for NADIA Human-in-the-Loop conversational AI system.

## Prerequisites

### System Requirements
- **Python**: 3.11+ (tested with 3.12)
- **Redis**: 6.0+ running on port 6379
- **PostgreSQL**: 13+ for production database
- **Node.js**: 18+ (for dashboard dependencies)
- **Git**: Latest version

### API Keys Required
- **OpenAI API Key**: For GPT-4o-mini (LLM2 and fallback)
- **Gemini API Key**: For Gemini 2.0 Flash (LLM1 - free tier)
- **Telegram API**: API_ID, API_HASH, PHONE_NUMBER for bot
- **Dashboard API Key**: Secure key for dashboard authentication

## Quick Start (5 minutes)

### 1. Clone and Setup Environment

```bash
# Clone repository
git clone <repository-url>
cd chatbot_nadia

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Configuration

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your configuration
nano .env
```

### 3. Required Environment Variables

```bash
# Telegram Configuration
API_ID=12345678
API_HASH=abcdef1234567890abcdef1234567890
PHONE_NUMBER=+1234567890

# LLM API Keys
OPENAI_API_KEY=sk-proj-xxxxxxxxxx
GEMINI_API_KEY=AIzaxxxxxxxxxxxxxx

# Database
DATABASE_URL=postgresql://username:password@localhost/nadia_hitl

# Redis
REDIS_URL=redis://localhost:6379

# Dashboard Security
DASHBOARD_API_KEY=your-secure-random-key-here

# Optional: Model Configuration
LLM_PROFILE=production
LLM1_PROVIDER=gemini
LLM2_PROVIDER=openai
```

### 4. Database Setup

```bash
# Install PostgreSQL (Ubuntu/Debian)
sudo apt update
sudo apt install postgresql postgresql-contrib

# Create database and user
sudo -u postgres createdb nadia_hitl
sudo -u postgres createuser nadia_user
sudo -u postgres psql -c "ALTER USER nadia_user WITH PASSWORD 'your_password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE nadia_hitl TO nadia_user;"

# Run migrations
python -c "from database.models import DatabaseManager; import asyncio; asyncio.run(DatabaseManager().create_tables())"
```

### 5. Redis Setup

```bash
# Install Redis (Ubuntu/Debian)
sudo apt install redis-server

# Start Redis
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Test Redis connection
redis-cli ping  # Should return "PONG"
```

### 6. Run Services

```bash
# Terminal 1: API Server (port 8000)
PYTHONPATH=/path/to/chatbot_nadia python -m api.server

# Terminal 2: Dashboard (port 3000)
python dashboard/backend/static_server.py

# Terminal 3: Telegram Bot
python userbot.py

# Terminal 4: Health Monitoring (optional)
python monitoring/health_check.py
```

## Detailed Setup

### Security Configuration

```bash
# Run security setup script
./setup-security.sh

# This will:
# - Configure pre-commit hooks
# - Set up .gitignore for sensitive files
# - Create secure environment templates
```

### Database Schema

The system uses these main tables:

#### Core Tables
- `interactions`: Conversation history and review data
- `user_current_status`: Customer status, nicknames, LTV
- `human_edits`: Edit history and quality metrics

#### Protocol Tables (PROTOCOLO DE SILENCIO)
- `user_protocol_status`: Active/inactive protocol status
- `quarantine_messages`: Messages from silenced users
- `protocol_audit_log`: Complete audit trail

#### Analytics Tables
- `conversation_analytics`: Performance metrics
- `llm_usage_tracking`: Model usage and costs

### LLM Configuration

#### Production Profile (Recommended)
```yaml
# Uses cost-optimized multi-LLM setup
LLM1: Gemini 2.0 Flash (free tier)
LLM2: GPT-4o-mini (cost-effective)
Cost: $0.000307/message (70% cheaper than OpenAI-only)
```

#### Development Profile
```yaml
# Uses single LLM for simplicity
LLM1: GPT-4o-mini
LLM2: GPT-4o-mini
Cost: $0.001/message
```

### Dashboard Configuration

```bash
# Install dashboard dependencies (if needed)
cd dashboard/frontend
npm install  # If using npm-based assets

# Configure CORS origins in api/server.py
CORS_ORIGINS = [
    "http://localhost:3000",    # Development
    "https://your-domain.com"   # Production
]
```

## Testing Setup

### Unit Tests
```bash
# Run all tests
python -m pytest

# Run specific test suites
python -m pytest tests/test_protocol_manager_simple.py -v
python -m pytest tests/test_protocol_api_integration.py -v

# Run with coverage
python -m pytest --cov=. --cov-report=html
```

### Integration Tests
```bash
# Test database connection
python scripts/test_db_connection.py

# Test Redis connection
python -c "import redis; r=redis.Redis(); print(r.ping())"

# Test LLM connections
python scripts/verify_multi_llm.py
```

## Production Deployment

### Environment-Specific Configuration

#### Development
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Use smaller limits for testing
export MAX_HISTORY_LENGTH=10
export TYPING_DEBOUNCE_DELAY=10
```

#### Production
```bash
# Use production logging
export LOG_LEVEL=INFO

# Optimize for performance
export MAX_HISTORY_LENGTH=50
export TYPING_DEBOUNCE_DELAY=60

# Enable monitoring
export ENABLE_HEALTH_CHECKS=true
```

### Performance Tuning

#### Redis Configuration
```bash
# In /etc/redis/redis.conf
maxmemory 2gb
maxmemory-policy allkeys-lru
save 900 1    # Backup every 15 minutes if ≥1 key changed
```

#### PostgreSQL Configuration
```sql
-- Optimize for read-heavy workload
shared_buffers = '256MB'
effective_cache_size = '1GB'
random_page_cost = 1.1
```

### Monitoring Setup

```bash
# Health check endpoint
curl http://localhost:8000/health

# Metrics endpoint
curl http://localhost:8000/metrics

# Protocol statistics
curl -H "Authorization: Bearer your-api-key" \
     http://localhost:8000/quarantine/stats
```

## Troubleshooting

### Common Issues

#### 1. "Could not find input entity" (Telegram)
```bash
# Clear session and restart
rm bot_session.session
python userbot.py  # Will prompt for phone verification
```

#### 2. Redis Connection Errors
```bash
# Check Redis status
sudo systemctl status redis-server

# Test connection
redis-cli ping

# Check Redis logs
sudo journalctl -u redis-server -f
```

#### 3. Database Connection Issues
```bash
# Test database connection
python scripts/test_db_connection.py

# Check PostgreSQL status
sudo systemctl status postgresql

# View PostgreSQL logs
sudo tail -f /var/log/postgresql/postgresql-*.log
```

#### 4. LLM API Errors
```bash
# Test API keys
python scripts/verify_multi_llm.py

# Check quota limits
curl -H "Authorization: Bearer $OPENAI_API_KEY" \
     https://api.openai.com/v1/usage
```

### Performance Issues

#### High Memory Usage
```bash
# Check Redis memory usage
redis-cli info memory

# Monitor Python processes
htop -p $(pgrep -f "python.*api.server")
```

#### Slow Response Times
```bash
# Check database performance
EXPLAIN ANALYZE SELECT * FROM interactions 
WHERE created_at > NOW() - INTERVAL '1 day';

# Monitor API response times
tail -f logs/api.log | grep "response_time"
```

## Development Workflow

### Code Style
```bash
# Format code
black .

# Sort imports
isort .

# Type checking
mypy . --ignore-missing-imports
```

### Git Workflow
```bash
# Feature branch
git checkout -b feature/new-functionality

# Commit with descriptive messages
git commit -m "feat: implement protocol batch processing

- Add batch endpoint for quarantine messages
- Include success/failure tracking
- Add comprehensive error handling"

# Push and create PR
git push origin feature/new-functionality
```

### Adding New Features

1. **Create tests first** (TDD approach)
2. **Update API documentation** in docs/
3. **Add database migrations** if needed
4. **Update CLAUDE.md** with changes
5. **Test thoroughly** before deployment

## Support

### Documentation
- **Architecture**: `bitacora/ARCHITECTURE.md`
- **API Reference**: `docs/api_documentation.py`
- **Session Notes**: `checkpoints/`

### Logging
```bash
# View real-time logs
tail -f logs/nadia.log

# API server logs
tail -f logs/api.log

# Protocol activity
tail -f logs/protocol.log
```

### Health Checks
```bash
# System health
./bitacora/health_check.sh

# Comprehensive system check
./bitacora/check_system.sh
```

**Last Updated**: December 26, 2025
**System Version**: Production Ready ✅
**Maintainer**: NADIA Development Team