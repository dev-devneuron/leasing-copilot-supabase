# Vendor Calling Issue Diagnosis

## Current Problem

The vendor call queue shows "calling" status, but the vendor is not receiving any call. The logs show:
- Queue status: "calling"
- Current vendor: "ABC Plumbing"
- But no actual VAPI call is being made

## Root Cause Analysis

The issue is likely one of these:

1. **Missing Assistant ID**: `vapi_vendor_calling_assistant_id` not configured for PropertyManager
2. **Missing Twilio Number**: PropertyManager doesn't have an assigned Twilio number
3. **Missing Twilio Credentials**: Environment variables not set
4. **Early Return in trigger_outbound_call**: Function returns before making API call

## Enhanced Logging Added

I've added detailed logging to help diagnose the issue:

### In `trigger_outbound_call`:
- Logs when function is called with all parameters
- Logs if assistant_id is missing
- Logs if Twilio credentials are missing
- Logs if from_number is missing
- Logs when proceeding to make VAPI API call
- Logs the full payload being sent to VAPI

### In `call_next_vendor`:
- Logs when triggering outbound call
- Logs the full result from `trigger_outbound_call`
- Logs any errors or exceptions

## Next Steps to Diagnose

1. **Check Server Logs** for these messages:
   - `🔍 [OUTBOUND CALLING] trigger_outbound_call called:`
   - `❌ [OUTBOUND CALLING]` (any error messages)
   - `✅ [OUTBOUND CALLING] All prerequisites met:`
   - `📤 SENDING PAYLOAD TO VAPI (VENDOR CALL):`
   - `✅ [VENDOR CALLING] Successfully initiated call`

2. **If you see "No VAPI outbound assistant ID configured"**:
   - Configure `vapi_vendor_calling_assistant_id` in Supabase for PropertyManager

3. **If you see "from_number is required"**:
   - Assign a Twilio number to the PropertyManager
   - Or set `DEFAULT_TWILIO_FROM_NUMBER` environment variable

4. **If you see "Twilio credentials not configured"**:
   - Set `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN` environment variables

5. **If you see "Vapi API error"**:
   - Check VAPI_API_KEY is set correctly
   - Check VAPI_BASE_URL is correct
   - Check the error message for details

## Database Migration Required

**Run this SQL in Supabase:**

```sql
-- Add call_metadata column to vendorcallattempt table
ALTER TABLE vendorcallattempt
ADD COLUMN IF NOT EXISTS call_metadata JSONB;
```

This will fix the 500 error on `/maintenance-requests/{id}/vendor-call-status`.

## Expected Log Flow

When a vendor call is successfully triggered, you should see:

1. `📞 [VENDOR CALLING] Triggering outbound call to vendor X`
2. `🔍 [OUTBOUND CALLING] trigger_outbound_call called:`
3. `✅ [OUTBOUND CALLING] All prerequisites met:`
4. `📤 SENDING PAYLOAD TO VAPI (VENDOR CALL):`
5. `✅ [VENDOR CALLING] Successfully initiated call to vendor X`

If any of these are missing, check the logs for error messages.
