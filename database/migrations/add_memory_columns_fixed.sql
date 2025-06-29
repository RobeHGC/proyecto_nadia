-- Migration: Add Memory-Related Columns (Fixed Version)
-- Date: 2025-06-29
-- Description: Extends existing tables with memory management columns (permission-safe)

-- Create memory_user_profiles table instead of altering existing tables
CREATE TABLE IF NOT EXISTS memory_user_profiles (
    user_id TEXT PRIMARY KEY,
    memory_tier VARCHAR(20) DEFAULT 'active' CHECK (memory_tier IN ('active', 'warm', 'cold', 'archived')),
    last_memory_consolidation TIMESTAMPTZ DEFAULT NOW(),
    memory_preferences JSONB DEFAULT '{}',
    conversation_themes JSONB DEFAULT '[]',
    emotional_profile JSONB DEFAULT '{}',
    total_interactions INTEGER DEFAULT 0,
    last_interaction TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create memory_interaction_metadata table for interaction-specific memory data
CREATE TABLE IF NOT EXISTS memory_interaction_metadata (
    interaction_id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL,
    memory_importance DECIMAL(3,2) DEFAULT 0.5 CHECK (memory_importance >= 0 AND memory_importance <= 1),
    consolidated BOOLEAN DEFAULT false,
    memory_tags JSONB DEFAULT '[]',
    emotional_context JSONB DEFAULT '{}',
    retrieval_count INTEGER DEFAULT 0,
    last_retrieved TIMESTAMPTZ,
    semantic_embedding VECTOR(384),  -- For local embeddings (384-dim)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_memory_user_profiles_tier ON memory_user_profiles(memory_tier);
CREATE INDEX IF NOT EXISTS idx_memory_user_profiles_consolidation ON memory_user_profiles(last_memory_consolidation);
CREATE INDEX IF NOT EXISTS idx_memory_interaction_importance ON memory_interaction_metadata(memory_importance) WHERE memory_importance > 0.7;
CREATE INDEX IF NOT EXISTS idx_memory_interaction_consolidated ON memory_interaction_metadata(consolidated);
CREATE INDEX IF NOT EXISTS idx_memory_interaction_user ON memory_interaction_metadata(user_id);
CREATE INDEX IF NOT EXISTS idx_memory_interaction_retrieval ON memory_interaction_metadata(retrieval_count) WHERE retrieval_count > 0;

-- Create function to update memory tier based on activity
CREATE OR REPLACE FUNCTION update_memory_profile_tier()
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
    
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to automatically update memory tier
CREATE TRIGGER update_memory_user_tier 
    BEFORE UPDATE ON memory_user_profiles 
    FOR EACH ROW EXECUTE FUNCTION update_memory_profile_tier();

-- Create trigger for memory_interaction_metadata updated_at
CREATE TRIGGER update_memory_interaction_updated_at 
    BEFORE UPDATE ON memory_interaction_metadata 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Initialize memory profiles for existing users (if any)
INSERT INTO memory_user_profiles (user_id, last_interaction, total_interactions)
SELECT user_id, updated_at, 1
FROM user_current_status
ON CONFLICT (user_id) DO NOTHING;