-- Migration: Update edit taxonomy - Add CONTENT_EMOJI_CUT, Remove MORE_CASUAL
-- Date: December 2024

-- Remove MORE_CASUAL tag
DELETE FROM edit_taxonomy WHERE code = 'MORE_CASUAL';

-- Add CONTENT_EMOJI_CUT tag
INSERT INTO edit_taxonomy (code, category, description) VALUES
('CONTENT_EMOJI_CUT', 'content', 'Removed excessive emojis to make more balanced')
ON CONFLICT (code) DO UPDATE SET 
    category = EXCLUDED.category,
    description = EXCLUDED.description;

-- Clean up any existing MORE_CASUAL references in interactions table
UPDATE interactions 
SET edit_tags = array_remove(edit_tags, 'MORE_CASUAL') 
WHERE 'MORE_CASUAL' = ANY(edit_tags);