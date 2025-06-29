-- Migration: Add Memory-Related Columns to Existing Tables
-- Date: 2025-06-29
-- Description: Extends existing tables with memory management columns

-- Add memory management columns to user_current_status
ALTER TABLE user_current_status 
ADD COLUMN IF NOT EXISTS memory_tier VARCHAR(20) DEFAULT 'active' CHECK (memory_tier IN ('active', 'warm', 'cold', 'archived')),
ADD COLUMN IF NOT EXISTS last_memory_consolidation TIMESTAMPTZ DEFAULT NOW(),
ADD COLUMN IF NOT EXISTS memory_preferences JSONB DEFAULT '{}',
ADD COLUMN IF NOT EXISTS conversation_themes JSONB DEFAULT '[]',
ADD COLUMN IF NOT EXISTS emotional_profile JSONB DEFAULT '{}';

-- Add memory tracking to interactions table
ALTER TABLE interactions 
ADD COLUMN IF NOT EXISTS memory_importance DECIMAL(3,2) DEFAULT 0.5 CHECK (memory_importance >= 0 AND memory_importance <= 1),
ADD COLUMN IF NOT EXISTS consolidated BOOLEAN DEFAULT false,
ADD COLUMN IF NOT EXISTS memory_tags JSONB DEFAULT '[]',
ADD COLUMN IF NOT EXISTS emotional_context JSONB DEFAULT '{}',
ADD COLUMN IF NOT EXISTS retrieval_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS last_retrieved TIMESTAMPTZ;

-- Create memory_events table for tracking memory operations
CREATE TABLE IF NOT EXISTS memory_events (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    event_type VARCHAR(50) NOT NULL, -- 'consolidation', 'retrieval', 'compression', 'archival'
    source_table VARCHAR(50), -- 'interactions', 'user_current_status', etc.
    source_id INTEGER,
    details JSONB DEFAULT '{}',
    performance_metrics JSONB DEFAULT '{}', -- latency, tokens_saved, etc.
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_user_current_status_memory_tier ON user_current_status(memory_tier);
CREATE INDEX IF NOT EXISTS idx_user_current_status_consolidation ON user_current_status(last_memory_consolidation);
CREATE INDEX IF NOT EXISTS idx_interactions_importance ON interactions(memory_importance) WHERE memory_importance > 0.7;
CREATE INDEX IF NOT EXISTS idx_interactions_consolidated ON interactions(consolidated);
CREATE INDEX IF NOT EXISTS idx_interactions_retrieval ON interactions(retrieval_count) WHERE retrieval_count > 0;
CREATE INDEX IF NOT EXISTS idx_memory_events_user_type ON memory_events(user_id, event_type);
CREATE INDEX IF NOT EXISTS idx_memory_events_created ON memory_events(created_at);

-- Create function to update memory tier based on activity
CREATE OR REPLACE FUNCTION update_memory_tier()
RETURNS TRIGGER AS $$
BEGIN
    -- Update memory tier based on last activity
    IF OLD.last_interaction IS DISTINCT FROM NEW.last_interaction THEN
        IF NEW.last_interaction > NOW() - INTERVAL '7 days' THEN
            NEW.memory_tier := 'active';
        ELSIF NEW.last_interaction > NOW() - INTERVAL '30 days' THEN
            NEW.memory_tier := 'warm';
        ELSIF NEW.last_interaction > NOW() - INTERVAL '90 days' THEN
            NEW.memory_tier := 'cold';
        ELSE
            NEW.memory_tier := 'archived';
        END IF;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to automatically update memory tier
CREATE TRIGGER update_user_memory_tier 
    BEFORE UPDATE ON user_current_status 
    FOR EACH ROW EXECUTE FUNCTION update_memory_tier();

-- Update existing users to have proper memory tier
UPDATE user_current_status 
SET memory_tier = CASE 
    WHEN last_interaction > NOW() - INTERVAL '7 days' THEN 'active'
    WHEN last_interaction > NOW() - INTERVAL '30 days' THEN 'warm'
    WHEN last_interaction > NOW() - INTERVAL '90 days' THEN 'cold'
    ELSE 'archived'
END
WHERE memory_tier = 'active'; -- Only update default values

-- Insert initial memory event for existing users
INSERT INTO memory_events (user_id, event_type, details)
SELECT user_id, 'initialization', 
       jsonb_build_object('memory_tier', memory_tier, 'migration_date', NOW())
FROM user_current_status;