-- Migration: Add call_metadata column to callrecord table
-- Run this SQL in your Supabase/PostgreSQL database

-- Add call_metadata column if it doesn't exist
ALTER TABLE callrecord 
ADD COLUMN IF NOT EXISTS call_metadata JSONB;

-- Add index on call_metadata if needed (optional, for JSONB queries)
-- CREATE INDEX IF NOT EXISTS idx_callrecord_metadata ON callrecord USING GIN (call_metadata);

-- Verify the column was added
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'callrecord' AND column_name = 'call_metadata';

