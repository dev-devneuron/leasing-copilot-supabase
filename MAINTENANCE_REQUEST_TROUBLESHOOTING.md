# Maintenance Request Troubleshooting Guide

## Problem: Bot Says "I couldn't find your tenant record" + "Looking for suitable time slots"

### Root Causes

#### 1. **Tenant Not Registered in Database**
The most common issue: The tenant calling hasn't been registered in the `tenant` table.

**Solution:**
- Register the tenant using `POST /tenants` endpoint or directly in the database
- Required fields: `name`, `property_id`, `property_manager_id`
- Recommended: `phone_number` (for automatic identification)

**Example:**
```sql
INSERT INTO tenant (name, phone_number, email, property_id, property_manager_id, unit_number, is_active)
VALUES ('John Smith', '+14125551234', 'john@example.com', 10, 1, 'Apt 3B', true);
```

#### 2. **Phone Number Format Mismatch**
The phone number in the database doesn't match the format VAPI sends.

**Check:**
- Database stores: `+14125551234` (E.164 format)
- VAPI might send: `14125551234`, `(412) 555-1234`, etc.

**Solution:**
- The system normalizes phone numbers, but verify the tenant's phone is stored correctly
- Check backend logs for: `🔍 Pre-identifying tenant from caller phone: <number>`
- Verify the normalized number matches what's in the database

#### 3. **Bot Confusing Maintenance with Booking**
The bot is calling `getAvailableSlots` (booking function) instead of `submitMaintenanceRequest`.

**Symptoms:**
- Bot says "wait looking for suitable time slots" (3 times)
- Bot says "couldn't find a suitable time slot"
- This is from `/get_slots/` endpoint, NOT maintenance request

**Root Cause:**
- VAPI assistant instructions might be confusing maintenance requests with apartment visits
- The function tool might not be properly configured
- The bot's system prompt might need clarification

**Solution:**
1. **Check VAPI Assistant Configuration:**
   - Ensure `submitMaintenanceRequest` function is added
   - Function URL: `https://leasing-copilot-mvp.onrender.com/submit_maintenance_request/`
   - Verify function name matches exactly: `submitMaintenanceRequest`

2. **Update VAPI Assistant Instructions:**
   ```
   IMPORTANT: Maintenance requests are DIFFERENT from apartment visit bookings.
   
   - Maintenance requests: When a tenant reports a repair issue (leaky faucet, broken AC, etc.)
     → Use submitMaintenanceRequest function
     → NO scheduling needed, just log the issue
   
   - Apartment visits: When someone wants to tour/view an apartment
     → Use getAvailableSlots and bookVisit functions
     → Requires scheduling a time slot
   ```

3. **Function Tool Priority:**
   - Make sure `submitMaintenanceRequest` is listed BEFORE booking functions
   - Or add explicit conditions in the function descriptions

### Debugging Steps

#### Step 1: Check Backend Logs

Look for these log messages when a tenant calls:

```
🔍 Pre-identifying tenant from caller phone: +14125551234
✅ Pre-identified tenant: John Smith (ID: 1)
```

OR

```
⚠️  Could not pre-identify tenant from phone number
🔍 Identifying tenant from conversation data (phone/email/name)...
❌ No tenant found matching criteria (phone=+14125551234, email=null, name=null)
```

#### Step 2: Verify Tenant Registration

```sql
-- Check if tenant exists
SELECT * FROM tenant WHERE phone_number = '+14125551234';

-- Check tenant's property
SELECT t.*, a.listing_metadata->>'address' as property_address
FROM tenant t
JOIN apartmentlisting a ON t.property_id = a.id
WHERE t.phone_number = '+14125551234';
```

#### Step 3: Test Phone Number Extraction

The endpoint logs the extracted phone number:
```
🔧 Submitting maintenance request:
   Caller phone (from VAPI): +14125551234
   Tenant phone (from conversation): null
```

If `caller_phone` is `null`, the phone extraction is failing.

#### Step 4: Check VAPI Request Headers

The system looks for phone number in:
- `x-vapi-from` header
- `twilio.from` or `twilio.From` in request body
- Various nested fields in VAPI payload

**Verify in VAPI Dashboard:**
- Check if custom headers are configured: `x-vapi-from={{from}}`
- Check phone number inbound settings

### Common Issues & Fixes

#### Issue 1: Phone Number Not Extracted

**Symptom:** `caller_phone` is `null` in logs

**Fix:**
1. Configure VAPI phone number inbound settings to include custom header:
   ```
   x-vapi-from={{from}}
   ```
2. Or ensure Twilio data is included in webhook payload

#### Issue 2: Tenant Exists But Not Found

**Symptom:** Tenant is in database but bot can't find them

**Possible Causes:**
- Phone number format mismatch (check normalization)
- Tenant's `is_active` is `false`
- Tenant's `property_manager_id` doesn't match the PM who owns the phone number

**Fix:**
```sql
-- Check tenant status
SELECT tenant_id, name, phone_number, is_active, property_manager_id 
FROM tenant 
WHERE phone_number LIKE '%14125551234%';
```

#### Issue 3: Bot Calls Wrong Function

**Symptom:** Bot tries to book a visit instead of submitting maintenance request

**Fix:**
1. Update VAPI assistant system prompt to clearly distinguish:
   - Maintenance requests = repair issues (use `submitMaintenanceRequest`)
   - Apartment visits = viewing/touring (use `getAvailableSlots` + `bookVisit`)

2. Add examples to function descriptions:
   ```json
   {
     "name": "submitMaintenanceRequest",
     "description": "Submit a maintenance or repair request. Use this when a tenant reports a problem that needs fixing (e.g., 'my sink is leaking', 'the AC is broken', 'there's no hot water'). DO NOT use this for scheduling apartment viewings - use getAvailableSlots for that."
   }
   ```

### Testing the Flow

1. **Register a test tenant:**
   ```bash
   POST /tenants
   {
     "name": "Test Tenant",
     "phone_number": "+14125551234",
     "property_id": 10,
     "property_manager_id": 1
   }
   ```

2. **Call the bot from that phone number:**
   - Say: "I need to report a maintenance issue. My kitchen sink is leaking."

3. **Check backend logs:**
   - Should see: `✅ Pre-identified tenant: Test Tenant`
   - Should see: `✅ Created maintenance request ID X`

4. **Verify in database:**
   ```sql
   SELECT * FROM maintenancerequest ORDER BY submitted_at DESC LIMIT 1;
   ```

### Error Messages Explained

| Error Message | Meaning | Solution |
|--------------|---------|----------|
| "I couldn't find your tenant record" | Tenant not in database or phone number mismatch | Register tenant or fix phone number |
| "wait looking for suitable time slots" | Bot is calling `getAvailableSlots` (wrong function) | Fix VAPI assistant instructions |
| "couldn't find a suitable time slot" | Bot tried to book a visit (wrong function) | Fix VAPI assistant instructions |
| Phone extraction returns null | Can't get caller phone from VAPI | Configure VAPI headers or check payload |

### Quick Fix Checklist

- [ ] Tenant is registered in database with correct phone number
- [ ] Phone number is in E.164 format: `+14125551234`
- [ ] Tenant's `is_active` is `true`
- [ ] Tenant's `property_manager_id` matches the PM
- [ ] VAPI function `submitMaintenanceRequest` is configured
- [ ] Function URL is correct: `https://leasing-copilot-mvp.onrender.com/submit_maintenance_request/`
- [ ] VAPI assistant instructions distinguish maintenance from bookings
- [ ] Custom headers are configured in VAPI: `x-vapi-from={{from}}`
- [ ] Backend logs show phone number extraction working

### Next Steps

1. **Check backend logs** for the exact error
2. **Verify tenant registration** in database
3. **Test phone number extraction** by calling and checking logs
4. **Update VAPI assistant** to clarify maintenance vs. booking
5. **Test the full flow** with a registered tenant

