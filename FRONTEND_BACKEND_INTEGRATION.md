# Frontend & Backend Integration Guide

Complete API documentation for integrating the frontend with the Leasap Backend API.

---

## Table of Contents

1. [Authentication](#-authentication)
2. [Demo Booking System](#-demo-booking-system-public)
3. [User Profile](#-user-profile)
4. [Property Manager - Realtor Management](#-property-manager---realtor-management)
5. [Property Management](#-property-management)
6. [Listing Uploads](#-listing-uploads)
7. [Phone Number System](#-phone-number-request--assignment-system)
8. [Call Forwarding Controls](#-call-forwarding-controls-pm--realtor)
9. [Admin Endpoints](#-admin-endpoints-tech-team)

---

## 🔐 Authentication

All endpoints (except `/book-demo`) require JWT authentication. Include the token in the Authorization header:

```
Authorization: Bearer <jwt_token>
```

The token is obtained from Supabase Auth after login.

---

## 🎯 Demo Booking System (Public)

### Book a Demo

**Endpoint:** `POST /book-demo`  
**Auth:** None (Public endpoint)

**Request:**
```json
{
  "name": "John Smith",
  "email": "john@example.com",
  "phone": "+14125551234",
  "company_name": "ABC Properties",  // Optional
  "preferred_date": "2024-01-15",  // Optional: YYYY-MM-DD
  "preferred_time": "10:00 AM",  // Optional
  "timezone": "America/New_York",  // Optional
  "notes": "Interested in property management"  // Optional
}
```

**Response:**
```json
{
  "message": "Thank you for your interest! We've received your demo request and will contact you soon to schedule a time.",
  "demo_request_id": 1,
  "status": "pending",
  "requested_at": "2024-01-15T10:30:00Z"
}
```

**Frontend Implementation:**
```javascript
async function bookDemo(formData) {
  const response = await fetch('/book-demo', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: formData.name,
      email: formData.email,
      phone: formData.phone,
      company_name: formData.companyName || null,
      preferred_date: formData.preferredDate || null,
      preferred_time: formData.preferredTime || null,
      timezone: formData.timezone || null,
      notes: formData.notes || null
    })
  });
  
  if (response.ok) {
    const data = await response.json();
    alert(data.message);
  }
}
```

**UI Requirements:**
- Replace "Sign Up" with "Book a Demo" button
- Form fields: Name, Email, Phone (required), Company, Date, Time, Timezone, Notes (optional)
- Show success message after submission

---

## 👤 User Profile

### Get Current User

**Endpoint:** `GET /user-profile`  
**Auth:** Required

**Response:**
```json
{
  "user": {
    "user_type": "property_manager" | "realtor",
    "id": 1,
    "name": "John Smith",
    "email": "john@example.com",
    "company_name": "ABC Properties"  // Only for property_manager
  }
}
```

---

## 🏢 Property Manager - Realtor Management

### Get Managed Realtors

**Endpoint:** `GET /property-manager/realtors`  
**Auth:** Required (PM only)

**Response:**
```json
{
  "realtors": [
    {
      "id": 1,
      "name": "Sarah Johnson",
      "email": "sarah@example.com",
      "contact": "555-0123",
      "status": "active"
    }
  ]
}
```

### Update Realtor

**Endpoint:** `PATCH /property-manager/realtors/{realtor_id}`  
**Auth:** Required (PM only)

**Request:**
```json
{
  "name": "Sarah Johnson Updated",
  "contact": "555-9999",
  "email": "sarah.new@example.com",
  "password": "newPassword123"  // Optional
}
```

**Response:**
```json
{
  "message": "Realtor updated successfully",
  "realtor_id": 1,
  "updated_fields": ["name", "contact", "email"]
}
```

---

## 🏠 Property Management

### Get Properties

**Endpoint:** `GET /apartments`  
**Auth:** Required

**Response:**
```json
{
  "apartments": [
    {
      "id": 1,
      "address": "123 Main St",
      "price": 250000,
      "bedrooms": 3,
      "bathrooms": 2.5,
      "listing_metadata": { ... }
    }
  ]
}
```

### Update Property

**Endpoint:** `PATCH /properties/{property_id}`  
**Auth:** Required

**Request:**
```json
{
  "price": 250000,
  "bedrooms": 3,
  "bathrooms": 2.5,
  "address": "123 New Address St",
  "features": ["Pool", "Gym"]
}
```

**Response:**
```json
{
  "message": "Property updated successfully",
  "property": { ... }
}
```

### Delete Property

**Endpoint:** `DELETE /properties/{property_id}`  
**Auth:** Required

---

## 📤 Listing Uploads

### Upload Listings (Realtor) — Deprecated

> Realtors can no longer upload listings directly. All inventory must be uploaded by the Property Manager via `/property-manager/upload-listings`, optionally targeting a specific realtor with `assign_to_realtor_id`.

### Upload Listings (Property Manager)

**Endpoint:** `POST /property-manager/upload-listings`  
**Auth:** Required (PM)

**Request:** `multipart/form-data`
- `listing_file`: File (JSON, CSV, or TXT)
- `listing_api_url`: string (optional)
- `assign_to_realtor_id`: int (optional)

**Response:**
```json
{
  "message": "Listings uploaded & embedded",
  "count": 10,
  "source_id": 5
}
```

**Notes:**
- Supports JSON, CSV, and TXT files
- AI-powered parser handles various formats and malformed data
- Listings are automatically embedded for semantic search
- PM uploads default to PM's source (PM owns them)
- PM can assign listings to realtors after upload

### Assign Properties to Realtor

**Endpoint:** `POST /property-manager/assign-properties`  
**Auth:** Required (PM)

**Request:**
```json
{
  "realtor_id": 123,
  "property_ids": [1, 2, 3, 4, 5]
}
```

**Response:**
```json
{
  "message": "Successfully assigned 5 properties to realtor",
  "realtor_id": 123,
  "property_count": 5
}
```

---

## 📞 Phone Number Request & Assignment System

### Overview

1. **Property Managers** request phone numbers via dashboard
2. **Tech Team** purchases and adds numbers to database
3. **Property Managers** assign purchased numbers to themselves or realtors
4. **Chatbot** automatically uses correct data based on assigned number

### 1. Request Phone Number

**Endpoint:** `POST /request-phone-number`  
**Auth:** Required (PM only)

**Request:**
```json
{
  "country_code": "+1",  // Optional
  "area_code": "412",  // Optional
  "notes": "Need number for new realtor"  // Optional
}
```

**Response:**
```json
{
  "message": "Your phone number request has been submitted successfully. A new number will be available in your portal within 24 hours.",
  "request_id": 1,
  "country_code": "+1",
  "area_code": "412",
  "status": "pending",
  "requested_at": "2024-01-15T10:30:00Z"
}
```

### 2. View My Phone Number Requests

**Endpoint:** `GET /my-phone-number-requests`  
**Auth:** Required (PM only)

**Response:**
```json
{
  "requests": [
    {
      "request_id": 1,
      "country_code": "+1",
      "area_code": "412",
      "status": "pending",
      "requested_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

### 3. View Purchased Phone Numbers

**Endpoint:** `GET /purchased-phone-numbers`  
**Auth:** Required (PM only)

**Response:**
```json
{
  "purchased_numbers": [
    {
      "purchased_phone_number_id": 1,
      "phone_number": "+14125551234",
      "status": "available",
      "assigned_to_type": null,
      "assigned_to_id": null
    }
  ],
  "available_for_assignment": [
    {
      "purchased_phone_number_id": 1,
      "phone_number": "+14125551234"
    }
  ],
  "realtors": [
    {
      "realtor_id": 5,
      "name": "Sarah Johnson",
      "email": "sarah@example.com",
      "twilio_number": "+14125551234",
      "forwarding_state": {
        "business_forwarding_enabled": true,
        "after_hours_enabled": false,
        "last_after_hours_update": "2024-01-15T17:00:00Z"
      }
    }
  ]
}
```

### 4. Assign Phone Number

**Endpoint:** `POST /assign-phone-number`  
**Auth:** Required (PM only)

**Assign to Property Manager:**
```json
{
  "purchased_phone_number_id": 1,
  "assign_to_type": "property_manager"
}
```

**Assign to Realtor:**
```json
{
  "purchased_phone_number_id": 1,
  "assign_to_type": "realtor",
  "assign_to_id": 5
}
```

**Response:**
```json
{
  "message": "Phone number +14125551234 has been successfully assigned",
  "purchased_phone_number_id": 1,
  "phone_number": "+14125551234",
  "assigned_to_type": "realtor",
  "assigned_to_id": 5,
  "forwarding_state": {
    "business_forwarding_enabled": false,
    "after_hours_enabled": false,
    "last_after_hours_update": null
  }
}
```

### 5. Unassign Phone Number

**Endpoint:** `POST /unassign-phone-number`  
**Auth:** Required (PM only)

**Request:**
```json
{
  "purchased_phone_number_id": 1
}
```

**Response:**
```json
{
  "message": "Phone number +14125551234 has been unassigned and is now available",
  "purchased_phone_number_id": 1,
  "phone_number": "+14125551234",
  "status": "available"
}
```

**Frontend Implementation:**
```javascript
async function unassignPhoneNumber(purchasedPhoneNumberId) {
  try {
    const response = await fetch('/unassign-phone-number', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        purchased_phone_number_id: purchasedPhoneNumberId
      })
    });
    
    // IMPORTANT: Always parse JSON response - even for errors!
    let data;
    try {
      data = await response.json();
    } catch (parseError) {
      // If response is not JSON, handle it
      const text = await response.text();
      throw new Error(`Server error: ${text || response.statusText}`);
    }
    
    if (response.ok) {
      // Success - data is already parsed
      console.log('Success:', data);
      console.log('Message:', data.message); // This will show the actual message
      alert(data.message); // Display the message properly
      // Refresh the phone numbers list
      loadPurchasedNumbers();
      return data; // Return the parsed data
    } else {
      // Error response - data.detail contains the error message
      const errorMessage = data.detail || data.message || 'Unknown error';
      console.error('Error response:', data);
      alert(`Error: ${errorMessage}`); // Show the actual error message
      throw new Error(errorMessage);
    }
  } catch (error) {
    // Handle network errors or other exceptions
    console.error('Fetch error:', error);
    
    // If error is already a string or has a message, use it
    const errorMessage = error.message || String(error);
    
    // Don't show [object Object] - check if it's an object
    if (typeof error === 'object' && error !== null && !error.message) {
      alert('Failed to unassign phone number. Please check the console for details.');
      console.error('Full error object:', error);
    } else {
      alert(`Failed to unassign phone number: ${errorMessage}`);
    }
    throw error;
  }
}
```

**Common Issues & Debugging:**

1. **If you see `[object Object]` - SIMPLE FIX:**
   
   The issue is that you're trying to display an error object directly. Here's the simplest fix:
   
   ```javascript
   // ❌ WRONG - This causes [object Object]
   catch (error) {
     alert("Error: " + error); // Shows [object Object]
   }
   
   // ✅ CORRECT - Extract the message properly
   catch (error) {
     // If it's a network error, the error object has a message
     if (error.message) {
       alert("Error: " + error.message);
     } 
     // If it's a response error, parse it
     else if (error.response) {
       error.response.json().then(data => {
         alert("Error: " + (data.detail || data.message || "Unknown error"));
       });
     }
     // Fallback
     else {
       alert("Error: " + JSON.stringify(error));
     }
   }
   ```

2. **Simplified Error Handling (Recommended):**
   
   ```javascript
   async function unassignPhoneNumber(purchasedPhoneNumberId) {
     const response = await fetch('/unassign-phone-number', {
       method: 'POST',
       headers: {
         'Authorization': `Bearer ${token}`,
         'Content-Type': 'application/json'
       },
       body: JSON.stringify({
         purchased_phone_number_id: purchasedPhoneNumberId
       })
     });
     
     const data = await response.json();
     
     if (!response.ok) {
       // Error response - FastAPI returns {detail: "error message"}
       const errorMsg = data.detail || data.message || 'Unknown error';
       alert('Error: ' + errorMsg);
       throw new Error(errorMsg);
     }
     
     // Success
     alert(data.message);
     loadPurchasedNumbers();
     return data;
   }
   ```

3. **Check the Network Tab:**
   - Open browser DevTools (F12) → Network tab
   - Make the request
   - Click on the `/unassign-phone-number` request
   - Check the "Response" tab - you should see JSON
   - If you see an error, it will be in format: `{"detail": "error message"}`

**Notes:**
- PMs can unassign numbers from themselves or their realtors
- Unassigning makes the number available for reassignment
- The number is not deleted (only tech team can delete purchased numbers)
- **Important:** Make sure to call `await response.json()` to parse the response, don't display the response object directly

### 6. Get My Phone Number

**Endpoint:** `GET /my-number`  
**Auth:** Required

**Response:**
```json
{
  "twilio_number": "+14125551234",
  "twilio_sid": "PN...",
  "user_type": "property_manager",
  "user_id": 1,
  "forwarding_state": {
    "business_forwarding_enabled": true,
    "business_forwarding_active": true,
    "business_forwarding_confirmed_at": "2024-01-10T15:30:00Z",
    "after_hours_enabled": false,
    "after_hours_active": false,
    "after_hours_last_enabled_at": null,
    "after_hours_last_disabled_at": "2024-02-10T09:05:00Z",
    "last_after_hours_update": "2024-02-10T09:05:00Z",
    "last_forwarding_update": "2024-02-10T09:05:00Z",
    "forwarding_failure_reason": null
  }
}
```

> **Heads-up:** If a legacy PM/realtor already has a purchased number but their profile still shows the “Assign a phone number to unlock forwarding controls” banner, simply call `GET /my-number` once after assignment. The backend now auto-synchronizes the stored Twilio DID from the assigned `purchased_phone_number_id`, so existing users don’t need to be re-saved manually.

Behind the scenes, the backend also scans the `purchased_phone_numbers` table for entries whose `assigned_to_type/assigned_to_id` match the user (even if `purchased_phone_number_id` on the profile is `NULL`) and automatically links it. That means any PM who was assigned a number prior to this release will be brought up-to-date the first time the dashboard hits `GET /my-number` or `GET /call-forwarding-state`.

> **Property Manager fallback:** If tech has added at least one purchased number for a PM but never explicitly assigned it (i.e., it just lives in the PM’s inventory), the backend now auto-promotes the oldest available number to the PM on first load. It updates both the PM record (`purchased_phone_number_id`, `twilio_contact`) and the `PurchasedPhoneNumber` row (`assigned_to_type = property_manager`). So the dashboard only needs to call `GET /my-number`; there’s no extra “assign to myself” step for existing customers.

---

## 📲 Call Forwarding Controls (PM & Realtor)

Property managers and their realtors keep their SIM-based carrier numbers, but we still need to drive calls into VAPI (Twilio bot) when certain conditions are met. Since carriers expose forwarding only via GSM/USSD dial codes, the frontend simply opens the dialer with pre-filled codes. Your backend responsibilities are:

1. **Expose each PM/realtor’s `bot_number` (Twilio DID)** via `GET /my-number` (self) and existing management endpoints (for realtors that a PM manages). The backend derives this strictly from `purchased_phone_numbers` (the official callbot pool)—it never falls back to whatever Twilio number was stored historically on the profile—so you can trust it’s the bot we provisioned.
2. **Persist forwarding state** per user so the UI can show which modes are “enabled.” Suggested schema additions:
   - `business_forwarding_enabled` (boolean, default `false`, set to `true` after the PM confirms one-time setup)
   - `after_hours_enabled` (boolean, toggled daily)
   - `last_after_hours_update` (timestamp, optional, helps with UX hints)
3. **Provide a lightweight state update endpoint**:

   ```
   PATCH /call-forwarding-state
   {
     "after_hours_enabled": true,   // or false
     "business_forwarding_enabled": true // optional future use
   }
   ```

   - Auth required.
   - Applies to the authenticated PM, or to a specific realtor if `realtor_id` is provided and owned by that PM.
   - The endpoint should only change database flags; carriers are controlled entirely by the dial codes below.

### Carrier Compatibility Testing

Use the built-in matrix to render QA checklists:

```http
GET /call-forwarding-carriers
```

```json
{
  "carriers": ["AT&T", "Verizon", "T-Mobile", "Mint", "Metro", "Google Fi"]
}
```

Each time we onboard a new PM, run through this list (or as many carriers as the team uses) to verify the GSM codes perform as expected. Record discrepancies so Support can coach PMs with carrier-specific notes.

### Frontend Button Mapping

| Button Label | Purpose | Dial Sequence | When Used | Backend UI Flag |
|--------------|---------|--------------|-----------|-----------------|
| Enable Business Hours Forwarding (One-Time Setup) | Conditional “no-answer” forwarding so missed calls route to the bot after 25s | `**61*${botNumber}**25#` | Run once per PM/realtor | Sets `business_forwarding_enabled = true` |
| Enable After-Hours Mode (Forward All Calls) | Every incoming call goes straight to the bot | `**21*${botNumber}#` | Daily at 5pm (or when manually enabling) | Sets `after_hours_enabled = true` |
| Disable After-Hours Mode (Back to Normal) | Remove full forwarding while keeping conditional forwarding | `##21#` | Daily at 9am (or when resuming live phone) | Sets `after_hours_enabled = false` |

> `botNumber` is the Twilio DID returned by the backend. Include the leading `+1`. Example: `+18885551234`.

### API Reference

**Get forwarding state (self or managed realtor)**  
`GET /call-forwarding-state?realtor_id=<optional>`  
Auth required. If `realtor_id` is omitted, the authenticated user’s state is returned. `realtor_id` is only allowed for property managers and must belong to them.

**Response**
```json
{
  "user_type": "property_manager",
  "user_id": 12,
  "twilio_number": "+18885551234",
  "twilio_sid": "PNabc...",
  "forwarding_state": {
    "business_forwarding_enabled": true,
    "business_forwarding_active": true,
    "business_forwarding_confirmed_at": "2024-01-10T15:30:00Z",
    "after_hours_enabled": false,
    "after_hours_active": false,
    "after_hours_last_enabled_at": null,
    "after_hours_last_disabled_at": "2024-02-10T09:05:00Z",
    "last_after_hours_update": "2024-02-10T09:05:00Z",
    "last_forwarding_update": "2024-02-10T09:05:00Z",
    "forwarding_failure_reason": null
  }
}
```

**Update forwarding state**  
`PATCH /call-forwarding-state`

**Request**
```json
{
  "after_hours_enabled": true,
  "business_forwarding_enabled": true,
  "realtor_id": 99,          // Optional; only PMs can set this
  "notes": "Enabled after-hours from dashboard",
  "confirmation_status": "success",  // "success" | "failure" | "pending"
  "failure_reason": "Carrier busy tone" // Only when confirmation_status = "failure"
}
```

At least one of `after_hours_enabled`, `business_forwarding_enabled`, or `confirmation_status` must be present. When `realtor_id` is set, the PM must own that realtor. The endpoint simply flips database flags; carriers are controlled solely via dial codes. Setting `confirmation_status` lets the backend know whether the carrier confirmed or rejected the dial code so Support can react (and optionally triggers an internal SMS alert if configured).

**Response**
```json
{
  "message": "Forwarding state updated",
  "user_type": "realtor",
  "user_id": 99,
  "forwarding_state": {
    "business_forwarding_enabled": true,
    "business_forwarding_active": true,
    "business_forwarding_confirmed_at": "2024-02-01T22:05:00Z",
    "after_hours_enabled": true,
    "after_hours_active": true,
    "after_hours_last_enabled_at": "2024-02-01T22:05:00Z",
    "after_hours_last_disabled_at": "2024-02-01T09:00:00Z",
    "last_after_hours_update": "2024-02-01T22:05:00Z",
    "last_forwarding_update": "2024-02-01T22:05:00Z",
    "forwarding_failure_reason": null
  }
}
```

> **Rate limiting:** Backend enforces a default limit of `CALL_FORWARDING_RATE_LIMIT_PER_HOUR` (10 by default) updates per user per hour. If the UI receives HTTP 429, show a friendly “you’ve toggled too many times, please wait” toast.

> **Error handling:** When `confirmation_status` is `"failure"`, include a human-readable `failure_reason`. The backend stores it and returns it in `forwarding_state.forwarding_failure_reason` so the UI can surface troubleshooting tips.

### Example Workflow

1. **Initial setup:** PM opens dashboard, sees “Business Hours Forwarding” card. Backend reports `business_forwarding_enabled = false`, so the button is highlighted. When the PM taps the button, the frontend:
   - Generates `**61*${botNumber}**25#`
   - Opens the device dialer via `tel:` link (no backend call here)
   - Once the PM confirms success, the frontend calls `PATCH /call-forwarding-state` with `{ "business_forwarding_enabled": true }`

2. **Daily after-hours toggle:**
   - At 5pm, PM presses “Enable After-Hours Mode.” Frontend triggers `tel:**21*${botNumber}#`, then `PATCH /call-forwarding-state` with `{ "after_hours_enabled": true }`.
   - At 9am, PM uses “Disable After-Hours Mode.” Frontend triggers `tel:##21#`, then `PATCH /call-forwarding-state` with `{ "after_hours_enabled": false }`.

3. **Realtor assignment:** When a PM assigns a bot number to a realtor (`POST /assign-phone-number`), store the `bot_number` relationship and initialize the forwarding flags for that realtor. The PM-facing UI should query both the realtor profile and the `forwarding_state` so the PM can walk their realtor through the exact same buttons/codes.

### Implementation Tips

- No carrier APIs are required; do not attempt to automate the GSM codes server-side.
- `bot_number` should mirror the value Twilio/VAPI expects for inbound routing. If you support regional numbers, return the exact E.164 string to avoid formatting errors.
- Consider adding an audit log table (`call_forwarding_events`) capturing the user, action (`business_enable`, `after_hours_on`, `after_hours_off`), timestamp, and optional notes so Support can troubleshoot.
- The backend already persists these audit entries in `call_forwarding_events`, so Support can filter by `target_user_type`/`target_user_id` to confirm when a PM toggled a mode.
- For mobile apps, use the native deep link format (`tel:${encodedCode}`); for web, `<a href="tel:**61*+18885551234**25#">`.
- Frontend should display clear success instructions (e.g., “Tap call, wait for carrier confirmation tone, then return to the app”). Backend can return these copy strings as part of `/call-forwarding-state` if you want server-driven UX.
- **Security guardrails:** The backend validates Twilio numbers (E.164 format) before responding, so disable the three dialer buttons if `twilio_number` is missing. Rate limit errors (HTTP 429) indicate the PM toggled more than the configured hourly allowance—surface a non-blocking alert and retry later.
- **User feedback:** After the dial code completes, call `PATCH /call-forwarding-state` with `confirmation_status`. For failures, pass `failure_reason` and show `forwarding_state.forwarding_failure_reason` in the UI until the next success. Success responses may trigger an internal SMS alert for Support, so you don’t need to page them manually.
- **Legacy data:** When an assigned number exists but `twilio_number` is still null (older records), the backend auto-fills it by reading the linked `purchased_phone_number`. Triggering `GET /my-number` (or any forwarding endpoint) will hydrate the value, so the “Assign a phone number” prompt should disappear without manual DB edits.

---

## 🔧 Admin Endpoints (Tech Team)

**Note:** These endpoints should be protected with admin authentication in production. Tech team can use curl, Postman, or any HTTP client.

### Add Purchased Phone Number

**Endpoint:** `POST /admin/add-purchased-number`

**Request:**
```json
{
  "property_manager_id": 1,
  "phone_number": "+14125551234",
  "twilio_sid": "PN1234567890abcdef",  // Optional
  "vapi_phone_number_id": "vapi_123",  // Optional
  "notes": "Purchased from Twilio"  // Optional
}
```

**Response:**
```json
{
  "message": "Phone number +14125551234 added successfully and is now available for assignment",
  "purchased_phone_number_id": 1,
  "phone_number": "+14125551234",
  "status": "available",
  "property_manager_id": 1,
  "pm_name": "John Smith",
  "pm_email": "john@example.com"
}
```

**Example (curl):**
```bash
curl -X POST https://your-backend-url.com/admin/add-purchased-number \
  -H "Content-Type: application/json" \
  -d '{
    "property_manager_id": 1,
    "phone_number": "+14125551234",
    "twilio_sid": "PN1234567890abcdef",
    "notes": "Purchased from Twilio"
  }'
```

### View All Phone Number Requests

**Endpoint:** `GET /admin/all-phone-number-requests?status=pending`

**Query Parameters:**
- `status` (optional): `pending`, `fulfilled`, `cancelled`

### View All Purchased Numbers

**Endpoint:** `GET /admin/all-purchased-numbers?property_manager_id=1&status=available`

**Query Parameters:**
- `property_manager_id` (optional)
- `status` (optional): `available`, `assigned`, `inactive`

### View All Demo Requests

**Endpoint:** `GET /demo-requests?status=pending`

**Query Parameters:**
- `status` (optional): `pending`, `scheduled`, `completed`, `cancelled`, `converted`

### Update Demo Request

**Endpoint:** `PATCH /demo-requests/{demo_request_id}`

**Request:**
```json
{
  "status": "scheduled",
  "scheduled_at": "2024-01-20T10:00:00Z",
  "completed_at": "2024-01-20T11:00:00Z",
  "converted_to_pm_id": 5,
  "notes": "Demo completed successfully"
}
```

---

## 📝 Key Points

- ✅ **Authentication:** All endpoints (except `/book-demo`) require JWT token
- ✅ **Data Isolation:** PMs only see their data, Realtors only see assigned data
- ✅ **AI-Powered Uploads:** Supports JSON, CSV, TXT with intelligent parsing
- ✅ **Phone Number System:** PM requests → Tech adds → PM assigns
- ✅ **Demo System:** Public booking, admin manages, converts to PM accounts

---

## 🔗 Base URL

**Production:** `https://your-backend-url.com`  
**Development:** `http://localhost:8000`

---

For detailed tech team instructions, see `TECH_TEAM_PHONE_NUMBER_GUIDE.md`
