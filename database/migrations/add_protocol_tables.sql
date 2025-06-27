-- Migration: Add Protocol de Silencio tables
-- Date: 2025-06-25
-- Purpose: Implement silence protocol for managing time-waster users

-- Table for protocol status
CREATE TABLE IF NOT EXISTS user_protocol_status (
    user_id TEXT PRIMARY KEY,
    status VARCHAR(20) NOT NULL DEFAULT 'INACTIVE' CHECK (status IN ('ACTIVE', 'INACTIVE')),
    activated_by TEXT, -- reviewer email/id who activated
    activated_at TIMESTAMPTZ,
    reason TEXT, -- optional reason for activation
    messages_quarantined INTEGER DEFAULT 0,
    cost_saved_usd DECIMAL(10,4) DEFAULT 0.0000, -- track saved costs
    last_message_at TIMESTAMPTZ, -- last quarantined message timestamp
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Audit trail for protocol changes
CREATE TABLE IF NOT EXISTS protocol_audit_log (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    action VARCHAR(20) NOT NULL CHECK (action IN ('ACTIVATED', 'DEACTIVATED', 'ONE_TIME_PASS')),
    performed_by TEXT NOT NULL,
    reason TEXT,
    previous_status VARCHAR(20),
    new_status VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Quarantine messages table (for persistent storage)
CREATE TABLE IF NOT EXISTS quarantine_messages (
    id SERIAL PRIMARY KEY,
    message_id TEXT UNIQUE NOT NULL,
    user_id TEXT NOT NULL,
    message_text TEXT NOT NULL,
    telegram_message_id INTEGER,
    received_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '7 days'),
    processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMPTZ,
    processed_by TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_protocol_status_active ON user_protocol_status(status) WHERE status = 'ACTIVE';
CREATE INDEX idx_protocol_updated ON user_protocol_status(updated_at DESC);
CREATE INDEX idx_audit_user_created ON protocol_audit_log(user_id, created_at DESC);
CREATE INDEX idx_quarantine_user_expires ON quarantine_messages(user_id, expires_at) WHERE NOT processed;
CREATE INDEX idx_quarantine_expires ON quarantine_messages(expires_at) WHERE NOT processed;

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for user_protocol_status
CREATE TRIGGER update_user_protocol_status_updated_at BEFORE UPDATE
    ON user_protocol_status FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Comments for documentation
COMMENT ON TABLE user_protocol_status IS 'Tracks silence protocol status for users to manage time-wasters';
COMMENT ON TABLE protocol_audit_log IS 'Audit trail for all protocol status changes';
COMMENT ON TABLE quarantine_messages IS 'Stores quarantined messages with auto-expiration';
COMMENT ON COLUMN user_protocol_status.cost_saved_usd IS 'Cumulative LLM costs saved by quarantining messages';
COMMENT ON COLUMN quarantine_messages.expires_at IS 'Messages auto-expire after 7 days if not processed';