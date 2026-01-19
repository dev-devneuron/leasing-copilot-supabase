# Frontend Guide: Outbound Calling with Email & Inquiry Context

This guide explains how to integrate the new **email-first extraction** and **inquiry context** features into the frontend outbound calling interface.

---

## 🎯 Overview of Changes

The backend now:
1. **Extracts email addresses** from call transcripts (priority #1)
2. **Infers names from email** (e.g., `rehan@gmail.com` → `Rehan`)
3. **Extracts inquiry context**: property address, purpose, and summary from last call
4. **Sends re-engagement context** to Vapi when making outbound calls

---

## 📋 API Response Structure

### GET `/outbound-calls/candidates`

**Updated Response:**
```json
{
  "candidates": [
    {
      "contact_id": 123,
      "phone_number": "+14125551234",
      
      // Name (prefer stored, fallback to inferred)
      "name": "Rehan",                    // contact.name OR inferred_name
      "inferred_name": "Rehan",           // Inferred from email
      
      // Email (prefer stored, fallback to extracted)
      "email": "rehan@gmail.com",         // contact.email OR extracted_email
      "extracted_email": "rehan@gmail.com", // Extracted from transcript
      
      // Inquiry context from last call
      "inquiry_property": "188 Alexandra Road, Santa Clara, California",
      "inquiry_purpose": "booking a tour",
      "inquiry_summary": "Purpose: booking a tour | Property: 188 Alexandra Road... | Email: rehan@gmail.com",
      "extracted_region": "California",
      
      // Existing fields
      "timezone": "America/New_York",
      "consent_status": true,
      "opted_out": false,
      "call_attempt_count": 1,
      "last_call_outcome": "no_answer",
      "last_called_at": "2024-01-15T14:30:00Z",
      "last_call_at": "2024-01-10T10:15:00Z",
      "call_direction": "inbound",
      "eligible": true,
      "eligibility_reason": "All checks passed",
      "eligibility_checks": { /* ... */ }
    }
  ],
  "total": 1
}
```

---

## 🔑 Key Fields Explained

### Email Fields
- **`email`** - Primary email field (contact.email OR extracted_email)
- **`extracted_email`** - Email extracted from transcript (may be null)

**Display Logic:**
```javascript
const displayEmail = candidate.email || candidate.extracted_email || "No email";
```

### Name Fields
- **`name`** - Primary name field (contact.name OR inferred_name)
- **`inferred_name`** - Name inferred from email (e.g., `rehan@gmail.com` → `Rehan`)

**Display Logic:**
```javascript
const displayName = candidate.name || candidate.inferred_name || "Unknown";
```

### Inquiry Context Fields (NEW)
- **`inquiry_property`** - Property address/name from last call (e.g., "188 Alexandra Road, Santa Clara, California")
- **`inquiry_purpose`** - Purpose of last call (e.g., "booking a tour", "pricing inquiry", "general information")
- **`inquiry_summary`** - Combined summary: `"Purpose: X | Property: Y | Email: Z"`
- **`extracted_region`** - Region/state extracted from transcript

**Purpose Values:**
- `"booking a tour"`
- `"availability inquiry"`
- `"pricing inquiry"`
- `"maintenance request"`
- `"general information"`
- `null` (if not detected)

---

## 💻 Frontend Implementation Examples

### React Component: Candidate Row

```jsx
import React from 'react';

function CandidateRow({ candidate }) {
  // Get display values with fallbacks
  const displayName = candidate.name || candidate.inferred_name || "Unknown";
  const displayEmail = candidate.email || candidate.extracted_email || "No email";
  
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
  
  // Inquiry context (NEW)
  const hasInquiryContext = candidate.inquiry_property || candidate.inquiry_purpose;
  const inquiryPurpose = candidate.inquiry_purpose || "No specific purpose";
  const inquiryProperty = candidate.inquiry_property || "No property mentioned";
  
  return (
    <tr>
      <td>{candidate.phone_number}</td>
      <td>
        <div>
          <strong>{displayName}</strong>
          {candidate.inferred_name && !candidate.name && (
            <span className="badge badge-info">Inferred from email</span>
          )}
        </div>
        <div className="text-muted small">{displayEmail}</div>
      </td>
      <td>{lastCalledDisplay}</td>
      
      {/* NEW: Inquiry Context */}
      <td>
        {hasInquiryContext ? (
          <div className="inquiry-context">
            <div className="purpose-badge">
              {inquiryPurpose}
            </div>
            {candidate.inquiry_property && (
              <div className="property-info small">
                📍 {candidate.inquiry_property}
              </div>
            )}
            {candidate.inquiry_summary && (
              <details className="summary-details">
                <summary className="small">View summary</summary>
                <div className="summary-text">{candidate.inquiry_summary}</div>
              </details>
            )}
          </div>
        ) : (
          <span className="text-muted">No inquiry context</span>
        )}
      </td>
      
      <td>{candidate.eligible ? "✅ Eligible" : "❌ Not Eligible"}</td>
      <td>
        <button 
          onClick={() => handleCall(candidate)}
          disabled={!candidate.eligible}
        >
          Call
        </button>
      </td>
    </tr>
  );
}
```

### Enhanced Candidate Table with Inquiry Context

```jsx
function CandidateTable({ candidates }) {
  return (
    <table className="candidates-table">
      <thead>
        <tr>
          <th>Phone</th>
          <th>Name / Email</th>
          <th>Last Called</th>
          <th>Last Inquiry</th> {/* NEW COLUMN */}
          <th>Status</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {candidates.map((candidate) => (
          <CandidateRow key={candidate.contact_id} candidate={candidate} />
        ))}
      </tbody>
    </table>
  );
}
```

### Call Trigger Function

```javascript
async function triggerOutboundCall(candidate) {
  try {
    const response = await fetch(
      'https://leasing-copilot-mvp.onrender.com/outbound-calls/trigger',
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${yourJwtToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          phone_number: candidate.phone_number,
          // Optional: override assistant_id or from_number
        })
      }
    );
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to trigger call');
    }
    
    const result = await response.json();
    
    // Show success message
    alert(`Call triggered successfully! Call ID: ${result.call_id}`);
    
    // Refresh candidates list
    await refreshCandidates();
    
  } catch (error) {
    console.error('Error triggering call:', error);
    alert(`Failed to trigger call: ${error.message}`);
  }
}
```

---

## 🎨 UI/UX Recommendations

### 1. Display Email Prominently

Since email is now the primary identifier:
- Show email **below the name** or in a secondary line
- Use a different color/style for email
- Add an email icon (📧)
- Make email copyable (click to copy)

```jsx
<div className="contact-info">
  <div className="name">{displayName}</div>
  <div className="email" onClick={() => copyToClipboard(displayEmail)}>
    📧 {displayEmail}
  </div>
</div>
```

### 2. Show Inquiry Context in a Card/Badge

Display the last inquiry context prominently:
- **Purpose badge**: Color-coded by purpose type
- **Property address**: Truncated if too long, expandable
- **Summary**: Collapsible details section

```jsx
<div className="inquiry-context-card">
  <div className="purpose-badge purpose-{candidate.inquiry_purpose?.replace(/\s+/g, '-')}">
    {candidate.inquiry_purpose || 'General inquiry'}
  </div>
  {candidate.inquiry_property && (
    <div className="property-address">
      <strong>Property:</strong> {candidate.inquiry_property}
    </div>
  )}
</div>
```

### 3. Purpose Badge Colors

Suggested color coding:
- `booking a tour` → Green badge
- `pricing inquiry` → Blue badge
- `availability inquiry` → Yellow badge
- `maintenance request` → Orange badge
- `general information` → Gray badge

### 4. Show Re-engagement Context Before Calling

When user clicks "Call", show a confirmation dialog with context:

```jsx
function CallConfirmationDialog({ candidate, onConfirm, onCancel }) {
  return (
    <div className="modal">
      <h3>Confirm Outbound Call</h3>
      <div className="call-context">
        <p><strong>Calling:</strong> {candidate.phone_number}</p>
        <p><strong>Name:</strong> {candidate.name || candidate.inferred_name || "Unknown"}</p>
        <p><strong>Email:</strong> {candidate.email || candidate.extracted_email || "No email"}</p>
        
        {candidate.inquiry_summary && (
          <div className="reengagement-context">
            <h4>Re-engagement Context:</h4>
            <p className="summary">{candidate.inquiry_summary}</p>
            <p className="note">
              This context will be sent to the AI assistant to help personalize the call.
            </p>
          </div>
        )}
      </div>
      <div className="modal-actions">
        <button onClick={onCancel}>Cancel</button>
        <button onClick={onConfirm} className="primary">Confirm Call</button>
      </div>
    </div>
  );
}
```

---

## 📊 Updated Table Columns

### Recommended Column Layout

| Column | Content | Notes |
|--------|---------|-------|
| Phone | `phone_number` | Copy button |
| **Name / Email** | `name` + `email` (with fallbacks) | **Show both prominently** |
| Last Called | `last_called_at` formatted | With timezone |
| **Last Inquiry** | `inquiry_purpose` + `inquiry_property` | **NEW: Show inquiry context** |
| Attempts | `call_attempt_count` | Badge style |
| Outcome | `last_call_outcome` | Color-coded badge |
| Eligible | `eligible` | Green/Red badge |
| Actions | Call button | Disabled if not eligible |

---

## 🔄 How Re-engagement Works

### Backend Behavior

When you trigger an outbound call via `POST /outbound-calls/trigger`:

1. **Backend loads** the latest call transcript for that contact
2. **Extracts** email, property, purpose from transcript
3. **Sends metadata to Vapi** including:
   ```json
   {
     "reengagementGoal": "Re-engage previously interested customers with AI-powered outreach.",
     "lastInquirySummary": "Purpose: booking a tour | Property: 188 Alexandra Road... | Email: rehan@gmail.com",
     "lastInquiryPurpose": "booking a tour",
     "lastInquiryProperty": "188 Alexandra Road, Santa Clara, California",
     "customerEmail": "rehan@gmail.com",
     "customerName": "Rehan",
     "customerRegion": "California"
   }
   ```
4. **Vapi AI assistant** receives this context and can personalize the call

### Frontend Display

You can show users that context will be sent:

```jsx
function CallButton({ candidate }) {
  const [showContext, setShowContext] = useState(false);
  
  return (
    <div>
      <button 
        onClick={() => triggerCall(candidate)}
        disabled={!candidate.eligible}
      >
        Call
      </button>
      
      {candidate.inquiry_summary && (
        <button 
          className="info-button"
          onClick={() => setShowContext(!showContext)}
          title="View re-engagement context"
        >
          ℹ️
        </button>
      )}
      
      {showContext && candidate.inquiry_summary && (
        <div className="context-tooltip">
          <strong>Re-engagement Context:</strong>
          <p>{candidate.inquiry_summary}</p>
          <small>This will be sent to the AI assistant</small>
        </div>
      )}
    </div>
  );
}
```

---

## 🎯 Priority Display Logic

### Email (Priority Order)
1. `candidate.email` (stored in Contact)
2. `candidate.extracted_email` (extracted from transcript)
3. Display "No email"

### Name (Priority Order)
1. `candidate.name` (stored in Contact)
2. `candidate.inferred_name` (inferred from email)
3. Display "Unknown" or phone number

### Inquiry Context
- Show `inquiry_purpose` as a badge
- Show `inquiry_property` if available
- Show `inquiry_summary` in expandable details
- If all are null, show "No inquiry context"

---

## 📝 Complete Example: Candidate Card Component

```jsx
function CandidateCard({ candidate }) {
  const displayName = candidate.name || candidate.inferred_name || "Unknown";
  const displayEmail = candidate.email || candidate.extracted_email || "No email";
  const hasEmail = displayEmail !== "No email";
  const hasInquiry = candidate.inquiry_purpose || candidate.inquiry_property;
  
  return (
    <div className="candidate-card">
      {/* Header */}
      <div className="card-header">
        <div className="contact-primary">
          <h3>{displayName}</h3>
          {candidate.inferred_name && !candidate.name && (
            <span className="badge badge-secondary">Inferred</span>
          )}
        </div>
        <div className="contact-secondary">
          <div className="phone">{candidate.phone_number}</div>
          <div className={`email ${hasEmail ? '' : 'no-email'}`}>
            {hasEmail ? `📧 ${displayEmail}` : '📧 No email'}
          </div>
        </div>
      </div>
      
      {/* Inquiry Context Section */}
      {hasInquiry && (
        <div className="inquiry-section">
          <div className="section-title">Last Inquiry</div>
          {candidate.inquiry_purpose && (
            <div className={`purpose-badge purpose-${candidate.inquiry_purpose.replace(/\s+/g, '-')}`}>
              {candidate.inquiry_purpose}
            </div>
          )}
          {candidate.inquiry_property && (
            <div className="property-info">
              <strong>Property:</strong> {candidate.inquiry_property}
            </div>
          )}
          {candidate.inquiry_summary && (
            <details className="summary">
              <summary>View full summary</summary>
              <div className="summary-content">{candidate.inquiry_summary}</div>
            </details>
          )}
        </div>
      )}
      
      {/* Call Info */}
      <div className="call-info">
        <div>Last Called: {formatLastCalled(candidate)}</div>
        <div>Attempts: {candidate.call_attempt_count}</div>
        <div>Status: {candidate.eligible ? "✅ Eligible" : "❌ Not Eligible"}</div>
      </div>
      
      {/* Actions */}
      <div className="card-actions">
        <button 
          onClick={() => triggerCall(candidate)}
          disabled={!candidate.eligible}
          className="call-button"
        >
          {candidate.inquiry_summary ? "Re-engage" : "Call"}
        </button>
      </div>
    </div>
  );
}
```

---

## 🎨 CSS Styling Suggestions

```css
/* Purpose Badge Colors */
.purpose-badge {
  display: inline-block;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}

.purpose-booking-a-tour {
  background-color: #10b981;
  color: white;
}

.purpose-pricing-inquiry {
  background-color: #3b82f6;
  color: white;
}

.purpose-availability-inquiry {
  background-color: #f59e0b;
  color: white;
}

.purpose-maintenance-request {
  background-color: #f97316;
  color: white;
}

.purpose-general-information {
  background-color: #6b7280;
  color: white;
}

/* Inquiry Context Card */
.inquiry-context-card {
  background: #f9fafb;
  border-left: 3px solid #3b82f6;
  padding: 12px;
  margin: 8px 0;
  border-radius: 4px;
}

.property-info {
  margin-top: 8px;
  font-size: 14px;
  color: #4b5563;
}

/* Email Display */
.email {
  color: #3b82f6;
  cursor: pointer;
  font-size: 14px;
}

.email:hover {
  text-decoration: underline;
}

.email.no-email {
  color: #9ca3af;
  cursor: default;
}
```

---

## ✅ Checklist for Frontend Implementation

- [ ] Update candidate table/row to show `email` with fallback to `extracted_email`
- [ ] Update name display to use `name` with fallback to `inferred_name`
- [ ] Add new column/section for "Last Inquiry" context
- [ ] Display `inquiry_purpose` as a color-coded badge
- [ ] Display `inquiry_property` if available
- [ ] Add expandable section for `inquiry_summary`
- [ ] Update call confirmation dialog to show re-engagement context
- [ ] Add visual indicator when name is "inferred" vs stored
- [ ] Add copy-to-clipboard for email
- [ ] Style purpose badges with appropriate colors
- [ ] Test with candidates that have/don't have inquiry context
- [ ] Handle null/empty values gracefully

---

## 🔍 Testing Scenarios

### Scenario 1: Candidate with Full Context
```json
{
  "name": "Rehan",
  "email": "rehan@gmail.com",
  "inquiry_purpose": "booking a tour",
  "inquiry_property": "188 Alexandra Road, Santa Clara, California",
  "inquiry_summary": "Purpose: booking a tour | Property: 188 Alexandra Road... | Email: rehan@gmail.com"
}
```
**Expected:** Show all fields, purpose badge, property address, expandable summary

### Scenario 2: Candidate with Only Email
```json
{
  "name": null,
  "inferred_name": "Rehan",
  "email": null,
  "extracted_email": "rehan@gmail.com",
  "inquiry_purpose": null,
  "inquiry_property": null
}
```
**Expected:** Show inferred name with badge, extracted email, "No inquiry context"

### Scenario 3: Candidate with No Context
```json
{
  "name": null,
  "inferred_name": null,
  "email": null,
  "extracted_email": null,
  "inquiry_purpose": null,
  "inquiry_property": null
}
```
**Expected:** Show "Unknown", "No email", "No inquiry context"

---

## 📚 Additional Notes

### Re-engagement Goal Message

The backend automatically sends this message to Vapi:
> "Re-engage previously interested customers with AI-powered outreach."

This helps the AI assistant understand the call's purpose. You don't need to send this from the frontend - it's handled automatically.

### Metadata Sent to Vapi

When triggering a call, the backend sends this metadata to Vapi (you don't need to handle this):
- `reengagementGoal`
- `lastInquirySummary`
- `lastInquiryPurpose`
- `lastInquiryProperty`
- `customerEmail`
- `customerName`
- `customerRegion`

The Vapi AI assistant can use this context to personalize the conversation.

---

## 🚀 Quick Start

1. **Update your candidate fetch function** to handle new fields
2. **Update candidate display** to show email prominently
3. **Add inquiry context section** to candidate rows/cards
4. **Style purpose badges** with appropriate colors
5. **Test with real data** to see inquiry context in action

The backend is ready - just update the frontend to display these new fields!
