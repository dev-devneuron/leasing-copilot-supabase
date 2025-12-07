# Troubleshooting: Contact Form Email Not Sending

## 🔍 Quick Diagnostic Steps

### Step 1: Run Diagnostic SQL
Run `DIAGNOSE_CONTACT_FORM_EMAIL.sql` in Supabase SQL Editor to check:
- ✅ Trigger exists and is enabled
- ✅ Function exists
- ✅ pg_net extension is enabled
- ✅ Recent submissions are being recorded

### Step 2: Check Edge Function Deployment
1. Go to **Supabase Dashboard → Edge Functions**
2. Verify `send-contact-email` function exists
3. If missing, deploy it:
   ```bash
   supabase functions deploy send-contact-email
   ```

### Step 3: Verify SMTP Secrets
1. Go to **Supabase Dashboard → Project Settings → Edge Functions → Secrets**
2. Verify these secrets are set:
   - `SMTP_USER` = Your Zoho email (e.g., `noreply@leasap.com`)
   - `SMTP_PASS` = Your Zoho app password
   - `RECIPIENT_EMAIL` = Where emails should be sent (e.g., `founders@leasap.com`)
   - `SMTP_HOST` = `smtp.zoho.com` (optional, defaults to this)
   - `SMTP_PORT` = `587` (optional, defaults to this)

### Step 4: Check Trigger Status
Run this SQL to verify trigger is enabled:
```sql
SELECT 
  tgname AS trigger_name,
  tgrelid::regclass AS table_name,
  CASE tgenabled
    WHEN 'O' THEN '✅ Enabled'
    WHEN 'D' THEN '❌ Disabled'
    ELSE '❓ Unknown'
  END AS status
FROM pg_trigger
WHERE tgname = 'on_contact_form_insert';
```

If status is **Disabled**, re-run `migration_contact_email_trigger.sql`.

### Step 5: Test the Trigger
Run `TEST_CONTACT_FORM_TRIGGER.sql` to insert a test submission and check:
1. **Edge Function Logs**: Dashboard → Edge Functions → send-contact-email → Logs
2. **Email Inbox**: Check the RECIPIENT_EMAIL inbox
3. **Database Logs**: Dashboard → Database → Logs (for trigger errors)

---

## 🐛 Common Issues & Solutions

### Issue 1: Trigger Not Firing
**Symptoms:**
- Contact form submissions are saved to database
- No email sent
- No logs in Edge Function

**Solution:**
1. Verify trigger exists:
   ```sql
   SELECT * FROM pg_trigger WHERE tgname = 'on_contact_form_insert';
   ```
2. If missing, run `migration_contact_email_trigger.sql`
3. Check if pg_net extension is enabled:
   ```sql
   CREATE EXTENSION IF NOT EXISTS pg_net;
   ```

### Issue 2: Edge Function Not Receiving Requests
**Symptoms:**
- Trigger fires (visible in database logs)
- Edge Function logs show no requests
- HTTP errors in database logs

**Solution:**
1. Check Edge Function URL in trigger function:
   ```sql
   SELECT prosrc FROM pg_proc WHERE proname = 'notify_contact_form';
   ```
   Should contain: `https://cmpywleowxnvucymvwgv.supabase.co/functions/v1/send-contact-email`
2. Verify service_role_key is correct in trigger function
3. Check Edge Function is deployed and active

### Issue 3: SMTP Authentication Failed
**Symptoms:**
- Edge Function logs show: "Invalid login" or "Authentication failed"
- Error 535 in logs

**Solution:**
1. Verify SMTP secrets are correct:
   - `SMTP_USER` should be full email (e.g., `noreply@leasap.com`)
   - `SMTP_PASS` should be app-specific password (not regular password)
2. For Zoho Mail:
   - Enable 2FA on your Zoho account
   - Generate app-specific password
   - Use app password in `SMTP_PASS`
3. Test SMTP connection manually (see below)

### Issue 4: Email Sent But Not Received
**Symptoms:**
- Edge Function logs show "Email sent successfully"
- No email in inbox
- Check spam/junk folder

**Solution:**
1. Check spam/junk folder
2. Verify `RECIPIENT_EMAIL` secret is correct
3. Check email provider's delivery logs
4. Verify sender email is not blocked

### Issue 5: Trigger Function Error
**Symptoms:**
- Database logs show trigger errors
- WARNING messages in logs

**Solution:**
1. Check database logs for specific error:
   ```sql
   -- Check recent errors
   SELECT * FROM pg_stat_database WHERE datname = current_database();
   ```
2. Verify function syntax:
   ```sql
   SELECT pg_get_functiondef(oid) FROM pg_proc WHERE proname = 'notify_contact_form';
   ```
3. Re-run `migration_contact_email_trigger.sql` to recreate function

---

## 🧪 Testing SMTP Connection

### Test 1: Manual Edge Function Call
Call the Edge Function directly to test SMTP:

```bash
curl -X POST https://cmpywleowxnvucymvwgv.supabase.co/functions/v1/send-contact-email \
  -H "Authorization: Bearer YOUR_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "contact_id": 999,
    "name": "Test User",
    "email": "test@example.com",
    "phone": "+1234567890",
    "subject": "Test Subject",
    "message": "This is a test message",
    "submitted_at": "2024-01-15T10:30:00Z"
  }'
```

Check Edge Function logs for response.

### Test 2: Database Trigger Test
Run `TEST_CONTACT_FORM_TRIGGER.sql` and monitor:
1. Database logs for trigger execution
2. Edge Function logs for incoming request
3. Email inbox for delivery

---

## 📋 Complete Checklist

- [ ] Contact form table exists (`contactform`)
- [ ] Trigger function exists (`notify_contact_form`)
- [ ] Trigger is enabled (`on_contact_form_insert`)
- [ ] pg_net extension is enabled
- [ ] Edge Function `send-contact-email` is deployed
- [ ] SMTP secrets are configured:
  - [ ] `SMTP_USER`
  - [ ] `SMTP_PASS`
  - [ ] `RECIPIENT_EMAIL`
- [ ] Test submission triggers email
- [ ] Email arrives in inbox (check spam too)

---

## 🔧 Re-run Setup

If nothing works, re-run the complete setup:

1. **Re-create trigger:**
   ```sql
   -- Run migration_contact_email_trigger.sql
   ```

2. **Re-deploy Edge Function:**
   ```bash
   supabase functions deploy send-contact-email
   ```

3. **Verify secrets:**
   - Dashboard → Project Settings → Edge Functions → Secrets
   - Re-enter all SMTP secrets

4. **Test again:**
   - Run `TEST_CONTACT_FORM_TRIGGER.sql`
   - Check all logs

---

## 📞 Still Not Working?

If you've tried everything:
1. Check Supabase status page for service issues
2. Review Edge Function logs for detailed error messages
3. Check database logs for trigger execution errors
4. Verify your Zoho Mail account is active and not suspended
5. Test with a different email provider (Gmail, Outlook) to isolate SMTP issues

---

## 📝 Log Locations

- **Edge Function Logs**: Dashboard → Edge Functions → send-contact-email → Logs
- **Database Logs**: Dashboard → Database → Logs
- **Trigger Logs**: Check database logs for `RAISE NOTICE` messages from trigger
- **Application Logs**: Your FastAPI server logs (for API endpoint issues)
