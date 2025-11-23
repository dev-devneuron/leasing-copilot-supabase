# Frontend Integration Guide: Maintenance Requests & Tenants

## Overview

This guide provides detailed instructions for integrating maintenance requests and tenant management features into the frontend dashboard for both Property Managers (PMs) and Realtors.

## Table of Contents

1. [Authentication](#authentication)
2. [Tenant Management](#tenant-management)
3. [Maintenance Requests](#maintenance-requests)
4. [Data Isolation & Permissions](#data-isolation--permissions)
5. [UI/UX Recommendations](#uiux-recommendations)
6. [Complete API Reference](#complete-api-reference)

---

## Authentication

All endpoints require JWT authentication. Include the token in the Authorization header:

```javascript
const headers = {
  'Authorization': `Bearer ${accessToken}`,
  'Content-Type': 'application/json'
};
```

**Base URL:** `https://leasing-copilot-mvp.onrender.com`

---

## Tenant Management

### 1. Get Tenants List

**Endpoint:** `GET /tenants`

**Query Parameters:**
- `property_id` (optional): Filter by specific property
- `is_active` (optional): Filter by active status (true/false)

**Response for Property Managers:**
```json
[
  {
    "tenant_id": 1,
    "name": "John Smith",
    "phone_number": "+14125551234",
    "email": "john@example.com",
    "property_id": 10,
    "property_manager_id": 1,
    "realtor_id": 5,
    "unit_number": "Apt 3B",
    "lease_start_date": "2024-01-15",
    "lease_end_date": "2025-01-14",
    "is_active": true,
    "notes": "Preferred contact method: email",
    "created_at": "2024-01-10T10:00:00Z",
    "updated_at": "2024-01-10T10:00:00Z",
    "property": {
      "id": 10,
      "address": "123 Main St, City, State",
      "listing_metadata": {...}
    },
    "realtor": {
      "realtor_id": 5,
      "name": "Jane Doe",
      "email": "jane@example.com"
    }
  }
]
```

**Response for Realtors:**
- Shows tenants for properties they manage (via Source)
- Shows tenants assigned to them (`realtor_id` matches)
- Same structure as PM response

**Example Implementation:**

```javascript
// Fetch tenants
async function fetchTenants(propertyId = null, isActive = null) {
  const params = new URLSearchParams();
  if (propertyId) params.append('property_id', propertyId);
  if (isActive !== null) params.append('is_active', isActive);
  
  const response = await fetch(
    `https://leasing-copilot-mvp.onrender.com/tenants?${params}`,
    {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json'
      }
    }
  );
  
  if (!response.ok) {
    throw new Error('Failed to fetch tenants');
  }
  
  return await response.json();
}

// Usage
const tenants = await fetchTenants();
const activeTenants = await fetchTenants(null, true);
const propertyTenants = await fetchTenants(10, true);
```

### 2. Create Tenant

**Endpoint:** `POST /tenants`

**Request Body:**
```json
{
  "name": "John Smith",
  "phone_number": "+14125551234",
  "email": "john@example.com",
  "property_id": 10,
  "realtor_id": 5,
  "unit_number": "Apt 3B",
  "lease_start_date": "2024-01-15",
  "lease_end_date": "2025-01-14",
  "is_active": true,
  "notes": "Preferred contact method: email"
}
```

**Required Fields:**
- `name`
- `property_id`
- `property_manager_id` (automatically set from authenticated user)

**Response:**
```json
{
  "tenant_id": 1,
  "name": "John Smith",
  "phone_number": "+14125551234",
  "email": "john@example.com",
  "property_id": 10,
  "property_manager_id": 1,
  "realtor_id": 5,
  "unit_number": "Apt 3B",
  "lease_start_date": "2024-01-15",
  "lease_end_date": "2025-01-14",
  "is_active": true,
  "notes": "Preferred contact method: email",
  "created_at": "2024-01-10T10:00:00Z",
  "updated_at": "2024-01-10T10:00:00Z"
}
```

**Note:** When a tenant is created, the property's `listing_status` is automatically updated to "Rented".

### 3. Update Tenant

**Endpoint:** `PATCH /tenants/{tenant_id}`

**Request Body:** (all fields optional)
```json
{
  "name": "John Smith Jr.",
  "phone_number": "+14125551235",
  "email": "johnjr@example.com",
  "unit_number": "Apt 3C",
  "lease_start_date": "2024-02-01",
  "lease_end_date": "2025-01-31",
  "is_active": false,
  "notes": "Moved out"
}
```

**Note:** When `is_active` is changed from `true` to `false`, the property's `listing_status` is automatically updated to "Available" (if no other active tenants).

---

## Maintenance Requests

### 1. Get Maintenance Requests List

**Endpoint:** `GET /maintenance-requests`

**Query Parameters:**
- `status` (optional): Filter by status (`pending`, `in_progress`, `completed`, `cancelled`)
- `limit` (optional): Number of results (default: 50, max: 100)
- `offset` (optional): Pagination offset (default: 0)

**Response:**
```json
[
  {
    "maintenance_request_id": 1,
    "tenant_id": 1,
    "property_id": 10,
    "property_manager_id": 1,
    "issue_description": "Kitchen sink is leaking continuously",
    "priority": "high",
    "status": "pending",
    "category": "plumbing",
    "location": "kitchen",
    "tenant_name": "John Smith",
    "tenant_phone": "+14125551234",
    "tenant_email": "john@example.com",
    "submitted_via": "phone",
    "vapi_call_id": "call_123",
    "call_transcript": "User reported sink leak...",
    "assigned_to_realtor_id": 5,
    "pm_notes": "Waiting for plumber",
    "resolution_notes": null,
    "submitted_at": "2024-01-15T10:00:00Z",
    "updated_at": "2024-01-15T10:00:00Z",
    "completed_at": null,
    "tenant": {
      "tenant_id": 1,
      "name": "John Smith",
      "unit_number": "Apt 3B"
    },
    "property": {
      "id": 10,
      "address": "123 Main St, City, State"
    },
    "assigned_realtor": {
      "realtor_id": 5,
      "name": "Jane Doe",
      "email": "jane@example.com"
    }
  }
]
```

**Example Implementation:**

```javascript
// Fetch maintenance requests
async function fetchMaintenanceRequests(status = null, limit = 50, offset = 0) {
  const params = new URLSearchParams();
  if (status) params.append('status', status);
  params.append('limit', limit);
  params.append('offset', offset);
  
  const response = await fetch(
    `https://leasing-copilot-mvp.onrender.com/maintenance-requests?${params}`,
    {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json'
      }
    }
  );
  
  if (!response.ok) {
    throw new Error('Failed to fetch maintenance requests');
  }
  
  return await response.json();
}

// Usage
const allRequests = await fetchMaintenanceRequests();
const pendingRequests = await fetchMaintenanceRequests('pending');
const inProgressRequests = await fetchMaintenanceRequests('in_progress');
```

### 2. Get Single Maintenance Request

**Endpoint:** `GET /maintenance-requests/{request_id}`

**Response:** Same structure as list item, but single object

```javascript
async function getMaintenanceRequest(requestId) {
  const response = await fetch(
    `https://leasing-copilot-mvp.onrender.com/maintenance-requests/${requestId}`,
    {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json'
      }
    }
  );
  
  if (!response.ok) {
    throw new Error('Failed to fetch maintenance request');
  }
  
  return await response.json();
}
```

### 3. Update Maintenance Request

**Endpoint:** `PATCH /maintenance-requests/{request_id}`

**Request Body:** (all fields optional)

**For Property Managers:**
```json
{
  "status": "in_progress",
  "priority": "urgent",
  "category": "plumbing",
  "location": "kitchen",
  "assigned_to_realtor_id": 5,
  "pm_notes": "Assigned to plumber, scheduled for tomorrow",
  "resolution_notes": null
}
```

**For Realtors:**
```json
{
  "status": "completed",
  "resolution_notes": "Fixed leaky faucet, replaced washer"
}
```

**Status Values:**
- `pending` - Initial status when request is created
- `in_progress` - Request is being worked on
- `completed` - Request is finished
- `cancelled` - Request was cancelled

**Note:** When status is set to `completed`, `completed_at` is automatically set. When changed from `completed` to another status, `completed_at` is cleared.

**Example Implementation:**

```javascript
async function updateMaintenanceRequest(requestId, updateData) {
  const response = await fetch(
    `https://leasing-copilot-mvp.onrender.com/maintenance-requests/${requestId}`,
    {
      method: 'PATCH',
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(updateData)
    }
  );
  
  if (!response.ok) {
    throw new Error('Failed to update maintenance request');
  }
  
  return await response.json();
}

// Usage examples
// Mark as in progress
await updateMaintenanceRequest(1, { status: 'in_progress' });

// Assign to realtor and add notes
await updateMaintenanceRequest(1, {
  status: 'in_progress',
  assigned_to_realtor_id: 5,
  pm_notes: 'Assigned to plumber'
});

// Mark as completed
await updateMaintenanceRequest(1, {
  status: 'completed',
  resolution_notes: 'Fixed leaky faucet'
});
```

### 4. Delete Maintenance Request

**Endpoint:** `DELETE /maintenance-requests/{request_id}`

**Response:**
```json
{
  "message": "Maintenance request deleted successfully",
  "maintenance_request_id": 1
}
```

**Example Implementation:**

```javascript
async function deleteMaintenanceRequest(requestId) {
  const response = await fetch(
    `https://leasing-copilot-mvp.onrender.com/maintenance-requests/${requestId}`,
    {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json'
      }
    }
  );
  
  if (!response.ok) {
    throw new Error('Failed to delete maintenance request');
  }
  
  return await response.json();
}

// Usage
await deleteMaintenanceRequest(1);
```

---

## Data Isolation & Permissions

### Property Managers (PMs)

**Can:**
- View all tenants for their properties
- View all maintenance requests for their properties
- Create, update, and delete tenants
- Create, update, and delete maintenance requests
- Assign maintenance requests to realtors
- Set priority, category, and location
- Add PM notes and resolution notes

**Cannot:**
- View tenants or requests from other PMs

### Realtors

**Can:**
- View tenants for properties they manage (via Source)
- View tenants assigned to them (`realtor_id` matches)
- View maintenance requests assigned to them
- View maintenance requests for properties they manage
- Update status and resolution notes on assigned requests
- Cannot delete requests (only PMs can delete)

**Cannot:**
- View tenants or requests from other realtors (unless assigned)
- Create or delete tenants (only PMs can)
- Assign requests to other realtors
- Set priority, category, or location (only PMs can)

---

## UI/UX Recommendations

### Dashboard Layout

#### For Property Managers:

1. **Maintenance Requests Section:**
   - Tabs: All | Pending | In Progress | Completed | Cancelled
   - Filter by property, priority, category
   - Sort by date, priority, status
   - Quick actions: View Details | Assign to Realtor | Mark Complete | Delete

2. **Tenants Section:**
   - List view with search/filter
   - Show: Name, Property, Unit, Contact Info, Active Status
   - Actions: View Details | Edit | View Maintenance History

3. **Maintenance Request Detail View:**
   - Tenant information (name, unit, contact)
   - Property address
   - Issue description
   - Status, priority, category, location
   - Timeline (submitted, updated, completed)
   - Assignment (if assigned to realtor)
   - Notes (PM notes, resolution notes)
   - Call transcript (if available)
   - Actions: Update Status | Assign to Realtor | Add Notes | Delete

#### For Realtors:

1. **My Maintenance Requests:**
   - Shows requests assigned to them OR for their properties
   - Tabs: All | Pending | In Progress | Completed
   - Quick actions: View Details | Update Status | Add Resolution Notes

2. **My Tenants:**
   - Shows tenants for properties they manage
   - Shows tenants assigned to them
   - View tenant details and maintenance history

3. **Maintenance Request Detail View:**
   - Same as PM view, but limited actions
   - Can update status and resolution notes
   - Cannot assign to other realtors or delete

### Status Badge Colors

```javascript
const statusColors = {
  pending: 'yellow',      // Yellow/Orange badge
  in_progress: 'blue',    // Blue badge
  completed: 'green',     // Green badge
  cancelled: 'gray'       // Gray badge
};
```

### Priority Badge Colors

```javascript
const priorityColors = {
  low: 'gray',           // Gray badge
  normal: 'blue',        // Blue badge
  high: 'orange',        // Orange badge
  urgent: 'red'          // Red badge
};
```

### Example React Component Structure

```jsx
// MaintenanceRequestsList.jsx
import React, { useState, useEffect } from 'react';

function MaintenanceRequestsList({ userType, userId }) {
  const [requests, setRequests] = useState([]);
  const [statusFilter, setStatusFilter] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchRequests();
  }, [statusFilter]);

  async function fetchRequests() {
    try {
      setLoading(true);
      const data = await fetchMaintenanceRequests(statusFilter);
      setRequests(data);
    } catch (error) {
      console.error('Error fetching requests:', error);
    } finally {
      setLoading(false);
    }
  }

  async function handleStatusUpdate(requestId, newStatus) {
    try {
      await updateMaintenanceRequest(requestId, { status: newStatus });
      fetchRequests(); // Refresh list
    } catch (error) {
      console.error('Error updating status:', error);
    }
  }

  async function handleDelete(requestId) {
    if (!confirm('Are you sure you want to delete this request?')) return;
    
    try {
      await deleteMaintenanceRequest(requestId);
      fetchRequests(); // Refresh list
    } catch (error) {
      console.error('Error deleting request:', error);
    }
  }

  if (loading) return <div>Loading...</div>;

  return (
    <div>
      <div className="tabs">
        <button onClick={() => setStatusFilter(null)}>All</button>
        <button onClick={() => setStatusFilter('pending')}>Pending</button>
        <button onClick={() => setStatusFilter('in_progress')}>In Progress</button>
        <button onClick={() => setStatusFilter('completed')}>Completed</button>
        {userType === 'property_manager' && (
          <button onClick={() => setStatusFilter('cancelled')}>Cancelled</button>
        )}
      </div>

      <div className="requests-list">
        {requests.map(request => (
          <div key={request.maintenance_request_id} className="request-card">
            <div className="request-header">
              <h3>{request.tenant_name} - {request.property.address}</h3>
              <span className={`badge status-${request.status}`}>
                {request.status}
              </span>
              <span className={`badge priority-${request.priority}`}>
                {request.priority}
              </span>
            </div>
            
            <p>{request.issue_description}</p>
            <p><strong>Location:</strong> {request.location}</p>
            <p><strong>Category:</strong> {request.category}</p>
            
            {request.assigned_realtor && (
              <p><strong>Assigned to:</strong> {request.assigned_realtor.name}</p>
            )}
            
            <div className="request-actions">
              <button onClick={() => handleStatusUpdate(request.maintenance_request_id, 'in_progress')}>
                Mark In Progress
              </button>
              <button onClick={() => handleStatusUpdate(request.maintenance_request_id, 'completed')}>
                Mark Complete
              </button>
              {userType === 'property_manager' && (
                <button onClick={() => handleDelete(request.maintenance_request_id)}>
                  Delete
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default MaintenanceRequestsList;
```

---

## Complete API Reference

### Tenant Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/tenants` | Required | List tenants (with filters) |
| POST | `/tenants` | Required (PM only) | Create new tenant |
| PATCH | `/tenants/{id}` | Required (PM only) | Update tenant |
| GET | `/tenants/{id}` | Required | Get tenant details |

### Maintenance Request Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/maintenance-requests` | Required | List requests (with filters) |
| GET | `/maintenance-requests/{id}` | Required | Get request details |
| PATCH | `/maintenance-requests/{id}` | Required | Update request |
| DELETE | `/maintenance-requests/{id}` | Required (PM only) | Delete request |
| POST | `/submit_maintenance_request/` | None | VAPI bot endpoint (public) |
| POST | `/lookup_tenant/` | None | VAPI bot endpoint (public) |

### Status Values

- `pending` - Request submitted, not yet started
- `in_progress` - Request is being worked on
- `completed` - Request is finished
- `cancelled` - Request was cancelled

### Priority Values

- `low` - Low priority issue
- `normal` - Normal priority (default)
- `high` - High priority issue
- `urgent` - Urgent issue requiring immediate attention

### Category Values

- `plumbing` - Plumbing issues (sinks, toilets, pipes, leaks)
- `electrical` - Electrical issues (lights, outlets, circuits)
- `heating` - Heating/HVAC issues (furnace, AC, heating)
- `appliance` - Appliance issues (refrigerator, dishwasher, etc.)
- `other` - Other issues

---

## Error Handling

All endpoints return standard HTTP status codes:

- `200` - Success
- `400` - Bad Request (invalid data)
- `401` - Unauthorized (missing/invalid token)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found
- `500` - Internal Server Error

**Error Response Format:**
```json
{
  "detail": "Error message here"
}
```

**Example Error Handling:**

```javascript
async function handleApiCall(apiFunction) {
  try {
    return await apiFunction();
  } catch (error) {
    if (error.response) {
      // API returned error
      const status = error.response.status;
      const message = error.response.data.detail || 'An error occurred';
      
      if (status === 401) {
        // Redirect to login
        window.location.href = '/login';
      } else if (status === 403) {
        alert('You do not have permission to perform this action');
      } else if (status === 404) {
        alert('Resource not found');
      } else {
        alert(`Error: ${message}`);
      }
    } else {
      // Network or other error
      alert('Network error. Please try again.');
    }
    throw error;
  }
}
```

---

## Testing Checklist

- [ ] Fetch tenants list (PM and Realtor views)
- [ ] Filter tenants by property and active status
- [ ] Create new tenant (PM only)
- [ ] Update tenant information (PM only)
- [ ] Fetch maintenance requests list
- [ ] Filter maintenance requests by status
- [ ] View single maintenance request details
- [ ] Update maintenance request status
- [ ] Assign maintenance request to realtor (PM only)
- [ ] Add notes to maintenance request
- [ ] Mark request as completed
- [ ] Delete maintenance request (PM only)
- [ ] Verify data isolation (PMs can't see other PMs' data)
- [ ] Verify realtor permissions (can only see assigned/their properties)

---

## Support

For questions or issues, contact the backend team or refer to the main API documentation in `FRONTEND_BACKEND_INTEGRATION.md`.

