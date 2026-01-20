# Fixes for "Looking" Name and False Opt-Out Issues

## ✅ Issues Fixed

### 1. **"Looking" Name Still Appearing**
**Problem:** Contact names like "Looking", "Following", "Providing" were still appearing in the frontend despite sanitization.

**Root Cause:** The candidate endpoint was returning raw `inferred_name` and `stored_name` without final sanitization before sending to frontend.

**Fix Applied:**
- Added centralized name sanitization in `/outbound-calls/candidates` endpoint
- Uses `_is_bad_person_name()` helper to filter bad names before returning to frontend
- Both `inferred_name` and `stored_name` are now sanitized
- `display_name` (the main "name" field) is built from sanitized values only

**Code Location:** `vapi/app.py` - `/outbound-calls/candidates` endpoint (around line 13120)

---

### 2. **False Opt-Out Detection**
**Problem:** Contacts were being marked as opted out even when they didn't opt out.

**Root Cause:** The opt-out detection was checking the entire transcript (including AI/bot responses) for opt-out keywords, causing false positives when the AI mentioned opt-out phrases.

**Fix Applied:**
- Made opt-out detection **more strict** - only detects opt-out if the **USER** says it, not the AI
- Filters out lines that start with "Bot:", "AI:", "Assistant:", "Riley:", "Agent:", etc.
- Only checks user lines for opt-out keywords
- Added logging to show which user text triggered opt-out detection

**Code Location:** `vapi/app.py` - `_detect_opt_out()` function (around line 7237)

---

## 🔧 New Features Added

### Clear Opt-Out Status Endpoint

**Endpoint:** `POST /outbound-calls/contacts/{contact_id}/clear-opt-out`

**Purpose:** Allows admins/PMs to manually clear opt-out status if it was incorrectly set.

**Usage:**
```bash
POST /outbound-calls/contacts/{contact_id}/clear-opt-out
```

**Response:**
```json
{
  "message": "Opt-out status cleared successfully",
  "contact_id": 123,
  "phone_number": "+16282725259",
  "opted_out": false
}
```

**Auth:** Requires property_manager authentication

---

## 📋 How to Use

### If a Contact Shows "Looking" as Name:

1. The system will now automatically filter out "Looking" and similar bad names
2. If you see it in the database, it will be filtered before display
3. The contact's name will show as `null` or use a better name if available

### If a Contact is Incorrectly Marked as Opted Out:

1. **Check the call transcript** to verify if user actually opted out
2. **Use the clear opt-out endpoint** to fix it:
   ```bash
   POST /outbound-calls/contacts/{contact_id}/clear-opt-out
   ```
3. The contact will be eligible for calls again

---

## 🔍 Verification

### Check Name Sanitization:
- Names like "Looking", "Following", "Providing", "Riley" should no longer appear
- If a contact has a bad stored name, the system will prefer `inferred_name` if available
- If both are bad, `name` will be `null`

### Check Opt-Out Detection:
- Opt-out should only be detected when the **user** explicitly says opt-out phrases
- AI mentions of opt-out should NOT trigger opt-out
- Check logs for: `🚫 Opt-out keyword detected in USER transcript: '{keyword}'`

---

## ⚠️ Important Notes

1. **Opt-Out Detection is Now Stricter:**
   - Only detects opt-out from user speech, not AI responses
   - This reduces false positives but may miss some edge cases
   - If a user opts out in a way that doesn't match keywords, you may need to manually opt them out

2. **Name Sanitization:**
   - Bad names are filtered at multiple layers:
     - During extraction (`extract_and_store_intel_for_call_record`)
     - During merging (`get_best_recent_intel_for_phone`)
     - Before returning to frontend (`/outbound-calls/candidates`)
   - If you see a bad name, it's likely in the database from before the fix

3. **Database Cleanup:**
   - Existing contacts with bad names won't be automatically updated
   - They will be filtered in the API response but remain in the database
   - You can manually update them if needed

---

## 🚀 Next Steps

1. **Test the fixes:**
   - Check if "Looking" names still appear in frontend
   - Verify opt-out detection is more accurate

2. **Monitor logs:**
   - Watch for opt-out detection messages
   - Verify they only trigger on user speech

3. **Clear incorrect opt-outs:**
   - Use the new endpoint to fix any contacts incorrectly marked as opted out

---

**Both issues should now be resolved!** 🎉
