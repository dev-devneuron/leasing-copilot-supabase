# Email Notification Triggers Setup

## ✅ Completed Setup

### Demo Request Trigger
- **Function:** `notify_demo_request()`
- **Trigger:** `on_demo_request_insert` on `demorequest` table
- **Edge Function:** `send-demo-email`
- **Status:** ✅ Working

### Contact Form Trigger
- **Function:** `notify_contact_form()`
- **Trigger:** `on_contact_form_insert` (auto-detects table name)
- **Edge Function:** `send-contact-email`
- **Status:** Ready to deploy

---

## 📋 Files Kept

### Working Files
- `FIX_TRIGGER_BODY_TYPE.sql` - The working fix for demo trigger (uses jsonb)
- `migration_contact_email_trigger.sql` - Contact form trigger (ready to run)
- `supabase/functions/send-demo-email/index.ts` - Demo email Edge Function ✅
- `supabase/functions/send-contact-email/index.ts` - Contact email Edge Function ✅
- `EMAIL_NOTIFICATIONS_SETUP.md` - Main setup documentation
- `ZOHO_MAIL_SETUP.md` - Zoho Mail configuration guide

---

## 🚀 Deploy Contact Form Trigger

### Step 1: Run the Migration

1. Go to **Supabase Dashboard → SQL Editor**
2. Open `migration_contact_email_trigger.sql`
3. Run the entire script

The script will:
- ✅ Enable pg_net extension
- ✅ Create `notify_contact_form()` function
- ✅ Auto-detect the contact form table name
- ✅ Create the trigger on the correct table
- ✅ Verify the trigger was created

### Step 2: Verify Table Name

If the script can't find the table, it will show a warning. Check what table name your contact form uses:

```sql
-- Find contact form table
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND (table_name LIKE '%contact%' OR table_name LIKE '%form%')
ORDER BY table_name;
```

If the table has a different name, update the trigger creation in the script.

### Step 3: Test the Trigger

```sql
-- Enable notices
SET client_min_messages TO NOTICE;

-- Insert a test contact form submission
-- Replace with your actual table name and columns
INSERT INTO contactform (name, email, phone, subject, message)
VALUES (
  'Test User',
  'test@example.com',
  '+1234567890',
  'Test Subject',
  'This is a test message'
);
```

### Step 4: Check Results

1. **SQL Editor output:** Should see `[TRIGGER]` NOTICE messages
2. **Edge Function logs:** Dashboard → Edge Functions → send-contact-email → Logs
3. **Email inbox:** Check `founders@leasap.com` (or your RECIPIENT_EMAIL)

---

## 🔧 Edge Functions

Both Edge Functions are updated to:
- ✅ Use `Deno.serve` (Supabase standard)
- ✅ Include proper type definitions
- ✅ Handle JSON parsing errors
- ✅ Log received payloads for debugging
- ✅ Support Zoho Mail SMTP configuration

---

## 📝 Notes

- Both triggers use `jsonb` for the HTTP body (required by `net.http_post`)
- Triggers are asynchronous - check Edge Function logs for execution status
- SMTP secrets must be set in Supabase Dashboard → Project Settings → Edge Functions → Secrets

---

## 🆘 Troubleshooting

If contact form trigger doesn't work:

1. **Check table name:** Run the table finder query above
2. **Check trigger exists:** 
   ```sql
   SELECT tgname, tgrelid::regclass, tgenabled
   FROM pg_trigger
   WHERE tgname = 'on_contact_form_insert';
   ```
3. **Check Edge Function logs:** Dashboard → Edge Functions → send-contact-email → Logs
4. **Verify SMTP secrets:** Dashboard → Project Settings → Edge Functions → Secrets

---

**Both triggers are ready! Run `migration_contact_email_trigger.sql` to set up the contact form trigger.**
