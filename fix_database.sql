-- Fix database migrations with proper permissions
-- Run as: sudo -u postgres psql -d nadia_hitl -f fix_database.sql

-- Grant necessary permissions to current user first
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO CURRENT_USER;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO CURRENT_USER;

-- Add columns for tracking which LLM models were used
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='interactions' AND column_name='llm1_model') THEN
        ALTER TABLE interactions ADD COLUMN llm1_model VARCHAR(50);
    END IF;
END $$;

DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='interactions' AND column_name='llm2_model') THEN
        ALTER TABLE interactions ADD COLUMN llm2_model VARCHAR(50);
    END IF;
END $$;

-- Add columns for tracking individual LLM costs
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='interactions' AND column_name='llm1_cost_usd') THEN
        ALTER TABLE interactions ADD COLUMN llm1_cost_usd DECIMAL(8,6);
    END IF;
END $$;

DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='interactions' AND column_name='llm2_cost_usd') THEN
        ALTER TABLE interactions ADD COLUMN llm2_cost_usd DECIMAL(8,6);
    END IF;
END $$;

-- Create indexes only if they don't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_interactions_llm1_model') THEN
        CREATE INDEX idx_interactions_llm1_model ON interactions(llm1_model);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_interactions_llm2_model') THEN
        CREATE INDEX idx_interactions_llm2_model ON interactions(llm2_model);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_interactions_costs') THEN
        CREATE INDEX idx_interactions_costs ON interactions(llm1_cost_usd, llm2_cost_usd);
    END IF;
END $$;