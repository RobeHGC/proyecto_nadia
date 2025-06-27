# Issue #30 Phase 2: Complete Test Coverage Plan

**Created**: June 27, 2025  
**Phase 1 PR**: #46 (10/50 tests fixed)  
**Objective**: Fix remaining 40+ tests to achieve 100% pass rate

## Current State (After Phase 1)

### Test Coverage Summary
- **Total Tests**: ~50
- **Passing**: 10 (20%)
- **Failing/Skipped**: ~40 (80%)

### By Component
| Component | Passing | Total | Coverage | Status |
|-----------|---------|-------|----------|---------|
| Coherence | 1 | 1 | 100% | ✅ Complete |
| Recovery Agent | 3 | 11 | 27% | ⚠️ Needs work |
| Protocol Manager | 1 | 20 | 5% | ❌ Critical |
| Protocol API | 5 | 19 | 26% | ⚠️ Needs work |

## Phase 2 Implementation Plan

### 1. Recovery Agent Tests (8 remaining)
**File**: `tests/test_recovery_agent.py`

#### Tests to Fix:
- `test_identify_recovery_gaps` - Missing method `_identify_recovery_gaps`
- `test_process_recovery_batch` - Wrong fixture name `mock_telegram`
- `test_rate_limiting` - Missing method `_check_rate_limit`
- `test_health_check` - Missing method `get_health_status`
- `test_quarantine_skip` - Import ProtocolManager incorrectly
- `test_error_handling` - Wrong fixture name
- `test_max_message_age_limit` - Wrong method name
- `test_concurrent_recovery_limit` - Missing methods

#### Fix Strategy:
```python
# Add to conftest.py
@pytest.fixture
def async_telegram_history():
    history = AsyncMock()
    history.scan_all_dialogs = AsyncMock(return_value=[])
    return history
```

### 2. Protocol Manager Tests (19 remaining)
**File**: `tests/test_protocol_manager.py`

#### Key Issues:
- All tests try to access `protocol_manager._redis_mock` which doesn't exist
- Missing proper Redis connection mocking
- Incorrect initialization patterns

#### Fix Strategy:
```python
# Update all tests to use proper mocking
@patch('utils.protocol_manager.ProtocolManager._get_redis')
async def test_example(self, mock_redis):
    mock_redis.return_value = AsyncMock()
    # ... rest of test
```

### 3. Protocol API Tests (14 remaining)
**File**: `tests/test_protocol_api_integration.py`

#### Tests to Fix:
- `test_get_quarantine_messages_with_filters` - Response format issue
- `test_process_quarantine_message_success` - Missing user_id already fixed
- `test_batch_process_quarantine_messages` - JSON body formatting
- `test_unauthorized_access` - Auth testing needs adjustment
- `test_error_handling_database_failure` - Mock exception handling

#### Common Issues:
- Missing `app.dependency_overrides.clear()` in many tests
- Response format assumptions incorrect
- Error message assertions too generic

## Technical Improvements Needed

### 1. Create Shared Test Fixtures
```python
# tests/conftest.py additions

@pytest.fixture
def mock_async_db():
    """Consistent async database mock."""
    db = AsyncMock()
    # Set default return values
    db.get_active_protocol_users = AsyncMock(return_value=[])
    db.get_quarantine_messages = AsyncMock(return_value=[])
    yield db

@pytest.fixture
def clean_app_overrides():
    """Ensure app overrides are cleaned."""
    yield
    from api.server import app
    app.dependency_overrides.clear()
```

### 2. Improve Error Assertions
```python
# Instead of generic assertions
assert "detail" in response_data

# Use specific assertions
assert response.status_code == 422
error_detail = response_data["detail"][0]
assert error_detail["loc"] == ["query", "action"]
assert "ensure this value is in" in error_detail["msg"]
```

### 3. Consistent Async Patterns
```python
# Create helper for all async mocks
def make_async_mock(return_value=None, side_effect=None):
    async def async_func(*args, **kwargs):
        if side_effect:
            raise side_effect
        return return_value
    return async_func
```

## Execution Plan

### Week 1: Recovery & Protocol Manager
- [ ] Fix Recovery Agent tests (8 tests)
- [ ] Fix Protocol Manager initialization tests (5 tests)
- [ ] Add shared fixtures to conftest.py

### Week 2: Protocol API & Integration
- [ ] Fix Protocol API response format tests (7 tests)
- [ ] Fix Protocol API error handling tests (7 tests)
- [ ] Fix remaining Protocol Manager tests (14 tests)

### Week 3: Polish & Documentation
- [ ] Improve all error assertions
- [ ] Add consistent cleanup patterns
- [ ] Update CLAUDE.md with test patterns
- [ ] Create GitHub Action for test suite

## Success Criteria

1. **100% Test Pass Rate**: All ~50 tests passing
2. **No Skipped Tests**: All async issues resolved
3. **Consistent Patterns**: Shared fixtures and helpers used
4. **Proper Cleanup**: All tests clean up properly
5. **Clear Assertions**: Specific error message validation

## Risk Mitigation

- **Incremental Approach**: Fix tests in small batches
- **Component Focus**: Complete one component before moving to next
- **Regular Validation**: Run full test suite after each batch
- **Documentation**: Update patterns in CLAUDE.md as we go

## Notes

- Priority: Protocol Manager (most broken) → Recovery Agent → Protocol API
- Consider adding integration tests for cross-component interactions
- May discover actual bugs while fixing tests - document separately

---

**Next Step**: Create Issue #47 for Phase 2 implementation