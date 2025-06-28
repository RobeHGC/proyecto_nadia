-- Rollback Migration: Remove authentication tables
-- Date: June 28, 2025
-- Purpose: Rollback Epic 53 Session 1 authentication system if needed

-- WARNING: This will remove all authentication data!
-- Make sure to backup before running this rollback script

-- Step 1: Remove foreign key dependencies first
DROP INDEX IF EXISTS idx_sessions_user_id;
DROP INDEX IF EXISTS idx_permissions_user_id;
DROP INDEX IF EXISTS idx_audit_user_id;

-- Step 2: Drop tables in reverse dependency order
DROP TABLE IF EXISTS auth_audit_log;
DROP TABLE IF EXISTS user_permissions;
DROP TABLE IF EXISTS user_sessions;
DROP TABLE IF EXISTS users;

-- Step 3: Verify tables are removed
-- Run this query to confirm cleanup:
-- SELECT tablename FROM pg_tables 
-- WHERE schemaname = 'public' 
-- AND tablename IN ('users', 'user_sessions', 'user_permissions', 'auth_audit_log');
-- Should return 0 rows

-- Step 4: Clean up any remaining sequences
DROP SEQUENCE IF EXISTS users_id_seq CASCADE;
DROP SEQUENCE IF EXISTS user_sessions_id_seq CASCADE;
DROP SEQUENCE IF EXISTS user_permissions_id_seq CASCADE;
DROP SEQUENCE IF EXISTS auth_audit_log_id_seq CASCADE;

-- Step 5: Documentation
COMMENT ON SCHEMA public IS 'Authentication tables rolled back - using legacy API key only';

-- Post-rollback verification:
-- 1. Confirm tables removed: \dt users user_sessions user_permissions auth_audit_log
-- 2. Check for orphaned data: SELECT * FROM pg_tables WHERE tablename LIKE '%user%';
-- 3. Verify API server still works with legacy DASHBOARD_API_KEY
-- 4. Remove auth environment variables if desired:
--    - GOOGLE_OAUTH_CLIENT_ID
--    - GOOGLE_OAUTH_CLIENT_SECRET  
--    - GITHUB_OAUTH_CLIENT_ID
--    - GITHUB_OAUTH_CLIENT_SECRET
--    - JWT_SECRET_KEY