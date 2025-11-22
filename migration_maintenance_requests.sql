-- Migration: Add Tenant and MaintenanceRequest tables
-- Run this migration to enable the maintenance request logging feature

-- Create Tenant table (without realtor_id foreign key first)
CREATE TABLE IF NOT EXISTS tenant (
    tenant_id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    phone_number TEXT,
    email TEXT,
    property_id INTEGER NOT NULL REFERENCES apartmentlisting(id),
    property_manager_id INTEGER NOT NULL REFERENCES propertymanager(property_manager_id),
    realtor_id INTEGER,
    unit_number TEXT,
    lease_start_date DATE,
    lease_end_date DATE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Add missing columns if table already exists from previous migration attempt
ALTER TABLE tenant ADD COLUMN IF NOT EXISTS realtor_id INTEGER;
ALTER TABLE tenant ADD COLUMN IF NOT EXISTS lease_start_date DATE;
ALTER TABLE tenant ADD COLUMN IF NOT EXISTS lease_end_date DATE;
ALTER TABLE tenant ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;

-- Create indexes for Tenant table
CREATE INDEX IF NOT EXISTS idx_tenant_name ON tenant(name);
CREATE INDEX IF NOT EXISTS idx_tenant_phone ON tenant(phone_number);
CREATE INDEX IF NOT EXISTS idx_tenant_email ON tenant(email);
CREATE INDEX IF NOT EXISTS idx_tenant_property_id ON tenant(property_id);
CREATE INDEX IF NOT EXISTS idx_tenant_property_manager_id ON tenant(property_manager_id);
CREATE INDEX IF NOT EXISTS idx_tenant_realtor_id ON tenant(realtor_id);
CREATE INDEX IF NOT EXISTS idx_tenant_is_active ON tenant(is_active);

-- Create MaintenanceRequest table (without realtor foreign key first)
CREATE TABLE IF NOT EXISTS maintenancerequest (
    maintenance_request_id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenant(tenant_id),
    property_id INTEGER NOT NULL REFERENCES apartmentlisting(id),
    property_manager_id INTEGER NOT NULL REFERENCES propertymanager(property_manager_id),
    issue_description TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'normal',
    status TEXT NOT NULL DEFAULT 'pending',
    category TEXT,
    location TEXT,
    tenant_name TEXT NOT NULL,
    tenant_phone TEXT,
    tenant_email TEXT,
    submitted_via TEXT NOT NULL DEFAULT 'phone',
    vapi_call_id TEXT,
    call_transcript TEXT,
    assigned_to_realtor_id INTEGER,
    pm_notes TEXT,
    resolution_notes TEXT,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- Add missing columns if table already exists from previous migration attempt
ALTER TABLE maintenancerequest ADD COLUMN IF NOT EXISTS assigned_to_realtor_id INTEGER;

-- Create indexes for MaintenanceRequest table
CREATE INDEX IF NOT EXISTS idx_maintenance_request_tenant_id ON maintenancerequest(tenant_id);
CREATE INDEX IF NOT EXISTS idx_maintenance_request_property_id ON maintenancerequest(property_id);
CREATE INDEX IF NOT EXISTS idx_maintenance_request_property_manager_id ON maintenancerequest(property_manager_id);
CREATE INDEX IF NOT EXISTS idx_maintenance_request_status ON maintenancerequest(status);
CREATE INDEX IF NOT EXISTS idx_maintenance_request_submitted_at ON maintenancerequest(submitted_at DESC);
CREATE INDEX IF NOT EXISTS idx_maintenance_request_assigned_realtor ON maintenancerequest(assigned_to_realtor_id);

-- Add foreign key constraints to realtor table
-- Since the realtor table exists with realtor_id column, we can add constraints directly
DO $$
BEGIN
    -- Add foreign key constraint for tenant.realtor_id
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_constraint
        WHERE conname = 'tenant_realtor_id_fkey'
    ) THEN
        BEGIN
            ALTER TABLE tenant 
            ADD CONSTRAINT tenant_realtor_id_fkey 
            FOREIGN KEY (realtor_id) REFERENCES public.realtor(realtor_id);
        EXCEPTION
            WHEN OTHERS THEN
                RAISE NOTICE 'Could not add tenant_realtor_id_fkey: %', SQLERRM;
        END;
    END IF;
    
    -- Add foreign key constraint for maintenancerequest.assigned_to_realtor_id
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_constraint
        WHERE conname = 'maintenancerequest_assigned_to_realtor_id_fkey'
    ) THEN
        BEGIN
            ALTER TABLE maintenancerequest 
            ADD CONSTRAINT maintenancerequest_assigned_to_realtor_id_fkey 
            FOREIGN KEY (assigned_to_realtor_id) REFERENCES public.realtor(realtor_id);
        EXCEPTION
            WHEN OTHERS THEN
                RAISE NOTICE 'Could not add maintenancerequest_assigned_to_realtor_id_fkey: %', SQLERRM;
        END;
    END IF;
END $$;

-- Add comments for documentation
COMMENT ON TABLE tenant IS 'Tenants renting properties managed by Property Managers';
COMMENT ON TABLE maintenancerequest IS 'Maintenance requests submitted by tenants via phone/text/email';
COMMENT ON COLUMN tenant.phone_number IS 'Phone number in E.164 format (e.g., +14125551234)';
COMMENT ON COLUMN maintenancerequest.priority IS 'Priority level: low, normal, high, urgent';
COMMENT ON COLUMN maintenancerequest.status IS 'Request status: pending, in_progress, completed, cancelled';
COMMENT ON COLUMN maintenancerequest.submitted_via IS 'How the request was submitted: phone, text, email';

