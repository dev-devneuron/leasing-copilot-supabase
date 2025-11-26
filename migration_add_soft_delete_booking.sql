-- Migration: Add soft delete fields to PropertyTourBooking table
-- This allows cancelled/deleted bookings to be stored in DB for PM/realtor visibility

-- Add soft delete fields
ALTER TABLE propertytourbooking 
ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS deletion_reason TEXT,
ADD COLUMN IF NOT EXISTS deleted_by TEXT;

-- Create index on deleted_at for efficient queries
CREATE INDEX IF NOT EXISTS idx_propertytourbooking_deleted_at ON propertytourbooking(deleted_at);

-- Update existing cancelled bookings to have deleted_at set
UPDATE propertytourbooking 
SET deleted_at = updated_at, 
    deleted_by = 'system',
    deletion_reason = 'Migrated existing cancelled bookings'
WHERE status = 'cancelled' AND deleted_at IS NULL;

