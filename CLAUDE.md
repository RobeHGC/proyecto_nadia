# CLAUDE.md

Guidance for Claude Code when working with NADIA HITL system.

## Project Overview

NADIA: Human-in-the-Loop conversational AI for Telegram. Bot persona: friendly 24yo American woman. All responses require human review before sending.

## System Status: PRODUCTION READY ✅ (Jun 26, 2025)

### Architecture
1. **Pipeline**: Telegram → UserBot → Redis WAL → Multi-LLM → Human Review → Send
2. **LLMs**: Gemini 2.0 Flash (free) → GPT-4.1-nano → Constitution Safety
3. **Cost**: $0.000307/message (70% cheaper than OpenAI-only)

### Recent Updates (Jun 26)
- ✅ Fixed 422 error: Added missing TONE_* tags to validation
- ✅ Security cleanup: Removed credentials from documentation  
- ✅ Enhanced .gitignore for sensitive files
- ✅ **CRITICAL FIX**: Resolved GPT-4o-nano interpretation bug (supervisor_agent.py:325)
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

### LLM Pipeline (Updated Jun 26)
1. **LLM1 (Gemini 2.0 Flash)**: Creative response generation with Emotional Intelligence Framework
   - Persona loaded from `persona/nadia_llm1.md` (2,486 chars)
   - 4-stage conversation flow: ICEBREAKER → SURFACE_FLIRT → DEEP_EMOTION → HIGH_INTENT
   - Texas-style American English specification
   - Advanced boundary management for content redirection

2. **LLM2 (GPT-4o-nano)**: Response humanization with 75% cost optimization
   - POFMC (Professional OFM Chatter) role from `persona/nadia_v1.md` (1,391 tokens)
   - OpenAI prompt caching enabled (≥1024 token stable prefix)
   - **CRITICAL FIX**: Separated instruction text from content (line 325)
   - [GLOBO] delimiter for message bubble splitting

3. **Constitution Layer**: Safety analysis (86.5% effective)

### Cache Performance
- Target cache ratio: ≥75% for cost optimization
- Monitor via `/api/models/cache-metrics` endpoint
- Warm-up required after persona changes

**Last Updated**: June 26, 2025 - LLM pipeline optimization and EI framework integration