-- Migration: Add CUSTOMER_STATUS dimension to interactions table
-- Date: June 21, 2025
-- Purpose: Track customer status progression through sales funnel

-- Add CUSTOMER_STATUS column with enum-like constraints
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS customer_status VARCHAR(20) DEFAULT 'PROSPECT' CHECK (
    customer_status IN ('PROSPECT', 'LEAD_QUALIFIED', 'CUSTOMER', 'CHURNED', 'LEAD_EXHAUSTED')
);

-- Add CTA tracking columns
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS cta_sent_count INTEGER DEFAULT 0;
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS cta_response_type VARCHAR(20) CHECK (
    cta_response_type IN ('IGNORED', 'POLITE_DECLINE', 'INTERESTED', 'CONVERTED', 'RUDE_DECLINE')
);
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS last_cta_sent_at TIMESTAMPTZ;
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS conversion_date TIMESTAMPTZ;
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS ltv_usd DECIMAL(8,2) DEFAULT 0.00;

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_interactions_customer_status ON interactions(customer_status);
CREATE INDEX IF NOT EXISTS idx_interactions_user_customer_status ON interactions(user_id, customer_status);
CREATE INDEX IF NOT EXISTS idx_interactions_cta_response ON interactions(cta_response_type);

-- Create customer status transition log table
CREATE TABLE IF NOT EXISTS customer_status_transitions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id TEXT NOT NULL,
    interaction_id UUID REFERENCES interactions(id),
    previous_status VARCHAR(20),
    new_status VARCHAR(20) NOT NULL,
    reason TEXT,
    automated BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for transitions table
CREATE INDEX IF NOT EXISTS idx_status_transitions_user ON customer_status_transitions(user_id);
CREATE INDEX IF NOT EXISTS idx_status_transitions_date ON customer_status_transitions(created_at DESC);

-- Create view for customer funnel analysis
CREATE OR REPLACE VIEW customer_funnel_metrics AS
SELECT 
    customer_status,
    COUNT(*) as interaction_count,
    COUNT(DISTINCT user_id) as unique_users,
    AVG(cta_sent_count) as avg_ctas_sent,
    COUNT(CASE WHEN conversion_date IS NOT NULL THEN 1 END) as converted_count,
    SUM(ltv_usd) as total_ltv,
    AVG(ltv_usd) as avg_ltv
FROM interactions
WHERE customer_status IS NOT NULL
GROUP BY customer_status
ORDER BY 
    CASE customer_status
        WHEN 'PROSPECT' THEN 1
        WHEN 'LEAD_QUALIFIED' THEN 2  
        WHEN 'CUSTOMER' THEN 3
        WHEN 'CHURNED' THEN 4
        WHEN 'LEAD_EXHAUSTED' THEN 5
    END;

-- Create view for current user status (latest per user)
CREATE OR REPLACE VIEW user_customer_status AS
SELECT DISTINCT ON (user_id)
    user_id,
    customer_status,
    cta_sent_count,
    last_cta_sent_at,
    conversion_date,
    ltv_usd,
    created_at as last_interaction
FROM interactions
WHERE customer_status IS NOT NULL
ORDER BY user_id, created_at DESC;

-- Function to update customer status based on CTA interactions
CREATE OR REPLACE FUNCTION update_customer_status(
    p_user_id TEXT,
    p_interaction_id UUID,
    p_cta_response_type TEXT DEFAULT NULL,
    p_converted BOOLEAN DEFAULT FALSE,
    p_ltv_amount DECIMAL DEFAULT 0.00
) RETURNS TEXT AS $$
DECLARE
    current_status TEXT;
    new_status TEXT;
    cta_count INTEGER;
BEGIN
    -- Get current status and CTA count for this user
    SELECT customer_status, COALESCE(cta_sent_count, 0)
    INTO current_status, cta_count
    FROM interactions 
    WHERE user_id = p_user_id 
    ORDER BY created_at DESC 
    LIMIT 1;
    
    -- Default to PROSPECT if no previous interaction
    IF current_status IS NULL THEN
        current_status := 'PROSPECT';
        cta_count := 0;
    END IF;
    
    -- Determine new status based on response and business rules
    IF p_converted THEN
        new_status := 'CUSTOMER';
    ELSIF p_cta_response_type = 'POLITE_DECLINE' AND cta_count <= 3 THEN
        new_status := 'LEAD_QUALIFIED';
    ELSIF p_cta_response_type = 'RUDE_DECLINE' OR cta_count > 5 THEN
        new_status := 'LEAD_EXHAUSTED';
    ELSIF p_cta_response_type = 'INTERESTED' THEN
        new_status := 'LEAD_QUALIFIED';
    ELSE
        new_status := current_status; -- No change
    END IF;
    
    -- Update interaction with new status
    UPDATE interactions 
    SET 
        customer_status = new_status,
        cta_response_type = p_cta_response_type,
        ltv_usd = COALESCE(ltv_usd, 0) + p_ltv_amount,
        conversion_date = CASE WHEN p_converted THEN NOW() ELSE conversion_date END
    WHERE id = p_interaction_id;
    
    -- Log status transition if status changed
    IF new_status != current_status THEN
        INSERT INTO customer_status_transitions (
            user_id, interaction_id, previous_status, new_status, 
            reason, automated
        ) VALUES (
            p_user_id, p_interaction_id, current_status, new_status,
            'CTA response: ' || COALESCE(p_cta_response_type, 'none'), TRUE
        );
    END IF;
    
    RETURN new_status;
END;
$$ LANGUAGE plpgsql;

-- Update comments for documentation
COMMENT ON COLUMN interactions.customer_status IS 'Customer funnel status: PROSPECT (no CTA), LEAD_QUALIFIED (engaged), CUSTOMER (converted), CHURNED (stopped paying), LEAD_EXHAUSTED (no potential)';
COMMENT ON COLUMN interactions.cta_sent_count IS 'Number of CTAs sent to this user';
COMMENT ON COLUMN interactions.cta_response_type IS 'How user responded to latest CTA';
COMMENT ON COLUMN interactions.ltv_usd IS 'User lifetime value in USD';
COMMENT ON VIEW customer_funnel_metrics IS 'Conversion funnel analytics by customer status';