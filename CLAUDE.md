# CLAUDE.md

Guidance for Claude Code when working with NADIA HITL system.

## Project Overview

NADIA: Human-in-the-Loop conversational AI for Telegram. Bot persona: friendly 24yo American woman. All responses require human review before sending.

## System Status: PRODUCTION READY ✅ (Jun 25, 2025 - 7:15 PM)

### Architecture
1. **Pipeline**: Telegram → UserBot → Redis WAL → Multi-LLM → Human Review → Send
2. **LLMs**: Gemini 2.0 Flash (free) → GPT-4o-mini → Constitution Safety
3. **Cost**: $0.000307/message (70% cheaper than OpenAI-only)
4. **Context**: 50 messages per user stored in Redis (7-day expiration)
5. **Debouncing**: 60-second delay for message batching

### Recent Updates (Jun 25 - Dashboard Critical Fixes & User Management)
- ✅ **DASHBOARD CRITICAL BUG FIXES**: Resolved all major errors from bugs.md
  - Fixed `user_current_status` table missing (created with migrations)
  - Fixed review queue showing approved messages (Redis fallback issue)
  - Fixed `user_id=undefined` errors in customer status calls
  - Fixed PostgreSQL permissions for new table
  - Fixed entity resolution for new users (immediate cache from events)
- ✅ **USER MANAGEMENT SYSTEM**: Nickname badges and customer status
  - Added `nickname` column to `user_current_status` table
  - Implemented nickname badges in review queue (editable via click)
  - Fixed customer status logic in review editor (fresh API calls vs cached data)
  - Removed complex customer status badges to avoid race conditions
- ✅ **API ENDPOINTS ENHANCED**: 
  - `GET /users/{user_id}/customer-status` - Returns status, nickname, LTV
  - `POST /users/{user_id}/nickname` - Updates user nickname
  - All endpoints use single `user_current_status` table for consistency
- ✅ **SIMPLIFIED FRONTEND**: Removed potentially harmful complexity
  - Eliminated duplicate badge IDs and race conditions
  - Simplified user badge loading (unique users only)
  - Removed temporary logging and debugging code
  - Maintained modular, clean structure

### Previous Updates (Jun 24 - Code Quality & Simplification) 
- ✅ **MAJOR REFACTORING**: Eliminated code duplication across project
  - Created `utils/redis_mixin.py` - RedisConnectionMixin for Redis connections
  - Created `utils/error_handling.py` - @handle_errors decorator
  - Created `utils/logging_config.py` - Centralized logging
  - Created `utils/constants.py` - No more magic numbers
  - Created `utils/datetime_helpers.py` - Consistent date formatting
- ✅ **PROJECT ORGANIZATION**: Clean structure
  - `bitacora/` - All historical docs, reports, scripts
  - `checkpoints/` - Session checkpoints
  - Removed 20+ utility scripts and empty files

### Previous Updates (Jun 27 - Session 3)
- ✅ **ENTITY RESOLUTION SYSTEM**: Fixed "Could not find input entity for PeerUser" errors
- ✅ **ASYNC/AWAIT CRITICAL FIXES**: Fixed race conditions
- ✅ **COMPREHENSIVE MONITORING**: Health checks and async issue detection
- ✅ **MEMORY FIX**: Bot responses saved to history
- ✅ **CONTEXT SYSTEM**: 10 recent + 40 temporal summary
- ✅ **ANTI-MULETILLA**: Prevents phrase repetition

### Known Issues
- Chrome DevTools noise: `/.well-known/appspecific/com.chrome.devtools.json` 404 (harmless)
- Edit taxonomy connection error (minor - dashboard loads fine)

## Quick Start

### Running Services
```bash
# API server (port 8000)
PYTHONPATH=/home/rober/projects/chatbot_nadia python -m api.server

# Dashboard (port 3000) 
python dashboard/backend/static_server.py

# Telegram bot
python userbot.py

# Health monitoring  
python monitoring/health_check.py

# Recovery health check (standalone)
python monitoring/recovery_health_check.py
```

### Development Workflow Commands
```bash
# Testing
PYTHONPATH=/home/rober/projects/chatbot_nadia pytest -v           # Run all tests
PYTHONPATH=/home/rober/projects/chatbot_nadia pytest tests/test_coherence_integration.py -q  # Run specific test

# Resilience & Performance Testing (Epic 4)
PYTHONPATH=/home/rober/projects/chatbot_nadia pytest tests/test_load_performance.py -v      # Load testing
PYTHONPATH=/home/rober/projects/chatbot_nadia pytest tests/test_api_resilience.py -v        # API failure testing
PYTHONPATH=/home/rober/projects/chatbot_nadia pytest tests/test_concurrent_processing.py -v # Concurrency testing
PYTHONPATH=/home/rober/projects/chatbot_nadia pytest tests/test_resource_exhaustion.py -v   # Resource limits testing

# GitHub Issues
gh issue create --template bug_report                             # Create bug report
gh issue create --template feature_request                        # Create feature request

# Code workflow (using .claude/commands)
.claude/commands/issue.md [ISSUE_NUMBER]                          # Process GitHub issue end-to-end
```

### Environment Variables
```bash
# Required
API_ID=12345678
API_HASH=abcdef...
PHONE_NUMBER=+1234567890
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AIza...
DATABASE_URL=postgresql://username:password@localhost/nadia_hitl
DASHBOARD_API_KEY=your-secure-key
```

## Project Structure (Organized Jun 24)

```
chatbot_nadia/
├── agents/          # Core agents (supervisor)
├── api/             # API server & endpoints
├── cognition/       # Constitution & cognitive controller
├── database/        # Models & migrations
├── llms/            # LLM clients & routing
├── memory/          # User memory management
├── utils/           # Shared utilities & mixins
├── dashboard/       # Frontend review interface
├── tests/           # Test files
├── scripts/         # Utility scripts
├── bitacora/        # Historical docs & reports
└── checkpoints/     # Session checkpoints
```

## Key Components

| Component | Purpose | Status |
|-----------|---------|--------|
| userbot.py | Telegram client with entity resolution | ✅ Enhanced |
| api/server.py | Review API + user management | ✅ Enhanced |
| agents/supervisor_agent.py | Multi-LLM orchestration | ✅ Working |
| database/models.py | Database operations | ✅ Updated |
| utils/entity_resolver.py | Entity pre-resolution system | ✅ Enhanced |
| utils/redis_mixin.py | Redis connection mixin | ✅ Working |
| utils/constants.py | Project constants | ✅ Working |
| user_current_status | Customer status & nickname table | ✅ Enhanced |
| dashboard/frontend/app.js | Review interface with nickname badges | ✅ Simplified |

## Development Notes

- Always use `python -m pytest` to avoid import errors
- Set `PYTHONPATH=/home/rober/projects/chatbot_nadia` for API server
- Redis required on port 6379
- PostgreSQL required for full functionality
- Use mixins and utilities to avoid code duplication

## Recent Code Patterns

### Redis Connection (use mixin)
```python
from utils.redis_mixin import RedisConnectionMixin

class MyClass(RedisConnectionMixin):
    async def my_method(self):
        r = await self._get_redis()
        # use redis
```

### Constants (no magic numbers)
```python
from utils.constants import MONTH_IN_SECONDS, TYPING_DEBOUNCE_DELAY
# Instead of: 86400 * 30
# Use: MONTH_IN_SECONDS
```

### Datetime (consistent formatting)
```python
from utils.datetime_helpers import now_iso, time_ago_text
# Instead of: datetime.now().isoformat()
# Use: now_iso()
```

## User Management System (Enhanced Jun 25)

### Database Schema
```sql
user_current_status (
    user_id TEXT PRIMARY KEY,
    customer_status VARCHAR(20) CHECK (status IN ('PROSPECT', 'LEAD_QUALIFIED', 'CUSTOMER', 'CHURNED', 'LEAD_EXHAUSTED')),
    ltv_usd DECIMAL(8,2) DEFAULT 0.00,
    nickname VARCHAR(50),
    updated_at TIMESTAMPTZ DEFAULT NOW()
)
```

### API Endpoints
- `GET /users/{user_id}/customer-status` - Returns status, nickname, LTV
- `POST /users/{user_id}/customer-status` - Update customer status  
- `POST /users/{user_id}/nickname` - Update user nickname

### Dashboard Features
- **Review Editor**: Fresh customer status loading (no cached data)
- **Review Queue**: Editable nickname badges (click to edit)
- **Auto-refresh**: Maintains user data consistency every 30 seconds

### Implementation Notes
- Single source of truth for user data
- No complex joins or race conditions
- Modular frontend with clean separation
- Entity resolution for new Telegram users

## Resilience & Performance Testing (Epic 4 - June 27, 2025) 

### Test Suite Overview
Comprehensive testing framework for system robustness under load and failure conditions:

```bash
# Load & Performance Testing
tests/test_load_performance.py      # Message burst, concurrent users, sustained load
tests/test_api_resilience.py        # API timeouts, rate limits, network failures  
tests/test_concurrent_processing.py # Race conditions, memory access, queue safety
tests/test_resource_exhaustion.py   # Memory/CPU/connection limits, graceful degradation
```

### Key Test Frameworks

#### LoadTestingFramework
```python
# Test message processing under load
await load_tester.simulate_message_burst(count=100, duration_seconds=15)
await load_tester.simulate_concurrent_users(users=25, messages_per_user=4)
await load_tester.measure_resource_usage(duration_seconds=20)
```

#### APIFailureSimulator  
```python
# Test API resilience patterns
async with api_simulator.simulate_api_timeout("openai", timeout_duration=30.0):
async with api_simulator.simulate_rate_limiting("gemini", failure_rate=0.8):
async with api_simulator.simulate_network_failures("openai", failure_rate=0.5):
```

#### ConcurrencyTestFramework
```python
# Test concurrent access safety
await concurrency_tester.simulate_concurrent_memory_access(user_count=20, operations_per_user=15)
await concurrency_tester.simulate_redis_connection_competition(concurrent_connections=25)
```

#### ResourceExhaustionSimulator
```python
# Test system limits and degradation
await resource_simulator.simulate_memory_exhaustion(target_mb=100)
await resource_simulator.simulate_connection_exhaustion(max_connections=50)
await resource_simulator.simulate_cpu_exhaustion(duration_seconds=10, cpu_threads=4)
```

### Performance Benchmarks
- **Response Time**: <2s average under normal load, <5s under stress
- **Throughput**: 100+ messages/minute sustained processing
- **Memory Usage**: <500MB stable operation, <1GB under load  
- **Error Rate**: <1% under normal load, <5% under stress
- **Recovery**: System recovers to normal operation within 5 minutes

### Resilience Patterns Tested
1. **API Failure Handling**: Timeout protection, rate limit respect, graceful fallback
2. **Concurrent Processing**: Race condition prevention, resource contention management  
3. **Resource Management**: Memory leak detection, connection pool management
4. **Queue Safety**: Message loss prevention, duplicate processing detection
5. **Circuit Breaker**: Cascading failure prevention, automatic recovery
6. **Graceful Degradation**: Performance degradation under increasing load

### Running Resilience Tests
```bash
# Quick validation (core functionality)
PYTHONPATH=/home/rober/projects/chatbot_nadia pytest tests/test_load_performance.py::TestLoadPerformance::test_message_burst_light_load -v

# Full resilience suite (extended runtime)
PYTHONPATH=/home/rober/projects/chatbot_nadia pytest tests/test_*_resilience.py tests/test_*_performance.py -v

# Specific test categories
pytest tests/test_load_performance.py -k "light"           # Light load tests only
pytest tests/test_concurrent_processing.py -k "memory"    # Memory concurrency tests  
pytest tests/test_resource_exhaustion.py -k "connection"  # Connection limit tests
```

**Last Updated**: June 27, 2025 (11:30 PM) - Epic 4: Resilience & Performance Testing Implementation