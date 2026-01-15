# Debugging: Testing Bypass Not Working

## Quick Checklist

### 1. Verify Backend Bypass is Enabled

**Test endpoint (new):**
```bash
GET /outbound-calls/test-bypass-status
```

**Expected response when enabled:**
```json
{
  "bypass_enabled": true,
  "message": "Testing bypass is ENABLED",
  "warning": "⚠️ This should be DISABLED before production!"
}
```

**If `bypass_enabled` is `false`:**
- Backend bypass is NOT active
- Check `.env` file has `DISABLE_ELIGIBILITY_CHECKS=true`
- **Restart backend server** (critical - env vars load at startup)

### 2. Check Backend Logs

When you call `/outbound-calls/candidates`, you should see:
```
⚠️  WARNING: Eligibility checks bypassed for testing! This should NOT be enabled in production!
   Would have been blocked by: Outside allowed calling hours (8 AM - 9 PM); No consent on record
```

**If you don't see this:**
- Backend bypass is NOT active
- Fix: Set env var and restart server

### 3. Test API Response Directly

```bash
curl -X GET "http://localhost:8000/outbound-calls/candidates?limit=1" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json"
```

**Check the response:**
- `eligible` should be `true` (forced by backend when bypass enabled)
- `bypassed_for_testing` should be `true` at **top level** (not inside `eligibility_checks`)

**Example correct response:**
```json
{
  "candidates": [
    {
      "contact_id": 123,
      "phone_number": "+14125551234",
      "eligible": true,  // ← Should be true
      "bypassed_for_testing": true,  // ← At top level
      "eligibility_reason": "Outside allowed calling hours...",
      "eligibility_checks": {
        "consent": false,
        "within_time_window": false,
        // ...
      }
    }
  ]
}
```

### 4. Frontend Debugging

**In browser console:**
```javascript
// Check what the API is returning
console.log('Candidates:', candidates);

// Check a specific candidate
const candidate = candidates[0];
console.log('Eligible:', candidate.eligible);
console.log('Bypassed:', candidate.bypassed_for_testing);
console.log('Can call:', candidate.eligible || candidate.bypassed_for_testing);
```

**What to look for:**
- `candidate.eligible` should be `true` when bypass enabled
- `candidate.bypassed_for_testing` should exist at top level (not undefined)
- `canCall` should be `true`

### 5. Common Issues

#### Issue: `eligible` is still `false` in API response
**Cause:** Backend bypass not active
**Fix:**
1. Check `.env` has `DISABLE_ELIGIBILITY_CHECKS=true`
2. Restart backend server
3. Test `/outbound-calls/test-bypass-status` endpoint

#### Issue: `eligible` is `true` but button still disabled
**Cause:** Frontend logic issue
**Fix:**
- Check `canCall()` function
- Verify it checks `candidate.eligible || candidate.bypassed_for_testing`
- Check TypeScript interface has `bypassed_for_testing` at top level

#### Issue: `bypassed_for_testing` is `undefined`
**Cause:** Backend not returning it or frontend checking wrong location
**Fix:**
- Verify backend code includes it in response (line 12700 in `vapi/app.py`)
- Check frontend is checking top level, not `eligibility_checks.bypassed_for_testing`

---

## Step-by-Step Verification

1. **Check env var:**
   ```bash
   # In your .env file
   DISABLE_ELIGIBILITY_CHECKS=true
   ```

2. **Restart backend server**

3. **Test bypass status:**
   ```bash
   GET /outbound-calls/test-bypass-status
   ```
   Should return `"bypass_enabled": true`

4. **Test candidates endpoint:**
   ```bash
   GET /outbound-calls/candidates?limit=1
   ```
   Should return `"eligible": true` and `"bypassed_for_testing": true`

5. **Check frontend:**
   - Open browser console
   - Check candidate object structure
   - Verify `canCall()` logic

---

## Still Not Working?

If after all these checks it's still not working, the issue is likely:
1. Backend server wasn't restarted after setting env var
2. Frontend is caching old API responses
3. There's another frontend check blocking the button

**Quick test:** Try calling the API directly from browser console or Postman to verify backend is working.
