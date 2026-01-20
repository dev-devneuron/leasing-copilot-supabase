-- Migration: Add vapi_outbound_assistant_id field to PropertyManager and Realtor tables
-- This separates inbound and outbound call assistants

-- Add vapi_outbound_assistant_id to PropertyManager table
ALTER TABLE propertymanager
ADD COLUMN IF NOT EXISTS vapi_outbound_assistant_id TEXT;

-- Add index for faster lookups
CREATE INDEX IF NOT EXISTS idx_propertymanager_vapi_outbound_assistant_id 
ON propertymanager(vapi_outbound_assistant_id);

-- Add vapi_outbound_assistant_id to Realtor table
ALTER TABLE realtor
ADD COLUMN IF NOT EXISTS vapi_outbound_assistant_id TEXT;

-- Add index for faster lookups
CREATE INDEX IF NOT EXISTS idx_realtor_vapi_outbound_assistant_id 
ON realtor(vapi_outbound_assistant_id);

-- Update comments/documentation
COMMENT ON COLUMN propertymanager.vapi_assistant_id IS 'VAPI assistant ID for inbound calls/chat requests';
COMMENT ON COLUMN propertymanager.vapi_outbound_assistant_id IS 'VAPI assistant ID for outbound calls';
COMMENT ON COLUMN realtor.vapi_assistant_id IS 'VAPI assistant ID for inbound calls/chat requests';
COMMENT ON COLUMN realtor.vapi_outbound_assistant_id IS 'VAPI assistant ID for outbound calls';
