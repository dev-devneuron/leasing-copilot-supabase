-- Script to update VAPI assistant IDs for Property Managers and Realtors
-- Run this after configuring assistants in VAPI to link them to users

-- Example: Update Property Manager assistant ID
-- UPDATE propertymanager
-- SET vapi_assistant_id = 'd37218d3-0b5f-4683-87ea-9ed447d925ae'
-- WHERE property_manager_id = 1;

-- Example: Update Realtor assistant ID
-- UPDATE realtor
-- SET vapi_assistant_id = 'd37218d3-0b5f-4683-87ea-9ed447d925ae'
-- WHERE realtor_id = 1;

-- Check current assistant IDs
SELECT 
    'PropertyManager' as user_type,
    property_manager_id as user_id,
    name,
    email,
    vapi_assistant_id
FROM propertymanager
WHERE vapi_assistant_id IS NOT NULL

UNION ALL

SELECT 
    'Realtor' as user_type,
    realtor_id as user_id,
    name,
    email,
    vapi_assistant_id
FROM realtor
WHERE vapi_assistant_id IS NOT NULL;

-- Find users without assistant IDs
SELECT 
    'PropertyManager' as user_type,
    property_manager_id as user_id,
    name,
    email,
    'No assistant ID configured' as status
FROM propertymanager
WHERE vapi_assistant_id IS NULL

UNION ALL

SELECT 
    'Realtor' as user_type,
    realtor_id as user_id,
    name,
    email,
    'No assistant ID configured' as status
FROM realtor
WHERE vapi_assistant_id IS NULL;
