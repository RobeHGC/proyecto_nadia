-- Migration: Add Coherence and Schedule System
-- Version: 1.0
-- Date: 2025-06-26
-- Description: Adds tables for commitment tracking and coherence analysis

-- Table for tracking Nadia's commitments and schedule
CREATE TABLE nadia_commitments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    commitment_timestamp TIMESTAMPTZ NOT NULL,
    details JSONB NOT NULL,
    commitment_text TEXT NOT NULL, -- Original text that created the commitment
    extracted_from_interaction UUID REFERENCES interactions(id),
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'fulfilled', 'expired', 'cancelled')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Table for storing LLM2 coherence analysis results
CREATE TABLE coherence_analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interaction_id UUID REFERENCES interactions(id),
    llm2_input JSONB NOT NULL, -- The input sent to LLM2
    llm2_output JSONB NOT NULL, -- Raw LLM2 response
    analysis_status VARCHAR(50) NOT NULL CHECK (analysis_status IN ('OK', 'CONFLICTO_DE_IDENTIDAD', 'CONFLICTO_DE_DISPONIBILIDAD')),
    conflict_details TEXT,
    correction_applied BOOLEAN DEFAULT FALSE,
    processing_time_ms INTEGER,
    json_parse_success BOOLEAN DEFAULT TRUE,
    llm_model_used VARCHAR(50) DEFAULT 'gpt-4o-mini',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Table for tracking prompt rotations (for identity conflict prevention)
CREATE TABLE prompt_rotations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    previous_prompt_id VARCHAR(50),
    new_prompt_id VARCHAR(50) NOT NULL,
    rotation_reason VARCHAR(100) DEFAULT 'CONFLICTO_DE_IDENTIDAD',
    triggered_by_interaction UUID REFERENCES interactions(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indices for optimal performance
CREATE INDEX idx_nadia_commitments_user_active 
ON nadia_commitments(user_id, commitment_timestamp) 
WHERE status = 'active';

CREATE INDEX idx_nadia_commitments_timeline 
ON nadia_commitments(commitment_timestamp, status);

CREATE INDEX idx_coherence_analysis_interaction 
ON coherence_analysis(interaction_id);

CREATE INDEX idx_coherence_analysis_status 
ON coherence_analysis(analysis_status, created_at);

CREATE INDEX idx_prompt_rotations_user 
ON prompt_rotations(user_id, created_at);

-- Note: interactions table modifications require owner permissions
-- These can be added manually later if needed:
-- ALTER TABLE interactions ADD COLUMN coherence_analysis_id UUID REFERENCES coherence_analysis(id);
-- ALTER TABLE interactions ADD COLUMN llm1_quality_rating INTEGER CHECK (llm1_quality_rating BETWEEN 1 AND 5);
-- ALTER TABLE interactions ADD COLUMN has_commitments BOOLEAN DEFAULT FALSE;
-- ALTER TABLE interactions ADD COLUMN commitment_count INTEGER DEFAULT 0;

-- Create a view for active commitments with time remaining
CREATE VIEW active_commitments_view AS
SELECT 
    nc.*,
    EXTRACT(EPOCH FROM (nc.commitment_timestamp - NOW())) / 3600 as hours_remaining,
    CASE 
        WHEN nc.commitment_timestamp <= NOW() THEN 'overdue'
        WHEN nc.commitment_timestamp <= NOW() + INTERVAL '2 hours' THEN 'urgent'
        WHEN nc.commitment_timestamp <= NOW() + INTERVAL '24 hours' THEN 'today'
        ELSE 'future'
    END as urgency_level
FROM nadia_commitments nc
WHERE nc.status = 'active';

-- Function to automatically update commitment status
CREATE OR REPLACE FUNCTION update_expired_commitments()
RETURNS void AS $$
BEGIN
    UPDATE nadia_commitments 
    SET status = 'expired', updated_at = NOW()
    WHERE status = 'active' 
    AND commitment_timestamp < NOW() - INTERVAL '1 hour';
END;
$$ LANGUAGE plpgsql;

-- Function to get commitment conflicts for a specific time range
CREATE OR REPLACE FUNCTION check_commitment_conflicts(
    p_user_id TEXT,
    p_start_time TIMESTAMPTZ,
    p_end_time TIMESTAMPTZ
)
RETURNS TABLE(
    conflict_id UUID,
    existing_commitment TEXT,
    conflict_timestamp TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        nc.id,
        nc.commitment_text,
        nc.commitment_timestamp
    FROM nadia_commitments nc
    WHERE nc.user_id = p_user_id
    AND nc.status = 'active'
    AND nc.commitment_timestamp BETWEEN p_start_time AND p_end_time;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_nadia_commitments_updated_at
    BEFORE UPDATE ON nadia_commitments
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Comments for documentation
COMMENT ON TABLE nadia_commitments IS 'Tracks Nadia''s commitments and schedule to maintain consistency';
COMMENT ON TABLE coherence_analysis IS 'Stores LLM2 analysis results for coherence checking';
COMMENT ON TABLE prompt_rotations IS 'Tracks prompt changes to prevent identity conflicts';

COMMENT ON COLUMN nadia_commitments.details IS 'JSONB field containing structured commitment data (activity, type, duration, etc.)';
COMMENT ON COLUMN coherence_analysis.llm2_output IS 'Raw JSON response from LLM2 analysis';
COMMENT ON COLUMN coherence_analysis.analysis_status IS 'Classification result: OK, CONFLICTO_DE_IDENTIDAD, or CONFLICTO_DE_DISPONIBILIDAD';

-- Sample data types for details JSONB field
/*
Example nadia_commitments.details structure:
{
    "activity": "gym",
    "type": "fitness",
    "duration_minutes": 90,
    "location": "downtown gym",
    "flexibility": "rigid",
    "reminder_sent": false
}

Example coherence_analysis.llm2_output structure:
{
    "status": "CONFLICTO_DE_DISPONIBILIDAD",
    "detalle_conflicto": "Gym session conflicts with proposed brunch time",
    "propuesta_correccion": {
        "oracion_original": "Want to grab brunch at 11?",
        "oracion_corregida": "Want to grab brunch at 1pm? I'll be done with gym by then!"
    },
    "nuevos_compromisos": ["brunch at 1pm on Saturday"]
}
*/