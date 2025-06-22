-- Migration: Add new tags December 2024
-- Date: 2024-12-21
-- Adds TONE_LESS_IA, CONTENT_QUESTION_CUT, CONTENT_SENTENCE_ADD, TONE_ROMANTIC_UP

-- Add new tags to edit_taxonomy
INSERT INTO edit_taxonomy (code, category, description) VALUES
('TONE_LESS_IA', 'tone', 'Make response less AI-like and more human'),
('CONTENT_QUESTION_CUT', 'content', 'Remove unnecessary questions'),
('CONTENT_SENTENCE_ADD', 'content', 'Add more sentences/context'),
('TONE_ROMANTIC_UP', 'tone', 'Increase romantic/intimate tone')
ON CONFLICT (code) DO UPDATE SET 
    category = EXCLUDED.category,
    description = EXCLUDED.description;

-- Verify tags were added
SELECT code, category, description 
FROM edit_taxonomy 
WHERE code IN ('TONE_LESS_IA', 'CONTENT_QUESTION_CUT', 'CONTENT_SENTENCE_ADD', 'TONE_ROMANTIC_UP');