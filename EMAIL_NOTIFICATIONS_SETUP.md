# Email Notifications Setup Guide

Complete guide for setting up automatic email notifications for demo requests and contact forms using Supabase Edge Functions.

---

## 📋 Overview

When a user submits a demo request or contact form:
1. Data is saved to your Supabase database table (`demorequest`)
2. A database trigger automatically fires
3. The trigger calls a Supabase Edge Function
4. The Edge Function sends an email notification to your Zoho Mail

---

## ✅ What's Already Done

- ✅ SQL trigger created and running in database
- ✅ Edge Function code ready (`supabase/functions/send-demo-email/index.ts`)

---

## 🚀 Setup Steps

### Step 1: Set Secrets in Supabase Dashboard

1. Go to **Supabase Dashboard** → **Settings** → **Edge Functions** → **Secrets**
2. Add these secrets:

| Secret Name | Value |
|------------|-------|
| `SMTP_USER` | `founders@leasap.com` |
| `SMTP_PASS` | `RyQXG11SSktn` |
| `SMTP_HOST` | `smtp.zoho.com` |
| `SMTP_PORT` | `587` |
| `SMTP_SECURE` | `false` |
| `RECIPIENT_EMAIL` | `founders@leasap.com` |

### Step 2: Deploy Edge Function via Dashboard

1. Go to **Edge Functions** → **Deploy Edge Function via Editor**
2. Click **Create a new function**
3. Name it: `send-demo-email`
4. Copy the code from `supabase/functions/send-demo-email/index.ts`
5. Paste into the editor
6. Click **Deploy**

### Step 3: Test It

**Option A: Test via Dashboard**
- Go to **Edge Functions** → **send-demo-email** → **Invoke**
- Use this payload:
```json
{
  "name": "Test User",
  "email": "test@example.com",
  "phone": "+1234567890"
}
```

**Option B: Test via Database (Real Test)**
- Go to **SQL Editor**
- Run:
```sql
INSERT INTO demorequest (name, email, phone, company_name, notes, status)
VALUES (
  'Test User',
  'test@example.com',
  '+1234567890',
  'Test Company',
  'Testing email notification',
  'pending'
);
```
- Check `founders@leasap.com` inbox

---

## 🔧 Troubleshooting

### Trigger Not Working?

1. **Check trigger exists:**
```sql
SELECT tgname, tgenabled 
FROM pg_trigger 
WHERE tgname = 'on_demo_request_insert';
```

2. **Run diagnostic SQL:** See `DIAGNOSE_TRIGGER.sql`

3. **Update trigger function:** See `FIX_TRIGGER.sql` (has better logging)

4. **Check Edge Function logs:** Dashboard → Edge Functions → send-demo-email → Logs

### Edge Function Errors?

- Check function logs in Dashboard
- Verify all secrets are set correctly
- See `TEST_EDGE_FUNCTION.md` for testing guide

### Email Not Received?

- Check spam folder
- Verify SMTP credentials are correct
- Check Edge Function logs for SMTP errors
- See `ZOHO_MAIL_SETUP.md` for Zoho Mail configuration

---

## 📚 Reference Files

- `migration_demo_contact_email_trigger_simple.sql` - SQL migration (already run)
- `FIX_TRIGGER.sql` - Updated trigger function with better logging
- `DIAGNOSE_TRIGGER.sql` - Diagnostic SQL queries
- `TEST_EDGE_FUNCTION.md` - Testing guide
- `DEBUG_TRIGGER.md` - Detailed debugging guide
- `ZOHO_MAIL_SETUP.md` - Zoho Mail configuration details
- `DEPLOY_VIA_DASHBOARD_EDITOR.md` - Dashboard deployment guide

---

## ✅ Checklist

- [x] SQL trigger created
- [ ] Secrets set in Dashboard
- [ ] Edge Function deployed
- [ ] Test email received

---

## 🎉 Done!

Once setup is complete, every demo request will automatically send an email notification to `founders@leasap.com`!
