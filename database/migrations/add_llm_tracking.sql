-- database/migrations/add_llm_tracking.sql
-- Migration to add multi-LLM tracking columns to interactions table

-- Add columns for tracking which LLM models were used
ALTER TABLE interactions ADD COLUMN llm1_model VARCHAR(50);
ALTER TABLE interactions ADD COLUMN llm2_model VARCHAR(50);

-- Add columns for tracking individual LLM costs
ALTER TABLE interactions ADD COLUMN llm1_cost_usd DECIMAL(8,6);
ALTER TABLE interactions ADD COLUMN llm2_cost_usd DECIMAL(8,6);

-- Create indexes for efficient querying by model
CREATE INDEX idx_interactions_llm1_model ON interactions(llm1_model);
CREATE INDEX idx_interactions_llm2_model ON interactions(llm2_model);

-- Create index for cost analysis
CREATE INDEX idx_interactions_costs ON interactions(llm1_cost_usd, llm2_cost_usd);

-- Add comments for documentation
COMMENT ON COLUMN interactions.llm1_model IS 'Model used for creative LLM-1 generation';
COMMENT ON COLUMN interactions.llm2_model IS 'Model used for refinement LLM-2 generation';
COMMENT ON COLUMN interactions.llm1_cost_usd IS 'Cost in USD for LLM-1 generation';
COMMENT ON COLUMN interactions.llm2_cost_usd IS 'Cost in USD for LLM-2 generation';