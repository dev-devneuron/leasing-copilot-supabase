# Frontend Complete Data Handling Guide

## 🎯 Overview

This guide explains the complete data flow, logic, and best practices for handling contact and candidate data in the frontend. It covers why you might see different data in different tabs and how to handle it correctly.

---

## 📊 Two Different Endpoints, Two Different Purposes

### 1. **Candidates Endpoint** (`/outbound-calls/candidates`)
**Purpose:** Shows contacts who are **eligible for outbound calls** (follow-up candidates)

**Key Features:**
- Only shows contacts who have called before
- Includes extracted intelligence (property, purpose, region) from call transcripts
- Names are **automatically sanitized** (bad names filtered out)
- Includes eligibility status and opt-out details
- Optimized for re-engagement workflows

### 2. **Contacts Endpoint** (`/outbound-calls/contacts`)
**Purpose:** Shows **all contacts** in the system (complete contact management)

**Key Features:**
- Shows ALL contacts regardless of call history
- Basic contact information (name, email, phone, consent, opt-out)
- Names are **now also sanitized** (backend fix applied)
- Used for contact management and administration
- No extracted intelligence (that's in candidates)

---

## 🔍 Why You See Different Data

### The "Looking" / "Providing" Issue

**Root Cause:**
- The Contacts endpoint was returning raw database values without sanitization
- Bad names like "Looking", "Providing", "Following" are verbs, not real names
- They were extracted incorrectly by AI and stored in the database

**Backend Fix:**
- ✅ Both endpoints now sanitize names before returning
- ✅ Bad names are filtered using `_is_bad_person_name()` helper
- ✅ Database cleanup endpoint available: `POST /admin/cleanup-bad-names`

**Frontend Responsibility:**
- Always display `name` field as-is (it's already sanitized)
- If `name` is `null`, show "N/A" or "Unknown"
- Never display raw database values without checking

---

## 📋 Complete Data Structure

### Candidates Response (`/outbound-calls/candidates`)

```typescript
interface Candidate {
  // Basic Info
  contact_id: number;
  phone_number: string;
  name: string | null;  // ✅ SANITIZED - bad names filtered
  inferred_name: string | null;  // ✅ SANITIZED
  stored_name: string | null;  // ✅ SANITIZED
  
  // Email
  email: string | null;
  extracted_email: string | null;
  stored_email: string | null;
  
  // Contact Metadata
  timezone: string;
  consent_status: boolean;
  opted_out: boolean;
  opt_out_reason: string | null;  // NEW: Why they opted out
  opt_out_transcript_line: string | null;  // NEW: Exact transcript line
  call_attempt_count: number;
  
  // Call History
  last_call_outcome: string | null;
  last_called_at: string | null;
  last_call_id: string | null;
  last_call_at: string | null;
  call_direction: "inbound" | "outbound";
  call_transcript: string | null;
  
  // Extracted Intelligence (FROM CALL TRANSCRIPTS)
  extracted_region: string | null;
  inquiry_property: string | null;  // Property they asked about
  inquiry_purpose: string | null;  // "booking a tour", "availability inquiry", etc.
  inquiry_summary: string | null;  // Structured summary
  call_summary: string | null;  // Full call summary
  
  // Eligibility
  eligible: boolean;
  eligibility_reason: string;
  eligibility_checks: {
    consent: boolean;
    not_opted_out: boolean;
    within_time_window: boolean;
    // ... other checks
  };
  bypassed_for_testing: boolean;
}
```

### Contacts Response (`/outbound-calls/contacts`)

```typescript
interface Contact {
  // Basic Info
  id: number;
  phone_number: string;
  name: string | null;  // ✅ NOW SANITIZED - bad names filtered
  email: string | null;
  timezone: string;
  
  // Consent
  consent_status: boolean;
  consent_source: string | null;
  consent_timestamp: string | null;
  
  // Opt-Out
  opted_out: boolean;
  opt_out_timestamp: string | null;
  opt_out_method: string | null;
  
  // DNC Lists
  internal_dnc: boolean;
  national_dnc: boolean;
  
  // Call Stats
  call_attempt_count: number;
  last_call_outcome: string | null;
  last_called_at: string | null;
  last_booking_at: string | null;
  
  // Timestamps
  created_at: string;
  updated_at: string;
}
```

---

## 🎨 Frontend Implementation

### 1. Name Display Logic

**Always use this pattern:**

```tsx
function ContactName({ name }: { name: string | null }) {
  // Backend already sanitizes, but add frontend safety check
  const displayName = name && name.trim() && name.length >= 2 
    ? name 
    : null;
  
  return (
    <span className="font-medium">
      {displayName || "N/A"}
    </span>
  );
}
```

**Why:**
- Backend sanitizes, but frontend should also validate
- Prevents edge cases where bad data slips through
- Provides consistent "N/A" display for missing names

### 2. Candidates Tab Component

```tsx
interface CandidatesTabProps {
  candidates: Candidate[];
}

function CandidatesTab({ candidates }: CandidatesTabProps) {
  return (
    <div className="space-y-4">
      {candidates.map((candidate) => (
        <CandidateCard key={candidate.contact_id} candidate={candidate} />
      ))}
    </div>
  );
}

function CandidateCard({ candidate }: { candidate: Candidate }) {
  return (
    <div className="border rounded-lg p-4">
      {/* Name - use sanitized name field */}
      <h3 className="text-lg font-semibold">
        {candidate.name || "N/A"}
      </h3>
      
      {/* Phone */}
      <p className="text-sm text-gray-600">{candidate.phone_number}</p>
      
      {/* Email */}
      <p className="text-sm text-gray-600">
        {candidate.email || "N/A"}
      </p>
      
      {/* Extracted Intelligence */}
      {candidate.inquiry_property && (
        <div className="mt-2">
          <p className="text-xs text-gray-500">Last Property:</p>
          <p className="text-sm">{candidate.inquiry_property}</p>
        </div>
      )}
      
      {candidate.inquiry_purpose && (
        <div className="mt-1">
          <p className="text-xs text-gray-500">Purpose:</p>
          <p className="text-sm">{candidate.inquiry_purpose}</p>
        </div>
      )}
      
      {/* Opt-Out Status */}
      {candidate.opted_out && (
        <OptOutBadge 
          reason={candidate.opt_out_reason}
          transcriptLine={candidate.opt_out_transcript_line}
        />
      )}
      
      {/* Eligibility */}
      <div className="mt-2">
        {candidate.eligible ? (
          <span className="px-2 py-1 bg-green-100 text-green-800 rounded text-xs">
            Eligible
          </span>
        ) : (
          <span className="px-2 py-1 bg-red-100 text-red-800 rounded text-xs">
            Not Eligible: {candidate.eligibility_reason}
          </span>
        )}
      </div>
    </div>
  );
}
```

### 3. Contacts Tab Component

```tsx
interface ContactsTabProps {
  contacts: Contact[];
}

function ContactsTab({ contacts }: ContactsTabProps) {
  return (
    <div className="space-y-4">
      {contacts.map((contact) => (
        <ContactCard key={contact.id} contact={contact} />
      ))}
    </div>
  );
}

function ContactCard({ contact }: { contact: Contact }) {
  return (
    <div className="border rounded-lg p-4">
      {/* Name - use sanitized name field */}
      <h3 className="text-lg font-semibold">
        {contact.name || "N/A"}
      </h3>
      
      {/* Phone */}
      <p className="text-sm text-gray-600">{contact.phone_number}</p>
      
      {/* Email */}
      <p className="text-sm text-gray-600">
        {contact.email || "N/A"}
      </p>
      
      {/* Consent Status */}
      <div className="mt-2">
        <span className={`px-2 py-1 rounded text-xs ${
          contact.consent_status 
            ? "bg-green-100 text-green-800" 
            : "bg-red-100 text-red-800"
        }`}>
          {contact.consent_status ? "Has Consent" : "No Consent"}
        </span>
      </div>
      
      {/* Opt-Out Status */}
      {contact.opted_out && (
        <div className="mt-2">
          <span className="px-2 py-1 bg-red-100 text-red-800 rounded text-xs">
            Opted Out
          </span>
          {contact.opt_out_method && (
            <span className="ml-2 text-xs text-gray-600">
              ({contact.opt_out_method})
            </span>
          )}
        </div>
      )}
      
      {/* Call Stats */}
      <div className="mt-2 text-xs text-gray-500">
        <p>Call Attempts: {contact.call_attempt_count}</p>
        {contact.last_called_at && (
          <p>Last Called: {formatDate(contact.last_called_at)}</p>
        )}
      </div>
    </div>
  );
}
```

---

## 🔄 Data Flow Logic

### How Names Are Sanitized

```
1. Call Transcript Received
   ↓
2. Gemini AI Extraction
   ↓
3. Post-Processing Validation
   - Check if name is verb/filler word
   - Reject: "Looking", "Providing", "Following", etc.
   ↓
4. Database Storage
   - Good names: Stored in Contact.name
   - Bad names: Stored as-is (legacy data)
   ↓
5. API Response
   - Candidates: Names sanitized before return
   - Contacts: Names sanitized before return (FIXED)
   ↓
6. Frontend Display
   - Always check if name is null/empty
   - Display "N/A" for missing names
```

### Why Same Contact Shows Differently

**Scenario:** Contact with phone `+16282725259`

**In Candidates Tab:**
- Shows: `name: "N/A"` ✅
- Reason: Bad name "Looking" was filtered out
- Has extracted intelligence from calls

**In Contacts Tab (Before Fix):**
- Showed: `name: "Looking"` ❌
- Reason: Raw database value returned
- No extracted intelligence (not a candidate endpoint)

**In Contacts Tab (After Fix):**
- Shows: `name: null` → Displayed as "N/A" ✅
- Reason: Bad name filtered before return
- Consistent with Candidates tab

---

## ✅ Best Practices

### 1. Always Use Sanitized Fields

```tsx
// ✅ GOOD
const displayName = candidate.name || "N/A";

// ❌ BAD - Don't use raw database values
const displayName = candidate.stored_name || candidate.inferred_name || "N/A";
```

### 2. Handle Null Values Gracefully

```tsx
// ✅ GOOD
{contact.name ? (
  <span>{contact.name}</span>
) : (
  <span className="text-gray-400">N/A</span>
)}

// ❌ BAD - Will show "null" or "undefined"
<span>{contact.name}</span>
```

### 3. Use Appropriate Endpoint

```tsx
// ✅ For re-engagement workflows
const candidates = await fetch('/outbound-calls/candidates');

// ✅ For contact management
const contacts = await fetch('/outbound-calls/contacts');
```

### 4. Display Extracted Intelligence Only in Candidates

```tsx
// ✅ GOOD - Only in Candidates tab
{candidate.inquiry_property && (
  <PropertyInfo property={candidate.inquiry_property} />
)}

// ❌ BAD - Contacts don't have this data
{contact.inquiry_property && (
  <PropertyInfo property={contact.inquiry_property} />
)}
```

---

## 🐛 Troubleshooting

### Issue: Same contact shows different names

**Check:**
1. Are you using the correct endpoint?
   - Candidates: `/outbound-calls/candidates`
   - Contacts: `/outbound-calls/contacts`
2. Is the backend updated? (Both endpoints now sanitize)
3. Are you displaying the `name` field correctly?

**Solution:**
```tsx
// Always use the main 'name' field
const displayName = contact.name || candidate.name || "N/A";
```

### Issue: Bad names still appearing

**Check:**
1. Is backend deployed with latest fixes?
2. Have you run the cleanup endpoint?
   ```bash
   POST /admin/cleanup-bad-names?dry_run=false
   ```
3. Is frontend handling null values correctly?

**Solution:**
- Backend filters bad names
- Frontend should also validate (defense in depth)
- Run cleanup to fix existing bad data

---

## 📚 Complete Feature Logic

### Candidates Feature

**Purpose:** Re-engage contacts who called before

**Data Sources:**
- Contact table (basic info)
- CallRecord table (call history)
- Extracted intelligence (from transcripts)

**Key Logic:**
1. Find contacts who have called (inbound or outbound)
2. Extract intelligence from their call transcripts
3. Check eligibility for outbound calls
4. Return enriched candidate data

**Display:**
- Name (sanitized)
- Phone, Email
- Last property inquired about
- Last purpose (booking, availability, etc.)
- Eligibility status
- Opt-out details

### Contacts Feature

**Purpose:** Manage all contacts in the system

**Data Sources:**
- Contact table only

**Key Logic:**
1. Get all contacts from database
2. Return basic contact information
3. Include consent and opt-out status

**Display:**
- Name (sanitized)
- Phone, Email
- Consent status
- Opt-out status
- Call statistics

---

## 🎯 Summary

1. **Two Different Endpoints:**
   - Candidates: For re-engagement (with extracted intelligence)
   - Contacts: For contact management (basic info only)

2. **Name Sanitization:**
   - Both endpoints now sanitize names
   - Bad names filtered before return
   - Frontend should handle null values

3. **Display Logic:**
   - Always use `name` field (already sanitized)
   - Show "N/A" for null/empty names
   - Don't use raw database values

4. **Data Consistency:**
   - Same contact should show same name in both tabs
   - If different, check endpoint and sanitization
   - Run cleanup endpoint to fix existing bad data

---

## 🚀 Next Steps

1. **Update Frontend:**
   - Use sanitized `name` field in both tabs
   - Handle null values gracefully
   - Display "N/A" for missing names

2. **Test:**
   - Verify same contact shows same name in both tabs
   - Check that bad names don't appear
   - Test with null/empty names

3. **Cleanup:**
   - Run `POST /admin/cleanup-bad-names?dry_run=false`
   - Fix existing bad names in database

---

**The backend is fixed - now update the frontend to match!** 🎉
