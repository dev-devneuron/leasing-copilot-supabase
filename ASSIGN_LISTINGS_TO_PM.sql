-- =====================================================
-- ASSIGN EXISTING LISTINGS TO TEST PROPERTY MANAGER
-- =====================================================
-- This script associates existing apartment listings with your test Property Manager
-- Run this AFTER you've created your test Property Manager

-- Step 1: Find your Property Manager's source_id
-- Replace 'john.smith@testcompany.com' with your actual Property Manager email
SELECT 
    pm.property_manager_id,
    pm.name,
    pm.email,
    s.source_id as pm_source_id
FROM propertymanager pm
LEFT JOIN source s ON s.property_manager_id = pm.property_manager_id
WHERE pm.email = 'john.smith@testcompany.com';

-- Step 2: Check how many listings currently have source_id = 66 (or whatever)
-- This helps you see what's currently there
SELECT 
    source_id,
    COUNT(*) as listing_count
FROM apartmentlisting
GROUP BY source_id
ORDER BY listing_count DESC;

-- Step 3: Ensure Property Manager has a Source (create if doesn't exist)
-- This is crucial - each Property Manager must have at least one Source
DO $$
DECLARE
    pm_id INTEGER;
    existing_source_id INTEGER;
BEGIN
    -- Get Property Manager ID
    SELECT property_manager_id INTO pm_id
    FROM propertymanager
    WHERE email = 'john.smith@testcompany.com';
    
    IF pm_id IS NULL THEN
        RAISE EXCEPTION 'Property Manager not found with email: john.smith@testcompany.com';
    END IF;
    
    -- Check if Source exists
    SELECT source_id INTO existing_source_id
    FROM source
    WHERE property_manager_id = pm_id
    LIMIT 1;
    
    -- Create Source if it doesn't exist
    IF existing_source_id IS NULL THEN
        -- Check table constraints first
        -- If realtor_id is NOT NULL, we need to handle it differently
        BEGIN
            -- Try inserting with only property_manager_id (omitting realtor_id)
            INSERT INTO source (property_manager_id)
            VALUES (pm_id)
            RETURNING source_id INTO existing_source_id;
            
            RAISE NOTICE 'Created new Source (ID: %) for Property Manager (ID: %)', existing_source_id, pm_id;
        EXCEPTION WHEN OTHERS THEN
            -- If that fails, check if we need to alter the table constraint
            RAISE EXCEPTION 'Failed to create Source. Error: %. The source table may need schema update to allow NULL realtor_id when property_manager_id is set.', SQLERRM;
        END;
    ELSE
        RAISE NOTICE 'Using existing Source (ID: %) for Property Manager (ID: %)', existing_source_id, pm_id;
    END IF;
END $$;

-- Step 4: Update a batch of listings to your Property Manager's source
-- This query is safe - it only updates if source_id exists and is NOT NULL
DO $$
DECLARE
    pm_source_id INTEGER;
    updated_count INTEGER;
BEGIN
    -- Get the Property Manager's source_id
    SELECT source_id INTO pm_source_id
    FROM source
    WHERE property_manager_id = (
        SELECT property_manager_id 
        FROM propertymanager 
        WHERE email = 'john.smith@testcompany.com'
    )
    LIMIT 1;
    
    -- Check if source exists
    IF pm_source_id IS NULL THEN
        RAISE EXCEPTION 'No source found for Property Manager. Run Step 3 first to create a source.';
    END IF;
    
    RAISE NOTICE 'Using Source ID: % for updates', pm_source_id;
    
    -- Update listings
    WITH listings_to_update AS (
        SELECT id 
        FROM apartmentlisting 
        WHERE source_id IS NULL OR source_id != pm_source_id
        ORDER BY id
        LIMIT 50  -- Change this number or remove LIMIT for all
    )
    UPDATE apartmentlisting
    SET source_id = pm_source_id
    FROM listings_to_update
    WHERE apartmentlisting.id = listings_to_update.id;
    
    GET DIAGNOSTICS updated_count = ROW_COUNT;
    
    RAISE NOTICE 'Updated % listings to use Source ID: %', updated_count, pm_source_id;
END $$;

-- Step 4b: Verify what was updated (run this separately after Step 4)
SELECT 
    al.id,
    al.source_id,
    CASE 
        WHEN al.source_id = (SELECT source_id FROM source WHERE property_manager_id = (
            SELECT property_manager_id FROM propertymanager WHERE email = 'john.smith@testcompany.com'
        ) LIMIT 1) THEN '✓ Assigned to PM'
        ELSE '✗ Not assigned'
    END as status,
    al.listing_metadata->>'address' as address
FROM apartmentlisting al
ORDER BY al.id
LIMIT 20;

-- Step 4: Verify the update
SELECT 
    s.property_manager_id,
    pm.name as property_manager_name,
    COUNT(al.id) as listing_count
FROM apartmentlisting al
JOIN source s ON al.source_id = s.source_id
JOIN propertymanager pm ON s.property_manager_id = pm.property_manager_id
WHERE pm.email = 'john.smith@testcompany.com'
GROUP BY s.property_manager_id, pm.name;

-- Step 5: See all listings now associated with your PM
SELECT 
    al.id,
    al.source_id,
    al.listing_metadata->>'address' as address,
    al.listing_metadata->>'price' as price,
    al.listing_metadata->>'bedrooms' as bedrooms
FROM apartmentlisting al
JOIN source s ON al.source_id = s.source_id
JOIN propertymanager pm ON s.property_manager_id = pm.property_manager_id
WHERE pm.email = 'john.smith@testcompany.com'
ORDER BY al.id
LIMIT 20;  -- Preview first 20

