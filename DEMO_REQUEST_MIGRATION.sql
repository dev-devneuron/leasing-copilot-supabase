-- =====================================================
-- DEMO REQUEST SYSTEM MIGRATION
-- =====================================================
-- This migration adds support for "Book a Demo" functionality
-- Replaces direct sign-up with demo booking system

-- =====================================================
-- STEP 1: CREATE DEMO REQUEST TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS demorequest (
    demo_request_id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    email VARCHAR NOT NULL,
    phone VARCHAR NOT NULL,
    company_name VARCHAR,
    preferred_date DATE,
    preferred_time VARCHAR(50),
    timezone VARCHAR(50),
    notes TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    scheduled_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    converted_to_pm_id INTEGER,
    converted_at TIMESTAMP WITH TIME ZONE,
    requested_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (converted_to_pm_id) REFERENCES propertymanager(property_manager_id) ON DELETE SET NULL
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_demorequest_status ON demorequest(status);
CREATE INDEX IF NOT EXISTS idx_demorequest_email ON demorequest(email);
CREATE INDEX IF NOT EXISTS idx_demorequest_requested_at ON demorequest(requested_at);
CREATE INDEX IF NOT EXISTS idx_demorequest_converted_pm ON demorequest(converted_to_pm_id);

-- =====================================================
-- VERIFICATION QUERIES
-- =====================================================
-- Check table was created:
-- SELECT table_name FROM information_schema.tables 
-- WHERE table_name = 'demorequest';

-- Check columns:
-- SELECT column_name, data_type FROM information_schema.columns 
-- WHERE table_name = 'demorequest';

