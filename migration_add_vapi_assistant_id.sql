-- Migration: Add VAPI Assistant ID to PropertyManager and Realtor tables
-- Purpose: Enable chat request identification when phone number is not available
-- Date: 2025-01-07

-- Add vapi_assistant_id column to PropertyManager table
ALTER TABLE propertymanager 
ADD COLUMN IF NOT EXISTS vapi_assistant_id TEXT;

-- Add vapi_assistant_id column to Realtor table
ALTER TABLE realtor 
ADD COLUMN IF NOT EXISTS vapi_assistant_id TEXT;

-- Create indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_propertymanager_vapi_assistant_id ON propertymanager(vapi_assistant_id) WHERE vapi_assistant_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_realtor_vapi_assistant_id ON realtor(vapi_assistant_id) WHERE vapi_assistant_id IS NOT NULL;

-- Add comments
COMMENT ON COLUMN propertymanager.vapi_assistant_id IS 'VAPI assistant ID for chat requests. Used to identify the user when phone number is not available in chat requests.';
COMMENT ON COLUMN realtor.vapi_assistant_id IS 'VAPI assistant ID for chat requests. Used to identify the user when phone number is not available in chat requests.';

-- Verify the columns were added
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'propertymanager' AND column_name = 'vapi_assistant_id'
    ) THEN
        RAISE NOTICE '✅ Successfully added vapi_assistant_id to propertymanager table';
    ELSE
        RAISE WARNING '❌ Failed to add vapi_assistant_id to propertymanager table';
    END IF;
    
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'realtor' AND column_name = 'vapi_assistant_id'
    ) THEN
        RAISE NOTICE '✅ Successfully added vapi_assistant_id to realtor table';
    ELSE
        RAISE WARNING '❌ Failed to add vapi_assistant_id to realtor table';
    END IF;
END $$;
