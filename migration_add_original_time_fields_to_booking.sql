-- Migration: Add original customer-sent time fields to PropertyTourBooking table
-- This stores the original time strings as the customer sent them, without timezone conversion

-- Add original time string fields
ALTER TABLE propertytourbooking
ADD COLUMN IF NOT EXISTS customer_sent_start_at TEXT DEFAULT NULL,
ADD COLUMN IF NOT EXISTS customer_sent_end_at TEXT DEFAULT NULL;

-- Add comments
COMMENT ON COLUMN propertytourbooking.customer_sent_start_at IS 'Original time string as customer sent it (no timezone conversion)';
COMMENT ON COLUMN propertytourbooking.customer_sent_end_at IS 'Original time string as customer sent it (no timezone conversion)';

