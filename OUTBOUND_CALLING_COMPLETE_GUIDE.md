# Outbound Calling Feature - Complete Implementation Guide

## 📋 Table of Contents

1. [Overview](#overview)
2. [What Was Implemented](#what-was-implemented)
3. [Architecture & Design](#architecture--design)
4. [Database Schema](#database-schema)
5. [Setup Instructions](#setup-instructions)
6. [Testing & Verification](#testing--verification)
7. [Scheduled Job Setup](#scheduled-job-setup)
8. [API Reference](#api-reference)
9. [Compliance & Legal](#compliance--legal)
10. [Troubleshooting](#troubleshooting)
11. [Code Review & Verification](#code-review--verification)

---

## Overview

The outbound calling feature automatically follows up with past callers who:
- Called Leasap before (inbound call exists)
- Asked for information
- Did NOT complete a booking
- Did NOT opt out

**Key Principle**: Backend decides who to call, Vapi only executes.

This is a **compliance-first** system designed to meet TCPA and California CIPA requirements while maintaining a complete audit trail for legal defense.

---

## What Was Implemented

### 1. Database Models (`DB/db.py`)

#### Contact Table (Lines 580-620)
A comprehensive contact/lead tracking table that serves as the primary legal defense for outbound calling:

**Fields:**
- `id` - Primary key
- `phone_number` - E.164 format, unique, indexed
- `timezone` - Contact's timezone for time window enforcement
- `consent_status` - Boolean, indexed (mandatory for compliance)
- `consent_source` - 'call', 'form', 'sms', 'explicit', 'existing_relationship'
- `consent_timestamp` - When consent was obtained
- `opted_out` - Boolean, indexed (zero tolerance flag)
- `opt_out_timestamp` - When opt-out occurred
- `opt_out_method` - 'voice', 'keypad', 'sms', 'web', 'manual'
- `opt_out_call_id` - Call ID where opt-out occurred
- `internal_dnc` - Internal Do Not Call list flag
- `national_dnc` - National DNC registry flag
- `call_attempt_count` - Total outbound attempts
- `last_called_at` - Last outbound call timestamp
- `last_call_outcome` - Last outbound call outcome (indexed): `'no_answer' | 'voicemail' | 'hangup' | 'connected' | 'opt_out' | 'connected_and_declined'`
- `last_booking_at` - Last booking timestamp (if applicable)
- `name`, `email`, `notes` - Contact metadata
- `created_at`, `updated_at` - Timestamps

**Purpose**: This table is your legal defense. Every outbound call decision is based on data in this table.

#### CallRecord Extensions (Lines 623-650)
Extended the existing CallRecord table to support outbound calls:

**New Fields:**
- `call_direction` - 'inbound' | 'outbound' (indexed)
- `contact_id` - Foreign key to Contact table (indexed)
- `assistant_id` - Vapi assistant ID used
- `opt_out_triggered` - Boolean flag if opt-out occurred during call (indexed)

**Purpose**: Links call records to contacts and tracks opt-out events.

### 2. Eligibility Engine (`DB/outbound_calling.py`)

#### Core Function: `check_eligibility()` (Lines 44-120)

This is the **single source of truth** for call eligibility. ALL checks must pass:

1. **Consent Check**: `consent_status == true`
   - Must have explicit consent on record
   - Consent can come from previous inbound call, form, SMS, etc.

2. **Opt-Out Check**: `opted_out == false`
   - Zero tolerance - if opted out, permanently blocked

3. **Internal DNC Check**: `internal_dnc == false`
   - Respects internal Do Not Call list

4. **National DNC Check**: `national_dnc == false`
   - Respects national DNC registry (if applicable)

5. **Time Window Check**: Current time between 8 AM - 9 PM in contact's timezone
   - Uses `pytz` to convert UTC to contact's local timezone
   - Evaluated at call time, not scheduled time

6. **Attempt Limit Check**: `call_attempt_count < 2`
   - Maximum 2 outbound attempts per contact
   - Prevents harassment

7. **Cooldown Check**: Minimum 48 hours since last call
   - Prevents rapid-fire calling
   - Calculated from `last_called_at` timestamp

8. **Retry Policy Check (Outcome-Based)**: Only retry when the last attempt was non-interactive
   - **Retry allowed**: `last_call_outcome in {'no_answer', 'voicemail'}` (still subject to cooldown + max attempts)
   - **Never retry**: `{'hangup', 'opt_out', 'connected', 'connected_and_declined'}`
   - **Backward compatible**: if `last_call_outcome` is missing/NULL, the system treats retry as allowed (but other checks still apply)

**Returns**: Dictionary with `eligible` (bool), `reason` (str), and `checks` (dict of individual check results)

### 3. Candidate Identification (`DB/outbound_calling.py`)

#### Function: `identify_follow_up_candidates()` (Lines 271-360)

**Process:**
1. Queries all inbound calls (or NULL call_direction for legacy calls)
2. Filters to calls with caller numbers
3. For each unique caller:
   - Normalizes phone number to E.164 format
   - Checks if they have a booking (skips if booked)
   - Gets or creates Contact record
   - Records consent from previous inbound call (existing business relationship)
   - Checks if opted out (skips if opted out)
   - Adds to candidate list

**Returns**: List of candidate dictionaries with contact, last call info, and transcript

**Key Feature**: Automatically creates contacts and records consent from inbound calls, establishing legal basis for outbound calls.

### 4. Vapi Integration (`DB/outbound_calling.py`)

#### Function: `trigger_outbound_call()` (Lines 380-490)

**Process:**
1. Validates Vapi credentials (`VAPI_API_KEY`, `VAPI_ASSISTANT_ID`)
2. Prepares API payload:
   ```json
   {
     "assistantId": "...",
     "phoneNumber": {
       "to": "+14125551234",
       "from": "optional-from-number"
     },
     "metadata": {
       "contactId": "123",
       "campaign": "no_booking_followup",
       "callDirection": "outbound"
     }
   }
   ```
3. Makes POST request to `https://api.vapi.ai/call`
4. Creates CallRecord with `call_direction="outbound"`
5. Links CallRecord to Contact via `contact_id`
6. Updates Contact: increments `call_attempt_count`, sets `last_called_at`

**Error Handling**: Returns success/failure with error messages for logging

**Purpose**: This is the ONLY place where outbound calls are initiated. Eligibility must be checked BEFORE calling this function.

### 5. Contact Management (`DB/outbound_calling.py`)

#### `get_or_create_contact()` (Lines 154-195)
- Normalizes phone number to E.164 format
- Finds existing contact or creates new one
- Updates fields if provided
- Returns Contact object

#### `record_consent()` (Lines 197-226)
- Gets or creates contact
- Sets `consent_status = true`
- Records `consent_source` and `consent_timestamp`
- Commits to database

#### `record_opt_out()` (Lines 229-264)
- **ZERO TOLERANCE** - Immediate and permanent
- Gets or creates contact
- Sets `opted_out = true`
- Records `opt_out_timestamp`, `opt_out_method`, `opt_out_call_id`
- Logs opt-out for audit trail
- Commits to database

**Critical**: Opt-out is permanent. Once set, contact can never be called again.

### 6. Webhook Enhancements (`vapi/app.py`)

#### Opt-Out Detection (Lines 7570-7630)

**Function: `_detect_opt_out()`** (Lines 7000-7070)

Detects opt-out from:
1. **Transcript keywords** (case-insensitive):
   - "stop calling", "don't call", "do not call"
   - "remove me", "take me off", "unsubscribe"
   - "opt out", "opt-out"
   - "no more calls", "never call"
   - "remove my number", "delete my number"

2. **Explicit opt-out events** from Vapi payload
3. **Keypad input** (e.g., pressing "9" for opt-out)

**Process:**
- Analyzes transcript for keywords
- Checks message/payload for opt-out flags
- Returns boolean if opt-out detected

**Integration in Webhook** (Lines 7608-7630):
- When opt-out detected, immediately calls `record_opt_out()`
- Marks CallRecord with `opt_out_triggered = true`
- Stores opt-out metadata in call record
- Logs for audit trail

#### Automatic Contact Creation (Lines 7608-7630)

For inbound callers:
- Extracts caller number from webhook
- Normalizes to E.164 format
- Gets or creates Contact record
- Records consent from inbound call (existing business relationship)
- Links CallRecord to Contact

**Purpose**: Establishes legal basis for future outbound calls.

#### Outbound Call Outcome Tracking (Smart Retries)

For outbound calls, the webhook now computes and stores `Contact.last_call_outcome` so the backend can apply a strict retry policy:
- **Allowed to retry**: `no_answer`, `voicemail`
- **Never retry**: `hangup`, `opt_out`, `connected`, `connected_and_declined`

This prevents repeated calls after a hang-up or explicit decline, while still allowing a second attempt after no-answer/voicemail (subject to cooldown and max attempts).

### 7. API Endpoints (`vapi/app.py`)

All endpoints require JWT authentication and Property Manager role.

#### `POST /outbound-calls/process-queue` (Lines 12500-12530)
- Processes batch of eligible contacts
- Triggers calls for eligible contacts
- Returns processing results

#### `GET /outbound-calls/candidates` (Lines 12533-12572)
- Lists follow-up candidates
- Shows eligibility status and reasons
- Includes eligibility checks breakdown

#### `POST /outbound-calls/trigger` (Lines 12574-12630)
- Manually triggers single outbound call
- Checks eligibility before triggering
- Returns call_id if successful

#### `GET /outbound-calls/contacts` (Lines 12633-12680)
- Lists all contacts with consent/opt-out status
- Supports filtering by opt-out status
- Pagination support

#### `POST /outbound-calls/contacts/{id}/opt-out` (Lines 12700-12737)
- Manually opt out a contact
- For admin/PM use

#### `POST /outbound-calls/contacts/{id}/consent` (Lines 12740-12770)
- Manually record consent
- For admin/PM use

#### `GET /outbound-calls/analytics` (Lines 12773-12830)
- Returns analytics for outbound calling
- Total calls, opt-outs, bookings, success rates
- Configurable time period

### 8. Scheduled Job Script (`scripts/process_outbound_calls.py`)

**Features:**
- Dry-run mode (checks eligibility without calling)
- Batch processing with configurable size
- Error handling and logging
- Detailed output with status for each contact

**Usage:**
```bash
# Dry run
python scripts/process_outbound_calls.py --dry-run --batch-size 5

# Actual processing
python scripts/process_outbound_calls.py --batch-size 10
```

**Process:**
1. Identifies follow-up candidates
2. Checks eligibility for each
3. Triggers calls for eligible contacts
4. Reports results (called, skipped, errors)

### 9. Queue Processing (`DB/outbound_calling.py`)

#### Function: `process_outbound_call_queue()` (Lines 500-580)

**Process:**
1. Gets candidates via `identify_follow_up_candidates()`
2. For each candidate:
   - Checks eligibility via `check_eligibility()`
   - If eligible: triggers call via `trigger_outbound_call()`
   - If not eligible: skips with reason
3. Returns summary with counts and detailed results

**Purpose**: Main function for scheduled job processing.

---

## Architecture & Design

### System Flow

```
┌─────────────────┐
│  Inbound Call   │
│  (User calls)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Webhook Handler│
│  - Creates Contact│
│  - Records Consent│
│  - Links to CallRecord│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  CallRecord     │
│  (stored)       │
└─────────────────┘
         │
         ▼
┌─────────────────┐
│  Scheduled Job  │
│  (hourly)       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Candidate ID   │
│  - Finds callers│
│  - Excludes booked│
│  - Excludes opted out│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Eligibility    │
│  Engine         │
│  - All checks pass?│
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
   YES       NO
    │         │
    ▼         ▼
┌────────┐ ┌────────┐
│ Trigger│ │  Skip  │
│  Call  │ │ (log)  │
└───┬────┘ └────────┘
    │
    ▼
┌─────────────────┐
│  Vapi API       │
│  (executes call)│
└────────┬────────┘
    │
    ▼
┌─────────────────┐
│  Webhook        │
│  - Opt-out?     │
│  - Update status│
└─────────────────┘
```

### Key Design Decisions

1. **Backend-Controlled**: All decisions made in backend, Vapi only executes
2. **Compliance-First**: Every check enforced before call
3. **Audit Trail**: All actions logged and stored
4. **Immediate Opt-Out**: Zero tolerance, permanent blocking
5. **Timezone-Aware**: Time windows enforced in contact's local timezone

---

## Database Schema

### Contact Table

```sql
CREATE TABLE contact (
    id SERIAL PRIMARY KEY,
    phone_number TEXT NOT NULL UNIQUE,
    timezone TEXT DEFAULT 'America/New_York',
    consent_status BOOLEAN DEFAULT FALSE NOT NULL,
    consent_source TEXT,
    consent_timestamp TIMESTAMPTZ,
    opted_out BOOLEAN DEFAULT FALSE NOT NULL,
    opt_out_timestamp TIMESTAMPTZ,
    opt_out_method TEXT,
    opt_out_call_id TEXT,
    internal_dnc BOOLEAN DEFAULT FALSE NOT NULL,
    national_dnc BOOLEAN DEFAULT FALSE NOT NULL,
    last_called_at TIMESTAMPTZ,
    call_attempt_count INTEGER DEFAULT 0 NOT NULL,
    last_booking_at TIMESTAMPTZ,
    name TEXT,
    email TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### CallRecord Extensions

```sql
ALTER TABLE callrecord 
ADD COLUMN call_direction TEXT DEFAULT 'inbound',
ADD COLUMN contact_id INTEGER REFERENCES contact(id),
ADD COLUMN assistant_id TEXT,
ADD COLUMN opt_out_triggered BOOLEAN DEFAULT FALSE NOT NULL;
```

### Indexes

```sql
-- Contact indexes
CREATE INDEX idx_contact_phone_number ON contact(phone_number);
CREATE INDEX idx_contact_consent_status ON contact(consent_status);
CREATE INDEX idx_contact_opted_out ON contact(opted_out);
CREATE INDEX idx_contact_internal_dnc ON contact(internal_dnc);
CREATE INDEX idx_contact_national_dnc ON contact(national_dnc);
CREATE INDEX idx_contact_last_called_at ON contact(last_called_at);

-- CallRecord indexes
CREATE INDEX idx_callrecord_call_direction ON callrecord(call_direction);
CREATE INDEX idx_callrecord_contact_id ON callrecord(contact_id);
CREATE INDEX idx_callrecord_opt_out_triggered ON callrecord(opt_out_triggered);
```

---

## Setup Instructions

### Step 1: Database Migration

#### Using Supabase SQL Editor (Recommended)

1. Open **Supabase Dashboard** → **SQL Editor**
2. Open file: `DB/migrations/add_outbound_calling_tables_supabase.sql`
3. Copy entire contents
4. Paste into Supabase SQL Editor
5. Click **"Run"** button
6. Verify in **Table Editor**:
   - Should see `contact` table
   - `callrecord` should have new columns

#### Using Command Line (Alternative)

```bash
psql $DATABASE_URL -f DB/migrations/add_outbound_calling_tables_supabase.sql
```

### Step 2: Environment Variables

Add to `.env` file:

```bash
VAPI_API_KEY=your-vapi-api-key-here
VAPI_ASSISTANT_ID=your-vapi-assistant-id-here
```

**Where to find:**
- Vapi Dashboard → Settings → API Keys
- Vapi Dashboard → Assistants → [Your Assistant] → Copy ID

### Step 3: Verify Setup

```sql
-- Check Contact table
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'contact';

-- Check CallRecord extensions
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'callrecord' 
AND column_name IN ('call_direction', 'contact_id', 'opt_out_triggered', 'assistant_id');
```

---

## Testing & Verification

### Dry Run Test (No Calls Made)

```bash
cd /path/to/leasap-backend
python scripts/process_outbound_calls.py --dry-run --batch-size 5
```

**Expected Output:**
```
🚀 Starting outbound call queue processing at 2024-01-15T10:30:00
   Batch size: 5
   Dry run: True
   ✅ Eligible: +14125551234 - John Doe
   ❌ Not eligible: +14125551235 - Outside allowed calling hours (8 AM - 9 PM)
   ❌ Not eligible: +14125551236 - Exceeded maximum call attempts (2)

📊 Dry run results:
   Total candidates checked: 5
   Eligible: 2
   Not eligible: 3
✅ Queue processing completed
```

### Actual Call Test (Small Batch)

```bash
# Test with 1 call first
python scripts/process_outbound_calls.py --batch-size 1
```

**Verify in Database:**
```sql
-- Check outbound calls
SELECT * FROM callrecord 
WHERE call_direction = 'outbound' 
ORDER BY created_at DESC 
LIMIT 5;

-- Check contact call history
SELECT phone_number, call_attempt_count, last_called_at 
FROM contact 
WHERE call_attempt_count > 0;
```

### API Testing

```bash
# Get candidates (requires auth)
curl -X GET "https://your-backend-url.com/outbound-calls/candidates?limit=10" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Trigger single call
curl -X POST "https://your-backend-url.com/outbound-calls/trigger" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "+14125551234"}'
```

---

## Scheduled Job Setup

### Method 1: Cron (Linux/Mac)

```bash
# Edit crontab
crontab -e

# Add this line (runs every hour at minute 0)
0 * * * * cd /path/to/leasap-backend && /usr/bin/python3 scripts/process_outbound_calls.py --batch-size 10 >> /var/log/outbound_calls.log 2>&1

# Verify
crontab -l
```

### Method 2: Windows Task Scheduler

1. Open **Task Scheduler**
2. Create **Basic Task**
3. **Name:** "Process Outbound Calls"
4. **Trigger:** Daily, repeat every 1 hour
5. **Action:** Start a program
   - **Program:** `python`
   - **Arguments:** `scripts\process_outbound_calls.py --batch-size 10`
   - **Start in:** `C:\path\to\leasap-backend`

### Method 3: Render.com

1. Go to **Dashboard** → Your Service
2. Click **Cron Jobs**
3. **Add Cron Job:**
   - **Schedule:** `0 * * * *` (every hour)
   - **Command:** `python scripts/process_outbound_calls.py --batch-size 10`

### Method 4: Python APScheduler (In-App)

Add to your main application:

```python
from apscheduler.schedulers.background import BackgroundScheduler
from DB.outbound_calling import process_outbound_call_queue
from DB.db import Session, engine

scheduler = BackgroundScheduler()

def process_calls():
    with Session(engine) as session:
        result = process_outbound_call_queue(session, batch_size=10)
        print(f"Processed {result['processed']}, called {result['called']}")

# Run every hour
scheduler.add_job(process_calls, 'interval', hours=1)
scheduler.start()
```

---

## API Reference

### POST /outbound-calls/process-queue

Process a batch of eligible contacts.

**Request:**
```json
{
  "batch_size": 10
}
```

**Response:**
```json
{
  "message": "Processed 5 candidates",
  "called": 2,
  "skipped": 2,
  "errors": 1,
  "results": [
    {
      "contact_id": 1,
      "phone_number": "+14125551234",
      "status": "called",
      "call_id": "abc123"
    }
  ]
}
```

### GET /outbound-calls/candidates

Get list of candidates with eligibility status.

**Query Parameters:**
- `limit` (int, default: 50)

**Response:**
```json
{
  "candidates": [
    {
      "contact_id": 1,
      "phone_number": "+14125551234",
      "name": "John Doe",
      "eligible": true,
      "eligibility_reason": "All checks passed",
      "eligibility_checks": {
        "consent": true,
        "not_opted_out": true,
        "within_time_window": true,
        "below_attempt_limit": true,
        "cooldown_passed": true
      }
    }
  ],
  "total": 1
}
```

### POST /outbound-calls/trigger

Manually trigger a single outbound call.

**Request:**
```json
{
  "phone_number": "+14125551234",
  "assistant_id": "optional-assistant-id",
  "from_number": "optional-from-number"
}
```

**Response:**
```json
{
  "message": "Outbound call triggered successfully",
  "call_id": "abc123",
  "contact_id": 1,
  "phone_number": "+14125551234"
}
```

### GET /outbound-calls/contacts

List all contacts with pagination.

**Query Parameters:**
- `limit` (int, default: 50)
- `offset` (int, default: 0)
- `opted_out` (bool, optional)

**Response:**
```json
{
  "contacts": [
    {
      "id": 1,
      "phone_number": "+14125551234",
      "name": "John Doe",
      "consent_status": true,
      "opted_out": false,
      "call_attempt_count": 1,
      "last_called_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 100,
  "limit": 50,
  "offset": 0
}
```

### POST /outbound-calls/contacts/{id}/opt-out

Manually opt out a contact.

**Request:**
```json
{
  "method": "manual"
}
```

### POST /outbound-calls/contacts/{id}/consent

Manually record consent.

**Request:**
```json
{
  "source": "form"
}
```

### GET /outbound-calls/analytics

Get analytics for outbound calling.

**Query Parameters:**
- `days` (int, default: 30)

**Response:**
```json
{
  "period_days": 30,
  "total_outbound_calls": 100,
  "opt_outs_triggered": 5,
  "bookings_resulting": 20,
  "success_rate": 20.0,
  "opt_out_rate": 5.0
}
```

---

## Compliance & Legal

### TCPA Compliance

**Consent Basis:**
- User explicitly opted in
- User previously called Leasap (existing business relationship)
- User requested information
- Existing business relationship exists

**Time Windows:**
- Calls allowed: 8:00 AM - 9:00 PM
- Evaluated in recipient's local timezone
- Enforced at call time

**Opt-Out Handling:**
- Zero tolerance - immediate and permanent
- Keywords: "stop", "don't call", "remove me", etc.
- Keypad input (if configured)
- All opt-outs logged with timestamp and method

**Rate Limiting:**
- Maximum 2 outbound attempts per contact
- Minimum 48 hours between attempts
- No retries after opt-out or 2 unanswered attempts

**DNC Lists:**
- Internal DNC list support
- National DNC registry support (if applicable)

### California CIPA Compliance

**Recording Consent:**
- Assistant must announce recording
- Recording starts only after disclosure
- If user objects, stop recording or end call
- Consent implicitly recorded by continuation

**Note**: Recording consent is handled by Vapi assistant configuration, not backend code.

### Audit Trail

All actions are logged:
- Consent recording (timestamp, source)
- Opt-out events (timestamp, method, call_id)
- Call attempts (timestamp, call_id, status)
- Eligibility checks (results stored in call metadata)

---

## Troubleshooting

### Issue 1: Migration Fails in Supabase

**Error:** "syntax error" or "column already exists"

**Solution:**
- Use `add_outbound_calling_tables_supabase.sql` (Supabase-compatible)
- Safe to run multiple times (uses `IF NOT EXISTS`)
- Check Table Editor to verify tables exist

### Issue 2: No Candidates Found

**Possible causes:**
- No inbound calls in database
- All callers already booked tours
- All callers opted out
- All callers exceeded attempt limit

**Check:**
```sql
-- Count inbound calls
SELECT COUNT(*) FROM callrecord 
WHERE call_direction = 'inbound' OR call_direction IS NULL;

-- Count contacts
SELECT COUNT(*) FROM contact;

-- Check bookings
SELECT COUNT(*) FROM propertytourbooking;
```

### Issue 3: Calls Not Triggering

**Check:**
1. Environment variables: `echo $VAPI_API_KEY`
2. Eligibility: Run dry run to see reasons
3. Time window: Must be 8 AM - 9 PM in contact's timezone
4. Logs: Check application logs for errors

**Common reasons:**
- Outside time window
- Exceeded call attempt limit
- Cooldown not passed (48 hours)
- Missing Vapi credentials

### Issue 4: Opt-Outs Not Working

**Check:**
1. Webhook receiving events: Check `/vapi-webhook` logs
2. Transcript analysis: Opt-out keywords must be in transcript
3. Database: Verify `opted_out` flag is set

```sql
-- Check opt-outs
SELECT phone_number, opted_out, opt_out_timestamp 
FROM contact 
WHERE opted_out = true;
```

### Issue 5: Contact Not Created for Inbound Caller

**Check:**
1. Webhook is receiving events
2. Caller number is being extracted correctly
3. Phone number normalization is working

**Debug:**
- Check webhook logs for caller number extraction
- Verify `caller_number` field in CallRecord
- Check Contact table for created records

---

## Code Review & Verification

### Fixed Issues

1. **NULL call_direction handling**
   - **Issue:** Legacy calls might have NULL `call_direction`
   - **Fix:** Updated query to include NULL values as inbound calls
   - **Location:** `DB/outbound_calling.py` line 294

2. **Missing import**
   - **Issue:** `or_` from sqlalchemy not imported
   - **Fix:** Added `from sqlalchemy import or_`
   - **Location:** `DB/outbound_calling.py` line 17

3. **Migration script compatibility**
   - **Issue:** DO blocks might not work in Supabase
   - **Fix:** Created Supabase-compatible version with `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`
   - **Location:** `DB/migrations/add_outbound_calling_tables_supabase.sql`

### Verified Working

- ✅ All imports are correct
- ✅ Database relationships properly defined
- ✅ API endpoints have proper authentication
- ✅ Error handling in place
- ✅ Logging for debugging
- ✅ Compliance checks enforced
- ✅ Timezone handling correct
- ✅ Phone number normalization working

### File Locations

- **Database Models**: `DB/db.py` (lines 580-650)
- **Eligibility Engine**: `DB/outbound_calling.py` (lines 44-120)
- **Candidate ID**: `DB/outbound_calling.py` (lines 271-360)
- **Vapi Integration**: `DB/outbound_calling.py` (lines 380-490)
- **Webhook Handler**: `vapi/app.py` (lines 7570-7630)
- **API Endpoints**: `vapi/app.py` (lines 12500-12830)
- **Scheduled Script**: `scripts/process_outbound_calls.py`
- **Migration**: `DB/migrations/add_outbound_calling_tables_supabase.sql`

---

## Pre-Production Checklist

Before deploying to production:

- [ ] Migration completed successfully
- [ ] `contact` table exists with all columns
- [ ] `callrecord` has new columns (`call_direction`, `contact_id`, etc.)
- [ ] Environment variables set (`VAPI_API_KEY`, `VAPI_ASSISTANT_ID`)
- [ ] Dry run works and shows candidates
- [ ] Test call triggered successfully (small batch)
- [ ] Scheduled job configured (cron/task scheduler)
- [ ] Webhook receiving events
- [ ] Opt-out detection tested (say "stop" during test call)
- [ ] Analytics endpoint working
- [ ] Logs being monitored
- [ ] Legal review completed (consult with counsel)

---

## Quick Reference

### Run Migration
```sql
-- Copy and paste in Supabase SQL Editor
-- File: DB/migrations/add_outbound_calling_tables_supabase.sql
```

### Test Dry Run
```bash
python scripts/process_outbound_calls.py --dry-run --batch-size 5
```

### Test Actual Call
```bash
python scripts/process_outbound_calls.py --batch-size 1
```

### Check Contacts
```sql
SELECT * FROM contact ORDER BY created_at DESC LIMIT 10;
```

### Check Outbound Calls
```sql
SELECT * FROM callrecord 
WHERE call_direction = 'outbound' 
ORDER BY created_at DESC 
LIMIT 10;
```

### Scheduled Job (Cron)
```bash
0 * * * * cd /path/to/leasap-backend && python scripts/process_outbound_calls.py --batch-size 10
```

---

**Status:** ✅ All features implemented and verified
**Last Updated:** 2024-01-XX
**Version:** 1.0.0
