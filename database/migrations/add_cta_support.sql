-- Migration: add_cta_support.sql
-- Adds CTA support to existing HITL system without breaking existing functionality

-- Add cta_data column to interactions table
ALTER TABLE interactions 
ADD COLUMN IF NOT EXISTS cta_data JSONB DEFAULT NULL;

-- Add CTA entries to edit_taxonomy if they don't exist
INSERT INTO edit_taxonomy (code, category, description) VALUES
('CTA_SOFT', 'cta', 'Soft call-to-action inserted'),
('CTA_MEDIUM', 'cta', 'Medium call-to-action inserted'),
('CTA_DIRECT', 'cta', 'Direct call-to-action inserted'),
('ENGLISH_SLANG', 'language', 'Added American slang'),
('TEXT_SPEAK', 'language', 'Converted to text messaging style'),
('REDUCED_CRINGE', 'tone', 'Reduced cringe/melodrama'),
('INCREASED_FLIRT', 'tone', 'Increased flirty tone'),
('MORE_CASUAL', 'tone', 'Made more casual')
ON CONFLICT (code) DO NOTHING;

-- Add index for CTA queries (optional, for performance)
CREATE INDEX IF NOT EXISTS idx_interactions_cta_data 
ON interactions USING GIN(cta_data) 
WHERE cta_data IS NOT NULL;

-- Add comment for documentation
COMMENT ON COLUMN interactions.cta_data IS 'JSONB data for manually inserted CTAs during review process';