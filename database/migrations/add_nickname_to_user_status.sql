-- Migration: Add nickname column to user_current_status
-- Date: June 25, 2025
-- Purpose: Store user nicknames for dashboard display

-- Add nickname column
ALTER TABLE user_current_status 
ADD COLUMN nickname VARCHAR(50);

-- Add comment for documentation
COMMENT ON COLUMN user_current_status.nickname IS 'User nickname for dashboard display (editable)';

-- Populate nicknames from memory system if available
-- (Optional: could be populated later from user_memory or manually)