-- Performance-focused indexes for Leasap Backend
-- Run this file in your Supabase/Postgres SQL editor.
-- All indexes use IF NOT EXISTS so they are safe to apply repeatedly.

-- ============================================================================
-- MAINTENANCEREQUEST: core table for tickets & dashboards
-- ============================================================================

-- Fast lookup by primary key is automatic, but we add targeted secondary indexes
-- for frequent filters / joins used by APIs and background workers.

CREATE INDEX IF NOT EXISTS idx_maintenancerequest_property_manager_id
ON maintenancerequest(property_manager_id);

CREATE INDEX IF NOT EXISTS idx_maintenancerequest_property_id
ON maintenancerequest(property_id);

CREATE INDEX IF NOT EXISTS idx_maintenancerequest_tenant_id
ON maintenancerequest(tenant_id);

CREATE INDEX IF NOT EXISTS idx_maintenancerequest_vapi_call_id
ON maintenancerequest(vapi_call_id);

CREATE INDEX IF NOT EXISTS idx_maintenancerequest_vendor_call_status
ON maintenancerequest(vendor_call_status);

CREATE INDEX IF NOT EXISTS idx_maintenancerequest_assigned_vendor_id
ON maintenancerequest(assigned_vendor_id);

CREATE INDEX IF NOT EXISTS idx_maintenancerequest_submitted_at
ON maintenancerequest(submitted_at);

-- ============================================================================
-- VENDOR CALLING TABLES
-- ============================================================================

-- VendorCallQueue: lookups by maintenance_request_id and status are common
CREATE INDEX IF NOT EXISTS idx_vendorcallqueue_maintenance_request_id
ON vendorcallqueue(maintenance_request_id);

CREATE INDEX IF NOT EXISTS idx_vendorcallqueue_status
ON vendorcallqueue(status);

-- VendorCallAttempt: heavily used for status polling & reporting
CREATE INDEX IF NOT EXISTS idx_vendorcallattempt_maintenance_request_id
ON vendorcallattempt(maintenance_request_id);

CREATE INDEX IF NOT EXISTS idx_vendorcallattempt_vendor_id
ON vendorcallattempt(vendor_id);

CREATE INDEX IF NOT EXISTS idx_vendorcallattempt_vapi_call_id
ON vendorcallattempt(vapi_call_id);

CREATE INDEX IF NOT EXISTS idx_vendorcallattempt_call_status
ON vendorcallattempt(call_status);

-- ============================================================================
-- CALL RECORDS & CONTACTS (for outbound & history lookups)
-- ============================================================================

-- CallRecord: used when loading latest extracted_intel per caller
CREATE INDEX IF NOT EXISTS idx_callrecord_caller_number_created_at
ON callrecord(caller_number, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_callrecord_extraction_status_created_at
ON callrecord(extraction_status, created_at DESC);

-- Contact: fast lookup by phone number
CREATE INDEX IF NOT EXISTS idx_contact_phone_number
ON contact(phone_number);

-- ============================================================================
-- VENDORS & PROPERTY VENDOR LINKING
-- ============================================================================

-- Vendor: filters by PM, service_type, active/opted_out are common
CREATE INDEX IF NOT EXISTS idx_vendor_property_manager_id
ON vendor(property_manager_id);

CREATE INDEX IF NOT EXISTS idx_vendor_service_type
ON vendor(service_type);

CREATE INDEX IF NOT EXISTS idx_vendor_is_active_opted_out
ON vendor(is_active, opted_out);

-- PropertyVendor: lookups by property_id & service_type for matching
CREATE INDEX IF NOT EXISTS idx_propertyvendor_property_id_service_type
ON propertyvendor(property_id, service_type);

CREATE INDEX IF NOT EXISTS idx_propertyvendor_property_id_priority
ON propertyvendor(property_id, priority);

-- ============================================================================
-- GENERAL NOTES
-- ============================================================================
-- 1. Apply these indexes in a maintenance window if your tables are very large;
--    index creation can take time but is online-safe for most workloads.
-- 2. After applying, monitor slow query logs to see which queries improved and
--    whether any additional composite indexes are needed for your specific usage.
-- 3. All indexes here are read-optimization only and do not change application
--    behavior or data semantics.

