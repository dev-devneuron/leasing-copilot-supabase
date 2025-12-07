-- Diagnostic Script for Contact Form Email Issue
-- Run this in Supabase SQL Editor to check what's wrong

-- 1. Check if trigger exists and is enabled
SELECT 
  tgname AS trigger_name,
  tgrelid::regclass AS table_name,
  proname AS function_name,
  CASE tgenabled
    WHEN 'O' THEN '✅ Enabled'
    WHEN 'D' THEN '❌ Disabled'
    WHEN 'R' THEN '⚠️ Replica'
    WHEN 'A' THEN '⚠️ Always'
    ELSE '❓ Unknown'
  END AS status
FROM pg_trigger t
JOIN pg_proc p ON t.tgfoid = p.oid
WHERE tgname = 'on_contact_form_insert';

-- 2. Check if the function exists
SELECT 
  proname AS function_name,
  prosrc AS function_source
FROM pg_proc
WHERE proname = 'notify_contact_form';

-- 3. Check if pg_net extension is enabled
SELECT 
  extname AS extension_name,
  extversion AS version
FROM pg_extension
WHERE extname = 'pg_net';

-- 4. Check recent contact form submissions
SELECT 
  contact_id,
  name,
  email,
  submitted_at,
  updated_at
FROM contactform
ORDER BY submitted_at DESC
LIMIT 5;

-- 5. Check if Edge Function exists (this will show in logs if called)
-- You'll need to check Supabase Dashboard → Edge Functions → send-contact-email

-- 6. Test the trigger manually (uncomment to test)
/*
INSERT INTO contactform (name, email, message, subject)
VALUES ('Test User', 'test@example.com', 'This is a test message', 'Test Subject');
*/

-- 7. Check for any errors in the function
SELECT 
  schemaname,
  funcname,
  calls,
  total_time,
  self_time
FROM pg_stat_user_functions
WHERE funcname = 'notify_contact_form';
