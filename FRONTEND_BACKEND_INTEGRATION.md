# Frontend & Backend Integration Guide
## Property Assignment Feature - Complete Implementation

This guide explains how to integrate the property assignment feature so Property Managers can assign properties to Realtors, view assignments, and Realtors can see their assigned properties.

---

## 📋 Overview

**Complete Flow:**
1. Property Manager views all available properties (unassigned)
2. PM selects properties and assigns them to a Realtor
3. Backend updates `source_id` of those properties to the Realtor's source
4. PM can view all assignments: which properties are assigned to which realtors
5. Realtor's dashboard automatically shows assigned properties (via `/apartments` endpoint)

**Key Points:**
- ✅ Backend is **complete** - all endpoints working
- ✅ Data isolation is **automatic** - Realtors only see their properties
- ✅ Assignment viewing is **available** - PM can see all assignments

---

## 🔌 Backend Endpoints (All Working)

### 1. Get Properties for PM (Available to Assign)
```http
GET /apartments
Authorization: Bearer <pm_jwt_token>
```
**Response:** Array of all properties (PM sees all, including assigned ones)
```json
[
  {
    "id": 1,
    "source_id": 123,
    "listing_id": "MLS000113",
    "address": "478 Larry Mission Suite 370, Seattle, WA",
    "price": 2912,
    "bedrooms": 4,
    "bathrooms": 2.9,
    "square_feet": 686,
    "lot_size_sqft": 2892,
    "year_built": 1951,
    "property_type": "Apartment",
    "listing_status": "Available",
    "days_on_market": 19,
    "listing_date": "2025-01-11",
    "agent": {
      "name": "Linda Foster",
      "phone": "001-539-542-2431x562",
      "email": "jennifer92@yahoo.com"
    },
    "features": ["Pool", "Gym", "Washer/Dryer", "Dishwasher", "Pet Friendly"],
    "description": "...",
    "image_url": "...",
    "owner_type": "property_manager",
    "owner_id": 1,
    "owner_name": "John Smith",
    "is_assigned": false,
    "assigned_to_realtor_id": null,
    "assigned_to_realtor_name": null,
    "full_metadata": {...}
  },
  {
    "id": 2,
    "address": "456 Oak Ave",
    "price": 2000,
    "bedrooms": 3,
    "bathrooms": 2,
    "owner_type": "realtor",
    "owner_id": 1,
    "owner_name": "Sarah Johnson",
    "is_assigned": true,
    "assigned_to_realtor_id": 1,
    "assigned_to_realtor_name": "Sarah Johnson"
  }
]
```

### 2. Get Property Assignments (PM View - Shows Who Has What)
```http
GET /property-manager/assignments
Authorization: Bearer <pm_jwt_token>
```
**Response:** Organized view of all assignments
```json
{
  "unassigned_properties": [
    {
      "id": 1,
      "source_id": 123,
      "listing_id": "MLS000113",
      "address": "478 Larry Mission Suite 370, Seattle, WA",
      "price": 2912,
      "bedrooms": 4,
      "bathrooms": 2.9,
      "square_feet": 686,
      "lot_size_sqft": 2892,
      "year_built": 1951,
      "property_type": "Apartment",
      "listing_status": "Available",
      "days_on_market": 19,
      "listing_date": "2025-01-11",
      "agent": {
        "name": "Linda Foster",
        "phone": "001-539-542-2431x562",
        "email": "jennifer92@yahoo.com"
      },
      "features": ["Pool", "Gym", "Washer/Dryer", "Dishwasher", "Pet Friendly"],
      "description": "...",
      "image_url": "..."
    }
  ],
  "assigned_properties": {
    "1": {
      "realtor_id": 1,
      "realtor_name": "Sarah Johnson",
      "realtor_email": "sarah.johnson@testcompany.com",
      "count": 5,
      "properties": [
        {
          "id": 2,
          "source_id": 456,
          "listing_id": "MLS000114",
          "address": "456 Oak Ave, Seattle, WA",
          "price": 2000,
          "bedrooms": 3,
          "bathrooms": 2,
          "square_feet": 1200,
          "lot_size_sqft": 5000,
          "year_built": 2020,
          "property_type": "Apartment",
          "listing_status": "Available",
          "days_on_market": 5,
          "listing_date": "2025-01-15",
          "agent": {
            "name": "John Doe",
            "phone": "555-0123",
            "email": "john@example.com"
          },
          "features": ["Gym", "Parking", "Elevator"],
          "description": "...",
          "image_url": "..."
        },
        ...
      ]
    },
    "2": {
      "realtor_id": 2,
      "realtor_name": "Mike Wilson",
      "realtor_email": "mike.wilson@testcompany.com",
      "count": 3,
      "properties": [...]
    }
  },
  "summary": {
    "total_properties": 9,
    "unassigned_count": 1,
    "assigned_count": 8,
    "realtor_counts": {
      "1": {
        "realtor_name": "Sarah Johnson",
        "count": 5
      },
      "2": {
        "realtor_name": "Mike Wilson",
        "count": 3
      }
    }
  }
}
```

### 3. Get Managed Realtors
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
      "status": "active"
    },
    {
      "id": 2,
      "name": "Mike Wilson",
      "email": "mike.wilson@testcompany.com",
      "status": "active"
    }
  ]
}
```

### 4. Assign Properties to Realtor
```http
POST /property-manager/assign-properties
Authorization: Bearer <pm_jwt_token>
Content-Type: application/json

{
  "realtor_id": 1,
  "property_ids": [1, 2, 3, 4, 5]
}
```
**Response:**
```json
{
  "message": "Successfully assigned 5 properties to realtor",
  "realtor_id": 1,
  "realtor_name": "Sarah Johnson",
  "realtor_email": "sarah.johnson@testcompany.com",
  "property_count": 5,
  "assigned_property_ids": [1, 2, 3, 4, 5]
}
```

### 5. Get Properties for Realtor (Dashboard)
```http
GET /apartments
Authorization: Bearer <realtor_jwt_token>
```
**Response:** Only properties assigned to this realtor
```json
[
  {
    "id": 2,
    "source_id": 456,
    "listing_id": "MLS000114",
    "address": "456 Oak Ave, Seattle, WA",
    "price": 2000,
    "bedrooms": 3,
    "bathrooms": 2,
    "square_feet": 1200,
    "lot_size_sqft": 5000,
    "year_built": 2020,
    "property_type": "Apartment",
    "listing_status": "Available",
    "days_on_market": 5,
    "listing_date": "2025-01-15",
    "agent": {
      "name": "John Doe",
      "phone": "555-0123",
      "email": "john@example.com"
    },
    "features": ["Gym", "Parking", "Elevator"],
    "description": "...",
    "image_url": "...",
    "owner_type": "realtor",
    "owner_id": 1,
    "owner_name": "Sarah Johnson",
    "is_assigned": true,
    "assigned_to_realtor_id": 1,
    "assigned_to_realtor_name": "Sarah Johnson",
    "full_metadata": {...}
  }
]
```

### 6. Unassign Properties from Realtor
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

### 7. Update Property Status
```http
PATCH /properties/{property_id}/status
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "listing_status": "Sold"  // Options: "Available", "For Sale", "For Rent", "Sold", "Rented"
}
```
**Response:**
```json
{
  "message": "Property status updated to Sold",
  "property_id": 1,
  "new_status": "Sold",
  "updated_metadata": {...}
}
```

### 8. Update or Remove Property Agent
```http
PATCH /properties/{property_id}/agent
Authorization: Bearer <jwt_token>
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
  },
  "updated_metadata": {...}
}
```

### 9. Update Property Details (General)
```http
PATCH /properties/{property_id}
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "listing_status": "Sold",
  "agent": null,
  "price": 2500,
  "days_on_market": 25,
  "features": ["Pool", "Gym", "Parking"]
}
```
**Response:**
```json
{
  "message": "Property updated successfully",
  "property_id": 1,
  "updated_fields": ["listing_status", "agent", "price", "days_on_market", "features"],
  "updated_metadata": {...}
}
```

### 10. Delete Realtor/Agent
```http
DELETE /property-manager/realtors/{realtor_id}
Authorization: Bearer <pm_jwt_token>
```
**What happens when a realtor is deleted:**
1. ✅ All properties assigned to them become **unassigned** (moved back to PM)
2. ✅ All bookings are **unassigned** (realtor_id set to NULL)
3. ✅ All sources belonging to the realtor are **deleted**
4. ✅ All rule chunks for those sources are **deleted**
5. ✅ The realtor record is **deleted** from the database

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

**⚠️ Important Notes:**
- This action **cannot be undone**
- The realtor's Supabase Auth account is **NOT deleted** (they can still login but won't have access)
- All properties are automatically reassigned to the Property Manager
- All bookings become unassigned (no realtor linked)

---

## 🎨 Frontend Implementation

### Component 0: Realtor Management (PM Manages Realtors)

```jsx
// RealtorManagementPage.jsx
import { useState, useEffect } from 'react';
import axios from 'axios';

const RealtorManagementPage = () => {
  const [realtors, setRealtors] = useState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null);

  const token = localStorage.getItem('access_token');

  useEffect(() => {
    fetchRealtors();
  }, []);

  const fetchRealtors = async () => {
    try {
      setLoading(true);
      const response = await axios.get('/property-manager/realtors', {
        headers: { Authorization: `Bearer ${token}` }
      });
      setRealtors(response.data.realtors || []);
    } catch (error) {
      console.error('Failed to fetch realtors:', error);
      setMessage('Failed to load realtors');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteRealtor = async (realtorId, realtorName) => {
    const confirmMessage = `Are you sure you want to delete ${realtorName}?\n\n` +
      `This will:\n` +
      `- Move all their properties back to you (unassigned)\n` +
      `- Unassign all their bookings\n` +
      `- Delete their sources and rule chunks\n` +
      `- Remove them from the system\n\n` +
      `⚠️ This action CANNOT be undone!`;

    if (!window.confirm(confirmMessage)) {
      return;
    }

    try {
      setLoading(true);
      const response = await axios.delete(
        `/property-manager/realtors/${realtorId}`,
        {
          headers: { Authorization: `Bearer ${token}` }
        }
      );

      setMessage(`✅ ${response.data.message}\n` +
        `Properties reassigned: ${response.data.summary.properties_reassigned}\n` +
        `Bookings unassigned: ${response.data.summary.bookings_unassigned}`);
      
      // Refresh the realtors list
      fetchRealtors();
    } catch (error) {
      console.error('Failed to delete realtor:', error);
      setMessage(`❌ Failed: ${error.response?.data?.detail || error.message}`);
    } finally {
      setLoading(false);
    }
  };

  if (loading && realtors.length === 0) {
    return <div className="loading">Loading realtors...</div>;
  }

  return (
    <div className="realtor-management-page">
      <h1>Manage Realtors</h1>

      {message && (
        <div className={`message ${message.startsWith('✅') ? 'success' : 'error'}`}>
          {message.split('\n').map((line, idx) => (
            <div key={idx}>{line}</div>
          ))}
        </div>
      )}

      {realtors.length > 0 ? (
        <div className="realtors-grid">
          {realtors.map(realtor => (
            <div key={realtor.id} className="realtor-card">
              <div className="realtor-header">
                <h3>{realtor.name}</h3>
                <button
                  onClick={() => handleDeleteRealtor(realtor.id, realtor.name)}
                  className="delete-realtor-btn"
                  title="Delete realtor"
                >
                  🗑️ Delete
                </button>
              </div>
              <div className="realtor-details">
                <p><strong>Email:</strong> {realtor.email}</p>
                <p><strong>Contact:</strong> {realtor.contact}</p>
                <p><strong>Properties Assigned:</strong> {realtor.property_count || 0}</p>
                {realtor.is_standalone && (
                  <span className="badge standalone">Standalone</span>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <p>No realtors found.</p>
        </div>
      )}
    </div>
  );
};

export default RealtorManagementPage;
```

### Component 1: Property Assignment Page (PM Assigns Properties)

```jsx
// PropertyAssignmentPage.jsx
import { useState, useEffect } from 'react';
import axios from 'axios';

const PropertyAssignmentPage = () => {
  const [properties, setProperties] = useState([]);
  const [realtors, setRealtors] = useState([]);
  const [selectedProperties, setSelectedProperties] = useState([]);
  const [selectedRealtor, setSelectedRealtor] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null);

  const token = localStorage.getItem('access_token'); // or from your auth context

  useEffect(() => {
    fetchProperties();
    fetchRealtors();
  }, []);

  const fetchProperties = async () => {
    try {
      const response = await axios.get('/apartments', {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      // Filter to only show PM's unassigned properties
      const unassignedProperties = response.data.filter(
        prop => !prop.is_assigned || prop.owner_type === 'property_manager'
      );
      
      setProperties(unassignedProperties);
    } catch (error) {
      console.error('Failed to fetch properties:', error);
      setMessage('Failed to load properties');
    }
  };

  const fetchRealtors = async () => {
    try {
      const response = await axios.get('/property-manager/realtors', {
        headers: { Authorization: `Bearer ${token}` }
      });
      setRealtors(response.data.realtors);
    } catch (error) {
      console.error('Failed to fetch realtors:', error);
      setMessage('Failed to load realtors');
    }
  };

  const handlePropertyToggle = (propertyId) => {
    setSelectedProperties(prev => 
      prev.includes(propertyId)
        ? prev.filter(id => id !== propertyId)
        : [...prev, propertyId]
    );
  };

  const handleSelectAll = () => {
    if (selectedProperties.length === properties.length) {
      setSelectedProperties([]);
    } else {
      setSelectedProperties(properties.map(p => p.id));
    }
  };

  const handleAssign = async () => {
    if (!selectedRealtor || selectedProperties.length === 0) {
      setMessage('Please select a realtor and at least one property');
      return;
    }

    setLoading(true);
    setMessage(null);

    try {
      const response = await axios.post(
        '/property-manager/assign-properties',
        {
          realtor_id: selectedRealtor,
          property_ids: selectedProperties
        },
        {
          headers: { Authorization: `Bearer ${token}` }
        }
      );

      setMessage(`✅ ${response.data.message}`);
      
      // Refresh properties list (assigned ones will disappear)
      fetchProperties();
      setSelectedProperties([]);
      setSelectedRealtor(null);
    } catch (error) {
      console.error('Assignment failed:', error);
      setMessage(`❌ Failed: ${error.response?.data?.detail || error.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="property-assignment-page">
      <h1>Assign Properties to Realtors</h1>

      {/* Realtor Selection */}
      <div className="realtor-selector">
        <label>Select Realtor:</label>
        <select 
          value={selectedRealtor || ''} 
          onChange={(e) => setSelectedRealtor(Number(e.target.value))}
          className="realtor-dropdown"
        >
          <option value="">Choose a realtor...</option>
          {realtors.map(realtor => (
            <option key={realtor.id} value={realtor.id}>
              {realtor.name} ({realtor.email})
            </option>
          ))}
        </select>
      </div>

      {/* Properties List */}
      <div className="properties-section">
        <div className="properties-header">
          <h2>
            Available Properties ({selectedProperties.length} selected)
          </h2>
          <button onClick={handleSelectAll} className="select-all-btn">
            {selectedProperties.length === properties.length ? 'Deselect All' : 'Select All'}
          </button>
        </div>

        <div className="properties-grid">
          {properties.map(property => (
            <div 
              key={property.id} 
              className={`property-card ${selectedProperties.includes(property.id) ? 'selected' : ''}`}
            >
              <input
                type="checkbox"
                checked={selectedProperties.includes(property.id)}
                onChange={() => handlePropertyToggle(property.id)}
                className="property-checkbox"
              />
              <div className="property-info">
                <h3>{property.address}</h3>
                <p className="price">${property.price?.toLocaleString()}</p>
                <div className="property-specs">
                  <span>🛏️ {property.bedrooms} bed</span>
                  <span>🚿 {property.bathrooms} bath</span>
                  {property.square_feet && <span>📐 {property.square_feet} sqft</span>}
                </div>
                {property.property_type && (
                  <p className="property-type">Type: {property.property_type}</p>
                )}
                {property.listing_status && (
                  <span className={`status-badge ${property.listing_status.toLowerCase()}`}>
                    {property.listing_status}
                  </span>
                )}
                {property.features && property.features.length > 0 && (
                  <div className="features">
                    <strong>Features:</strong>
                    <div className="features-list">
                      {property.features.map((feature, idx) => (
                        <span key={idx} className="feature-tag">{feature}</span>
                      ))}
                    </div>
                  </div>
                )}
                {property.agent && (
                  <div className="agent-info">
                    <strong>Agent:</strong> {property.agent.name}
                  </div>
                )}
                <p className="property-id">Listing ID: {property.listing_id || property.id}</p>
              </div>
            </div>
          ))}
        </div>

        {properties.length === 0 && (
          <p className="no-properties">
            No properties available to assign. All properties may already be assigned.
          </p>
        )}
      </div>

      {/* Assign Button */}
      <div className="assign-section">
        <button 
          onClick={handleAssign} 
          disabled={loading || !selectedRealtor || selectedProperties.length === 0}
          className="assign-button"
        >
          {loading ? 'Assigning...' : `Assign ${selectedProperties.length} Properties`}
        </button>
      </div>

      {/* Message Display */}
      {message && (
        <div className={`message ${message.startsWith('✅') ? 'success' : 'error'}`}>
          {message}
        </div>
      )}
    </div>
  );
};

export default PropertyAssignmentPage;
```

---

### Component 2: Property Assignments View (PM Views All Assignments)

```jsx
// PropertyAssignmentsView.jsx
import { useState, useEffect } from 'react';
import axios from 'axios';

const PropertyAssignmentsView = () => {
  const [assignments, setAssignments] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const token = localStorage.getItem('access_token');

  useEffect(() => {
    fetchAssignments();
  }, []);

  const fetchAssignments = async () => {
    try {
      setLoading(true);
      const response = await axios.get('/property-manager/assignments', {
        headers: { Authorization: `Bearer ${token}` }
      });
      setAssignments(response.data);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch assignments:', err);
      setError('Failed to load assignments');
    } finally {
      setLoading(false);
    }
  };

  const handleUnassignProperty = async (propertyId) => {
    if (!window.confirm('Are you sure you want to unassign this property?')) {
      return;
    }

    try {
      const response = await axios.post(
        '/property-manager/unassign-properties',
        { property_ids: [propertyId] },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      
      alert(`✅ ${response.data.message}`);
      fetchAssignments(); // Refresh the view
    } catch (error) {
      console.error('Failed to unassign property:', error);
      alert(`❌ Failed: ${error.response?.data?.detail || error.message}`);
    }
  };

  const handleStatusChange = async (propertyId, newStatus) => {
    try {
      const response = await axios.patch(
        `/properties/${propertyId}/status`,
        { listing_status: newStatus },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      
      // Optionally show success message
      console.log(`✅ ${response.data.message}`);
      fetchAssignments(); // Refresh to show updated status
    } catch (error) {
      console.error('Failed to update status:', error);
      alert(`❌ Failed: ${error.response?.data?.detail || error.message}`);
      fetchAssignments(); // Refresh to revert change
    }
  };

  const handleRemoveAgent = async (propertyId) => {
    if (!window.confirm('Are you sure you want to remove the agent from this property?')) {
      return;
    }

    try {
      const response = await axios.patch(
        `/properties/${propertyId}/agent`,
        { agent: null },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      
      alert(`✅ ${response.data.message}`);
      fetchAssignments(); // Refresh the view
    } catch (error) {
      console.error('Failed to remove agent:', error);
      alert(`❌ Failed: ${error.response?.data?.detail || error.message}`);
    }
  };

  if (loading) return <div className="loading">Loading assignments...</div>;
  if (error) return <div className="error">{error}</div>;
  if (!assignments) return <div>No data available</div>;

  const { unassigned_properties, assigned_properties, summary } = assignments;

  return (
    <div className="property-assignments-view">
      <div className="header">
        <h1>Property Assignments Overview</h1>
        <button onClick={fetchAssignments} className="refresh-btn">
          🔄 Refresh
        </button>
      </div>

      {/* Summary Cards */}
      <div className="summary-cards">
        <div className="summary-card">
          <h3>Total Properties</h3>
          <p className="number">{summary.total_properties}</p>
        </div>
        <div className="summary-card unassigned">
          <h3>Unassigned</h3>
          <p className="number">{summary.unassigned_count}</p>
        </div>
        <div className="summary-card assigned">
          <h3>Assigned</h3>
          <p className="number">{summary.assigned_count}</p>
        </div>
      </div>

      {/* Unassigned Properties Section */}
      <section className="unassigned-section">
        <h2>
          Unassigned Properties 
          <span className="badge">{unassigned_properties.length}</span>
        </h2>
        {unassigned_properties.length > 0 ? (
          <div className="properties-grid">
            {unassigned_properties.map(property => (
              <div key={property.id} className="property-card unassigned-card">
                <div className="property-header">
                  <h3>{property.address || 'N/A'}</h3>
                  <span className="status-badge unassigned-badge">Unassigned</span>
                </div>
                <div className="property-details">
                  <p className="price-large"><strong>${property.price?.toLocaleString() || 'N/A'}</strong></p>
                  <div className="specs-row">
                    <span>🛏️ {property.bedrooms || 'N/A'} bed</span>
                    <span>🚿 {property.bathrooms || 'N/A'} bath</span>
                    {property.square_feet && <span>📐 {property.square_feet} sqft</span>}
                  </div>
                  {property.property_type && (
                    <p><strong>Type:</strong> {property.property_type}</p>
                  )}
                  {property.year_built && (
                    <p><strong>Year Built:</strong> {property.year_built}</p>
                  )}
                  {property.listing_status && (
                    <p><strong>Status:</strong> 
                      <span className={`status ${property.listing_status.toLowerCase()}`}>
                        {property.listing_status}
                      </span>
                    </p>
                  )}
                  {property.days_on_market !== undefined && (
                    <p><strong>Days on Market:</strong> {property.days_on_market}</p>
                  )}
                  {property.features && property.features.length > 0 && (
                    <div className="features-section">
                      <strong>Features:</strong>
                      <div className="features-tags">
                        {property.features.map((feature, idx) => (
                          <span key={idx} className="feature-badge">{feature}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {property.agent && (
                    <div className="agent-section">
                      <div className="agent-header">
                        <strong>Agent:</strong>
                        <button 
                          onClick={() => handleRemoveAgent(property.id)}
                          className="remove-agent-btn"
                          title="Remove agent"
                        >
                          ✕
                        </button>
                      </div>
                      <p>{property.agent.name}</p>
                      {property.agent.email && <p>{property.agent.email}</p>}
                      {property.agent.phone && <p>{property.agent.phone}</p>}
                    </div>
                  )}
                  {property.description && (
                    <p className="description">{property.description}</p>
                  )}
                </div>
                <p className="property-id">Property ID: {property.id}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="empty-state">All properties have been assigned! 🎉</p>
        )}
      </section>

      {/* Assigned Properties by Realtor */}
      <section className="assigned-section">
        <h2>Assigned Properties by Realtor</h2>
        {Object.keys(assigned_properties).length > 0 ? (
          Object.values(assigned_properties).map(realtorGroup => (
            <div key={realtorGroup.realtor_id} className="realtor-group">
              <div className="realtor-header">
                <div className="realtor-info">
                  <h3>{realtorGroup.realtor_name}</h3>
                  <p className="realtor-email">{realtorGroup.realtor_email}</p>
                </div>
                <div className="realtor-count">
                  <span className="count-badge">{realtorGroup.count}</span>
                  <span>properties</span>
                </div>
              </div>
              
              <div className="properties-grid">
                {realtorGroup.properties.map(property => (
                  <div key={property.id} className="property-card assigned-card">
                    <div className="property-header">
                      <h4>{property.address || 'N/A'}</h4>
                      <span className="status-badge assigned-badge">
                        Assigned to {realtorGroup.realtor_name}
                      </span>
                    </div>
                    <div className="property-details">
                      <p className="price-large"><strong>${property.price?.toLocaleString() || 'N/A'}</strong></p>
                      <div className="specs-row">
                        <span>🛏️ {property.bedrooms || 'N/A'} bed</span>
                        <span>🚿 {property.bathrooms || 'N/A'} bath</span>
                        {property.square_feet && <span>📐 {property.square_feet} sqft</span>}
                      </div>
                      {property.property_type && (
                        <p><strong>Type:</strong> {property.property_type}</p>
                      )}
                      {property.year_built && (
                        <p><strong>Year Built:</strong> {property.year_built}</p>
                      )}
                      {property.listing_status && (
                        <p><strong>Status:</strong> 
                          <span className={`status ${property.listing_status.toLowerCase()}`}>
                            {property.listing_status}
                          </span>
                        </p>
                      )}
                      {property.days_on_market !== undefined && (
                        <p><strong>Days on Market:</strong> {property.days_on_market}</p>
                      )}
                      {property.features && property.features.length > 0 && (
                        <div className="features-section">
                          <strong>Features:</strong>
                          <div className="features-tags">
                            {property.features.map((feature, idx) => (
                              <span key={idx} className="feature-badge">{feature}</span>
                            ))}
                          </div>
                        </div>
                      )}
                      {property.agent && (
                        <div className="agent-section">
                          <strong>Agent:</strong>
                          <p>{property.agent.name}</p>
                          {property.agent.email && <p>{property.agent.email}</p>}
                          {property.agent.phone && <p>{property.agent.phone}</p>}
                        </div>
                      )}
                      {property.listing_id && (
                        <p className="listing-id">MLS: {property.listing_id}</p>
                      )}
                      {property.description && (
                        <p className="description">{property.description}</p>
                      )}
                    </div>
                    <div className="property-actions">
                      <button 
                        onClick={() => handleUnassignProperty(property.id)}
                        className="unassign-btn"
                        title="Unassign from realtor"
                      >
                        Unassign
                      </button>
                      <select
                        value={property.listing_status || 'Available'}
                        onChange={(e) => handleStatusChange(property.id, e.target.value)}
                        className="status-select"
                      >
                        <option value="Available">Available</option>
                        <option value="For Sale">For Sale</option>
                        <option value="For Rent">For Rent</option>
                        <option value="Sold">Sold</option>
                        <option value="Rented">Rented</option>
                      </select>
                    </div>
                    <p className="property-id">Property ID: {property.id}</p>
                  </div>
                ))}
              </div>
            </div>
          ))
        ) : (
          <p className="empty-state">No properties assigned yet.</p>
        )}
      </section>

      {/* Realtor Summary */}
      {Object.keys(summary.realtor_counts).length > 0 && (
        <section className="realtor-summary">
          <h2>Realtor Summary</h2>
          <div className="realtor-summary-grid">
            {Object.entries(summary.realtor_counts).map(([realtorId, data]) => (
              <div key={realtorId} className="realtor-summary-card">
                <h4>{data.realtor_name}</h4>
                <p className="count">{data.count} properties</p>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
};

export default PropertyAssignmentsView;
```

---

### Component 3: Realtor Dashboard (Views Assigned Properties)

```jsx
// RealtorDashboard.jsx
import { useState, useEffect } from 'react';
import axios from 'axios';

const RealtorDashboard = () => {
  const [properties, setProperties] = useState([]);
  const [loading, setLoading] = useState(true);

  const token = localStorage.getItem('access_token');

  useEffect(() => {
    fetchProperties();
  }, []);

  const fetchProperties = async () => {
    try {
      const response = await axios.get('/apartments', {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      // This automatically returns ONLY properties assigned to this realtor
      setProperties(response.data);
    } catch (error) {
      console.error('Failed to fetch properties:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className="loading">Loading your properties...</div>;

  return (
    <div className="realtor-dashboard">
      <div className="dashboard-header">
        <h1>My Properties</h1>
        <p className="property-count">{properties.length} properties assigned to you</p>
      </div>
      
      {properties.length > 0 ? (
        <div className="properties-grid">
          {properties.map(property => (
            <div key={property.id} className="property-card">
              {property.image_url && (
                <img 
                  src={property.image_url} 
                  alt={property.address}
                  className="property-image"
                />
              )}
              <div className="property-content">
                <h3>{property.address || 'N/A'}</h3>
                {property.listing_id && (
                  <p className="listing-id">MLS: {property.listing_id}</p>
                )}
                <div className="property-details">
                  <p className="price">${property.price?.toLocaleString() || 'N/A'}</p>
                  <div className="specs">
                    <span>🛏️ {property.bedrooms || 'N/A'} bed</span>
                    <span>🚿 {property.bathrooms || 'N/A'} bath</span>
                    {property.square_feet && <span>📐 {property.square_feet} sqft</span>}
                  </div>
                  {property.property_type && (
                    <p className="property-type">Type: {property.property_type}</p>
                  )}
                  {property.listing_status && (
                    <span className={`status-badge ${property.listing_status.toLowerCase()}`}>
                      {property.listing_status}
                    </span>
                  )}
                  {property.features && property.features.length > 0 && (
                    <div className="features-preview">
                      {property.features.slice(0, 3).map((feature, idx) => (
                        <span key={idx} className="feature-chip">{feature}</span>
                      ))}
                      {property.features.length > 3 && (
                        <span className="feature-more">+{property.features.length - 3} more</span>
                      )}
                    </div>
                  )}
                  {property.agent && (
                    <p className="agent-name">Agent: {property.agent.name}</p>
                  )}
                  {property.description && (
                    <p className="description">{property.description}</p>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <p>No properties assigned yet.</p>
          <p className="help-text">Contact your Property Manager to get properties assigned to you.</p>
        </div>
      )}
    </div>
  );
};

export default RealtorDashboard;
```

---

## 🎨 Complete CSS Styling

```css
/* Property Assignment Page */
.property-assignment-page {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
}

.realtor-selector {
  margin-bottom: 30px;
  padding: 20px;
  background: #f5f5f5;
  border-radius: 8px;
}

.realtor-selector label {
  display: block;
  margin-bottom: 10px;
  font-weight: bold;
  font-size: 16px;
}

.realtor-dropdown {
  padding: 12px;
  font-size: 16px;
  min-width: 300px;
  border: 2px solid #ddd;
  border-radius: 4px;
}

.properties-section {
  margin-bottom: 30px;
}

.properties-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 10px;
  border-bottom: 2px solid #eee;
}

.select-all-btn {
  padding: 8px 16px;
  background: #6c757d;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.select-all-btn:hover {
  background: #5a6268;
}

.properties-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}

.property-card {
  border: 2px solid #ddd;
  border-radius: 8px;
  padding: 15px;
  cursor: pointer;
  transition: all 0.2s;
  background: white;
}

.property-card:hover {
  border-color: #007bff;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  transform: translateY(-2px);
}

.property-card.selected {
  border-color: #007bff;
  background-color: #f0f8ff;
  box-shadow: 0 4px 12px rgba(0,123,255,0.3);
}

.property-checkbox {
  margin-right: 10px;
  transform: scale(1.2);
}

.property-info h3 {
  margin: 10px 0 5px 0;
  color: #333;
}

.property-id {
  font-size: 12px;
  color: #666;
  margin-top: 10px;
}

.assign-section {
  text-align: center;
  margin-top: 30px;
  padding: 20px;
}

.assign-button {
  padding: 15px 30px;
  font-size: 18px;
  background-color: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: bold;
}

.assign-button:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}

.assign-button:hover:not(:disabled) {
  background-color: #0056b3;
}

.message {
  padding: 15px;
  margin-top: 20px;
  border-radius: 4px;
  font-size: 16px;
}

.message.success {
  background-color: #d4edda;
  color: #155724;
  border: 1px solid #c3e6cb;
}

.message.error {
  background-color: #f8d7da;
  color: #721c24;
  border: 1px solid #f5c6cb;
}

/* Property Assignments View */
.property-assignments-view {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30px;
}

.refresh-btn {
  padding: 10px 20px;
  background: #6c757d;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.summary-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
  margin-bottom: 40px;
}

.summary-card {
  padding: 20px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  text-align: center;
}

.summary-card h3 {
  margin: 0 0 10px 0;
  color: #666;
  font-size: 14px;
  text-transform: uppercase;
}

.summary-card .number {
  font-size: 36px;
  font-weight: bold;
  margin: 0;
  color: #333;
}

.summary-card.unassigned .number {
  color: #ffc107;
}

.summary-card.assigned .number {
  color: #28a745;
}

section {
  margin-bottom: 40px;
}

section h2 {
  margin-bottom: 20px;
  color: #333;
  display: flex;
  align-items: center;
  gap: 10px;
}

.badge {
  background: #007bff;
  color: white;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 14px;
}

.unassigned-section,
.assigned-section {
  background: #f9f9f9;
  padding: 30px;
  border-radius: 8px;
  margin-bottom: 30px;
}

.realtor-group {
  margin-bottom: 30px;
  background: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.realtor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 2px solid #eee;
}

.realtor-info h3 {
  margin: 0 0 5px 0;
  color: #333;
}

.realtor-email {
  color: #666;
  font-size: 14px;
  margin: 0;
}

.realtor-count {
  display: flex;
  align-items: center;
  gap: 8px;
}

.count-badge {
  background: #007bff;
  color: white;
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 18px;
  font-weight: bold;
}

.status-badge {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: bold;
}

.unassigned-badge {
  background: #ffc107;
  color: #333;
}

.assigned-badge {
  background: #28a745;
  color: white;
}

.property-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 10px;
}

.property-header h3,
.property-header h4 {
  margin: 0;
  flex: 1;
}

.property-details {
  margin-top: 10px;
}

.property-details p {
  margin: 5px 0;
  color: #555;
}

.description {
  font-size: 14px;
  color: #666;
  margin-top: 10px;
  line-height: 1.4;
}

/* Enhanced Property Details */
.price-large {
  font-size: 28px;
  font-weight: bold;
  color: #007bff;
  margin: 10px 0;
}

.specs-row {
  display: flex;
  gap: 15px;
  margin: 10px 0;
  flex-wrap: wrap;
}

.specs-row span {
  color: #666;
  font-size: 14px;
}

.property-type {
  color: #666;
  font-size: 14px;
  margin: 5px 0;
}

.status {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: bold;
  margin-left: 8px;
}

.status.available {
  background: #28a745;
  color: white;
}

.status.pending {
  background: #ffc107;
  color: #333;
}

.status.sold {
  background: #dc3545;
  color: white;
}

.features-section {
  margin-top: 15px;
}

.features-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.feature-badge,
.feature-tag,
.feature-chip {
  background: #e9ecef;
  color: #495057;
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.feature-more {
  color: #007bff;
  font-size: 12px;
  font-style: italic;
}

.features-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 5px;
}

.features-preview {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
  align-items: center;
}

.agent-info,
.agent-section {
  margin-top: 10px;
  padding: 10px;
  background: #f8f9fa;
  border-radius: 4px;
}

.agent-section p {
  margin: 3px 0;
  font-size: 14px;
  color: #555;
}

.agent-name {
  font-size: 13px;
  color: #666;
  margin-top: 5px;
}

.listing-id {
  font-size: 12px;
  color: #999;
  margin: 5px 0;
}

.empty-state {
  text-align: center;
  padding: 40px;
  color: #666;
  font-size: 16px;
}

.help-text {
  font-size: 14px;
  color: #999;
  margin-top: 10px;
}

.realtor-summary {
  margin-top: 40px;
  padding: 20px;
  background: white;
  border-radius: 8px;
}

.realtor-summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 15px;
}

.realtor-summary-card {
  padding: 15px;
  background: #f8f9fa;
  border-radius: 6px;
  text-align: center;
}

.realtor-summary-card h4 {
  margin: 0 0 5px 0;
  color: #333;
}

.realtor-summary-card .count {
  font-size: 24px;
  font-weight: bold;
  color: #007bff;
  margin: 0;
}

/* Realtor Dashboard */
.realtor-dashboard {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
}

.dashboard-header {
  margin-bottom: 30px;
}

.property-count {
  color: #666;
  font-size: 16px;
}

.property-image {
  width: 100%;
  height: 200px;
  object-fit: cover;
  border-radius: 4px 4px 0 0;
}

.property-content {
  padding: 15px;
}

.property-content h3 {
  margin: 0 0 10px 0;
  color: #333;
}

.price {
  font-size: 24px;
  font-weight: bold;
  color: #007bff;
  margin: 10px 0;
}

.specs {
  display: flex;
  gap: 15px;
  margin: 10px 0;
  color: #666;
}

.loading {
  text-align: center;
  padding: 40px;
  font-size: 18px;
  color: #666;
}

.error {
  text-align: center;
  padding: 20px;
  background: #f8d7da;
  color: #721c24;
  border-radius: 4px;
}

.no-properties {
  text-align: center;
  padding: 40px;
  color: #666;
  font-style: italic;
}

/* Property Actions */
.property-actions {
  display: flex;
  gap: 10px;
  margin-top: 15px;
  padding-top: 15px;
  border-top: 1px solid #eee;
}

.unassign-btn {
  padding: 6px 12px;
  background: #dc3545;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.unassign-btn:hover {
  background: #c82333;
}

.status-select {
  padding: 6px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
  cursor: pointer;
  flex: 1;
}

.status-select:hover {
  border-color: #007bff;
}

.agent-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 5px;
}

.remove-agent-btn {
  background: #dc3545;
  color: white;
  border: none;
  border-radius: 50%;
  width: 20px;
  height: 20px;
  cursor: pointer;
  font-size: 12px;
  line-height: 1;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.remove-agent-btn:hover {
  background: #c82333;
}

/* Realtor Management Page */
.realtor-management-page {
  padding: 40px 20px;
  max-width: 1600px;
  margin: 0 auto;
}

.realtor-management-page h1 {
  font-size: 3rem;
  font-weight: 800;
  background: linear-gradient(135deg, #ffffff 0%, #f0f0f0 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin-bottom: 40px;
  text-align: center;
  text-shadow: 0 4px 20px rgba(255, 255, 255, 0.3);
}

.realtors-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 30px;
  margin-top: 30px;
}

.realtor-card {
  background: rgba(255, 255, 255, 0.15);
  backdrop-filter: blur(20px);
  border-radius: 24px;
  padding: 30px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
  transition: all 0.3s ease;
}

.realtor-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 48px rgba(102, 126, 234, 0.3);
  border-color: rgba(255, 255, 255, 0.5);
}

.realtor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 2px solid rgba(255, 255, 255, 0.2);
}

.realtor-header h3 {
  margin: 0;
  color: #ffffff;
  font-size: 1.5rem;
  font-weight: 700;
  text-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
}

.delete-realtor-btn {
  padding: 10px 20px;
  background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
  color: white;
  border: none;
  border-radius: 12px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  transition: all 0.3s ease;
  box-shadow: 0 4px 20px rgba(250, 112, 154, 0.4);
}

.delete-realtor-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 30px rgba(250, 112, 154, 0.5);
}

.realtor-details {
  color: rgba(255, 255, 255, 0.9);
}

.realtor-details p {
  margin: 10px 0;
  font-size: 15px;
  font-weight: 500;
}

.realtor-details strong {
  color: #ffffff;
  font-weight: 700;
}

.badge.standalone {
  display: inline-block;
  padding: 6px 14px;
  background: linear-gradient(135deg, rgba(79, 172, 254, 0.3) 0%, rgba(0, 242, 254, 0.3) 100%);
  color: #ffffff;
  border-radius: 14px;
  font-size: 12px;
  font-weight: 700;
  margin-top: 10px;
  border: 2px solid rgba(79, 172, 254, 0.5);
}
```

---

## 🔄 Real-time Updates

### Option 1: Manual Refresh
```jsx
// Add refresh button to components
<button onClick={fetchAssignments}>🔄 Refresh</button>
```

### Option 2: Auto Refresh (Polling)
```jsx
useEffect(() => {
  const interval = setInterval(() => {
    fetchAssignments();
  }, 30000); // Every 30 seconds

  return () => clearInterval(interval);
}, []);
```

### Option 3: Refresh on Window Focus
```jsx
useEffect(() => {
  const handleFocus = () => {
    fetchAssignments();
    fetchProperties(); // If you have multiple fetches
  };
  
  window.addEventListener('focus', handleFocus);
  return () => window.removeEventListener('focus', handleFocus);
}, []);
```

---

## 📱 Complete Navigation Structure

```jsx
// PropertyManagerDashboard.jsx
import { useState } from 'react';
import PropertyAssignmentPage from './PropertyAssignmentPage';
import PropertyAssignmentsView from './PropertyAssignmentsView';

const PropertyManagerDashboard = () => {
  const [activeTab, setActiveTab] = useState('assignments'); // or 'assign'

  return (
    <div className="pm-dashboard">
      <nav className="dashboard-nav">
        <button 
          className={activeTab === 'assignments' ? 'active' : ''}
          onClick={() => setActiveTab('assignments')}
        >
          View Assignments
        </button>
        <button 
          className={activeTab === 'assign' ? 'active' : ''}
          onClick={() => setActiveTab('assign')}
        >
          Assign Properties
        </button>
      </nav>

      {activeTab === 'assignments' && <PropertyAssignmentsView />}
      {activeTab === 'assign' && <PropertyAssignmentPage />}
    </div>
  );
};

export default PropertyManagerDashboard;
```

---

## ✅ Testing Checklist

1. **Property Manager Assignment:**
   - [ ] PM can see unassigned properties
   - [ ] PM can select multiple properties
   - [ ] PM can choose a realtor from dropdown
   - [ ] Assignment succeeds and shows success message
   - [ ] Assigned properties disappear from available list

2. **Property Manager View Assignments:**
   - [ ] PM can see all unassigned properties
   - [ ] PM can see all assigned properties grouped by realtor
   - [ ] Summary shows correct counts
   - [ ] Refresh button updates the view

3. **Realtor Dashboard:**
   - [ ] Realtor logs in
   - [ ] Realtor dashboard shows ONLY assigned properties
   - [ ] After PM assigns properties, they appear on Realtor dashboard (after refresh)

4. **Data Isolation:**
   - [ ] Realtor 1 only sees properties assigned to them
   - [ ] Realtor 2 only sees properties assigned to them
   - [ ] PM can see all properties (own + all realtors')

---

## 🚀 Quick Start

1. **Copy the 3 components above** to your frontend
2. **Add the CSS** to your stylesheet
3. **Set up navigation** to switch between "Assign Properties" and "View Assignments"
4. **Test the flow:**
   - Login as PM
   - Go to "Assign Properties" → Assign 5 properties to Realtor 1
   - Go to "View Assignments" → See the 5 properties under Realtor 1
   - Login as Realtor 1 → See those 5 properties on dashboard

---

## 📌 Key Points

- ✅ **Two views for PM:** "Assign Properties" (to assign) and "View Assignments" (to see who has what)
- ✅ **Automatic filtering:** Realtors only see their properties automatically
- ✅ **Clear UI:** Badges and colors show assignment status
- ✅ **Real-time ready:** Easy to add polling or WebSocket updates
- ✅ **Property Management:** Unassign properties, update status, remove/update agents
- ✅ **Status Management:** Change property status between Available, For Sale, For Rent, Sold, Rented

## 🗄️ Database Structure

### Property Data Storage

All property data is stored in the `apartmentlisting` table:
- **`listing_metadata`** (JSONB column): Contains all property information:
  - `listing_id`: String (e.g., "MLS000113")
  - `address`: String
  - `price`: Number
  - `bedrooms`, `bathrooms`: Numbers
  - `square_feet`, `lot_size_sqft`: Numbers
  - `year_built`: Number
  - `property_type`: String (e.g., "Apartment")
  - **`listing_status`**: String ("Available", "For Sale", "For Rent", "Sold", "Rented")
  - `days_on_market`: Number
  - `listing_date`: String (ISO date)
  - **`agent`**: Object with `name`, `phone`, `email` (can be `null`)
  - `features`: Array of strings
  - `description`: String
  - `image_url`: String

### To Check in Database

**Query to see all property statuses:**
```sql
SELECT 
  id,
  source_id,
  listing_metadata->>'listing_status' as status,
  listing_metadata->>'address' as address,
  listing_metadata->>'listing_id' as listing_id,
  listing_metadata->'agent' as agent
FROM apartmentlisting
ORDER BY id;
```

**Query to see properties by status:**
```sql
SELECT 
  id,
  listing_metadata->>'listing_status' as status,
  listing_metadata->>'address' as address
FROM apartmentlisting
WHERE listing_metadata->>'listing_status' = 'Sold';
```

**Query to see properties with agents:**
```sql
SELECT 
  id,
  listing_metadata->>'address' as address,
  listing_metadata->'agent'->>'name' as agent_name,
  listing_metadata->'agent'->>'email' as agent_email
FROM apartmentlisting
WHERE listing_metadata->'agent' IS NOT NULL;
```

**Query to see assignment (which source/property manager/realtor owns property):**
```sql
SELECT 
  al.id,
  al.source_id,
  s.property_manager_id,
  s.realtor_id,
  CASE 
    WHEN s.property_manager_id IS NOT NULL THEN 'Property Manager'
    WHEN s.realtor_id IS NOT NULL THEN 'Realtor'
  END as owner_type
FROM apartmentlisting al
JOIN source s ON al.source_id = s.source_id;
```

**Query to check realtors and their property counts before deletion:**
```sql
SELECT 
  r.realtor_id,
  r.name,
  r.email,
  r.property_manager_id,
  COUNT(al.id) as property_count,
  COUNT(b.id) as booking_count
FROM realtor r
LEFT JOIN source s ON s.realtor_id = r.realtor_id
LEFT JOIN apartmentlisting al ON al.source_id = s.source_id
LEFT JOIN booking b ON b.realtor_id = r.realtor_id
WHERE r.property_manager_id = 1  -- Replace with your PM ID
GROUP BY r.realtor_id, r.name, r.email, r.property_manager_id;
```

**Query to verify properties were reassigned after deletion:**
```sql
SELECT 
  al.id,
  al.source_id,
  s.property_manager_id,
  s.realtor_id,
  listing_metadata->>'address' as address
FROM apartmentlisting al
JOIN source s ON al.source_id = s.source_id
WHERE s.property_manager_id = 1  -- Replace with your PM ID
ORDER BY al.id;
```

Everything is ready! Just copy the components and CSS, and you'll have a complete property assignment system! 🎉
