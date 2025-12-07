# Zoho Mail Setup Guide

This guide will help you configure email notifications to use your Zoho Mail account.

## 📋 Prerequisites

- Zoho Mail account (https://mail.zoho.com/)
- Supabase CLI installed and logged in
- Your Supabase project linked

---

## 🔑 Step 1: Generate Zoho Mail App Password

Zoho Mail requires an app-specific password for SMTP authentication. Here's how to get it:

### For Zoho Mail (Personal/Free Accounts):

1. **Log in to Zoho Mail**
   - Go to https://mail.zoho.com/
   - Sign in with your Zoho account

2. **Access Security Settings**
   - Click on your profile icon (top right)
   - Go to **Settings** → **Security**
   - Or directly visit: https://accounts.zoho.com/home#security/apppasswords

3. **Generate App Password**
   - Scroll down to **App Passwords** section
   - Click **Generate New Password**
   - Give it a name (e.g., "Supabase Email Notifications")
   - Click **Generate**
   - **IMPORTANT**: Copy the password immediately - you won't be able to see it again!

### For Zoho Mail (Business/Organization Accounts):

1. **Log in to Zoho Mail Admin Console**
   - Go to https://mailadmin.zoho.com/
   - Sign in with admin credentials

2. **Enable App Passwords**
   - Go to **Security** → **App Passwords**
   - Enable app passwords for your organization (if not already enabled)

3. **Generate App Password for Your Account**
   - Go to https://accounts.zoho.com/home#security/apppasswords
   - Follow the same steps as personal accounts above

---

## ⚙️ Step 2: Set Supabase Secrets

Now set your Zoho Mail credentials as Supabase secrets:

```bash
# Make sure you're in your project directory
cd "e:\Leasap Backend"

# Login to Supabase (if not already logged in)
supabase login

# Link your project (if not already linked)
supabase link --project-ref cmpywleowxnvucymvwgv

# Set Zoho Mail credentials
supabase secrets set SMTP_USER=your-email@zoho.com
supabase secrets set SMTP_PASS=your-app-password-from-step-1

# Set Zoho Mail SMTP settings (optional - these are defaults)
supabase secrets set SMTP_HOST=smtp.zoho.com
supabase secrets set SMTP_PORT=587
supabase secrets set SMTP_SECURE=false

# Optional: Set recipient email (defaults to SMTP_USER)
supabase secrets set RECIPIENT_EMAIL=notifications@yourdomain.com
```

**Replace:**
- `your-email@zoho.com` - Your Zoho Mail email address
- `your-app-password-from-step-1` - The app password you generated

---

## 🚀 Step 3: Deploy Edge Functions

Deploy the updated Edge Functions:

```bash
# Deploy demo email function
supabase functions deploy send-demo-email

# Deploy contact email function (if you use contact forms)
supabase functions deploy send-contact-email
```

---

## ✅ Step 4: Test the Setup

1. **Submit a test demo request** through your form or API:
   ```bash
   curl -X POST https://your-api-url.com/book-demo \
     -H "Content-Type: application/json" \
     -d '{
       "name": "Test User",
       "email": "test@example.com",
       "phone": "+1234567890",
       "notes": "Testing Zoho Mail integration"
     }'
   ```

2. **Check your Zoho Mail inbox** - you should receive the notification email

3. **Check Edge Function logs** in Supabase Dashboard:
   - Go to **Edge Functions** → **send-demo-email** → **Logs**
   - Look for any errors or success messages

---

## 🔧 Zoho Mail SMTP Settings Reference

| Setting | Value |
|---------|-------|
| **SMTP Host** | `smtp.zoho.com` |
| **SMTP Port** | `587` (TLS) or `465` (SSL) |
| **Security** | TLS (port 587) or SSL (port 465) |
| **Authentication** | Required (use app password) |
| **Username** | Your full Zoho Mail email address |
| **Password** | App-specific password (not your regular password) |

---

## 🆘 Troubleshooting

### Issue: "Authentication failed" error

**Solution:**
- Make sure you're using an **app password**, not your regular Zoho Mail password
- Verify the email address is correct (full email, e.g., `user@zoho.com`)
- Check that app passwords are enabled in your Zoho account

### Issue: "Connection timeout" or "Connection refused"

**Solution:**
- Verify SMTP settings:
  - Host: `smtp.zoho.com`
  - Port: `587` (or `465` for SSL)
  - Secure: `false` for port 587, `true` for port 465
- Check if your network/firewall blocks SMTP ports
- Try using port 465 with SSL instead:
  ```bash
  supabase secrets set SMTP_PORT=465
  supabase secrets set SMTP_SECURE=true
  ```

### Issue: Emails going to spam

**Solution:**
- Add the sender email to your contacts
- Check spam folder
- Verify the "From" address matches your Zoho Mail account
- Consider setting up SPF/DKIM records for your domain (if using custom domain)

### Issue: No emails received

**Solution:**
1. Check Edge Function logs in Supabase Dashboard
2. Verify secrets are set correctly:
   ```bash
   supabase secrets list
   ```
3. Test SMTP connection manually (see below)
4. Verify the trigger is firing:
   ```sql
   -- Run in Supabase SQL Editor
   SELECT * FROM pg_trigger WHERE tgname = 'on_demo_request_insert';
   ```

---

## 🧪 Testing SMTP Connection

You can test your Zoho Mail SMTP settings using a simple Node.js script:

```javascript
const nodemailer = require('nodemailer');

const transporter = nodemailer.createTransport({
  host: 'smtp.zoho.com',
  port: 587,
  secure: false,
  auth: {
    user: 'your-email@zoho.com',
    pass: 'your-app-password'
  },
  tls: {
    ciphers: 'SSLv3'
  }
});

transporter.verify(function (error, success) {
  if (error) {
    console.log('❌ SMTP Error:', error);
  } else {
    console.log('✅ SMTP Server is ready to send emails');
  }
});
```

---

## 📝 Quick Reference Commands

```bash
# View all secrets
supabase secrets list

# Update SMTP user
supabase secrets set SMTP_USER=new-email@zoho.com

# Update SMTP password
supabase secrets set SMTP_PASS=new-app-password

# Redeploy function after secret changes
supabase functions deploy send-demo-email

# View function logs
supabase functions logs send-demo-email
```

---

## ✅ Checklist

- [ ] Zoho Mail app password generated
- [ ] SMTP secrets set in Supabase
- [ ] Edge Functions deployed
- [ ] Test email received successfully
- [ ] Checked spam folder (if email not in inbox)

---

## 🎉 You're Done!

Your email notifications are now configured to use Zoho Mail. Every new demo request will automatically send an email notification to your Zoho Mail inbox!
