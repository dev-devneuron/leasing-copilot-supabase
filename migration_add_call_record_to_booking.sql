-- Migration: Add call record fields to PropertyTourBooking table
-- This links bookings created via VAPI phone calls to their call recordings and transcripts

-- Add call record linking fields
ALTER TABLE propertytourbooking
ADD COLUMN IF NOT EXISTS vapi_call_id TEXT DEFAULT NULL,
ADD COLUMN IF NOT EXISTS call_transcript TEXT DEFAULT NULL,
ADD COLUMN IF NOT EXISTS call_recording_url TEXT DEFAULT NULL;

-- Create index on vapi_call_id for faster lookups
CREATE INDEX IF NOT EXISTS idx_propertytourbooking_vapi_call_id ON propertytourbooking(vapi_call_id);

-- Add comment
COMMENT ON COLUMN propertytourbooking.vapi_call_id IS 'VAPI call ID if booking was created via phone call';
COMMENT ON COLUMN propertytourbooking.call_transcript IS 'Transcript of the call that created this booking';
COMMENT ON COLUMN propertytourbooking.call_recording_url IS 'MP3 recording URL from VAPI for the call that created this booking';

