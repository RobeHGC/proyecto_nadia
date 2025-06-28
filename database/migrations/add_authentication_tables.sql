-- Migration: Add authentication and authorization tables
-- Date: June 28, 2025
-- Purpose: Replace single API key with OAuth + RBAC system (Epic 53 Session 1)

-- Step 1: Create users table for OAuth accounts
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    role VARCHAR(50) NOT NULL DEFAULT 'viewer' CHECK (
        role IN ('admin', 'reviewer', 'viewer')
    ),
    oauth_provider VARCHAR(50) NOT NULL CHECK (
        oauth_provider IN ('google', 'github')
    ),
    oauth_id VARCHAR(255) NOT NULL,
    avatar_url VARCHAR(500),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_login TIMESTAMPTZ,
    UNIQUE(oauth_provider, oauth_id)
);

-- Step 2: Create user sessions table for JWT token tracking
CREATE TABLE IF NOT EXISTS user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) UNIQUE NOT NULL,
    refresh_token_hash VARCHAR(255) UNIQUE,
    ip_address INET,
    user_agent TEXT,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_activity TIMESTAMPTZ DEFAULT NOW(),
    is_active BOOLEAN DEFAULT true
);

-- Step 3: Create user permissions table for fine-grained access control
CREATE TABLE IF NOT EXISTS user_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    resource VARCHAR(100) NOT NULL,
    action VARCHAR(50) NOT NULL,
    granted_by UUID REFERENCES users(id),
    granted_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    UNIQUE(user_id, resource, action)
);

-- Step 4: Create audit log table for security tracking
CREATE TABLE IF NOT EXISTS auth_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    event_type VARCHAR(50) NOT NULL CHECK (
        event_type IN ('login', 'logout', 'login_failed', 'token_refresh', 
                      'permission_denied', 'role_changed', 'permission_granted',
                      'session_expired', 'password_reset')
    ),
    ip_address INET,
    user_agent TEXT,
    details JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Step 5: Create indexes for performance
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_oauth ON users(oauth_provider, oauth_id);
CREATE INDEX idx_users_role ON users(role) WHERE is_active = true;
CREATE INDEX idx_users_last_login ON users(last_login DESC);

CREATE INDEX idx_sessions_user_id ON user_sessions(user_id);
CREATE INDEX idx_sessions_token ON user_sessions(token_hash);
CREATE INDEX idx_sessions_expires ON user_sessions(expires_at) WHERE is_active = true;

CREATE INDEX idx_permissions_user_id ON user_permissions(user_id);
CREATE INDEX idx_permissions_resource ON user_permissions(resource, action);

CREATE INDEX idx_audit_user_id ON auth_audit_log(user_id);
CREATE INDEX idx_audit_event ON auth_audit_log(event_type);
CREATE INDEX idx_audit_created ON auth_audit_log(created_at DESC);

-- Step 6: Create default admin user (to be updated with first OAuth login)
-- This ensures there's always an admin to grant permissions
INSERT INTO users (email, name, role, oauth_provider, oauth_id)
VALUES ('admin@nadia-hitl.com', 'System Admin', 'admin', 'google', 'pending-first-login')
ON CONFLICT (email) DO NOTHING;

-- Step 7: Add helpful comments
COMMENT ON TABLE users IS 'OAuth authenticated users with role-based access';
COMMENT ON TABLE user_sessions IS 'Active JWT sessions with expiration tracking';
COMMENT ON TABLE user_permissions IS 'Fine-grained permissions beyond basic roles';
COMMENT ON TABLE auth_audit_log IS 'Security audit trail for authentication events';

COMMENT ON COLUMN users.role IS 'Basic role: admin (full access), reviewer (approve messages), viewer (read-only)';
COMMENT ON COLUMN user_sessions.token_hash IS 'SHA256 hash of JWT access token';
COMMENT ON COLUMN user_sessions.refresh_token_hash IS 'SHA256 hash of refresh token';
COMMENT ON COLUMN user_permissions.resource IS 'Resource path like "api/messages" or "dashboard/settings"';
COMMENT ON COLUMN user_permissions.action IS 'Action like "read", "write", "delete", "approve"';