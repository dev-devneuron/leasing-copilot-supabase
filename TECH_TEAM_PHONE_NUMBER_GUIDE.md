# Tech Team Phone Number Management Guide

Complete guide for the tech team on managing phone numbers for Property Managers and Realtors.

---

## Overview

The phone number system works as follows:
1. **Property Managers** request phone numbers via dashboard (`POST /request-phone-number`)
2. **Tech Team** purchases numbers and adds them to the database
3. **Property Managers** assign purchased numbers to themselves or their realtors
4. **Chatbot** automatically uses the correct data based on assigned number

---

## Admin Endpoints

All admin endpoints should be protected with admin authentication in production. Tech team can use curl, Postman, or any HTTP client.

**Base URL:**
- **Production:** `https://leasing-copilot-mvp.onrender.com`
- **Development:** `http://localhost:8000`

---

## 1. View Phone Number Requests

**Endpoint:** `GET /admin/all-phone-number-requests?status=pending`

**Query Parameters:**
- `status` (optional): Filter by status (`pending`, `fulfilled`, `cancelled`)

**Response:**
```json
{
  "requests": [
    {
      "request_id": 1,
      "property_manager_id": 1,
      "country_code": "+1",
      "area_code": "412",
      "status": "pending",
      "notes": "Need number for new realtor",
      "requested_at": "2024-01-15T10:30:00Z",
      "fulfilled_at": null
    }
  ]
}
```

**Example (curl):**
```bash
curl -X GET "https://your-backend-url.com/admin/all-phone-number-requests?status=pending" \
  -H "Content-Type: application/json"
```

---

## 2. Add Purchased Phone Number (Recommended)

**Endpoint:** `POST /admin/add-purchased-number`

Use this endpoint when you've already purchased a phone number from any platform (Twilio, other providers, etc.) and just need to add it to the database.

**Request:**
```json
{
  "property_manager_id": 1,
  "phone_number": "+14125551234",
  "twilio_sid": "PN1234567890abcdef",  // Optional - if purchased from Twilio
  "vapi_phone_number_id": "vapi_123",  // Optional - if registered with VAPI
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
    "vapi_phone_number_id": "vapi_123",
    "notes": "Purchased from Twilio"
  }'
```

**Notes:**
- Phone number must be in E.164 format (e.g., `+14125551234`)
- If `twilio_sid` is not provided, a unique SID will be auto-generated
- The number will appear as "available" for the PM to assign
- Any pending requests for that PM will be automatically marked as "fulfilled"

---

## 3. Purchase Phone Number from Twilio (Automated)

**Endpoint:** `POST /admin/purchase-phone-number`

This endpoint automatically purchases a number from Twilio and registers it with VAPI. Use this if you want the system to handle everything automatically.

**Request:**
```json
{
  "property_manager_id": 1,
  "area_code": "412",  // Optional - defaults to "412"
  "notes": "Purchased via admin endpoint"  // Optional
}
```

**Response:**
```json
{
  "message": "Phone number purchased and added successfully",
  "purchased_phone_number_id": 1,
  "phone_number": "+14125551234",
  "twilio_sid": "PN1234567890abcdef",
  "vapi_phone_number_id": "vapi_123",
  "status": "available",
  "property_manager_id": 1
}
```

**Example (curl):**
```bash
curl -X POST https://your-backend-url.com/admin/purchase-phone-number \
  -H "Content-Type: application/json" \
  -d '{
    "property_manager_id": 1,
    "area_code": "412",
    "notes": "Purchased via admin endpoint"
  }'
```

**Requirements:**
- Twilio credentials must be configured (`TWILIO_ACCOUNT_SID2`, `TWILIO_AUTH_TOKEN2`)
- VAPI credentials must be configured (`VAPI_API_KEY2`, `VAPI_ASSISTANT_ID2`)
- The endpoint will automatically:
  1. Search for available numbers in the specified area code
  2. Purchase the number from Twilio
  3. Register it with VAPI
  4. Add it to the database

---

## 4. View All Purchased Numbers

**Endpoint:** `GET /admin/all-purchased-numbers?property_manager_id=1&status=available`

**Query Parameters:**
- `property_manager_id` (optional): Filter by Property Manager
- `status` (optional): Filter by status (`available`, `assigned`, `inactive`)

**Response:**
```json
{
  "purchased_numbers": [
    {
      "purchased_phone_number_id": 1,
      "property_manager_id": 1,
      "phone_number": "+14125551234",
      "twilio_sid": "PN1234567890abcdef",
      "vapi_phone_number_id": "vapi_123",
      "status": "available",
      "assigned_to_type": null,
      "assigned_to_id": null,
      "purchased_at": "2024-01-15T10:30:00Z",
      "assigned_at": null,
      "notes": "Purchased from Twilio"
    }
  ]
}
```

**Example (curl):**
```bash
# View all available numbers
curl -X GET "https://your-backend-url.com/admin/all-purchased-numbers?status=available" \
  -H "Content-Type: application/json"

# View all numbers for a specific PM
curl -X GET "https://your-backend-url.com/admin/all-purchased-numbers?property_manager_id=1" \
  -H "Content-Type: application/json"
```

---

## Workflow

### Step 1: Check for Pending Requests

```bash
curl -X GET "https://your-backend-url.com/admin/all-phone-number-requests?status=pending" \
  -H "Content-Type: application/json"
```

### Step 2: Purchase/Add Phone Number

**Option A: Add already-purchased number (Recommended)**
```bash
curl -X POST https://your-backend-url.com/admin/add-purchased-number \
  -H "Content-Type: application/json" \
  -d '{
    "property_manager_id": 1,
    "phone_number": "+14125551234",
    "twilio_sid": "PN1234567890abcdef",
    "vapi_phone_number_id": "vapi_123",
    "notes": "Purchased from Twilio"
  }'
```

**Option B: Auto-purchase from Twilio**
```bash
curl -X POST https://your-backend-url.com/admin/purchase-phone-number \
  -H "Content-Type: application/json" \
  -d '{
    "property_manager_id": 1,
    "area_code": "412",
    "notes": "Purchased via admin endpoint"
  }'
```

### Step 3: Verify Number Was Added

```bash
curl -X GET "https://your-backend-url.com/admin/all-purchased-numbers?property_manager_id=1&status=available" \
  -H "Content-Type: application/json"
```

The number should now appear as "available" and the PM can assign it to themselves or a realtor via the dashboard.

---

## Important Notes

1. **Phone Number Format:** Always use E.164 format (e.g., `+14125551234`)
2. **Status Values:**
   - `available` - Number is available for assignment
   - `assigned` - Number is assigned to a PM or Realtor
   - `inactive` - Number is inactive (not in use)
3. **Automatic Request Fulfillment:** When you add a purchased number, any pending requests for that PM are automatically marked as "fulfilled"
4. **VAPI Registration:** If you're purchasing from Twilio, make sure to register the number with VAPI using the `vapi_phone_number_id` field
5. **Twilio SID:** If the number wasn't purchased from Twilio, you can leave `twilio_sid` empty and a unique SID will be auto-generated

---

## Troubleshooting

### Number Already Exists
If you get an error that the number already exists, check:
```bash
curl -X GET "https://your-backend-url.com/admin/all-purchased-numbers" \
  -H "Content-Type: application/json"
```

### PM Not Found
Verify the PM exists by checking the database or contacting the team.

### VAPI Registration Failed
If auto-purchase fails at VAPI registration step:
1. The Twilio number will be automatically cleaned up
2. You can manually register with VAPI and use `/admin/add-purchased-number` instead

---

## Security Notes

⚠️ **Important:** These endpoints should be protected with admin authentication in production. Currently, they are open for development purposes only.

**Recommended Implementation:**
- Add admin JWT token validation
- Restrict access to specific IP addresses
- Use API keys for admin endpoints
- Log all admin actions for audit purposes

