# Gemini API Key Setup Guide

This guide explains how to add your Gemini API key to the backend environment for both local development and production deployment.

---

## 🔑 Your Gemini API Key

```
AIzaSyC5SU8EF-3Tld5xuR_XnMFTJrqNKGLRjYw
```

---

## 📋 Configuration Options

The backend supports two AI configurations:

1. **Vertex AI** (Recommended for production) - Requires GCP setup
2. **Gemini API** (Simpler, direct API) - Just needs an API key

Since you have a Gemini API key, we'll configure it to use the **Gemini API directly** (simpler setup).

**💰 Cost Optimization:** The backend is configured to automatically use `gemini-1.5-flash` (the cheapest Gemini model) which is perfect for transcript extraction tasks. This keeps costs low while maintaining excellent accuracy for extracting emails, property addresses, and inquiry purposes.

---

## 🏠 Local Development Setup

### Step 1: Create/Update `.env` file

In your project root (`e:\Leasap Backend\`), create or update the `.env` file:

```bash
# If .env doesn't exist, copy from example
cp env.example .env
```

### Step 2: Add Gemini API Key

Open `.env` and add/update these lines:

```env
# Disable Vertex AI (use Gemini API instead)
USE_VERTEX_AI=false

# Add your Gemini API key
GEMINI_API_KEY=AIzaSyC5SU8EF-3Tld5xuR_XnMFTJrqNKGLRjYw
```

**Important:** Make sure `USE_VERTEX_AI=false` so it uses Gemini API instead of trying Vertex AI.

### Step 3: Verify Configuration

The backend will automatically:
- Use Gemini API when `USE_VERTEX_AI=false` and `GEMINI_API_KEY` is set
- Fall back to Vertex AI if `USE_VERTEX_AI=true` and GCP is configured
- Show an error if neither is configured

---

## 🚀 Production Deployment (Render.com)

### Method 1: Using Render Dashboard (Recommended)

1. **Go to Render Dashboard**
   - Navigate to: https://dashboard.render.com
   - Select your service (likely `leasing-copilot-mvp`)

2. **Open Environment Variables**
   - Click on your service
   - Go to **"Environment"** tab in the left sidebar
   - Click **"Add Environment Variable"**

3. **Add the Variables**
   
   Add these two environment variables:
   
   **Variable 1:**
   - **Key:** `USE_VERTEX_AI`
   - **Value:** `false`
   - **Description:** Use Gemini API instead of Vertex AI
   
   **Variable 2:**
   - **Key:** `GEMINI_API_KEY`
   - **Value:** `AIzaSyC5SU8EF-3Tld5xuR_XnMFTJrqNKGLRjYw`
   - **Description:** Gemini API key for AI transcript extraction

4. **Save and Redeploy**
   - Click **"Save Changes"**
   - Render will automatically redeploy your service
   - Wait for deployment to complete

### Method 2: Using Render CLI

If you have Render CLI installed:

```bash
# Set environment variables
render env:set USE_VERTEX_AI=false
render env:set GEMINI_API_KEY=AIzaSyC5SU8EF-3Tld5xuR_XnMFTJrqNKGLRjYw

# Trigger redeploy
render deploy
```

### Method 3: Using render.yaml (If you use Infrastructure as Code)

If you have a `render.yaml` file, add:

```yaml
services:
  - type: web
    name: leasing-copilot-mvp
    envVars:
      - key: USE_VERTEX_AI
        value: false
      - key: GEMINI_API_KEY
        value: AIzaSyC5SU8EF-3Tld5xuR_XnMFTJrqNKGLRjYw
```

---

## ✅ Verification

### Check if it's working:

1. **After deployment, check logs:**
   - In Render dashboard, go to **"Logs"** tab
   - Look for: `✅ Using Gemini API: models/gemini-1.5-flash`
   - Or: `💡 Using cheapest Gemini model for cost efficiency: models/gemini-1.5-flash`

2. **Test the extraction:**
   - Make a call or trigger an outbound call
   - Check if email/property extraction works
   - Check server logs for any AI-related errors

### Expected Log Messages:

**Success:**
```
✅ Using Gemini API: models/gemini-1.5-flash
💡 Using cheapest Gemini model for cost efficiency: models/gemini-1.5-flash
```

**Error (if key is wrong):**
```
⚠️  Gemini API initialization failed: [error message]
```

---

## 🔧 Configuration Details

### How the Backend Chooses AI Provider

The backend checks in this order:

1. **If `USE_VERTEX_AI=true` AND GCP is configured:**
   - Uses Vertex AI (Google Cloud)
   - Requires: `GCP_PROJECT_ID`, `GCP_LOCATION`

2. **If `USE_VERTEX_AI=false` OR Vertex AI not available:**
   - Uses Gemini API directly
   - Requires: `GEMINI_API_KEY`

3. **If neither is configured:**
   - Shows warning: `⚠️  No AI model available`
   - Transcript extraction will return null values

### Current Configuration (Recommended)

For your setup, use:

```env
USE_VERTEX_AI=false
GEMINI_API_KEY=AIzaSyC5SU8EF-3Tld5xuR_XnMFTJrqNKGLRjYw
```

This will:
- ✅ Use Gemini API directly (no GCP setup needed)
- ✅ Use **cheapest model** (`gemini-1.5-flash`) for cost efficiency
- ✅ Enable email extraction from transcripts
- ✅ Enable property/purpose extraction
- ✅ Work immediately after adding the key

**Note:** The backend automatically uses `gemini-1.5-flash` (the cheapest Gemini model) which is perfect for simple extraction tasks like email, property, and purpose extraction from transcripts. This keeps costs low while maintaining excellent accuracy.

---

## 🛡️ Security Notes

### ⚠️ Important Security Practices:

1. **Never commit `.env` file to git**
   - The `.env` file should be in `.gitignore`
   - Only commit `env.example` (without real keys)

2. **Keep API key secret**
   - Don't share the key in public repositories
   - Don't paste it in chat logs or screenshots
   - Rotate the key if it's ever exposed

3. **Use environment variables in production**
   - Never hardcode API keys in code
   - Always use environment variables
   - Render.com securely stores environment variables

---

## 📝 Quick Reference

### Environment Variables to Set:

| Variable | Value | Purpose |
|----------|-------|---------|
| `USE_VERTEX_AI` | `false` | Use Gemini API instead of Vertex AI |
| `GEMINI_API_KEY` | `AIzaSyC5SU8EF-3Tld5xuR_XnMFTJrqNKGLRjYw` | Your Gemini API key |

### Where to Add:

- **Local:** `.env` file in project root
- **Render.com:** Environment tab in service settings
- **Other platforms:** Follow their environment variable documentation

---

## 🐛 Troubleshooting

### Issue: "No AI model available"

**Solution:**
- Check that `GEMINI_API_KEY` is set correctly
- Check that `USE_VERTEX_AI=false` (or not set)
- Verify the key is valid (check Google AI Studio)

### Issue: "Gemini API initialization failed"

**Possible causes:**
- Invalid API key
- API key doesn't have proper permissions
- Network issues

**Solution:**
- Verify the key at: https://makersuite.google.com/app/apikey
- Check if the key is enabled for Gemini API
- Try regenerating the key if needed

### Issue: Extraction not working

**Check:**
1. Server logs for AI initialization messages
2. That the key is actually set (check Render environment variables)
3. That the service was redeployed after adding the key

---

## 🚀 After Setup

Once the key is added and deployed:

1. **The backend will automatically:**
   - Extract emails from call transcripts
   - Extract property addresses and inquiry purposes
   - Infer names from email addresses
   - Send re-engagement context to Vapi

2. **No code changes needed** - it's all configured via environment variables!

3. **Test it:**
   - Make a test call
   - Check if email/property extraction works
   - Verify candidates show extracted data

---

## 📞 Support

If you encounter issues:
1. Check Render deployment logs
2. Verify environment variables are set correctly
3. Test the API key directly with a simple request
4. Check that the service was redeployed after adding variables

The backend is ready - just add the environment variables and redeploy!
