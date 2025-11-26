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
9. [Call Records & Transcripts](#-call-records--transcripts)
10. [Maintenance Request Logging](#-maintenance-request-logging)
11. [Property Tour Booking System](#-property-tour-booking-system)
12. [Admin Endpoints](#-admin-endpoints-tech-team)

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
    "company_name": "ABC Properties",  // Only for property_manager
    "timezone": "America/New_York",
    "calendar_preferences": {
      "defaultSlotLengthMins": 30,
      "workingHours": {
        "start": "09:00",
        "end": "17:00"
      }
    }
  }
}
```

**Note:** The user profile now includes calendar preferences (timezone, working hours, slot length) for easy access in the dashboard.

### Get Calendar Preferences

**Endpoint:** `GET /api/users/{user_id}/calendar-preferences?user_type={user_type}`  
**Auth:** Required

**Response:**
```json
{
  "timezone": "America/New_York",
  "defaultSlotLengthMins": 30,
  "workingHours": {
    "start": "09:00",
    "end": "17:00"
  }
}
```

### Update Calendar Preferences

**Endpoint:** `PATCH /api/users/{user_id}/calendar-preferences?user_type={user_type}`  
**Auth:** Required

**Request Body (all fields optional - only send fields you want to update):**
```json
{
  "timezone": "America/New_York",  // Optional: IANA timezone string (e.g., "America/New_York", "America/Los_Angeles")
  "default_slot_length_mins": 30,  // Optional: Integer between 15-120
  "working_hours_start": "09:00",  // Optional: HH:MM format (24-hour)
  "working_hours_end": "17:00",    // Optional: HH:MM format (24-hour)
  "working_days": [0, 1, 2, 3, 4]  // Optional: Array of day numbers (0=Monday, 1=Tuesday, ..., 6=Sunday). Default: [0,1,2,3,4] (Mon-Fri)
}
```

**Response:**
```json
{
  "message": "Calendar preferences updated successfully",
  "preferences": {
    "timezone": "America/New_York",
    "defaultSlotLengthMins": 30,
    "workingHours": {
      "start": "09:00",
      "end": "17:00"
    }
  }
}
```

**Error Responses:**
- `400 Bad Request`: Invalid time format, slot length out of range, or end time before start time
- `403 Forbidden`: User can only update their own preferences
- `404 Not Found`: User not found

**Example Usage:**
```javascript
// Update working hours only
async function updateWorkingHours(userId, userType, start, end) {
  const response = await fetch(
    `/api/users/${userId}/calendar-preferences?user_type=${userType}`,
    {
      method: 'PATCH',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        working_hours_start: start,  // e.g., "09:00"
        working_hours_end: end        // e.g., "17:00"
      })
    }
  );
  
  if (response.ok) {
    const data = await response.json();
    console.log('Updated preferences:', data.preferences);
    return data.preferences;
  } else {
    const error = await response.json();
    throw new Error(error.detail);
  }
}

// Update timezone only
async function updateTimezone(userId, userType, timezone) {
  const response = await fetch(
    `/api/users/${userId}/calendar-preferences?user_type=${userType}`,
    {
      method: 'PATCH',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ timezone })
    }
  );
  return response.json();
}

// Update working days (e.g., Monday-Friday = [0,1,2,3,4], All week = [0,1,2,3,4,5,6])
async function updateWorkingDays(userId, userType, days) {
  // days should be an array like [0, 1, 2, 3, 4] for Monday-Friday
  // 0=Monday, 1=Tuesday, 2=Wednesday, 3=Thursday, 4=Friday, 5=Saturday, 6=Sunday
  const response = await fetch(
    `/api/users/${userId}/calendar-preferences?user_type=${userType}`,
    {
      method: 'PATCH',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ working_days: days })
    }
  );
  
  if (response.ok) {
    const data = await response.json();
    return data.preferences;
  } else {
    const error = await response.json();
    throw new Error(error.detail);
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

> **Important:** The backend automatically finds assigned bot numbers by:
> 1. Checking the user's `purchased_phone_number_id` field
> 2. Searching `purchased_phone_numbers` for entries where `assigned_to_type`/`assigned_to_id` matches the user
> 3. For PMs only: Auto-promoting the oldest unassigned number from their inventory if none is explicitly assigned
>
> **Troubleshooting "No Number Assigned":**
> - If a PM has assigned themselves a number via `/assign-phone-number` but `/my-number` still returns 404, check:
>   1. The number's `property_manager_id` must match the PM's ID (numbers can only be assigned from the PM's own inventory)
>   2. The number's `assigned_to_type` should be `"property_manager"` (case-insensitive matching handles variations)
>   3. The number's `assigned_to_id` must equal the PM's `property_manager_id`
> - The backend now handles case variations in `assigned_to_type` (e.g., "Property Manager", "property_manager", "PROPERTY_MANAGER")
> - If the issue persists, check backend logs for debug output showing what numbers were found in the inventory

> **Property Manager fallback:** If tech has added at least one purchased number for a PM but never explicitly assigned it (i.e., it just lives in the PM’s inventory), the backend now auto-promotes the oldest available number to the PM on first load. It updates both the PM record (`purchased_phone_number_id`, `twilio_contact`) and the `PurchasedPhoneNumber` row (`assigned_to_type = property_manager`). So the dashboard only needs to call `GET /my-number`; there’s no extra “assign to myself” step for existing customers.

---

## 📲 Call Forwarding Controls (PM & Realtor)

Property managers and their realtors keep their SIM-based carrier numbers, but we still need to drive calls into VAPI (Twilio bot) when certain conditions are met. **Different carriers use different dial codes**, so the backend now provides carrier-specific codes based on the user's configured carrier.

### Important: Carrier-Specific Implementation

**Each carrier has different forwarding codes!** The backend automatically generates the correct codes based on the user's carrier setting. The frontend must:

1. **Collect the user's carrier** during onboarding or settings
2. **Use the carrier-specific codes** returned by the backend
3. **Handle carrier limitations** (e.g., Verizon doesn't support 25-second forwarding)

### Supported Carriers & Capabilities

| Carrier | Forward ALL | 25-Second Forwarding | Code Format |
|---------|-------------|---------------------|-------------|
| **AT&T** | ✅ Yes | ✅ Yes | GSM (`**21*`, `**61*`) |
| **T-Mobile** | ✅ Yes | ✅ Yes | GSM (`**21*`, `**61*`) |
| **Mint** | ✅ Yes | ✅ Yes | GSM (`**21*`, `**61*`) |
| **Metro** | ✅ Yes | ✅ Yes | GSM (`**21*`, `**61*`) |
| **Consumer Cellular** | ✅ Yes | ✅ Yes | GSM (`**21*`, `**61*`) |
| **Ultra Mobile** | ✅ Yes | ✅ Yes | GSM (`**21*`, `**61*`) |
| **Verizon** | ✅ Yes | ❌ No | `*72` / `*73` |
| **Xfinity Mobile** | ✅ Yes | ❌ No (default ring time only) | `*72` / `*73` / `*71` |
| **Google Fi** | ⚠️ App Only | ❌ No | Must use Google Fi app |

### Carrier Code Reference

#### GSM Carriers (AT&T, T-Mobile, Mint, Metro, Consumer Cellular, Ultra Mobile)

**Forward ALL calls:**
- Activate: `**21*+14123882328#`
- Deactivate: `##21#`
- Check status: `*#21#`

**Forward after 25 seconds (no-answer):**
- Activate: `**61*+14123882328**25#`
- Deactivate: `##61#`
- Check status: `*#61#`

#### Verizon

**Forward ALL calls:**
- Activate: `*72 14123882328` (no + sign, space after *72)
- Deactivate: `*73`
- Check status: Not available

**25-second forwarding:** ❌ Not supported

#### Xfinity Mobile

**Forward ALL calls:**
- Activate: `*72 14123882328` (no + sign, space after *72)
- Deactivate: `*73`
- Check status: Not available

**No-answer forwarding (default ring time, no custom seconds):**
- Activate: `*71 14123882328`
- Deactivate: `*73`
- Check status: Not available

#### Google Fi

**Forward ALL calls:**
- ⚠️ Must configure through Google Fi app or website
- No dial codes supported

**25-second forwarding:** ❌ Not supported

### API Reference

**Get forwarding state (self or managed realtor)**  
`GET /call-forwarding-state?realtor_id=<optional>`  
Auth required. If `realtor_id` is omitted, the authenticated user's state is returned. `realtor_id` is only allowed for property managers and must belong to them.

**Response (when number is assigned):**
```json
{
  "user_type": "property_manager",
  "user_id": 12,
  "twilio_number": "+18885551234",
  "twilio_sid": "PNabc...",
  "forwarding_state": {
    "carrier": "AT&T",
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
  },
  "forwarding_codes": {
    "carrier": "AT&T",
    "carrier_type": "gsm",
    "supports_25_second_forwarding": true,
    "forward_all": {
      "activate": "**21*+18885551234#",
      "deactivate": "##21#",
      "check": "*#21#"
    },
    "forward_no_answer": {
      "activate": "**61*+18885551234**25#",
      "deactivate": "##61#",
      "check": "*#61#",
      "supports_custom_seconds": true
    }
  }
}
```

**Response (when realtor has no number assigned):**
```json
{
  "user_type": "realtor",
  "user_id": 96,
  "twilio_number": null,
  "twilio_sid": null,
  "message": "No phone number assigned to this realtor. Please assign a number first.",
  "forwarding_state": {
    "carrier": null,
    "business_forwarding_enabled": false,
    "after_hours_enabled": false,
    ...
  },
  "forwarding_codes": {
    "carrier": "AT&T",
    "carrier_type": "gsm",
    "supports_25_second_forwarding": true,
    "forward_all": {
      "activate": null,
      "deactivate": null,
      "check": null
    },
    "forward_no_answer": {
      "activate": null,
      "deactivate": null,
      "check": null,
      "supports_custom_seconds": true
    }
  }
}
```

**Important:** 
- If `twilio_number` is `null`, the realtor has no number assigned
- The backend will **never** return the PM's number when querying for a realtor's forwarding state
- Frontend should check for `twilio_number === null` and show "No number assigned" message
- Disable forwarding controls when `twilio_number` is `null`

**Example Response for Verizon (no 25-second support):**
```json
{
  "forwarding_codes": {
    "carrier": "Verizon",
    "carrier_type": "verizon",
    "supports_25_second_forwarding": false,
    "forward_all": {
      "activate": "*72 18885551234",
      "deactivate": "*73",
      "check": null
    },
    "forward_no_answer": {
      "activate": null,
      "deactivate": null,
      "check": null,
      "supports_custom_seconds": false
    }
  }
}
```

**Example Response for Google Fi (app-only):**
```json
{
  "forwarding_codes": {
    "carrier": "Google Fi",
    "carrier_type": "google_fi",
    "supports_25_second_forwarding": false,
    "forward_all": {
      "activate": "app_only",
      "instructions": "Use Google Fi app or website to set up call forwarding",
      "deactivate": "app_only",
      "check": "app_only"
    },
    "forward_no_answer": {
      "activate": null,
      "deactivate": null,
      "check": null,
      "supports_custom_seconds": false
    }
  }
}
```

**Update forwarding state**  
`PATCH /call-forwarding-state`

**Request**
```json
{
  "after_hours_enabled": true,        // Optional
  "business_forwarding_enabled": true, // Optional
  "carrier": "AT&T",                  // Optional; update user's carrier (can be updated independently)
  "realtor_id": 99,                   // Optional; only PMs can set this
  "notes": "Enabled after-hours from dashboard", // Optional
  "confirmation_status": "success",   // Optional: "success" | "failure" | "pending"
  "failure_reason": "Carrier busy tone" // Optional; only when confirmation_status = "failure"
}
```

**Important:** At least one of `after_hours_enabled`, `business_forwarding_enabled`, `carrier`, or `confirmation_status` must be present. You can update just the `carrier` field without providing any other fields. When `realtor_id` is set, the PM must own that realtor. The endpoint updates database flags and carrier setting; carriers are controlled via dial codes returned in the response.

**Example: Update carrier only**
```json
{
  "carrier": "Verizon"
}
```

**Response**
```json
{
  "message": "Forwarding state updated",
  "user_type": "realtor",
  "user_id": 99,
  "forwarding_state": {
    "carrier": "AT&T",
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
  },
  "forwarding_codes": {
    "carrier": "AT&T",
    "carrier_type": "gsm",
    "supports_25_second_forwarding": true,
    "forward_all": {
      "activate": "**21*+18885551234#",
      "deactivate": "##21#",
      "check": "*#21#"
    },
    "forward_no_answer": {
      "activate": "**61*+18885551234**25#",
      "deactivate": "##61#",
      "check": "*#61#",
      "supports_custom_seconds": true
    }
  }
}
```

**Get supported carriers**  
`GET /call-forwarding-carriers`

Returns list of supported carriers and their capabilities.

**Response**
```json
{
  "carriers": [
    "AT&T",
    "T-Mobile",
    "Mint",
    "Metro",
    "Verizon",
    "Xfinity Mobile",
    "Google Fi",
    "Consumer Cellular",
    "Ultra Mobile"
  ],
  "carrier_details": [
    {
      "name": "AT&T",
      "type": "gsm",
      "supports_forward_all": true,
      "supports_25_second_forwarding": true,
      "requires_app": false,
      "notes": ""
    },
    {
      "name": "Verizon",
      "type": "verizon",
      "supports_forward_all": true,
      "supports_25_second_forwarding": false,
      "requires_app": false,
      "notes": "Only supports unconditional forwarding (*72). 25-second forwarding not available."
    },
    {
      "name": "Google Fi",
      "type": "google_fi",
      "supports_forward_all": false,
      "supports_25_second_forwarding": false,
      "requires_app": true,
      "notes": ""
    }
  ]
}
```

> **Rate limiting:** Backend enforces a default limit of `CALL_FORWARDING_RATE_LIMIT_PER_HOUR` (10 by default) updates per user per hour. If the UI receives HTTP 429, show a friendly “you’ve toggled too many times, please wait” toast.

> **Error handling:** When `confirmation_status` is `"failure"`, include a human-readable `failure_reason`. The backend stores it and returns it in `forwarding_state.forwarding_failure_reason` so the UI can surface troubleshooting tips.

### Frontend Implementation Guide

#### 1. Carrier Selection Workflow

**IMPORTANT: Carrier selection should be the FIRST step before showing any forwarding controls.**

##### Step 1: Check if carrier is already set

When the user opens the call forwarding section, first check if they have a carrier configured:

```javascript
// Get forwarding state to check if carrier is set
async function getForwardingState() {
  const response = await fetch('/call-forwarding-state', {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  const data = await response.json();
  return data;
}

// On page load / component mount
async function initializeCallForwarding() {
  const state = await getForwardingState();
  
  // Check if carrier is not set
  if (!state.forwarding_state.carrier) {
    // Show carrier selection modal/screen FIRST
    showCarrierSelectionModal();
    return; // Don't show forwarding controls yet
  }
  
  // Carrier is set - show forwarding controls based on carrier capabilities
  showForwardingControls(state.forwarding_codes);
}
```

##### Step 2: Carrier Selection (First Time / Onboarding)

**When carrier is `null` or not set:**
- Show a carrier selection screen/modal BEFORE showing forwarding controls
- This should be the FIRST thing the user sees in the call forwarding section
- Use the carrier list from `/call-forwarding-carriers` endpoint

```javascript
// Get list of supported carriers
async function getSupportedCarriers() {
  const response = await fetch('/call-forwarding-carriers', {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  const data = await response.json();
  return data.carrier_details; // Use this to populate a dropdown
}

// Show carrier selection modal
async function showCarrierSelectionModal() {
  const carriers = await getSupportedCarriers();
  
  // Display carrier selection UI
  // Show list of carriers with their capabilities:
  // - "AT&T" - Supports all features
  // - "Verizon" - No 25-second forwarding
  // - "Google Fi" - App-only setup
  // etc.
  
  // When user selects a carrier:
  await updateCarrier(selectedCarrier);
  
  // After carrier is set, refresh and show forwarding controls
  const state = await getForwardingState();
  showForwardingControls(state.forwarding_codes);
}

// Update user's carrier
async function updateCarrier(carrier) {
  const response = await fetch('/call-forwarding-state', {
    method: 'PATCH',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ carrier: carrier })
  });
  return await response.json();
}
```

##### Step 3: Show UI Based on Carrier

**After carrier is selected:**
- Show forwarding controls based on carrier capabilities
- Use `forwarding_codes.supports_25_second_forwarding` to show/hide features
- Use `forwarding_codes.forward_all.activate` to check if it's "app_only"

```javascript
function showForwardingControls(forwardingCodes) {
  // Check carrier capabilities
  const supports25Second = forwardingCodes.supports_25_second_forwarding;
  const isAppOnly = forwardingCodes.forward_all.activate === "app_only";
  
  // Show/hide UI elements based on carrier
  if (isAppOnly) {
    // Google Fi - show app instructions, hide dial code buttons
    showAppInstructions(forwardingCodes.forward_all.instructions);
  } else {
    // Show dial code buttons
    if (supports25Second) {
      // Show "Business Hours Forwarding" button (25-second)
      showBusinessHoursButton(forwardingCodes.forward_no_answer.activate);
    } else {
      // Hide "Business Hours Forwarding" button
      // Show message: "Your carrier (Verizon) doesn't support 25-second forwarding"
      showCarrierLimitationMessage();
    }
    
    // Show "After Hours Forwarding" button (forward all)
    showAfterHoursButton(forwardingCodes.forward_all.activate);
  }
}
```

##### Step 4: Change Carrier (Settings)

**For users who already have a carrier set:**
- Don't show carrier selection on every login
- Provide a "Change Carrier" option in settings/preferences
- When changed, refresh forwarding codes and update UI

```javascript
// In settings/preferences section
async function changeCarrier() {
  // Show carrier selection modal again
  const carriers = await getSupportedCarriers();
  const selectedCarrier = await showCarrierSelectionModal();
  
  // Update carrier
  await updateCarrier(selectedCarrier);
  
  // Refresh forwarding state and codes
  const state = await getForwardingState();
  
  // Update UI with new carrier's capabilities
  showForwardingControls(state.forwarding_codes);
  
  // Show success message
  showNotification("Carrier updated successfully. Forwarding codes have been updated.");
}
```

##### Complete Flow Summary

1. **First Visit (No Carrier Set):**
   ```
   User opens Call Forwarding → Carrier Selection Modal → User selects carrier → 
   Backend updates carrier → Show forwarding controls based on carrier
   ```

2. **Subsequent Visits (Carrier Already Set):**
   ```
   User opens Call Forwarding → Check carrier (already set) → 
   Show forwarding controls immediately → Option to change carrier in settings
   ```

3. **Changing Carrier:**
   ```
   User clicks "Change Carrier" in settings → Carrier Selection Modal → 
   User selects new carrier → Backend updates → Refresh UI with new codes
   ```

#### 2. Using Carrier-Specific Codes

**Always use codes from the backend response**, never hardcode them:

```javascript
// Get forwarding state with carrier-specific codes
async function getForwardingState() {
  const response = await fetch('/call-forwarding-state', {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  const data = await response.json();
  
  // Use the codes from response.forwarding_codes
  const codes = data.forwarding_codes;
  
  // Check if carrier supports 25-second forwarding
  if (!codes.supports_25_second_forwarding) {
    // Show warning: "Your carrier (Verizon) doesn't support 25-second forwarding"
  }
  
  // For Google Fi, show app instructions
  if (codes.forward_all.activate === "app_only") {
    // Show: "Please configure forwarding in Google Fi app"
    return;
  }
  
  return codes;
}

// Enable business hours forwarding (25-second)
function enableBusinessHoursForwarding(codes) {
  if (!codes.forward_no_answer.activate) {
    alert("Your carrier doesn't support 25-second forwarding");
    return;
  }
  
  // Use the code from backend
  const dialCode = codes.forward_no_answer.activate;
  window.location.href = `tel:${dialCode}`;
  
  // After user confirms, update state
  updateForwardingState({ business_forwarding_enabled: true });
}

// Enable after-hours forwarding (forward all)
function enableAfterHoursForwarding(codes) {
  if (codes.forward_all.activate === "app_only") {
    alert("Please configure forwarding in Google Fi app or website");
    return;
  }
  
  const dialCode = codes.forward_all.activate;
  window.location.href = `tel:${dialCode}`;
  
  // After user confirms, update state
  updateForwardingState({ after_hours_enabled: true });
}

// Disable after-hours forwarding
function disableAfterHoursForwarding(codes) {
  const dialCode = codes.forward_all.deactivate;
  window.location.href = `tel:${dialCode}`;
  
  updateForwardingState({ after_hours_enabled: false });
}
```

#### 3. UI Considerations

**Carrier-specific UI:**

- **If carrier is not set:** Show carrier selection dropdown before enabling forwarding
- **If carrier doesn't support 25-second forwarding (Verizon, Xfinity):** 
  - Disable or hide "Business Hours Forwarding" button
  - Show message: "Your carrier (Verizon) only supports forwarding all calls, not 25-second forwarding"
- **If carrier is Google Fi:**
  - Show instructions: "Configure forwarding in Google Fi app: Settings → Calls → Call forwarding"
  - Don't show dial code buttons
- **For GSM carriers (AT&T, T-Mobile, etc.):**
  - Show both buttons (Business Hours + After Hours)
  - Use codes from `forwarding_codes.forward_no_answer.activate` and `forwarding_codes.forward_all.activate`

### Example Workflow

1. **Initial setup:**
   - PM opens dashboard, sees "Call Forwarding" section
   - If `carrier` is null, show carrier selection dropdown
   - PM selects "AT&T" → Frontend calls `PATCH /call-forwarding-state` with `{ "carrier": "AT&T" }`
   - Backend returns `forwarding_codes` with AT&T-specific codes
   - PM taps "Enable Business Hours Forwarding" → Frontend uses `forwarding_codes.forward_no_answer.activate` (`**61*+18885551234**25#`)
   - Opens dialer via `tel:**61*+18885551234**25#`
   - After PM confirms success, frontend calls `PATCH /call-forwarding-state` with `{ "business_forwarding_enabled": true, "confirmation_status": "success" }`

2. **Daily after-hours toggle:**
   - At 5pm, PM presses "Enable After-Hours Mode"
   - Frontend uses `forwarding_codes.forward_all.activate` from latest state
   - For AT&T: `tel:**21*+18885551234#`
   - For Verizon: `tel:*72 18885551234` (note: no +, space after *72)
   - After confirmation, calls `PATCH /call-forwarding-state` with `{ "after_hours_enabled": true, "confirmation_status": "success" }`
   - At 9am, PM uses "Disable After-Hours Mode" → Uses `forwarding_codes.forward_all.deactivate`

3. **Carrier limitations:**
   - If PM has Verizon and tries to enable 25-second forwarding, show: "Verizon doesn't support 25-second forwarding. Only unconditional forwarding is available."
   - If PM has Google Fi, show app instructions instead of dial codes

### Implementation Tips

- **Carrier selection is the FIRST step:** Always check if `forwarding_state.carrier` is `null` before showing forwarding controls. If `null`, show carrier selection modal first.
- **Don't ask for carrier on every login:** Once carrier is set, don't prompt again. Only show carrier selection if `carrier === null`.
- **Provide carrier change option:** Add a "Change Carrier" button in settings/preferences for users who want to update their carrier later.
- **Always use carrier-specific codes from the backend** - Never hardcode dial codes in the frontend. The backend generates the correct codes based on the user's carrier.
- **Handle carrier limitations gracefully:**
  - Check `forwarding_codes.supports_25_second_forwarding` before showing "Business Hours Forwarding" button
  - For Google Fi, show app instructions instead of dial codes
  - For Verizon/Xfinity, explain that only unconditional forwarding is available
- **Number formatting:** The backend handles number formatting automatically. GSM carriers get `+1` prefix, Verizon/Xfinity get numbers without `+` and with spaces.
- **No carrier APIs required:** Do not attempt to automate the dial codes server-side. The frontend opens the dialer, user executes the code, then confirms success.
- **Audit logging:** The backend persists all forwarding events in `call_forwarding_events` table, including carrier information and dial codes used.
- **Mobile vs Web:** 
  - Mobile apps: Use native deep link `tel:${code}`
  - Web: Use `<a href="tel:${code}">` (works on mobile browsers)
- **User instructions:** Display clear instructions:
  - "Tap the button to open your dialer"
  - "Wait for carrier confirmation tone (usually 3 beeps)"
  - "Return to the app and confirm success"
- **Error handling:** 
  - If `confirmation_status = "failure"`, show `forwarding_failure_reason` to the user
  - Common issues: "Carrier busy", "Invalid code", "Carrier not responding"
  - For Google Fi, remind users to use the app
- **Rate limiting:** Backend enforces 10 updates per hour per user. Show friendly message if HTTP 429 is received.
- **UI State Management:**
  - Store carrier in component state after first selection
  - Check `forwarding_state.carrier` on component mount
  - If carrier exists, load forwarding controls immediately
  - If carrier is `null`, show selection modal first

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

## 📞 Call Records & Transcripts

VAPI automatically sends call events (transcripts, recordings, call status) to our webhook endpoint. The backend stores these in the database and provides endpoints for PMs and Realtors to view their call history.

### Webhook Endpoints (VAPI → Backend)

**Primary Endpoint:** `POST /vapi-webhook` (with hyphen)  
**Alternative Endpoint:** `POST /vapi/webhook` (with slash)  
**Auth:** None (Public endpoints, called by VAPI)

**Important Notes:**
- VAPI sends **multiple webhook events** during a call (status updates, function calls, etc.)
- **Only the final `end-of-call-report` event contains the transcript** in `message.artifact.messages`
- The backend automatically skips non-transcript events and only processes end-of-call-report
- **Audio recordings are NOT sent in webhooks** - the backend automatically fetches them from VAPI API
- The backend fetches recording URLs from VAPI API when a call ends

**Event Types Handled:**
- `End Of Call Report` - **Final transcript when call ends** (sent to `/vapi-webhook`, contains transcript in `artifact.messages`)
- `Status Update`, `Conversation Update`, `Speech Update` - Intermediate events (skipped, no transcript)
- `transcript.created` - Real-time transcript chunks during the call (if sent to alternative endpoint)
- `call.ended` - Call completion event
- `recording.ready` - Audio recording ready (if sent, though typically not)
- `call.started` - Call initiation event

**Note:** VAPI uses "End Of Call Report" (with spaces and capitals) as the event type name. The backend detects this by checking if the type contains "end", "call", and "report" (case-insensitive).

**Backend Behavior:**
- Creates/updates call records in the database
- Links calls to the correct PM/Realtor based on the Twilio DID
- Stores transcripts from webhooks
- **Automatically fetches recording URLs from VAPI API** when call ends (recordings not in webhooks)
- Handles phone number resolution from `phoneNumberId` if needed
- Extracts transcript from `message.artifact.messages` array
- Combines transcript with summary from `message.analysis.summary`

**End-of-Call-Report Payload Structure:**
```json
{
  "message": {
    "type": "end-of-call-report",
    "timestamp": 1763495432536,
    "artifact": {
      "messages": [
        {
          "role": "user" | "bot" | "assistant",
          "message": "Message text",
          "time": 1763495278084,
          "secondsFromStart": 0
        }
      ]
    },
    "analysis": {
      "summary": "Call summary text",
      "successEvaluation": "true"
    }
  }
}
```

**Note:** Configure the webhook URL `https://leasing-copilot-mvp.onrender.com/vapi-webhook` in your VAPI dashboard settings.

### Get Call Records

**Endpoint:** `GET /call-records?limit=50&offset=0`  
**Auth:** Required

**Query Parameters:**
- `limit` (optional): Number of records to return (default: 50, max: 100)
- `offset` (optional): Pagination offset (default: 0)

**Response:**
```json
{
  "call_records": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "call_id": "vapi_call_123",
      "realtor_number": "+14125551234",
      "recording_url": "https://storage.vapi.ai/recordings/abc123.mp3",
      "transcript": "Full conversation transcript...",
      "call_duration": 180,
      "call_status": "ended",
      "caller_number": "+15551234567",
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:33:00Z"
    }
  ],
  "total": 25,
  "limit": 50,
  "offset": 0
}
```

**Data Isolation:**
- **Property Managers:** See all calls for their own number AND all their realtors' numbers
- **Realtors:** See only calls for their assigned number

### Get Call Record Details

**Endpoint:** `GET /call-records/{call_id}`  
**Auth:** Required

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "call_id": "vapi_call_123",
  "realtor_number": "+14125551234",
  "recording_url": "https://storage.vapi.ai/recordings/abc123.mp3",
  "transcript": "Full conversation transcript...",
  "live_transcript_chunks": [
    "Hello, I'm interested in...",
    "Can you tell me about...",
    "What's the rent for..."
  ],
  "call_duration": 180,
  "call_status": "ended",
  "caller_number": "+15551234567",
  "metadata": {
    "last_event_type": "call.ended",
    "last_event_at": "2024-01-15T10:33:00Z"
  },
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:33:00Z"
}
```

### Delete Call Record / Assets

**Endpoint:** `DELETE /call-records/{call_id}?hard_delete=false`  
**Auth:** Required

- Default (`hard_delete=false`): removes transcript, live transcript chunks, and recording URL while keeping the row for auditing.
- `hard_delete=true`: permanently deletes the row (irreversible).

**⚠️ IMPORTANT: Use `call_id` NOT `id`**

The `call_id` parameter must be the **`call_id` field** from the GET response (string), NOT the `id` field (UUID).

**Correct:**
- Use `call_id` from response: `"call_id": "vapi_call_123"` → `/call-records/vapi_call_123`

**Wrong:**
- Don't use `id` from response: `"id": "550e8400-e29b-41d4-a716-446655440000"` ❌

**Responses**

Soft delete (default):
```json
{
  "message": "Call transcript and recording removed",
  "call_id": "vapi_call_123",
  "hard_delete": false
}
```

Hard delete:
```json
{
  "message": "Call record permanently deleted",
  "call_id": "vapi_call_123",
  "hard_delete": true
}
```

**Error Responses:**

If you use the wrong field (UUID `id` instead of `call_id`):
```json
{
  "detail": "Invalid call_id: '550e8400-e29b-41d4-a716-446655440000' appears to be a database UUID. Please use the 'call_id' field from the GET /call-records response, not the 'id' field. The correct call_id for this record is: 'vapi_call_123'"
}
```

If call record not found:
```json
{
  "detail": "Call record not found with call_id: 'invalid_id'. Make sure you're using the 'call_id' field from GET /call-records response."
}
```

**UI Guidance**
- Present two destructive actions ("Remove transcript & audio" vs. "Delete record") with confirmation dialogs.
- After a soft delete, refresh the list so the row remains but transcript/recording columns are empty; hard deletes remove the row entirely.
- Backend already enforces ownership (PMs manage their own + realtors' calls; Realtors only their own), so surface a toast if API returns 403.
- **Always use the `call_id` field from the GET response, never the `id` field.**
- URL encode the `call_id` if it contains special characters before using it in the DELETE request.

**Frontend Implementation:**
```javascript
// Remove transcript & audio (soft delete)
async function removeCallContent(callRecord) {
  // IMPORTANT: Use call_id, not id
  const callId = callRecord.call_id; // ✅ Correct
  // const callId = callRecord.id; // ❌ WRONG - This is a UUID, not the call_id
  
  // URL encode the call_id in case it has special characters
  const encodedCallId = encodeURIComponent(callId);
  
  const response = await fetch(`/call-records/${encodedCallId}?hard_delete=false`, {
    method: 'DELETE',
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
  
  if (response.ok) {
    const data = await response.json();
    // Success - refresh the call records list
    // The call record will still exist but transcript/recording will be null
    refreshCallRecords();
    return data;
  } else {
    const errorData = await response.json();
    const errorMsg = errorData.detail || 'Failed to remove call content';
    console.error('Delete error:', errorMsg);
    alert(errorMsg);
    throw new Error(errorMsg);
  }
}

// Delete record entirely (hard delete)
async function deleteCallRecord(callRecord) {
  if (!confirm('Are you sure you want to permanently delete this call record? This cannot be undone.')) {
    return;
  }
  
  // IMPORTANT: Use call_id, not id
  const callId = callRecord.call_id; // ✅ Correct
  // const callId = callRecord.id; // ❌ WRONG
  
  // URL encode the call_id
  const encodedCallId = encodeURIComponent(callId);
  
  const response = await fetch(`/call-records/${encodedCallId}?hard_delete=true`, {
    method: 'DELETE',
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
  
  if (response.ok) {
    const data = await response.json();
    // Success - refresh the call records list
    // The call record will be completely removed
    refreshCallRecords();
    return data;
  } else {
    const errorData = await response.json();
    const errorMsg = errorData.detail || 'Failed to delete call record';
    console.error('Delete error:', errorMsg);
    alert(errorMsg);
    throw new Error(errorMsg);
  }
}

// Example usage in a React component:
function CallRecordRow({ callRecord }) {
  return (
    <tr>
      <td>{callRecord.call_id}</td>
      <td>{callRecord.caller_number}</td>
      <td>
        <button onClick={() => removeCallContent(callRecord)}>
          Remove Transcript & Audio
        </button>
        <button onClick={() => deleteCallRecord(callRecord)}>
          Delete Record
        </button>
      </td>
    </tr>
  );
}
```

**Common Mistakes to Avoid:**
1. ❌ Using `callRecord.id` (UUID) instead of `callRecord.call_id` (string)
2. ❌ Not URL encoding the call_id if it contains special characters
3. ❌ Using the wrong field name from the response object

**Frontend Implementation:**
```javascript
// Get call records list
async function getCallRecords(limit = 50, offset = 0) {
  const response = await fetch(`/call-records?limit=${limit}&offset=${offset}`, {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
  
  if (response.ok) {
    const data = await response.json();
    return data;
  }
  throw new Error('Failed to fetch call records');
}

// Get specific call details
async function getCallRecordDetail(callId) {
  const response = await fetch(`/call-records/${callId}`, {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
  
  if (response.ok) {
    const data = await response.json();
    return data;
  }
  throw new Error('Failed to fetch call record');
}

// Play recording
function playRecording(recordingUrl) {
  // Use HTML5 audio player or download link
  const audio = new Audio(recordingUrl);
  audio.play();
}

// Download recording
function downloadRecording(recordingUrl, callId) {
  const link = document.createElement('a');
  link.href = recordingUrl;
  link.download = `call-${callId}.mp3`;
  link.click();
}
```

**UI Requirements:**
- Display call records in a table/list with:
  - Caller number
  - Date/time
  - Duration
  - Status (ended, started, failed)
  - Actions: View transcript, Play recording, Download recording
- For PMs: Show which realtor's number received the call
- Pagination controls for large call histories
- Search/filter by date range, caller number, or realtor

---

## 🔧 Maintenance Request Logging

### Overview

Tenants can call or text the AI bot to submit maintenance or repair requests. The workflow is:

1. **Bot asks for tenant info** (name, phone, email)
2. **Bot calls lookup endpoint** to verify tenant and get unit/apartment info
3. **Bot confirms with user** (shows name and unit number)
4. **Bot collects issue description** and submits maintenance request

### VAPI Bot Integration - Two-Step Process

#### Step 1: Lookup Tenant (NEW)

**Endpoint:** `POST /lookup_tenant/`  
**Auth:** None (Public endpoint, called by VAPI)

This endpoint is called FIRST when the bot collects tenant information. It verifies the tenant exists and returns their name and unit number for confirmation.

**VAPI Function Tool Definition:**

```json
{
  "type": "function",
  "function": {
    "name": "lookupTenant",
    "description": "Lookup tenant information by name, phone, or email. Use this to verify tenant identity and get their unit/apartment number before submitting a maintenance request.",
    "parameters": {
      "type": "object",
      "properties": {
        "tenant_name": {
          "type": "string",
          "description": "Tenant's name"
        },
        "tenant_phone": {
          "type": "string",
          "description": "Tenant's phone number"
        },
        "tenant_email": {
          "type": "string",
          "description": "Tenant's email address"
        }
      }
    }
  }
}
```

**Response Format:**

```json
{
  "results": [{
    "toolCallId": "...",
    "result": {
      "found": true,
      "tenant_name": "John Smith",
      "unit_number": "Apt 3B",
      "property_address": "123 Main St, City, State",
      "tenant_id": 1,
      "property_id": 10,
      "message": "Found tenant: John Smith in unit Apt 3B"
    }
  }]
}
```

If tenant not found:
```json
{
  "results": [{
    "toolCallId": "...",
    "result": {
      "found": false,
      "message": "Tenant not found. Please verify your information or contact your property manager."
    }
  }]
}
```

#### Step 2: Submit Maintenance Request

**Endpoint:** `POST /submit_maintenance_request/`  
**Auth:** None (Public endpoint, called by VAPI)

This endpoint is called AFTER tenant verification to actually submit the maintenance request. The bot should use the `submitMaintenanceRequest` function tool.

**VAPI Function Tool Definition:**

Add this function to your VAPI assistant configuration:

```json
{
  "type": "function",
  "function": {
    "name": "submitMaintenanceRequest",
    "description": "Submit a maintenance or repair request for a tenant's property. Use this when a tenant reports an issue that needs to be fixed.",
    "parameters": {
      "type": "object",
      "properties": {
        "issue_description": {
          "type": "string",
          "description": "Detailed description of the maintenance issue or problem"
        },
        "category": {
          "type": "string",
          "description": "Category of the issue (e.g., plumbing, electrical, appliance, heating, other)",
          "enum": ["plumbing", "electrical", "appliance", "heating", "hvac", "other"]
        },
        "location": {
          "type": "string",
          "description": "Specific location in the property (e.g., Kitchen, Bathroom, Bedroom 2)"
        },
        "priority": {
          "type": "string",
          "description": "Priority level of the issue",
          "enum": ["low", "normal", "high", "urgent"],
          "default": "normal"
        },
        "tenant_name": {
          "type": "string",
          "description": "Tenant's name (if not already identified)"
        },
        "tenant_phone": {
          "type": "string",
          "description": "Tenant's phone number (if not already identified)"
        },
        "tenant_email": {
          "type": "string",
          "description": "Tenant's email address (if not already identified)"
        }
      },
      "required": ["issue_description"]
    }
  }
}
```

**Response:**

Success:
```json
{
  "results": [{
    "toolCallId": "...",
    "result": {
      "success": true,
      "message": "I've submitted your maintenance request for 123 Main St. Your request ID is 42. Your property manager will be notified and should respond soon.",
      "maintenance_request_id": 42,
      "property_address": "123 Main St",
      "status": "pending"
    }
  }]
}
```

Error (tenant not found):
```json
{
  "results": [{
    "toolCallId": "...",
    "result": {
      "success": false,
      "error": "I couldn't find your tenant record in our system. Please contact your property manager directly to register your information.",
      "tenant_not_found": true
    }
  }]
}
```

### Dashboard Endpoints (PM & Realtor)

#### Get Maintenance Requests

**Endpoint:** `GET /maintenance-requests?status=pending&limit=50&offset=0`  
**Auth:** Required

**Query Parameters:**
- `status` (optional): Filter by status (`pending`, `in_progress`, `completed`, `cancelled`)
- `limit` (optional): Number of results (default: 50, max: 100)
- `offset` (optional): Pagination offset (default: 0)

**Response:**
```json
{
  "maintenance_requests": [
    {
      "maintenance_request_id": 1,
      "tenant_id": 5,
      "tenant_name": "John Smith",
      "tenant_phone": "+14125551234",
      "tenant_email": "john@example.com",
      "property_id": 10,
      "property_address": "123 Main St, Apt 3B",
      "issue_description": "Kitchen sink is leaking",
      "priority": "normal",
      "status": "pending",
      "category": "plumbing",
      "location": "Kitchen",
      "submitted_via": "phone",
      "submitted_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:30:00Z",
      "completed_at": null,
      "assigned_to_realtor_id": null,
      "assigned_to_realtor_name": null,
      "pm_notes": null,
      "resolution_notes": null
    }
  ],
  "total": 25,
  "limit": 50,
  "offset": 0
}
```

**Data Isolation:**
- **Property Managers:** See all maintenance requests for their properties
- **Realtors:** See maintenance requests assigned to them OR for properties they manage

#### Get Maintenance Request Details

**Endpoint:** `GET /maintenance-requests/{request_id}`  
**Auth:** Required

**Response:**
```json
{
  "maintenance_request_id": 1,
  "tenant_id": 5,
  "tenant_name": "John Smith",
  "tenant_phone": "+14125551234",
  "tenant_email": "john@example.com",
  "tenant_unit_number": "Apt 3B",
  "property_id": 10,
  "property_address": "123 Main St, Apt 3B",
  "issue_description": "Kitchen sink is leaking",
  "priority": "normal",
  "status": "pending",
  "category": "plumbing",
  "location": "Kitchen",
  "submitted_via": "phone",
  "vapi_call_id": "vapi_call_123",
  "call_transcript": "Tenant: My kitchen sink is leaking...",
  "submitted_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z",
  "completed_at": null,
  "assigned_to_realtor_id": null,
  "assigned_to_realtor_name": null,
  "pm_notes": null,
  "resolution_notes": null
}
```

#### Update Maintenance Request

**Endpoint:** `PATCH /maintenance-requests/{request_id}`  
**Auth:** Required

**Request:**
```json
{
  "status": "in_progress",
  "priority": "high",
  "assigned_to_realtor_id": 5,
  "pm_notes": "Assigned to plumber",
  "category": "plumbing",
  "location": "Kitchen"
}
```

**Response:**
```json
{
  "message": "Maintenance request updated successfully",
  "maintenance_request_id": 1,
  "status": "in_progress"
}
```

**Field Permissions:**
- **Property Managers:** Can update all fields (status, priority, assignment, notes, category, location)
- **Realtors:** Can only update status and resolution_notes for assigned requests

**Valid Values:**
- `status`: `pending`, `in_progress`, `completed`, `cancelled`
- `priority`: `low`, `normal`, `high`, `urgent`

#### Delete Maintenance Request

**Endpoint:** `DELETE /maintenance-requests/{request_id}`  
**Auth:** Required

**Permissions:**
- **Property Managers:** Can delete any maintenance request for their properties
- **Realtors:** Can delete maintenance requests assigned to them OR for properties they manage

**Response:**
```json
{
  "message": "Maintenance request deleted successfully",
  "maintenance_request_id": 1
}
```

**Error Responses:**

If maintenance request not found:
```json
{
  "detail": "Maintenance request not found"
}
```

If user doesn't have permission:
```json
{
  "detail": "You can only delete maintenance requests for your properties"
}
```

**Note:** This is a hard delete - the request is permanently removed from the database. Use with caution.

**Frontend Implementation:**
```javascript
// Delete maintenance request
async function deleteMaintenanceRequest(requestId) {
  if (!confirm('Are you sure you want to delete this maintenance request? This action cannot be undone.')) {
    return;
  }
  
  const response = await fetch(`/maintenance-requests/${requestId}`, {
    method: 'DELETE',
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
  
  if (response.ok) {
    const data = await response.json();
    // Success - refresh the maintenance requests list
    refreshMaintenanceRequests();
    return data;
  } else {
    const errorData = await response.json();
    const errorMsg = errorData.detail || 'Failed to delete maintenance request';
    alert(errorMsg);
    throw new Error(errorMsg);
  }
}
```

**Frontend Implementation:**
```javascript
// Get maintenance requests
async function getMaintenanceRequests(status = null, limit = 50, offset = 0) {
  const params = new URLSearchParams({ limit, offset });
  if (status) params.append('status', status);
  
  const response = await fetch(`/maintenance-requests?${params}`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  return await response.json();
}

// Update maintenance request
async function updateMaintenanceRequest(requestId, updateData) {
  const response = await fetch(`/maintenance-requests/${requestId}`, {
    method: 'PATCH',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(updateData)
  });
  return await response.json();
}
```

**UI Requirements:**
- Display maintenance requests in a table/list with:
  - Tenant name and contact info
  - Property address
  - Issue description
  - Priority (with color coding: red=urgent, orange=high, yellow=normal, gray=low)
  - Status (with badges: pending, in_progress, completed, cancelled)
  - Submitted date/time
  - Actions: View details, Update status, Assign to realtor, Add notes
- Filter by status (pending, in_progress, completed, cancelled)
- Sort by submitted date (newest first)
- For PMs: Show assignment options (assign to realtor)
- For Realtors: Show only assigned requests or requests for their properties

### Tenant Management

**Important:** When a tenant is created, the property's `listing_status` is automatically updated to **"Rented"** to mark it as unavailable. When a tenant is marked as inactive (moved out), the property status is automatically updated back to **"Available"** (if no other active tenants).

#### Create Tenant

**Endpoint:** `POST /tenants`  
**Auth:** Required (PM only)

**Request:**
```json
{
  "name": "John Smith",
  "property_id": 10,
  "phone_number": "+14125551234",
  "email": "john@example.com",
  "realtor_id": 5,
  "unit_number": "Apt 3B",
  "lease_start_date": "2024-01-01",
  "lease_end_date": "2024-12-31",
  "notes": "First-time renter"
}
```

**Response:**
```json
{
  "message": "Tenant created successfully and property marked as Rented",
  "tenant": {
    "tenant_id": 1,
    "name": "John Smith",
    "phone_number": "+14125551234",
    "email": "john@example.com",
    "property_id": 10,
    "property_address": "123 Main St",
    "realtor_id": 5,
    "unit_number": "Apt 3B",
    "lease_start_date": "2024-01-01",
    "lease_end_date": "2024-12-31",
    "is_active": true
  }
}
```

**Notes:**
- Property status is automatically set to "Rented" when tenant is created
- If `realtor_id` is provided, it must belong to the PM's managed realtors
- Property must belong to the PM (via Source)
- Property cannot have another active tenant

#### Get Tenants

**Endpoint:** `GET /tenants?property_id=10&is_active=true`  
**Auth:** Required

**Query Parameters:**
- `property_id` (optional): Filter by property
- `is_active` (optional): Filter by active status (true/false)

**Response:**
```json
{
  "tenants": [
    {
      "tenant_id": 1,
      "name": "John Smith",
      "phone_number": "+14125551234",
      "email": "john@example.com",
      "property_id": 10,
      "property_address": "123 Main St",
      "property_manager_id": 1,
      "realtor_id": 5,
      "unit_number": "Apt 3B",
      "lease_start_date": "2024-01-01",
      "lease_end_date": "2024-12-31",
      "is_active": true,
      "notes": "First-time renter",
      "created_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

**Data Isolation:**
- **Property Managers:** See all tenants for their properties
- **Realtors:** See tenants for properties they manage OR tenants they helped rent

#### Update Tenant

**Endpoint:** `PATCH /tenants/{tenant_id}`  
**Auth:** Required

**Request:**
```json
{
  "is_active": false,
  "lease_end_date": "2024-12-31",
  "notes": "Tenant moved out"
}
```

**Response:**
```json
{
  "message": "Tenant updated successfully",
  "tenant_id": 1,
  "is_active": false
}
```

**Important:** When `is_active` is set to `false` (tenant moved out), the property status is automatically updated back to "Available" (if no other active tenants exist).

**Tenant Record Fields:**
- `name`: Tenant's full name (required)
- `phone_number`: Phone number in E.164 format (e.g., +14125551234)
- `email`: Email address (optional but recommended)
- `property_id`: ID of the property/apartment they rent (required)
- `property_manager_id`: ID of the PM who manages the property (required)
- `realtor_id`: ID of the realtor who helped rent the property (optional)
- `unit_number`: Unit/apartment number (optional, e.g., "Apt 3B")
- `lease_start_date`: When the lease started (optional, YYYY-MM-DD)
- `lease_end_date`: When the lease ends (optional, YYYY-MM-DD)
- `is_active`: Whether tenant is currently active (default: true)
- `notes`: Additional notes (optional)

**Tenant Identification (for maintenance requests):**
The bot identifies tenants by:
1. **Phone number** (primary method - from caller ID)
2. **Email** (if provided during the call)
3. **Name** (if phone/email not available, partial match)

---

## 🏠 Property Tour Booking System

### Overview

The property tour booking system allows tenants to schedule property tours via VAPI AI or through the dashboard. The system manages availability, approval workflows, and notifications.

**Key Features:**
- VAPI integration for automated booking requests
- In-app calendar management (no external calendars required)
- Approval workflow (bookings start as "pending")
- Conflict detection and prevention
- SMS notifications for booking lifecycle events
- Property assignment to realtors with audit trail

### VAPI Integration Endpoints

**These endpoints are designed for VAPI to call (no authentication required):**

#### 1. Search Properties (REUSE EXISTING `searchApartments` TOOL)

**✅ VAPI Already Has This Tool:** `searchApartments`  
**Endpoint:** `POST /search_apartments/`  
**VAPI Tool Name:** `searchApartments`

**What VAPI sends:**
```json
{
  "query": "Looking for a 2 bed apartment in Mountain View CA under $2000"
}
```

**What Backend returns (ENHANCED with booking info):**
```json
{
  "results": [{
    "toolCallId": "...",
    "result": [
      {
        // Original listing data
        "id": 123,
        "address": "123 Main St, Apt 3B",
        "bedrooms": 2,
        "bathrooms": 1.5,
        "price": 1800,
        "square_feet": 1200,
        "property_type": "Apartment",
        "features": ["Parking", "Laundry"],
        
        // NEW: Booking-related fields (automatically added)
        "property_id": 123,
        "listing_status": "available",  // "available" | "rented" | "offline"
        "is_available_for_tours": true,  // true if listing_status === "available"
        "assigned_to": {
          "user_id": 5,
          "user_type": "realtor",
          "name": "Sarah Johnson",
          "phone": "+14125551234",
          "email": "sarah@example.com"
        },
        "availability": {
          "hasAvailability": true,
          "nextAvailableSlot": {
            "startAt": "2025-12-01T16:00:00Z",
            "endAt": "2025-12-01T16:30:00Z"
          },
          "totalSlots": 15
        }
      }
    ]
  }]
}
```

**VAPI Action:** 
- Check `listing_status === "available"` or `is_available_for_tours === true` before offering booking
- Use `availability.hasAvailability` to know if time slots exist
- If `availability.hasAvailability === false`, inform user that property is available but no tour slots are currently open
- If `listing_status === "rented"`, inform user that property is no longer available

**Important:** The existing `searchApartments` tool now automatically includes booking availability information. No need to create a new tool or endpoint!

**Example VAPI Response from `searchApartments`:**
```json
{
  "results": [{
    "toolCallId": "abc123",
    "result": [
      {
        "id": 123,
        "address": "123 Main St, Apt 3B",
        "bedrooms": 2,
        "bathrooms": 1.5,
        "price": 1800,
        "listing_status": "available",
        "is_available_for_tours": true,
        "property_id": 123,
        "assigned_to": {
          "user_id": 5,
          "user_type": "realtor",
          "name": "Sarah Johnson"
        },
        "availability": {
          "hasAvailability": true,
          "nextAvailableSlot": {
            "startAt": "2025-12-01T16:00:00Z",
            "endAt": "2025-12-01T16:30:00Z"
          },
          "totalSlots": 15
        }
      }
    ]
  }]
}
```

---

#### 2. Validate Tour Request (RECOMMENDED - Use This Instead of #2a)

**Endpoint:** `POST /vapi/properties/validate-tour-request`  
**What VAPI sends:**
```json
{
  "property_name": "123 Main St, Apt 3B",  // REQUIRED: property name/address (user-provided)
  "requested_start_at": "2025-12-01T16:00:00Z",
  "requested_end_at": "2025-12-01T16:30:00Z"
}
```

**Important:** 
- **NO property_id needed** - VAPI should only send `property_name` (what the user tells it)
- Backend will search for the property using semantic search
- VAPI can only do POST requests, not GET

**What Backend returns (if requested time is AVAILABLE):**
```json
{
  "isAvailable": true,
  "canBook": true,
  "requestedSlot": {
    "startAt": "2025-12-01T16:00:00Z",
    "endAt": "2025-12-01T16:30:00Z"
  },
  "assignedUser": {
    "userId": 5,
    "userType": "realtor",
    "name": "Sarah Johnson"
  },
  "timezone": "America/New_York",
  "message": "Requested time slot is available"
}
```

**What Backend returns (if requested time is NOT AVAILABLE):**
```json
{
  "isAvailable": false,
  "canBook": false,
  "propertyId": 123,
  "propertyName": "123 Main St, Apt 3B",
  "reason": "Requested time slot is not available",
  "requestedSlot": {
    "startAt": "2025-12-01T16:00:00Z",
    "endAt": "2025-12-01T16:30:00Z"
  },
  "suggestedSlots": [
    {
      "startAt": "2025-12-01T17:00:00Z",
      "endAt": "2025-12-01T17:30:00Z"
    },
    {
      "startAt": "2025-12-02T14:00:00Z",
      "endAt": "2025-12-02T14:30:00Z"
    },
    {
      "startAt": "2025-12-02T15:00:00Z",
      "endAt": "2025-12-02T15:30:00Z"
    }
  ],
  "assignedUser": {
    "userId": 5,
    "userType": "realtor",
    "name": "Sarah Johnson"
  },
  "timezone": "America/New_York",
  "message": "Requested time is not available. Here are 3 alternative options."
}
```

**VAPI Action:**
- If `isAvailable === true`: Tell user "Great! That time works. I'll submit your booking request."
- If `isAvailable === false`: Present the suggested slots to user: "That time isn't available, but I have these options: [list slots]. Which works for you?"

**Important:**
- Backend automatically identifies which PM/Realtor the call is for from the call's destination number
- Only validates slots within 2 weeks from now
- Returns 2-3 alternative slots closest to the requested time if not available
- Checks property status and assigned user automatically

---

#### 2a. Check Assigned User Availability (Alternative - Get All Slots)

**Endpoint:** `POST /vapi/properties/availability`  
**What VAPI sends:**
```json
{
  "property_name": "123 Main St, Apt 3B",  // REQUIRED: property name/address (user-provided)
  "from_date": "2025-12-01T00:00:00Z",  // Optional: defaults to now
  "to_date": "2025-12-07T00:00:00Z"  // Optional: defaults to 2 weeks from now
}
```

**Important:**
- **NO property_id needed** - only `property_name` (what the user tells it)
- If `from_date`/`to_date` not provided, defaults to next 2 weeks
- VAPI can only do POST requests, not GET

**What Backend returns:**
```json
{
  "propertyId": 123,
  "assignedUser": {
    "userId": 5,
    "userType": "realtor",
    "name": "Sarah Johnson"
  },
  "timezone": "America/New_York",
  "availableSlots": [
    {
      "startAt": "2025-12-01T16:00:00Z",
      "endAt": "2025-12-01T16:30:00Z"
    },
    {
      "startAt": "2025-12-02T14:00:00Z",
      "endAt": "2025-12-02T14:30:00Z"
    }
  ]
}
```

**VAPI Action:** Use this if you want to show all available slots. Otherwise, use endpoint #2 above.

---

#### 3. Create Pending Booking Request
**Endpoint:** `POST /vapi/bookings/request`  
**What VAPI sends:**
```json
{
  "property_name": "123 Main St, Apt 3B",  // REQUIRED: property name/address (user-provided)
  "visitor_name": "John Doe",
  "visitor_phone": "+14125551234",
  "visitor_email": "john@example.com",
  "requested_start_at": "2025-12-01T16:00:00Z",
  "requested_end_at": "2025-12-01T16:30:00Z",
  "timezone": "America/New_York",
  "notes": "Interested in 2-bedroom unit"
}
```

**Important:**
- **NO property_id needed** - only `property_name` (what the user tells it)
- Backend automatically sets `created_by` to "vapi"

**What Backend returns:**
```json
{
  "bookingId": 1,
  "status": "pending",
  "message": "Booking request created successfully. Awaiting approval."
}
```

**VAPI Action:** Inform user that booking request has been submitted and is pending approval. **Never** tell user the booking is confirmed - it's only pending.

**Important:** 
- Backend automatically determines the approver (realtor if property is assigned to realtor, else PM)
- Backend automatically identifies which PM/Realtor the call is for from the call's destination number
- SMS notifications are automatically sent to the approver

---

#### 4. Get Booking Details by Visitor
**Endpoint:** `POST /vapi/bookings/by-visitor`  
**What VAPI sends:**
```json
{
  "visitor_phone": "+14125551234",  // Optional: use phone OR name
  "visitor_name": "John Doe",  // Optional: use name OR phone
  "status": "pending"  // Optional: filter by status
}
```

**Important:**
- VAPI can send EITHER `visitor_phone` OR `visitor_name` (or both)
- VAPI can only do POST requests, not GET

**What Backend returns:**
```json
{
  "visitorPhone": "+14125551234",
  "bookings": [
    {
      "bookingId": 1,
      "propertyId": 123,
      "visitor": {
        "name": "John Doe",
        "phone": "+14125551234",
        "email": "john@example.com"
      },
      "startAt": "2025-12-01T16:00:00Z",
      "endAt": "2025-12-01T16:30:00Z",
      "timezone": "America/New_York",
      "status": "pending",  // or "approved", "denied", "cancelled", "rescheduled"
      "createdBy": "vapi",
      "notes": "Interested in 2-bedroom unit",
      "proposedSlots": null,  // Only set if status is "rescheduled"
      "requestedAt": "2025-11-26T10:30:00Z",
      "createdAt": "2025-11-26T10:30:00Z",
      "updatedAt": "2025-11-26T10:30:00Z"
    }
  ]
}
```

**VAPI Action:** 
- If `status === "pending"`: "Your booking request is still pending approval."
- If `status === "approved"`: "Your booking is confirmed for [date/time]."
- If `status === "denied"`: "Unfortunately, your booking request was not approved."
- If `status === "rescheduled"`: "Your booking has been rescheduled. Please select from: [proposed slots]"
- If `status === "cancelled"`: "Your booking has been cancelled."

---

#### 5. Cancel/Delete Booking by Visitor
**Endpoint:** `POST /vapi/bookings/cancel`  
**What VAPI sends:**
```json
{
  "property_name": "123 Main St, Apt 3B",  // Optional: helps identify the specific booking
  "visitor_phone": "+14125551234",  // Required: use phone OR name
  "visitor_name": "John Doe",  // Required: use name OR phone
  "reason": "Changed my mind"  // Optional: reason for cancellation
}
```

**How it works:**
1. **First checks** for existing bookings (pending/approved) by visitor name and phone
2. **If found:** Cancels them (soft delete - stored in DB with `deleted_at` timestamp)
3. **If not found:** Checks for pending requests and deletes them (soft delete)
4. **All cancellations stored** in DB so PM/realtor can see what was cancelled and why

**Important:**
- **NO booking_id needed** - VAPI should only send user-provided info (name, phone, property_name)
- Backend automatically finds and cancels the correct booking
- All cancelled/deleted bookings are stored in DB with `deleted_at`, `deletion_reason`, and `deleted_by` fields

**What Backend returns:**
```json
{
  "message": "Successfully cancelled 1 booking(s)",
  "cancelledBookings": [
    {
      "bookingId": 1,
      "status": "cancelled",
      "propertyId": 123
    }
  ]
}
```

**VAPI Action:** Confirm cancellation to user. If no booking found, inform user they have no active bookings.

---

### Complete VAPI Integration Flow

**1. User asks about a property:**
```
VAPI → Uses existing searchApartments tool → POST /search_apartments/
Backend → Returns properties with ALL original data PLUS:
  - listing_status ("available" | "rented" | "offline")
  - is_available_for_tours (boolean)
  - assigned_to (user info)
  - availability (hasAvailability, nextAvailableSlot, totalSlots)

VAPI checks: 
  if (property.listing_status === "available" && property.availability?.hasAvailability === true) {
    // Property is available and has tour slots - offer booking
  } else if (property.listing_status === "available" && property.availability?.hasAvailability === false) {
    // Property is available but no slots - inform user
  } else if (property.listing_status === "rented") {
    // Property is rented - inform user it's no longer available
  }
```

**2. User wants to book a tour:**
```
User says: "I'd like to tour this property tomorrow at 2 PM"
VAPI → POST /vapi/properties/validate-tour-request
  {
    "property_name": "123 Main St, Apt 3B",  // REQUIRED: what user told VAPI
    "requested_start_at": "2025-12-01T14:00:00Z",
    "requested_end_at": "2025-12-01T14:30:00Z"
  }
  (NO property_id needed - only property_name from user)
  
Backend → Returns:
  - If available: {isAvailable: true, canBook: true, propertyId, propertyName}
  - If not available: {isAvailable: false, suggestedSlots: [2-3 alternatives], propertyId, propertyName}

VAPI → 
  - If available: "Great! That time works. I'll submit your booking request."
  - If not available: "That time isn't available, but I have these options: [list slots]. Which works for you?"
```

**3. User confirms a time slot:**
```
VAPI collects: visitor name, phone, email (optional)
VAPI → POST /vapi/bookings/request with booking details
  {
    "property_name": "123 Main St, Apt 3B",  // What user told VAPI (NO property_id)
    "visitor_name": "John Doe",
    "visitor_phone": "+14125551234",
    "visitor_email": "john@example.com",
    "requested_start_at": "2025-12-01T16:00:00Z",
    "requested_end_at": "2025-12-01T16:30:00Z",
    "timezone": "America/New_York"
  }
Backend → Returns { bookingId, status: "pending" }
VAPI tells user: "Your booking request has been submitted. You'll receive a confirmation once it's approved."
```

**4. User calls back to check status:**
```
VAPI → POST /vapi/bookings/by-visitor
  {
    "visitor_phone": "+14125551234",  // OR "visitor_name": "John Doe"
    "status": "pending"  // Optional: filter by status
  }
Backend → Returns all bookings for that phone/name
VAPI → Tells user current status and details:
  - If status === "pending": "Your booking request is still pending approval."
  - If status === "approved": "Your booking is confirmed for [date/time]."
  - If status === "denied": "Unfortunately, your booking request was not approved."
  - If status === "rescheduled": "Your booking has been rescheduled. Please select from: [proposed slots]"
  - If status === "cancelled": "Your booking has been cancelled."
```

**5. User wants to cancel:**
```
VAPI → POST /vapi/bookings/cancel
  {
    "property_name": "123 Main St, Apt 3B",  // Optional: helps identify specific booking
    "visitor_phone": "+14125551234",  // OR "visitor_name": "John Doe"
    "reason": "Changed my mind"  // Optional
  }
  (NO booking_id needed - backend finds booking by name/phone)

Backend Flow:
  1. First checks for existing bookings (pending/approved) by name and phone
  2. If found: Cancels them (soft delete - stored in DB with deleted_at)
  3. If not found: Checks for pending requests and deletes them (soft delete)
  4. All cancellations stored in DB so PM/realtor can see what was cancelled and why

Backend → Returns confirmation with cancelled/deleted bookings
VAPI → Tells user: "Your booking has been cancelled."
```

### VAPI Integration Summary

**Quick Reference - What VAPI Should Call:**

| Action | Endpoint | Method | Auth Required |
|--------|----------|--------|---------------|
| **Search Properties** | `POST /search_apartments/` | POST | No (uses existing `searchApartments` tool) |
| **Check Availability** | `GET /vapi/properties/{property_id}/availability` | GET | No |
| **Create Booking** | `POST /api/bookings/request` | POST | No |
| **Check Booking Status** | `GET /vapi/bookings/by-visitor-phone` | GET | No |
| **Cancel Booking** | `POST /vapi/bookings/cancel-by-visitor-phone` | POST | No |

### Important VAPI Rules

✅ **VAPI can only do POST requests** - all endpoints are POST (no GET requests)  
✅ **NO property_id needed** - VAPI should only send `property_name` (what the user tells it)  
✅ **Use existing `searchApartments` tool** - it now includes booking availability automatically  
✅ **Check `listing_status === "available"`** before offering booking  
✅ **Check `availability.hasAvailability === true`** to know if tour slots exist  
✅ **Always** create bookings with `status: "pending"` - never auto-approve  
✅ **Always** inform users that bookings are "pending approval"  
✅ **Never** tell users a booking is "confirmed" unless `status === "approved"`  
✅ Use visitor phone number OR name to lookup bookings (not booking_id)  
✅ Backend automatically identifies PM/Realtor from call's destination number - no need to send it  
✅ **Cancellation flow:** First checks for bookings, then deletes pending requests - all stored in DB with reason

### VAPI Tool Configuration

**1. searchApartments (Already Configured - No Changes Needed)**
- **Tool Name:** `searchApartments`
- **Endpoint:** `POST /search_apartments/`
- **Description:** Search for properties. Now automatically includes booking availability info.
- **Returns:** Property listings with `listing_status`, `is_available_for_tours`, `assigned_to`, and `availability` fields

**2. validateTourRequest (NEW - Add to VAPI) - RECOMMENDED**
- **Tool Name:** `validateTourRequest`
- **Endpoint:** `POST /vapi/properties/validate-tour-request`
- **Description:** Validate a specific tour time request and get alternatives if not available
- **Parameters:**
  - `property_name` (body, required): Property name/address (e.g., "123 Main St, Apt 3B") - **NO property_id needed**
  - `requested_start_at` (body, required): Requested start time in ISO format
  - `requested_end_at` (body, required): Requested end time in ISO format
- **Returns:** 
  - If available: `{isAvailable: true, canBook: true, propertyId, propertyName}`
  - If not: `{isAvailable: false, suggestedSlots: [2-3 alternatives], propertyId, propertyName}`

**2a. checkPropertyAvailability (Alternative - Add to VAPI)**
- **Tool Name:** `checkPropertyAvailability`
- **Endpoint:** `POST /vapi/properties/availability`
- **Description:** Get all available time slots for a property's assigned user
- **Parameters:**
  - `property_name` (body, required): Property name/address - **NO property_id needed**
  - `from_date` (body, optional): Start date in ISO format (defaults to now)
  - `to_date` (body, optional): End date in ISO format (defaults to 2 weeks from now)

**3. createBookingRequest (NEW - Add to VAPI)**
- **Tool Name:** `createBookingRequest`
- **Endpoint:** `POST /vapi/bookings/request`
- **Description:** Create a pending booking request for a property tour
- **Parameters:**
  - `property_name` (required): Property name/address - **NO property_id needed**
  - `visitor_name`: Visitor's name
  - `visitor_phone`: Visitor's phone number
  - `visitor_email`: Visitor's email (optional)
  - `requested_start_at`: Start time in ISO format
  - `requested_end_at`: End time in ISO format
  - `timezone`: Timezone (e.g., "America/New_York", defaults to "America/New_York")
  - `notes`: Additional notes (optional)

**4. getBookingStatus (NEW - Add to VAPI)**
- **Tool Name:** `getBookingStatus`
- **Endpoint:** `POST /vapi/bookings/by-visitor`
- **Description:** Get booking status and details for a visitor
- **Parameters:**
  - `visitor_phone` (optional): Visitor's phone number
  - `visitor_name` (optional): Visitor's name
  - `status` (optional): Filter by status
- **Note:** Send EITHER `visitor_phone` OR `visitor_name` (or both)

**5. cancelBooking (NEW - Add to VAPI)**
- **Tool Name:** `cancelBooking`
- **Endpoint:** `POST /vapi/bookings/cancel`
- **Description:** Cancel or delete a booking/tour request by visitor information
- **Parameters:**
  - `property_name` (optional): Property name/address (helps identify specific booking)
  - `visitor_phone` (required): Visitor's phone number (or use visitor_name)
  - `visitor_name` (required): Visitor's name (or use visitor_phone)
  - `reason` (optional): Cancellation reason
- **Flow:**
  1. First checks for existing bookings (pending/approved) by name and phone
  2. If found: Cancels them (soft delete - stored in DB)
  3. If not found: Checks for pending requests and deletes them (soft delete)
  4. All cancellations stored in DB so PM/realtor can see what was cancelled and why
- **Note:** **NO booking_id needed** - backend finds booking by name/phone

### Dashboard Endpoints (PM/Realtor)

These endpoints require authentication and are for the dashboard UI:

- `GET /api/users/{user_id}/bookings` - Get user's bookings
- `POST /api/bookings/{booking_id}/approve` - Approve booking
- `POST /api/bookings/{booking_id}/deny` - Deny booking
- `POST /api/bookings/{booking_id}/reschedule` - Reschedule booking
- `POST /api/bookings/{booking_id}/cancel` - Cancel booking (by approver)
- `POST /api/properties/{property_id}/assign` - Assign property to realtor

See the full documentation above for details on these endpoints.

---

## 📅 Dashboard Calendar & Booking Management UI Guide

### Overview

This section provides comprehensive guidance for building the dashboard calendar interface for Property Managers and Realtors to manage property tour bookings, availability, and scheduling.

### Core Features to Implement

#### 1. Calendar View

**Multiple View Options:**
- **Day View:** Show all bookings and availability for a single day
- **Week View:** Show 7-day calendar with time slots
- **Month View:** Show monthly overview with booking indicators
- **List View:** Show upcoming bookings in a list format

**Calendar Display Requirements:**
- Color-code bookings by status:
  - 🟡 **Pending** - Yellow/Orange (needs action)
  - 🟢 **Approved** - Green (confirmed)
  - 🔴 **Denied** - Red (cancelled)
  - 🔵 **Rescheduled** - Blue (awaiting confirmation)
  - ⚫ **Cancelled** - Gray (inactive)
- Show property address on each booking
- Show visitor name and phone number
- Display time slots clearly
- Highlight current day/time
- Show timezone information

**Implementation Example:**
```javascript
// Calendar component structure
function BookingCalendar({ userId, userType, view = 'week' }) {
  const [bookings, setBookings] = useState([]);
  const [selectedDate, setSelectedDate] = useState(new Date());
  
  useEffect(() => {
    // Fetch bookings for the selected date range
    fetchBookings(userId, userType, selectedDate, view);
  }, [userId, userType, selectedDate, view]);
  
  return (
    <div className="calendar-container">
      {/* View selector */}
      <ViewSelector view={view} onChange={setView} />
      
      {/* Calendar grid */}
      <CalendarGrid 
        bookings={bookings}
        selectedDate={selectedDate}
        onDateSelect={setSelectedDate}
        onBookingClick={handleBookingClick}
      />
    </div>
  );
}
```

---

#### 2. Booking Management Panel

**Pending Bookings Queue:**
- Show all pending bookings in a prominent section
- Display:
  - Property address
  - Visitor name, phone, email
  - Requested date/time
  - Time since request (e.g., "2 hours ago")
  - Quick action buttons: Approve, Deny, Reschedule
- Sort by: Request time (newest first) or Requested date (soonest first)
- Filter by: Property, Date range, Visitor name

**Approved Bookings:**
- Show upcoming approved bookings
- Display confirmation details
- Allow cancellation
- Show property details and visitor contact info

**Implementation:**
```javascript
function PendingBookingsPanel({ userId, userType }) {
  const [pendingBookings, setPendingBookings] = useState([]);
  
  useEffect(() => {
    fetchUserBookings(userId, userType, 'pending').then(setPendingBookings);
  }, [userId, userType]);
  
  return (
    <div className="pending-bookings-panel">
      <h2>Pending Bookings ({pendingBookings.length})</h2>
      {pendingBookings.map(booking => (
        <BookingCard 
          key={booking.bookingId}
          booking={booking}
          onApprove={() => handleApprove(booking.bookingId)}
          onDeny={() => handleDeny(booking.bookingId)}
          onReschedule={() => handleReschedule(booking.bookingId)}
        />
      ))}
    </div>
  );
}
```

---

#### 3. Manual Event Creation & Calendar Management

**Features:**
- Create manual bookings/tours from dashboard
- Add holidays, off days, and busy periods
- Select properties from dropdown or properties view
- View all calendar events (bookings + availability slots) in one place

**Endpoints:**

**1. Get Properties for Dropdown**
- **Endpoint:** `GET /api/users/{user_id}/properties`
- **Description:** Get list of properties for dropdown when creating manual events
- **Response:**
```json
{
  "properties": [
    {
      "id": 123,
      "address": "123 Main St, Berkeley, CA",
      "price": 2500,
      "bedrooms": 2,
      "bathrooms": 1,
      "listing_status": "available"
    }
  ],
  "total": 1
}
```

**2. Create Manual Booking/Tour**
- **Endpoint:** `POST /api/bookings/manual`
- **Description:** Create a manual booking/tour from dashboard (auto-approved)
- **Body:**
```json
{
  "property_id": 123,
  "visitor_name": "John Doe",
  "visitor_phone": "+15409773737",
  "visitor_email": "john@example.com",
  "start_at": "2025-12-01T16:00:00Z",
  "end_at": "2025-12-01T17:00:00Z",
  "timezone": "America/New_York",
  "notes": "Manual booking created from dashboard"
}
```
- **Response:**
```json
{
  "bookingId": 456,
  "status": "approved",
  "propertyId": 123,
  "visitorName": "John Doe",
  "startAt": "2025-12-01T16:00:00Z",
  "endAt": "2025-12-01T17:00:00Z",
  "message": "Manual booking created and approved successfully"
}
```
- **Note:** Manual bookings are automatically approved since created by the approver

**3. Create Availability Slot (Enhanced)**
- **Endpoint:** `POST /api/users/{user_id}/availability`
- **Description:** Create manual availability/unavailability slot, including full-day events
- **Body:**
```json
{
  "user_type": "property_manager",
  "start_at": "2025-12-25T00:00:00Z",
  "end_at": "2025-12-25T23:59:59Z",
  "slot_type": "holiday",
  "is_full_day": true,
  "notes": "Christmas Day"
}
```
- **Slot Types:**
  - `available` - Mark time as available
  - `unavailable` - Mark time as unavailable
  - `busy` - Mark as busy
  - `personal` - Personal time
  - `holiday` - Holiday (full day)
  - `off_day` - Day off (full day)
- **Full-Day Events:** Set `is_full_day: true` to mark entire day(s) as holiday/off day

**4. Get All Calendar Events**
- **Endpoint:** `GET /api/users/{user_id}/calendar-events?from_date={ISO_DATE}&to_date={ISO_DATE}`
- **Description:** Get all calendar events (bookings + availability slots) for calendar display
- **Response:**
```json
{
  "userId": 12,
  "userType": "property_manager",
  "fromDate": "2025-12-01T00:00:00Z",
  "toDate": "2025-12-31T23:59:59Z",
  "events": [
    {
      "id": "booking_456",
      "type": "booking",
      "bookingId": 456,
      "propertyId": 123,
      "propertyAddress": "123 Main St",
      "visitorName": "John Doe",
      "visitorPhone": "+15409773737",
      "startAt": "2025-12-01T16:00:00Z",
      "endAt": "2025-12-01T17:00:00Z",
      "status": "approved",
      "callRecord": {
        "vapiCallId": "call_abc123",
        "callTranscript": "Full transcript...",
        "callRecordingUrl": "https://..."
      }
    },
    {
      "id": "slot_789",
      "type": "availability_slot",
      "slotId": 789,
      "startAt": "2025-12-25T00:00:00Z",
      "endAt": "2025-12-25T23:59:59Z",
      "slotType": "holiday",
      "isFullDay": true
    }
  ],
  "bookings": [...],
  "availabilitySlots": [...],
  "total": 2
}
```

**Implementation Guide:**

**Manual Booking Creation Flow:**
1. User clicks "Add Event" or "Create Tour" button
2. Modal/form opens with:
   - Property dropdown (populated from `/api/users/{user_id}/properties`)
   - OR: Click on property from properties view → pre-fills property_id
   - Visitor name, phone, email fields
   - Date/time picker for start and end times
   - Optional notes field
3. On submit, call `POST /api/bookings/manual`
4. Show success message and refresh calendar

**Adding Holidays/Off Days:**
1. User selects a day in calendar (or date picker)
2. Modal opens with:
   - Date pre-filled
   - Slot type dropdown: Holiday, Off Day, Busy, etc.
   - Optional notes/reason
3. Set `is_full_day: true` in request
4. Backend automatically sets time to 00:00:00 - 23:59:59 for that day
5. Call `POST /api/users/{user_id}/availability`

**Call Record Linking:**
- Bookings created via VAPI phone calls are automatically linked to their call recordings and transcripts
- The backend extracts `x-call-id` header from VAPI requests and links to the `CallRecord` table
- When viewing a booking in the dashboard:
  - If `callRecord` is present, display:
    - Audio player for call recording (`callRecordingUrl`)
    - Full call transcript (`callTranscript`)
    - Call ID for reference (`vapiCallId`)
  - This allows PMs/Realtors to review the original conversation that led to the booking
- The call record information is included in:
  - `GET /api/bookings/{booking_id}` - Single booking details
  - `GET /api/users/{user_id}/calendar-events` - All calendar events
  - `GET /api/users/{user_id}/bookings` - User's bookings list

**Calendar Display:**
- Use `GET /api/users/{user_id}/calendar-events` to fetch all events
- Display bookings with different colors by status
- Display availability slots (holidays, off days) as background colors or overlays
- Full-day events should span entire day in calendar view
- Show call record indicator (📞 icon) on bookings that have linked call recordings

**Example Implementation:**
```javascript
// Manual booking creation
async function createManualBooking(propertyId, visitorInfo, startAt, endAt) {
  const response = await fetch(`/api/bookings/manual`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      property_id: propertyId,
      visitor_name: visitorInfo.name,
      visitor_phone: visitorInfo.phone,
      visitor_email: visitorInfo.email,
      start_at: startAt,
      end_at: endAt,
      timezone: 'America/New_York',
      notes: visitorInfo.notes
    })
  });
  return response.json();
}

// Add holiday/off day
async function addHoliday(date, slotType, notes) {
  const startOfDay = new Date(date);
  startOfDay.setHours(0, 0, 0, 0);
  const endOfDay = new Date(date);
  endOfDay.setHours(23, 59, 59, 999);
  
  const response = await fetch(`/api/users/${userId}/availability`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      user_type: userType,
      start_at: startOfDay.toISOString(),
      end_at: endOfDay.toISOString(),
      slot_type: slotType, // 'holiday' or 'off_day'
      is_full_day: true,
      notes: notes
    })
  });
  return response.json();
}

// Get all calendar events
async function getCalendarEvents(fromDate, toDate) {
  const response = await fetch(
    `/api/users/${userId}/calendar-events?from_date=${fromDate}&to_date=${toDate}`,
    {
      headers: { 'Authorization': `Bearer ${token}` }
    }
  );
  return response.json();
}
```

---

#### 4. Availability Management

**Working Hours Configuration:**
- Allow users to set default working hours (e.g., 9 AM - 5 PM)
- Set timezone preference
- Set default slot length (15, 30, 45, 60 minutes)
- Set working days (e.g., Monday-Friday, or all week)
- **Note:** Working hours apply to all selected working days (same hours for all days)

**Manual Availability Blocking:**
- **Mark Unavailable:** Block specific time slots (personal time, meetings)
- **Mark Busy:** Mark as busy but allow override for urgent bookings
- **Bulk Block:** Block entire days or date ranges
- **Recurring Blocks:** Set recurring unavailable times (e.g., every Monday 12-1 PM)

**Visual Availability Indicator:**
- Show available slots in green
- Show blocked/unavailable slots in red
- Show booked slots in blue
- Show pending bookings in yellow

**Calendar Preferences Endpoints:**

**Get Calendar Preferences:**
- **Endpoint:** `GET /api/users/{user_id}/calendar-preferences?user_type={user_type}`
- **Auth:** Required
- **Response:**
```json
{
  "timezone": "America/New_York",
  "defaultSlotLengthMins": 30,
  "workingHours": {
    "start": "09:00",
    "end": "17:00"
  }
}
```

**Update Calendar Preferences:**
- **Endpoint:** `PATCH /api/users/{user_id}/calendar-preferences?user_type={user_type}`
- **Auth:** Required
- **Request Body (all fields optional):**
```json
{
  "timezone": "America/New_York",  // Optional: IANA timezone string
  "default_slot_length_mins": 30,  // Optional: 15-120 minutes
  "working_hours_start": "09:00",  // Optional: HH:MM format
  "working_hours_end": "17:00",    // Optional: HH:MM format
  "working_days": [0, 1, 2, 3, 4]  // Optional: Array of day numbers (0=Monday, 6=Sunday)
}
```
- **Response:**
```json
{
  "message": "Calendar preferences updated successfully",
  "preferences": {
    "timezone": "America/New_York",
    "defaultSlotLengthMins": 30,
    "workingHours": {
      "start": "09:00",
      "end": "17:00"
    }
  }
}
```

**Important Notes:**
- You can update individual fields (e.g., just `working_hours_start` and `working_hours_end`)
- `working_hours_end` must be after `working_hours_start`
- `default_slot_length_mins` must be between 15 and 120
- Time format must be `HH:MM` (24-hour format, e.g., "09:00", "17:00")
- `working_days` is an array of integers: 0=Monday, 1=Tuesday, 2=Wednesday, 3=Thursday, 4=Friday, 5=Saturday, 6=Sunday
- Default `working_days` is `[0, 1, 2, 3, 4]` (Monday-Friday)
- Changes are saved immediately and persist across sessions

**Implementation:**
```javascript
function AvailabilityManager({ userId, userType }) {
  const [preferences, setPreferences] = useState({
    timezone: 'America/New_York',
    defaultSlotLengthMins: 30,
    workingHours: {
      start: '09:00',
      end: '17:00'
    }
  });
  
  const [unavailableSlots, setUnavailableSlots] = useState([]);
  
  // Fetch calendar preferences on mount
  useEffect(() => {
    fetchCalendarPreferences();
  }, [userId, userType]);
  
  async function fetchCalendarPreferences() {
    const response = await fetch(
      `/api/users/${userId}/calendar-preferences?user_type=${userType}`,
      {
        headers: { 'Authorization': `Bearer ${token}` }
      }
    );
    const data = await response.json();
    setPreferences(data);
  }
  
  // Update calendar preferences
  async function updateWorkingHours(start, end) {
    const response = await fetch(
      `/api/users/${userId}/calendar-preferences?user_type=${userType}`,
      {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          working_hours_start: start,
          working_hours_end: end
        })
      }
    );
    
    if (response.ok) {
      const data = await response.json();
      setPreferences(data.preferences);
      // Show success message
      alert('Working hours updated successfully!');
    } else {
      const error = await response.json();
      alert(`Error: ${error.detail}`);
    }
  }
  
  // Update timezone
  async function updateTimezone(timezone) {
    const response = await fetch(
      `/api/users/${userId}/calendar-preferences?user_type=${userType}`,
      {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ timezone })
      }
    );
    
    if (response.ok) {
      const data = await response.json();
      setPreferences(data.preferences);
    }
  }
  
  // Update slot length
  async function updateSlotLength(minutes) {
    if (minutes < 15 || minutes > 120) {
      alert('Slot length must be between 15 and 120 minutes');
      return;
    }
    
    const response = await fetch(
      `/api/users/${userId}/calendar-preferences?user_type=${userType}`,
      {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          default_slot_length_mins: minutes
        })
      }
    );
    
    if (response.ok) {
      const data = await response.json();
      setPreferences(data.preferences);
    }
  }
  
  // Create unavailable slot
  async function blockTimeSlot(startAt, endAt, reason) {
    const response = await fetch(`/api/users/${userId}/availability`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        user_type: userType,
        start_at: startAt,
        end_at: endAt,
        slot_type: 'unavailable',
        notes: reason
      })
    });
    
    if (response.ok) {
      // Refresh unavailable slots
      fetchUnavailableSlots();
    }
  }
  
  return (
    <div className="availability-manager">
      <WorkingHoursConfig 
        preferences={preferences}
        onUpdateWorkingHours={updateWorkingHours}
        onUpdateTimezone={updateTimezone}
        onUpdateSlotLength={updateSlotLength}
      />
      <TimeSlotBlocker onBlock={blockTimeSlot} />
      <UnavailableSlotsList slots={unavailableSlots} />
    </div>
  );
}
```

**User Profile Endpoint (includes calendar preferences):**
- **Endpoint:** `GET /user-profile`
- **Auth:** Required
- **Response:**
```json
{
  "user": {
    "user_type": "property_manager",
    "id": 12,
    "name": "John Smith",
    "email": "john@example.com",
    "company_name": "ABC Properties",
    "timezone": "America/New_York",
    "calendar_preferences": {
      "defaultSlotLengthMins": 30,
      "workingHours": {
        "start": "09:00",
        "end": "17:00"
      }
    }
  }
}
```

---

#### 4. Booking Detail Modal/Card

**When user clicks on a booking, show:**
- **Visitor Information:**
  - Name, phone, email
  - Contact buttons (call, email, SMS)
- **Property Information:**
  - Address
  - Property details (bedrooms, bathrooms, price)
  - Link to property details page
- **Booking Details:**
  - Requested date/time
  - Status and status history
  - Timezone
  - Notes from visitor
  - Audit log (who did what and when)
- **Call Record (if booking came from phone call):**
  - **Call Recording:** Play button to listen to the call recording
  - **Call Transcript:** Full transcript of the conversation
  - **Call ID:** Link to view full call details
  - Display prominently if `callRecord` is present in booking data
- **Actions (based on status):**
  - **Pending:** Approve, Deny, Reschedule buttons
  - **Approved:** Cancel, View Property, Contact Visitor
  - **Rescheduled:** Show proposed slots, Approve Reschedule
  - **Denied/Cancelled:** View details only

**Implementation:**
```javascript
function BookingDetailModal({ booking, onClose, onAction }) {
  return (
    <Modal onClose={onClose}>
      <div className="booking-detail">
        <h2>Booking #{booking.bookingId}</h2>
        
        {/* Visitor Info */}
        <section>
          <h3>Visitor</h3>
          <p>{booking.visitor.name}</p>
          <p>{booking.visitor.phone}</p>
          <p>{booking.visitor.email}</p>
          <button onClick={() => callVisitor(booking.visitor.phone)}>Call</button>
          <button onClick={() => emailVisitor(booking.visitor.email)}>Email</button>
        </section>
        
        {/* Property Info */}
        <section>
          <h3>Property</h3>
          <p>{booking.propertyAddress}</p>
          <Link to={`/properties/${booking.propertyId}`}>View Property</Link>
        </section>
        
        {/* Booking Info */}
        <section>
          <h3>Booking Details</h3>
          <p>Date: {formatDate(booking.startAt)}</p>
          <p>Time: {formatTime(booking.startAt)} - {formatTime(booking.endAt)}</p>
          <p>Status: <StatusBadge status={booking.status} /></p>
          {booking.notes && <p>Notes: {booking.notes}</p>}
        </section>
        
        {/* Actions */}
        <section className="booking-actions">
          {booking.status === 'pending' && (
            <>
              <button onClick={() => onAction('approve', booking.bookingId)}>
                Approve
              </button>
              <button onClick={() => onAction('deny', booking.bookingId)}>
                Deny
              </button>
              <button onClick={() => onAction('reschedule', booking.bookingId)}>
                Reschedule
              </button>
            </>
          )}
          {booking.status === 'approved' && (
            <button onClick={() => onAction('cancel', booking.bookingId)}>
              Cancel Booking
            </button>
          )}
        </section>
        
        {/* Audit Log */}
        {booking.auditLog && (
          <section>
            <h3>History</h3>
            <AuditLogTimeline log={booking.auditLog} />
          </section>
        )}
      </div>
    </Modal>
  );
}
```

---

#### 5. Quick Actions & Bulk Operations

**Quick Approve/Deny:**
- Show approve/deny buttons directly on calendar items
- Confirmation dialogs for destructive actions
- Toast notifications for success/error

**Bulk Actions:**
- Select multiple pending bookings
- Bulk approve/deny (with confirmation)
- Export bookings to CSV/PDF

**Keyboard Shortcuts:**
- `A` - Approve selected booking
- `D` - Deny selected booking
- `R` - Reschedule selected booking
- `C` - Cancel selected booking
- `←/→` - Navigate days
- `↑/↓` - Navigate weeks

---

#### 6. Notifications & Alerts

**Real-time Notifications:**
- Show toast/popup when new booking request arrives
- Badge count on "Pending Bookings" tab
- Sound notification (optional, user preference)
- Browser push notifications (if supported)

**Notification Types:**
- 🆕 **New Booking Request:** "New tour request from John Doe for 123 Main St"
- ✅ **Booking Approved:** "Your booking for 123 Main St has been approved"
- ❌ **Booking Denied:** "Your booking request was not approved"
- 🔄 **Booking Rescheduled:** "Your booking has been rescheduled - please confirm new time"
- 🚫 **Booking Cancelled:** "Booking cancelled by visitor"

**Implementation:**
```javascript
// Real-time notifications using WebSocket or polling
function useBookingNotifications(userId, userType) {
  const [notifications, setNotifications] = useState([]);
  
  useEffect(() => {
    // Poll for new bookings every 30 seconds
    const interval = setInterval(async () => {
      const response = await fetch(`/api/users/${userId}/bookings?status=pending`);
      const data = await response.json();
      
      // Check for new bookings
      const newBookings = data.bookings.filter(b => 
        !notifications.some(n => n.bookingId === b.bookingId)
      );
      
      if (newBookings.length > 0) {
        newBookings.forEach(booking => {
          showNotification({
            type: 'new_booking',
            message: `New booking request from ${booking.visitor.name}`,
            booking: booking
          });
        });
      }
    }, 30000);
    
    return () => clearInterval(interval);
  }, [userId, userType]);
  
  return notifications;
}
```

---

#### 7. Property Assignment Interface (PM Only)

**Property Assignment Panel:**
- List all properties
- Show current assignment (PM or Realtor)
- Quick assign/unassign buttons
- Bulk assign multiple properties to a realtor
- Filter by: Assigned/Unassigned, Realtor, Property status

**Assignment Workflow:**
1. PM selects property(ies)
2. PM selects realtor from dropdown
3. PM adds reason (optional)
4. System updates assignment and sends notification to realtor

**Implementation:**
```javascript
function PropertyAssignmentPanel({ pmId }) {
  const [properties, setProperties] = useState([]);
  const [realtors, setRealtors] = useState([]);
  const [selectedProperties, setSelectedProperties] = useState([]);
  
  async function assignProperties(realtorId, propertyIds, reason) {
    for (const propertyId of propertyIds) {
      await fetch(`/api/properties/${propertyId}/assign`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          to_user_id: realtorId,
          to_user_type: 'realtor',
          reason: reason
        })
      });
    }
    
    // Refresh properties list
    fetchProperties();
  }
  
  return (
    <div className="property-assignment-panel">
      <h2>Property Assignment</h2>
      
      {/* Realtor selector */}
      <RealtorSelector 
        realtors={realtors}
        onSelect={setSelectedRealtor}
      />
      
      {/* Properties list with checkboxes */}
      <PropertiesList 
        properties={properties}
        selected={selectedProperties}
        onSelect={setSelectedProperties}
      />
      
      {/* Assign button */}
      <button 
        onClick={() => assignProperties(selectedRealtor, selectedProperties)}
        disabled={!selectedRealtor || selectedProperties.length === 0}
      >
        Assign {selectedProperties.length} Properties
      </button>
    </div>
  );
}
```

---

#### 8. Reschedule Workflow

**Reschedule Interface:**
- Show current booking details
- Show calendar with available slots
- Allow approver to select multiple alternative slots
- Add reason/note for reschedule
- Preview proposed slots before submitting
- Send notification to visitor with proposed slots

**Implementation:**
```javascript
function RescheduleModal({ booking, onClose, onReschedule }) {
  const [proposedSlots, setProposedSlots] = useState([]);
  const [availableSlots, setAvailableSlots] = useState([]);
  const [reason, setReason] = useState('');
  
  useEffect(() => {
    // Fetch available slots for next 7 days
    fetch(`/vapi/properties/${booking.propertyId}/availability?from=${getNextWeekStart()}&to=${getNextWeekEnd()}`)
      .then(res => res.json())
      .then(data => setAvailableSlots(data.availableSlots));
  }, [booking.propertyId]);
  
  function handleReschedule() {
    onReschedule(booking.bookingId, {
      proposed_slots: proposedSlots,
      reason: reason
    });
  }
  
  return (
    <Modal onClose={onClose}>
      <h2>Reschedule Booking</h2>
      <p>Current booking: {formatDateTime(booking.startAt)}</p>
      
      <h3>Select Alternative Time Slots</h3>
      <AvailableSlotsCalendar 
        slots={availableSlots}
        selected={proposedSlots}
        onSelect={setProposedSlots}
        multiple={true}
      />
      
      <textarea 
        placeholder="Reason for reschedule (optional)"
        value={reason}
        onChange={e => setReason(e.target.value)}
      />
      
      <button 
        onClick={handleReschedule}
        disabled={proposedSlots.length === 0}
      >
        Propose Reschedule
      </button>
    </Modal>
  );
}
```

---

#### 9. Statistics & Analytics Dashboard

**Key Metrics to Display:**
- **Total Bookings:** All-time and this month
- **Pending Bookings:** Count requiring action
- **Approval Rate:** Percentage of approved vs denied
- **Average Response Time:** Time to approve/deny bookings
- **Upcoming Bookings:** Next 7 days
- **Cancellation Rate:** Percentage of cancelled bookings

**Charts & Visualizations:**
- Bookings by status (pie chart)
- Bookings over time (line chart)
- Most requested properties (bar chart)
- Peak booking times (heatmap)

**Implementation:**
```javascript
function BookingStatistics({ userId, userType }) {
  const [stats, setStats] = useState({});
  
  useEffect(() => {
    // Calculate statistics from bookings
    fetchUserBookings(userId, userType).then(bookings => {
      const stats = {
        total: bookings.length,
        pending: bookings.filter(b => b.status === 'pending').length,
        approved: bookings.filter(b => b.status === 'approved').length,
        denied: bookings.filter(b => b.status === 'denied').length,
        cancelled: bookings.filter(b => b.status === 'cancelled').length,
        approvalRate: calculateApprovalRate(bookings),
        avgResponseTime: calculateAvgResponseTime(bookings)
      };
      setStats(stats);
    });
  }, [userId, userType]);
  
  return (
    <div className="statistics-dashboard">
      <StatCard label="Total Bookings" value={stats.total} />
      <StatCard label="Pending" value={stats.pending} color="warning" />
      <StatCard label="Approved" value={stats.approved} color="success" />
      <StatCard label="Approval Rate" value={`${stats.approvalRate}%`} />
      
      <BookingChart data={bookings} />
    </div>
  );
}
```

---

#### 10. Search & Filtering

**Search Functionality:**
- Search by visitor name, phone, email
- Search by property address
- Search by booking ID
- Full-text search across all booking fields

**Filtering Options:**
- **By Status:** Pending, Approved, Denied, Cancelled, Rescheduled
- **By Date Range:** Today, This Week, This Month, Custom Range
- **By Property:** Filter by specific property
- **By Realtor:** (PM only) Filter by assigned realtor
- **By Time:** Morning, Afternoon, Evening

**Sorting Options:**
- Date (newest/oldest first)
- Request time (newest/oldest first)
- Visitor name (A-Z, Z-A)
- Property address (A-Z, Z-A)

**Implementation:**
```javascript
function BookingFilters({ onFilterChange }) {
  const [filters, setFilters] = useState({
    status: null,
    dateRange: null,
    propertyId: null,
    search: ''
  });
  
  function handleFilterChange(key, value) {
    const newFilters = { ...filters, [key]: value };
    setFilters(newFilters);
    onFilterChange(newFilters);
  }
  
  return (
    <div className="booking-filters">
      <input 
        type="text"
        placeholder="Search bookings..."
        value={filters.search}
        onChange={e => handleFilterChange('search', e.target.value)}
      />
      
      <select 
        value={filters.status || ''}
        onChange={e => handleFilterChange('status', e.target.value || null)}
      >
        <option value="">All Statuses</option>
        <option value="pending">Pending</option>
        <option value="approved">Approved</option>
        <option value="denied">Denied</option>
        <option value="cancelled">Cancelled</option>
      </select>
      
      <DateRangePicker 
        value={filters.dateRange}
        onChange={range => handleFilterChange('dateRange', range)}
      />
    </div>
  );
}
```

---

#### 11. Mobile Responsive Design

**Mobile-Specific Features:**
- Swipe gestures: Swipe left to approve, swipe right to deny
- Touch-friendly buttons (minimum 44x44px)
- Simplified calendar view for small screens
- Bottom sheet modals instead of center modals
- Quick action buttons at bottom of screen

**Responsive Breakpoints:**
- **Mobile:** < 768px - List view, simplified calendar
- **Tablet:** 768px - 1024px - Week view, side panel
- **Desktop:** > 1024px - Full calendar, multiple panels

---

#### 12. Export & Reporting

**Export Options:**
- **CSV Export:** All bookings with filters applied
- **PDF Report:** Formatted booking report
- **Calendar Export:** iCal format for external calendars
- **Email Summary:** Daily/weekly booking summary

**Report Types:**
- Daily booking summary
- Weekly booking report
- Monthly statistics report
- Property performance report

---

### UI/UX Best Practices

#### Color Coding
- Use consistent colors for status throughout the app
- Ensure sufficient contrast for accessibility
- Consider colorblind-friendly palettes

#### Loading States
- Show skeleton loaders while fetching bookings
- Display "No bookings" state when empty
- Show error states with retry options

#### Confirmation Dialogs
- Always confirm destructive actions (deny, cancel)
- Show impact of action (e.g., "This will notify the visitor")
- Allow cancellation of confirmation

#### Error Handling
- Show user-friendly error messages
- Provide actionable error messages
- Log errors for debugging

#### Performance Optimization
- Paginate booking lists (50 per page)
- Lazy load calendar events
- Cache frequently accessed data
- Debounce search inputs

---

### Recommended Dashboard Layout

```
┌─────────────────────────────────────────────────────────┐
│  Header: Logo, User Menu, Notifications                 │
├──────────────┬──────────────────────────────────────────┤
│              │  Calendar View (Week/Month/Day)          │
│  Sidebar:    │  ┌────────────────────────────────────┐ │
│  - Stats     │  │  Mon  Tue  Wed  Thu  Fri  Sat  Sun│ │
│  - Filters   │  │  ┌──┐ ┌──┐ ┌──┐ ┌──┐ ┌──┐ ┌──┐ ┌──┐│ │
│  - Properties│  │  │  │ │  │ │  │ │  │ │  │ │  │ │  ││ │
│              │  │  └──┘ └──┘ └──┘ └──┘ └──┘ └──┘ └──┘│ │
│              │  └────────────────────────────────────┘ │
│              │                                          │
│              │  Pending Bookings Panel                  │
│              │  ┌────────────────────────────────────┐ │
│              │  │ 🟡 John Doe - 123 Main St         │ │
│              │  │    Dec 1, 4:00 PM                 │ │
│              │  │    [Approve] [Deny] [Reschedule]  │ │
│              │  └────────────────────────────────────┘ │
└──────────────┴──────────────────────────────────────────┘
```

---

### Implementation Checklist

- [ ] Calendar view (day/week/month)
- [ ] Pending bookings queue
- [ ] Booking detail modal
- [ ] Approve/Deny/Reschedule actions
- [ ] Availability management
- [ ] Working hours configuration
- [ ] Property assignment (PM only)
- [ ] Search and filtering
- [ ] Notifications system
- [ ] Statistics dashboard
- [ ] Export functionality
- [ ] Mobile responsive design
- [ ] Keyboard shortcuts
- [ ] Real-time updates (polling or WebSocket)

---

### Example Complete Dashboard Component

```javascript
function BookingDashboard({ userId, userType }) {
  const [view, setView] = useState('week');
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [bookings, setBookings] = useState([]);
  const [filters, setFilters] = useState({});
  
  // Fetch bookings
  useEffect(() => {
    fetchUserBookings(userId, userType, filters.status, filters.dateRange)
      .then(setBookings);
  }, [userId, userType, filters]);
  
  // Handle booking actions
  async function handleApprove(bookingId) {
    const response = await fetch(`/api/bookings/${bookingId}/approve`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ approver_id: userId })
    });
    
    if (response.ok) {
      showNotification('Booking approved successfully');
      refreshBookings();
    }
  }
  
  return (
    <div className="booking-dashboard">
      {/* Header */}
      <DashboardHeader 
        view={view}
        onViewChange={setView}
        selectedDate={selectedDate}
        onDateChange={setSelectedDate}
      />
      
      <div className="dashboard-content">
        {/* Sidebar */}
        <Sidebar>
          <BookingStatistics bookings={bookings} />
          <BookingFilters onFilterChange={setFilters} />
          {userType === 'property_manager' && (
            <PropertyAssignmentPanel pmId={userId} />
          )}
        </Sidebar>
        
        {/* Main Content */}
        <MainContent>
          {/* Pending Bookings Queue */}
          <PendingBookingsPanel 
            bookings={bookings.filter(b => b.status === 'pending')}
            onApprove={handleApprove}
            onDeny={handleDeny}
            onReschedule={handleReschedule}
          />
          
          {/* Calendar View */}
          <BookingCalendar 
            view={view}
            bookings={bookings}
            selectedDate={selectedDate}
            onBookingClick={handleBookingClick}
          />
        </MainContent>
      </div>
      
      {/* Booking Detail Modal */}
      {selectedBooking && (
        <BookingDetailModal 
          booking={selectedBooking}
          onClose={() => setSelectedBooking(null)}
          onAction={handleBookingAction}
        />
      )}
    </div>
  );
}
```

This provides a complete guide for building a comprehensive booking management dashboard!

---

## 📝 Key Points

- ✅ **Authentication:** All endpoints (except `/book-demo` and `/vapi/webhook`) require JWT token
- ✅ **Data Isolation:** PMs only see their data, Realtors only see assigned data
- ✅ **AI-Powered Uploads:** Supports JSON, CSV, TXT with intelligent parsing
- ✅ **Phone Number System:** PM requests → Tech adds → PM assigns
- ✅ **Demo System:** Public booking, admin manages, converts to PM accounts
- ✅ **Call Records:** Automatic storage of transcripts and recordings from VAPI webhooks

---

## 🔗 Base URL

**Production:** `https://leasing-copilot-mvp.onrender.com`  
**Development:** `http://localhost:8000`

---

For detailed tech team instructions, see `TECH_TEAM_PHONE_NUMBER_GUIDE.md`

---

## 📥 Import Historical Calls from VAPI

**Endpoint:** `POST /admin/import-vapi-calls?limit=100&offset=0`  
**Auth:** Admin only (add authentication in production)

This endpoint fetches historical calls from VAPI API and imports them into the database. Useful for backfilling call history.

**Query Parameters:**
- `limit` (optional): Number of calls to fetch per request (default: 100, max: 100)
- `offset` (optional): Pagination offset (default: 0)

**Response:**
```json
{
  "message": "Import completed",
  "total_fetched": 50,
  "total_available": 150,
  "imported": 45,
  "updated": 5,
  "skipped": 0,
  "errors": []
}
```

**Usage:**
```javascript
// Import calls in batches
async function importAllCalls() {
  let offset = 0;
  const limit = 100;
  let hasMore = true;
  
  while (hasMore) {
    const response = await fetch(`/admin/import-vapi-calls?limit=${limit}&offset=${offset}`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${adminToken}`
      }
    });
    
    const data = await response.json();
    console.log(`Imported ${data.imported}, Updated ${data.updated}, Skipped ${data.skipped}`);
    
    hasMore = data.total_fetched === limit;
    offset += limit;
  }
}
```

**Features:**
- Automatically skips duplicate calls (based on `call_id`)
- Updates existing records with new data (transcripts, recordings)
- **Fetches recording URLs from VAPI API** (recordings are not in list endpoint, must fetch per call)
- Fetches phone numbers from VAPI if only `phoneNumberId` is provided
- Handles pagination for large call histories
- Preserves original call timestamps from VAPI

**How Recordings Are Fetched:**
The import function automatically fetches recording URLs from VAPI API using:
```
GET https://api.vapi.ai/calls/{callId}
Authorization: Bearer YOUR_VAPI_API_KEY
```

This endpoint returns:
- `recordingUrl` - The audio recording URL (if recording is enabled)
- `transcript` - The call transcript
- Call metadata (duration, status, etc.)

---

## 🗄️ Database Migrations Required

### Migration 1: Call Records Table

To enable call records functionality, run this SQL migration:

```sql
-- Create call_records table (if it doesn't exist)
CREATE TABLE IF NOT EXISTS callrecord (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id TEXT NOT NULL UNIQUE,
    realtor_number TEXT NOT NULL,
    recording_url TEXT,
    transcript TEXT,
    live_transcript_chunks JSONB,
    call_duration INTEGER,
    call_status TEXT,
    caller_number TEXT,
    call_metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- IMPORTANT: If table already exists, add missing call_metadata column
ALTER TABLE callrecord 
ADD COLUMN IF NOT EXISTS call_metadata JSONB;

-- Create indexes for performance
CREATE UNIQUE INDEX IF NOT EXISTS idx_callrecord_call_id_unique ON callrecord(call_id);
CREATE INDEX IF NOT EXISTS idx_callrecord_realtor_number ON callrecord(realtor_number);
CREATE INDEX IF NOT EXISTS idx_callrecord_caller_number ON callrecord(caller_number);
CREATE INDEX IF NOT EXISTS idx_callrecord_created_at ON callrecord(created_at DESC);
```

**Note:** 
- The `call_id` field has a UNIQUE constraint to prevent duplicate imports
- **If you're getting "column call_metadata does not exist" error, run the `ALTER TABLE` statement above**
- The backend will automatically create this table on startup if using SQLModel's `create_all()`, but running the migration manually ensures proper indexes are in place
- The schema includes indexes on `realtor_number`, `caller_number`, and `created_at` for efficient queries

### Migration 2: Carrier Column for Call Forwarding

To enable carrier-specific call forwarding, run this SQL migration:

```sql
-- Add carrier column to PropertyManager table
ALTER TABLE propertymanager 
ADD COLUMN IF NOT EXISTS carrier TEXT;

-- Add carrier column to Realtor table
ALTER TABLE realtor 
ADD COLUMN IF NOT EXISTS carrier TEXT;
```

**Note:**
- The `carrier` column stores the user's mobile carrier (e.g., "AT&T", "Verizon", "T-Mobile")
- This allows the backend to generate carrier-specific forwarding codes
- Users can update their carrier via `PATCH /call-forwarding-state` with `{ "carrier": "AT&T" }`
- If carrier is not set, backend defaults to AT&T (GSM) codes, but frontend should prompt for carrier selection

**See `migration_add_carrier_column.sql` for the complete migration script.**

### Migration 3: Property Tour Booking System

To enable the property tour booking system, run `migration_property_tour_booking.sql`:

```sql
-- See migration_property_tour_booking.sql for complete migration
-- This adds:
-- - PropertyTourBooking table
-- - AvailabilitySlot table
-- - PropertyAssignment table
-- - timezone and calendar_preferences columns to PropertyManager and Realtor
```

**Note:**
- The migration creates all necessary tables and indexes
- Calendar preferences default to 9 AM - 5 PM working hours, 30-minute slots
- Users can customize their timezone and working hours after migration

