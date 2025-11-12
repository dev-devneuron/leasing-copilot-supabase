-- =====================================================
-- PHONE NUMBER REQUEST - ADD COUNTRY CODE COLUMN
-- =====================================================
-- This migration adds country_code field to phonenumberrequest table

-- Add country_code column
ALTER TABLE phonenumberrequest 
ADD COLUMN IF NOT EXISTS country_code VARCHAR(10);

-- Create index for better query performance
CREATE INDEX IF NOT EXISTS idx_phonenumberrequest_country_code ON phonenumberrequest(country_code);

-- =====================================================
-- VERIFICATION
-- =====================================================
-- Check column was added:
-- SELECT column_name, data_type FROM information_schema.columns 
-- WHERE table_name = 'phonenumberrequest' AND column_name = 'country_code';

