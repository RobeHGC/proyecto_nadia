# Epic 53 Session 1: Authentication & Authorization Overhaul

**GitHub Issue**: #60 - Epic 53: Security Hardening & Production Readiness  
**Session**: 1 of 5 - Authentication & Authorization Overhaul  
**Priority**: CRITICAL  
**Timeline**: Week 1 (Days 1-2)

## 🎯 Session 1 Objectives

Replace the current single API key authentication with a robust OAuth + RBAC system:
1. OAuth authentication (Google/GitHub)
2. Role-based access control (admin/reviewer/viewer)
3. Secure session management with JWT tokens
4. Protect all API endpoints with backward compatibility

## 🔍 Current State Analysis

### Existing Authentication System
- **Location**: `api/server.py:243-251`
- **Method**: Single API key from `DASHBOARD_API_KEY` env var
- **Protection**: All endpoints use `api_key: str = Depends(verify_api_key)`
- **Frontend**: Dashboard fetches API key from config endpoint
- **Security Issues**: 
  - No user differentiation
  - No role-based permissions
  - Single shared credential
  - No session management
  - No audit trail

## 📋 Implementation Tasks

### Phase 1: Database Schema (Task 1)
Create new tables for user management:
- `users` - User accounts with OAuth details
- `user_sessions` - Active session tracking
- `user_permissions` - Fine-grained permissions

### Phase 2: Auth Components (Task 2)
Create core authentication modules:
- `auth/oauth_provider.py` - OAuth provider integration
- `auth/token_manager.py` - JWT token handling
- `auth/rbac_manager.py` - Role-based access control
- `auth/session_manager.py` - Session lifecycle

### Phase 3: API Middleware (Task 3)
- `api/middleware/auth.py` - Authentication middleware
- `api/middleware/rbac.py` - Permission checking
- Update all endpoints with new decorators
- Maintain backward compatibility with existing API key

### Phase 4: Frontend Integration (Task 4)
- Add OAuth login flow to dashboard
- Implement token-based authentication
- Add user profile and logout functionality
- Update all API calls to use JWT tokens

## 🔧 Technical Design

### OAuth Flow
```
1. User clicks "Login with Google/GitHub"
2. Redirect to OAuth provider
3. Provider redirects back with code
4. Exchange code for user info
5. Create/update user record
6. Generate JWT token
7. Return token to frontend
```

### JWT Token Structure
```json
{
  "sub": "user_id",
  "email": "user@example.com",
  "role": "reviewer",
  "exp": 1234567890,
  "iat": 1234567800
}
```

### RBAC Permissions
- **admin**: Full access to all endpoints
- **reviewer**: Access to review queue and message approval
- **viewer**: Read-only access to dashboard

### Backward Compatibility Strategy
1. Check for JWT token first
2. Fall back to API key if no JWT
3. Log deprecation warning for API key usage
4. Remove API key support in future version

## 🚨 Risk Mitigation

### Risks
1. Breaking existing API integrations
2. OAuth provider downtime
3. Session management complexity
4. Token security concerns

### Mitigations
1. Gradual migration with fallback
2. Support multiple OAuth providers
3. Redis-based session storage
4. Short-lived tokens with refresh

## ✅ Success Criteria

- [ ] OAuth login working (Google/GitHub)
- [ ] Three user roles implemented
- [ ] All API endpoints protected
- [ ] Dashboard login/logout functional
- [ ] Session management working
- [ ] Backward compatibility maintained
- [ ] No performance degradation
- [ ] Security tests passing

## 🔗 Next Steps

1. Start with database schema creation
2. Build OAuth provider integration
3. Implement JWT token management
4. Update API middleware
5. Integrate with dashboard frontend
6. Test all authentication flows
7. Document setup and migration

---

**Session Status**: Ready to implement  
**Next Action**: Create database migration for user tables