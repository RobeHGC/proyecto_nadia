-- NADIA Rapport Database Schema
-- Optimized for fast emotional connection and user memory

CREATE DATABASE nadia_rapport;

\c nadia_rapport;

-- ════════════════════════════════════════════════════════════════
-- CORE USER PROFILE
-- ════════════════════════════════════════════════════════════════

-- Basic user profile information
CREATE TABLE user_profiles (
    user_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100),
    age INTEGER,
    location VARCHAR(200),
    occupation VARCHAR(200),
    timezone VARCHAR(50),
    language VARCHAR(10) DEFAULT 'en',
    created_at TIMESTAMP DEFAULT NOW(),
    last_active TIMESTAMP DEFAULT NOW(),
    total_messages INTEGER DEFAULT 0
);

-- ════════════════════════════════════════════════════════════════
-- PREFERENCES & INTERESTS
-- ════════════════════════════════════════════════════════════════

-- User preferences and interests
CREATE TABLE user_preferences (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(50) REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    category VARCHAR(50) NOT NULL, -- 'music', 'food', 'hobbies', 'movies', 'sports'
    preference TEXT NOT NULL,
    confidence FLOAT DEFAULT 1.0, -- 0.0-1.0 confidence in this preference
    learned_at TIMESTAMP DEFAULT NOW(),
    mentioned_count INTEGER DEFAULT 1,
    last_mentioned TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_user_preferences_user_category ON user_preferences(user_id, category);
CREATE INDEX idx_user_preferences_confidence ON user_preferences(user_id, confidence DESC);

-- ════════════════════════════════════════════════════════════════
-- LIFE EVENTS & IMPORTANT DATES
-- ════════════════════════════════════════════════════════════════

-- Important events and dates for rapport building
CREATE TABLE user_life_events (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(50) REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL, -- 'birthday', 'anniversary', 'achievement', 'loss', 'celebration'
    event_date DATE,
    description TEXT NOT NULL,
    importance_level INTEGER DEFAULT 5, -- 1-10 scale
    reminded_last TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_user_events_user_date ON user_life_events(user_id, event_date);
CREATE INDEX idx_user_events_upcoming ON user_life_events(event_date) WHERE event_date >= CURRENT_DATE;

-- ════════════════════════════════════════════════════════════════
-- EMOTIONAL STATE TRACKING
-- ════════════════════════════════════════════════════════════════

-- Track emotional states over time
CREATE TABLE emotional_states (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(50) REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    state VARCHAR(50) NOT NULL, -- 'happy', 'sad', 'excited', 'stressed', 'angry', 'lonely', 'romantic'
    intensity FLOAT DEFAULT 5.0, -- 1.0-10.0 intensity scale
    context TEXT, -- What caused this emotional state
    detected_at TIMESTAMP DEFAULT NOW(),
    confidence FLOAT DEFAULT 0.8 -- AI confidence in detection
);

CREATE INDEX idx_emotional_states_user_time ON emotional_states(user_id, detected_at DESC);
CREATE INDEX idx_emotional_states_recent ON emotional_states(detected_at DESC) WHERE detected_at >= NOW() - INTERVAL '7 days';

-- ════════════════════════════════════════════════════════════════
-- CONVERSATION MEMORY
-- ════════════════════════════════════════════════════════════════

-- Optimized conversation snapshots
CREATE TABLE conversation_snapshots (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(50) REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    summary TEXT NOT NULL, -- Key conversation summary
    key_topics TEXT[], -- Array of main topics discussed
    emotional_tone VARCHAR(50), -- Overall emotional tone
    intimacy_level INTEGER DEFAULT 1, -- 1-10 intimacy scale
    created_at TIMESTAMP DEFAULT NOW(),
    messages JSONB, -- Last 10-15 messages for context
    message_count INTEGER DEFAULT 0
);

CREATE INDEX idx_conversation_snapshots_user_recent ON conversation_snapshots(user_id, created_at DESC);
CREATE INDEX idx_conversation_snapshots_intimacy ON conversation_snapshots(user_id, intimacy_level DESC);

-- ════════════════════════════════════════════════════════════════
-- INTERACTION PATTERNS
-- ════════════════════════════════════════════════════════════════

-- User communication patterns and preferences
CREATE TABLE interaction_patterns (
    user_id VARCHAR(50) PRIMARY KEY REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    preferred_chat_times INTEGER[], -- Hours of day [14, 15, 20, 21]
    avg_message_length INTEGER DEFAULT 50,
    preferred_topics TEXT[], -- Most discussed topics
    communication_style VARCHAR(50) DEFAULT 'casual', -- 'casual', 'formal', 'playful', 'flirty', 'intimate'
    response_time_preference VARCHAR(20) DEFAULT 'normal', -- 'immediate', 'normal', 'delayed'
    emoji_usage_frequency FLOAT DEFAULT 0.3, -- 0.0-1.0
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ════════════════════════════════════════════════════════════════
-- RELATIONSHIP PROGRESSION
-- ════════════════════════════════════════════════════════════════

-- Track relationship development over time
CREATE TABLE relationship_milestones (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(50) REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    milestone_type VARCHAR(50) NOT NULL, -- 'first_name', 'personal_share', 'flirt_escalation', 'trust_moment'
    description TEXT,
    intimacy_impact INTEGER DEFAULT 1, -- How much this increased intimacy (1-5)
    achieved_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_relationship_milestones_user_time ON relationship_milestones(user_id, achieved_at DESC);

-- ════════════════════════════════════════════════════════════════
-- PERSONALIZATION CACHE
-- ════════════════════════════════════════════════════════════════

-- Fast lookup cache for personalized responses
CREATE TABLE personalization_cache (
    user_id VARCHAR(50) PRIMARY KEY REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    quick_facts JSONB, -- {"name": "John", "age": 25, "loves": ["coffee", "dogs"]}
    conversation_starters TEXT[], -- Personalized conversation starters
    recent_mood VARCHAR(50), -- Last detected mood
    preferred_greeting VARCHAR(100), -- How they like to be greeted
    cached_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP DEFAULT NOW() + INTERVAL '24 hours'
);

-- ════════════════════════════════════════════════════════════════
-- VIEWS FOR QUICK ACCESS
-- ════════════════════════════════════════════════════════════════

-- Quick user context view
CREATE VIEW user_context_view AS
SELECT 
    up.user_id,
    up.name,
    up.age,
    up.location,
    up.last_active,
    pc.quick_facts,
    pc.recent_mood,
    ip.communication_style,
    ip.preferred_topics,
    (
        SELECT AVG(intensity) 
        FROM emotional_states es 
        WHERE es.user_id = up.user_id 
        AND es.detected_at >= NOW() - INTERVAL '7 days'
    ) as avg_recent_mood_intensity
FROM user_profiles up
LEFT JOIN personalization_cache pc ON up.user_id = pc.user_id
LEFT JOIN interaction_patterns ip ON up.user_id = ip.user_id;

-- Recent preferences view
CREATE VIEW recent_preferences_view AS
SELECT 
    user_id,
    category,
    preference,
    confidence,
    mentioned_count
FROM user_preferences
WHERE last_mentioned >= NOW() - INTERVAL '30 days'
ORDER BY user_id, confidence DESC, mentioned_count DESC;

-- ════════════════════════════════════════════════════════════════
-- FUNCTIONS FOR RAPPORT BUILDING
-- ════════════════════════════════════════════════════════════════

-- Function to get user rapport context
CREATE OR REPLACE FUNCTION get_user_rapport_context(target_user_id VARCHAR(50))
RETURNS JSON AS $$
DECLARE
    result JSON;
BEGIN
    SELECT json_build_object(
        'profile', row_to_json(up),
        'top_preferences', (
            SELECT json_agg(row_to_json(pref))
            FROM (
                SELECT category, preference, confidence
                FROM user_preferences
                WHERE user_id = target_user_id
                ORDER BY confidence DESC, mentioned_count DESC
                LIMIT 8
            ) pref
        ),
        'recent_emotions', (
            SELECT json_agg(row_to_json(emo))
            FROM (
                SELECT state, intensity, context, detected_at
                FROM emotional_states
                WHERE user_id = target_user_id
                ORDER BY detected_at DESC
                LIMIT 5
            ) emo
        ),
        'interaction_style', row_to_json(ip),
        'recent_conversations', (
            SELECT json_agg(row_to_json(conv))
            FROM (
                SELECT summary, key_topics, emotional_tone, intimacy_level, created_at
                FROM conversation_snapshots
                WHERE user_id = target_user_id
                ORDER BY created_at DESC
                LIMIT 3
            ) conv
        )
    )
    INTO result
    FROM user_profiles up
    LEFT JOIN interaction_patterns ip ON up.user_id = ip.user_id
    WHERE up.user_id = target_user_id;
    
    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- ════════════════════════════════════════════════════════════════
-- PERFORMANCE OPTIMIZATIONS
-- ════════════════════════════════════════════════════════════════

-- Cleanup old emotional states (keep last 100 per user)
CREATE OR REPLACE FUNCTION cleanup_old_emotional_states()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER := 0;
BEGIN
    WITH ranked_emotions AS (
        SELECT id, user_id,
               ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY detected_at DESC) as rn
        FROM emotional_states
    )
    DELETE FROM emotional_states
    WHERE id IN (
        SELECT id FROM ranked_emotions WHERE rn > 100
    );
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Auto-update last_active on any table interaction
CREATE OR REPLACE FUNCTION update_last_active()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE user_profiles 
    SET last_active = NOW() 
    WHERE user_id = COALESCE(NEW.user_id, OLD.user_id);
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Triggers to auto-update last_active
CREATE TRIGGER trigger_update_last_active_preferences
    AFTER INSERT OR UPDATE ON user_preferences
    FOR EACH ROW EXECUTE FUNCTION update_last_active();

CREATE TRIGGER trigger_update_last_active_emotions
    AFTER INSERT ON emotional_states
    FOR EACH ROW EXECUTE FUNCTION update_last_active();

CREATE TRIGGER trigger_update_last_active_conversations
    AFTER INSERT ON conversation_snapshots
    FOR EACH ROW EXECUTE FUNCTION update_last_active();

-- ════════════════════════════════════════════════════════════════
-- INITIAL SETUP
-- ════════════════════════════════════════════════════════════════

-- Create cleanup job (to be run daily)
-- This would typically be set up as a cron job or scheduled task

COMMENT ON DATABASE nadia_rapport IS 'NADIA Rapport Database - Optimized for fast emotional connection and personalized interactions';