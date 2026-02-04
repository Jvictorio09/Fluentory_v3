-- Manual SQL to fix the slug field if migration doesn't work
-- Run this in your PostgreSQL database if the migration doesn't apply

-- First, check current state:
-- SELECT column_name, character_maximum_length 
-- FROM information_schema.columns 
-- WHERE table_name = 'myapp_lesson' AND column_name = 'slug';

-- Update the slug column to allow 200 characters
ALTER TABLE myapp_lesson ALTER COLUMN slug TYPE varchar(200);

-- Add the content column if it doesn't exist
-- (This should be handled by the migration, but just in case)
-- ALTER TABLE myapp_lesson ADD COLUMN IF NOT EXISTS content JSONB DEFAULT '{}'::jsonb;





