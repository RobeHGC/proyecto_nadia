# Authentication Setup Guide - Epic 53 Session 1

This guide covers the setup and configuration of the new OAuth + RBAC authentication system implemented in Epic 53 Session 1.

## Overview

The NADIA HITL system now supports:
- **OAuth Authentication** (Google/GitHub)
- **Role-Based Access Control** (admin/reviewer/viewer)
- **JWT Session Management** with refresh tokens
- **Security Audit Logging**
- **Backward compatibility** with legacy API key

## Prerequisites

1. PostgreSQL database
2. Redis server
3. OAuth provider credentials (Google and/or GitHub)
4. Environment variables configured

## Step 1: Database Migration

Run the authentication tables migration:

```bash
# Run the migration script
python scripts/run_auth_migration.py

# Verify tables were created
psql $DATABASE_URL -c "\dt users user_sessions user_permissions auth_audit_log"
```

### Expected Tables
- `users` - OAuth user accounts
- `user_sessions` - JWT session tracking
- `user_permissions` - Fine-grained permissions
- `auth_audit_log` - Security audit trail

## Step 2: OAuth Provider Setup

### Google OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create or select a project
3. Enable the Google+ API
4. Create OAuth 2.0 credentials
5. Add authorized redirect URIs:
   - `http://localhost:3000/auth/callback` (development)
   - `https://yourdomain.com/auth/callback` (production)

### GitHub OAuth Setup

1. Go to GitHub Settings > Developer settings > OAuth Apps
2. Create a new OAuth App
3. Set Authorization callback URL to:
   - `http://localhost:3000/auth/callback` (development)
   - `https://yourdomain.com/auth/callback` (production)

## Step 3: Environment Variables

Add these environment variables:

```bash
# OAuth Providers
GOOGLE_OAUTH_CLIENT_ID=your-google-client-id
GOOGLE_OAUTH_CLIENT_SECRET=your-google-client-secret
GITHUB_OAUTH_CLIENT_ID=your-github-client-id
GITHUB_OAUTH_CLIENT_SECRET=your-github-client-secret

# OAuth Configuration
OAUTH_REDIRECT_URI=http://localhost:3000/auth/callback
FRONTEND_URL=http://localhost:3000

# JWT Configuration
JWT_SECRET_KEY=your-secure-secret-key-here
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30

# Session Configuration  
SESSION_TIMEOUT_MINUTES=30
MAX_SESSIONS_PER_USER=5

# Legacy compatibility (optional)
DASHBOARD_API_KEY=your-existing-api-key
```

## Step 4: Start Services

Start the API server with authentication enabled:

```bash
# Start API server
PYTHONPATH=/home/rober/projects/chatbot_nadia python -m api.server

# Start dashboard (with OAuth support)
python dashboard/backend/static_server.py
```

## Step 5: User Roles and Permissions

### Role Hierarchy
- **admin**: Full system access, user management
- **reviewer**: Message approval/rejection, analytics access
- **viewer**: Read-only access to dashboard

### Permission System
The system uses fine-grained permissions:
- `message:approve` - Approve messages
- `message:reject` - Reject messages
- `user:manage_roles` - Change user roles
- `dashboard:settings` - Access settings
- And more...

### Setting User Roles

By default, new users get the `viewer` role. To promote users:

```sql
-- Promote user to reviewer
UPDATE users SET role = 'reviewer' WHERE email = 'user@example.com';

-- Promote user to admin
UPDATE users SET role = 'admin' WHERE email = 'admin@example.com';
```

## Step 6: Testing Authentication

### API Endpoints

Test the authentication endpoints:

```bash
# Health check (no auth required)
curl http://localhost:8000/health

# OAuth login initiation
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"provider": "google"}'

# Get current user (requires JWT token)
curl http://localhost:8000/auth/me \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Dashboard Login

1. Navigate to `http://localhost:3000`
2. Click "Login with Google" or "Login with GitHub"
3. Complete OAuth flow
4. Verify login and role-based access

## Migration from Legacy API Key

The system maintains backward compatibility:

1. **Immediate**: Both JWT and API key work
2. **Transition**: Users migrate to OAuth gradually
3. **Future**: API key support can be removed

To check legacy usage:
```bash
# Check logs for legacy API key warnings
grep "Legacy API key used" logs/api.log
```

## Security Features

### Session Management
- JWT access tokens (30 min default)
- Refresh tokens (30 days default)
- Maximum 5 sessions per user
- Automatic session cleanup

### Rate Limiting (NEW)
Authentication endpoints are protected with rate limits:
- `/auth/login`: 5 requests per 5 minutes (15 min block on violation)
- `/auth/refresh`: 10 requests per 5 minutes (10 min block on violation)
- `/auth/callback`: 20 requests per 5 minutes (OAuth flow support)

### Token Blacklisting (NEW)
Compromised tokens can be immediately revoked:
```python
# Blacklist a compromised token
from auth.token_blacklist import token_blacklist
await token_blacklist.revoke_compromised_token(token, "security_breach")
```

### Audit Logging
All authentication events are logged:
```sql
-- View recent auth events
SELECT event_type, user_id, ip_address, created_at 
FROM auth_audit_log 
ORDER BY created_at DESC 
LIMIT 10;
```

### RBAC Protection
All endpoints are protected by role-based permissions:
```python
# Example: Only reviewers can approve messages
@require_permission(Permission.MESSAGE_APPROVE)
async def approve_review(review_id: str, current_user: dict):
    # Implementation
```

## Troubleshooting

### Common Issues

1. **Database Migration Fails**
   ```bash
   # Check database connection
   python scripts/test_db_connection.py
   
   # Verify DATABASE_URL
   echo $DATABASE_URL
   ```

2. **OAuth Redirect Mismatch**
   - Verify OAUTH_REDIRECT_URI matches OAuth provider settings
   - Check CORS configuration in API server

3. **JWT Token Issues**
   - Verify JWT_SECRET_KEY is set
   - Check token expiration settings
   - Ensure system clocks are synchronized

4. **Permission Denied**
   - Check user role in database
   - Verify endpoint permission requirements
   - Check audit logs for details

### Debug Mode

Enable debug logging:
```bash
export LOG_LEVEL=DEBUG
python -m api.server
```

### Health Checks

```bash
# API health
curl http://localhost:8000/health

# Database connectivity
python scripts/test_db_connection.py

# Redis connectivity
redis-cli ping

# Test authentication endpoints
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"provider": "google"}'
```

### Migration Rollback (NEW)

If authentication migration needs to be rolled back:

```bash
# DANGEROUS: This removes all authentication data!
python scripts/rollback_auth_migration.py

# Follow prompts to confirm rollback
# System will revert to legacy API key only
```

**Rollback includes:**
- Automatic data backup before rollback
- Complete removal of authentication tables
- Verification of legacy API key functionality
- Step-by-step rollback documentation

## Production Deployment

### Security Checklist
- [ ] Use HTTPS for all OAuth redirects
- [ ] Set secure JWT_SECRET_KEY (32+ characters)
- [ ] Configure proper CORS origins
- [ ] Set up SSL/TLS certificates
- [ ] Enable audit log monitoring
- [ ] Configure session timeout policies
- [ ] Set up OAuth provider monitoring

### Environment Variables
Update production environment variables:
```bash
OAUTH_REDIRECT_URI=https://yourdomain.com/auth/callback
FRONTEND_URL=https://yourdomain.com
ALLOWED_ORIGINS=https://yourdomain.com
```

### Monitoring
Monitor authentication health:
- Failed login attempts
- Session creation/destruction
- Permission denied events
- OAuth provider availability

## Next Steps

After completing Session 1:
1. **Session 2**: Rate limiting and DoS protection
2. **Session 3**: Data encryption at rest
3. **Session 4**: Redis high availability
4. **Session 5**: Security audit and compliance

## Support

For issues or questions:
1. Check logs: `tail -f logs/api.log`
2. Review audit trail: `SELECT * FROM auth_audit_log ORDER BY created_at DESC`
3. Test endpoints: Use provided curl examples
4. Verify configuration: Check environment variables

---

**Epic 53 Session 1 Complete**: Authentication & Authorization Overhaul ✅  
**Next Session**: Rate Limiting & DoS Protection 🛡️