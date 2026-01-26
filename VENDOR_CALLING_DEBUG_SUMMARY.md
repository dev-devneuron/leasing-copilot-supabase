# Vendor Calling Debug Summary

## Issues Found

### 1. Missing Database Column
**Error**: `column vendorcallattempt.call_metadata does not exist`

**Fix**: Run the SQL in `ADD_VENDOR_CALL_ATTEMPT_CALL_METADATA_COLUMN.sql`

### 2. Vendor Not Receiving Calls

**Possible Causes**:

1. **Missing Assistant ID**: The PropertyManager might not have `vapi_vendor_calling_assistant_id` configured
   - Check logs for: `❌ [VENDOR CALLING] No assistant ID available`
   - Solution: Configure `vapi_vendor_calling_assistant_id` in Supabase for PropertyManager

2. **Missing Twilio Number**: The PropertyManager might not have a Twilio number assigned
   - Check logs for: `from_number is required for outbound calls`
   - Solution: Assign a Twilio number to the PropertyManager

3. **VAPI API Call Failing**: The actual HTTP request to VAPI might be failing
   - Check logs for: `❌ Vapi API error:`
   - Solution: Check VAPI_API_KEY and VAPI_BASE_URL environment variables

## Comparison with Outbound Customer Calling

The vendor calling uses the **same** `trigger_outbound_call()` function as customer re-engagement calls. The key differences are:

1. **Assistant ID**: Vendor calls use `vapi_vendor_calling_assistant_id` (or fallback to `vapi_outbound_assistant_id`)
2. **Metadata**: Vendor calls include `vendorCall: True` in metadata
3. **Context**: Vendor calls include maintenance request details in `callContext`

## Enhanced Logging Added

The code now logs:
- Assistant ID selection process
- PropertyManager configuration
- Full result from `trigger_outbound_call()`
- Any errors during call initiation

## Next Steps

1. Run the SQL migration for `call_metadata` column
2. Check server logs for the detailed logging output
3. Verify PropertyManager has `vapi_vendor_calling_assistant_id` configured
4. Verify PropertyManager has a Twilio number assigned
5. Check VAPI API credentials are configured
