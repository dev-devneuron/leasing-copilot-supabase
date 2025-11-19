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
10. [Admin Endpoints](#-admin-endpoints-tech-team)

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

**Response**
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
  "after_hours_enabled": true,
  "business_forwarding_enabled": true,
  "carrier": "AT&T",              // Optional; update user's carrier
  "realtor_id": 99,               // Optional; only PMs can set this
  "notes": "Enabled after-hours from dashboard",
  "confirmation_status": "success",  // "success" | "failure" | "pending"
  "failure_reason": "Carrier busy tone" // Only when confirmation_status = "failure"
}
```

At least one of `after_hours_enabled`, `business_forwarding_enabled`, `carrier`, or `confirmation_status` must be present. When `realtor_id` is set, the PM must own that realtor. The endpoint updates database flags and carrier setting; carriers are controlled via dial codes returned in the response.

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

#### 1. Carrier Selection (Onboarding/Settings)

**First-time setup:** Collect the user's carrier during onboarding or in settings:

```javascript
// Get list of supported carriers
async function getSupportedCarriers() {
  const response = await fetch('/call-forwarding-carriers', {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  const data = await response.json();
  return data.carrier_details; // Use this to populate a dropdown
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

- **Always use carrier-specific codes from the backend** - Never hardcode dial codes in the frontend. The backend generates the correct codes based on the user's carrier.
- **Handle carrier limitations gracefully:**
  - Check `forwarding_codes.supports_25_second_forwarding` before showing "Business Hours Forwarding" button
  - For Google Fi, show app instructions instead of dial codes
  - For Verizon/Xfinity, explain that only unconditional forwarding is available
- **Carrier selection is required:** Prompt users to select their carrier before enabling forwarding. Store it via `PATCH /call-forwarding-state` with `{ "carrier": "AT&T" }`.
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
- **Default carrier:** If carrier is not set, backend defaults to AT&T (GSM) codes. However, frontend should always prompt for carrier selection to ensure accuracy.

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

**Responses**

```json
{
  "message": "Call transcript and recording removed",
  "call_id": "vapi_call_123",
  "hard_delete": false
}

{
  "message": "Call record permanently deleted",
  "call_id": "vapi_call_123",
  "hard_delete": true
}
```

**UI Guidance**
- Present two destructive actions (“Remove transcript & audio” vs. “Delete record”) with confirmation dialogs.
- After a soft delete, refresh the list so the row remains but transcript/recording columns are empty; hard deletes remove the row entirely.
- Backend already enforces ownership (PMs manage their own + realtors’ calls; Realtors only their own), so surface a toast if API returns 403.

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

