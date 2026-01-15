# Quick Testing Setup - Disable Eligibility Checks

## ⚠️ For Testing Only - Must Disable Before Production!

---

## Step 1: Enable Backend Bypass

### Option A: Add to `.env` file

1. Open your `.env` file (or create it from `env.example`)
2. Add this line:
   ```bash
   DISABLE_ELIGIBILITY_CHECKS=true
   ```
3. **Save the file**
4. **Restart your backend server** (this is critical - the env var is only read at startup)

### Option B: Set as environment variable (temporary)

If running directly:
```bash
# Windows PowerShell
$env:DISABLE_ELIGIBILITY_CHECKS="true"

# Windows CMD
set DISABLE_ELIGIBILITY_CHECKS=true

# Linux/Mac
export DISABLE_ELIGIBILITY_CHECKS=true
```

Then restart your server.

---

## Step 2: Verify Backend is Bypassing

After restarting, check your backend console logs. You should see:
```
⚠️  WARNING: Eligibility checks bypassed for testing! This should NOT be enabled in production!
```

If you don't see this, the bypass is NOT active. Check:
- ✅ `.env` file has `DISABLE_ELIGIBILITY_CHECKS=true`
- ✅ Server was restarted after adding the variable
- ✅ No typos in the variable name

---

## Step 3: Frontend Changes (If Frontend is Blocking)

If your frontend is still disabling the "Call" button, you need to update the frontend code to check for the bypass flag.

### Update Frontend Logic

**Before (blocking):**
```javascript
// ❌ This blocks calls when eligible=false
const canCall = candidate.eligible;
```

**After (allow with bypass):**
```javascript
// ✅ Allow call if eligible OR if bypassed for testing
const canCall = candidate.eligible || candidate.bypassed_for_testing;

// Show warning if bypassed
if (candidate.bypassed_for_testing) {
  // Show warning badge: "⚠️ Testing Mode"
  // Still enable the "Call" button
}
```

### Where to Update

Look for where you're checking `eligible` to enable/disable the "Call" button:
- Candidates table row actions
- Manual call trigger form
- Batch process button

Update all places to also check `bypassed_for_testing`.

---

## Step 4: Test

1. Try calling a contact that would normally be blocked (no consent, outside hours, etc.)
2. The call should proceed
3. Check backend logs - you should see bypass warnings
4. Frontend should show a warning badge if `bypassed_for_testing=true`

---

## Step 5: Disable Before Production

**Before deploying to production:**

1. **Backend**: Remove or set to `false` in `.env`:
   ```bash
   DISABLE_ELIGIBILITY_CHECKS=false
   ```
   Or simply remove the line.

2. **Restart backend server**

3. **Frontend**: Remove the bypass logic (or keep it but it won't trigger since backend won't send the flag)

4. **Test**: Verify eligibility checks block calls correctly

---

## Troubleshooting

### "I set the env var but still can't call"

1. **Did you restart the server?** (Most common issue)
   - The env var is read at startup, not dynamically
   - Stop and restart your backend server

2. **Check the variable name:**
   - Must be exactly: `DISABLE_ELIGIBILITY_CHECKS`
   - Value must be exactly: `true` (case-insensitive)

3. **Check backend logs:**
   - Look for: `⚠️  WARNING: Eligibility checks bypassed for testing!`
   - If you don't see this, bypass is NOT active

4. **Frontend might be blocking:**
   - Check browser console for errors
   - Check if frontend code checks `eligible` and disables button
   - Update frontend to also check `bypassed_for_testing`

### "Backend allows it but frontend button is disabled"

This means the frontend is checking `eligible` and disabling the button. You need to update the frontend code to also check `bypassed_for_testing`:

```javascript
// In your component
const isCallEnabled = (candidate) => {
  return candidate.eligible || candidate.bypassed_for_testing;
};

// In your render
<button 
  disabled={!isCallEnabled(candidate)}
  onClick={() => triggerCall(candidate)}
>
  {candidate.bypassed_for_testing && (
    <span className="warning-badge">⚠️ Testing Mode</span>
  )}
  Call Now
</button>
```

---

## Quick Reference

**Backend env var:**
```bash
DISABLE_ELIGIBILITY_CHECKS=true
```

**Frontend check:**
```javascript
candidate.eligible || candidate.bypassed_for_testing
```

**API response includes:**
- `eligible: true` (forced to true when bypass enabled)
- `bypassed_for_testing: true` (flag indicating bypass is active)
- `eligibility_reason: "..."` (original reason that would have blocked)

---

**Status:** Temporary testing feature
**Must disable before:** Production deployment
