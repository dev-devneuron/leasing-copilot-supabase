-- Add call_metadata column to vendorcallattempt table
-- Run this in Supabase SQL Editor

-- Add call_metadata column (JSONB for flexible storage)
ALTER TABLE vendorcallattempt
ADD COLUMN IF NOT EXISTS call_metadata JSONB;

-- Verify the column was added
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'vendorcallattempt' 
AND column_name = 'call_metadata';
