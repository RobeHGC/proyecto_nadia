# TODO NEXT SESSION - Sistema de Coherencia VALIDATION & OPTIMIZATION

## ✅ **COMPLETED IN THIS SESSION**

### **Coherence Pipeline Integration (100% DONE)**
- ✅ Fixed circular import by creating `agents/types.py`
- ✅ Modified `supervisor_agent.py` to initialize coherence agents in `set_db_manager()`
- ✅ Updated `_generate_creative_response()` to use full coherence pipeline
- ✅ Added `interaction_id` parameter flow through entire system
- ✅ Implemented fallback safety (returns original if analysis fails)
- ✅ All tests passing, integration verified

## 🧪 **NEXT SESSION: END-TO-END VALIDATION**

### **1. Real-World Testing Scenarios**
**Objective**: Validate coherence system with actual user messages  
**Test Cases**:
- **Identity Conflict**: Send "tomorrow I have an exam" multiple times from same user
- **Schedule Conflict**: "Let's meet at 3pm" when gym already scheduled at 3pm
- **Commitment Extraction**: "I'll text you later tonight" → verify DB save
- **JSON Fallback**: Intentionally malform LLM2 response to test recovery
- **Performance**: Measure actual latency added by coherence pipeline

**Actions**:
```bash
# Start all services
PYTHONPATH=/home/rober/projects/chatbot_nadia python -m api.server
python dashboard/backend/static_server.py
python userbot.py

# Send test messages via Telegram
# Monitor dashboard at http://localhost:3000
```

**Estimado**: 1.5 hours  
**Priority**: HIGH

### **2. Database Verification Queries**
**Objective**: Confirm data is being stored correctly  
**SQL Queries**:
```sql
-- Check coherence analysis results
SELECT * FROM coherence_analysis 
WHERE created_at > NOW() - INTERVAL '1 hour'
ORDER BY created_at DESC;

-- Check commitments being saved
SELECT * FROM nadia_commitments 
WHERE user_id = 'test_user_id'
ORDER BY commitment_timestamp DESC;

-- Check conflict distribution
SELECT analysis_status, COUNT(*) 
FROM coherence_analysis 
GROUP BY analysis_status;

-- Verify prompt rotations
SELECT * FROM prompt_rotations 
ORDER BY created_at DESC LIMIT 10;
```

**Estimado**: 30 minutes  
**Priority**: HIGH

### **3. Dashboard Metrics Validation**
**Objective**: Ensure real-time updates working  
**Checklist**:
- [ ] Coherence score updates when messages processed
- [ ] Active commitments counter increments
- [ ] Schedule conflicts appear in violations list
- [ ] Color coding changes based on score (green >90%, yellow 70-90%, red <70%)
- [ ] API response times stay under 1 second

**Estimado**: 30 minutes  
**Priority**: HIGH

## 🎨 **PROMPT DIVERSITY IMPLEMENTATION**

### **4. Create LLM1 Prompt Variants**
**Objective**: Prevent identity loops with diverse personalities  
**Structure**:
```
persona/llm1_variants/
├── base_nadia.md          # Original personality (default)
├── artistic_nadia.md      # Focus on creative pursuits
├── fitness_nadia.md       # Gym enthusiast variant  
├── studious_nadia.md      # Medical school focused
├── social_nadia.md        # Party/social butterfly
├── homebody_nadia.md      # Cozy, intimate variant
├── adventurous_nadia.md   # Travel and outdoors
├── foodie_nadia.md        # Culinary interests
├── tech_nadia.md          # Gaming/tech savvy
└── professional_nadia.md  # Career-driven variant
```

**Implementation**:
```python
# In supervisor_agent.py
def _select_prompt_variant(self, user_id: str, has_identity_conflict: bool):
    if has_identity_conflict:
        # Rotate to next variant
        variants = ['artistic', 'fitness', 'studious', ...]
        current_index = self._get_user_variant_index(user_id)
        next_variant = variants[(current_index + 1) % len(variants)]
        return f"persona/llm1_variants/{next_variant}_nadia.md"
    return "persona/nadia_llm1.md"  # Default
```

**Estimado**: 2 hours  
**Priority**: MEDIUM

### **5. Implement Prompt Rotation Logic**
**Objective**: Auto-switch on CONFLICTO_DE_IDENTIDAD  
**Changes**:
- Track variant per user in Redis
- Rotate on identity conflicts
- Log rotations to prompt_rotations table
- Maintain personality consistency

**Estimado**: 1 hour  
**Priority**: MEDIUM

## 🔧 **PERFORMANCE OPTIMIZATION**

### **6. LLM2 Cache Optimization**
**Objective**: Achieve >75% cache hit rate  
**Actions**:
- Monitor actual cache performance
- Ensure static prompt prefix is stable
- Test with high message volume
- Optimize prompt structure if needed

**Estimado**: 1 hour  
**Priority**: MEDIUM

### **7. Database Query Optimization**
**Objective**: Keep commitment queries under 50ms  
**Actions**:
- EXPLAIN ANALYZE on commitment queries
- Add indexes if needed
- Test with 1000+ commitments per user
- Implement query result caching

**Estimado**: 1 hour  
**Priority**: LOW

## 📊 **MONITORING & METRICS**

### **8. Production Monitoring Setup**
**Objective**: Track system health in production  
**Metrics to Monitor**:
- Coherence analysis success rate
- Average correction rate
- LLM2 cache hit ratio
- JSON parsing failure rate
- Commitment extraction accuracy
- Pipeline latency percentiles (p50, p95, p99)

**Tools**:
- Add Prometheus metrics
- Create Grafana dashboard
- Set up alerts for failures

**Estimado**: 2 hours  
**Priority**: LOW

## 🐛 **EDGE CASES & ERROR HANDLING**

### **9. Edge Case Testing**
**Test Scenarios**:
- User with 100+ active commitments
- Malformed timestamp in commitment text
- LLM2 returns non-JSON response
- Database connection lost mid-pipeline
- Concurrent messages from same user
- Unicode/emoji in commitments

**Estimado**: 1 hour  
**Priority**: MEDIUM

### **10. Error Recovery Enhancement**
**Improvements**:
- Better error messages in logs
- User-friendly fallback responses
- Retry logic for transient failures
- Circuit breaker for LLM2 failures

**Estimado**: 1 hour  
**Priority**: LOW

## 📋 **SESSION EXECUTION PLAN**

### **Phase 1: Validation (2 hours)**
1. Start all services
2. Run real-world test scenarios
3. Verify database queries
4. Check dashboard metrics
5. Document any issues found

### **Phase 2: Prompt Diversity (2 hours)**
6. Create 10 prompt variants
7. Implement rotation logic
8. Test identity conflict handling

### **Phase 3: Optimization (1 hour)**
9. Monitor cache performance
10. Optimize slow queries
11. Test edge cases

### **Phase 4: Polish (Optional)**
12. Setup monitoring
13. Enhance error handling
14. Update documentation

## 🎯 **SUCCESS CRITERIA**

### **Must Have**
- ✅ Coherence system detecting and fixing conflicts in production
- ✅ Dashboard showing accurate real-time metrics
- ✅ No significant performance degradation (<500ms added)
- ✅ All edge cases handled gracefully

### **Nice to Have**
- ✅ Prompt rotation preventing identity loops
- ✅ Cache hit rate >75%
- ✅ Comprehensive monitoring dashboard
- ✅ Zero JSON parsing failures

## ⚡ **QUICK START COMMANDS**

```bash
# Terminal 1: API Server
cd /home/rober/projects/chatbot_nadia
PYTHONPATH=/home/rober/projects/chatbot_nadia python -m api.server

# Terminal 2: Dashboard
cd /home/rober/projects/chatbot_nadia
python dashboard/backend/static_server.py

# Terminal 3: Telegram Bot
cd /home/rober/projects/chatbot_nadia
python userbot.py

# Terminal 4: Monitor logs
tail -f logs/supervisor.log | grep -E "coherence|conflict"

# Browser: Open dashboard
http://localhost:3000
```

---

**Current Status**: COHERENCE SYSTEM 100% INTEGRATED ✅  
**Next Goal**: PRODUCTION VALIDATION & OPTIMIZATION 🎯  
**Estimated Time**: 4-5 hours for complete validation