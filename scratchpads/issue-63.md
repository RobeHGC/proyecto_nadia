# Issue #63: API Server Dependency Fix

**GitHub Issue**: [#63 - API Server Does Not Work](https://github.com/RobeHGC/chatbot_nadia/issues/63)

## Root Cause Analysis

The API server fails to start due to a missing dependency for JWT token management:

```
ModuleNotFoundError: No module named 'jose'
```

**Location**: `auth/token_manager.py:8`  
**Import**: `from jose import jwt, JWTError`

## Problem Summary

The `python-jose` package is not defined in the project dependencies, but is required by the authentication system for JWT token operations. The pyproject.toml file has dependencies commented out (line 12), preventing proper package installation.

## Dependencies Analysis

From codebase analysis, the following dependencies are required but not defined:

### Critical (blocking API server):
- `python-jose[cryptography]` - JWT token operations
- `python-dotenv` - Environment variable loading
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `redis` - Redis operations

### Additional (from Epic 53 roadmap):
- `passlib[bcrypt]` - Password hashing for future auth enhancements
- `cryptography` - Encryption operations

## Implementation Plan

### Task 1: Update pyproject.toml Dependencies
- Uncomment and populate the dependencies section
- Add all required packages with appropriate version constraints
- Follow the pattern from the commented example

### Task 2: Install Dependencies
- Run pip install to verify package resolution
- Test import of critical modules

### Task 3: Test API Server Startup
- Run the API server startup command
- Verify no import errors
- Check basic endpoint functionality

### Task 4: Add Regression Test
- Create test to verify critical imports work
- Prevent future dependency issues

## Success Criteria

- [ ] API server starts without import errors
- [ ] JWT token operations functional
- [ ] All authentication routes accessible
- [ ] Dependencies properly defined in pyproject.toml
- [ ] Regression test added

## Risk Assessment

**Risk Level**: LOW  
**Impact**: HIGH (API server completely broken)  
**Confidence**: HIGH (straightforward dependency fix)

## Next Steps

1. Fix pyproject.toml dependencies
2. Test API server startup
3. Verify authentication functionality
4. Add regression test coverage