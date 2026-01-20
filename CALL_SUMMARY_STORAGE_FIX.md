# Call Summary Storage Fix

## ✅ Issue Fixed

**Problem:** New calls were only storing transcripts, not summaries, in call logs.

**Root Cause:** 
- The `call.ended` webhook event handler was storing transcripts but **not extracting or storing summaries**
- Summaries were only being stored in the `end-of-call-report` webhook handler
- If Vapi sent a `call.ended` event without a summary, it was never stored

---

## 🔧 Fixes Applied

### 1. **Summary Extraction in `call.ended` Handler**

Added comprehensive summary extraction logic to the `call.ended` event handler:

- Checks multiple locations for summary:
  - `data.analysis.summary` (most common)
  - `data.summary`
  - `payload.analysis.summary`
  - `payload.summary`
- Stores summary in `call_record.call_metadata["summary"]`
- Marks source as `"vapi_call_ended_event"`

**Code Location:** `vapi/app.py` lines ~8386-8419

---

### 2. **Summary Fetching from Vapi API**

Added fallback logic to fetch summaries from Vapi API if not in webhook:

- In `end-of-call-report` handler: Fetches summary from API if missing
- In `call.ended` handler: Fetches summary from API if missing
- Checks `analysis.summary` and `summary` fields in API response

**Code Locations:**
- `vapi/app.py` lines ~8133-8150 (end-of-call-report handler)
- `vapi/app.py` lines ~8519-8560 (call.ended handler)

---

## 📋 How It Works Now

### Summary Storage Flow

```
1. Webhook Received (call.ended or end-of-call-report)
   ↓
2. Extract Summary from Webhook
   - Check data.analysis.summary
   - Check data.summary
   - Check payload.analysis.summary
   - Check payload.summary
   ↓
3. Store Summary in call_metadata["summary"]
   ↓
4. If Summary Still Missing:
   - Fetch call details from Vapi API
   - Extract summary from API response
   - Store in call_metadata["summary"]
```

---

## ✅ Expected Results

After this fix:

1. **All calls store both transcript AND summary:**
   - Transcript: Stored in `CallRecord.transcript`
   - Summary: Stored in `CallRecord.call_metadata["summary"]`

2. **Summary sources tracked:**
   - `"vapi_end_of_call_report"` - From end-of-call-report webhook
   - `"vapi_call_ended_event"` - From call.ended webhook
   - `"vapi_api"` - Fetched from Vapi API

3. **Fallback ensures completeness:**
   - If webhook doesn't include summary, we fetch it from API
   - No calls should be missing summaries anymore

---

## 🔍 Verification

To verify summaries are being stored:

1. **Check database:**
   ```sql
   SELECT call_id, transcript IS NOT NULL as has_transcript,
          call_metadata->>'summary' IS NOT NULL as has_summary,
          call_metadata->>'summary_source' as summary_source
   FROM callrecord
   WHERE created_at > NOW() - INTERVAL '1 day'
   ORDER BY created_at DESC;
   ```

2. **Check logs:**
   - Look for: `📋 Storing summary for call {call_id}`
   - Look for: `📋 Fetched summary from Vapi API`

3. **Check frontend:**
   - Call logs should show both transcript and summary
   - Summary should appear in call details view

---

## 📊 Summary Storage Locations

Summaries are stored in:
- **Database:** `CallRecord.call_metadata["summary"]` (JSONB field)
- **Source tracking:** `CallRecord.call_metadata["summary_source"]`

**Access in code:**
```python
if call_record.call_metadata:
    summary = call_record.call_metadata.get("summary")
    source = call_record.call_metadata.get("summary_source")
```

---

## 🚀 Next Steps

1. **Test with new calls:**
   - Make a test call
   - Verify both transcript and summary are stored
   - Check call logs display both

2. **Backfill existing calls (if needed):**
   - If you have calls missing summaries, you can create a script to fetch them from Vapi API
   - Use `_fetch_call_details_from_vapi(call_id)` function

---

**All calls should now store both transcript and summary!** 🎉
