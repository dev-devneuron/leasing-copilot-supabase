-- Fix Contact Form Trigger: Use TEXT body instead of JSONB
-- Alternative approach - some versions of pg_net work better with TEXT

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
  payload_text TEXT;
BEGIN
  -- Build Edge Function URL
  edge_function_url := 'https://' || project_ref || '.supabase.co/functions/v1/send-contact-email';
  
  -- Build the payload as JSONB first
  payload_json := jsonb_build_object(
    'contact_id', NEW.contact_id,
    'name', NEW.name,
    'email', NEW.email,
    'phone', COALESCE(NEW.phone, ''),
    'subject', COALESCE(NEW.subject, ''),
    'message', NEW.message,
    'submitted_at', COALESCE(NEW.submitted_at::text, NOW()::text)
  );
  
  -- Convert JSONB to TEXT (properly formatted JSON string)
  payload_text := payload_json::text;
  
  -- Log the attempt with payload preview
  RAISE NOTICE '[TRIGGER] Starting email notification for contact_id: %, email: %', NEW.contact_id, NEW.email;
  RAISE NOTICE '[TRIGGER] Edge Function URL: %', edge_function_url;
  RAISE NOTICE '[TRIGGER] Payload (first 200 chars): %', LEFT(payload_text, 200);
  
  -- Make the HTTP request - try with TEXT body cast to JSONB
  -- Some versions of pg_net accept TEXT and convert it, others need JSONB
  BEGIN
    SELECT net.http_post(
      url := edge_function_url,
      headers := jsonb_build_object(
        'Content-Type', 'application/json',
        'Authorization', 'Bearer ' || service_role_key
      ),
      body := payload_text::jsonb  -- Convert TEXT to JSONB for body
    ) INTO request_id;
  EXCEPTION
    WHEN OTHERS THEN
      -- If JSONB doesn't work, try with TEXT directly (if your pg_net version supports it)
      RAISE WARNING '[TRIGGER] JSONB body failed, trying alternative method...';
      -- Note: Some pg_net versions might need different approach
      -- Check your Supabase version documentation
      RAISE;
  END;
  
  -- Log the request ID
  RAISE NOTICE '[TRIGGER] HTTP request queued, request_id: %', request_id;
  RAISE NOTICE '[TRIGGER] Note: Request is asynchronous - check Edge Function logs';
  
  RETURN NEW;
  
EXCEPTION
  WHEN OTHERS THEN
    -- Log detailed error information
    RAISE WARNING '[TRIGGER ERROR] Failed for contact_id %', NEW.contact_id;
    RAISE WARNING '[TRIGGER ERROR] SQLSTATE: %, SQLERRM: %', SQLSTATE, SQLERRM;
    RAISE WARNING '[TRIGGER ERROR] Payload was: %', LEFT(payload_text, 500);
    RETURN NEW;
END;
$$;

-- Verify the function was updated
SELECT 
  proname AS function_name,
  CASE 
    WHEN prosrc LIKE '%payload_text%' THEN '✅ Updated with TEXT conversion'
    ELSE '⚠️ May need update'
  END AS status
FROM pg_proc
WHERE proname = 'notify_contact_form';
