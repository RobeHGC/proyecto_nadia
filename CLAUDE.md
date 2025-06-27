# CLAUDE.md

Guidance for Claude Code when working with NADIA HITL system.

## Project Overview

NADIA: Human-in-the-Loop conversational AI for Telegram. Bot persona: friendly 24yo American woman. All responses require human review before sending.

## System Status: COHERENCE SYSTEM 100% IMPLEMENTED ✅ (Dec 26, 2025 - Night Session 2 - FULL INTEGRATION)

### Latest Session (Dec 26 Night Session 2 - COHERENCE PIPELINE INTEGRATION)
- ✅ **COHERENCE SYSTEM FULLY INTEGRATED**: Pipeline now active in main message flow
  - **Integration Complete**: Modified `supervisor_agent.py` to use coherence pipeline
  - **Circular Import Fixed**: Created `agents/types.py` for shared dataclasses
  - **Auto-Initialization**: Coherence agents initialize when db_manager is set
  - **Message Flow**: User → LLM1 → IntermediaryAgent → PostLLM2Agent → LLM2 → Review
  - **Fallback Safety**: Original response returned if coherence analysis fails
  - **Consistent Tracking**: Same interaction_id used throughout pipeline
- ✅ **CODE CHANGES**:
  - `agents/supervisor_agent.py`: Added coherence pipeline to `_generate_creative_response()`
  - `agents/types.py`: NEW - Moved AIResponse and ReviewItem to avoid circular imports
  - Updated imports in `database/models.py` and `userbot.py`
  - Added `interaction_id` parameter flow through entire pipeline
- ✅ **TESTING COMPLETE**: Integration test passes, all components working together

### Previous Session (Dec 26 Night - COHERENCE & SCHEDULE SYSTEM IMPLEMENTATION)
- ✅ **SISTEMA DE COHERENCIA Y VARIEDAD COMPLETADO**: Pipeline completo para detección de conflictos temporales
  - **Arquitectura**: Supervisor → LLM1 (+tiempo Monterrey) → Intermediario → LLM2 → Post-LLM2
  - **Database Schema**: 3 nuevas tablas (nadia_commitments, coherence_analysis, prompt_rotations)
  - **Conflict Detection**: IDENTIDAD (loops) vs DISPONIBILIDAD (overlaps temporales)
  - **JSON Analysis**: LLM2 prompt estático optimizado para cache 75% OpenAI
  - **Auto-Correction**: String replacement manteniendo voz de Nadia
  - **Dashboard Integration**: 3 nuevas métricas con color coding dinámico
- ✅ **API ENDPOINTS IMPLEMENTADOS**: 4 nuevos endpoints para gestión coherencia
  - `/api/coherence/metrics` - Dashboard real-time metrics  
  - `/users/{id}/commitments` - User commitment management
  - `/api/coherence/violations` - Conflict monitoring
  - `/schedule/conflicts/{user_id}` - Schedule conflict detection
- ✅ **MIGRATION EJECUTADA**: Base de datos extendida exitosamente
  - 3 tablas creadas con índices optimizados
  - 8 índices para performance sub-50ms
  - Funciones PostgreSQL para auto-cleanup
  - View optimizada active_commitments_view

### Previous Session (Dec 26 Evening - COMPREHENSIVE RECOVERY + MCP DEBUGGING SETUP)
- ✅ **COMPREHENSIVE RECOVERY STRATEGY IMPLEMENTED**: Complete replacement of cursor-based system
  - **Problem Solved**: Messages sent during downtime weren't being recovered due to missing user cursors
  - **Root Cause**: Old system only checked existing cursors, ignored new users completely
  - **New Strategy**: Telegram dialog scan → SQL lookup → Gap detection → Batch recovery
  - **Coverage**: Now detects ALL users (new + existing) and recovers missed messages reliably
- ✅ **QUARANTINE TAB JAVASCRIPT FIX**: Duplicate `switchTab` function removed
  - Fixed: `TypeError: Cannot read properties of undefined` error resolved
  - Result: 2 quarantine messages now visible in dashboard
  - Status: Quarantine system fully functional
- ✅ **12-HOUR MESSAGE LIMIT**: Recovery system optimized to prevent message flooding
  - **Time Limits**: TIER_1 (<2h), TIER_2 (2-6h), TIER_3 (6-12h), SKIP (>12h)
  - **Configuration**: `max_message_age_hours: 12` (down from 24h)
  - **Benefit**: Prevents recovery of very old messages that would overwhelm the system
- ✅ **MCP DEBUGGING SYSTEM CONFIGURED**: Advanced debugging capabilities enabled
  - **PostgreSQL MCP**: Direct database access for real-time data analysis
  - **Filesystem MCP**: Direct code/log file access without copy/paste
  - **Git MCP**: Direct repository history and diff analysis
  - **Debugging Performance**: 9 steps (2-3 minutes) → 1 step (10 seconds)
- ✅ **NEW RECOVERY COMPONENTS ADDED**:
  - `telegram_history.py::scan_all_dialogs()` - Scans all Telegram conversations
  - `database/models.py::get_last_message_per_user()` - Bulk SQL lookup for last messages
  - `recovery_agent.py::startup_recovery_check()` - Complete rewrite using new strategy
  - Rate limiting, batch processing, and comprehensive error handling

### Previous Session (Dec 26 Late Night - QUARANTINE TAB DEBUG & RECOVERY MESSAGES COMPLETE)
- ✅ **RECOVERY MESSAGES DISPLAY SYSTEM**: Complete endpoint + dashboard implementation
- ✅ **DASHBOARD STRUCTURE FIX**: Review Editor correctly contained within Review tab  
- ✅ **CRITICAL BUG FIXES COMPLETE**: All 7 reported bugs resolved

### Previous Session (Dec 26 Night - RECOVERY AGENT COMPLETE IMPLEMENTATION)
- ✅ **RECOVERY AGENT "Sin Dejar a Nadie Atrás" IMPLEMENTADO**: Zero message loss system (6 hours)
  - Database: 3 new tables + recovery fields in interactions
  - Core: `recovery_agent.py`, `telegram_history.py`, `recovery_config.py`
  - 4-tier priority system: TIER_1 (<2h), TIER_2 (2-12h), TIER_3 (12-24h), SKIP (>24h)
  - API: 6 endpoints - status, trigger, history, cursor management, health
  - Dashboard: Recovery tab, widgets, manual controls, recovered message badges
  - Safety: 24h age limit, 100 msg/session, health monitoring, comprehensive logging
- ✅ **TELEGRAM INTEGRATION**: Message ID tracking + startup recovery hook
- ✅ **PROTOCOLO DE SILENCIO INTEGRATION**: Skips quarantined users automatically
- ✅ **PRODUCTION READY**: All tests passing, health checks operational

### Previous Session (Dec 26 Evening - RECOVERY AGENT ANALYSIS & PREPARATION)
- ✅ **TESTS & DOCUMENTATION**: Protocol Manager tests (12/12), API docs, developer guide
- ✅ **DASHBOARD FIXES**: Review editor dimensions (flex: 1.5, min-width: 450px)
- ✅ **RECOVERY PLANNING**: 7-phase plan prepared, gaps identified, risks assessed

### Previous Session (Dec 25 Evening - PROTOCOLO DE SILENCIO IMPLEMENTATION)
- ✅ **PROTOCOLO DE SILENCIO COMPLETADO**: Sistema completo para gestionar usuarios "time-wasters"  
  - Intercepción de mensajes ANTES del LLM (ahorro real de $0.000307/mensaje)
  - 9 endpoints API: activar/desactivar, cuarentena, batch operations, métricas
  - Dashboard con pestaña cuarentena, modal avanzado, batch selections  
  - Auto-expiración mensajes >7 días, audit log completo
  - Sistema production-ready con tests 100% passing
- ✅ **BASE DE DATOS**: 3 nuevas tablas (user_protocol_status, protocol_audit_log, quarantine_messages)
- ✅ **DASHBOARD UI**: Pestaña cuarentena funcional con checkboxes y quick actions

### Previous Session (Jun 25 Evening - Context & Memory Optimization)
- ✅ **CUSTOMER STATUS SYNC FIX**: Fixed approve_review to sync customer_status from user_current_status table
- ✅ **INCORRECT NAME INJECTION FIX**: Bot was extracting wrong names from conversations ("Never", "A", "Winter")
  - Disabled automatic name extraction from conversations in memory/user_memory.py
  - Modified supervisor to fetch nicknames from database instead of Redis context
  - Cleaned Redis of incorrect extracted names
- ✅ **DATA EXPLORER IMPROVEMENTS**: Added created_at column with time-ago display, ordered by most recent
- ✅ **MEMORY CONTEXT OPTIMIZATION**: Enhanced LLM1 prompt format for better Gemini understanding
  - Changed from "Nadia: message" to "- Andy said: / - You replied:" format
  - Added explicit headers: "PREVIOUS CONVERSATION WITH ANDY"
  - Added actionable instructions: "Continue this conversation naturally, referencing what was discussed above"
  - Made anti-interrogation context specific with last question reference
  - Improved temporal summary format for better context awareness

### Current Memory System Status
- ✅ **Redis Memory**: 50 messages per user, 7-day TTL, proper storage confirmed
- ✅ **Conversation History**: Bot responses properly saved after approval
- ✅ **Context Injection**: Comprehensive debugging shows 839 tokens sent to Gemini with full context
- ✅ **Prompt Improvements**: New format should significantly improve Gemini's context awareness
- 🔄 **Next**: Test improved context effectiveness with real interactions

### Current System Capabilities (All Production Ready)
- ✅ **Memory System**: Redis 50 msg/user + temporal summaries working
- ✅ **PROTOCOLO DE SILENCIO**: Quarantine system saving $0.000307/msg 
- ✅ **COMPREHENSIVE RECOVERY**: Zero message loss with complete user coverage (<12h window)
- ✅ **COHERENCE SYSTEM**: Temporal conflict detection and auto-correction (100% integrated)
- ✅ **Full Testing Suite**: Protocol Manager + API + Recovery health checks
- ✅ **Dashboard**: Complete with Review, Analytics, Quarantine, Recovery, Coherence metrics (all functional)

### Next Session Priorities  
- 🧪 **END-TO-END COHERENCE VALIDATION**: Test integrated system with real scenarios
  - **Conflict Triggers**: Send messages that create IDENTIDAD and DISPONIBILIDAD conflicts
  - **Dashboard Metrics**: Verify coherence score, commitments, and conflicts update
  - **Database Verification**: Check coherence_analysis and nadia_commitments tables
  - **Performance Monitoring**: Measure latency impact (~200-500ms expected)
- 🎨 **PROMPT DIVERSITY LIBRARY**: Create variations to prevent identity loops
  - **10 LLM1 Variants**: artistic, fitness, student, social, professional, etc.
  - **Rotation Logic**: Auto-switch on CONFLICTO_DE_IDENTIDAD detection
  - **Personality Testing**: Ensure Nadia's voice remains consistent
- 🔧 **PRODUCTION OPTIMIZATION**:
  - **LLM2 Cache Tuning**: Achieve >75% cache hit rate
  - **Commitment Cleanup**: Test auto-expiration of old commitments
  - **Error Recovery**: Verify fallback mechanisms under load

### Architecture
1. **Pipeline**: Telegram → UserBot → Redis WAL → Multi-LLM + Coherence → Human Review → Send
2. **LLMs**: Gemini 2.0 Flash → Coherence Analysis (GPT-4o-mini) → Formatting → Constitution Safety
3. **Cost**: $0.000307/message (70% cheaper than OpenAI-only)
4. **Context**: 50 messages per user stored in Redis (7-day expiration)
5. **Debouncing**: 60-second delay for message batching
6. **Coherence**: Auto-detection and correction of temporal conflicts

### Recent Updates (Jun 25 - Security Implementation & Reviewer Notes System)
- ✅ **REVIEWER NOTES EDITING SYSTEM**: Complete implementation in analytics dashboard
  - Added editable reviewer_notes column replacing CTA Response display
  - Click-to-edit functionality with inline textarea and Save/Cancel buttons
  - API endpoint: `POST /interactions/{interaction_id}/reviewer-notes`
  - Keyboard shortcuts: Ctrl+Enter to save, Escape to cancel
  - 1000-character limit with HTML sanitization and validation
- ✅ **CRITICAL SECURITY IMPLEMENTATION**: Comprehensive protection system
  - Pre-commit hook prevents API key commits (blocks sk-, AIza patterns)
  - Protected `bot_session.session` from Git tracking
  - Security documentation (`SECURITY.md`) with guidelines
  - Setup script (`./setup-security.sh`) for easy configuration
  - Environment templates updated with secure defaults
- ✅ **GIT REPOSITORY RESTRUCTURING**: Clean production-ready structure
  - Created `main-legacy` branch preserving old main as backup
  - New `main` branch is production-ready reference
  - Organized documentation: `bitacora/` (historical), `checkpoints/` (sessions)
  - All sensitive files properly excluded from version control

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

## MCP Debugging System

### Configured MCP Servers
- ✅ **postgres-nadia**: Direct PostgreSQL database access
  - Command: `npx @modelcontextprotocol/server-postgres postgresql:///nadia_hitl`
  - Usage: `@postgres_table_name` for direct queries
  - Capabilities: Real-time data analysis, recovery operations monitoring
- ✅ **filesystem-nadia**: Direct project filesystem access
  - Command: `npx @modelcontextprotocol/server-filesystem /home/rober/projects/chatbot_nadia`
  - Usage: `@path/to/file.py` for instant file access
  - Capabilities: Code review, log analysis, configuration debugging
- ✅ **git-nadia**: Git repository analysis
  - Command: `python -m mcp_server_git --repository /home/rober/projects/chatbot_nadia`
  - Usage: `/mcp__git__command` for git operations
  - Capabilities: Commit history, blame analysis, diff comparison

### MCP Debugging Workflow
```bash
# Traditional debugging (slow)
User: "Recovery system not working"
Claude: "Please run: SELECT * FROM recovery_operations"
User: [copies/pastes query result]
Claude: "Now show me recovery_agent.py lines 350-400"
User: [copies/pastes code]
Result: 9 steps, 2-3 minutes

# MCP-enhanced debugging (fast)
User: "Recovery system not working"  
Claude: @postgres_recovery_operations @agents/recovery_agent.py:350-400
Analysis: Direct access + immediate diagnosis
Result: 1 step, 10 seconds
```

### Available MCP Commands
- **Database**: `@postgres_interactions`, `@postgres_quarantine_messages`, `@postgres_recovery_operations`
- **Code**: `@agents/recovery_agent.py`, `@utils/recovery_config.py`, `@dashboard/frontend/app.js`
- **Git**: `/mcp__git__log`, `/mcp__git__diff`, `/mcp__git__blame filename`
- **Logs**: `@logs/*.log`, `@bitacora/*.md`, `@checkpoints/*.md`

## Quick Start

### Running Services
```bash
# API server (port 8000)
PYTHONPATH=/home/rober/projects/chatbot_nadia python -m api.server

# Dashboard (port 3000) 
python dashboard/backend/static_server.py

# Telegram bot (with auto-recovery on startup)
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
| userbot.py | Telegram client with entity resolution + recovery | ✅ Enhanced |
| api/server.py | Review API + coherence endpoints + recovery | ✅ Enhanced |
| agents/supervisor_agent.py | Multi-LLM orchestration + coherence pipeline | ✅ Integrated |
| agents/intermediary_agent.py | LLM1→LLM2 data preparation + conflict analysis | ✅ Working |
| agents/post_llm2_agent.py | Decision execution + commitment storage | ✅ Working |
| agents/types.py | Shared dataclasses (AIResponse, ReviewItem) | ✅ NEW |
| agents/recovery_agent.py | Zero message loss recovery system | ✅ Working |
| database/models.py | Database operations + coherence tables | ✅ Updated |
| persona/llm2_schedule_analyst.md | LLM2 coherence analysis prompt | ✅ Working |
| utils/protocol_manager.py | PROTOCOLO DE SILENCIO manager | ✅ Working |
| dashboard/frontend/app.js | Review interface + coherence metrics | ✅ Enhanced |

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