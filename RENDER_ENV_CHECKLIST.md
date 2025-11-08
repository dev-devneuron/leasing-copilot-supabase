# Render Environment Variables Checklist

## ✅ Currently Configured in Render

### Core Database & Supabase
- ✅ `DATABASE_1_URL` - Main PostgreSQL database
- ✅ `DATABASE_2_URL` - Secondary database (for syncing, optional)
- ✅ `SUPABASE_URL` - Supabase project URL
- ✅ `SUPABASE_SERVICE_KEY` - Service role key
- ✅ `SUPABASE_SERVICE_ROLE_KEY` - Service role key (alternative)
- ✅ `SUPABASE_JWT_SECRET` - JWT secret for authentication

### AI/ML Configuration
- ✅ `GEMINI_API_KEY` - Gemini API key (fallback mode)

### Voice & Communication
- ✅ `VAPI_API_KEY` - Primary VAPI key
- ✅ `VAPI_API_KEY2` - Secondary VAPI key (optional)
- ✅ `VAPI_ASSISTANT_ID` - Primary assistant ID
- ✅ `VAPI_ASSISTANT_ID2` - Secondary assistant ID (optional)
- ✅ `TWILIO_ACCOUNT_SID` - Primary Twilio account
- ✅ `TWILIO_ACCOUNT_SID2` - Secondary Twilio account (optional)
- ✅ `TWILIO_AUTH_TOKEN` - Primary Twilio token
- ✅ `TWILIO_AUTH_TOKEN2` - Secondary Twilio token (optional)

### Google Services
- ✅ `GOOGLE_API_KEY` - Google API key (may be for Calendar API, but OAuth is preferred)

---

## ⚠️ Optional but Recommended (Vertex AI)

If you want to use **Vertex AI** for better ML performance, add these:

```
USE_VERTEX_AI=true
GCP_PROJECT_ID=your-gcp-project-id
GCP_LOCATION=us-central1
VERTEX_AI_MODEL=gemini-2.0-flash-exp
VERTEX_AI_EMBEDDING_MODEL=textembedding-gecko@003
```

**Note:** If you don't add these, the system will automatically use Gemini API (which you already have configured).

---

## 📝 Optional Configuration

These have defaults but can be customized:

```
# AI Model Settings (optional)
EMBEDDING_MODEL_NAME=BAAI/bge-large-en-v1.5
LLM_MODEL_NAME=models/gemini-2.0-flash
CHUNK_SIZE=800
CHUNK_OVERLAP=50

# Application Settings (optional)
REDIRECT_URI=https://leasing-copilot-mvp.onrender.com/oauth2callback
DAILY_LIMIT=50
DEFAULT_TIMEZONE=Asia/Karachi
```

---

## 🔍 Notes

1. **GOOGLE_API_KEY**: This appears to be set, but the codebase uses OAuth flow for Google Calendar. The API key might not be actively used. You can keep it for other Google services if needed.

2. **DATABASE_2_URL**: This is used for the secondary database sync feature. It's optional - the app will work without it, but sync features won't work.

3. **Vertex AI**: Currently using Gemini API fallback mode. To enable Vertex AI:
   - Add the Vertex AI variables above
   - Set up GCP authentication (service account or gcloud auth)
   - See `VERTEX_AI_SETUP.md` for details

4. **All Required Variables Present**: ✅ You have all the essential variables needed for the app to run!

---

## 🚀 Current Status

**Status:** ✅ **READY TO RUN**

Your configuration is complete for basic operation. The system will:
- Use Gemini API for AI parsing (since Vertex AI vars aren't set)
- Connect to Supabase for database and storage
- Use VAPI for voice assistant
- Use Twilio for WhatsApp integration

To upgrade to Vertex AI later, just add those 5 variables!

