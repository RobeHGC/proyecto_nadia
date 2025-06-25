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

**Last Updated**: June 25, 2025 (7:15 PM) - User management and critical fixes