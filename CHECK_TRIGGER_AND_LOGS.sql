-- Check Trigger Status and Recent Activity
-- Run this to see if trigger is firing and what's happening

-- 1. Check trigger status
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

-- 2. Check recent contact form submissions
SELECT 
  contact_id,
  name,
  email,
  submitted_at
FROM contactform
ORDER BY submitted_at DESC
LIMIT 5;

-- 3. Check if pg_net extension is enabled
SELECT 
  extname AS extension_name,
  extversion AS version
FROM pg_extension
WHERE extname = 'pg_net';

-- 4. Check recent HTTP requests from pg_net (if available)
-- Note: This might not be available in all Supabase plans
SELECT 
  id,
  url,
  method,
  status_code,
  created_at
FROM net.http_request_queue
ORDER BY created_at DESC
LIMIT 10;

-- 5. Test the trigger function manually with a test payload
-- Uncomment to test:
/*
DO $$
DECLARE
  test_payload JSONB;
  result BIGINT;
BEGIN
  test_payload := jsonb_build_object(
    'contact_id', 999,
    'name', 'Test User',
    'email', 'test@example.com',
    'phone', '+1234567890',
    'subject', 'Test Subject',
    'message', 'Test message',
    'submitted_at', NOW()::text
  );
  
  RAISE NOTICE 'Test payload: %', test_payload::text;
  
  -- This will show if the HTTP request can be made
  SELECT net.http_post(
    url := 'https://cmpywleowxnvucymvwgv.supabase.co/functions/v1/send-contact-email',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'Authorization', 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNtcHl3bGVvd3hudnVjeW12d2d2Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1Mzg0OTAyNSwiZXhwIjoyMDY5NDI1MDI1fQ.Wqr-HNkeWSIYt6Okc38FCgq8lppsf2c2EPvr5S5e1qc'
    ),
    body := test_payload
  ) INTO result;
  
  RAISE NOTICE 'HTTP request ID: %', result;
END $$;
*/
