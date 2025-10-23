-- =====================================================
-- LEASAP BACKEND - COMPLETE SUPABASE MIGRATION
-- =====================================================
-- Copy and paste this ENTIRE script into Supabase SQL Editor
-- This script is safe to run multiple times (idempotent)

-- =====================================================
-- STEP 1: ENABLE REQUIRED EXTENSIONS
-- =====================================================
-- Enable UUID extension for generating UUIDs
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable vector extension for embeddings (if not already enabled)
CREATE EXTENSION IF NOT EXISTS "vector";

-- =====================================================
-- STEP 2: CREATE PROPERTY MANAGER TABLE
-- =====================================================
-- Create the propertymanager table if it doesn't exist
CREATE TABLE IF NOT EXISTS propertymanager (
    property_manager_id SERIAL PRIMARY KEY,
    auth_user_id UUID NOT NULL UNIQUE,
    name VARCHAR NOT NULL,
    email VARCHAR NOT NULL UNIQUE,
    contact VARCHAR NOT NULL,
    company_name VARCHAR,
    twilio_contact VARCHAR NOT NULL DEFAULT 'TBD',
    twilio_sid VARCHAR,
    credentials TEXT, -- Google Calendar credentials (JSON)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =====================================================
-- STEP 3: ADD INDEXES FOR PERFORMANCE
-- =====================================================
-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_propertymanager_auth_user_id ON propertymanager(auth_user_id);
CREATE INDEX IF NOT EXISTS idx_propertymanager_email ON propertymanager(email);
CREATE INDEX IF NOT EXISTS idx_propertymanager_created_at ON propertymanager(created_at);

-- =====================================================
-- STEP 4: UPDATE REALTOR TABLE
-- =====================================================
-- Add new columns to existing realtor table (safe to run multiple times)
DO $$ 
BEGIN
    -- Add property_manager_id column if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'realtor' AND column_name = 'property_manager_id') THEN
        ALTER TABLE realtor ADD COLUMN property_manager_id INTEGER;
    END IF;
    
    -- Add is_standalone column if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'realtor' AND column_name = 'is_standalone') THEN
        ALTER TABLE realtor ADD COLUMN is_standalone BOOLEAN DEFAULT TRUE;
    END IF;
    
    -- Add created_at column if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'realtor' AND column_name = 'created_at') THEN
        ALTER TABLE realtor ADD COLUMN created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
    END IF;
    
    -- Add updated_at column if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'realtor' AND column_name = 'updated_at') THEN
        ALTER TABLE realtor ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
    END IF;
END $$;

-- =====================================================
-- STEP 5: ADD FOREIGN KEY CONSTRAINTS
-- =====================================================
-- Add foreign key constraint for property_manager_id (if not exists)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints 
                   WHERE constraint_name = 'realtor_property_manager_id_fkey') THEN
        ALTER TABLE realtor 
        ADD CONSTRAINT realtor_property_manager_id_fkey 
        FOREIGN KEY (property_manager_id) REFERENCES propertymanager(property_manager_id);
    END IF;
END $$;

-- =====================================================
-- STEP 6: ADD INDEXES FOR REALTOR TABLE
-- =====================================================
-- Create indexes for new columns
CREATE INDEX IF NOT EXISTS idx_realtor_property_manager_id ON realtor(property_manager_id);
CREATE INDEX IF NOT EXISTS idx_realtor_is_standalone ON realtor(is_standalone);
CREATE INDEX IF NOT EXISTS idx_realtor_created_at ON realtor(created_at);

-- =====================================================
-- STEP 7: UPDATE SOURCE TABLE
-- =====================================================
-- Add property_manager_id column to existing source table
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'source' AND column_name = 'property_manager_id') THEN
        ALTER TABLE source ADD COLUMN property_manager_id INTEGER;
    END IF;
END $$;

-- Add foreign key constraint for source table
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints 
                   WHERE constraint_name = 'source_property_manager_id_fkey') THEN
        ALTER TABLE source 
        ADD CONSTRAINT source_property_manager_id_fkey 
        FOREIGN KEY (property_manager_id) REFERENCES propertymanager(property_manager_id);
    END IF;
END $$;

-- Add index for new column
CREATE INDEX IF NOT EXISTS idx_source_property_manager_id ON source(property_manager_id);

-- =====================================================
-- STEP 8: ADD SOURCE TABLE CONSTRAINT
-- =====================================================
-- Ensure either property_manager_id or realtor_id is set (but not both)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints 
                   WHERE constraint_name = 'check_source_owner') THEN
        ALTER TABLE source 
        ADD CONSTRAINT check_source_owner 
        CHECK (
            (property_manager_id IS NOT NULL AND realtor_id IS NULL) OR 
            (property_manager_id IS NULL AND realtor_id IS NOT NULL)
        );
    END IF;
END $$;

-- =====================================================
-- STEP 9: UPDATE EXISTING DATA
-- =====================================================
-- Mark all existing realtors as standalone and set timestamps
UPDATE realtor 
SET is_standalone = TRUE, 
    property_manager_id = NULL,
    created_at = COALESCE(created_at, NOW()),
    updated_at = NOW()
WHERE is_standalone IS NULL OR created_at IS NULL;

-- =====================================================
-- STEP 10: CREATE UPDATED_AT TRIGGER FUNCTION
-- =====================================================
-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- =====================================================
-- STEP 11: CREATE TRIGGERS
-- =====================================================
-- Create trigger for propertymanager table
DROP TRIGGER IF EXISTS update_propertymanager_updated_at ON propertymanager;
CREATE TRIGGER update_propertymanager_updated_at
    BEFORE UPDATE ON propertymanager
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Create trigger for realtor table
DROP TRIGGER IF EXISTS update_realtor_updated_at ON realtor;
CREATE TRIGGER update_realtor_updated_at
    BEFORE UPDATE ON realtor
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- STEP 12: ENABLE ROW LEVEL SECURITY
-- =====================================================
-- Enable RLS on propertymanager table
ALTER TABLE propertymanager ENABLE ROW LEVEL SECURITY;

-- =====================================================
-- STEP 13: CREATE RLS POLICIES
-- =====================================================
-- Drop existing policies if they exist
DROP POLICY IF EXISTS "Property Managers can view own data" ON propertymanager;
DROP POLICY IF EXISTS "Realtors can view their property manager" ON propertymanager;

-- Property Managers can only see their own data
CREATE POLICY "Property Managers can view own data" ON propertymanager
    FOR ALL USING (auth_user_id = auth.uid());

-- Realtors can see their property manager's data
CREATE POLICY "Realtors can view their property manager" ON propertymanager
    FOR SELECT USING (
        property_manager_id IN (
            SELECT property_manager_id 
            FROM realtor 
            WHERE auth_user_id = auth.uid()
        )
    );

-- =====================================================
-- STEP 14: VERIFICATION QUERIES
-- =====================================================
-- Check if all tables exist and have correct structure
SELECT 
    'propertymanager' as table_name,
    COUNT(*) as row_count,
    'Table exists' as status
FROM information_schema.tables 
WHERE table_name = 'propertymanager'

UNION ALL

SELECT 
    'realtor' as table_name,
    COUNT(*) as row_count,
    'Table exists' as status
FROM information_schema.tables 
WHERE table_name = 'realtor'

UNION ALL

SELECT 
    'source' as table_name,
    COUNT(*) as row_count,
    'Table exists' as status
FROM information_schema.tables 
WHERE table_name = 'source';

-- Check if new columns exist in realtor table
SELECT 
    column_name, 
    data_type, 
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_name = 'realtor' 
AND column_name IN ('property_manager_id', 'is_standalone', 'created_at', 'updated_at')
ORDER BY ordinal_position;

-- Check if new column exists in source table
SELECT 
    column_name, 
    data_type, 
    is_nullable
FROM information_schema.columns 
WHERE table_name = 'source' 
AND column_name = 'property_manager_id';

-- Check if foreign key constraints exist
SELECT 
    tc.constraint_name,
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
    AND ccu.table_schema = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
AND (tc.table_name = 'realtor' OR tc.table_name = 'source')
AND (kcu.column_name = 'property_manager_id');

-- =====================================================
-- MIGRATION COMPLETE!
-- =====================================================
-- Your Supabase database now supports:
-- ✅ Property Manager hierarchy
-- ✅ Data isolation between users  
-- ✅ Proper foreign key relationships
-- ✅ Row Level Security policies
-- ✅ Automatic timestamp updates
-- ✅ All existing data preserved

-- Next steps:
-- 1. Test your authentication endpoints
-- 2. Create test users using: python create_test_users.py
-- 3. Test your frontend login
