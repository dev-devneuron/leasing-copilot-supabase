-- Update Assistant ID for the user who owns the "Leasing Copilot" assistant
-- Assistant ID: d37218d3-0b5f-4683-87ea-9ed447d925ae
-- Assistant Name: Leasing Copilot

-- First, check which users exist (to help identify which one should get this assistant ID)
SELECT 
    'PropertyManager' as user_type,
    property_manager_id as user_id,
    name,
    email,
    vapi_assistant_id as current_assistant_id
FROM propertymanager
ORDER BY property_manager_id;

SELECT 
    'Realtor' as user_type,
    realtor_id as user_id,
    name,
    email,
    vapi_assistant_id as current_assistant_id
FROM realtor
ORDER BY realtor_id;

-- Update Property Manager (replace property_manager_id = 1 with the correct ID)
-- Uncomment and modify the line below with the correct property_manager_id:
-- UPDATE propertymanager
-- SET vapi_assistant_id = 'd37218d3-0b5f-4683-87ea-9ed447d925ae'
-- WHERE property_manager_id = 1;  -- CHANGE THIS TO THE CORRECT ID

-- OR Update Realtor (replace realtor_id = 1 with the correct ID)
-- Uncomment and modify the line below with the correct realtor_id:
-- UPDATE realtor
-- SET vapi_assistant_id = 'd37218d3-0b5f-4683-87ea-9ed447d925ae'
-- WHERE realtor_id = 1;  -- CHANGE THIS TO THE CORRECT ID

-- After updating, verify the change:
SELECT 
    'PropertyManager' as user_type,
    property_manager_id as user_id,
    name,
    email,
    vapi_assistant_id
FROM propertymanager
WHERE vapi_assistant_id = 'd37218d3-0b5f-4683-87ea-9ed447d925ae'

UNION ALL

SELECT 
    'Realtor' as user_type,
    realtor_id as user_id,
    name,
    email,
    vapi_assistant_id
FROM realtor
WHERE vapi_assistant_id = 'd37218d3-0b5f-4683-87ea-9ed447d925ae';
