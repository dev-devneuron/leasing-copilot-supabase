-- Migration: Add carrier column to PropertyManager and Realtor tables
-- Run this migration to add carrier support for call forwarding

-- Add carrier column to PropertyManager table
ALTER TABLE propertymanager 
ADD COLUMN IF NOT EXISTS carrier TEXT;

-- Add carrier column to Realtor table
ALTER TABLE realtor 
ADD COLUMN IF NOT EXISTS carrier TEXT;

-- Add comment to document the column
COMMENT ON COLUMN propertymanager.carrier IS 'User''s mobile carrier (e.g., "AT&T", "Verizon", "T-Mobile", "Mint", "Metro", "Google Fi", "Xfinity Mobile")';
COMMENT ON COLUMN realtor.carrier IS 'User''s mobile carrier (e.g., "AT&T", "Verizon", "T-Mobile", "Mint", "Metro", "Google Fi", "Xfinity Mobile")';

-- Optional: Create index for faster carrier lookups (if needed for analytics)
-- CREATE INDEX IF NOT EXISTS idx_propertymanager_carrier ON propertymanager(carrier);
-- CREATE INDEX IF NOT EXISTS idx_realtor_carrier ON realtor(carrier);

