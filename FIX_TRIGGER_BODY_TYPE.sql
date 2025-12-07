-- Fix Trigger: Change body parameter from text to jsonb
-- The net.http_post function expects body as jsonb, not text

CREATE OR REPLACE FUNCTION notify_demo_request()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  project_ref TEXT := 'cmpywleowxnvucymvwgv';
  service_role_key TEXT := 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNtcHl3bGVvd3hudnVjeW12d2d2Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1Mzg0OTAyNSwiZXhwIjoyMDY5NDI1MDI1fQ.Wqr-HNkeWSIYt6Okc38FCgq8lppsf2c2EPvr5S5e1qc';
  edge_function_url TEXT;
  request_id BIGINT;
  payload_json JSONB;  -- Changed from TEXT to JSONB
BEGIN
  -- Build Edge Function URL
  edge_function_url := 'https://' || project_ref || '.supabase.co/functions/v1/send-demo-email';
  
  -- Build the payload as JSONB
  payload_json := jsonb_build_object(
    'demo_request_id', NEW.demo_request_id,
    'name', NEW.name,
    'email', NEW.email,
    'phone', NEW.phone,
    'company_name', COALESCE(NEW.company_name, ''),
    'preferred_date', COALESCE(NEW.preferred_date::text, ''),
    'preferred_time', COALESCE(NEW.preferred_time, ''),
    'timezone', COALESCE(NEW.timezone, ''),
    'notes', COALESCE(NEW.notes, ''),
    'status', NEW.status,
    'requested_at', COALESCE(NEW.requested_at::text, NOW()::text)
  );
  
  -- Log the attempt
  RAISE NOTICE '[TRIGGER] Starting email notification for demo_request_id: %, email: %', NEW.demo_request_id, NEW.email;
  RAISE NOTICE '[TRIGGER] Edge Function URL: %', edge_function_url;
  
  -- Make the HTTP request (body is now jsonb, not text)
  SELECT net.http_post(
    url := edge_function_url,
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'Authorization', 'Bearer ' || service_role_key
    ),
    body := payload_json  -- Now passing jsonb directly
  ) INTO request_id;
  
  -- Log the request ID
  RAISE NOTICE '[TRIGGER] HTTP request queued, request_id: %', request_id;
  RAISE NOTICE '[TRIGGER] Note: Request is asynchronous - check Edge Function logs';
  
  RETURN NEW;
  
EXCEPTION
  WHEN OTHERS THEN
    -- Log detailed error information
    RAISE WARNING '[TRIGGER ERROR] Failed for demo_request_id %', NEW.demo_request_id;
    RAISE WARNING '[TRIGGER ERROR] SQLSTATE: %, SQLERRM: %', SQLSTATE, SQLERRM;
    RETURN NEW;
END;
$$;

-- Verify the function was updated
SELECT 
  proname AS function_name,
  pg_get_functiondef(oid) LIKE '%jsonb%' AS uses_jsonb
FROM pg_proc
WHERE proname = 'notify_demo_request';
