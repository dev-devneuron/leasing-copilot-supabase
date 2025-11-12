# Frontend & Backend Integration Guide
## Complete API Documentation

This guide documents all backend endpoints for user profile, realtor management, property management, **AI-powered listing uploads**, and **demo booking system**.

---

## 🎯 Demo Booking System (Public - No Auth Required)

### Overview

The system uses a "Book a Demo" approach instead of direct sign-up:
1. Visitors book a demo through the public endpoint
2. Admin team reviews and schedules demos
3. After demo, PMs are onboarded if they're interested
4. Demo requests can be marked as "converted" when PM account is created

### 1. Book a Demo (Public Endpoint)

**Endpoint:**
```http
POST /book-demo
Content-Type: application/json

{
  "name": "John Smith",
  "email": "john@example.com",
  "phone": "+14125551234",
  "company_name": "ABC Properties",  // Optional
  "preferred_date": "2024-01-15",  // Optional: YYYY-MM-DD format
  "preferred_time": "10:00 AM",  // Optional
  "timezone": "America/New_York",  // Optional
  "notes": "Interested in property management features"  // Optional
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
// Public landing page - Book Demo Form
async function bookDemo(formData) {
  const response = await fetch('/book-demo', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      name: formData.name,
      email: formData.email,
      phone: formData.phone,
      company_name: formData.companyName || null,
      preferred_date: formData.preferredDate || null,  // YYYY-MM-DD
      preferred_time: formData.preferredTime || null,
      timezone: formData.timezone || null,
      notes: formData.notes || null
    })
  });
  
  if (response.ok) {
    const data = await response.json();
    // Show success message
    alert(data.message);
    // Clear form or redirect
  } else {
    const error = await response.json();
    alert(`Error: ${error.detail}`);
  }
}
```

**UI Requirements:**
- Replace "Sign Up" button with "Book a Demo" button
- Create a demo booking form with:
  - Name (required)
  - Email (required)
  - Phone (required)
  - Company Name (optional)
  - Preferred Date (optional date picker)
  - Preferred Time (optional time picker)
  - Timezone (optional dropdown)
  - Notes/Message (optional textarea)
- Show success message after submission
- No authentication required - this is a public endpoint

---

### 2. Admin: View Demo Requests

**Endpoint:**
```http
GET /demo-requests?status=pending
Authorization: Bearer <admin_token>
```

**Query Parameters:**
- `status` (optional): Filter by status - `pending`, `scheduled`, `completed`, `cancelled`, `converted`

**Response:**
```json
{
  "demo_requests": [
    {
      "demo_request_id": 1,
      "name": "John Smith",
      "email": "john@example.com",
      "phone": "+14125551234",
      "company_name": "ABC Properties",
      "preferred_date": "2024-01-15",
      "preferred_time": "10:00 AM",
      "timezone": "America/New_York",
      "notes": "Interested in property management features",
      "status": "pending",
      "scheduled_at": null,
      "completed_at": null,
      "converted_to_pm_id": null,
      "converted_at": null,
      "requested_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

**Frontend Implementation:**
```javascript
// Admin Dashboard - View Demo Requests
async function getDemoRequests(status = null) {
  const url = status ? `/demo-requests?status=${status}` : '/demo-requests';
  const response = await fetch(url, {
    headers: { 'Authorization': `Bearer ${adminToken}` }
  });
  
  if (response.ok) {
    const data = await response.json();
    // Display demo requests in a table
    data.demo_requests.forEach(req => {
      console.log(`${req.name} - ${req.status}`);
    });
  }
}
```

---

### 3. Admin: Update Demo Request

**Endpoint:**
```http
PATCH /demo-requests/{demo_request_id}
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "status": "scheduled",  // pending, scheduled, completed, cancelled, converted
  "scheduled_at": "2024-01-20T10:00:00Z",  // Optional: ISO datetime
  "completed_at": "2024-01-20T11:00:00Z",  // Optional: ISO datetime
  "converted_to_pm_id": 5,  // Optional: PM ID if converted
  "notes": "Demo completed successfully"  // Optional
}
```

**Response:**
```json
{
  "message": "Demo request updated successfully",
  "demo_request_id": 1,
  "status": "scheduled",
  "scheduled_at": "2024-01-20T10:00:00Z",
  "completed_at": null,
  "converted_to_pm_id": null
}
```

**Frontend Implementation:**
```javascript
// Admin Dashboard - Update Demo Request
async function updateDemoRequest(demoRequestId, updates) {
  const response = await fetch(`/demo-requests/${demoRequestId}`, {
    method: 'PATCH',
    headers: {
      'Authorization': `Bearer ${adminToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(updates)
  });
  
  if (response.ok) {
    const data = await response.json();
    alert(data.message);
    // Refresh demo requests list
    getDemoRequests();
  }
}

// Example: Mark as scheduled
updateDemoRequest(1, {
  status: "scheduled",
  scheduled_at: "2024-01-20T10:00:00Z"
});

// Example: Mark as converted (after creating PM account)
updateDemoRequest(1, {
  status: "converted",
  converted_to_pm_id: 5  // The PM ID created from this demo
});
```

**UI Requirements:**
- Admin dashboard to view all demo requests
- Filter by status (pending, scheduled, completed, cancelled, converted)
- Update status with dropdown
- Schedule demo with date/time picker
- Mark as completed after demo
- Link to PM account when converted
- Add internal notes

---

### Demo Request Status Flow

```
pending → scheduled → completed → converted
   ↓         ↓
cancelled  cancelled
```

**Status Meanings:**
- `pending`: New request, not yet reviewed
- `scheduled`: Demo has been scheduled
- `completed`: Demo was completed
- `cancelled`: Request was cancelled
- `converted`: Demo led to PM account creation

---

## 🔐 Authentication

Most endpoints require JWT authentication. Include the token in the Authorization header:
```
Authorization: Bearer <jwt_token>
```

The token is obtained from Supabase Auth after login.

**Note:** The `/book-demo` endpoint is **public** and does not require authentication.

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

---

## 📤 AI-Powered Listing Upload Feature

### Overview

The listing upload system uses **AI-powered parsing** to handle property/apartment data in various formats (JSON, CSV, TXT) with intelligent normalization. The system automatically:

- ✅ Handles malformed or inconsistent data formats
- ✅ Normalizes field names (e.g., "bedrooms" vs "beds" vs "bedroom_count")
- ✅ Extracts data from nested structures
- ✅ Validates and cleans data before storage
- ✅ Uses Vertex AI (Gemini models) for robust parsing of unstructured text files
- ✅ Falls back to Gemini API if Vertex AI is not configured
- ✅ Stores data in consistent format matching existing database schema

### Data Ownership & Assignment Flow

**Important:** All uploaded listings are stored against the Property Manager (PM) by default. The PM can then assign listings to their realtors as needed.

**Flow:**
1. **PM Uploads Listings** → Listings are stored in PM's source (owned by PM)
2. **PM Assigns to Realtors** → PM can assign specific listings to their managed realtors
3. **PM Can Unassign** → PM can unassign listings from realtors back to themselves
4. **Standalone Realtors** → Realtors without a PM (`is_standalone=True`) are essentially PMs themselves - they upload directly to their own source and manage their own listings

**Key Points:**
- ✅ Uploads default to PM's source (unless `assign_to_realtor_id` is specified during upload)
- ✅ PM maintains ownership and control over all uploaded listings
- ✅ PM can assign/unassign listings to/from realtors at any time
- ✅ Standalone realtors work independently with their own source

### How the Upload Button Works

#### 1. Navigation (Dashboard)

The "Upload" button in the PM dashboard is a navigation link:
- Located in the header section
- Uses React Router's `Link` component to navigate to `/uploadpage`
- No upload logic here; it just routes to the upload page

#### 2. Upload Page Functionality

The upload page supports two types of file uploads:

**A. Upload Rules**
- File Selection: Multiple files can be selected
- State Management: Selected files stored in `ruleFiles` state
- Upload Process:
  - Creates a FormData object
  - Appends all selected files with key "files"
  - Sends POST request to `/UploadRules` endpoint
  - Includes JWT token in Authorization header
- After Upload: Shows success message, displays uploaded file names, clears selection

**B. Upload Listings** ⭐ **NEW: AI-Powered Parser**
- File Selection: Multiple files can be selected
- State Management: Selected files stored in `listingFiles` state
- Upload Process:
  - Creates a FormData object
  - Appends all selected files with key "listing_file"
  - Sends POST request to `/UploadListings` or `/property-manager/upload-listings` endpoint
  - Includes JWT token in Authorization header
- **AI Processing:** Files are automatically parsed using AI to handle:
  - Various file formats (JSON, CSV, TXT)
  - Inconsistent column names
  - Malformed data
  - Missing fields
  - Nested data structures
- After Upload: Shows success message, displays uploaded file names, clears selection

### Upload Endpoints

#### 1. Realtor Upload Listings
```http
POST /UploadListings
Authorization: Bearer <realtor_jwt_token>
Content-Type: multipart/form-data

Form Data:
- listing_file: File (optional) - JSON, CSV, or TXT file
- listing_api_url: string (optional) - URL to fetch listings from API
```

**Notes:**
- Either `listing_file` OR `listing_api_url` must be provided
- Supports multiple file formats with AI-powered parsing
- Files are automatically normalized to match database schema
- Files are stored in Supabase storage at `realtors/{realtor_id}/listings/{filename}`

**Response:**
```json
{
  "message": "Listings uploaded & embedded"
}
```

**Example:**
```javascript
const formData = new FormData();
formData.append('listing_file', fileInput.files[0]);

const response = await fetch('/UploadListings', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`
  },
  body: formData
});

if (response.ok) {
  const data = await response.json();
  console.log(data.message);
  // Show success message to user
}
```

#### 2. Property Manager Upload Listings
```http
POST /property-manager/upload-listings
Authorization: Bearer <pm_jwt_token>
Content-Type: multipart/form-data

Form Data:
- listing_file: File (optional) - JSON, CSV, or TXT file
- listing_api_url: string (optional) - URL to fetch listings from API
- assign_to_realtor_id: integer (optional) - Directly assign listings to specific realtor during upload
```

**Notes:**
- Either `listing_file` OR `listing_api_url` must be provided
- **Default Behavior:** If `assign_to_realtor_id` is NOT provided, listings are stored in PM's own source (PM owns them)
- **Direct Assignment:** If `assign_to_realtor_id` is provided, listings go directly to that realtor's source (but PM can still reassign later)
- Uses same AI-powered parsing as realtor upload
- **Recommended:** Upload to PM's source first, then assign to realtors using the assignment endpoints (see below)

**Response:**
```json
{
  "message": "Listings uploaded successfully",
  "assigned_to": "property_manager" | "realtor",
  "realtor_id": 1,  // Only if assigned to realtor
  "source_id": 83,
  "count": 15
}
```

**Example:**
```javascript
const formData = new FormData();
formData.append('listing_file', fileInput.files[0]);
// Optional: Assign to specific realtor
formData.append('assign_to_realtor_id', realtorId);

const response = await fetch('/property-manager/upload-listings', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`
  },
  body: formData
});

if (response.ok) {
  const data = await response.json();
  console.log(`Uploaded ${data.count} listings`);
  console.log(`Assigned to: ${data.assigned_to}`);
}
```

### Supported File Formats

#### JSON Format
```json
[
  {
    "address": "123 Main St, Seattle, WA",
    "price": 2500,
    "bedrooms": 3,
    "bathrooms": 2.5,
    "square_feet": 1200,
    "property_type": "Apartment",
    "features": ["Pool", "Gym"]
  }
]
```

**Flexible Field Names Supported:**
- Address: `address`, `addr`, `location`, `street`, `street_address`
- Price: `price`, `cost`, `rent`, `rental_price`, `monthly_rent`, `list_price`
- Bedrooms: `bedrooms`, `beds`, `bed`, `bedroom_count`, `num_bedrooms`
- Bathrooms: `bathrooms`, `baths`, `bath`, `bathroom_count`, `num_bathrooms`
- Square Feet: `square_feet`, `sqft`, `sq_ft`, `square_footage`, `area`, `size`
- And many more variations...

#### CSV Format
```csv
address,price,bedrooms,bathrooms,square_feet,property_type
"123 Main St, Seattle, WA",2500,3,2.5,1200,Apartment
"456 Oak Ave, Portland, OR",1800,2,1,900,Apartment
```

**Features:**
- Auto-detects delimiter (comma, semicolon, tab, pipe)
- Handles quoted values
- Maps column names to standard fields
- Supports various column name variations

#### TXT Format (Unstructured)
```
Property 1:
Address: 123 Main Street, Seattle, WA
Price: $2,500/month
Bedrooms: 3
Bathrooms: 2.5
Square Feet: 1200
Features: Pool, Gym, Parking

Property 2:
Address: 456 Oak Avenue, Portland, OR
Price: $1,800
Bedrooms: 2
Bathrooms: 1
```

**Features:**
- Uses AI (Google Gemini) to extract structured data from unstructured text
- Handles various text formats and layouts
- Extracts multiple properties from single file
- Handles missing or incomplete information

### Data Normalization

The AI parser automatically normalizes all data to match the expected database schema:

**Required Fields:**
- `address` (string) - Full property address
- `price` (number) - Property price (automatically extracts from strings like "$2,500" or "2500 USD")

**Optional Fields (with defaults):**
- `listing_id` (string) - MLS or listing ID
- `bedrooms` (number) - Default: 0
- `bathrooms` (number) - Can be decimal (e.g., 2.5), Default: 0
- `square_feet` (number) - Square footage
- `lot_size_sqft` (number) - Lot size in square feet
- `year_built` (number) - Year built
- `property_type` (string) - Default: "Apartment"
- `listing_status` (string) - One of: "Available", "For Sale", "For Rent", "Sold", "Rented". Default: "Available"
- `days_on_market` (number) - Days on market
- `listing_date` (string) - ISO format (YYYY-MM-DD)
- `description` (string) - Property description
- `image_url` (string) - URL to property image
- `features` (array) - Array of feature strings, e.g., ["Pool", "Gym", "Parking"]
- `agent` (object) - Agent information:
  ```json
  {
    "name": "Jane Smith",
    "phone": "555-9876",
    "email": "jane@example.com"
  }
  ```

### Data Storage Format

Uploaded listings are stored in the `apartment_listing` table with the following structure:

```json
{
  "id": 684,
  "source_id": 83,
  "text": "Address: 1474 Peter Curve, Berkeley, CA. Price: 1726. Bedrooms: 3. Bathrooms: 2.7. Description: ",
  "listing_metadata": {
    "listing_id": "MLS000258",
    "address": "1474 Peter Curve, Berkeley, CA",
    "price": 3000,
    "bedrooms": 3,
    "bathrooms": 2.7,
    "square_feet": 1477,
    "lot_size_sqft": 1696,
    "year_built": 1959,
    "property_type": "Apartment",
    "listing_status": "Available",
    "days_on_market": 68,
    "agent": {
      "name": "Cheryl Martin",
      "phone": "335-447-7890",
      "email": "kelly87@hotmail.com"
    },
    "features": ["Fireplace", "Pet Friendly", "Hardwood Floors", "Central Air", "Pool", "Gym"],
    "listing_date": "2025-01-08"
  },
  "embedding": [0.06252559, -0.017695166, ...]  // 768-dimensional vector
}
```

### Error Handling

**Common Errors:**

1. **Invalid File Format:**
```json
{
  "detail": "Failed to parse file listings.csv: CSV parsing error: ..."
}
```

2. **No Listings Found:**
```json
{
  "detail": "No valid listings found in the provided data"
}
```

3. **Missing Required Fields:**
The parser will attempt to construct missing required fields (e.g., address from components) or use defaults.

4. **AI Parsing Failure:**
If AI parsing fails, the system falls back to regex-based parsing.

**Example Error Handling:**
```javascript
try {
  const formData = new FormData();
  formData.append('listing_file', fileInput.files[0]);

  const response = await fetch('/UploadListings', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`
    },
    body: formData
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Upload failed');
  }

  const data = await response.json();
  console.log('Success:', data.message);
  // Show success message to user
} catch (error) {
  console.error('Upload error:', error.message);
  // Show error to user
  alert(`Failed to upload listings: ${error.message}`);
}
```

### Property Assignment Endpoints

After uploading listings to PM's source, the PM can assign them to realtors:

#### 1. Assign Properties to Realtor
```http
POST /property-manager/assign-properties
Authorization: Bearer <pm_jwt_token>
Content-Type: application/json

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
  "realtor_name": "Sarah Johnson",
  "realtor_email": "sarah@example.com",
  "property_count": 5,
  "assigned_property_ids": [1, 2, 3, 4, 5]
}
```

#### 2. Bulk Assign Properties to Multiple Realtors
```http
POST /property-manager/bulk-assign-properties
Authorization: Bearer <pm_jwt_token>
Content-Type: application/json

{
  "assignments": [
    {
      "realtor_id": 123,
      "property_ids": [1, 2, 3]
    },
    {
      "realtor_id": 124,
      "property_ids": [4, 5, 6]
    }
  ]
}
```

**Response:**
```json
{
  "message": "Bulk assignment completed",
  "total_assignments": 2,
  "results": [
    {
      "realtor_id": 123,
      "realtor_name": "Sarah Johnson",
      "status": "success",
      "assigned_count": 3,
      "assigned_property_ids": [1, 2, 3]
    },
    {
      "realtor_id": 124,
      "realtor_name": "John Doe",
      "status": "success",
      "assigned_count": 3,
      "assigned_property_ids": [4, 5, 6]
    }
  ]
}
```

#### 3. Unassign Properties from Realtor
```http
POST /property-manager/unassign-properties
Authorization: Bearer <pm_jwt_token>
Content-Type: application/json

{
  "property_ids": [1, 2, 3, 4, 5]
}
```

**Response:**
```json
{
  "message": "Successfully unassigned 5 properties from realtors",
  "property_count": 5,
  "unassigned_property_ids": [1, 2, 3, 4, 5]
}
```

**Notes:**
- PM can only assign/unassign properties that belong to their sources
- Properties are moved between sources by changing `source_id`
- Unassigned properties return to PM's source
- PM maintains full control over all listings

### Upload Rules Endpoint

```http
POST /UploadRules
Authorization: Bearer <realtor_jwt_token>
Content-Type: multipart/form-data

Form Data:
- files: File[] (required) - Multiple rule/policy documents
```

**Response:**
```json
{
  "message": "Rules uploaded & embedded",
  "files": ["rules1.pdf", "rules2.txt"]
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

4. **Listing Uploads:**
   - [ ] Can upload JSON files with various field name variations
   - [ ] Can upload CSV files with different delimiters
   - [ ] Can upload TXT files with unstructured data
   - [ ] AI parser handles malformed data correctly
   - [ ] Data is normalized to match database schema
   - [ ] Multiple listings in single file are processed correctly
   - [ ] Missing fields are handled with defaults
   - [ ] Files are stored in Supabase storage
   - [ ] Listings are embedded and searchable after upload
   - [ ] **Uploads default to PM's source (PM owns them)**
   - [ ] **PM can assign listings to realtors after upload**
   - [ ] **PM can unassign listings from realtors back to themselves**
   - [ ] **Standalone realtors upload directly to their own source**
   - [ ] Error messages are clear and helpful

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

### Upload Listings (JSON)
```javascript
const formData = new FormData();
formData.append('listing_file', fileInput.files[0]);

const response = await fetch('/UploadListings', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`
  },
  body: formData
});

if (response.ok) {
  const data = await response.json();
  console.log('Success:', data.message);
  // Show success notification
} else {
  const error = await response.json();
  console.error('Error:', error.detail);
}
```

### Upload Listings (CSV)
```javascript
// Same as JSON upload - parser automatically detects format
const formData = new FormData();
formData.append('listing_file', csvFile);

const response = await fetch('/property-manager/upload-listings', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`
  },
  body: formData
});
```

### Upload Listings (Recommended: Upload to PM First)
```javascript
// Step 1: Upload to PM's source (PM owns the listings)
const formData = new FormData();
formData.append('listing_file', fileInput.files[0]);
// Don't include assign_to_realtor_id - uploads go to PM's source

const response = await fetch('/property-manager/upload-listings', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`
  },
  body: formData
});

if (response.ok) {
  const data = await response.json();
  console.log(`Uploaded ${data.count} listings to PM's source`);
  // Listings are now owned by PM and can be assigned to realtors
}
```

### Assign Listings to Realtor (After Upload)
```javascript
// Step 2: Assign specific listings to a realtor
const response = await fetch('/property-manager/assign-properties', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    realtor_id: 123,
    property_ids: [1, 2, 3, 4, 5]  // IDs of listings to assign
  })
});

if (response.ok) {
  const data = await response.json();
  console.log(`Assigned ${data.property_count} properties to ${data.realtor_name}`);
}
```

### Direct Upload to Realtor (Alternative)
```javascript
// Alternative: Upload directly to realtor during upload (not recommended)
const formData = new FormData();
formData.append('listing_file', fileInput.files[0]);
formData.append('assign_to_realtor_id', realtorId);

const response = await fetch('/property-manager/upload-listings', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`
  },
  body: formData
});

if (response.ok) {
  const data = await response.json();
  console.log(`Uploaded ${data.count} listings directly to realtor`);
}
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
- ✅ **AI-Powered Uploads:** Intelligent parsing handles various formats and malformed data
- ✅ **Data Normalization:** All uploaded data is automatically normalized to match database schema
- ✅ **Multiple Formats:** Supports JSON, CSV, and TXT files with flexible field names
- ✅ **PM Ownership:** All PM uploads are stored in PM's source by default
- ✅ **Flexible Assignment:** PM can assign/unassign listings to/from realtors at any time
- ✅ **Standalone Realtors:** Realtors without PM work independently with their own source

---

## 📞 Phone Number Request & Assignment System

### Overview

The phone number system has been redesigned to provide better control and management:

1. **Property Managers** request phone numbers via dashboard
2. **Tech Team** purchases and configures numbers (within 24 hours)
3. **Property Managers** assign purchased numbers to themselves or their realtors
4. **Chatbot** automatically uses the correct data based on assigned number

### Workflow

```
PM Dashboard → Request Number → Tech Team Purchases → PM Assigns → Chatbot Works
```

---

### 1. Request Phone Number (Property Manager Only)

**Endpoint:**
```http
POST /request-phone-number
Authorization: Bearer <pm_jwt_token>
Content-Type: application/json

{
  "area_code": "412",  // Optional: Preferred area code
  "notes": "Need number for new realtor"  // Optional: Additional notes
}
```

**Response:**
```json
{
  "message": "Your phone number request has been submitted successfully. A new number will be available in your portal within 24 hours.",
  "request_id": 1,
  "status": "pending",
  "requested_at": "2024-01-15T10:30:00Z"
}
```

**Frontend Implementation:**
```javascript
// PM Dashboard - Request Phone Number Button
async function requestPhoneNumber(areaCode = null, notes = null) {
  const response = await fetch('/request-phone-number', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      area_code: areaCode,
      notes: notes
    })
  });
  
  if (response.ok) {
    const data = await response.json();
    // Show success message: "Number will be available in 24 hours"
    alert(data.message);
  } else {
    const error = await response.json();
    alert(`Error: ${error.detail}`);
  }
}
```

**UI Requirements:**
- Show a "Request Phone Number" button on PM dashboard
- Optional: Form with area code input and notes field
- Display success message: "Your phone number request has been submitted. A new number will be available in your portal within 24 hours."

---

### 2. View Phone Number Requests (Property Manager)

**Endpoint:**
```http
GET /my-phone-number-requests
Authorization: Bearer <pm_jwt_token>
```

**Response:**
```json
{
  "requests": [
    {
      "request_id": 1,
      "area_code": "412",
      "status": "pending",  // pending, fulfilled, cancelled
      "notes": "Need number for new realtor",
      "requested_at": "2024-01-15T10:30:00Z",
      "fulfilled_at": null
    },
    {
      "request_id": 2,
      "area_code": "415",
      "status": "fulfilled",
      "notes": null,
      "requested_at": "2024-01-14T09:00:00Z",
      "fulfilled_at": "2024-01-14T14:30:00Z"
    }
  ]
}
```

**Frontend Implementation:**
```javascript
// PM Dashboard - View Requests
async function getPhoneNumberRequests() {
  const response = await fetch('/my-phone-number-requests', {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  
  if (response.ok) {
    const data = await response.json();
    // Display requests in a table
    data.requests.forEach(req => {
      console.log(`Request ${req.request_id}: ${req.status}`);
    });
  }
}
```

**UI Requirements:**
- Display requests in a table/list
- Show status badges (Pending, Fulfilled, Cancelled)
- Show timestamps for request and fulfillment

---

### 3. View Purchased Phone Numbers (Property Manager)

**Endpoint:**
```http
GET /purchased-phone-numbers
Authorization: Bearer <pm_jwt_token>
```

**Response:**
```json
{
  "purchased_numbers": [
    {
      "purchased_phone_number_id": 1,
      "phone_number": "+14125551234",
      "status": "available",  // available, assigned, inactive
      "assigned_to_type": null,
      "assigned_to_id": null,
      "purchased_at": "2024-01-15T14:30:00Z",
      "assigned_at": null
    },
    {
      "purchased_phone_number_id": 2,
      "phone_number": "+14125551235",
      "status": "assigned",
      "assigned_to_type": "realtor",
      "assigned_to_id": 5,
      "purchased_at": "2024-01-14T10:00:00Z",
      "assigned_at": "2024-01-15T09:00:00Z"
    }
  ],
  "available_for_assignment": [
    {
      "purchased_phone_number_id": 1,
      "phone_number": "+14125551234",
      "purchased_at": "2024-01-15T14:30:00Z"
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

**Frontend Implementation:**
```javascript
// PM Dashboard - View Available Numbers
async function getPurchasedNumbers() {
  const response = await fetch('/purchased-phone-numbers', {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  
  if (response.ok) {
    const data = await response.json();
    // Show available numbers for assignment
    data.available_for_assignment.forEach(num => {
      console.log(`Available: ${num.phone_number}`);
    });
    // Show realtors for assignment dropdown
    data.realtors.forEach(realtor => {
      console.log(`Realtor: ${realtor.name} (ID: ${realtor.realtor_id})`);
    });
  }
}
```

**UI Requirements:**
- Display all purchased numbers (available and assigned)
- Highlight available numbers that can be assigned
- Show assignment status (Assigned to PM, Assigned to Realtor, Available)
- Display realtors list for assignment dropdown

---

### 4. Assign Phone Number (Property Manager)

**Endpoint:**
```http
POST /assign-phone-number
Authorization: Bearer <pm_jwt_token>
Content-Type: application/json

{
  "purchased_phone_number_id": 1,
  "assign_to_type": "property_manager",  // or "realtor"
  "assign_to_id": null  // Required if assign_to_type is "realtor"
}
```

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
  "assigned_at": "2024-01-15T15:00:00Z"
}
```

**Frontend Implementation:**
```javascript
// PM Dashboard - Assign Number to Self
async function assignToSelf(purchasedPhoneNumberId) {
  const response = await fetch('/assign-phone-number', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      purchased_phone_number_id: purchasedPhoneNumberId,
      assign_to_type: "property_manager"
    })
  });
  
  if (response.ok) {
    const data = await response.json();
    alert(data.message);
    // Refresh purchased numbers list
    getPurchasedNumbers();
  }
}

// PM Dashboard - Assign Number to Realtor
async function assignToRealtor(purchasedPhoneNumberId, realtorId) {
  const response = await fetch('/assign-phone-number', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      purchased_phone_number_id: purchasedPhoneNumberId,
      assign_to_type: "realtor",
      assign_to_id: realtorId
    })
  });
  
  if (response.ok) {
    const data = await response.json();
    alert(data.message);
    // Refresh purchased numbers list
    getPurchasedNumbers();
  }
}
```

**UI Requirements:**
- For each available number, show "Assign to Me" button
- For each available number, show dropdown to select realtor and "Assign to Realtor" button
- After assignment, update the UI to show new status
- Show confirmation message

---

### 5. Get My Phone Number (Property Manager or Realtor)

**Endpoint:**
```http
GET /my-number
Authorization: Bearer <jwt_token>
```

**Response (if assigned):**
```json
{
  "twilio_number": "+14125551234",
  "twilio_sid": "PN...",
  "user_type": "property_manager",
  "user_id": 1
}
```

**Response (if not assigned):**
```json
{
  "detail": "You haven't purchased a phone number yet! Use the /buy-number endpoint to purchase one."
}
```

**Frontend Implementation:**
```javascript
// Display current phone number
async function getMyNumber() {
  const response = await fetch('/my-number', {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  
  if (response.ok) {
    const data = await response.json();
    // Display phone number in UI
    document.getElementById('phone-number').textContent = data.twilio_number;
  } else {
    // Show "No number assigned" message
    document.getElementById('phone-number').textContent = "No number assigned";
  }
}
```

**UI Requirements:**
- Display current assigned phone number (if any)
- Show "No number assigned" if none
- For PMs: Show link to request/assign numbers

---

### 6. Admin Endpoints (Tech Team)

These endpoints are for the tech team to manage phone number purchases. **In production, these should be protected with admin authentication.**

#### View All Requests
```http
GET /admin/all-phone-number-requests?status=pending
Authorization: Bearer <admin_token>
```

#### Purchase Phone Number
```http
POST /admin/purchase-phone-number
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "property_manager_id": 1,
  "area_code": "412",  // Optional
  "notes": "Purchased for PM request #1"  // Optional
}
```

#### View All Purchased Numbers
```http
GET /admin/all-purchased-numbers?property_manager_id=1&status=available
Authorization: Bearer <admin_token>
```

---

### Complete Frontend Flow Example

```javascript
// PM Dashboard - Complete Phone Number Management

// 1. Request a new number
async function requestNewNumber() {
  const areaCode = document.getElementById('area-code-input').value;
  const notes = document.getElementById('notes-input').value;
  
  const response = await fetch('/request-phone-number', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ area_code: areaCode, notes: notes })
  });
  
  if (response.ok) {
    const data = await response.json();
    showSuccessMessage(data.message); // "Number will be available in 24 hours"
  }
}

// 2. Load and display purchased numbers
async function loadPurchasedNumbers() {
  const response = await fetch('/purchased-phone-numbers', {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  
  if (response.ok) {
    const data = await response.json();
    
    // Display available numbers
    const availableList = document.getElementById('available-numbers');
    data.available_for_assignment.forEach(num => {
      const item = document.createElement('div');
      item.innerHTML = `
        <span>${num.phone_number}</span>
        <button onclick="assignToSelf(${num.purchased_phone_number_id})">Assign to Me</button>
        <select id="realtor-${num.purchased_phone_number_id}">
          ${data.realtors.map(r => `<option value="${r.realtor_id}">${r.name}</option>`).join('')}
        </select>
        <button onclick="assignToRealtor(${num.purchased_phone_number_id})">Assign to Realtor</button>
      `;
      availableList.appendChild(item);
    });
    
    // Display assigned numbers
    const assignedList = document.getElementById('assigned-numbers');
    data.purchased_numbers
      .filter(num => num.status === 'assigned')
      .forEach(num => {
        const item = document.createElement('div');
        item.innerHTML = `
          <span>${num.phone_number}</span>
          <span>Assigned to: ${num.assigned_to_type} (ID: ${num.assigned_to_id})</span>
        `;
        assignedList.appendChild(item);
      });
  }
}

// 3. Assign to self
async function assignToSelf(purchasedPhoneNumberId) {
  const response = await fetch('/assign-phone-number', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      purchased_phone_number_id: purchasedPhoneNumberId,
      assign_to_type: "property_manager"
    })
  });
  
  if (response.ok) {
    showSuccessMessage("Number assigned successfully!");
    loadPurchasedNumbers(); // Refresh list
  }
}

// 4. Assign to realtor
async function assignToRealtor(purchasedPhoneNumberId) {
  const realtorId = document.getElementById(`realtor-${purchasedPhoneNumberId}`).value;
  
  const response = await fetch('/assign-phone-number', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      purchased_phone_number_id: purchasedPhoneNumberId,
      assign_to_type: "realtor",
      assign_to_id: parseInt(realtorId)
    })
  });
  
  if (response.ok) {
    showSuccessMessage("Number assigned to realtor successfully!");
    loadPurchasedNumbers(); // Refresh list
  }
}
```

---

### Key Points

- ✅ **PM Only:** Only Property Managers can request and assign numbers
- ✅ **24 Hour Promise:** Show message that numbers will be available within 24 hours
- ✅ **Flexible Assignment:** PM can assign to themselves or any of their realtors
- ✅ **Automatic Data Isolation:** Chatbot automatically uses correct data based on assigned number
- ✅ **Status Tracking:** Track request status (pending, fulfilled) and number status (available, assigned)
- ✅ **Reassignment:** Numbers can be reassigned (old assignment is automatically unassigned)

---

## 🔧 Technical Details

### Property Update Fix
The property update endpoint was fixed to properly persist changes to the JSONB `listing_metadata` column by:
1. Using `flag_modified()` from SQLAlchemy to mark the JSONB field as changed
2. Creating a new dict object to ensure SQLAlchemy detects the change
3. Proper session management with `session.add()` before commit

This ensures all property field updates (price, address, features, etc.) are correctly saved to the database.

### AI-Powered Listing Parser

The listing parser (`DB/listing_parser.py`) provides:

1. **Format Support:**
   - JSON (with flexible field names)
   - CSV (auto-detects delimiter)
   - TXT (uses AI for unstructured text)

2. **Data Normalization:**
   - Maps various field name variations to standard schema
   - Handles nested data structures
   - Extracts agent information from various formats
   - Normalizes features from strings, arrays, or comma-separated values
   - Validates and cleans all data before storage

3. **AI Integration:**
   - Uses Vertex AI (Gemini models like `gemini-2.0-flash-exp`) for robust parsing
   - Automatically falls back to Gemini API if Vertex AI not configured
   - Falls back to regex-based parsing if AI is unavailable
   - Handles malformed JSON with automatic fixes
   - Extracts multiple properties from single text file

4. **Error Handling:**
   - Graceful degradation if AI is unavailable
   - Clear error messages for parsing failures
   - Automatic field construction when possible
   - Default values for missing optional fields

5. **Data Storage:**
   - All listings are stored with consistent schema
   - Text representations generated for embedding
   - Vector embeddings created for semantic search
   - Files stored in Supabase storage for reference

---

## 📝 Notes

- **Vertex AI (Recommended)**: Set `GCP_PROJECT_ID`, `GCP_LOCATION`, and `USE_VERTEX_AI=true` for best performance
- **Fallback**: If Vertex AI not configured, set `GEMINI_API_KEY` for Gemini API fallback
- If AI is unavailable, the parser falls back to regex-based parsing
- All uploaded files are stored in Supabase storage for audit purposes
- Listings are immediately searchable after upload via semantic search
- The parser handles edge cases like missing fields, wrong data types, and malformed structures
- See `VERTEX_AI_SETUP.md` for detailed Vertex AI configuration guide
