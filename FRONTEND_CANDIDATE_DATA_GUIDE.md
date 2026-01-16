# Frontend Guide: Getting Candidate Name, Email, and Last Called Time

This guide explains how to extract and display candidate name, email, and last called time from the `/outbound-calls/candidates` API endpoint.

---

## API Endpoint

**GET** `/outbound-calls/candidates?limit=50`

**Authentication:** Required (JWT Bearer token)
**Role:** Property Manager only

---

## Response Structure

```json
{
  "candidates": [
    {
      "contact_id": 123,
      "phone_number": "+14125551234",
      "name": "John Smith",                    // Primary name field
      "email": "john@example.com",              // Contact email (may be null)
      "timezone": "America/New_York",
      "consent_status": true,
      "opted_out": false,
      "call_attempt_count": 1,
      "last_call_outcome": "no_answer",
      "last_called_at": "2024-01-15T14:30:00Z", // ISO 8601 UTC format
      "last_booking_at": null,
      "last_call_id": "call_abc123",
      "last_call_at": "2024-01-10T10:15:00Z",  // ISO 8601 UTC format
      "call_direction": "inbound",
      "extracted_name": "John Smith",           // AI-extracted from transcript
      "extracted_region": "New York",           // AI-extracted from transcript
      "eligible": true,
      "eligibility_reason": "All checks passed",
      "eligibility_checks": { /* ... */ },
      "bypassed_for_testing": false
    }
  ],
  "total": 1
}
```

---

## 📋 Getting Candidate Name

### Name Field Priority

The `name` field is the **primary source** and already includes the best available name:
1. **Contact's stored name** (if set in Contact record)
2. **OR AI-extracted name** from transcript (if contact name was not set)

### Fallback Strategy

If `name` is null, use this priority:
1. `name` (primary field)
2. `extracted_name` (AI-extracted from transcript)
3. Display "Unknown" or phone number

### Code Examples

**JavaScript/TypeScript:**
```javascript
// Helper function to get candidate name
function getCandidateName(candidate) {
  // name field already includes extracted_name as fallback
  return candidate.name || candidate.extracted_name || "Unknown";
}

// Usage
const displayName = getCandidateName(candidate);
```

**React Component:**
```jsx
function CandidateRow({ candidate }) {
  // Get name with fallback
  const name = candidate.name || candidate.extracted_name || "Unknown";
  
  return (
    <tr>
      <td>{candidate.phone_number}</td>
      <td>{name}</td>
      {/* ... other columns */}
    </tr>
  );
}
```

---

## 📧 Getting Candidate Email

### Email Field

- Use the `email` field directly
- It may be `null` if the contact hasn't provided an email
- Display "No email" or hide the email column if null

### Code Examples

**JavaScript/TypeScript:**
```javascript
// Helper function to get candidate email
function getCandidateEmail(candidate) {
  return candidate.email || "No email";
}

// Usage
const displayEmail = getCandidateEmail(candidate);
```

**React Component:**
```jsx
function CandidateRow({ candidate }) {
  // Get email with fallback
  const email = candidate.email || "No email";
  
  return (
    <tr>
      <td>{candidate.phone_number}</td>
      <td>{candidate.name || "Unknown"}</td>
      <td>{email}</td>
      {/* ... other columns */}
    </tr>
  );
}
```

---

## 🕐 Displaying Last Called Time

### Available Time Fields

1. **`last_called_at`** (Primary)
   - ISO 8601 UTC string from Contact record
   - Example: `"2024-01-15T14:30:00Z"`
   - Updated when outbound calls are made
   - Most accurate for tracking when contact was last called

2. **`last_call_at`** (Fallback)
   - ISO 8601 UTC string from CallRecord
   - Example: `"2024-01-10T10:15:00Z"`
   - When the last call record was created
   - May be more recent than `last_called_at` in some cases

### Recommended Approach

1. Use **`last_called_at`** as primary (preferred for outbound calls)
2. Fallback to **`last_call_at`** if `last_called_at` is null
3. **Always convert from UTC to user's local timezone** for display
4. Show "Never called" if both are null

### Code Examples

**JavaScript/TypeScript (Native):**
```javascript
// Format last called time with timezone conversion
function formatLastCalledTime(candidate) {
  // Use last_called_at (preferred) or fallback to last_call_at
  const timeString = candidate.last_called_at || candidate.last_call_at;
  
  if (!timeString) {
    return "Never called";
  }
  
  // Parse ISO 8601 UTC string
  const date = new Date(timeString);
  
  // Format for display (automatically converts to user's timezone)
  return date.toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZoneName: 'short'
  });
  
  // Example output: "Jan 15, 2024, 02:30 PM EST"
}

// Usage
const lastCalledDisplay = formatLastCalledTime(candidate);
```

**Using date-fns library:**
```javascript
import { format, parseISO } from 'date-fns';

function formatLastCalledTimeWithDateFns(candidate) {
  const timeString = candidate.last_called_at || candidate.last_call_at;
  if (!timeString) return "Never called";
  
  const date = parseISO(timeString);
  return format(date, 'MMM d, yyyy h:mm a zzz');
  // Example output: "Jan 15, 2024 2:30 PM EST"
}
```

**React Component Example:**
```jsx
function CandidateRow({ candidate }) {
  // Format last called time
  const lastCalledAt = candidate.last_called_at || candidate.last_call_at;
  
  const lastCalledDisplay = lastCalledAt 
    ? new Date(lastCalledAt).toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        timeZoneName: 'short'
      })
    : "Never called";
  
  return (
    <tr>
      <td>{candidate.phone_number}</td>
      <td>{candidate.name || "Unknown"}</td>
      <td>{candidate.email || "No email"}</td>
      <td>{lastCalledDisplay}</td>
      {/* Example: "Jan 15, 2024, 02:30 PM EST" */}
      <td>{candidate.eligible ? "✅ Eligible" : "❌ Not Eligible"}</td>
    </tr>
  );
}
```

**Complete React Component Example:**
```jsx
import React from 'react';

function CandidateTable({ candidates }) {
  // Helper function to get name
  const getName = (candidate) => {
    return candidate.name || candidate.extracted_name || "Unknown";
  };
  
  // Helper function to get email
  const getEmail = (candidate) => {
    return candidate.email || "No email";
  };
  
  // Helper function to format last called time
  const formatLastCalled = (candidate) => {
    const timeString = candidate.last_called_at || candidate.last_call_at;
    if (!timeString) return "Never called";
    
    const date = new Date(timeString);
    return date.toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      timeZoneName: 'short'
    });
  };
  
  return (
    <table>
      <thead>
        <tr>
          <th>Phone</th>
          <th>Name</th>
          <th>Email</th>
          <th>Last Called</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {candidates.map((candidate) => (
          <tr key={candidate.contact_id}>
            <td>{candidate.phone_number}</td>
            <td>{getName(candidate)}</td>
            <td>{getEmail(candidate)}</td>
            <td>{formatLastCalled(candidate)}</td>
            <td>{candidate.eligible ? "✅ Eligible" : "❌ Not Eligible"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default CandidateTable;
```

---

## ⚠️ Important Notes

### Time Format
- All time fields are in **UTC ISO 8601 format** (ends with `Z`)
- Example: `"2024-01-15T14:30:00Z"`
- **Always convert to user's local timezone** using `toLocaleString()` or a date library

### Field Priority
- **Name:** `name` → `extracted_name` → "Unknown"
- **Email:** `email` → "No email"
- **Last Called:** `last_called_at` → `last_call_at` → "Never called"

### Null Handling
- Both `last_called_at` and `last_call_at` can be `null`
- `email` can be `null`
- `name` and `extracted_name` can both be `null`
- Always handle null cases gracefully

### Best Practices
- ✅ Use `last_called_at` as primary (most accurate for outbound calls)
- ✅ Always convert UTC to local timezone for display
- ✅ Show "Never called" if both time fields are null
- ✅ Consider showing relative time too (e.g., "2 hours ago") for better UX
- ✅ Use the `name` field directly (it already includes extracted name as fallback)

---

## Quick Reference

| Field | Type | Description | Fallback |
|-------|------|-------------|----------|
| `name` | string \| null | Contact name or extracted name | `extracted_name` → "Unknown" |
| `email` | string \| null | Contact email | "No email" |
| `last_called_at` | string \| null | Last called time (UTC ISO 8601) | `last_call_at` → "Never called" |
| `last_call_at` | string \| null | Last call record time (UTC ISO 8601) | "Never called" |
| `extracted_name` | string \| null | AI-extracted name from transcript | "Unknown" |
| `extracted_region` | string \| null | AI-extracted region from transcript | null |

---

## Example API Call

```javascript
// Fetch candidates
async function fetchCandidates(limit = 50) {
  const response = await fetch(
    'https://leasing-copilot-mvp.onrender.com/outbound-calls/candidates?limit=' + limit,
    {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${yourJwtToken}`,
        'Content-Type': 'application/json'
      }
    }
  );
  
  if (!response.ok) {
    throw new Error('Failed to fetch candidates');
  }
  
  const data = await response.json();
  return data.candidates;
}

// Usage
const candidates = await fetchCandidates();
candidates.forEach(candidate => {
  const name = candidate.name || candidate.extracted_name || "Unknown";
  const email = candidate.email || "No email";
  const lastCalled = candidate.last_called_at || candidate.last_call_at;
  const lastCalledDisplay = lastCalled 
    ? new Date(lastCalled).toLocaleString()
    : "Never called";
  
  console.log(`${name} (${email}) - Last called: ${lastCalledDisplay}`);
});
```
