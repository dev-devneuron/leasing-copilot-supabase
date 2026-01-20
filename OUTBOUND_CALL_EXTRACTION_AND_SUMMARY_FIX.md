# Outbound Call Extraction & Summary Fix

## ✅ Issues Fixed

### Issue 1: Outbound Calls Not Triggering Extraction
**Problem:** When outbound call logs arrived from Vapi with transcript/summary, extraction wasn't being triggered or wasn't using the most recent data.

**Root Cause:**
- `call_direction` wasn't being detected from webhook metadata
- Extraction was using `force_re_extract=False`, so it wouldn't re-extract if data already existed

**Fix:**
- ✅ Detect `call_direction` from webhook metadata (`payload.metadata.callDirection` or `message.metadata.callDirection`)
- ✅ Set `call_direction="outbound"` when detected
- ✅ Force re-extraction for outbound calls (`force_re_extract=True`) to ensure most recent data

---

### Issue 2: Summary Not Returned to Frontend
**Problem:** Summaries were stored in `call_metadata["summary"]` but not explicitly returned in API responses.

**Root Cause:**
- `/call-records` endpoint didn't include summary
- `/call-records/{call_id}` endpoint returned full `metadata` but summary wasn't extracted

**Fix:**
- ✅ Added `summary` field to `/call-records` response (extracted from `call_metadata["summary"]`)
- ✅ Added `summary` field to `/call-records/{call_id}` response (explicitly extracted)
- ✅ Added `call_direction` field to both endpoints

---

## 🔧 Changes Applied

### 1. **Call Direction Detection in `/vapi-webhook`**
**Location:** `vapi/app.py` line ~8003

**Before:**
```python
call_record = CallRecord(
    call_direction="inbound",  # Always defaulted to inbound
)
```

**After:**
```python
# Detect from payload.metadata.callDirection or message.metadata.callDirection
call_direction = "inbound"  # Default
if payload_metadata.get("callDirection") == "outbound":
    call_direction = "outbound"
```

---

### 2. **Call Direction Detection in `/vapi/webhook`**
**Location:** `vapi/app.py` line ~8428

**Before:**
```python
call_record = CallRecord(
    call_direction="inbound",  # Always defaulted to inbound
)
```

**After:**
```python
# Detect from payload.metadata.callDirection or data.metadata.callDirection
call_direction = "inbound"  # Default
if payload_metadata.get("callDirection") == "outbound":
    call_direction = "outbound"
```

---

### 3. **Force Re-Extraction for Outbound Calls**
**Location:** `vapi/app.py` lines ~8085 and ~8471

**Before:**
```python
extracted_intel = extract_and_store_intel_for_call_record(
    call_record, session, force_re_extract=False
)
```

**After:**
```python
# Force re-extract for outbound calls to get most recent data
force_re_extract = (call_record.call_direction == "outbound")
extracted_intel = extract_and_store_intel_for_call_record(
    call_record, session, force_re_extract=force_re_extract
)
```

---

### 4. **Summary Added to `/call-records` Endpoint**
**Location:** `vapi/app.py` line ~8741

**Before:**
```python
{
    "transcript": cr.transcript,
    "recording_url": cr.recording_url,
    # No summary field
}
```

**After:**
```python
{
    "transcript": cr.transcript,
    "summary": cr.call_metadata.get("summary") if cr.call_metadata else None,
    "recording_url": cr.recording_url,
    "call_direction": cr.call_direction,
}
```

---

### 5. **Summary Added to `/call-records/{call_id}` Endpoint**
**Location:** `vapi/app.py` line ~8791

**Before:**
```python
{
    "transcript": call_record.transcript,
    "metadata": call_record.call_metadata,  # Summary buried in metadata
}
```

**After:**
```python
{
    "transcript": call_record.transcript,
    "summary": summary,  # Explicitly extracted from metadata
    "call_direction": call_record.call_direction,
    "metadata": call_record.call_metadata,  # Full metadata still available
}
```

---

## 📋 Summary Storage

### Where Summaries Are Stored:
- **Database:** `CallRecord.call_metadata["summary"]` (JSONB field)
- **Source tracking:** `CallRecord.call_metadata["summary_source"]`
  - `"vapi_end_of_call_report"` - From end-of-call-report webhook
  - `"vapi_call_ended_event"` - From call.ended webhook
  - `"vapi_api"` - Fetched from Vapi API

### When Summaries Are Stored:
1. **`/vapi-webhook` (end-of-call-report):**
   - Extracted from `message.analysis.summary` or `message.summary`
   - Stored at line ~8048

2. **`/vapi/webhook` (call.ended event):**
   - Extracted from `data.analysis.summary`, `data.summary`, or `payload.analysis.summary`
   - Stored at line ~8458
   - Fallback: Fetched from Vapi API if not in webhook

---

## 🎯 Frontend Integration Guide

### API Endpoints

#### 1. **GET `/call-records`** (List All Calls)
**Response:**
```json
{
  "call_records": [
    {
      "id": "uuid",
      "call_id": "vapi_call_id",
      "realtor_number": "+14125551234",
      "recording_url": "https://...",
      "transcript": "Full conversation transcript...",
      "summary": "Call summary from Vapi...",  // ✅ NEW
      "call_duration": 120,
      "call_status": "ended",
      "caller_number": "+1234567890",
      "call_direction": "outbound",  // ✅ NEW: "inbound" or "outbound"
      "created_at": "2026-01-20T10:30:00Z",
      "updated_at": "2026-01-20T10:35:00Z"
    }
  ],
  "total": 100,
  "limit": 50,
  "offset": 0
}
```

**Frontend Usage:**
```typescript
interface CallRecord {
  id: string;
  call_id: string;
  realtor_number: string;
  recording_url: string | null;
  transcript: string | null;
  summary: string | null;  // ✅ NEW - Extract from metadata
  call_duration: number | null;
  call_status: string;
  caller_number: string | null;
  call_direction: "inbound" | "outbound";  // ✅ NEW
  created_at: string | null;
  updated_at: string | null;
}

// Display summary if available
{callRecord.summary && (
  <div className="call-summary">
    <h3>Call Summary</h3>
    <p>{callRecord.summary}</p>
  </div>
)}
```

---

#### 2. **GET `/call-records/{call_id}`** (Single Call Detail)
**Response:**
```json
{
  "id": "uuid",
  "call_id": "vapi_call_id",
  "realtor_number": "+14125551234",
  "recording_url": "https://...",
  "transcript": "Full conversation transcript...",
  "summary": "Call summary from Vapi...",  // ✅ NEW - Explicitly extracted
  "live_transcript_chunks": [],
  "call_duration": 120,
  "call_status": "ended",
  "caller_number": "+1234567890",
  "call_direction": "outbound",  // ✅ NEW
  "metadata": {
    "summary": "Call summary...",  // Also available in metadata
    "summary_source": "vapi_end_of_call_report",
    // ... other metadata
  },
  "created_at": "2026-01-20T10:30:00Z",
  "updated_at": "2026-01-20T10:35:00Z"
}
```

**Frontend Usage:**
```typescript
interface CallRecordDetail {
  id: string;
  call_id: string;
  realtor_number: string;
  recording_url: string | null;
  transcript: string | null;
  summary: string | null;  // ✅ NEW - Use this field directly
  live_transcript_chunks: string[];
  call_duration: number | null;
  call_status: string;
  caller_number: string | null;
  call_direction: "inbound" | "outbound";  // ✅ NEW
  metadata: Record<string, any>;  // Full metadata still available
  created_at: string | null;
  updated_at: string | null;
}

// Display both transcript and summary
<div className="call-details">
  {callRecord.summary && (
    <div className="summary-section">
      <h3>Summary</h3>
      <p>{callRecord.summary}</p>
    </div>
  )}
  
  {callRecord.transcript && (
    <div className="transcript-section">
      <h3>Full Transcript</h3>
      <pre>{callRecord.transcript}</pre>
    </div>
  )}
  
  {callRecord.recording_url && (
    <div className="recording-section">
      <h3>Recording</h3>
      <audio src={callRecord.recording_url} controls />
    </div>
  )}
</div>
```

---

## 🔍 Data Flow

### Outbound Call Flow:
```
1. Outbound call triggered via trigger_outbound_call()
   ↓
2. Vapi makes call
   ↓
3. Call ends → Vapi sends webhook
   ↓
4. Webhook received:
   - Extract call_direction from metadata → "outbound"
   - Store transcript in CallRecord.transcript
   - Store summary in CallRecord.call_metadata["summary"]
   ↓
5. Real-time extraction triggered:
   - force_re_extract=True (for outbound calls)
   - Gemini extracts: email, name, property, purpose, region
   - Stored in CallRecord.extracted_intel
   ↓
6. Frontend requests call records:
   - GET /call-records → Returns transcript + summary
   - GET /call-records/{call_id} → Returns transcript + summary
```

---

## ✅ Verification Checklist

- [x] Call direction detected from webhook metadata
- [x] Outbound calls trigger extraction with `force_re_extract=True`
- [x] Summaries stored for both inbound and outbound calls
- [x] Summaries returned in `/call-records` endpoint
- [x] Summaries returned in `/call-records/{call_id}` endpoint
- [x] `call_direction` field added to both endpoints
- [x] Extraction works for both inbound and outbound calls
- [x] Most recent data extracted for outbound calls

---

## 🎉 Result

**Outbound calls now:**
- ✅ Trigger extraction automatically when transcript arrives
- ✅ Force re-extraction to get most recent data
- ✅ Store summaries correctly
- ✅ Return summaries to frontend

**Frontend can now:**
- ✅ Display summaries for all calls (inbound and outbound)
- ✅ Access summary via `callRecord.summary` field
- ✅ Distinguish between inbound and outbound calls via `call_direction`
- ✅ Display transcript, summary, and recording together

**Ready for production!** 🚀
