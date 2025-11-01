-- =====================================================
-- FIX SOURCE TABLE CONSTRAINT
-- =====================================================
-- This script fixes the source table to allow NULL realtor_id
-- when property_manager_id is set (for Property Manager sources)

-- Step 1: Check current table structure
SELECT 
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_schema = 'public' 
AND table_name = 'source'
ORDER BY ordinal_position;

-- Step 2: Check current constraints
SELECT 
    tc.constraint_name,
    tc.constraint_type,
    kcu.column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
    ON tc.constraint_name = kcu.constraint_name
WHERE tc.table_schema = 'public' 
AND tc.table_name = 'source';

-- Step 3: Check if realtor_id has NOT NULL constraint
SELECT 
    column_name,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'public' 
AND table_name = 'source'
AND column_name = 'realtor_id';

-- Step 4: If realtor_id is NOT NULL, alter it to allow NULL
-- This is safe because we have a CHECK constraint ensuring one is set
DO $$
BEGIN
    -- Check if realtor_id is NOT NULL
    IF EXISTS (
        SELECT 1 
        FROM information_schema.columns
        WHERE table_schema = 'public' 
        AND table_name = 'source'
        AND column_name = 'realtor_id'
        AND is_nullable = 'NO'
    ) THEN
        -- Alter column to allow NULL
        ALTER TABLE source ALTER COLUMN realtor_id DROP NOT NULL;
        RAISE NOTICE 'Updated realtor_id column to allow NULL';
    ELSE
        RAISE NOTICE 'realtor_id already allows NULL';
    END IF;
END $$;

-- Step 5: Verify the change
SELECT 
    column_name,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'public' 
AND table_name = 'source'
AND column_name IN ('property_manager_id', 'realtor_id');

-- Step 6: Verify CHECK constraint exists (ensures one is set)
SELECT 
    constraint_name,
    check_clause
FROM information_schema.check_constraints
WHERE constraint_name = 'check_source_owner';

