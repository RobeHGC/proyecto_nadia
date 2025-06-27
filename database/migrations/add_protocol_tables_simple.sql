-- Migration: Add Protocol de Silencio tables
-- Date: 2025-06-25

-- Table for protocol status
CREATE TABLE user_protocol_status (
    user_id TEXT PRIMARY KEY,
    status VARCHAR(20) NOT NULL DEFAULT 'INACTIVE' CHECK (status IN ('ACTIVE', 'INACTIVE')),
    activated_by TEXT,
    activated_at TIMESTAMPTZ,
    reason TEXT,
    messages_quarantined INTEGER DEFAULT 0,
    cost_saved_usd DECIMAL(10,4) DEFAULT 0.0000,
    last_message_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Audit trail for protocol changes
CREATE TABLE protocol_audit_log (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    action VARCHAR(20) NOT NULL CHECK (action IN ('ACTIVATED', 'DEACTIVATED', 'ONE_TIME_PASS')),
    performed_by TEXT NOT NULL,
    reason TEXT,
    previous_status VARCHAR(20),
    new_status VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Quarantine messages table
CREATE TABLE quarantine_messages (
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