# Frontend Guide: Call Records with Summary

## ✅ Summary

All call records (both **inbound** and **outbound**) now include:
- ✅ **Transcript** - Full conversation transcript
- ✅ **Summary** - AI-generated call summary from Vapi
- ✅ **Recording** - Audio recording URL (if available)
- ✅ **Call Direction** - "inbound" or "outbound"

---

## 📋 API Endpoints

### 1. **GET `/call-records`** - List All Calls

**Request:**
```typescript
GET /call-records?limit=50&offset=0
Headers: {
  Authorization: "Bearer <JWT_TOKEN>"
}
```

**Response:**
```typescript
{
  call_records: [
    {
      id: string;                    // UUID
      call_id: string;                // Vapi call ID
      realtor_number: string;         // Bot's phone number
      recording_url: string | null;   // Audio recording URL
      transcript: string | null;       // Full conversation transcript
      summary: string | null;         // ✅ NEW - Call summary
      call_duration: number | null;   // Duration in seconds
      call_status: string;            // "ended", "started", etc.
      caller_number: string | null;   // Caller's phone number
      call_direction: "inbound" | "outbound";  // ✅ NEW
      created_at: string | null;      // ISO timestamp
      updated_at: string | null;      // ISO timestamp
    }
  ],
  total: number;
  limit: number;
  offset: number;
}
```

---

### 2. **GET `/call-records/{call_id}`** - Single Call Detail

**Request:**
```typescript
GET /call-records/{call_id}
Headers: {
  Authorization: "Bearer <JWT_TOKEN>"
}
```

**Response:**
```typescript
{
  id: string;
  call_id: string;
  realtor_number: string;
  recording_url: string | null;
  transcript: string | null;
  summary: string | null;            // ✅ NEW - Explicitly extracted
  live_transcript_chunks: string[];  // Real-time transcript chunks
  call_duration: number | null;
  call_status: string;
  caller_number: string | null;
  call_direction: "inbound" | "outbound";  // ✅ NEW
  metadata: {                         // Full metadata (includes summary too)
    summary?: string;
    summary_source?: string;
    // ... other metadata
  };
  created_at: string | null;
  updated_at: string | null;
}
```

---

## 🎨 Frontend Implementation Examples

### React/TypeScript Example

```typescript
// Types
interface CallRecord {
  id: string;
  call_id: string;
  realtor_number: string;
  recording_url: string | null;
  transcript: string | null;
  summary: string | null;  // ✅ NEW
  call_duration: number | null;
  call_status: string;
  caller_number: string | null;
  call_direction: "inbound" | "outbound";  // ✅ NEW
  created_at: string | null;
  updated_at: string | null;
}

// Component
function CallRecordCard({ callRecord }: { callRecord: CallRecord }) {
  return (
    <div className="call-record-card">
      {/* Call Direction Badge */}
      <div className="call-direction-badge">
        {callRecord.call_direction === "outbound" ? "📞 Outbound" : "📥 Inbound"}
      </div>
      
      {/* Summary Section */}
      {callRecord.summary && (
        <div className="summary-section">
          <h3>Call Summary</h3>
          <p className="summary-text">{callRecord.summary}</p>
        </div>
      )}
      
      {/* Transcript Section */}
      {callRecord.transcript && (
        <div className="transcript-section">
          <h3>Full Transcript</h3>
          <details>
            <summary>View Transcript ({callRecord.transcript.length} chars)</summary>
            <pre className="transcript-text">{callRecord.transcript}</pre>
          </details>
        </div>
      )}
      
      {/* Recording Section */}
      {callRecord.recording_url && (
        <div className="recording-section">
          <h3>Recording</h3>
          <audio src={callRecord.recording_url} controls />
        </div>
      )}
      
      {/* Metadata */}
      <div className="call-metadata">
        <p>Duration: {callRecord.call_duration}s</p>
        <p>Status: {callRecord.call_status}</p>
        <p>Caller: {callRecord.caller_number || "Unknown"}</p>
        <p>Date: {new Date(callRecord.created_at || "").toLocaleString()}</p>
      </div>
    </div>
  );
}
```

---

### Display Priority

**Recommended Display Order:**
1. **Summary** (if available) - Most important, concise overview
2. **Transcript** (if available) - Full conversation details
3. **Recording** (if available) - Audio playback

**Example Layout:**
```
┌─────────────────────────────────────┐
│ 📞 Outbound Call                    │
├─────────────────────────────────────┤
│ 📋 Summary                          │
│ The customer called to inquire...   │
├─────────────────────────────────────┤
│ 📄 Transcript                       │
│ [View Full Transcript ▼]           │
├─────────────────────────────────────┤
│ 🎙️ Recording                        │
│ [Audio Player]                      │
└─────────────────────────────────────┘
```

---

## 🔍 Handling Null/Empty Values

### Summary Field
```typescript
// Check if summary exists and is not empty
if (callRecord.summary && callRecord.summary.trim()) {
  // Display summary
} else {
  // Show "No summary available" or hide section
}
```

### Transcript Field
```typescript
// Check if transcript exists
if (callRecord.transcript && callRecord.transcript.trim()) {
  // Display transcript
} else {
  // Show "No transcript available"
}
```

### Recording Field
```typescript
// Check if recording exists
if (callRecord.recording_url) {
  // Show audio player
} else {
  // Show "No recording available" or hide section
}
```

---

## 📊 Summary Source Information

If you need to know where the summary came from, check `metadata.summary_source`:

```typescript
// In detail view (GET /call-records/{call_id})
const summarySource = callRecord.metadata?.summary_source;

// Possible values:
// - "vapi_end_of_call_report" - From end-of-call-report webhook
// - "vapi_call_ended_event" - From call.ended webhook
// - "vapi_api" - Fetched from Vapi API

if (summarySource) {
  console.log(`Summary source: ${summarySource}`);
}
```

---

## 🎯 Best Practices

### 1. **Always Check for Null**
```typescript
// ✅ Good
{callRecord.summary && <SummaryDisplay summary={callRecord.summary} />}

// ❌ Bad
<SummaryDisplay summary={callRecord.summary} />  // May be null
```

### 2. **Show Loading States**
```typescript
if (loading) {
  return <LoadingSpinner />;
}

if (!callRecord) {
  return <ErrorMessage message="Call record not found" />;
}
```

### 3. **Handle Empty Summaries**
```typescript
{callRecord.summary ? (
  <div className="summary">{callRecord.summary}</div>
) : (
  <div className="no-summary">No summary available for this call</div>
)}
```

### 4. **Distinguish Call Types**
```typescript
const callTypeIcon = callRecord.call_direction === "outbound" 
  ? "📞" 
  : "📥";

const callTypeLabel = callRecord.call_direction === "outbound"
  ? "Outbound Call"
  : "Inbound Call";
```

---

## 🔄 Auto-Refresh (Optional)

If you want to auto-refresh when new summaries arrive:

```typescript
// Poll for updates
useEffect(() => {
  const interval = setInterval(() => {
    fetchCallRecords();  // Refetch call records
  }, 30000);  // Every 30 seconds

  return () => clearInterval(interval);
}, []);
```

---

## ✅ Complete Example

```typescript
import React, { useState, useEffect } from 'react';

interface CallRecord {
  id: string;
  call_id: string;
  transcript: string | null;
  summary: string | null;  // ✅ NEW
  recording_url: string | null;
  call_direction: "inbound" | "outbound";  // ✅ NEW
  call_duration: number | null;
  created_at: string | null;
}

function CallRecordsPage() {
  const [callRecords, setCallRecords] = useState<CallRecord[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchCallRecords();
  }, []);

  const fetchCallRecords = async () => {
    try {
      const response = await fetch('/call-records?limit=50', {
        headers: {
          'Authorization': `Bearer ${getAuthToken()}`,
        },
      });
      const data = await response.json();
      setCallRecords(data.call_records);
    } catch (error) {
      console.error('Error fetching call records:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div>Loading...</div>;
  }

  return (
    <div className="call-records-page">
      <h1>Call Records</h1>
      {callRecords.map((record) => (
        <div key={record.id} className="call-record">
          {/* Call Direction Badge */}
          <div className={`badge ${record.call_direction}`}>
            {record.call_direction === "outbound" ? "📞 Outbound" : "📥 Inbound"}
          </div>
          
          {/* Summary */}
          {record.summary && (
            <div className="summary">
              <h3>Summary</h3>
              <p>{record.summary}</p>
            </div>
          )}
          
          {/* Transcript */}
          {record.transcript && (
            <div className="transcript">
              <h3>Transcript</h3>
              <details>
                <summary>View Full Transcript</summary>
                <pre>{record.transcript}</pre>
              </details>
            </div>
          )}
          
          {/* Recording */}
          {record.recording_url && (
            <div className="recording">
              <h3>Recording</h3>
              <audio src={record.recording_url} controls />
            </div>
          )}
          
          {/* Metadata */}
          <div className="metadata">
            <p>Duration: {record.call_duration}s</p>
            <p>Date: {new Date(record.created_at || "").toLocaleString()}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
```

---

## 🎉 Summary

**Frontend now receives:**
- ✅ `summary` field in all call record responses
- ✅ `call_direction` field to distinguish inbound/outbound
- ✅ Both transcript and summary for complete call information
- ✅ Recording URL for audio playback

**All fields are:**
- ✅ Explicitly extracted (not buried in metadata)
- ✅ Null-safe (check for null before displaying)
- ✅ Available for both inbound and outbound calls

**Ready to integrate!** 🚀
