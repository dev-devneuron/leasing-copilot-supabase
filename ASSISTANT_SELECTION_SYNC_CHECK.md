# Assistant Selection & Automation Flow Sync Check

## Executive Summary

**Status:** ⚠️ **CRITICAL GAP IDENTIFIED** - Vendor calls are using the wrong assistant ID field.

**Key Finding:** Vendor calls are currently using `vapi_outbound_assistant_id` which is the same field used for customer re-engagement. This will cause vendor calls to use the wrong assistant (customer re-engagement assistant instead of vendor calling assistant).

---

## 1️⃣ Assistant Selection for Outbound Calls

### Current Implementation (PROBLEM)

**Where assistant is selected:**
- Location: `DB/outbound_calling.py:2319-2335`
- Logic: Uses `PropertyManager.vapi_outbound_assistant_id` (same field for all outbound calls)

**Code Evidence:**
```python
# DB/outbound_calling.py:2319-2329
if not assistant_id and property_manager_id:
    try:
        pm = session.get(PropertyManager, property_manager_id)
        if pm and pm.vapi_outbound_assistant_id:
            assistant_id = pm.vapi_outbound_assistant_id  # ❌ SAME FIELD FOR ALL OUTBOUND CALLS
            print(f"✅ Using outbound assistant ID from PropertyManager {property_manager_id}: {assistant_id}")
```

**Problem:**
- Vendor calls don't pass explicit `assistant_id` parameter
- Falls back to `vapi_outbound_assistant_id` (customer re-engagement assistant)
- **Vendor calls will use the wrong assistant!**

**Vendor Call Trigger:**
```python
# DB/vendor_calling.py:326-337
result = trigger_outbound_call(
    contact=contact,
    property_manager_id=maintenance_request.property_manager_id,
    session=session,
    metadata={...}
    # ❌ NO assistant_id parameter passed!
)
```

### What's Missing

1. **Separate field for vendor calling assistant**
   - Need: `vapi_vendor_calling_assistant_id` in `PropertyManager` table
   - Current: Only `vapi_outbound_assistant_id` exists (for customer re-engagement)

2. **Explicit assistant selection logic**
   - Need: Detect call type from metadata (`vendorCall: True`)
   - Current: No differentiation between vendor calls and customer calls

3. **Assistant ID passed explicitly**
   - Need: Vendor calls should pass `assistant_id` parameter
   - Current: Vendor calls rely on fallback logic

### Recommendation

**Add new field to PropertyManager:**
```python
# DB/db.py - PropertyManager class
vapi_outbound_assistant_id: Optional[str] = Field(default=None)  # For customer re-engagement
vapi_vendor_calling_assistant_id: Optional[str] = Field(default=None)  # NEW: For vendor calls
```

**Update trigger_outbound_call() to detect call type:**
```python
# DB/outbound_calling.py:2319-2340
if not assistant_id and property_manager_id:
    pm = session.get(PropertyManager, property_manager_id)
    if pm:
        # Check metadata to determine call type
        is_vendor_call = metadata and metadata.get("vendorCall") == True
        
        if is_vendor_call:
            # Use vendor calling assistant
            assistant_id = pm.vapi_vendor_calling_assistant_id
            if not assistant_id:
                print(f"⚠️  No vendor calling assistant configured, falling back to outbound assistant")
                assistant_id = pm.vapi_outbound_assistant_id
        else:
            # Use customer re-engagement assistant
            assistant_id = pm.vapi_outbound_assistant_id
```

**Or better: Pass assistant_id explicitly from vendor_calling.py:**
```python
# DB/vendor_calling.py:326-337
# Get vendor calling assistant from PM
pm = session.get(PropertyManager, maintenance_request.property_manager_id)
vendor_assistant_id = pm.vapi_vendor_calling_assistant_id if pm else None

result = trigger_outbound_call(
    contact=contact,
    assistant_id=vendor_assistant_id,  # ✅ EXPLICIT
    property_manager_id=maintenance_request.property_manager_id,
    session=session,
    metadata={...}
)
```

---

## 2️⃣ Automation Flow Confirmation

### Complete Step-by-Step Flow

**Step 1: Maintenance Request Created**
- **Trigger:** `POST /submit_maintenance_request/`
- **Location:** `vapi/app.py:1618-1910`
- **Action:** Creates `MaintenanceRequest` record
- **Automatic:** ✅ YES

**Step 2: Auto-Call Check**
- **Trigger:** Immediately after request creation
- **Location:** `vapi/app.py:1896`
- **Function:** `should_auto_call_vendors(maintenance_request, session)`
- **Checks:**
  - Property-level settings (`auto_call_enabled`)
  - Emergency-only flag
  - Call time restrictions
- **Automatic:** ✅ YES

**Step 3: Vendor Queue Built**
- **Trigger:** If auto-call enabled
- **Location:** `DB/vendor_calling.py:32` → `create_vendor_call_queue()`
- **Function:** `match_vendors_to_maintenance_request()`
- **Process:**
  1. Maps category to service type (e.g., "water leakage" → "plumber")
  2. Gets vendors for property (`get_vendors_for_property()`)
  3. Filters by service type, priority, emergency availability
  4. Excludes opted-out vendors
  5. Sorts by priority (ascending)
  6. Builds queue JSON array
- **Priority Order:** ✅ YES (sorted by `PropertyVendor.priority`)
- **Automatic:** ✅ YES

**Step 4: Outbound Call Triggered**
- **Trigger:** If `auto_start=True` in queue creation
- **Location:** `DB/vendor_calling.py:100-101` → `start_vendor_calling()` → `call_next_vendor()`
- **Function:** `trigger_outbound_call()` in `DB/outbound_calling.py:2284`
- **VAPI Endpoint:** `POST https://api.vapi.ai/call`
- **Assistant Selection:** ❌ **USES WRONG ASSISTANT** (falls back to customer re-engagement)
- **Phone Number:** Uses `get_pm_twilio_number()` or `DEFAULT_TWILIO_FROM_NUMBER`
- **Automatic:** ✅ YES

**Step 5: Vendor Response Captured**
- **Trigger:** VAPI webhook when call ends
- **Location:** `vapi/app.py:10403-10520`
- **Process:**
  1. Webhook detects `metadata.vendorCall == True`
  2. Extracts `vendorCallAttemptId` from metadata
  3. Determines outcome from call status and transcript
  4. Calls `handle_vendor_call_outcome()`
- **Automatic:** ✅ YES

**Step 6: Escalation to Next Vendor**
- **Trigger:** If vendor unavailable (declined/no_response/voicemail)
- **Location:** `DB/vendor_calling.py:486-520`
- **Process:**
  - If declined: Immediately escalates
  - If no_response: After retry check, escalates (retry delay not implemented)
  - Increments `current_vendor_index`
  - Calls `call_next_vendor()` recursively
- **Automatic:** ✅ YES

**Step 7: Assignment Created**
- **Trigger:** If vendor accepts (`outcome == "accepted"`)
- **Location:** `DB/vendor_calling.py:464-484`
- **Process:**
  - Updates `MaintenanceRequest.assigned_vendor_id`
  - Sets `vendor_call_status = "vendor_accepted"`
  - Sets `status = "in_progress"`
  - Marks queue as `completed`
- **Automatic:** ✅ YES

**Step 8: Notifications Triggered**
- **Trigger:** ❌ **NOT IMPLEMENTED**
- **Location:** `vapi/app.py:5100-5200` (endpoint exists but only logs)
- **Function:** `sendVendorNotification` endpoint
- **Status:** Only logs notification request, doesn't send
- **Automatic:** ❌ NO (not implemented)

### Manual Triggers (If Any)

**Manual Override Available:**
- `POST /maintenance-requests/{request_id}/start-vendor-calls` - Manually start calling
- `POST /maintenance-requests/{request_id}/pause-vendor-calls` - Pause calling
- `POST /maintenance-requests/{request_id}/cancel-vendor-calls` - Cancel calling

**But:** Default flow is fully automatic (no manual trigger needed for normal operation).

---

## 3️⃣ Phone Number + Assistant Mapping

### Current Implementation

**Phone Number Selection:**
- **Location:** `DB/outbound_calling.py:2352-2367`
- **Logic:**
  1. Uses `from_number` parameter if provided
  2. Falls back to `get_pm_twilio_number(property_manager_id)` - PM's assigned Twilio number
  3. Falls back to `DEFAULT_TWILIO_FROM_NUMBER` environment variable
- **Tied to:** Property Manager (not assistant)

**Assistant Selection:**
- **Location:** `DB/outbound_calling.py:2319-2340`
- **Logic:**
  1. Uses `assistant_id` parameter if provided
  2. Falls back to `pm.vapi_outbound_assistant_id` (customer re-engagement)
  3. Falls back to `VAPI_ASSISTANT_ID` environment variable
- **Problem:** No vendor-specific assistant selection

### Can Different Assistants Use Different Caller IDs?

**Current:** ❌ **NO** - Phone number is selected independently of assistant
- Phone number comes from PM's assigned number or default
- Assistant comes from PM's outbound assistant or default
- No mapping between assistant and phone number

**Recommendation:** 
- Phone number selection is fine (PM-level makes sense)
- Assistant selection needs to be fixed (vendor vs customer)

---

## 4️⃣ Failure & Fallback Handling

### If assistantId is Missing or Invalid

**Current Behavior:**
```python
# DB/outbound_calling.py:2337-2342
if not assistant_id:
    return {
        "success": False,
        "error": "No VAPI outbound assistant ID configured. Please set vapi_outbound_assistant_id for the PropertyManager or set VAPI_ASSISTANT_ID environment variable.",
        "contact_id": contact.id
    }
```

**What Happens:**
- Call is not initiated
- Error returned to caller
- Queue moves to next vendor (if VAPI API call fails)
- **No retry** for missing assistant ID

**Code Evidence:**
```python
# DB/vendor_calling.py:353-368
if result["success"]:
    # Update attempt with VAPI call ID
    attempt.vapi_call_id = result.get("call_id")
    attempt.call_status = "initiated"
else:
    # Call failed
    attempt.call_status = "failed"
    # Move to next vendor
    queue.current_vendor_index += 1
    return call_next_vendor(...)  # Escalates to next vendor
```

### If VAPI Call Fails

**Current Behavior:**
1. **API Failure:** Returns `{"success": False, "error": "..."}`
2. **Attempt Marked:** `call_status = "failed"`
3. **Escalation:** Immediately moves to next vendor
4. **No Retry:** For API failures (only retries for no-response)

**Code Evidence:**
```python
# DB/vendor_calling.py:353-368
else:
    # Call failed
    attempt.call_status = "failed"
    attempt.completed_at = datetime.utcnow()
    session.add(attempt)
    
    # Move to next vendor after delay
    queue.current_vendor_index += 1
    session.add(queue)
    session.commit()
    
    return {
        "success": False,
        "error": result.get("error", "Call failed"),
        "will_retry": queue.current_vendor_index < len(vendor_queue)
    }
```

### Retry / Escalate / Log

**Retry Logic:**
- ✅ **No-response scenarios:** Retries same vendor (up to `max_retries_per_vendor`)
- ❌ **API failures:** No retry, escalates immediately
- ❌ **Missing assistant:** No retry, call fails

**Escalation Logic:**
- ✅ **Automatic:** Moves to next vendor on failure/decline/no-response
- ✅ **Queue exhaustion:** Stops safely when all vendors tried

**Logging:**
- ✅ **Console logs:** All steps logged via `print()`
- ⚠️ **Structured logging:** Not implemented (only console)
- ✅ **Database:** All attempts stored in `VendorCallAttempt` table

---

## 5️⃣ What's Missing & Recommendations

### Critical (Must Fix)

1. **❌ Separate Assistant Field for Vendor Calls**
   - **Missing:** `vapi_vendor_calling_assistant_id` field in `PropertyManager`
   - **Impact:** Vendor calls use wrong assistant (customer re-engagement)
   - **Fix:** Add field + update selection logic

2. **❌ Explicit Assistant Selection in Vendor Calls**
   - **Missing:** Vendor calls don't pass `assistant_id` parameter
   - **Impact:** Falls back to wrong assistant
   - **Fix:** Pass `assistant_id` explicitly from `call_next_vendor()`

### High Priority (Should Fix)

3. **⚠️ Retry Delay Not Implemented**
   - **Missing:** Background worker for delayed retries
   - **Impact:** Moves to next vendor immediately (should wait 15 min)
   - **Fix:** Implement background worker/cron job

4. **⚠️ Webhook Timeout Not Handled**
   - **Missing:** Timeout mechanism if webhook never arrives
   - **Impact:** Queue can get stuck
   - **Fix:** Add timeout + VAPI API polling

### Medium Priority (Nice to Have)

5. **💡 Notifications Not Sent**
   - **Missing:** Actual SMS/email sending
   - **Impact:** No confirmations to vendors/tenants
   - **Fix:** Integrate with notification service

6. **💡 Callback Scheduling Not Implemented**
   - **Missing:** Job queue for scheduled callbacks
   - **Impact:** Vendor-requested callbacks never happen
   - **Fix:** Implement job queue (Celery/RQ)

---

## 6️⃣ Implementation Plan

### Step 1: Add Vendor Calling Assistant Field

```python
# DB/db.py - PropertyManager class
vapi_outbound_assistant_id: Optional[str] = Field(default=None, index=True)  # Customer re-engagement
vapi_vendor_calling_assistant_id: Optional[str] = Field(default=None, index=True)  # NEW: Vendor calls
```

**Migration:** Add column to existing table (SQLAlchemy will handle on next deploy)

### Step 2: Update Vendor Call Trigger

```python
# DB/vendor_calling.py:326-337
# Get vendor calling assistant from PM
pm = session.get(PropertyManager, maintenance_request.property_manager_id)
vendor_assistant_id = None
if pm:
    vendor_assistant_id = pm.vapi_vendor_calling_assistant_id
    if not vendor_assistant_id:
        # Fallback to outbound assistant if vendor assistant not configured
        vendor_assistant_id = pm.vapi_outbound_assistant_id
        print(f"⚠️  No vendor calling assistant configured, using outbound assistant")

result = trigger_outbound_call(
    contact=contact,
    assistant_id=vendor_assistant_id,  # ✅ EXPLICIT
    property_manager_id=maintenance_request.property_manager_id,
    session=session,
    metadata={
        "callContext": json.dumps(call_metadata),
        "vendorCall": True,
        "maintenanceRequestId": maintenance_request_id,
        "vendorId": vendor_id,
        "vendorCallAttemptId": attempt.attempt_id,
    }
)
```

### Step 3: Update trigger_outbound_call() Fallback Logic

```python
# DB/outbound_calling.py:2319-2340
if not assistant_id and property_manager_id:
    pm = session.get(PropertyManager, property_manager_id)
    if pm:
        # Check metadata to determine call type (backup logic)
        is_vendor_call = metadata and metadata.get("vendorCall") == True
        
        if is_vendor_call:
            # Prefer vendor calling assistant
            assistant_id = pm.vapi_vendor_calling_assistant_id
            if not assistant_id:
                print(f"⚠️  No vendor calling assistant, falling back to outbound assistant")
                assistant_id = pm.vapi_outbound_assistant_id
        else:
            # Customer re-engagement
            assistant_id = pm.vapi_outbound_assistant_id
```

**Note:** This is backup logic. Primary fix is passing `assistant_id` explicitly from vendor calls.

### Step 4: Add API Endpoint to Update Vendor Assistant

```python
# vapi/app.py
@app.patch("/property-managers/{pm_id}/vendor-assistant")
async def update_vendor_calling_assistant(
    pm_id: int,
    assistant_id: str = Body(..., embed=True),
    current_user: Dict[str, Any] = Depends(get_current_user_data)
):
    """Update vendor calling assistant ID for a property manager."""
    # Implementation
```

---

## 7️⃣ Verification Checklist

### Assistant Selection
- [ ] `vapi_vendor_calling_assistant_id` field added to `PropertyManager`
- [ ] Vendor calls pass `assistant_id` explicitly
- [ ] Fallback logic differentiates vendor vs customer calls
- [ ] API endpoint to update vendor assistant ID

### Automation Flow
- [x] Maintenance request creation triggers auto-call check
- [x] Vendor queue built automatically
- [x] Outbound call triggered automatically
- [ ] **Assistant selected correctly (FIX NEEDED)**
- [x] Vendor response captured via webhook
- [x] Escalation to next vendor automatic
- [x] Assignment created automatically
- [ ] Notifications sent (not implemented)

### Phone Number Mapping
- [x] Phone number selected from PM's assigned number
- [x] Falls back to default if not assigned
- [ ] Assistant-phone mapping (not needed, PM-level is fine)

### Error Handling
- [x] Missing assistant ID returns error
- [x] VAPI API failure escalates to next vendor
- [x] All attempts logged in database
- [ ] Webhook timeout handling (not implemented)
- [ ] Retry delay implementation (not implemented)

---

## Conclusion

**Status:** ⚠️ **CRITICAL FIX NEEDED** - Assistant selection is broken for vendor calls.

**Core Automation:** ✅ **WORKING** - All steps are automatic except assistant selection.

**Must Fix Before Production:**
1. Add `vapi_vendor_calling_assistant_id` field
2. Pass `assistant_id` explicitly in vendor calls
3. Update fallback logic to differentiate call types

**Timeline:** This fix is critical and should be done immediately. Without it, vendor calls will use the wrong assistant (customer re-engagement assistant instead of vendor calling assistant).

**Impact:** High - Vendor calls will fail or behave incorrectly if using customer re-engagement assistant.
