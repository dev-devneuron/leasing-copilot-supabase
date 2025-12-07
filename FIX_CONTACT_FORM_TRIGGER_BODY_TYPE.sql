-- Fix Contact Form Trigger: Use JSONB body (same as demo trigger fix)
-- The net.http_post function expects body as jsonb, not text
-- This matches the working demo trigger pattern

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
  payload_json JSONB;  -- Use JSONB directly (same as demo trigger)
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
  RAISE NOTICE '[TRIGGER] Payload: %', payload_json::text;
  
  -- Make the HTTP request (body is jsonb, not text) - same as demo trigger
  SELECT net.http_post(
    url := edge_function_url,
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'Authorization', 'Bearer ' || service_role_key
    ),
    body := payload_json  -- Pass JSONB directly (same as working demo trigger)
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

-- Verify the function was updated
SELECT 
  proname AS function_name,
  CASE 
    WHEN pg_get_functiondef(oid) LIKE '%body := payload_json%' AND pg_get_functiondef(oid) LIKE '%payload_json JSONB%' THEN '✅ Updated with JSONB (same as demo trigger)'
    ELSE '⚠️ May need update'
  END AS status
FROM pg_proc
WHERE proname = 'notify_contact_form';
