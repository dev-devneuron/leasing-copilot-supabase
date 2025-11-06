# Frontend & Backend Integration Guide
## Newly Implemented Features - Complete API Documentation

This guide documents all newly implemented backend endpoints for user profile, realtor management, and property management features.

---

## 🔐 Authentication

All endpoints require JWT authentication. Include the token in the Authorization header:
```
Authorization: Bearer <jwt_token>
```

The token is obtained from Supabase Auth after login.

---

## 👤 User Profile Endpoint

### Get Current User Information
```http
GET /user-profile
Authorization: Bearer <jwt_token>
```

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

**Use Case:** Display the logged-in user's name and details in the frontend.

**Example:**
```javascript
const response = await fetch('/user-profile', {
  headers: { 'Authorization': `Bearer ${token}` }
});
const { user } = await response.json();
console.log(user.name); // Display user name
```

---

## 🏢 Property Manager - Realtor Management

### 1. Get Managed Realtors
```http
GET /property-manager/realtors
Authorization: Bearer <pm_jwt_token>
```

**Response:**
```json
{
  "realtors": [
    {
      "id": 1,
      "name": "Sarah Johnson",
      "email": "sarah.johnson@testcompany.com",
      "contact": "555-0123",
      "status": "active"
    }
  ]
}
```

### 2. Update Realtor Details
```http
PATCH /property-manager/realtors/{realtor_id}
Authorization: Bearer <pm_jwt_token>
Content-Type: application/json

{
  "name": "Sarah Johnson Updated",
  "contact": "555-9999",
  "email": "sarah.new@example.com",
  "password": "newPassword123"
}
```

**Notes:**
- All fields are optional - only include fields you want to update
- Email and password updates also update Supabase Auth
- Only Property Managers can update realtors they manage

**Response:**
```json
{
  "message": "Realtor updated successfully",
  "realtor_id": 1,
  "updated_fields": ["name", "contact", "email"],
  "realtor": {
    "id": 1,
    "name": "Sarah Johnson Updated",
    "email": "sarah.new@example.com",
    "contact": "555-9999"
  }
}
```

**Example:**
```javascript
const response = await fetch(`/property-manager/realtors/${realtorId}`, {
  method: 'PATCH',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    name: 'New Name',
    contact: '555-1234',
    email: 'new@example.com',
    password: 'newPassword123'  // Optional
  })
});
```

### 3. Delete Realtor
```http
DELETE /property-manager/realtors/{realtor_id}
Authorization: Bearer <pm_jwt_token>
```

**What happens:**
- All properties assigned to the realtor are moved back to the Property Manager
- All bookings are unassigned (realtor_id set to NULL)
- All sources and rule chunks for the realtor are deleted
- The realtor record is deleted from the database
- **Note:** The Supabase Auth account is NOT deleted (they can still login but won't have access)

**Response:**
```json
{
  "message": "Realtor 'Sarah Johnson' deleted successfully",
  "realtor_id": 1,
  "realtor_name": "Sarah Johnson",
  "realtor_email": "sarah.johnson@testcompany.com",
  "summary": {
    "properties_reassigned": 5,
    "properties_reassigned_ids": [101, 102, 103, 104, 105],
    "bookings_unassigned": 3,
    "bookings_unassigned_ids": [201, 202, 203],
    "rule_chunks_deleted": 12,
    "sources_deleted": 1
  },
  "note": "The user account in Supabase Auth still exists. They cannot access the system but their auth account remains."
}
```

---

## 🏠 Property Manager - Property Management

### 1. Update Property Details (Comprehensive - FIXED)
```http
PATCH /properties/{property_id}
Authorization: Bearer <pm_jwt_token>
Content-Type: application/json

{
  "address": "123 New Street, Seattle, WA",
  "price": 2500,
  "bedrooms": 3,
  "bathrooms": 2.5,
  "square_feet": 1200,
  "lot_size_sqft": 5000,
  "year_built": 2020,
  "property_type": "Apartment",
  "listing_status": "Available",
  "days_on_market": 25,
  "listing_date": "2024-01-15",
  "listing_id": "MLS000123",
  "features": ["Pool", "Gym", "Parking", "Elevator"],
  "description": "Beautiful apartment in downtown Seattle",
  "image_url": "https://example.com/image.jpg",
  "agent": {
    "name": "Jane Smith",
    "phone": "555-9876",
    "email": "jane@example.com"
  }
}
```

**Notes:**
- ✅ **FIXED:** Now properly persists all updates to database
- All fields are optional - only include fields you want to update
- Property Managers can edit properties they own OR properties assigned to their realtors
- `listing_status` must be one of: `"Available"`, `"For Sale"`, `"For Rent"`, `"Sold"`, `"Rented"`
- To remove agent, send `"agent": null`
- You can update any combination of fields in a single request
- Supports partial updates - only send fields you want to change

**Response:**
```json
{
  "message": "Property updated successfully",
  "property_id": 1,
  "updated_fields": ["price", "bedrooms", "listing_status", "agent"],
  "property": {
    "id": 1,
    "address": "123 New Street, Seattle, WA",
    "price": 2500,
    "bedrooms": 3,
    "bathrooms": 2.5,
    "square_feet": 1200,
    "lot_size_sqft": 5000,
    "year_built": 2020,
    "property_type": "Apartment",
    "listing_status": "Available",
    "days_on_market": 25,
    "listing_date": "2024-01-15",
    "listing_id": "MLS000123",
    "features": ["Pool", "Gym", "Parking"],
    "description": "Beautiful property description...",
    "image_url": "https://example.com/image.jpg",
    "agent": {
      "name": "Jane Smith",
      "phone": "555-9876",
      "email": "jane@example.com"
    }
  }
}
```

**Error Responses:**
- `400` - Bad Request (validation errors, empty body, invalid status)
- `403` - Forbidden (no access to property)
- `404` - Not Found (property doesn't exist)
- `500` - Internal Server Error

All errors return:
```json
{
  "detail": "Error message here"
}
```

**Example:**
```javascript
// Update multiple fields at once
const response = await fetch(`/properties/${propertyId}`, {
  method: 'PATCH',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    price: 2500,
    listing_status: 'Sold',
    days_on_market: 30,
    address: '123 Main St'
  })
});

if (response.ok) {
  const data = await response.json();
  console.log('Updated property:', data.property);
  // Use data.property to update your UI
} else {
  const error = await response.json();
  console.error('Error:', error.detail);
}
```

**Important Notes:**
- ✅ **FIXED:** Uses `flag_modified()` to ensure SQLAlchemy detects JSONB changes
- ✅ Supports partial updates - only send fields you want to change
- ✅ All fields are optional
- ✅ Empty strings and 0 values are accepted
- ✅ `null` values are ignored (except for `agent: null` which removes the agent)
- ✅ Response includes the full updated property object
- ✅ Property ID must be an integer
- ✅ All updates are now properly persisted to the database

### 2. Update Property Status Only
```http
PATCH /properties/{property_id}/status
Authorization: Bearer <pm_jwt_token>
Content-Type: application/json

{
  "listing_status": "Sold"
}
```

**Status Options:** `"Available"`, `"For Sale"`, `"For Rent"`, `"Sold"`, `"Rented"`

**Response:**
```json
{
  "message": "Property status updated to Sold",
  "property_id": 1,
  "new_status": "Sold"
}
```

### 3. Update or Remove Property Agent
```http
PATCH /properties/{property_id}/agent
Authorization: Bearer <pm_jwt_token>
Content-Type: application/json

{
  "agent": {
    "name": "Jane Smith",
    "phone": "555-9876",
    "email": "jane@example.com"
  }
}
```

**To Remove Agent:**
```json
{
  "agent": null
}
```

**Response:**
```json
{
  "message": "Property agent updated successfully",
  "property_id": 1,
  "agent": {
    "name": "Jane Smith",
    "phone": "555-9876",
    "email": "jane@example.com"
  }
}
```

### 4. Delete Property
```http
DELETE /properties/{property_id}
Authorization: Bearer <pm_jwt_token>
```

**Notes:**
- Only Property Managers can delete properties
- PM can delete their own properties OR properties assigned to their realtors
- This action cannot be undone

**Response:**
```json
{
  "message": "Property '123 Main St, Seattle, WA' deleted successfully",
  "property_id": 1,
  "deleted_address": "123 Main St, Seattle, WA"
}
```

**Example:**
```javascript
if (confirm('Are you sure you want to delete this property?')) {
  const response = await fetch(`/properties/${propertyId}`, {
    method: 'DELETE',
    headers: { 'Authorization': `Bearer ${token}` }
  });
  
  if (response.ok) {
    const data = await response.json();
    console.log(data.message);
    // Refresh property list
  }
}
```

---

## 📊 Property Update Fields Reference

The following fields can be updated via `PATCH /properties/{property_id}`:

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `address` | string | Property address | `"123 Main St, Seattle, WA"` |
| `price` | number | Property price | `250000` |
| `bedrooms` | number | Number of bedrooms | `3` |
| `bathrooms` | number | Number of bathrooms | `2.5` |
| `square_feet` | number | Square footage | `1200` |
| `lot_size_sqft` | number | Lot size in square feet | `5000` |
| `year_built` | number | Year the property was built | `2020` |
| `property_type` | string | Type of property | `"Apartment"` or `"House"` |
| `listing_status` | string | Status (see valid values below) | `"Available"` |
| `days_on_market` | number | Days the property has been on market | `25` |
| `listing_date` | string | ISO date string | `"2024-01-15"` |
| `listing_id` | string | MLS or listing ID | `"MLS000123"` |
| `features` | array | Array of feature strings | `["Pool", "Gym", "Parking"]` |
| `description` | string | Property description | `"Beautiful property..."` |
| `image_url` | string | URL to property image | `"https://example.com/image.jpg"` |
| `agent` | object/null | Agent object or null to remove | See agent format below |

**Valid `listing_status` values:**
- `"Available"`
- `"For Sale"`
- `"For Rent"`
- `"Sold"`
- `"Rented"`

**Agent object format:**
```json
{
  "name": "Jane Smith",
  "phone": "555-9876",
  "email": "jane@example.com"
}
```

---

## 🔄 Error Handling

All endpoints return standard HTTP status codes:
- `200` - Success
- `400` - Bad Request (validation errors)
- `401` - Unauthorized (invalid/missing token)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found
- `500` - Internal Server Error

Error responses follow this format:
```json
{
  "detail": "Error message here"
}
```

**Example Error Handling:**
```javascript
try {
  const response = await fetch(`/properties/${propertyId}`, {
    method: 'PATCH',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(updateData)
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Update failed');
  }

  const data = await response.json();
  console.log('Success:', data.message);
  // Update UI with data.property
} catch (error) {
  console.error('Error:', error.message);
  // Show error to user
  alert(`Failed to update property: ${error.message}`);
}
```

---

## ✅ Testing Checklist

1. **User Profile:**
   - [ ] `GET /user-profile` returns correct user name and details
   - [ ] Works for both Property Managers and Realtors

2. **Realtor Management:**
   - [ ] PM can fetch list of managed realtors
   - [ ] PM can update realtor name, contact, email, password
   - [ ] Email and password updates work in Supabase Auth
   - [ ] PM can delete realtor (properties are reassigned)

3. **Property Management:**
   - [ ] PM can update property price (cost)
   - [ ] PM can update property address
   - [ ] PM can update property bedrooms, bathrooms
   - [ ] PM can update property features array
   - [ ] PM can update property status
   - [ ] PM can add/remove/update property agent
   - [ ] PM can delete properties (own and from realtors)
   - [ ] Updates persist correctly in database
   - [ ] PM cannot update properties they don't have access to

---

## 🚀 Quick Start Examples

### Get User Profile
```javascript
const token = localStorage.getItem('access_token');
const response = await fetch('/user-profile', {
  headers: { 'Authorization': `Bearer ${token}` }
});
const { user } = await response.json();
console.log('Logged in as:', user.name);
```

### Update Property Price
```javascript
const response = await fetch(`/properties/${propertyId}`, {
  method: 'PATCH',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    price: 250000  // Update only the price
  })
});

if (response.ok) {
  const data = await response.json();
  console.log('New price:', data.property.price);
}
```

### Update Multiple Property Fields
```javascript
const response = await fetch(`/properties/${propertyId}`, {
  method: 'PATCH',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    price: 250000,
    bedrooms: 3,
    bathrooms: 2.5,
    address: '123 New Address St',
    features: ['Pool', 'Gym', 'Parking']
  })
});
```

### Update Realtor
```javascript
const response = await fetch(`/property-manager/realtors/${realtorId}`, {
  method: 'PATCH',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    name: 'Updated Name',
    contact: '555-1234'
  })
});
```

### Delete Property
```javascript
if (confirm('Are you sure you want to delete this property?')) {
  const response = await fetch(`/properties/${propertyId}`, {
    method: 'DELETE',
    headers: { 'Authorization': `Bearer ${token}` }
  });
  
  if (response.ok) {
    // Refresh property list
    window.location.reload();
  }
}
```

---

## 📌 Key Points

- ✅ **User Profile:** Use `/user-profile` to get current user's name and details
- ✅ **Realtor Management:** PM can update realtor name, contact, email, and password
- ✅ **Property Updates:** PM can update ALL property fields comprehensively
- ✅ **Property Deletion:** PM can delete properties (own and from realtors)
- ✅ **Flexible Updates:** Update any combination of fields in a single request
- ✅ **Access Control:** PM can only edit/delete properties they own or from their realtors
- ✅ **FIXED:** Property updates now properly persist to database using `flag_modified()`
- ✅ **Partial Updates:** Only send fields you want to change
- ✅ **Complete Response:** Response includes full updated property object for immediate UI update

---

## 🔧 Technical Details

### Property Update Fix
The property update endpoint was fixed to properly persist changes to the JSONB `listing_metadata` column by:
1. Using `flag_modified()` from SQLAlchemy to mark the JSONB field as changed
2. Creating a new dict object to ensure SQLAlchemy detects the change
3. Proper session management with `session.add()` before commit

This ensures all property field updates (price, address, features, etc.) are correctly saved to the database.
