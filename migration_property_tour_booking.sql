-- Migration: Property Tour Booking System
-- This migration adds tables and columns for the in-app property tour booking system

-- Add timezone and calendar preferences to PropertyManager
ALTER TABLE propertymanager 
ADD COLUMN IF NOT EXISTS timezone TEXT DEFAULT 'America/New_York';

ALTER TABLE propertymanager 
ADD COLUMN IF NOT EXISTS calendar_preferences JSONB;

-- Add timezone and calendar preferences to Realtor
ALTER TABLE realtor 
ADD COLUMN IF NOT EXISTS timezone TEXT DEFAULT 'America/New_York';

ALTER TABLE realtor 
ADD COLUMN IF NOT EXISTS calendar_preferences JSONB;

-- Create PropertyTourBooking table
CREATE TABLE IF NOT EXISTS propertytourbooking (
    booking_id SERIAL PRIMARY KEY,
    property_id INTEGER NOT NULL REFERENCES apartmentlisting(id),
    assigned_to_user_id INTEGER NOT NULL,
    assigned_to_user_type TEXT NOT NULL CHECK (assigned_to_user_type IN ('property_manager', 'realtor')),
    visitor_name TEXT NOT NULL,
    visitor_phone TEXT NOT NULL,
    visitor_email TEXT,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    start_at TIMESTAMPTZ NOT NULL,
    end_at TIMESTAMPTZ NOT NULL,
    timezone TEXT NOT NULL DEFAULT 'America/New_York',
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'denied', 'cancelled', 'rescheduled')),
    created_by TEXT NOT NULL DEFAULT 'vapi' CHECK (created_by IN ('vapi', 'ui', 'phone')),
    notes TEXT,
    audit_log JSONB,
    proposed_slots JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes for PropertyTourBooking
CREATE INDEX IF NOT EXISTS idx_propertytourbooking_property_id ON propertytourbooking(property_id);
CREATE INDEX IF NOT EXISTS idx_propertytourbooking_assigned_to_user_id ON propertytourbooking(assigned_to_user_id);
CREATE INDEX IF NOT EXISTS idx_propertytourbooking_assigned_to_user_type ON propertytourbooking(assigned_to_user_type);
CREATE INDEX IF NOT EXISTS idx_propertytourbooking_visitor_phone ON propertytourbooking(visitor_phone);
CREATE INDEX IF NOT EXISTS idx_propertytourbooking_requested_at ON propertytourbooking(requested_at);
CREATE INDEX IF NOT EXISTS idx_propertytourbooking_start_at ON propertytourbooking(start_at);
CREATE INDEX IF NOT EXISTS idx_propertytourbooking_end_at ON propertytourbooking(end_at);
CREATE INDEX IF NOT EXISTS idx_propertytourbooking_status ON propertytourbooking(status);
CREATE INDEX IF NOT EXISTS idx_propertytourbooking_time_range ON propertytourbooking(start_at, end_at);

-- Create AvailabilitySlot table
CREATE TABLE IF NOT EXISTS availabilityslot (
    slot_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    user_type TEXT NOT NULL CHECK (user_type IN ('property_manager', 'realtor')),
    start_at TIMESTAMPTZ NOT NULL,
    end_at TIMESTAMPTZ NOT NULL,
    slot_type TEXT NOT NULL CHECK (slot_type IN ('available', 'unavailable', 'busy', 'personal', 'booking')),
    source TEXT NOT NULL DEFAULT 'manual' CHECK (source IN ('manual', 'booking', 'system')),
    booking_id INTEGER REFERENCES propertytourbooking(booking_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes for AvailabilitySlot
CREATE INDEX IF NOT EXISTS idx_availabilityslot_user_id ON availabilityslot(user_id);
CREATE INDEX IF NOT EXISTS idx_availabilityslot_user_type ON availabilityslot(user_type);
CREATE INDEX IF NOT EXISTS idx_availabilityslot_start_at ON availabilityslot(start_at);
CREATE INDEX IF NOT EXISTS idx_availabilityslot_end_at ON availabilityslot(end_at);
CREATE INDEX IF NOT EXISTS idx_availabilityslot_slot_type ON availabilityslot(slot_type);
CREATE INDEX IF NOT EXISTS idx_availabilityslot_time_range ON availabilityslot(start_at, end_at);
CREATE INDEX IF NOT EXISTS idx_availabilityslot_user_time ON availabilityslot(user_id, user_type, start_at, end_at);

-- Create PropertyAssignment table (audit trail)
CREATE TABLE IF NOT EXISTS propertyassignment (
    assignment_id SERIAL PRIMARY KEY,
    property_id INTEGER NOT NULL REFERENCES apartmentlisting(id),
    from_user_id INTEGER,
    from_user_type TEXT CHECK (from_user_type IN ('property_manager', 'realtor')),
    to_user_id INTEGER,
    to_user_type TEXT CHECK (to_user_type IN ('property_manager', 'realtor')),
    reason TEXT,
    changed_by_user_id INTEGER NOT NULL,
    changed_by_user_type TEXT NOT NULL CHECK (changed_by_user_type IN ('property_manager', 'realtor', 'admin')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes for PropertyAssignment
CREATE INDEX IF NOT EXISTS idx_propertyassignment_property_id ON propertyassignment(property_id);
CREATE INDEX IF NOT EXISTS idx_propertyassignment_created_at ON propertyassignment(created_at);

-- Add relationship to ApartmentListing (for SQLModel relationships)
-- Note: SQLModel will handle relationships automatically, but we ensure foreign keys exist

-- Add constraint to prevent overlapping approved bookings for same user
-- This is enforced at application level with transactions, but we can add a partial unique index
-- Note: PostgreSQL doesn't support partial unique indexes with overlapping ranges easily,
-- so we'll rely on application-level transaction checks

COMMENT ON TABLE propertytourbooking IS 'Property tour bookings for in-app scheduling system';
COMMENT ON TABLE availabilityslot IS 'User-specific availability slots for calendar management';
COMMENT ON TABLE propertyassignment IS 'Audit trail for property assignment changes between PMs and Realtors';

