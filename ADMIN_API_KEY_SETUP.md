# Admin API Key Authentication Setup

## ✅ Implementation Complete

Admin endpoints now support **dual authentication**:
1. **ADMIN_API_KEY** - For programmatic/automated access
2. **Property Manager JWT** - For UI access (existing method)

---

## 🔐 How It Works

### Authentication Methods

The `get_admin_auth()` function accepts either:

1. **Admin API Key** (Recommended for automation):
   ```bash
   Authorization: Bearer <ADMIN_API_KEY>
   ```

2. **Property Manager JWT Token** (For UI access):
   ```bash
   Authorization: Bearer <JWT_TOKEN>
   ```

---

## 📋 Setup Instructions

### Step 1: Generate Admin API Key

Generate a secure random string (at least 32 characters):

```bash
# Option 1: Using OpenSSL
openssl rand -hex 32

# Option 2: Using Python
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Option 3: Using Node.js
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
```

### Step 2: Add to Environment Variables

Add the key to your deployment environment:

**Render.com:**
1. Go to your service settings
2. Navigate to "Environment" tab
3. Add new variable:
   - Key: `ADMIN_API_KEY`
   - Value: `<your-generated-key>`

**Local Development (.env file):**
```env
ADMIN_API_KEY=your-generated-key-here
```

### Step 3: Restart Service

Restart your backend service to load the new environment variable.

---

## 🚀 Usage Examples

### Using Admin API Key

```bash
# Dry run (safe - just counts)
curl -X POST "https://your-backend.com/admin/cleanup-bad-names?dry_run=true" \
  -H "Authorization: Bearer YOUR_ADMIN_API_KEY"

# Actual cleanup
curl -X POST "https://your-backend.com/admin/cleanup-bad-names?dry_run=false" \
  -H "Authorization: Bearer YOUR_ADMIN_API_KEY"

# Cleanup short calls
curl -X POST "https://your-backend.com/admin/cleanup-short-calls?dry_run=false&min_duration_seconds=90" \
  -H "Authorization: Bearer YOUR_ADMIN_API_KEY"
```

### Using Property Manager JWT (UI)

```bash
# Same endpoints work with JWT token from logged-in property manager
curl -X POST "https://your-backend.com/admin/cleanup-bad-names?dry_run=true" \
  -H "Authorization: Bearer <JWT_TOKEN_FROM_UI>"
```

---

## 📋 Protected Endpoints

The following endpoints now use `get_admin_auth()`:

1. **`POST /admin/cleanup-bad-names`**
   - Clean up bad contact names (verbs, filler words)
   - Parameters: `dry_run` (bool)

2. **`POST /admin/cleanup-short-calls`**
   - Clean up short call records
   - Parameters: `dry_run` (bool), `min_duration_seconds` (int)

3. **`POST /admin/import-vapi-calls`**
   - Import historical calls from Vapi API
   - Parameters: `limit` (int), `offset` (int)

---

## 🔒 Security Best Practices

1. **Keep API Key Secret:**
   - Never commit `ADMIN_API_KEY` to version control
   - Use environment variables only
   - Rotate keys periodically

2. **Use Different Keys for Different Environments:**
   - Production: `ADMIN_API_KEY_PROD`
   - Staging: `ADMIN_API_KEY_STAGING`
   - Development: `ADMIN_API_KEY_DEV`

3. **Monitor API Key Usage:**
   - Log all admin endpoint access
   - Set up alerts for suspicious activity
   - Review access logs regularly

4. **Limit Access:**
   - Only share API key with trusted team members
   - Revoke keys immediately if compromised
   - Use JWT tokens for UI access when possible

---

## 🧪 Testing

### Test Admin API Key Authentication

```bash
# Test with valid API key
curl -X POST "https://your-backend.com/admin/cleanup-bad-names?dry_run=true" \
  -H "Authorization: Bearer YOUR_ADMIN_API_KEY"
# Expected: 200 OK with cleanup results

# Test with invalid API key
curl -X POST "https://your-backend.com/admin/cleanup-bad-names?dry_run=true" \
  -H "Authorization: Bearer invalid-key"
# Expected: 401 Unauthorized

# Test without authentication
curl -X POST "https://your-backend.com/admin/cleanup-bad-names?dry_run=true"
# Expected: 401 Unauthorized
```

---

## 📊 Response Format

Both authentication methods return the same response format:

**Success Response:**
```json
{
  "message": "Cleanup completed",
  "result": {
    "fixed": 150,
    "dry_run": false
  }
}
```

**Error Response (Invalid Auth):**
```json
{
  "detail": "Invalid authentication. Use ADMIN_API_KEY or valid property manager JWT token."
}
```

---

## 🔍 Troubleshooting

### Issue: "Invalid authentication" error

**Check:**
1. Is `ADMIN_API_KEY` set in environment variables?
2. Is the API key correct in your request header?
3. Did you restart the service after adding the key?

**Solution:**
```bash
# Verify key is set (in your deployment logs)
echo $ADMIN_API_KEY

# Test with curl
curl -X POST "https://your-backend.com/admin/cleanup-bad-names?dry_run=true" \
  -H "Authorization: Bearer YOUR_ADMIN_API_KEY" \
  -v  # Verbose output to see headers
```

### Issue: JWT authentication not working

**Check:**
1. Is the JWT token valid and not expired?
2. Is the user a property manager (not a realtor)?
3. Is `SUPABASE_JWT_SECRET` configured correctly?

---

## 🚀 Next Steps

1. **Generate and set `ADMIN_API_KEY`** in your environment
2. **Test authentication** with a dry run
3. **Document key** in your team's secure password manager
4. **Set up monitoring** for admin endpoint access

---

**Admin API key authentication is now ready!** 🔐
