-- Create Contact Form Table
-- This table stores contact form submissions from the website

CREATE TABLE IF NOT EXISTS contactform (
    contact_id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    subject VARCHAR(500),
    message TEXT NOT NULL,
    submitted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create index on email for faster lookups
CREATE INDEX IF NOT EXISTS idx_contactform_email ON contactform(email);
CREATE INDEX IF NOT EXISTS idx_contactform_submitted_at ON contactform(submitted_at);

-- Add comments
COMMENT ON TABLE contactform IS 'Stores contact form submissions from the website';
COMMENT ON COLUMN contactform.contact_id IS 'Primary key, auto-incrementing ID';
COMMENT ON COLUMN contactform.name IS 'Name of the person submitting the form';
COMMENT ON COLUMN contactform.email IS 'Email address of the submitter';
COMMENT ON COLUMN contactform.phone IS 'Optional phone number';
COMMENT ON COLUMN contactform.subject IS 'Optional subject line';
COMMENT ON COLUMN contactform.message IS 'The message content';
COMMENT ON COLUMN contactform.submitted_at IS 'Timestamp when the form was submitted';
COMMENT ON COLUMN contactform.updated_at IS 'Timestamp when the record was last updated';
