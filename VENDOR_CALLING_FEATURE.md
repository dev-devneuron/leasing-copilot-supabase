# Automated Vendor Calling for Maintenance Requests

## Overview

This feature enables automated vendor calling when tenants submit maintenance requests. The system automatically contacts repair vendors (electrician, plumber, carpenter, HVAC, etc.) linked to properties, collects availability/confirmation, and surfaces results to Property Managers.

## Architecture

### Database Models

1. **Vendor** - Stores vendor information (name, service type, phone, operating hours, etc.)
2. **PropertyVendor** - Links vendors to properties with priority and service type
3. **VendorCallQueue** - Manages call queue for each maintenance request
4. **VendorCallAttempt** - Tracks individual call attempts and outcomes
5. **PropertyVendorSettings** - Property-level settings for auto-calling behavior

### Core Modules

1. **`DB/vendor_matching.py`** - Vendor matching logic based on property, category, priority
2. **`DB/vendor_calling.py`** - Automated calling flow, queue management, retry logic
3. **`vapi/app.py`** - API endpoints for vendor management and calling

## API Endpoints

### Vendor Management

- `POST /vendors` - Create a new vendor
- `GET /vendors` - Get all vendors for PM
- `GET /vendors/{vendor_id}` - Get specific vendor
- `PATCH /vendors/{vendor_id}` - Update vendor
- `DELETE /vendors/{vendor_id}` - Delete vendor (soft delete)

### Property-Vendor Linking

- `POST /properties/{property_id}/vendors` - Link vendor to property
- `GET /properties/{property_id}/vendors` - Get all vendors for property
- `DELETE /properties/{property_id}/vendors/{property_vendor_id}` - Unlink vendor

### Vendor Calling

- `POST /maintenance-requests/{request_id}/start-vendor-calls` - Start automated calling
- `GET /maintenance-requests/{request_id}/vendor-call-status` - Get call status and attempts
- `POST /maintenance-requests/{request_id}/pause-vendor-calls` - Pause calling
- `POST /maintenance-requests/{request_id}/cancel-vendor-calls` - Cancel calling

### Property Settings

- `POST /properties/{property_id}/vendor-settings` - Update auto-calling settings
- `GET /properties/{property_id}/vendor-settings` - Get auto-calling settings

## Workflow

### 1. Pre-Setup (PM Dashboard)

PM configures vendors per property:

```json
POST /vendors
{
  "name": "ABC Plumbing",
  "service_type": "plumber",
  "phone_number": "+14125551234",
  "backup_phone": "+14125551235",
  "email": "contact@abcplumbing.com",
  "operating_hours_start": "09:00",
  "operating_hours_end": "17:00",
  "emergency_available": true,
  "timezone": "America/New_York",
  "notes": "Preferred vendor"
}
```

Link vendor to property:

```json
POST /properties/123/vendors
{
  "vendor_id": 1,
  "service_type": "plumber",
  "priority": 1,
  "notes": "Primary plumber for this property"
}
```

### 2. Tenant Submits Maintenance Request

When a tenant submits a maintenance request via phone/text, the system:
1. Creates the maintenance request
2. Checks if auto-calling is enabled (property settings)
3. If enabled, automatically creates a vendor call queue and starts calling

### 3. Vendor Matching

The system matches vendors based on:
- Property ID
- Issue category (mapped to service type: plumbing → plumber, electrical → electrician, etc.)
- Priority (urgent requests may use emergency vendors)
- Operating hours (respects vendor availability)
- Priority order (1st call, 2nd call, etc.)

### 4. Automated Calling Flow

1. **Queue Creation**: System creates a call queue with vendors in priority order
2. **Call Initiation**: Calls first vendor in queue
3. **Outcome Processing**: 
   - **Accepted**: Vendor confirms availability → Assign to request → Complete queue
   - **Declined**: Vendor not available → Move to next vendor
   - **No Response**: Retry same vendor (up to max retries) → Move to next vendor
4. **Retry Logic**: Configurable retries per vendor with delay between attempts

### 5. PM Dashboard Visibility

PM can view:
- Call queue status
- All call attempts with outcomes
- Vendor responses (availability time, cost estimate, notes)
- Call transcripts and recordings

## VAPI Assistant Configuration

For vendor calls, configure a VAPI assistant with the following script:

### Assistant Script

```
You are calling on behalf of [Property Management Company] regarding a maintenance request.

The issue is: [Issue Description]
Category: [Category]
Priority: [Priority]
Property: [Property Address]
Unit: [Unit Number]
Tenant: [Tenant Name]

Please ask the vendor:
1. Are you available to handle this request?
2. What is the earliest time you can come?
3. What is the estimated cost range? (optional)

Be professional, brief, and collect clear yes/no answers for availability.

If vendor says yes/available → mark as accepted
If vendor says no/not available/declines → mark as declined
If no answer/voicemail → mark as no_response
```

### Key Points

- **No mention of "previous calls" or internal systems** (compliance-safe)
- **Clear availability question** (yes/no)
- **Collect time and cost estimates** (optional)
- **Professional and brief**

### Metadata Structure

When triggering vendor calls, the system passes metadata:

```json
{
  "callContext": {
    "maintenance_request_id": 123,
    "vendor_id": 1,
    "vendor_call_attempt_id": 456,
    "issue_description": "Kitchen sink is leaking",
    "category": "plumbing",
    "priority": "normal",
    "property_address": "123 Main St",
    "tenant_name": "John Smith",
    "tenant_unit": "Apt 3B"
  },
  "vendorCall": true,
  "maintenanceRequestId": 123,
  "vendorId": 1,
  "vendorCallAttemptId": 456
}
```

## Webhook Processing

The webhook handler (`/vapi-webhook`) automatically:
1. Detects vendor calls from metadata (`vendorCall: true`)
2. Extracts outcome from call status and transcript
3. Processes outcome via `handle_vendor_call_outcome()`
4. Updates maintenance request and call queue
5. Moves to next vendor if needed

## Configuration

### Property-Level Settings

```json
POST /properties/{property_id}/vendor-settings
{
  "auto_call_enabled": true,
  "emergency_only": false,
  "call_time_restrictions": {
    "start_hour": 8,
    "end_hour": 21,
    "timezone": "America/New_York"
  }
}
```

### Queue Configuration

- `max_retries_per_vendor`: Default 2
- `retry_delay_minutes`: Default 15

## Status Values

### Maintenance Request
- `vendor_call_status`: `not_started`, `calling`, `vendor_accepted`, `vendor_declined`, `no_response`, `paused`, `cancelled`

### Call Queue
- `status`: `pending`, `calling`, `completed`, `cancelled`, `paused`

### Call Attempt
- `call_status`: `initiated`, `answered`, `declined`, `no_answer`, `voicemail`, `failed`
- `outcome`: `accepted`, `declined`, `no_response`, `voicemail`

## Error Handling

- Vendor calling failures don't block maintenance request creation
- Retry logic handles transient failures
- Fallback to next vendor if current vendor fails
- PM can manually trigger calls if auto-calling fails

## Vendor Opt-Out Management

Vendors can opt out of automated AI calls, similar to contact opt-out functionality.

### Opt-Out Detection

The system automatically detects vendor opt-outs during calls by:
- Listening for opt-out keywords in transcripts ("stop calling", "don't call", "opt out", etc.)
- Detecting explicit opt-out events from VAPI
- Recording opt-out immediately (zero tolerance)

### Opt-Out Fields

Each vendor has:
- `opted_out`: Boolean flag indicating opt-out status
- `opt_out_timestamp`: When opt-out occurred
- `opt_out_method`: How opt-out was detected ('voice', 'keypad', 'sms', 'email', 'manual')
- `opt_out_call_id`: Call ID where opt-out occurred (if applicable)

### API Endpoints

- `POST /vendors/{vendor_id}/opt-out` - Manually opt-out a vendor (PM only)
- `POST /vendors/{vendor_id}/clear-opt-out` - Clear opt-out status (PM only)

### Behavior

- **Opted-out vendors are automatically excluded** from vendor matching and call queues
- Opt-out is **immediate and permanent** until manually cleared by PM
- When a vendor opts out during a call, the system:
  1. Records opt-out in vendor record
  2. Records opt-out in contact record (for consistency)
  3. Skips vendor in future call queues
  4. Logs opt-out details for audit trail

### Example

```json
POST /vendors/1/opt-out
{
  "message": "Vendor opted out successfully",
  "vendor_id": 1,
  "vendor_name": "ABC Plumbing",
  "opted_out": true,
  "opt_out_timestamp": "2024-01-15T10:30:00Z"
}
```

## Compliance

- Respects vendor operating hours
- Time-of-day restrictions configurable per property
- Call logging and audit trail
- No mention of internal systems in calls (compliance-safe)
- **Vendor opt-out support** - vendors can opt out of automated calls
- **Zero-tolerance opt-out** - immediate and permanent until cleared

## VAPI Function Endpoints

All VAPI function endpoints are available at: `https://leasing-copilot-mvp.onrender.com/vapi/vendor/`

### 1. captureVendorResponse
**Endpoint:** `POST /vapi/vendor/capture-response`

Captures vendor's availability, timing, and cost estimate.

**Function:** `captureVendorResponse`

**Required Metadata:**
- `vendorCallAttemptId` - ID of the vendor call attempt

**Response:** Updates vendor call attempt and processes outcome (accepted/declined)

---

### 2. escalateToNextVendor
**Endpoint:** `POST /vapi/vendor/escalate-next`

Triggers when current vendor declines or call fails, moves to next vendor in queue.

**Function:** `escalateToNextVendor`

**Required Metadata:**
- `vendorCallAttemptId` - ID of the vendor call attempt

**Response:** Processes outcome and moves to next vendor if applicable

---

### 3. logVendorCall
**Endpoint:** `POST /vapi/vendor/log-call`

Logs call details for tracking and reporting.

**Function:** `logVendorCall`

**Required Metadata:**
- `vendorCallAttemptId` - ID of the vendor call attempt

**Response:** Updates call attempt with call log data

---

### 4. scheduleVendorCallback
**Endpoint:** `POST /vapi/vendor/schedule-callback`

Schedules a follow-up call with vendor for future availability.

**Function:** `scheduleVendorCallback`

**Required Metadata:**
- `vendorCallAttemptId` - ID of the vendor call attempt

**Required Parameters:**
- `callbackDate` (YYYY-MM-DD)
- `callbackTime` (HH:MM)
- `callbackReason`

**Response:** Stores callback information in call attempt metadata

---

### 5. updateMaintenanceTicket
**Endpoint:** `POST /vapi/vendor/update-ticket`

Updates maintenance ticket with vendor response information.

**Function:** `updateMaintenanceTicket`

**Required Metadata:**
- `maintenanceRequestId` - ID of the maintenance request

**Required Parameters:**
- `vendorStatus` - Current status with vendor

**Response:** Updates maintenance request status and PM notes

---

### 6. checkVendorOperatingHours
**Endpoint:** `POST /vapi/vendor/check-operating-hours`

Verifies if call is within vendor's stated operating hours.

**Function:** `checkVendorOperatingHours`

**Required Metadata:**
- `vendorId` - ID of the vendor

**Response:** Returns whether vendor is currently available and next available call time

---

### 7. validateEmergencyRequest
**Endpoint:** `POST /vapi/vendor/validate-emergency`

Validates and processes emergency maintenance requests.

**Function:** `validateEmergencyRequest`

**Required Metadata:**
- `maintenanceRequestId` - ID of the maintenance request
- `vendorId` (optional) - ID of the vendor

**Required Parameters:**
- `isEmergency` - Whether this is an emergency request

**Response:** Validates emergency status and updates priority if needed

---

### 8. createVendorAssignment
**Endpoint:** `POST /vapi/vendor/create-assignment`

Creates vendor assignment for the maintenance job.

**Function:** `createVendorAssignment`

**Required Metadata:**
- `maintenanceRequestId` - ID of the maintenance request

**Required Parameters:**
- `assignmentStatus` - Status of assignment (proposed/tentative/confirmed/declined)
- `assignedVendorId` - ID of vendor being assigned

**Response:** Creates vendor assignment and completes call queue

---

### 9. sendVendorNotification
**Endpoint:** `POST /vapi/vendor/send-notification`

Sends confirmation/notification to vendor via preferred method.

**Function:** `sendVendorNotification`

**Required Metadata:**
- `vendorId` (optional) - ID of the vendor
- `maintenanceRequestId` (optional) - ID of the maintenance request

**Required Parameters:**
- `notificationType` - Type of notification
- `deliveryMethod` - How to send (email/sms/portal/phone)

**Response:** Logs notification request (actual sending handled by notification service)

---

## Error Handling

All endpoints return VAPI-compatible responses:
- **Success:** `{"results": [{"toolCallId": "...", "result": {"success": true, ...}}]}`
- **Error:** `{"results": [{"toolCallId": "...", "result": {"success": false, "error": "..."}}]}`

If a function fails, the response includes: *"I'm having technical difficulties. Let me have our property manager follow up with you directly."*

## Future Enhancements

1. **Notification System**: SMS/email to tenant and vendor when vendor accepts
2. **Scheduling Integration**: Auto-schedule vendor visits
3. **Cost Tracking**: Track actual vs estimated costs
4. **Vendor Ratings**: Rate vendors based on performance
5. **Multi-language Support**: Support for vendors speaking different languages
