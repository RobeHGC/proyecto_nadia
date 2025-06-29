-- Migration: Add Memory-Related Tables (Final Version)
-- Date: 2025-06-29
-- Description: Creates memory management tables without vector dependencies

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
    semantic_embedding_text TEXT, -- Store embedding as text for now
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_memory_interaction_importance ON memory_interaction_metadata(memory_importance) WHERE memory_importance > 0.7;
CREATE INDEX IF NOT EXISTS idx_memory_interaction_consolidated ON memory_interaction_metadata(consolidated);
CREATE INDEX IF NOT EXISTS idx_memory_interaction_user ON memory_interaction_metadata(user_id);
CREATE INDEX IF NOT EXISTS idx_memory_interaction_retrieval ON memory_interaction_metadata(retrieval_count) WHERE retrieval_count > 0;

-- Create trigger for memory_interaction_metadata updated_at
CREATE TRIGGER update_memory_interaction_updated_at 
    BEFORE UPDATE ON memory_interaction_metadata 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();