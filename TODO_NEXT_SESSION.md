# TODO - Next Session

## Immediate Tasks (High Priority)

### 1. Apply Database Migration
```bash
psql $DATABASE_URL < database/migrations/simplify_customer_status.sql
```
- Verify migration runs without errors
- Test that existing data migrates correctly
- Confirm frontend shows correct customer status

### 2. Implement Silence Protocol System
From `bitacora/bugs.md` - implement strategic silence system for time-wasters:

**Requirements:**
- Red button in dashboard to activate silence protocol for users
- New SQL dimension: `silence_protocol` (activated/deactivated/approved)
- When activated: messages bypass LLM, go directly to silence dashboard section
- Manual review and approval system for silenced users
- Debouncing time (5 min) after approval before next message goes to LLM

**Implementation Plan:**
1. Add silence_protocol column to user_current_status table
2. Add red button UI to dashboard review cards
3. Create silence protocol dashboard section
4. Modify supervisor to check silence status before routing to LLM
5. Add approval workflow for silenced users

### 3. Review Queue Management
- Current: 150 pending messages (saturated)
- Investigate why queue is not being processed efficiently
- Consider batch processing improvements
- Add queue monitoring and alerts

## Medium Priority

### 4. Performance Optimization
- Profile database queries under load
- Optimize Redis usage patterns
- Consider pagination for large review queues

### 5. Testing & Validation
- Add integration tests for new customer status system
- Test silence protocol end-to-end
- Verify all refactored code paths

## Documentation Updates

### 6. Update README.md
- Reflect new project structure
- Update with latest features
- Add deployment instructions

## Code Quality (Ongoing)

### 7. Continue Refactoring
- Apply error handling decorator to more functions
- Convert remaining magic numbers to constants
- Standardize datetime usage across all files

## Files Ready for Next Session

**New Migrations:**
- `database/migrations/simplify_customer_status.sql` ✅ Ready
- Next: silence protocol migration

**Updated Core Files:**
- `CLAUDE.md` ✅ Updated with latest architecture
- `utils/` directory ✅ New utilities ready
- `api/server.py` ✅ Simplified customer status endpoints

**Project Structure:**
- `bitacora/` ✅ All historical docs organized
- `checkpoints/` ✅ Session summaries preserved
- Clean main directory ✅ Only active code

## Current System Status
- ✅ Bot operational
- ✅ Dashboard functional
- ✅ Customer status fix applied
- ⚠️ Need migration run
- ⚠️ Queue saturation needs attention