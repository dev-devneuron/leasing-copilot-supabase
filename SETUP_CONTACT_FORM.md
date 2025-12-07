# Contact Form Setup Guide

## 📋 Overview

Complete setup guide for the contact form feature, including database, backend API, and email notifications.

---

## 🗄️ Step 1: Create Database Table

Run the migration SQL file to create the `contactform` table:

**File:** `migration_create_contact_form_table.sql`

1. Go to **Supabase Dashboard → SQL Editor**
2. Open `migration_create_contact_form_table.sql`
3. Run the entire script

This will create:
- `contactform` table with all required columns
- Indexes on `email` and `submitted_at` for performance
- Table comments for documentation

---

## 🔧 Step 2: Update Backend Code

The backend code has been updated with:

### Database Model
- **File:** `DB/db.py`
- **Model:** `ContactForm` class
- **Table:** `contactform`

### API Endpoint
- **File:** `vapi/app.py`
- **Endpoint:** `POST /contact`
- **Status:** ✅ Already added

### Restart Backend
After updating the code, restart your FastAPI server:
```bash
# If using uvicorn
uvicorn vapi.app:app --reload

# Or however you normally run your backend
```

---

## 📧 Step 3: Set Up Email Notifications

### 3.1 Deploy Edge Function

The Edge Function `send-contact-email` should already be deployed. If not:

1. Go to **Supabase Dashboard → Edge Functions**
2. Deploy `send-contact-email` function
3. Or use CLI: `supabase functions deploy send-contact-email`

### 3.2 Set SMTP Secrets

Ensure these secrets are set in Supabase:

1. Go to **Supabase Dashboard → Project Settings → Edge Functions → Secrets**
2. Verify these are set:
   - `SMTP_USER` = your Zoho email
   - `SMTP_PASS` = your Zoho app password
   - `RECIPIENT_EMAIL` = founders@leasap.com (or your email)

### 3.3 Create Email Trigger

Run the trigger migration:

**File:** `migration_contact_email_trigger.sql`

1. Go to **Supabase Dashboard → SQL Editor**
2. Open `migration_contact_email_trigger.sql`
3. Run the entire script

This will:
- Create `notify_contact_form()` function
- Create trigger `on_contact_form_insert` on `contactform` table
- Automatically send email notifications when forms are submitted

---

## 🧪 Step 4: Test the Setup

### Test API Endpoint

```bash
curl -X POST http://localhost:8000/contact \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test User",
    "email": "test@example.com",
    "message": "This is a test message",
    "phone": "+1234567890",
    "subject": "Test Subject"
  }'
```

**Expected Response:**
```json
{
  "message": "Thank you for contacting us! We've received your message and will get back to you soon.",
  "contact_id": 1,
  "submitted_at": "2024-01-15T10:30:00.000Z"
}
```

### Test Email Notification

1. Submit a contact form via API
2. Check Edge Function logs: **Dashboard → Edge Functions → send-contact-email → Logs**
3. Check your email inbox (`founders@leasap.com`)

---

## 📱 Step 5: Frontend Integration

Share `FRONTEND_CONTACT_FORM_INTEGRATION.md` with your frontend developer.

**Key Points:**
- **Endpoint:** `POST /contact`
- **Required fields:** `name`, `email`, `message`
- **Optional fields:** `phone`, `subject`
- **CORS:** Already configured for common domains

See `FRONTEND_CONTACT_FORM_INTEGRATION.md` for:
- Complete API documentation
- React/Next.js example code
- Vanilla JavaScript example
- Form validation examples
- Error handling
- Testing instructions

---

## ✅ Verification Checklist

- [ ] Database table `contactform` created
- [ ] Backend code updated and server restarted
- [ ] API endpoint `POST /contact` working
- [ ] Edge Function `send-contact-email` deployed
- [ ] SMTP secrets configured
- [ ] Email trigger created and working
- [ ] Test submission sends email notification
- [ ] Frontend developer has integration guide

---

## 🆘 Troubleshooting

### Table doesn't exist
- Run `migration_create_contact_form_table.sql` again
- Check Supabase Dashboard → Table Editor to verify table exists

### API endpoint not found
- Restart FastAPI server
- Check that `ContactForm` model is imported in `vapi/app.py`
- Verify endpoint is defined: `@app.post("/contact")`

### Email not sending
- Check Edge Function logs for errors
- Verify SMTP secrets are set correctly
- Check trigger exists: `SELECT * FROM pg_trigger WHERE tgname = 'on_contact_form_insert';`
- Verify trigger is enabled (status should be 'O')

### CORS errors
- Add frontend domain to CORS whitelist in `vapi/app.py`
- Check `origins` list in the FastAPI app

---

## 📝 Files Created/Modified

### New Files
- `migration_create_contact_form_table.sql` - Database table creation
- `migration_contact_email_trigger.sql` - Email notification trigger
- `FRONTEND_CONTACT_FORM_INTEGRATION.md` - Frontend developer guide
- `SETUP_CONTACT_FORM.md` - This file

### Modified Files
- `DB/db.py` - Added `ContactForm` model
- `vapi/app.py` - Added `POST /contact` endpoint
- `supabase/functions/send-contact-email/index.ts` - Updated to use Deno.serve

---

**Setup complete!** The contact form is ready to use. Share the frontend integration guide with your frontend developer.
