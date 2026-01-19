-- ============================================================================
-- MIGRATION: Add Extraction Intelligence Fields to CallRecord Table
-- ============================================================================
-- 
-- This migration adds three new fields to the callrecord table:
-- 1. extracted_intel (JSONB) - Cached extraction results from Gemini AI
-- 2. extracted_intel_updated_at (TIMESTAMP) - When extraction was performed
-- 3. extraction_status (TEXT, INDEXED) - Status: 'pending', 'completed', 'failed', 'skipped'
--
-- Run this in Supabase SQL Editor
-- ============================================================================

-- Step 1: Add extracted_intel column (JSONB for storing extraction results)
ALTER TABLE callrecord
ADD COLUMN IF NOT EXISTS extracted_intel JSONB;

-- Step 2: Add extracted_intel_updated_at column (timestamp)
ALTER TABLE callrecord
ADD COLUMN IF NOT EXISTS extracted_intel_updated_at TIMESTAMP;

-- Step 3: Add extraction_status column (text, nullable, indexed)
ALTER TABLE callrecord
ADD COLUMN IF NOT EXISTS extraction_status TEXT;

-- Step 4: Create index on extraction_status for fast queries
CREATE INDEX IF NOT EXISTS idx_callrecord_extraction_status 
ON callrecord(extraction_status);

-- Step 5: Add comment to document the fields
COMMENT ON COLUMN callrecord.extracted_intel IS 
'Cached extraction results from Gemini AI. Stores: email, inferred_name, inquiry_property, inquiry_purpose, region, call_summary';

COMMENT ON COLUMN callrecord.extracted_intel_updated_at IS 
'Timestamp when extraction was last performed';

COMMENT ON COLUMN callrecord.extraction_status IS 
'Extraction status: pending, completed, failed, or skipped';

-- ============================================================================
-- VERIFICATION QUERIES (Optional - run these to verify the migration)
-- ============================================================================

-- Check if columns were added successfully
-- SELECT column_name, data_type, is_nullable
-- FROM information_schema.columns
-- WHERE table_name = 'callrecord'
-- AND column_name IN ('extracted_intel', 'extracted_intel_updated_at', 'extraction_status');

-- Check if index was created
-- SELECT indexname, indexdef
-- FROM pg_indexes
-- WHERE tablename = 'callrecord'
-- AND indexname = 'idx_callrecord_extraction_status';

-- ============================================================================
-- ROLLBACK (if needed - run these to remove the fields)
-- ============================================================================

-- DROP INDEX IF EXISTS idx_callrecord_extraction_status;
-- ALTER TABLE callrecord DROP COLUMN IF EXISTS extraction_status;
-- ALTER TABLE callrecord DROP COLUMN IF EXISTS extracted_intel_updated_at;
-- ALTER TABLE callrecord DROP COLUMN IF EXISTS extracted_intel;
