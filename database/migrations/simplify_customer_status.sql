-- Migration: Simplify customer status to single source of truth
-- Date: June 24, 2025
-- Purpose: Replace complex status tracking with simple current status table

-- Create simple user status table
CREATE TABLE IF NOT EXISTS user_current_status (
    user_id TEXT PRIMARY KEY,
    customer_status VARCHAR(20) NOT NULL DEFAULT 'PROSPECT' CHECK (
        customer_status IN ('PROSPECT', 'LEAD_QUALIFIED', 'CUSTOMER', 'CHURNED', 'LEAD_EXHAUSTED')
    ),
    ltv_usd DECIMAL(8,2) DEFAULT 0.00,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index for quick lookups
CREATE INDEX IF NOT EXISTS idx_user_current_status_updated ON user_current_status(updated_at DESC);

-- Migrate existing data from interactions table (get latest status per user)
INSERT INTO user_current_status (user_id, customer_status, ltv_usd, updated_at)
SELECT DISTINCT ON (user_id)
    user_id,
    COALESCE(customer_status, 'PROSPECT'),
    COALESCE(ltv_usd, 0.00),
    created_at
FROM interactions
WHERE user_id IS NOT NULL
ORDER BY user_id, created_at DESC
ON CONFLICT (user_id) DO NOTHING;

-- Add comment for documentation
COMMENT ON TABLE user_current_status IS 'Single source of truth for current customer status per user';
COMMENT ON COLUMN user_current_status.customer_status IS 'Current funnel status: PROSPECT, LEAD_QUALIFIED, CUSTOMER, CHURNED, LEAD_EXHAUSTED';
COMMENT ON COLUMN user_current_status.ltv_usd IS 'User lifetime value in USD';

-- Note: We keep the existing tables for now to maintain backward compatibility
-- They can be removed in a future migration after verifying everything works