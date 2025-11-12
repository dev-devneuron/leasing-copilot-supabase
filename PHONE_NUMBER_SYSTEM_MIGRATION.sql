-- =====================================================
-- PHONE NUMBER REQUEST & ASSIGNMENT SYSTEM MIGRATION
-- =====================================================
-- This migration adds support for PM phone number requests
-- and tech team-managed phone number purchases/assignments

-- =====================================================
-- STEP 1: CREATE PHONE NUMBER REQUEST TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS phonenumberrequest (
    request_id SERIAL PRIMARY KEY,
    property_manager_id INTEGER NOT NULL,
    area_code VARCHAR(10),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    notes TEXT,
    requested_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    fulfilled_at TIMESTAMP WITH TIME ZONE,
    FOREIGN KEY (property_manager_id) REFERENCES propertymanager(property_manager_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_phonenumberrequest_pm_id ON phonenumberrequest(property_manager_id);
CREATE INDEX IF NOT EXISTS idx_phonenumberrequest_status ON phonenumberrequest(status);

-- =====================================================
-- STEP 2: CREATE PURCHASED PHONE NUMBER TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS purchasedphonenumber (
    purchased_phone_number_id SERIAL PRIMARY KEY,
    property_manager_id INTEGER NOT NULL,
    phone_number VARCHAR(20) NOT NULL UNIQUE,
    twilio_sid VARCHAR(50) NOT NULL UNIQUE,
    vapi_phone_number_id VARCHAR(50),
    status VARCHAR(20) NOT NULL DEFAULT 'available',
    assigned_to_type VARCHAR(20),
    assigned_to_id INTEGER,
    purchased_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    assigned_at TIMESTAMP WITH TIME ZONE,
    notes TEXT,
    FOREIGN KEY (property_manager_id) REFERENCES propertymanager(property_manager_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_purchasedphonenumber_pm_id ON purchasedphonenumber(property_manager_id);
CREATE INDEX IF NOT EXISTS idx_purchasedphonenumber_status ON purchasedphonenumber(status);
CREATE INDEX IF NOT EXISTS idx_purchasedphonenumber_phone ON purchasedphonenumber(phone_number);
CREATE INDEX IF NOT EXISTS idx_purchasedphonenumber_assigned ON purchasedphonenumber(assigned_to_type, assigned_to_id);

-- =====================================================
-- STEP 3: ADD PURCHASED PHONE NUMBER ID TO PROPERTY MANAGER
-- =====================================================
ALTER TABLE propertymanager 
ADD COLUMN IF NOT EXISTS purchased_phone_number_id INTEGER;

-- Add foreign key constraint (drop first if exists to avoid errors)
DO $$ 
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'fk_pm_purchased_phone'
    ) THEN
        ALTER TABLE propertymanager DROP CONSTRAINT fk_pm_purchased_phone;
    END IF;
END $$;

ALTER TABLE propertymanager
ADD CONSTRAINT fk_pm_purchased_phone 
FOREIGN KEY (purchased_phone_number_id) 
REFERENCES purchasedphonenumber(purchased_phone_number_id) 
ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_propertymanager_purchased_phone ON propertymanager(purchased_phone_number_id);

-- =====================================================
-- STEP 4: ADD PURCHASED PHONE NUMBER ID TO REALTOR
-- =====================================================
ALTER TABLE realtor 
ADD COLUMN IF NOT EXISTS purchased_phone_number_id INTEGER;

-- Add foreign key constraint (drop first if exists to avoid errors)
DO $$ 
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'fk_realtor_purchased_phone'
    ) THEN
        ALTER TABLE realtor DROP CONSTRAINT fk_realtor_purchased_phone;
    END IF;
END $$;

ALTER TABLE realtor
ADD CONSTRAINT fk_realtor_purchased_phone 
FOREIGN KEY (purchased_phone_number_id) 
REFERENCES purchasedphonenumber(purchased_phone_number_id) 
ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_realtor_purchased_phone ON realtor(purchased_phone_number_id);

-- =====================================================
-- STEP 5: UPDATE EXISTING DATA (if needed)
-- =====================================================
-- If you have existing phone numbers in twilio_contact fields,
-- you can migrate them to the new system by creating PurchasedPhoneNumber
-- records. This is optional and should be done manually by tech team.

-- =====================================================
-- VERIFICATION QUERIES
-- =====================================================
-- Check tables were created:
-- SELECT table_name FROM information_schema.tables 
-- WHERE table_name IN ('phonenumberrequest', 'purchasedphonenumber');

-- Check columns were added:
-- SELECT column_name FROM information_schema.columns 
-- WHERE table_name = 'propertymanager' AND column_name = 'purchased_phone_number_id';
-- SELECT column_name FROM information_schema.columns 
-- WHERE table_name = 'realtor' AND column_name = 'purchased_phone_number_id';

