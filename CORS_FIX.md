# CORS Fix for Outbound Calls Endpoint

## Issue
Frontend at `https://www.leasap.com` is getting CORS errors when calling `/outbound-calls/trigger`:
```
Access to fetch at 'https://leasing-copilot-mvp.onrender.com/outbound-calls/trigger' 
from origin 'https://www.leasap.com' has been blocked by CORS policy: 
No 'Access-Control-Allow-Origin' header is present on the requested resource.
```

## Root Cause
The CORS configuration is correct (`https://www.leasap.com` is in allowed origins), but:
1. **Server needs restart** - CORS middleware changes require server restart
2. **Error responses** - If the request fails (401, 403, 500) before CORS middleware processes it, headers might not be added

## Fixes Applied

### 1. Fixed Typo in Origins List
- Changed `https://leaseap.com` → `https://leasap.com` (was missing 's')

### 2. Added Explicit OPTIONS Handler
- Added `@app.options("/outbound-calls/trigger")` endpoint to handle preflight requests explicitly
- This ensures CORS headers are always sent for OPTIONS requests

### 3. Verified CORS Middleware Configuration
- CORS middleware is properly configured with:
  - `allow_origins`: Includes `https://www.leasap.com`
  - `allow_credentials`: `True`
  - `allow_methods`: Includes `POST`, `OPTIONS`
  - `allow_headers`: `["*"]`

## Required Actions

### 1. Restart Backend Server
**CRITICAL**: The server must be restarted for CORS changes to take effect.

```bash
# If using Render.com, redeploy or restart the service
# If running locally:
# Stop the server (Ctrl+C) and restart:
uvicorn vapi.app:app --reload --host 0.0.0.0 --port 8000
```

### 2. Verify CORS Headers
After restart, test with:
```bash
curl -X OPTIONS https://leasing-copilot-mvp.onrender.com/outbound-calls/trigger \
  -H "Origin: https://www.leasap.com" \
  -H "Access-Control-Request-Method: POST" \
  -v
```

Expected response headers:
```
Access-Control-Allow-Origin: https://www.leasap.com
Access-Control-Allow-Methods: POST, OPTIONS
Access-Control-Allow-Headers: *
Access-Control-Allow-Credentials: true
```

### 3. Test from Frontend
After server restart, the frontend should be able to make requests without CORS errors.

## Debugging

If CORS errors persist after restart:

1. **Check server logs** - Look for any errors that might prevent CORS middleware from running
2. **Verify origin** - Ensure frontend is making requests from exactly `https://www.leasap.com` (not `http://` or different subdomain)
3. **Check authentication** - If auth fails (401/403), CORS headers should still be included, but verify in network tab
4. **Test with curl** - Use the curl command above to verify CORS headers are being sent

## Additional Notes

- The CORS middleware should automatically handle all endpoints
- Explicit OPTIONS handlers are optional but can help with debugging
- If you add more outbound-calls endpoints, they should automatically work with the existing CORS configuration
