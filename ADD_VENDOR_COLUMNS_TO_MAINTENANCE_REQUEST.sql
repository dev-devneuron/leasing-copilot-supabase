-- Add vendor-related columns to maintenancerequest table
-- Run this in Supabase SQL Editor

-- Add assigned_vendor_id column (foreign key to vendor table)
ALTER TABLE maintenancerequest
ADD COLUMN IF NOT EXISTS assigned_vendor_id INTEGER;

-- Add foreign key constraint
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'maintenancerequest_assigned_vendor_id_fkey'
    ) THEN
        ALTER TABLE maintenancerequest
        ADD CONSTRAINT maintenancerequest_assigned_vendor_id_fkey
        FOREIGN KEY (assigned_vendor_id) REFERENCES vendor(vendor_id);
    END IF;
END $$;

-- Create index for assigned_vendor_id
CREATE INDEX IF NOT EXISTS idx_maintenancerequest_assigned_vendor_id 
ON maintenancerequest(assigned_vendor_id);

-- Add vendor_call_status column
ALTER TABLE maintenancerequest
ADD COLUMN IF NOT EXISTS vendor_call_status TEXT;

-- Create index for vendor_call_status
CREATE INDEX IF NOT EXISTS idx_maintenancerequest_vendor_call_status 
ON maintenancerequest(vendor_call_status);

-- Add vendor_call_automation_enabled column (boolean, default true)
ALTER TABLE maintenancerequest
ADD COLUMN IF NOT EXISTS vendor_call_automation_enabled BOOLEAN DEFAULT TRUE;

-- Set default value for existing rows
UPDATE maintenancerequest
SET vendor_call_automation_enabled = TRUE
WHERE vendor_call_automation_enabled IS NULL;

-- Verify the columns were added
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'maintenancerequest' 
AND column_name IN ('assigned_vendor_id', 'vendor_call_status', 'vendor_call_automation_enabled')
ORDER BY column_name;
