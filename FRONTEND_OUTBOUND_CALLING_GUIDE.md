# Frontend Guide: Automated Outbound Calling (Vapi + Twilio) — PM Dashboard

This guide is **for the frontend cursor AI** implementing the UI/UX for the new outbound-calling feature of LEASAP Product.

Everything here is **a strong suggestion**, not a constraint. You’re good—use your creativity and make the UX **clean, modern, safe, and delightful**. But also treat this feature like a **regulated workflow**: compliance and “do not break existing behavior” are non‑negotiable.

---

## 1) Context (how this fits into Leasap)

Leasap already has:
- Vapi webhooks storing **call logs, transcripts, recordings** in `CallRecord`
- A full bookings system with calendar + approvals
- Existing role-based access: **Property Managers** vs **Realtors**
- A backend that enforces “who can see what” and “who can do what”

This new feature adds:
- A backend-controlled system to **follow up** with warm leads (people who called before but didn’t book)
- A PM-only UI to **review candidates**, **see eligibility reasons**, **trigger a call**, and **manage consent/opt-out**

**Key architecture principle**:
- **Backend decides who is eligible.**
- Frontend is an operator dashboard.
- Vapi only executes calls; the backend owns compliance decisions.

---

## 2) Feature goal (explain it like a product)

### The problem
Many inbound callers ask questions but never finish booking. These are warm leads and can be re-engaged.

### The goal
Build a PM-facing “Outbound Calling” dashboard that:
- Shows eligible follow-up candidates
- Makes it easy to trigger a compliant follow-up call
- Makes it impossible (or at least very hard) to accidentally violate rules:
  - calling outside allowed hours
  - calling opted-out contacts
  - excessive attempts/retries

### The non-negotiables (must be ensured)
- **Compliance first**: opt-out is permanent; calling rules are enforced by backend.
- **No regressions**: don’t break bookings, call records, calendar, or existing navigation.
- **Role safety**: only Property Managers can access outbound calling controls.
- **Never “invent” eligibility** in the UI: show backend’s eligibility checks + reasons.
- **Audit friendliness**: display key compliance fields and outcomes in a readable way.

---

## 3) UX: Suggested screens & interactions (be creative)

You can implement this however you like, but a solid layout is:

### A) “Outbound Calling” page (PM-only)
Tabs:
1. **Candidates** (operational queue)
2. **Contacts** (consent/opt-out management)
3. **Analytics** (simple performance view)

### B) Candidates tab (core operator workflow)
**Table columns (suggested):**
- Phone (E.164, copy button)
- Name / Email (if available)
- Timezone
- Last inbound call date (if provided)
- Attempt count
- Last called at
- **Last call outcome** (badge)
- Eligibility (green/red badge)
- “Why” (eligibility reason, expandable)
- Actions: **Call**, View details

**Row details drawer/modal (suggested):**
- Eligibility checks breakdown (backend-provided booleans)
- Prior call context (last_call_id, last_call_at)
- Quick links:
  - open `Call Records` page filtered by that phone (if you have such filter)
  - view associated transcript/recording if available

**Safety UX suggestions:**
- Disable “Call” if `eligible=false` (still show why).
- If “Call” enabled, show a confirmation dialog:
  - “This will place an outbound call now.”
  - Display the key checks: consent, opted-out, time window, cooldown, attempts.

### C) Contacts tab (compliance control center)
Use this to manage consent/opt-out safely:
- Filters: opted_out true/false, consent_status true/false
- Per-contact actions:
  - “Record consent” (manual)
  - “Opt out” (manual)

**Danger zone UX:**
- Opt-out should require confirmation: “This is permanent.”
- Show method and timestamp when opted out.

### D) Analytics tab (simple and useful)
Show:
- Total outbound calls (period)
- Opt-outs
- Estimated bookings resulting
- Success rate / opt-out rate

Keep it clean; this can be iterated later.

---

## 4) Backend integration rules (do not break existing functionality)

These match the patterns in `FRONTEND_BACKEND_INTEGRATION.md`:

- **Auth**: All outbound calling endpoints require JWT:
  - Header: `Authorization: Bearer <jwt_token>`
- **Role**: PM-only. Backend returns **403** if not PM. Frontend should:
  - Hide navigation and routes for non-PM
  - Also handle backend 403 with a friendly message
- **Error parsing**: FastAPI errors typically return `{ "detail": "..." }`.
  - Always parse JSON before checking `response.ok` (prevents “[object Object]” surprises)
- **Base URL**: use the same base url config used everywhere else:
  - Production: `https://leasing-copilot-mvp.onrender.com`
  - Dev: `http://localhost:8000`

---

## 5) API endpoints you will use (Outbound Calling)

All these endpoints exist in backend (`vapi/app.py`) and require PM auth.

### 5.1 Get candidates
**Endpoint:** `GET /outbound-calls/candidates?limit=50`

**Response shape (high-level):**
- `candidates[]` items include:
  - `contact_id`, `phone_number`, `name`, `email`, `timezone`
  - `consent_status`, `opted_out`
  - `call_attempt_count`, `last_called_at`
  - `last_call_outcome` (badge)
  - `last_booking_at`
  - `last_call_id`, `last_call_at`
  - `eligible` (bool)
  - `eligibility_reason` (string)
  - `eligibility_checks` (object of booleans)

**Frontend expectations:**
- Treat `eligible` and `eligibility_checks` as authoritative.
- Render `eligibility_checks` in an expandable UI (operator needs “why”).

### 5.2 Process queue (batch)
**Endpoint:** `POST /outbound-calls/process-queue`

**Body:**
```json
{ "batch_size": 10 }
```

**Response:** includes counts:
- `called`, `skipped`, `errors`, plus per-contact results

**Frontend UX suggestion:**
- A “Run batch” button (PM-only) with batch size selector.
- Show results in a modal/toast + render per-contact results.

### 5.3 Trigger single call (manual)
**Endpoint:** `POST /outbound-calls/trigger`

**Body:**
```json
{
  "phone_number": "+14125551234",
  "assistant_id": null,
  "from_number": null
}
```

**Response:**
- `call_id`, `contact_id`, `phone_number`

**Frontend UX suggestion:**
- “Call now” action on eligible candidates
- Optional manual entry (paste number → validate → call)

### 5.4 List contacts (compliance table)
**Endpoint:** `GET /outbound-calls/contacts?limit=50&offset=0&opted_out=true|false`

**Response:**
- `contacts[]` items include:
  - consent fields (status/source/timestamp)
  - opt-out fields (timestamp/method)
  - DNC flags
  - attempts, last_called_at
  - `last_call_outcome`
  - `last_booking_at`

**Frontend UX suggestion:**
- Pagination controls using `limit` + `offset`
- Filters toggles (opted_out, consent_status)

### 5.5 Manual opt-out (PM action)
**Endpoint:** `POST /outbound-calls/contacts/{contact_id}/opt-out`

**Body:**
```json
{ "method": "manual" }
```

**UX requirement:**
- Confirmation dialog (permanent)
- After success: refresh row + show toast

### 5.6 Manual consent (PM action)
**Endpoint:** `POST /outbound-calls/contacts/{contact_id}/consent`

**Body:**
```json
{ "source": "manual" }
```

**UX suggestion:**
- Ask for “source” via select: manual / form / sms / call / other

### 5.7 Analytics
**Endpoint:** `GET /outbound-calls/analytics?days=30`

---

## 6) How retries work (show this clearly in UI)

The backend caps attempts and enforces cooldown. In addition:

### Outcome-based retry policy
Backend tracks `last_call_outcome` and uses it to allow/deny retries:

**Only retry on:**
- `no_answer`
- `voicemail`

**Never retry on:**
- `hangup`
- `opt_out`
- `connected`
- `connected_and_declined`

**UX requirement:**
- Display `last_call_outcome` as a badge with tooltips:
  - “Retry allowed” vs “Retry blocked”
- If retry blocked, show it as one of the eligibility check failures (already provided).

---

## 7) How frontend should “coordinate” with backend (workflow)

### Recommended operator workflow
1. PM opens Candidates tab
2. PM sorts by eligible first
3. PM clicks into a candidate → reads “why eligible”
4. PM triggers a call (single) or runs a small batch
5. PM later checks:
   - call record transcript/recording (existing Call Records screens)
   - whether contact opted out
   - whether booking happened afterward

### What not to do in frontend
- Don’t compute calling windows/timezones in UI as a gate. It’s fine to *display* local time, but **don’t enforce**.
- Don’t “retry” by just calling trigger again if backend says not eligible.
- Don’t build a CSV bulk uploader / campaign dialer UI.

---

## 8) Integration with existing Call Records UI (nice UX win)

Your app already has “Call Records & Transcripts”.
Great UX idea: from Outbound Calling UI, provide:
- “View call records for this phone”
- “View last inbound transcript”
- “Open recording” (if available)

**Reminder from existing guide:** call records have both `id` (UUID) and `call_id` (Vapi call id). When calling call-record endpoints, use **`call_id`**.

---

## 9) Testing Mode (Temporary - For Development Only)

### Backend Testing Bypass

The backend has a temporary testing mode that bypasses all eligibility checks. This is controlled by the environment variable `DISABLE_ELIGIBILITY_CHECKS=true`.

**When bypass is enabled:**
- Backend returns `eligible=true` even when checks fail
- Response includes `bypassed_for_testing=true` flag
- Response includes `eligibility_reason` showing what would have blocked it
- API calls succeed even if consent/time window/cooldown checks fail

**Frontend handling for testing mode:**
- Check for `bypassed_for_testing` flag in eligibility response
- If `true`, allow the "Call" button even if `eligible=false` (show warning badge)
- Display warning: "⚠️ Testing Mode: Eligibility checks bypassed"
- Show the original `eligibility_reason` so user knows what's being bypassed

**Example frontend code:**
```javascript
// ✅ CORRECT: Check bypassed_for_testing at TOP LEVEL (not inside eligibility_checks)
// The backend returns: { eligible: true, bypassed_for_testing: true, eligibility_checks: {...} }
const canCall = candidate.eligible || candidate.bypassed_for_testing;

// Show warning if bypassed
if (candidate.bypassed_for_testing) {
  // Show warning badge: "⚠️ Testing Mode"
  // Still enable the "Call" button
}

// ❌ WRONG: Don't check inside eligibility_checks
// const canCall = candidate.eligible || candidate.eligibility_checks?.bypassed_for_testing; // WRONG!
```

**⚠️ IMPORTANT**: This is for testing only. Before production:
1. Backend: Set `DISABLE_ELIGIBILITY_CHECKS=false` or remove from `.env`
2. Frontend: Remove any testing mode bypass logic
3. Verify eligibility checks block calls correctly

---

## 10) Engineering checklist (avoid regressions)

- **Routing**: add a PM-only route; don’t break Realtor navigation.
- **Auth**: reuse the same token plumbing; don’t store tokens in unsafe places.
- **State**: don’t spam refresh loops; use sane polling (or manual refresh button).
- **Performance**: debounce search, paginate contacts; don’t render 5k rows.
- **Error UX**: always show readable error messages from `detail`.
- **Safety**: confirmations for “Call now” and “Opt out”.
- **Testing**:
  - Verify 403 behavior for Realtors
  - Verify candidates list loads
  - Verify disabled call button when not eligible
  - Verify opt-out action updates UI immediately

---

## 11) Final note (creativity + compliance)

Make it visually awesome—great table UX, good filters, clear badges, smart details drawer, perfect empty states.

But the must-haves are:
- **Don’t harm existing functionality**
- **Let backend be the single source of truth for eligibility**
- **Make irreversible actions obvious**
- **Prioritize compliance and user respect over aggressiveness**

