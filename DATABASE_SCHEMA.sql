-- NADIA HITL Database Schema
-- PostgreSQL 14+

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Main interactions table
CREATE TABLE interactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    message_number INTEGER NOT NULL,
    
    -- User Input
    user_message TEXT NOT NULL,
    user_message_timestamp TIMESTAMPTZ NOT NULL,
    
    -- AI Generation
    llm1_raw_response TEXT,
    llm1_tokens_used INTEGER,
    llm1_cost_usd DECIMAL(6,4),
    
    llm2_bubbles TEXT[],
    llm2_tokens_used INTEGER,
    llm2_cost_usd DECIMAL(6,4),
    
    -- Constitution Analysis
    constitution_risk_score FLOAT CHECK (constitution_risk_score >= 0 AND constitution_risk_score <= 1),
    constitution_flags TEXT[],
    constitution_recommendation TEXT CHECK (constitution_recommendation IN ('approve', 'review', 'flag')),
    
    -- Human Review
    review_status TEXT DEFAULT 'pending' CHECK (review_status IN ('pending', 'reviewing', 'approved', 'rejected')),
    reviewer_id TEXT,
    review_started_at TIMESTAMPTZ,
    review_completed_at TIMESTAMPTZ,
    review_time_seconds INTEGER,
    
    -- Final Output
    final_bubbles TEXT[],
    messages_sent_at TIMESTAMPTZ,
    
    -- Edit Tracking
    edit_tags TEXT[],
    quality_score INTEGER CHECK (quality_score BETWEEN 1 AND 5),
    reviewer_notes TEXT,
    
    -- Metadata
    total_cost_usd DECIMAL(6,4),
    priority_score FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_interactions_user ON interactions(user_id);
CREATE INDEX idx_interactions_conversation ON interactions(conversation_id);
CREATE INDEX idx_interactions_pending ON interactions(review_status) WHERE review_status = 'pending';
CREATE INDEX idx_interactions_priority ON interactions(priority_score DESC) WHERE review_status = 'pending';
CREATE INDEX idx_interactions_edit_tags ON interactions USING GIN(edit_tags);
CREATE INDEX idx_interactions_created ON interactions(created_at DESC);

-- Edit taxonomy reference table
CREATE TABLE edit_taxonomy (
    code TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    examples JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert taxonomy
INSERT INTO edit_taxonomy (code, category, description) VALUES
('TONE_CASUAL', 'tone', 'Made more casual/informal'),
('TONE_FLIRT_UP', 'tone', 'Increased flirty/playful tone'),
('TONE_CRINGE_DOWN', 'tone', 'Reduced cringe/melodrama'),
('TONE_ENERGY_UP', 'tone', 'Added energy/enthusiasm'),
('STRUCT_SHORTEN', 'structure', 'Shortened significantly'),
('STRUCT_BUBBLE', 'structure', 'Changed bubble division'),
('CONTENT_EMOJI_ADD', 'content', 'Added emojis'),
('CONTENT_QUESTION', 'content', 'Added engaging question'),
('CONTENT_REWRITE', 'content', 'Complete rewrite');

-- User interaction metrics (materialized view for performance)
CREATE MATERIALIZED VIEW user_metrics AS
SELECT 
    user_id,
    COUNT(*) as total_interactions,
    AVG(quality_score) as avg_quality_score,
    COUNT(DISTINCT conversation_id) as total_conversations,
    MAX(created_at) as last_interaction,
    SUM(total_cost_usd) as total_cost
FROM interactions
GROUP BY user_id;

-- Create index on materialized view
CREATE INDEX idx_user_metrics_user ON user_metrics(user_id);

-- Refresh function for materialized view
CREATE OR REPLACE FUNCTION refresh_user_metrics()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY user_metrics;
END;
$$ LANGUAGE plpgsql;

-- Analytics views
CREATE VIEW hourly_metrics AS
SELECT 
    DATE_TRUNC('hour', created_at) as hour,
    COUNT(*) as messages,
    AVG(review_time_seconds) as avg_review_time,
    COUNT(DISTINCT user_id) as unique_users,
    SUM(total_cost_usd) as hourly_cost
FROM interactions
GROUP BY 1
ORDER BY 1 DESC;

CREATE VIEW edit_pattern_analysis AS
SELECT 
    unnest(edit_tags) as edit_tag,
    COUNT(*) as frequency,
    AVG(quality_score) as avg_quality,
    AVG(review_time_seconds) as avg_review_time
FROM interactions
WHERE edit_tags IS NOT NULL
GROUP BY 1
ORDER BY 2 DESC;

-- Function to calculate message priority
CREATE OR REPLACE FUNCTION calculate_priority(
    wait_time_minutes INTEGER,
    user_value_score FLOAT,
    risk_score FLOAT
) RETURNS FLOAT AS $$
BEGIN
    RETURN (wait_time_minutes / 60.0) * 0.4 +  -- Time weight
           user_value_score * 0.3 +              -- User value weight
           risk_score * 0.3;                     -- Risk weight
END;
$$ LANGUAGE plpgsql;

-- Trigger to update timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_interactions_updated_at
BEFORE UPDATE ON interactions
FOR EACH ROW
EXECUTE FUNCTION update_updated_at();