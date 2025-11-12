# Tech Team Guide: Adding Phone Numbers for Property Managers

## Overview

This guide explains how to add purchased phone numbers to the database so Property Managers can see and assign them. **No admin console needed** - just use simple HTTP requests.

---

## Quick Start (3 Steps)

### Step 1: Find the Property Manager ID

You need to know which PM the number is for. You can get this from:
- The PM's email address
- The demo request they submitted
- The phone number request they made

**Option A: Get PM ID from email (if you know their email)**
```bash
# Query the database or ask the backend team
# PM ID is usually visible in the phone number requests
```

**Option B: Check pending phone number requests**
```bash
curl https://your-backend-url.com/admin/all-phone-number-requests?status=pending
```

This will show you:
- `property_manager_id` - The PM ID you need
- `country_code` - What country code they requested
- `area_code` - What area code they requested
- `notes` - Any special notes

**Example Response:**
```json
{
  "requests": [
    {
      "request_id": 1,
      "property_manager_id": 5,  // ← This is what you need!
      "country_code": "+1",
      "area_code": "412",
      "status": "pending",
      "notes": "Need number for new realtor",
      "requested_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

---

### Step 2: Purchase the Phone Number

Purchase the phone number from **any platform**:
- Twilio Console
- Another phone provider
- Any other platform

**What you'll get:**
- Phone number (e.g., `+14125551234`)
- Provider SID/ID (e.g., Twilio SID: `PN1234567890abcdef`)
- (Optional) VAPI phone number ID if you register it with VAPI

---

### Step 3: Add to Database

Use the simple endpoint to add the number:

```bash
curl -X POST https://your-backend-url.com/admin/add-purchased-number \
  -H "Content-Type: application/json" \
  -d '{
    "property_manager_id": 5,
    "phone_number": "+14125551234",
    "twilio_sid": "PN1234567890abcdef",
    "notes": "Purchased from Twilio for request #1"
  }'
```

**That's it!** The number is now in the database and the PM can see it.

---

## Complete Example Workflow

### Scenario: PM requested a phone number

**1. Check what PMs need numbers:**
```bash
curl https://your-backend-url.com/admin/all-phone-number-requests?status=pending
```

**Response:**
```json
{
  "requests": [
    {
      "request_id": 1,
      "property_manager_id": 5,
      "country_code": "+1",
      "area_code": "412",
      "status": "pending",
      "notes": "Need number for new realtor"
    }
  ]
}
```

**2. Purchase number from Twilio (or any platform):**
- Go to Twilio Console
- Buy a number in area code 412
- Get the number: `+14125551234`
- Get the SID: `PN1234567890abcdef`

**3. Add to database:**
```bash
curl -X POST https://your-backend-url.com/admin/add-purchased-number \
  -H "Content-Type: application/json" \
  -d '{
    "property_manager_id": 5,
    "phone_number": "+14125551234",
    "twilio_sid": "PN1234567890abcdef",
    "notes": "Purchased from Twilio for request #1"
  }'
```

**Response:**
```json
{
  "message": "Phone number +14125551234 added successfully and is now available for assignment",
  "purchased_phone_number_id": 1,
  "phone_number": "+14125551234",
  "status": "available",
  "property_manager_id": 5,
  "pm_name": "John Smith",
  "pm_email": "john@example.com"
}
```

**4. What happens automatically:**
- ✅ Number is added with status "available"
- ✅ PM's pending request #1 is marked as "fulfilled"
- ✅ PM can now see the number in their dashboard
- ✅ PM can assign it to themselves or a realtor

---

## Endpoint Details

### POST `/admin/add-purchased-number`

**URL:** `https://your-backend-url.com/admin/add-purchased-number`

**Method:** `POST`

**Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "property_manager_id": 5,              // Required: PM ID
  "phone_number": "+14125551234",        // Required: E.164 format
  "twilio_sid": "PN1234567890abcdef",    // Optional: If from Twilio
  "vapi_phone_number_id": "vapi_123",    // Optional: If registered with VAPI
  "notes": "Purchased from Twilio"       // Optional: Any notes
}
```

**Required Fields:**
- `property_manager_id` - The PM's ID (get from requests endpoint)
- `phone_number` - Phone number in E.164 format (e.g., `+14125551234`)

**Optional Fields:**
- `twilio_sid` - Only if purchased from Twilio
- `vapi_phone_number_id` - Only if already registered with VAPI
- `notes` - Any internal notes

**Success Response (200):**
```json
{
  "message": "Phone number +14125551234 added successfully and is now available for assignment",
  "purchased_phone_number_id": 1,
  "phone_number": "+14125551234",
  "status": "available",
  "property_manager_id": 5,
  "pm_name": "John Smith",
  "pm_email": "john@example.com"
}
```

**Error Responses:**

**404 - PM Not Found:**
```json
{
  "detail": "Property Manager not found"
}
```

**400 - Invalid Phone Number:**
```json
{
  "detail": "Phone number should be in E.164 format (e.g., +14125551234)"
}
```

**400 - Duplicate Number:**
```json
{
  "detail": "Phone number +14125551234 already exists in database"
}
```

---

## Using Postman (Alternative to curl)

1. **Create New Request:**
   - Method: `POST`
   - URL: `https://your-backend-url.com/admin/add-purchased-number`

2. **Set Headers:**
   - Key: `Content-Type`
   - Value: `application/json`

3. **Set Body:**
   - Select "raw" and "JSON"
   - Paste:
   ```json
   {
     "property_manager_id": 5,
     "phone_number": "+14125551234",
     "twilio_sid": "PN1234567890abcdef",
     "notes": "Purchased from Twilio"
   }
   ```

4. **Send Request**

---

## Using Python (Alternative)

```python
import requests

url = "https://your-backend-url.com/admin/add-purchased-number"
data = {
    "property_manager_id": 5,
    "phone_number": "+14125551234",
    "twilio_sid": "PN1234567890abcdef",
    "notes": "Purchased from Twilio"
}

response = requests.post(url, json=data)
print(response.json())
```

---

## Common Scenarios

### Scenario 1: Number from Twilio

```bash
curl -X POST https://your-backend-url.com/admin/add-purchased-number \
  -H "Content-Type: application/json" \
  -d '{
    "property_manager_id": 5,
    "phone_number": "+14125551234",
    "twilio_sid": "PN1234567890abcdef",
    "notes": "Purchased from Twilio"
  }'
```

### Scenario 2: Number from Another Provider

```bash
curl -X POST https://your-backend-url.com/admin/add-purchased-number \
  -H "Content-Type: application/json" \
  -d '{
    "property_manager_id": 5,
    "phone_number": "+14125551234",
    "notes": "Purchased from alternative provider"
  }'
```

**Note:** If `twilio_sid` is not provided, the system will auto-generate one.

### Scenario 3: Number Already Registered with VAPI

```bash
curl -X POST https://your-backend-url.com/admin/add-purchased-number \
  -H "Content-Type: application/json" \
  -d '{
    "property_manager_id": 5,
    "phone_number": "+14125551234",
    "twilio_sid": "PN1234567890abcdef",
    "vapi_phone_number_id": "vapi_123456",
    "notes": "Already registered with VAPI"
  }'
```

---

## Verification

After adding a number, verify it was added correctly:

```bash
# Check all purchased numbers for a PM
curl https://your-backend-url.com/admin/all-purchased-numbers?property_manager_id=5&status=available
```

You should see your newly added number in the response.

---

## Troubleshooting

### "Property Manager not found"
- **Solution:** Check the `property_manager_id` is correct
- **How to find:** Use `/admin/all-phone-number-requests` to see PM IDs

### "Phone number already exists"
- **Solution:** The number is already in the database
- **Check:** Use `/admin/all-purchased-numbers` to see existing numbers

### "Invalid phone number format"
- **Solution:** Use E.164 format: `+14125551234`
- **Format:** `+` followed by country code and number (no spaces, dashes, or parentheses)

### Phone number shows "NA" in frontend
- **Solution:** Make sure you're sending `phone_number` in the request body
- **Check:** Verify the response includes the phone number

---

## Summary

**The process is simple:**

1. **Find PM ID** → Check pending requests
2. **Purchase number** → From any platform
3. **Add to database** → One curl command
4. **Done!** → PM can see and assign it

**No admin console needed** - just use curl, Postman, or any HTTP client!

