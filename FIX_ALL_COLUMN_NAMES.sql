-- =====================================================
-- COMPREHENSIVE COLUMN NAME FIX
-- =====================================================
-- This script fixes ALL column name issues for authentication

-- =====================================================
-- STEP 1: RENAME REALTOR TABLE PRIMARY KEY
-- =====================================================
-- Rename the 'id' column to 'realtor_id' in the realtor table
ALTER TABLE realtor RENAME COLUMN id TO realtor_id;

-- =====================================================
-- STEP 2: RENAME SOURCE TABLE PRIMARY KEY
-- =====================================================
-- Rename the 'id' column to 'source_id' in the source table
ALTER TABLE source RENAME COLUMN id TO source_id;

-- =====================================================
-- STEP 3: UPDATE ALL FOREIGN KEY REFERENCES
-- =====================================================

-- Update source table to reference the new realtor column name
ALTER TABLE source DROP CONSTRAINT IF EXISTS source_realtor_id_fkey;
ALTER TABLE source 
ADD CONSTRAINT source_realtor_id_fkey 
FOREIGN KEY (realtor_id) REFERENCES realtor(realtor_id);

-- Update source table to reference the new propertymanager column name
ALTER TABLE source DROP CONSTRAINT IF EXISTS source_property_manager_id_fkey;
ALTER TABLE source 
ADD CONSTRAINT source_property_manager_id_fkey 
FOREIGN KEY (property_manager_id) REFERENCES propertymanager(property_manager_id);

-- Update booking table to reference the new realtor column name
ALTER TABLE booking DROP CONSTRAINT IF EXISTS booking_realtor_id_fkey;
ALTER TABLE booking 
ADD CONSTRAINT booking_realtor_id_fkey 
FOREIGN KEY (realtor_id) REFERENCES realtor(realtor_id);

-- Update apartment_realtors table to reference the new realtor column name
ALTER TABLE apartment_realtors DROP CONSTRAINT IF EXISTS apartment_realtors_realtor_id_fkey;
ALTER TABLE apartment_realtors 
ADD CONSTRAINT apartment_realtors_realtor_id_fkey 
FOREIGN KEY (realtor_id) REFERENCES realtor(realtor_id);

-- Update rulechunk table to reference the new source column name
ALTER TABLE rulechunk DROP CONSTRAINT IF EXISTS rulechunk_source_id_fkey;
ALTER TABLE rulechunk 
ADD CONSTRAINT rulechunk_source_id_fkey 
FOREIGN KEY (source_id) REFERENCES source(source_id);

-- Update apartmentlisting table to reference the new source column name
ALTER TABLE apartmentlisting DROP CONSTRAINT IF EXISTS apartmentlisting_source_id_fkey;
ALTER TABLE apartmentlisting 
ADD CONSTRAINT apartmentlisting_source_id_fkey 
FOREIGN KEY (source_id) REFERENCES source(source_id);

-- =====================================================
-- STEP 4: VERIFICATION
-- =====================================================
-- Check if the column renames were successful
SELECT 'realtor' as table_name, column_name, data_type
FROM information_schema.columns 
WHERE table_name = 'realtor' 
AND column_name IN ('realtor_id', 'id')

UNION ALL

SELECT 'source' as table_name, column_name, data_type
FROM information_schema.columns 
WHERE table_name = 'source' 
AND column_name IN ('source_id', 'id');

-- Check if foreign key constraints are working
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
AND (tc.table_name = 'source' OR tc.table_name = 'booking' OR tc.table_name = 'apartment_realtors' OR tc.table_name = 'rulechunk' OR tc.table_name = 'apartmentlisting')
AND (kcu.column_name = 'realtor_id' OR kcu.column_name = 'source_id')
ORDER BY tc.table_name, kcu.column_name;

-- =====================================================
-- FIX COMPLETE!
-- =====================================================
-- Both realtor and source tables now have correct column names:
-- - realtor.id -> realtor.realtor_id
-- - source.id -> source.source_id
-- All foreign key references have been updated
-- Authentication should now work correctly
