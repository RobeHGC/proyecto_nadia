# DEBUGGING GUIDE - NADIA HITL SYSTEM

## Current Status (June 2025)

### ✅ Working Components
- Multi-LLM pipeline (LLM1 → LLM2 → Constitution)
- Redis-based review queue
- Dashboard with LLM response separation
- Integration tests (9/10 passing)
- Cost optimization and quota management

### 🔧 Known Issues & Solutions

#### 1. Database Migration Pending
**Issue**: Missing columns `llm1_model`, `llm2_model`, `llm1_cost_usd`, `llm2_cost_usd`
**Impact**: API errors, can't approve/reject reviews with database mode
**Solution**:
```bash
sudo -u postgres psql nadia_hitl
ALTER TABLE interactions ADD COLUMN llm1_model VARCHAR(50);
ALTER TABLE interactions ADD COLUMN llm2_model VARCHAR(50);
ALTER TABLE interactions ADD COLUMN llm1_cost_usd DECIMAL(8,6);
ALTER TABLE interactions ADD COLUMN llm2_cost_usd DECIMAL(8,6);
CREATE INDEX idx_interactions_llm1_model ON interactions(llm1_model);
CREATE INDEX idx_interactions_llm2_model ON interactions(llm2_model);
CREATE INDEX idx_interactions_costs ON interactions(llm1_cost_usd, llm2_cost_usd);
\q
```

#### 2. Approve/Reject "Internal Server Error"
**Issue**: Endpoints fail when DATABASE_MODE=skip because they try to write to database
**Status**: Partially fixed in June 2025, needs completion
**Workaround**: Use DATABASE_MODE=skip mode until database is migrated

#### 3. LLM Response Visibility
**Issue**: Dashboard doesn't clearly show LLM1 vs LLM2 responses
**Status**: Fixed in June 2025 - now shows separated sections with model badges

## Testing Procedures

### Quick Health Check
```bash
# 1. Test imports work
python -c "from agents.supervisor_agent import SupervisorAgent; print('✓ Imports OK')"

# 2. Run integration tests
python -m pytest tests/test_multi_llm_integration.py -v

# 3. Check Redis connection
redis-cli ping

# 4. Verify services are running
curl http://localhost:8000/health
curl http://localhost:3000
```

### Full System Test
```bash
# Terminal 1: API
DATABASE_MODE=skip PYTHONPATH=/home/rober/projects/chatbot_nadia python -m api.server

# Terminal 2: Dashboard
python dashboard/backend/static_server.py

# Terminal 3: Bot
DATABASE_MODE=skip python userbot.py

# Terminal 4: Manual test
python test_system.py
```

### Manual Test Flow
1. Send message to bot via Telegram
2. Check dashboard at http://localhost:3000
3. Select a review (should show LLM1 and LLM2 sections)
4. Edit if needed and approve
5. Verify message is sent back to Telegram

## Common Errors & Solutions

### ModuleNotFoundError: No module named 'cognition'
**Solution**: Use `python -m pytest` instead of `pytest`

### 'Redis' object has no attribute 'decode'
**Solution**: Fixed - uses redis.asyncio correctly now

### 429 You exceeded your current quota (Gemini)
**Solution**: Wait 10-15 seconds between tests (free tier limit: 10/minute)

### must be owner of table interactions
**Solution**: Use sudo commands with postgres user

### Reviews not appearing in dashboard
**Solution**: Check DATABASE_MODE=skip is set for both API and bot

## Performance Notes

### Cost Optimization Working
- Current: $0.000307/message with cache
- LLM1 (Gemini): FREE tier (32k tokens/day)
- LLM2 (GPT-4.1-nano): $0.0001 input, $0.0004 output with 75% cache discount

### Cache Hit Rates
- Target: >75% cache hits
- Monitor via dashboard metrics
- Stable prefixes: 1,062 tokens for maximum cache efficiency

## Future Session Checklist

### Before Making Changes
1. Run integration tests to ensure baseline works
2. Check if database migration is completed
3. Verify all services start without errors
4. Test basic message flow manually

### After Making Changes
1. Run specific tests for modified components
2. Test manual flow end-to-end
3. Check logs for new errors
4. Update this guide if new issues found

## Key File Locations

### Configuration
- `.env` - Environment variables
- `llms/model_config.yaml` - LLM profiles
- `CLAUDE.md` - Project documentation

### Core Components
- `userbot.py` - Telegram bot
- `api/server.py` - API endpoints
- `agents/supervisor_agent.py` - Multi-LLM pipeline
- `dashboard/frontend/` - Web interface

### Testing
- `tests/test_multi_llm_integration.py` - Main integration tests
- `tests/test_constitution.py` - Security tests
- `scripts/verify_multi_llm.py` - Manual verification

Last Updated: June 21, 2025