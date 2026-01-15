# Frontend Fix: Testing Mode Bypass

## ⚠️ Issue

The "Call" button is still disabled even when testing bypass is enabled.

## Root Cause

The frontend is checking `candidate.eligibility_checks?.bypassed_for_testing`, but the backend returns `bypassed_for_testing` at the **TOP LEVEL** of the candidate object, not inside `eligibility_checks`.

## ✅ Correct Response Structure

The backend returns candidates like this:

```json
{
  "candidates": [
    {
      "contact_id": 123,
      "phone_number": "+14125551234",
      "eligible": true,  // ← Forced to true when bypass enabled
      "eligibility_reason": "Outside allowed calling hours (8 AM - 9 PM); No consent on record",
      "eligibility_checks": {
        "consent": false,
        "within_time_window": false,
        // ... other checks
      },
      "bypassed_for_testing": true  // ← TOP LEVEL, not inside eligibility_checks!
    }
  ]
}
```

## ❌ Wrong Frontend Code

```javascript
// ❌ WRONG - bypassed_for_testing is NOT inside eligibility_checks
const canCall = candidate.eligible || candidate.eligibility_checks?.bypassed_for_testing;
```

## ✅ Correct Frontend Code

```javascript
// ✅ CORRECT - Check bypassed_for_testing at TOP LEVEL
const canCall = candidate.eligible || candidate.bypassed_for_testing;

// Show warning if bypassed
if (candidate.bypassed_for_testing) {
  // Show warning badge: "⚠️ Testing Mode"
}
```

## Quick Fix

In your `CandidatesTab.tsx` or wherever you check eligibility:

**Change this:**
```typescript
// ❌ WRONG - bypassed_for_testing is NOT inside eligibility_checks
const canCall = candidate.eligible || candidate.eligibility_checks?.bypassed_for_testing;

// ❌ WRONG - checking wrong location
if (candidate.eligibility_checks?.bypassed_for_testing) { ... }
```

**To this:**
```typescript
// ✅ CORRECT - Check at TOP LEVEL
const canCall = candidate.eligible || candidate.bypassed_for_testing;

// ✅ CORRECT - Check at TOP LEVEL
if (candidate.bypassed_for_testing) { ... }
```

**And update all references:**
- `candidate.eligibility_checks?.bypassed_for_testing` → `candidate.bypassed_for_testing`
- Check the TypeScript interface too - make sure `bypassed_for_testing` is at the top level of the Candidate interface, not inside `eligibility_checks`

**TypeScript Interface Fix:**
```typescript
interface Candidate {
  contact_id: number;
  phone_number: string;
  eligible: boolean;
  eligibility_reason: string;
  eligibility_checks: {
    consent: boolean;
    not_opted_out: boolean;
    // ... other checks
    // ❌ DON'T put bypassed_for_testing here
  };
  bypassed_for_testing?: boolean; // ✅ Put it HERE at top level
}
```

## Verify Backend is Working

1. Check backend logs for:
   ```
   ⚠️  WARNING: Eligibility checks bypassed for testing!
   ```

2. Test the API directly:
   ```bash
   curl -H "Authorization: Bearer YOUR_TOKEN" \
        http://localhost:8000/outbound-calls/candidates?limit=1
   ```

3. Look for `"bypassed_for_testing": true` in the response (at top level of candidate object)

## Still Not Working?

1. **Verify env var is set:**
   - Check `.env` file has `DISABLE_ELIGIBILITY_CHECKS=true`
   - **Restart backend server** (critical!)

2. **Check backend logs:**
   - Should see bypass warnings when calling candidates endpoint

3. **Verify API response:**
   - `eligible` should be `true` when bypass is enabled
   - `bypassed_for_testing` should be `true` at top level

4. **Frontend debugging:**
   - Console.log the candidate object
   - Check if `bypassed_for_testing` exists at top level
   - Verify `canCall()` function logic

---

**The fix is simple: move `bypassed_for_testing` check from `eligibility_checks` to top level of candidate object!**

---

## Additional Debugging

### When Bypass is Enabled, `eligible` Should Be `true`

When `DISABLE_ELIGIBILITY_CHECKS=true`:
- Backend **forces** `eligible = true` (line 134 in `DB/outbound_calling.py`)
- So even if frontend only checks `candidate.eligible`, it should work

**If `eligible` is still `false` in the API response:**
- Backend bypass is NOT active
- Check: Is `DISABLE_ELIGIBILITY_CHECKS=true` in `.env`?
- Check: Was backend server restarted after setting env var?
- Check: Backend logs should show: `⚠️  WARNING: Eligibility checks bypassed for testing!`

### Test Backend Directly

```bash
# Test the API endpoint
curl -X GET "http://localhost:8000/outbound-calls/candidates?limit=1" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json"
```

**Expected response when bypass enabled:**
```json
{
  "candidates": [
    {
      "eligible": true,  // ← Should be true when bypass enabled
      "bypassed_for_testing": true,  // ← At top level
      "eligibility_reason": "Outside allowed calling hours...",  // Original reason
      "eligibility_checks": { ... }
    }
  ]
}
```

**If `eligible` is `false` in response:**
- Backend bypass is NOT working
- Fix: Set env var and restart server

**If `eligible` is `true` but button still disabled:**
- Frontend is checking wrong location
- Fix: Change `candidate.eligibility_checks?.bypassed_for_testing` to `candidate.bypassed_for_testing`
