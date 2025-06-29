-- Migration: Add Hybrid Memory Architecture Tables
-- Date: 2025-06-29
-- Description: Creates tables for procedural memory (prompt_library) and agent configuration

-- Create prompt_library table for procedural memory
CREATE TABLE IF NOT EXISTS prompt_library (
    id SERIAL PRIMARY KEY,
    prompt_id VARCHAR(100) UNIQUE NOT NULL,
    category VARCHAR(50) NOT NULL, -- 'persona', 'system', 'safety', 'context'
    name VARCHAR(100) NOT NULL,
    template TEXT NOT NULL,
    variables JSONB DEFAULT '{}', -- Dynamic variables for template substitution
    trigger_condition VARCHAR(200), -- Condition when this prompt should be used
    priority INTEGER DEFAULT 1, -- Higher priority prompts take precedence
    active BOOLEAN DEFAULT true,
    version INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create agent_config table for agent memory strategies
CREATE TABLE IF NOT EXISTS agent_config (
    agent_type VARCHAR(50) PRIMARY KEY, -- 'supervisor', 'llm1', 'llm2', 'constitution'
    memory_strategy VARCHAR(20) NOT NULL DEFAULT 'hybrid', -- 'redis_only', 'hybrid', 'full_persistent'
    context_window_tokens INTEGER DEFAULT 8000,
    compression_threshold DECIMAL(3,2) DEFAULT 0.75, -- When to compress context
    retrieval_k INTEGER DEFAULT 5, -- Number of memory items to retrieve
    temperature DECIMAL(3,2) DEFAULT 0.7,
    max_memory_age_days INTEGER DEFAULT 30, -- Max age before memory consolidation
    memory_tier_strategy VARCHAR(20) DEFAULT 'frequency', -- 'frequency', 'recency', 'importance'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_prompt_library_category ON prompt_library(category);
CREATE INDEX IF NOT EXISTS idx_prompt_library_trigger ON prompt_library(trigger_condition) WHERE trigger_condition IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_prompt_library_active ON prompt_library(active) WHERE active = true;

-- Insert default agent configurations
INSERT INTO agent_config (agent_type, memory_strategy, context_window_tokens, compression_threshold, retrieval_k, temperature) 
VALUES 
    ('supervisor', 'hybrid', 8000, 0.75, 5, 0.7),
    ('llm1', 'hybrid', 6000, 0.80, 3, 0.8),
    ('llm2', 'hybrid', 4000, 0.85, 2, 0.6),
    ('constitution', 'redis_only', 2000, 0.90, 1, 0.3)
ON CONFLICT (agent_type) DO NOTHING;

-- Insert default prompt templates
INSERT INTO prompt_library (prompt_id, category, name, template, variables, trigger_condition, priority)
VALUES 
    ('nadia_base_persona', 'persona', 'Nadia Base Personality', 
     'You are Nadia, a friendly 24-year-old medical student from Monterrey. Your personality: {{personality_traits}}. Current context: {{context_summary}}',
     '{"personality_traits": "warm, curious, empathetic", "context_summary": ""}',
     NULL, 10),
    
    ('memory_consolidation', 'system', 'Memory Consolidation Prompt',
     'Analyze this conversation for important memories to preserve: {{conversation_text}}. Extract: 1) Key facts, 2) Emotional moments, 3) User preferences',
     '{"conversation_text": ""}',
     'memory_consolidation_needed', 5),
     
    ('context_compression', 'system', 'Context Compression',
     'Summarize this conversation context while preserving: emotional tone, key facts, user preferences. Context: {{full_context}}',
     '{"full_context": ""}',
     'context_size_exceeded', 8),
     
    ('safety_filter', 'safety', 'Content Safety Check',
     'Analyze this message for safety concerns: {{message}}. Return: safe/unsafe and reason.',
     '{"message": ""}',
     'pre_send_safety_check', 9)
ON CONFLICT (prompt_id) DO NOTHING;

-- Create trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_agent_config_updated_at 
    BEFORE UPDATE ON agent_config 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_prompt_library_updated_at 
    BEFORE UPDATE ON prompt_library 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();