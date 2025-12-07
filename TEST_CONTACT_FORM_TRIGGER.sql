-- Test Contact Form Trigger
-- This will insert a test contact form and trigger the email

-- Insert a test contact form submission
INSERT INTO contactform (name, email, message, subject, phone)
VALUES (
  'Test User',
  'test@example.com',
  'This is a test message to verify the email trigger is working.',
  'Test Subject - Please Ignore',
  '+1234567890'
)
RETURNING contact_id, name, email, submitted_at;

-- After running this, check:
-- 1. Supabase Dashboard → Edge Functions → send-contact-email → Logs
-- 2. Check your email inbox (the RECIPIENT_EMAIL configured in Edge Function secrets)
-- 3. Check Supabase Dashboard → Database → Logs for trigger errors
