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
8. [Admin Endpoints](#-admin-endpoints-tech-team)

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
      "email": "sarah@example.com"
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
  "assigned_to_id": 5
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
  "user_id": 1
}
```

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
