-- Quick check: Are listings from listings_test_malformed.json in database?
SELECT 
    id,
    listing_metadata->>'address' as address,
    listing_metadata->>'price' as price,
    listing_metadata->>'bedrooms' as bedrooms,
    listing_metadata->>'bathrooms' as bathrooms,
    listing_metadata->>'property_type' as property_type,
    CASE WHEN embedding IS NOT NULL THEN '✅' ELSE '❌' END as has_embedding
FROM apartmentlisting
WHERE 
    listing_metadata->>'address' ILIKE '%Maple Drive%' OR
    listing_metadata->>'address' ILIKE '%Cedar Lane%' OR
    listing_metadata->>'address' ILIKE '%Birch Court%'
ORDER BY id DESC;

