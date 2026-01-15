# Testing Bypass for Outbound Calling - TEMPORARY

## ⚠️ IMPORTANT: This is for TESTING ONLY

The eligibility checks have been temporarily bypassed to allow testing. **This MUST be disabled before production deployment!**

---

## How to Enable Testing Bypass

Add this to your `.env` file:

```bash
DISABLE_ELIGIBILITY_CHECKS=true
```

Then restart your backend server.

---

## What This Does

When enabled, the system will:
- ✅ Allow calls even if consent is missing
- ✅ Allow calls even if contact opted out
- ✅ Allow calls outside time windows (8 AM - 9 PM)
- ✅ Allow calls even if cooldown hasn't passed
- ✅ Allow calls even if attempt limit exceeded
- ✅ Allow calls even if retry is blocked by last_call_outcome

**The checks still run and are logged**, but they don't block calls.

---

## What You'll See

When bypass is enabled:
- Console warnings: `⚠️  WARNING: Eligibility checks bypassed for testing!`
- API responses include `"bypassed_for_testing": true` in eligibility results
- Calls proceed even when eligibility checks fail

---

## How to Disable (Before Production)

1. Remove or set to `false` in `.env`:
   ```bash
   DISABLE_ELIGIBILITY_CHECKS=false
   ```
   OR simply remove the line entirely.

2. Restart your backend server.

3. Verify eligibility checks are working:
   - Try calling a contact without consent → should be blocked
   - Try calling outside time window → should be blocked
   - Try calling opted-out contact → should be blocked

---

## Code Locations

The bypass is implemented in:
- `DB/outbound_calling.py` - `check_eligibility()` function
- `vapi/app.py` - `/outbound-calls/trigger` endpoint
- `DB/outbound_calling.py` - `process_outbound_call_queue()` function

---

## Production Checklist

Before deploying to production:
- [ ] Verify `DISABLE_ELIGIBILITY_CHECKS` is NOT set or set to `false`
- [ ] Test that eligibility checks block calls correctly
- [ ] Verify console shows no bypass warnings
- [ ] Review all outbound calling logs for compliance

---

**Status:** Temporary testing feature
**Must be disabled before:** Production deployment
**Date created:** 2024-01-XX
