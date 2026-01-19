# Complete Frontend Integration Guide: Outbound Calling with AI-Powered Intelligence

> **⚠️ CRITICAL**: This guide shows you EXACTLY what data the backend sends and how to display ALL of it. Make sure you're displaying `inquiry_summary`, `call_summary`, and `extracted_region` - these are often missed!

## 📋 Table of Contents
1. [Overview](#overview)
2. [API Endpoint Reference](#api-endpoint-reference)
3. [Complete Data Structure](#complete-data-structure)
4. [Integration Steps](#integration-steps)
5. [Display Logic](#display-logic)
6. [UI Components](#ui-components)
7. [Error Handling](#error-handling)
8. [Testing Checklist](#testing-checklist)
9. [Common Issues & Solutions](#common-issues--solutions)

---

## 🎯 Overview

The backend now provides **AI-powered intelligence extraction** from call transcripts, automatically extracting:
- **Email addresses** (highest priority)
- **Customer names** (inferred from email or direct extraction)
- **Inquiry context**: Property addresses, purpose, and summaries
- **Region/State** information

This intelligence is **automatically extracted and cached** when transcripts arrive, and is **sent to Vapi** when making outbound calls for personalized re-engagement.

---

## 📡 API Endpoint Reference

### GET `/outbound-calls/candidates?limit=100`

**Authentication:** Bearer token required

**Query Parameters:**
- `limit` (optional): Maximum number of candidates to return (default: 100)

**Response:**
```json
{
  "candidates": [
    {
      // ... candidate object (see Complete Data Structure below)
    }
  ],
  "total": 5
}
```

### POST `/outbound-calls/trigger`

**Authentication:** Bearer token required

**Request Body:**
```json
{
  "phone_number": "+14125551234"
}
```

**Response:**
```json
{
  "call_id": "call_abc123",
  "status": "queued",
  "message": "Outbound call triggered successfully"
}
```

---

## 📊 Complete Data Structure

### Candidate Object (Full Schema)

```typescript
interface Candidate {
  // ============================================
  // BASIC CONTACT INFORMATION
  // ============================================
  contact_id: number;
  phone_number: string;
  timezone: string;
  
  // ============================================
  // NAME FIELDS (Smart Fallback Logic)
  // ============================================
  name: string | null;              // BEST AVAILABLE: stored_name OR inferred_name
  inferred_name: string | null;      // Name inferred from email/extraction
  stored_name: string | null;       // Name stored in contact table
  
  // ============================================
  // EMAIL FIELDS (Smart Fallback Logic)
  // ============================================
  email: string | null;             // BEST AVAILABLE: stored_email OR extracted_email
  extracted_email: string | null;   // Email extracted from transcript
  stored_email: string | null;      // Email stored in contact table
  
  // ============================================
  // EXTRACTED INTELLIGENCE (NEW - CRITICAL)
  // ============================================
  extracted_region: string | null;        // Region/state: "California", "Santa Clara, California"
  inquiry_property: string | null;        // Property address: "188 Alexandra Road, Santa Clara, California"
  inquiry_purpose: string | null;         // Purpose: "booking a tour", "availability inquiry", "pricing inquiry", etc.
  inquiry_summary: string | null;         // Structured: "Purpose: booking a tour | Property: 188 Alexandra Road... | Email: rehan@gmail.com"
  call_summary: string | null;            // Full call summary from transcript
  
  // ============================================
  // CALL HISTORY
  // ============================================
  last_call_id: string | null;
  last_call_at: string | null;           // ISO 8601 format
  last_called_at: string | null;         // ISO 8601 format
  last_call_outcome: string | null;       // "connected", "no_answer", "voicemail", etc.
  call_direction: string;                 // "inbound" or "outbound"
  call_transcript: string | null;         // Full transcript if available
  call_attempt_count: number;
  last_booking_at: string | null;        // ISO 8601 format
  
  // ============================================
  // CONSENT & COMPLIANCE
  // ============================================
  consent_status: boolean;
  opted_out: boolean;
  
  // ============================================
  // ELIGIBILITY INFORMATION
  // ============================================
  eligible: boolean;
  eligibility_reason: string;
  eligibility_checks: {
    consent?: boolean;
    not_opted_out?: boolean;
    not_internal_dnc?: boolean;
    not_national_dnc?: boolean;
    within_time_window?: boolean;
    below_attempt_limit?: boolean;
    cooldown_passed?: boolean;
    retry_allowed?: boolean;
  };
  bypassed_for_testing: boolean;
}
```

---

## 🔑 Key Fields Explained

### Name Fields (Priority Order)
1. **`name`** - **USE THIS** - Best available name (stored_name OR inferred_name)
2. **`inferred_name`** - Name inferred from email or extracted from transcript
3. **`stored_name`** - Name stored in contact table (may be outdated or "Riley")

**Display Logic:**
```typescript
const displayName = candidate.name || candidate.inferred_name || candidate.stored_name || "Unknown";
const isInferred = candidate.inferred_name && !candidate.stored_name;
```

### Email Fields (Priority Order)
1. **`email`** - **USE THIS** - Best available email (stored_email OR extracted_email)
2. **`extracted_email`** - Email extracted from transcript (most recent)
3. **`stored_email`** - Email stored in contact table (may be outdated)

**Display Logic:**
```typescript
const displayEmail = candidate.email || candidate.extracted_email || candidate.stored_email || "No email";
const isExtracted = candidate.extracted_email && !candidate.stored_email;
```

### Inquiry Context Fields (NEW - CRITICAL)
- **`inquiry_property`** - Property address from last call (e.g., "188 Alexandra Road, Santa Clara, California")
- **`inquiry_purpose`** - Purpose of last call:
  - `"booking a tour"`
  - `"availability inquiry"`
  - `"pricing inquiry"`
  - `"maintenance request"`
  - `"general information"`
  - `"viewing request"`
  - `"application inquiry"`
  - `null` (if not detected)
- **`inquiry_summary`** - Combined summary: `"Purpose: X | Property: Y | Email: Z"`
- **`call_summary`** - Full call summary from transcript
- **`extracted_region`** - Region/state: "California", "Santa Clara, California"

---

## 🚀 Integration Steps

### Step 1: Update API Call

```typescript
// Fetch candidates
async function fetchCandidates(limit: number = 100) {
  const response = await fetch(
    `https://leasing-copilot-mvp.onrender.com/outbound-calls/candidates?limit=${limit}`,
    {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${yourJwtToken}`,
        'Content-Type': 'application/json'
      }
    }
  );
  
  if (!response.ok) {
    throw new Error(`Failed to fetch candidates: ${response.statusText}`);
  }
  
  const data = await response.json();
  return data.candidates; // Array of Candidate objects
}
```

### Step 2: Create Helper Functions

```typescript
// Get display name with fallback
function getDisplayName(candidate: Candidate): string {
  return candidate.name || candidate.inferred_name || candidate.stored_name || "Unknown";
}

// Get display email with fallback
function getDisplayEmail(candidate: Candidate): string {
  return candidate.email || candidate.extracted_email || candidate.stored_email || "No email";
}

// Check if name is inferred
function isNameInferred(candidate: Candidate): boolean {
  return !!candidate.inferred_name && !candidate.stored_name;
}

// Check if email is extracted
function isEmailExtracted(candidate: Candidate): boolean {
  return !!candidate.extracted_email && !candidate.stored_email;
}

// Check if has inquiry context
function hasInquiryContext(candidate: Candidate): boolean {
  return !!(candidate.inquiry_property || candidate.inquiry_purpose);
}

// Format last called time
function formatLastCalled(candidate: Candidate): string {
  const lastCalled = candidate.last_called_at || candidate.last_call_at;
  if (!lastCalled) return "Never called";
  
  return new Date(lastCalled).toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZoneName: 'short'
  });
}
```

### Step 3: Update Candidate Table/List Component

```typescript
interface CandidateRowProps {
  candidate: Candidate;
  onCall: (candidate: Candidate) => void;
}

function CandidateRow({ candidate, onCall }: CandidateRowProps) {
  const displayName = getDisplayName(candidate);
  const displayEmail = getDisplayEmail(candidate);
  const hasInquiry = hasInquiryContext(candidate);
  const isInferred = isNameInferred(candidate);
  const isExtracted = isEmailExtracted(candidate);
  
  return (
    <tr>
      {/* Phone */}
      <td>
        <div className="phone-number">
          {candidate.phone_number}
          <button onClick={() => copyToClipboard(candidate.phone_number)}>
            📋
          </button>
        </div>
      </td>
      
      {/* Name / Email */}
      <td>
        <div className="contact-info">
          <div className="name-row">
            <strong>{displayName}</strong>
            {isInferred && (
              <span className="badge badge-info" title="Name inferred from email or transcript">
                Inferred
              </span>
            )}
          </div>
          <div className={`email-row ${displayEmail === "No email" ? "no-email" : ""}`}>
            📧 {displayEmail}
            {isExtracted && (
              <span className="badge badge-success" title="Email extracted from transcript">
                Extracted
              </span>
            )}
            {displayEmail !== "No email" && (
              <button onClick={() => copyToClipboard(displayEmail)}>
                📋
              </button>
            )}
          </div>
        </div>
      </td>
      
      {/* Timezone */}
      <td>{candidate.timezone}</td>
      
      {/* Attempts */}
      <td>
        <span className="badge badge-secondary">
          {candidate.call_attempt_count}
        </span>
      </td>
      
      {/* Last Called */}
      <td>{formatLastCalled(candidate)}</td>
      
      {/* Last Inquiry (NEW COLUMN) */}
      <td>
        {hasInquiry ? (
          <div className="inquiry-context">
            {candidate.inquiry_purpose && (
              <div className={`purpose-badge purpose-${candidate.inquiry_purpose.replace(/\s+/g, '-')}`}>
                {candidate.inquiry_purpose}
              </div>
            )}
            {candidate.inquiry_property && (
              <div className="property-info small" title={candidate.inquiry_property}>
                📍 {truncateText(candidate.inquiry_property, 50)}
              </div>
            )}
            {/* ALWAYS show inquiry_summary if available - it contains the structured overview */}
            {candidate.inquiry_summary && (
              <details className="summary-details">
                <summary className="small">View summary</summary>
                <div className="summary-text">{candidate.inquiry_summary}</div>
              </details>
            )}
            {/* Also show full call_summary if available and different from inquiry_summary */}
            {candidate.call_summary && candidate.call_summary !== candidate.inquiry_summary && (
              <details className="call-summary-details">
                <summary className="small">View full call summary</summary>
                <div className="call-summary-text">{candidate.call_summary}</div>
              </details>
            )}
            {/* Show region if available */}
            {candidate.extracted_region && (
              <div className="region-info small">
                🌍 {candidate.extracted_region}
              </div>
            )}
          </div>
        ) : (
          <span className="text-muted">No inquiry context</span>
        )}
      </td>
      
      {/* Outcome */}
      <td>
        <span className={`outcome-badge outcome-${candidate.last_call_outcome || 'none'}`}>
          {candidate.last_call_outcome || 'N/A'}
        </span>
      </td>
      
      {/* Eligible */}
      <td>
        {candidate.eligible ? (
          <span className="badge badge-success">✅ Eligible</span>
        ) : (
          <span className="badge badge-danger">❌ Not Eligible</span>
        )}
        {candidate.bypassed_for_testing && (
          <div className="text-warning small">Testing Mode</div>
        )}
      </td>
      
      {/* Actions */}
      <td>
        <button
          onClick={() => onCall(candidate)}
          disabled={!candidate.eligible}
          className="btn btn-primary"
        >
          {hasInquiry ? "Re-engage" : "Call"}
        </button>
      </td>
    </tr>
  );
}
```

### Step 4: Create Inquiry Context Card Component

```typescript
function InquiryContextCard({ candidate }: { candidate: Candidate }) {
  if (!hasInquiryContext(candidate)) {
    return (
      <div className="inquiry-context-empty">
        <span className="text-muted">No inquiry context available</span>
      </div>
    );
  }
  
  return (
    <div className="inquiry-context-card">
      <div className="card-header">
        <h4>Last Inquiry Context</h4>
        <span className="badge badge-info">AI Extracted</span>
      </div>
      
      <div className="card-body">
        {/* Purpose Badge - ALWAYS SHOW IF AVAILABLE */}
        {candidate.inquiry_purpose && (
          <div className="purpose-section">
            <label>Purpose:</label>
            <div className={`purpose-badge purpose-${candidate.inquiry_purpose.replace(/\s+/g, '-')}`}>
              {candidate.inquiry_purpose}
            </div>
          </div>
        )}
        
        {/* Property Address - ALWAYS SHOW IF AVAILABLE */}
        {candidate.inquiry_property && (
          <div className="property-section">
            <label>Property:</label>
            <div className="property-address" title={candidate.inquiry_property}>
              📍 {candidate.inquiry_property}
            </div>
          </div>
        )}
        
        {/* Region - ALWAYS SHOW IF AVAILABLE */}
        {candidate.extracted_region && (
          <div className="region-section">
            <label>Region:</label>
            <div className="region-text">🌍 {candidate.extracted_region}</div>
          </div>
        )}
        
        {/* Structured Summary - ALWAYS SHOW IF AVAILABLE (This is the most important field!) */}
        {candidate.inquiry_summary && (
          <div className="summary-section">
            <label>Summary:</label>
            <div className="summary-text">{candidate.inquiry_summary}</div>
            <small className="text-muted">Combined: Purpose | Property | Email</small>
          </div>
        )}
        
        {/* Full Call Summary (Expandable) - Show if different from inquiry_summary */}
        {candidate.call_summary && candidate.call_summary !== candidate.inquiry_summary && (
          <details className="full-summary">
            <summary>View Full Call Summary</summary>
            <div className="call-summary-text">{candidate.call_summary}</div>
          </details>
        )}
        
        {/* Show if we have extracted email/name from this inquiry */}
        {(candidate.extracted_email || candidate.inferred_name) && (
          <div className="extracted-info-section">
            <label>Extracted from Call:</label>
            {candidate.extracted_email && (
              <div className="extracted-email">📧 {candidate.extracted_email}</div>
            )}
            {candidate.inferred_name && (
              <div className="extracted-name">👤 {candidate.inferred_name}</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
```

### Step 5: Update Call Trigger Function

```typescript
async function triggerOutboundCall(candidate: Candidate) {
  try {
    // Show confirmation dialog with context
    const confirmed = await showCallConfirmation(candidate);
    if (!confirmed) return;
    
    const response = await fetch(
      'https://leasing-copilot-mvp.onrender.com/outbound-calls/trigger',
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${yourJwtToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          phone_number: candidate.phone_number
        })
      }
    );
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to trigger call');
    }
    
    const result = await response.json();
    
    // Show success message
    showNotification({
      type: 'success',
      message: `Call triggered successfully! Call ID: ${result.call_id}`,
      description: hasInquiryContext(candidate) 
        ? 'AI will use inquiry context for personalized conversation'
        : undefined
    });
    
    // Refresh candidates list
    await refreshCandidates();
    
  } catch (error) {
    console.error('Error triggering call:', error);
    showNotification({
      type: 'error',
      message: `Failed to trigger call: ${error.message}`
    });
  }
}

// Call Confirmation Dialog
function showCallConfirmation(candidate: Candidate): Promise<boolean> {
  return new Promise((resolve) => {
    const dialog = document.createElement('div');
    dialog.className = 'call-confirmation-dialog';
    dialog.innerHTML = `
      <div class="dialog-content">
        <h3>Confirm Outbound Call</h3>
        <div class="call-context">
          <p><strong>Calling:</strong> ${candidate.phone_number}</p>
          <p><strong>Name:</strong> ${getDisplayName(candidate)}</p>
          <p><strong>Email:</strong> ${getDisplayEmail(candidate)}</p>
          
          ${hasInquiryContext(candidate) ? `
            <div class="reengagement-context">
              <h4>Re-engagement Context:</h4>
              ${candidate.inquiry_summary ? `<p class="summary">${candidate.inquiry_summary}</p>` : ''}
              ${candidate.inquiry_property ? `<p><strong>Property:</strong> ${candidate.inquiry_property}</p>` : ''}
              ${candidate.inquiry_purpose ? `<p><strong>Purpose:</strong> ${candidate.inquiry_purpose}</p>` : ''}
              <p class="note">
                This context will be sent to the AI assistant to help personalize the call.
              </p>
            </div>
          ` : ''}
        </div>
        <div class="dialog-actions">
          <button class="btn btn-secondary" onclick="this.closest('.call-confirmation-dialog').remove(); window.__callConfirmResolve(false);">
            Cancel
          </button>
          <button class="btn btn-primary" onclick="this.closest('.call-confirmation-dialog').remove(); window.__callConfirmResolve(true);">
            Confirm Call
          </button>
        </div>
      </div>
    `;
    
    (window as any).__callConfirmResolve = resolve;
    document.body.appendChild(dialog);
  });
}
```

---

## 🎨 Display Logic

### Priority Display Rules

#### Name Display
```typescript
// Priority: name > inferred_name > stored_name > "Unknown"
const displayName = candidate.name || "Unknown";

// Show badge if inferred
const showInferredBadge = candidate.inferred_name && !candidate.stored_name;
```

#### Email Display
```typescript
// Priority: email > extracted_email > stored_email > "No email"
const displayEmail = candidate.email || "No email";

// Show badge if extracted
const showExtractedBadge = candidate.extracted_email && !candidate.stored_email;
```

#### Inquiry Context Display
```typescript
// Show inquiry context if ANY of these exist:
const hasInquiry = !!(
  candidate.inquiry_property || 
  candidate.inquiry_purpose || 
  candidate.inquiry_summary
);

// Show purpose badge (color-coded)
if (candidate.inquiry_purpose) {
  // Apply color based on purpose type
}

// Show property (truncate if long)
if (candidate.inquiry_property) {
  // Display with location icon
}
```

---

## 💻 UI Components

### Complete Candidate Table

```typescript
function CandidateTable({ candidates }: { candidates: Candidate[] }) {
  return (
    <div className="candidates-table-container">
      <table className="candidates-table">
        <thead>
          <tr>
            <th>Phone</th>
            <th>Name / Email</th>
            <th>Timezone</th>
            <th>Attempts</th>
            <th>Last Called</th>
            <th>Last Inquiry</th> {/* NEW */}
            <th>Outcome</th>
            <th>Eligible</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {candidates.map((candidate) => (
            <CandidateRow key={candidate.contact_id} candidate={candidate} />
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

### Candidate Card View (Alternative)

```typescript
function CandidateCard({ candidate }: { candidate: Candidate }) {
  return (
    <div className="candidate-card">
      {/* Header */}
      <div className="card-header">
        <div className="contact-primary">
          <h3>{getDisplayName(candidate)}</h3>
          {isNameInferred(candidate) && (
            <span className="badge badge-info">Inferred</span>
          )}
        </div>
        <div className="contact-secondary">
          <div className="phone">{candidate.phone_number}</div>
          <div className={`email ${getDisplayEmail(candidate) === "No email" ? "no-email" : ""}`}>
            📧 {getDisplayEmail(candidate)}
            {isEmailExtracted(candidate) && (
              <span className="badge badge-success">Extracted</span>
            )}
          </div>
        </div>
      </div>
      
      {/* Inquiry Context Section */}
      <InquiryContextCard candidate={candidate} />
      
      {/* Call Info */}
      <div className="call-info">
        <div>Last Called: {formatLastCalled(candidate)}</div>
        <div>Attempts: {candidate.call_attempt_count}</div>
        <div>Status: {candidate.eligible ? "✅ Eligible" : "❌ Not Eligible"}</div>
      </div>
      
      {/* Actions */}
      <div className="card-actions">
        <button
          onClick={() => triggerOutboundCall(candidate)}
          disabled={!candidate.eligible}
          className="btn btn-primary"
        >
          {hasInquiryContext(candidate) ? "Re-engage" : "Call"}
        </button>
      </div>
    </div>
  );
}
```

---

## 🎨 CSS Styling

```css
/* Purpose Badge Colors */
.purpose-badge {
  display: inline-block;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  text-transform: capitalize;
}

.purpose-booking-a-tour {
  background-color: #10b981;
  color: white;
}

.purpose-availability-inquiry {
  background-color: #f59e0b;
  color: white;
}

.purpose-pricing-inquiry {
  background-color: #3b82f6;
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

.purpose-viewing-request {
  background-color: #8b5cf6;
  color: white;
}

.purpose-application-inquiry {
  background-color: #ec4899;
  color: white;
}

/* Inquiry Context Card */
.inquiry-context-card {
  background: #f9fafb;
  border-left: 3px solid #3b82f6;
  padding: 16px;
  margin: 12px 0;
  border-radius: 8px;
}

.inquiry-context-card .card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.inquiry-context-card .card-body > div {
  margin-bottom: 12px;
}

.inquiry-context-card label {
  font-weight: 600;
  color: #4b5563;
  display: block;
  margin-bottom: 4px;
}

.property-address {
  font-size: 14px;
  color: #1f2937;
}

.summary-text {
  font-size: 13px;
  color: #4b5563;
  line-height: 1.5;
}

/* Email Display */
.email-row {
  color: #3b82f6;
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.email-row.no-email {
  color: #9ca3af;
}

.email-row button {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 12px;
}

/* Badges */
.badge {
  display: inline-block;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}

.badge-info {
  background-color: #dbeafe;
  color: #1e40af;
}

.badge-success {
  background-color: #d1fae5;
  color: #065f46;
}

.badge-secondary {
  background-color: #e5e7eb;
  color: #374151;
}

/* Outcome Badges */
.outcome-badge {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  text-transform: capitalize;
}

.outcome-connected {
  background-color: #d1fae5;
  color: #065f46;
}

.outcome-no_answer {
  background-color: #fef3c7;
  color: #92400e;
}

.outcome-voicemail {
  background-color: #e0e7ff;
  color: #3730a3;
}
```

---

## ⚠️ Error Handling

```typescript
async function fetchCandidatesWithErrorHandling(limit: number = 100) {
  try {
    const response = await fetch(
      `https://leasing-copilot-mvp.onrender.com/outbound-calls/candidates?limit=${limit}`,
      {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${yourJwtToken}`,
          'Content-Type': 'application/json'
        }
      }
    );
    
    if (!response.ok) {
      if (response.status === 401) {
        // Handle unauthorized
        throw new Error('Authentication required');
      } else if (response.status === 403) {
        // Handle forbidden
        throw new Error('Access denied');
      } else if (response.status === 500) {
        // Handle server error
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || 'Server error occurred');
      } else {
        throw new Error(`Failed to fetch: ${response.statusText}`);
      }
    }
    
    const data = await response.json();
    
    // Validate response structure
    if (!data.candidates || !Array.isArray(data.candidates)) {
      throw new Error('Invalid response format');
    }
    
    return data.candidates;
    
  } catch (error) {
    console.error('Error fetching candidates:', error);
    
    // Show user-friendly error message
    showNotification({
      type: 'error',
      message: error.message || 'Failed to load candidates',
      duration: 5000
    });
    
    // Return empty array to prevent crashes
    return [];
  }
}
```

---

## ✅ Testing Checklist

### Data Display Tests
- [ ] Name displays correctly (with fallback logic)
- [ ] Email displays correctly (with fallback logic)
- [ ] "Inferred" badge shows when name is inferred
- [ ] "Extracted" badge shows when email is extracted
- [ ] Inquiry context displays when available
- [ ] Purpose badge shows with correct color
- [ ] Property address displays (truncated if long)
- [ ] Summary is expandable/collapsible
- [ ] "No inquiry context" shows when no data

### Functionality Tests
- [ ] Call trigger works with inquiry context
- [ ] Call confirmation dialog shows context
- [ ] Eligibility status displays correctly
- [ ] Last called time formats correctly
- [ ] Copy to clipboard works for phone/email
- [ ] Table/card view works correctly
- [ ] Error handling works for API failures

### Edge Cases
- [ ] Candidate with no email/name
- [ ] Candidate with only inquiry_purpose (no email/name) - **MUST still show purpose badge**
- [ ] Candidate with only inquiry_purpose and inquiry_property (no email/name) - **MUST show both**
- [ ] Candidate with inquiry_summary but missing individual fields - **MUST show summary**
- [ ] Candidate with only email (no name)
- [ ] Candidate with only name (no email)
- [ ] Candidate with all fields populated - **Verify ALL fields display**
- [ ] Candidate with null/undefined values - **Must not crash, show "No X" or empty state**
- [ ] Empty candidates array
- [ ] Network error handling

### Real-World Test Cases (Based on Your Data)
- [ ] **Test Case 1**: `+15404497896` - Has email, name, property, purpose, summary
  - ✅ Should show: "Yashan Jamal", "kj373@gmail.com", purpose badge "booking a tour", property "891 Bullock Ford...", summary
- [ ] **Test Case 2**: `+15419126397` - Has only inquiry_purpose "availability inquiry"
  - ✅ Should show: purpose badge "availability inquiry", "No email", "Unknown"
  - ⚠️ If inquiry_summary exists, MUST show it
- [ ] **Test Case 3**: `+15404496457` - Has email and name but "No inquiry context"
  - ✅ Should show: "John", "john@gmail.com", "No inquiry context"
- [ ] **Test Case 4**: `+14129695225` - No data at all
  - ✅ Should show: "Unknown", "No email", "No inquiry context"

---

## 🔄 How Re-engagement Works

### Backend Behavior

When you trigger an outbound call via `POST /outbound-calls/trigger`:

1. **Backend automatically:**
   - Loads the latest call transcript for that contact
   - Extracts email, property, purpose from transcript (if not already cached)
   - Sends metadata to Vapi including:
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

2. **Vapi AI assistant** receives this context and personalizes the call

### Frontend Display

You can show users that context will be sent:

```typescript
function CallButton({ candidate }: { candidate: Candidate }) {
  const [showContext, setShowContext] = useState(false);
  
  return (
    <div>
      <button
        onClick={() => triggerCall(candidate)}
        disabled={!candidate.eligible}
        className="btn btn-primary"
      >
        {hasInquiryContext(candidate) ? "Re-engage" : "Call"}
      </button>
      
      {hasInquiryContext(candidate) && (
        <button
          className="btn btn-info"
          onClick={() => setShowContext(!showContext)}
          title="View re-engagement context"
        >
          ℹ️ Context
        </button>
      )}
      
      {showContext && hasInquiryContext(candidate) && (
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

## 📝 Complete Example: Full Integration

```typescript
// types.ts
export interface Candidate {
  contact_id: number;
  phone_number: string;
  name: string | null;
  inferred_name: string | null;
  stored_name: string | null;
  email: string | null;
  extracted_email: string | null;
  stored_email: string | null;
  timezone: string;
  consent_status: boolean;
  opted_out: boolean;
  call_attempt_count: number;
  last_call_outcome: string | null;
  last_called_at: string | null;
  last_booking_at: string | null;
  last_call_id: string | null;
  last_call_at: string | null;
  call_direction: string;
  call_transcript: string | null;
  extracted_region: string | null;
  inquiry_property: string | null;
  inquiry_purpose: string | null;
  inquiry_summary: string | null;
  call_summary: string | null;
  eligible: boolean;
  eligibility_reason: string;
  eligibility_checks: Record<string, boolean>;
  bypassed_for_testing: boolean;
}

// api.ts
export async function fetchCandidates(limit: number = 100): Promise<Candidate[]> {
  const response = await fetch(
    `${API_BASE_URL}/outbound-calls/candidates?limit=${limit}`,
    {
      headers: {
        'Authorization': `Bearer ${getAuthToken()}`,
        'Content-Type': 'application/json'
      }
    }
  );
  
  if (!response.ok) {
    throw new Error(`Failed to fetch candidates: ${response.statusText}`);
  }
  
  const data = await response.json();
  return data.candidates;
}

export async function triggerCall(phoneNumber: string): Promise<{ call_id: string }> {
  const response = await fetch(
    `${API_BASE_URL}/outbound-calls/trigger`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${getAuthToken()}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ phone_number: phoneNumber })
    }
  );
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to trigger call');
  }
  
  return response.json();
}

// utils.ts
export function getDisplayName(candidate: Candidate): string {
  return candidate.name || "Unknown";
}

export function getDisplayEmail(candidate: Candidate): string {
  return candidate.email || "No email";
}

export function hasInquiryContext(candidate: Candidate): boolean {
  return !!(candidate.inquiry_property || candidate.inquiry_purpose);
}

// Component usage
function OutboundCallsPage() {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    loadCandidates();
  }, []);
  
  async function loadCandidates() {
    try {
      setLoading(true);
      const data = await fetchCandidates();
      setCandidates(data);
    } catch (error) {
      console.error('Error loading candidates:', error);
      showError('Failed to load candidates');
    } finally {
      setLoading(false);
    }
  }
  
  async function handleCall(candidate: Candidate) {
    try {
      await triggerCall(candidate.phone_number);
      showSuccess('Call triggered successfully!');
      await loadCandidates(); // Refresh
    } catch (error) {
      showError(error.message);
    }
  }
  
  if (loading) return <LoadingSpinner />;
  
  return (
    <div className="outbound-calls-page">
      <h1>Follow-up Candidates</h1>
      <CandidateTable candidates={candidates} onCall={handleCall} />
    </div>
  );
}
```

---

## 🎯 Summary

### What the Backend Provides
✅ **Complete candidate data** with all extracted intelligence  
✅ **Smart fallback logic** for names and emails  
✅ **Inquiry context** (property, purpose, summary)  
✅ **Automatic extraction** when transcripts arrive  
✅ **Re-engagement metadata** sent to Vapi automatically  

### What the Frontend Needs to Do
✅ **Display all fields** using the provided data structure  
✅ **Use smart fallback logic** for names and emails  
✅ **Show inquiry context** prominently  
✅ **Handle null/empty values** gracefully  
✅ **Provide good UX** with badges, tooltips, and expandable sections  

### Key Points
- **`name`** and **`email`** fields already have smart fallback applied - use them directly
- **`inquiry_purpose`** and **`inquiry_property`** are the most important new fields
- **`inquiry_summary`** provides a quick overview
- **`call_summary`** provides full context (can be expandable)
- All fields can be `null` - always handle gracefully

---

## 🚀 Quick Start Checklist

1. [ ] Update API call to use `/outbound-calls/candidates`
2. [ ] Add TypeScript interface for `Candidate` (copy from guide)
3. [ ] Create helper functions for display logic (copy from guide)
4. [ ] Update candidate table/row component
5. [ ] Add "Last Inquiry" column
6. [ ] **CRITICAL: Display inquiry_summary when available** (most important field!)
7. [ ] Display inquiry_purpose as color-coded badge
8. [ ] Display inquiry_property with location icon
9. [ ] Display extracted_region if available
10. [ ] Create `InquiryContextCard` component
11. [ ] Update call trigger function
12. [ ] Add CSS styling for purpose badges
13. [ ] Test with real data (use the test cases provided)
14. [ ] Handle edge cases (null values, empty arrays)
15. [ ] Verify ALL fields from API response are accessible in component

## ⚠️ CRITICAL: Must-Display Fields

Based on your current frontend display, you're missing some fields. **MUST display:**

1. **`inquiry_summary`** - This is the MOST IMPORTANT field! It contains: "Purpose: X | Property: Y | Email: Z"
   - Currently you show purpose and property separately, but the summary gives the complete picture
   - **ALWAYS show this if available**, even if individual fields are missing

2. **`extracted_region`** - Region/state information
   - Show with 🌍 icon if available

3. **`call_summary`** - Full call summary from transcript
   - Show in expandable details if available and different from inquiry_summary

4. **`extracted_email` and `inferred_name`** - Show these separately to indicate they were extracted
   - Even if `email` and `name` already show them, display badges to indicate extraction

## 🔍 Debugging: Check What Backend Sends

Add this to your frontend to see ALL data:

```typescript
// In your candidate row component
console.log('Full candidate data:', candidate);
console.log('Inquiry summary:', candidate.inquiry_summary);
console.log('Call summary:', candidate.call_summary);
console.log('Extracted region:', candidate.extracted_region);
```

This will help you see if the backend is sending data that the frontend isn't displaying.

---

## 🔧 Common Issues & Solutions

### Issue 1: "No inquiry context" but backend has data

**Problem**: Frontend shows "No inquiry context" but backend logs show data exists.

**Solution**: Check if you're checking ALL fields:
```typescript
// WRONG - only checks two fields
const hasInquiry = candidate.inquiry_property || candidate.inquiry_purpose;

// CORRECT - checks all inquiry fields
const hasInquiry = !!(
  candidate.inquiry_property || 
  candidate.inquiry_purpose || 
  candidate.inquiry_summary ||  // ← Don't forget this!
  candidate.extracted_region
);
```

### Issue 2: inquiry_summary not displaying

**Problem**: `inquiry_summary` exists in API response but doesn't show on frontend.

**Solution**: 
1. Check console.log to verify data is received
2. Make sure you're displaying it:
```typescript
// MUST display inquiry_summary - it's the most important field!
{candidate.inquiry_summary && (
  <div className="inquiry-summary">
    {candidate.inquiry_summary}
  </div>
)}
```

### Issue 3: Property address too long

**Problem**: Property address breaks layout.

**Solution**: Truncate with tooltip:
```typescript
{candidate.inquiry_property && (
  <div 
    className="property-address" 
    title={candidate.inquiry_property}  // Full text on hover
  >
    📍 {truncateText(candidate.inquiry_property, 50)}
  </div>
)}
```

### Issue 4: Missing extracted_region

**Problem**: Region not showing even though backend extracts it.

**Solution**: Add region display:
```typescript
{candidate.extracted_region && (
  <div className="region-info">
    🌍 {candidate.extracted_region}
  </div>
)}
```

### Issue 5: call_summary not showing

**Problem**: Full call summary exists but not displayed.

**Solution**: Show in expandable section:
```typescript
{candidate.call_summary && (
  <details className="call-summary">
    <summary>View Full Call Summary</summary>
    <div>{candidate.call_summary}</div>
  </details>
)}
```

## 📊 Complete Field Mapping

| Backend Field | Frontend Display | Priority | Notes |
|--------------|------------------|----------|-------|
| `name` | Display name | HIGH | Use directly (already has fallback) |
| `email` | Display email | HIGH | Use directly (already has fallback) |
| `inquiry_purpose` | Purpose badge | HIGH | Color-coded badge |
| `inquiry_property` | Property address | HIGH | With 📍 icon, truncate if long |
| `inquiry_summary` | Summary text | **CRITICAL** | **MOST IMPORTANT** - shows combined overview |
| `call_summary` | Expandable summary | MEDIUM | Full call context |
| `extracted_region` | Region text | MEDIUM | With 🌍 icon |
| `extracted_email` | Email badge | LOW | Show "Extracted" badge |
| `inferred_name` | Name badge | LOW | Show "Inferred" badge |

## 🎯 Display Priority Rules

1. **ALWAYS show `inquiry_summary` if available** - This is the complete overview
2. **ALWAYS show `inquiry_purpose` as badge** - Quick visual indicator
3. **ALWAYS show `inquiry_property` if available** - With location icon
4. **SHOULD show `extracted_region`** - Additional context
5. **SHOULD show `call_summary`** - Full context in expandable section

---

**The backend is ready - just integrate the frontend using this guide!** 🎉

**Remember**: The backend sends ALL this data. Make sure your frontend displays ALL of it, especially `inquiry_summary` which is the most important field!
