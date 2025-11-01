# Frontend & Backend Integration Guide
## Property Assignment Feature

This guide explains how to integrate the property assignment feature so Property Managers can assign properties to Realtors, and those properties appear on the Realtor's dashboard.

---

## 📋 Overview

**Flow:**
1. Property Manager views all available properties (from their source)
2. PM selects properties and assigns them to a Realtor
3. Backend updates `source_id` of those properties to the Realtor's source
4. Realtor's dashboard automatically shows assigned properties (via `/apartments` endpoint)

**Key Points:**
- ✅ Backend is **already complete** - no changes needed
- ✅ Data isolation is **already working** - Realtors only see their properties
- ✅ You just need to **connect the frontend UI**

---

## 🔌 Backend Endpoints (Already Working)

### 1. Get Properties for PM (Available to Assign)
```http
GET /apartments
Authorization: Bearer <pm_jwt_token>
```
**Response:** Array of all properties PM can assign
```json
[
  {
    "id": 1,
    "address": "123 Main St",
    "price": 1500,
    "bedrooms": 2,
    "bathrooms": 1,
    "description": "...",
    "image_url": "...",
    "source_id": 123,
    "owner_type": "property_manager",
    "owner_id": 1,
    "owner_name": "John Smith"
  },
  ...
]
```

### 2. Get Managed Realtors
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

### 3. Assign Properties to Realtor
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

### 4. Get Properties for Realtor (Dashboard)
```http
GET /apartments
Authorization: Bearer <realtor_jwt_token>
```
**Response:** Only properties assigned to this realtor
```json
[
  {
    "id": 1,
    "address": "123 Main St",
    "price": 1500,
    "bedrooms": 2,
    "bathrooms": 1,
    "source_id": 456,
    "owner_type": "realtor",
    "owner_id": 1,
    "owner_name": "Sarah Johnson"
  },
  ...
]
```

---

## 🎨 Frontend Implementation

### Step 1: Property Manager Assignment Page

Create a component for PMs to assign properties:

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

  // Get auth token from your auth context/store
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
      
      // Filter to only show PM's own properties (not already assigned to realtors)
      const pmProperties = response.data.filter(
        prop => prop.owner_type === 'property_manager'
      );
      
      setProperties(pmProperties);
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
      
      // Refresh properties list (assigned ones will no longer show)
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
                <p>Price: ${property.price}</p>
                <p>Bedrooms: {property.bedrooms} | Bathrooms: {property.bathrooms}</p>
                <p className="property-id">ID: {property.id}</p>
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

### Step 2: Realtor Dashboard (Already Works!)

The Realtor dashboard should use the same `/apartments` endpoint:

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

  if (loading) return <div>Loading...</div>;

  return (
    <div className="realtor-dashboard">
      <h1>My Properties ({properties.length})</h1>
      
      <div className="properties-grid">
        {properties.map(property => (
          <div key={property.id} className="property-card">
            <h3>{property.address}</h3>
            <p>Price: ${property.price}</p>
            <p>Bedrooms: {property.bedrooms} | Bathrooms: {property.bathrooms}</p>
          </div>
        ))}
      </div>

      {properties.length === 0 && (
        <p>No properties assigned yet. Contact your Property Manager.</p>
      )}
    </div>
  );
};

export default RealtorDashboard;
```

---

## 🔄 Automatic Updates (Real-time Options)

### Option 1: Polling (Simple)
```jsx
// In RealtorDashboard, poll every 30 seconds
useEffect(() => {
  const interval = setInterval(() => {
    fetchProperties();
  }, 30000); // 30 seconds

  return () => clearInterval(interval);
}, []);
```

### Option 2: WebSocket (Advanced)
If you want real-time updates, implement WebSocket on backend and listen for assignment events.

### Option 3: Refresh on Focus
```jsx
useEffect(() => {
  const handleFocus = () => fetchProperties();
  window.addEventListener('focus', handleFocus);
  return () => window.removeEventListener('focus', handleFocus);
}, []);
```

---

## 📝 CSS Styling (Basic Example)

```css
.property-assignment-page {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.realtor-selector {
  margin-bottom: 30px;
}

.realtor-dropdown {
  padding: 10px;
  font-size: 16px;
  min-width: 300px;
}

.properties-section {
  margin-bottom: 30px;
}

.properties-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
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
}

.property-card:hover {
  border-color: #007bff;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.property-card.selected {
  border-color: #007bff;
  background-color: #f0f8ff;
}

.property-checkbox {
  margin-right: 10px;
}

.assign-button {
  padding: 12px 24px;
  font-size: 16px;
  background-color: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.assign-button:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}

.message {
  padding: 15px;
  margin-top: 20px;
  border-radius: 4px;
}

.message.success {
  background-color: #d4edda;
  color: #155724;
}

.message.error {
  background-color: #f8d7da;
  color: #721c24;
}
```

---

## ✅ Testing Checklist

1. **Property Manager Flow:**
   - [ ] PM can see all available properties
   - [ ] PM can select multiple properties
   - [ ] PM can choose a realtor from dropdown
   - [ ] Assignment succeeds and shows success message
   - [ ] Assigned properties disappear from PM's available list

2. **Realtor Flow:**
   - [ ] Realtor logs in
   - [ ] Realtor dashboard shows ONLY assigned properties
   - [ ] After PM assigns properties, they appear on Realtor dashboard (after refresh)

3. **Data Isolation:**
   - [ ] Realtor 1 only sees properties assigned to them
   - [ ] Realtor 2 only sees properties assigned to them
   - [ ] PM can see all properties (own + all realtors')

---

## 🚀 Quick Start

1. **Add PropertyAssignmentPage component** to your PM dashboard
2. **Ensure RealtorDashboard uses `/apartments` endpoint**
3. **Test the flow:**
   - Login as PM
   - Assign 5 properties to Realtor 1
   - Login as Realtor 1
   - Verify those 5 properties appear on dashboard

**That's it!** The backend handles everything automatically. The `/apartments` endpoint already filters based on user type and source ownership.

---

## 📌 Key Points

- ✅ **No backend changes needed** - everything is already implemented
- ✅ **Data isolation works automatically** - `/apartments` endpoint filters correctly
- ✅ **Assignment is instant** - properties move from PM source to Realtor source immediately
- ✅ **Simple frontend** - just UI components calling existing endpoints

The hardest part is already done! You just need to build the UI. 🎉

