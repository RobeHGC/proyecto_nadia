-- Migration: Add Recovery System Tables and Fields
-- Date: December 26, 2025
-- Purpose: Enable "Sin Dejar a Nadie Atrás" (Recovery Agent) functionality

BEGIN;

-- 1. Add recovery fields to existing interactions table
ALTER TABLE interactions 
ADD COLUMN telegram_message_id BIGINT,
ADD COLUMN telegram_date TIMESTAMPTZ,
ADD COLUMN is_recovered_message BOOLEAN DEFAULT FALSE;

-- 2. Create message processing cursors table
-- Tracks the last processed message for each user to avoid duplicates
CREATE TABLE message_processing_cursors (
    user_id TEXT PRIMARY KEY,
    last_processed_telegram_id BIGINT NOT NULL,
    last_processed_telegram_date TIMESTAMPTZ NOT NULL,
    last_recovery_check TIMESTAMPTZ DEFAULT NOW(),
    total_recovered_messages INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Create recovery operations audit log
-- Tracks all recovery operations for monitoring and debugging
CREATE TABLE recovery_operations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    operation_type TEXT NOT NULL CHECK (operation_type IN ('startup', 'periodic', 'manual')),
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    users_checked INTEGER DEFAULT 0,
    messages_recovered INTEGER DEFAULT 0,
    messages_skipped INTEGER DEFAULT 0,
    errors_encountered INTEGER DEFAULT 0,
    status TEXT DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed')),
    error_details JSONB,
    metadata JSONB
);

-- 4. Create performance-optimized indexes
-- For efficient lookups by user and telegram message ID
CREATE INDEX idx_interactions_telegram_id ON interactions(user_id, telegram_message_id) 
WHERE telegram_message_id IS NOT NULL;

-- For efficient date-based queries (most recent first)
CREATE INDEX idx_interactions_telegram_date ON interactions(user_id, telegram_date DESC) 
WHERE telegram_date IS NOT NULL;

-- For efficient recovery message filtering
CREATE INDEX idx_interactions_recovered ON interactions(user_id, is_recovered_message) 
WHERE is_recovered_message = TRUE;

-- For cursor table performance
CREATE INDEX idx_cursors_last_check ON message_processing_cursors(last_recovery_check);

-- For recovery operations monitoring
CREATE INDEX idx_recovery_ops_status ON recovery_operations(status, started_at DESC);
CREATE INDEX idx_recovery_ops_type ON recovery_operations(operation_type, started_at DESC);

-- 5. Add trigger to update cursors.updated_at automatically
CREATE OR REPLACE FUNCTION update_cursor_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_cursor_timestamp
    BEFORE UPDATE ON message_processing_cursors
    FOR EACH ROW
    EXECUTE FUNCTION update_cursor_timestamp();

-- 6. Add comments for documentation
COMMENT ON COLUMN interactions.telegram_message_id IS 'Telegram message ID for recovery tracking';
COMMENT ON COLUMN interactions.telegram_date IS 'Original Telegram message timestamp';
COMMENT ON COLUMN interactions.is_recovered_message IS 'True if message was recovered during downtime';

COMMENT ON TABLE message_processing_cursors IS 'Tracks last processed message per user for recovery';
COMMENT ON TABLE recovery_operations IS 'Audit log of all recovery operations';

-- 7. Grant permissions (adjust as needed for your setup)
-- GRANT SELECT, INSERT, UPDATE ON message_processing_cursors TO your_app_user;
-- GRANT SELECT, INSERT, UPDATE ON recovery_operations TO your_app_user;

COMMIT;

-- Success message
\echo 'Recovery system migration completed successfully'
\echo 'Tables created: message_processing_cursors, recovery_operations'
\echo 'Fields added: interactions.telegram_message_id, telegram_date, is_recovered_message'
\echo 'Indexes created: 6 performance-optimized indexes'