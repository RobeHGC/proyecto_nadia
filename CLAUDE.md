# CLAUDE.md

Guidance for Claude Code when working with NADIA HITL system.

## Project Overview

NADIA: Human-in-the-Loop conversational AI for Telegram. Bot persona: friendly 24yo American woman. All responses require human review before sending.

## System Status: PRODUCTION READY ✅ (Jun 27, 2025 - 4:00 PM)

### Architecture
1. **Pipeline**: Telegram → UserBot → Redis WAL → Multi-LLM → Human Review → Send
2. **LLMs**: Gemini 2.0 Flash (free) → GPT-4o-mini → Constitution Safety
3. **Cost**: $0.000307/message (70% cheaper than OpenAI-only)
4. **Context**: 50 messages per user stored in Redis (7-day expiration)
5. **Debouncing**: 60-second delay for message batching

### Recent Updates (Jun 27 - Session 2)
- ✅ **MEMORY FIX**: Bot responses now saved to conversation history 
- ✅ **CONTEXT SYSTEM**: Implemented 10 recent messages + temporal summary of 40 older messages
- ✅ **TEMPORAL AWARENESS**: Summary includes "2 hours ago", "Yesterday" time markers
- ✅ **ANTI-MULETILLA**: Tracks repeated phrases like "tell me more" to avoid repetition
- ✅ **VERIFIED**: Redis stores 50 messages per user (not 50 total) - currently 3 active users

### Previous Updates (Jun 27 - Morning)
- ✅ **CRITICAL FIX**: Fixed LLM router initialization error (`'SupervisorAgent' object has no attribute 'llm_router'`)
- ✅ **LLM2 FIX**: Corrected refinement prompt to prevent LLM2 from responding to LLM1 as user
- ✅ **PROMPT UPDATE**: LLM2 now correctly acts as editor/refinador with [GLOBO] formatting
- ✅ **DEBOUNCING**: Updated to 60 seconds for better message batching

### Previous Updates (Jun 26)
- ✅ Fixed 422 error: Added missing TONE_* tags to validation
- ✅ Security cleanup: Removed credentials from documentation  
- ✅ Enhanced .gitignore for sensitive files
- ✅ **LLM OPTIMIZATION**: Externalized prompts to persona/ directory with OpenAI caching
- ✅ **AI ENHANCEMENT**: Integrated Emotional Intelligence Framework for LLM1
- ❌ Customer tracking exists but not integrated in current dashboard

### Known Issues
- Dashboard always shows "PROSPECT" for customer status
- Customer status tracking needs frontend integration
- Constitution has 2 Spanish bypass vulnerabilities

## Quick Start

### Running Services
```bash
# API server (port 8000)
PYTHONPATH=/home/rober/projects/chatbot_nadia python -m api.server

# Dashboard (port 3000) 
python dashboard/backend/static_server.py

# Telegram bot
python userbot.py
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

## Key Components

| Component | Purpose | Status |
|-----------|---------|--------|
| userbot.py | Telegram client with WAL | ✅ Working |
| api/server.py | Review API + dashboard | ✅ Working |
| agents/supervisor_agent.py | Multi-LLM orchestration | ✅ Working |
| persona/nadia_llm1.md | LLM1 persona with EI framework | ✅ Working |
| persona/nadia_v1.md | LLM2 POFMC humanizer (1391 tokens) | ✅ Working |
| llms/stable_prefix_manager.py | OpenAI prompt caching manager | ✅ Working |
| cognition/constitution.py | Safety layer | ⚠️ 86.5% effective |
| dashboard/frontend/app.js | Review interface | ⚠️ Missing customer status |

## Development Notes

- Always use `python -m pytest` to avoid import errors
- Set `PYTHONPATH=/home/rober/projects/chatbot_nadia` for API server
- Redis required on port 6379
- PostgreSQL required for full functionality

## AI System Architecture

### LLM Pipeline (Updated Jun 27 - Session 2)
1. **LLM1 (Gemini 2.0 Flash)**: Creative response generation with Emotional Intelligence Framework
   - Persona loaded from `persona/nadia_llm1.md` (2,486 chars)
   - 4-stage conversation flow: ICEBREAKER → SURFACE_FLIRT → DEEP_EMOTION → HIGH_INTENT
   - Texas-style American English specification
   - Advanced boundary management for content redirection
   - **NEW**: Uses last 10 messages + temporal summary of 40 older messages
   - **NEW**: Receives temporal context like "2 hours ago: User mentioned work"
   - **NEW**: Anti-muletilla warnings in context

2. **LLM2 (GPT-4o-mini)**: Response humanization with 75% cost optimization
   - POFMC (Professional OFM Chatter) role from `persona/nadia_v1.md` (1,391 tokens)
   - OpenAI prompt caching enabled (≥1024 token stable prefix)
   - **STABLE**: Editor role maintained with explicit prompt
   - Current prompt: "ORIGINAL DRAFT...REFORMAT TASK...You are an EDITOR"
   - [GLOBO] delimiter for message bubble splitting

3. **Constitution Layer**: Safety analysis (86.5% effective)

### Cache Performance
- Target cache ratio: ≥75% for cost optimization
- Monitor via `/api/models/cache-metrics` endpoint
- Warm-up required after persona changes

## Memory & Context Management

### Redis Storage (FULLY IMPLEMENTED ✅)
- **Per-user conversation history**: 50 messages max (auto-trimmed)
- **Redis keys**: `user:{user_id}:history` (7-day expiration)
- **Context window**: Last 10 messages + temporal summary of 40 older
- **Isolation**: Each user has separate conversation history
- **Current state**: 3 active users, 110 total messages stored

### Conversation Context System
- **Recent messages**: Full text of last 10 messages (5 exchanges)
- **Temporal summary**: AI-free summary with time markers:
  - "3 hours ago: User introduced themselves as John"
  - "2 hours ago: Discussed work/profession"
  - "Note: Used 'tell me more' 3 times recently"
- **Anti-muletilla**: Tracks overused phrases to prevent repetition

### Message Debouncing  
- **Current setting**: 60 seconds (configurable via TYPING_DEBOUNCE_DELAY)
- **Purpose**: Batch rapid messages into single context
- **Config location**: `.env` file

## Implementation Details

### Key Files Modified (Jun 27)
1. **userbot.py:232-238**: Added bot response saving to history
2. **memory/user_memory.py:247-282**: Added `get_conversation_with_summary()`
3. **memory/user_memory.py:415-540**: Added `_generate_temporal_summary()`
4. **supervisor_agent.py:352-418**: Updated to use 10+40 context system

### Critical Fixes Applied
- Bot responses now saved with role="assistant" 
- Temporal summaries use Python pattern matching (no LLM)
- Anti-muletilla integrated into summary generation
- LLM2 prompt remains stable to prevent interpretation issues

**Last Updated**: June 27, 2025 (4:00 PM) - Full memory system implementation