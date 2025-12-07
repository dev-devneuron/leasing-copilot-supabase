-- Email Notification Trigger for Contact Form
-- This trigger sends email notifications when a contact form is submitted

-- Enable pg_net extension (required for HTTP requests from triggers)
CREATE EXTENSION IF NOT EXISTS pg_net;
GRANT USAGE ON SCHEMA net TO postgres;

-- Create function to notify Edge Function when a contact form is inserted
CREATE OR REPLACE FUNCTION notify_contact_form()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  project_ref TEXT := 'cmpywleowxnvucymvwgv';
  service_role_key TEXT := 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNtcHl3bGVvd3hudnVjeW12d2d2Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1Mzg0OTAyNSwiZXhwIjoyMDY5NDI1MDI1fQ.Wqr-HNkeWSIYt6Okc38FCgq8lppsf2c2EPvr5S5e1qc';
  edge_function_url TEXT;
  request_id BIGINT;
  payload_json JSONB;
BEGIN
  -- Build Edge Function URL
  edge_function_url := 'https://' || project_ref || '.supabase.co/functions/v1/send-contact-email';
  
  -- Build the payload as JSONB
  payload_json := jsonb_build_object(
    'contact_id', NEW.contact_id,
    'name', NEW.name,
    'email', NEW.email,
    'phone', COALESCE(NEW.phone, ''),
    'subject', COALESCE(NEW.subject, ''),
    'message', NEW.message,
    'submitted_at', COALESCE(NEW.submitted_at::text, NOW()::text)
  );
  
  -- Log the attempt
  RAISE NOTICE '[TRIGGER] Starting email notification for contact_id: %, email: %', NEW.contact_id, NEW.email;
  RAISE NOTICE '[TRIGGER] Edge Function URL: %', edge_function_url;
  
  -- Make the HTTP request (body is jsonb)
  SELECT net.http_post(
    url := edge_function_url,
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'Authorization', 'Bearer ' || service_role_key
    ),
    body := payload_json
  ) INTO request_id;
  
  -- Log the request ID
  RAISE NOTICE '[TRIGGER] HTTP request queued, request_id: %', request_id;
  RAISE NOTICE '[TRIGGER] Note: Request is asynchronous - check Edge Function logs';
  
  RETURN NEW;
  
EXCEPTION
  WHEN OTHERS THEN
    -- Log detailed error information
    RAISE WARNING '[TRIGGER ERROR] Failed for contact_id %', NEW.contact_id;
    RAISE WARNING '[TRIGGER ERROR] SQLSTATE: %, SQLERRM: %', SQLSTATE, SQLERRM;
    RETURN NEW;
END;
$$;

-- Drop existing trigger if it exists
DROP TRIGGER IF EXISTS on_contact_form_insert ON contactform;

-- Create trigger on contactform table
CREATE TRIGGER on_contact_form_insert
  AFTER INSERT ON contactform
  FOR EACH ROW
  EXECUTE FUNCTION notify_contact_form();

-- Verify trigger was created
SELECT 
  tgname AS trigger_name,
  tgrelid::regclass AS table_name,
  proname AS function_name,
  CASE tgenabled
    WHEN 'O' THEN '✅ Enabled'
    WHEN 'D' THEN '❌ Disabled'
    ELSE '❓ Unknown'
  END AS status
FROM pg_trigger t
JOIN pg_proc p ON t.tgfoid = p.oid
WHERE tgname = 'on_contact_form_insert';

COMMENT ON FUNCTION notify_contact_form() IS 'Sends email notification via Edge Function when a contact form is submitted';
COMMENT ON TRIGGER on_contact_form_insert ON contactform IS 'Triggers email notification after contact form insert';
