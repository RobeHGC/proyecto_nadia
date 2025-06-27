-- Migration: Create user_current_status and remove customer_status_transitions
-- Date: June 25, 2025
-- Purpose: Simplify to single current status table

-- Step 1: Create new simple status table
CREATE TABLE IF NOT EXISTS user_current_status (
    user_id TEXT PRIMARY KEY,
    customer_status VARCHAR(20) NOT NULL DEFAULT 'PROSPECT' CHECK (
        customer_status IN ('PROSPECT', 'LEAD_QUALIFIED', 'CUSTOMER', 'CHURNED', 'LEAD_EXHAUSTED')
    ),
    ltv_usd DECIMAL(8,2) DEFAULT 0.00,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Step 2: Create index for quick lookups
CREATE INDEX IF NOT EXISTS idx_user_current_status_updated ON user_current_status(updated_at DESC);

-- Step 3: Migrate data from interactions (most recent status per user)
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

-- Step 4: Migrate any additional data from customer_status_transitions
INSERT INTO user_current_status (user_id, customer_status, ltv_usd, updated_at)
SELECT DISTINCT ON (user_id)
    user_id,
    new_status,
    0.00,
    created_at
FROM customer_status_transitions
WHERE user_id IS NOT NULL
ORDER BY user_id, created_at DESC
ON CONFLICT (user_id) DO UPDATE SET
    customer_status = EXCLUDED.customer_status,
    updated_at = EXCLUDED.updated_at;

-- Step 5: Remove old table
DROP TABLE IF EXISTS customer_status_transitions;

-- Step 6: Add documentation
COMMENT ON TABLE user_current_status IS 'Single source of truth for current customer status per user';
COMMENT ON COLUMN user_current_status.customer_status IS 'Current funnel status: PROSPECT, LEAD_QUALIFIED, CUSTOMER, CHURNED, LEAD_EXHAUSTED';
COMMENT ON COLUMN user_current_status.ltv_usd IS 'User lifetime value in USD';