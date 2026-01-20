# Outbound Call Phone Number Fix

## ✅ Issue Resolved

**Problem:** Outbound calls were failing with error: `'dict' object has no attribute 'strip'`

**Root Cause:** For outbound calls, Vapi returns phone numbers as **dict objects** (with `twilioPhoneNumber`, `twilioAccountSid`, etc.) instead of simple strings. The code was trying to call `.strip()` on these dict objects, causing the error.

**Why Only Outbound Calls?** Inbound calls typically have phone numbers as strings, but outbound calls include the full Twilio phone number object.

---

## 🔧 Fixes Applied

### 1. **`get_phone_number_from_vapi_call()` - Extract from Dict**
**Location:** `DB/vapi_helpers.py` line ~39

**Fix:** Now checks if `phoneNumber` is a dict and extracts the actual phone number string:
```python
if isinstance(phone_number, dict):
    phone_number = (
        phone_number.get("number") or
        phone_number.get("phoneNumber") or
        phone_number.get("twilioPhoneNumber") or
        phone_number.get("twilio_phone_number")
    )
```

---

### 2. **Cache Retrieval - Handle Dict Values**
**Location:** `DB/vapi_helpers.py` line ~363

**Fix:** When retrieving from cache, if value is a dict, extract the phone number string and update cache:
```python
if isinstance(cached_number, dict):
    cached_number = (
        cached_number.get("number") or
        cached_number.get("phoneNumber") or
        cached_number.get("twilioPhoneNumber") or
        cached_number.get("twilio_phone_number")
    )
    # Update cache with string value for future use
    _call_phone_cache[call_id_from_header] = cached_number
```

---

### 3. **Webhook Phone Number Extraction - Enhanced**
**Location:** `vapi/app.py` line ~7927

**Fix:** Enhanced extraction to handle `twilioPhoneNumber` field:
```python
if isinstance(phone_number_obj, dict):
    realtor_number = (
        phone_number_obj.get("number") or
        phone_number_obj.get("phoneNumber") or
        phone_number_obj.get("twilioPhoneNumber") or  # NEW
        phone_number_obj.get("twilio_phone_number")  # NEW
    )
```

**Also added defensive check:**
```python
# Ensure realtor_number is a string (not a dict) before normalizing
if isinstance(realtor_number, dict):
    realtor_number = extract_from_dict(realtor_number) or "unknown"
```

---

### 4. **`_update_vapi_caches()` - Defensive Filtering**
**Location:** `vapi/app.py` line ~2506

**Fix:** Added defensive check to ensure only strings are stored in cache:
```python
# Ensure phone_number is a string (not a dict) - defensive fix for outbound calls
if phone_number and isinstance(phone_number, dict):
    phone_number = extract_from_dict(phone_number)
    if not phone_number:
        return  # Skip cache update if can't extract
```

---

### 5. **Request Body Phone Number Extraction**
**Location:** `DB/vapi_helpers.py` line ~743

**Fix:** Added dict handling when extracting phone number from request body:
```python
if isinstance(phone_number, dict):
    phone_number = extract_from_dict(phone_number)
```

---

## 📋 Phone Number Extraction Priority

When extracting phone number from a dict, we check in this order:
1. `number`
2. `phoneNumber`
3. `twilioPhoneNumber` (for outbound calls)
4. `twilio_phone_number` (alternative format)

---

## ✅ Verification

**Before Fix:**
```
✅ Found phone number from cached call ID: {'twilioPhoneNumber': '+14123882328', ...}
⚠️  Error identifying user: 'dict' object has no attribute 'strip'
```

**After Fix:**
```
✅ Found phone number from cached call ID: {'twilioPhoneNumber': '+14123882328', ...}
✅ Extracted phone number from cached call ID (was dict): +14123882328
✅ Found phone number in request: +14123882328
```

---

## 🎯 Impact

- ✅ **Outbound calls now work correctly** - Phone numbers are properly extracted
- ✅ **Cache stores strings only** - Prevents future dict issues
- ✅ **Defensive handling** - Multiple layers of protection
- ✅ **Backward compatible** - Inbound calls still work (strings handled normally)

---

## 🔍 Why This Only Happened for Outbound Calls

**Inbound Calls:**
- Vapi sends phone number as simple string: `"+14123882328"`
- Works fine with existing code

**Outbound Calls:**
- Vapi sends phone number as full object:
  ```json
  {
    "twilioPhoneNumber": "+14123882328",
    "twilioAccountSid": "AC...",
    "twilioAuthToken": "..."
  }
  ```
- Code tried to call `.strip()` on this dict → Error

---

## ✅ All Fixed!

The system now handles both:
- ✅ **Inbound calls** - String phone numbers (existing behavior)
- ✅ **Outbound calls** - Dict phone numbers (newly fixed)

**Ready for production!** 🚀
