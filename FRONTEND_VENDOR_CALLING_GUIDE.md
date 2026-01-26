# Frontend Implementation Guide: Automated Vendor Calling for Maintenance Requests

> **Note:** This feature has been simplified. Vendor calling assistant ID is configured by the technical team in Supabase. SMS/reminder systems are not part of this feature.

## Table of Contents
1. [Feature Overview](#feature-overview)
2. [Architecture & Data Models](#architecture--data-models)
3. [API Endpoints Reference](#api-endpoints-reference)
4. [UI Components & Pages](#ui-components--pages)
5. [State Management](#state-management)
6. [Integration Steps](#integration-steps)
7. [Code Examples](#code-examples)
8. [Real-time Updates](#real-time-updates)
9. [Error Handling](#error-handling)
10. [Testing Checklist](#testing-checklist)
11. [Architecture Summary](#architecture-summary)

---

## Feature Overview

### What This Feature Does

When a tenant submits a maintenance request, the system can automatically call repair vendors (electrician, plumber, carpenter, HVAC, etc.) linked to **that specific property** to:
- Check vendor availability
- Collect time estimates
- Get cost estimates
- Assign the best available vendor

### Architecture Overview

**Important Architecture Points:**

1. **One PM → Multiple Properties**: A Property Manager can manage multiple properties
2. **Each Property → Multiple Vendors**: Each property can have multiple vendors assigned
3. **Vendors are PM-Level**: Vendors are created/managed at the PM level (PM owns the vendor pool)
4. **Vendors are Property-Specific**: Vendors are assigned to specific properties via PropertyVendor links
5. **Maintenance Requests are Property-Linked**: Maintenance requests already have `property_id` (from tenant record)
6. **Vendor Matching is Property-Based**: System matches vendors based on the property_id from the maintenance request

### Data Flow Example

```
PM (Property Manager)
  ├── Vendor Pool (PM owns these - created at PM level)
  │   ├── Vendor A (ABC Plumbing)
  │   ├── Vendor B (XYZ Electric)
  │   └── Vendor C (Quick Fix HVAC)
  │
  └── Properties
      ├── Property 1 (123 Main St)
      │   ├── PropertyVendor: Vendor A → plumber, priority 1
      │   └── PropertyVendor: Vendor B → electrician, priority 1
      │
      ├── Property 2 (456 Oak Ave)
      │   ├── PropertyVendor: Vendor A → plumber, priority 1 (same vendor, different property)
      │   └── PropertyVendor: Vendor C → hvac, priority 1
      │
      └── Property 3 (789 Pine Rd)
          └── PropertyVendor: Vendor B → electrician, priority 1

Tenant (John, renting Property 1)
  ├── tenant_id: 10
  ├── property_id: Property 1 ← Tenant is linked to Property 1
  └── Maintenance Request
      ├── tenant_id: 10
      ├── property_id: Property 1 ← Inherited from tenant (KEY FOR VENDOR MATCHING)
      ├── category: "plumbing"
      └── System automatically:
          ├── Gets property_id from maintenance request
          ├── Finds PropertyVendor records for Property 1
          ├── Filters by service_type = "plumber" (mapped from "plumbing")
          ├── Sorts by priority
          └── Calls Vendor A (plumber, priority 1) for Property 1
```

### Architecture Summary

**Three-Level Hierarchy:**

1. **PM Level (Top)**
   - PM creates/manages vendors
   - Vendors belong to PM (`property_manager_id`)
   - Vendors are reusable across properties

2. **Property Level (Middle)**
   - PM assigns vendors to specific properties
   - Each property has its own vendor list
   - Same vendor can be assigned to multiple properties
   - Each property-vendor link has:
     - Service type (for that property)
     - Priority (for that property)
     - Notes (property-specific)

3. **Maintenance Request Level (Bottom)**
   - Maintenance request already has `property_id` (from tenant)
   - System automatically matches vendors from that property
   - No manual property selection needed

### Key User Flows

1. **PM Setup Flow**: 
   - PM creates vendors (PM-level, reusable across properties)
   - PM assigns vendors to specific properties
   - PM sets priority per property (same vendor can have different priority for different properties)
   
2. **Auto-Calling Flow**: 
   - Tenant submits maintenance request (already has property_id)
   - System automatically matches vendors for that property
   - System calls vendors in priority order
   
3. **Manual Calling Flow**: 
   - PM manually triggers vendor calls for a maintenance request
   - System uses property_id from maintenance request to find vendors
   
4. **Monitoring Flow**: 
   - PM views call status, attempts, and outcomes
   - All data is scoped to the specific property via maintenance request
   
5. **Assignment Flow**: 
   - PM reviews vendor responses and assigns vendor
   - Vendor is assigned to the maintenance request (which is already property-linked)

### Base URL

All API endpoints use: `https://leasing-copilot-mvp.onrender.com`

---

## Architecture & Data Models

### Vendor Model

**Note:** Vendors are created at PM level but assigned to specific properties.

```typescript
interface Vendor {
  vendor_id: number;
  property_manager_id: number; // PM who owns/manages this vendor
  name: string;
  service_type: 'electrician' | 'plumber' | 'carpenter' | 'hvac' | 'general' | 'emergency';
  phone_number: string; // E.164 format: +14125551234
  backup_phone?: string;
  email?: string;
  operating_hours_start?: string; // "09:00:00"
  operating_hours_end?: string; // "17:00:00"
  emergency_available: boolean;
  timezone: string; // "America/New_York"
  notes?: string;
  is_active: boolean;
  opted_out: boolean;
  opt_out_timestamp?: string;
  opt_out_method?: 'voice' | 'keypad' | 'sms' | 'email' | 'manual';
  created_at: string;
  updated_at: string;
}

// Important: A vendor can be assigned to multiple properties
// The same vendor (e.g., "ABC Plumbing") can serve Property 1 and Property 2
// But they may have different priorities for each property
```

### PropertyVendor Model

**This is the key linking table:** Links vendors to specific properties with property-specific configuration.

```typescript
interface PropertyVendor {
  property_vendor_id: number;
  property_id: number; // Which property this vendor is assigned to
  vendor_id: number; // Which vendor (from PM's vendor pool)
  vendor_name: string;
  service_type: string; // Service type for THIS property (vendor can provide different services per property)
  priority: number; // Priority for THIS property (1 = first call, 2 = second call, etc.)
  notes?: string; // Property-specific notes
  vendor_phone: string;
  vendor_email?: string;
  emergency_available: boolean;
}

// Example:
// Vendor A (ABC Plumbing) can be:
// - Property 1: plumber, priority 1
// - Property 2: plumber, priority 2 (different priority for different property)
// - Property 3: general, priority 1 (different service type for different property)
```

### VendorCallQueue Model

```typescript
interface VendorCallQueue {
  queue_id: number;
  maintenance_request_id: number;
  status: 'pending' | 'calling' | 'completed' | 'cancelled' | 'paused';
  current_vendor_index: number;
  vendor_queue: Array<{
    vendor_id: number;
    priority: number;
    name: string;
  }>;
  max_retries_per_vendor: number;
  retry_delay_minutes: number;
  started_at?: string;
  completed_at?: string;
}
```

### VendorCallAttempt Model

```typescript
interface VendorCallAttempt {
  attempt_id: number;
  maintenance_request_id: number;
  vendor_id: number;
  vendor_name: string;
  call_status: 'initiated' | 'answered' | 'declined' | 'no_answer' | 'voicemail' | 'failed';
  outcome?: 'accepted' | 'declined' | 'no_response' | 'voicemail';
  is_available?: boolean;
  earliest_available_time?: string;
  estimated_cost_range?: string;
  vendor_notes?: string;
  vapi_call_id?: string;
  call_transcript?: string;
  call_recording_url?: string;
  call_duration_seconds?: number;
  attempt_number: number;
  initiated_at: string;
  answered_at?: string;
  completed_at?: string;
}
```

### MaintenanceRequest (Updated Fields)

**Important:** Maintenance requests already have `property_id` from the tenant record.

```typescript
interface MaintenanceRequest {
  // ... existing fields ...
  tenant_id: number; // Tenant who submitted (already has property_id)
  property_id: number; // Property this request is for (from tenant record) - **KEY FOR VENDOR MATCHING**
  property_manager_id: number; // PM who manages this property
  // ... other fields ...
  assigned_vendor_id?: number; // Vendor assigned to handle this request
  vendor_call_status?: 'not_started' | 'calling' | 'vendor_accepted' | 'vendor_declined' | 'no_response' | 'paused' | 'cancelled';
  vendor_call_automation_enabled: boolean;
}

// Vendor matching flow:
// 1. Get property_id from maintenance_request
// 2. Find PropertyVendor records where property_id matches
// 3. Filter by service_type (mapped from issue category)
// 4. Sort by priority
// 5. Call vendors in order
```

### PropertyVendorSettings Model

```typescript
interface PropertyVendorSettings {
  settings_id: number;
  property_id: number;
  auto_call_enabled: boolean;
  emergency_only: boolean;
  call_time_restrictions?: {
    start_hour: number;
    end_hour: number;
    timezone: string;
  };
}
```

---

## API Endpoints Reference

### Authentication

All endpoints require authentication. Include the auth token in headers:
```typescript
headers: {
  'Authorization': `Bearer ${authToken}`,
  'Content-Type': 'application/json'
}
```

### 1. Vendor Management Endpoints

#### Create Vendor
```typescript
POST /vendors

Request Body:
{
  "name": "ABC Plumbing",
  "service_type": "plumber",
  "phone_number": "+14125551234",
  "backup_phone": "+14125551235", // optional
  "email": "contact@abcplumbing.com", // optional
  "operating_hours_start": "09:00", // optional, format: "HH:MM"
  "operating_hours_end": "17:00", // optional
  "emergency_available": true,
  "timezone": "America/New_York", // optional, default: "America/New_York"
  "notes": "Preferred vendor" // optional
}

Response: Vendor object
```

#### Get All Vendors
```typescript
GET /vendors?service_type=plumber&is_active=true

Query Parameters:
- service_type (optional): Filter by service type
- is_active (optional): Filter by active status

Response: {
  "vendors": Vendor[]
}
```

#### Get Single Vendor
```typescript
GET /vendors/{vendor_id}

Response: Vendor object
```

#### Update Vendor
```typescript
PATCH /vendors/{vendor_id}

Request Body: Partial Vendor object (only fields to update)

Response: Updated Vendor object
```

#### Delete Vendor (Soft Delete)
```typescript
DELETE /vendors/{vendor_id}

Response: {
  "message": "Vendor deleted successfully",
  "vendor_id": number
}
```

#### Opt-Out Vendor
```typescript
POST /vendors/{vendor_id}/opt-out

Response: {
  "message": "Vendor opted out successfully",
  "vendor_id": number,
  "vendor_name": string,
  "opted_out": true,
  "opt_out_timestamp": string
}
```

#### Clear Vendor Opt-Out
```typescript
POST /vendors/{vendor_id}/clear-opt-out

Response: {
  "message": "Vendor opt-out status cleared successfully",
  "vendor_id": number,
  "vendor_name": string,
  "opted_out": false
}
```

### 2. Property-Vendor Linking Endpoints

#### Link Vendor to Property
```typescript
POST /properties/{property_id}/vendors

Request Body:
{
  "vendor_id": 1,
  "service_type": "plumber",
  "priority": 1, // 1 = first call, 2 = second call, etc.
  "notes": "Primary plumber for this property" // optional
}

Response: PropertyVendor object
```

#### Get Property Vendors
```typescript
GET /properties/{property_id}/vendors?service_type=plumber

Query Parameters:
- service_type (optional): Filter by service type

Response: {
  "property_vendors": PropertyVendor[]
}
```

#### Unlink Vendor from Property
```typescript
DELETE /properties/{property_id}/vendors/{property_vendor_id}

Response: {
  "message": "Vendor unlinked from property successfully",
  "property_vendor_id": number
}
```

### 3. Vendor Calling Endpoints

#### Start Vendor Calls
```typescript
POST /maintenance-requests/{request_id}/start-vendor-calls

Response: {
  "success": true,
  "call_id": string, // VAPI call ID
  "vendor_id": number,
  "vendor_name": string,
  "attempt_id": number
}
```

#### Get Vendor Call Status
```typescript
GET /maintenance-requests/{request_id}/vendor-call-status

Response: {
  "maintenance_request_id": number,
  "vendor_call_status": string,
  "assigned_vendor_id": number | null,
  "queue": VendorCallQueue | null,
  "call_attempts": VendorCallAttempt[]
}
```

#### Pause Vendor Calls
```typescript
POST /maintenance-requests/{request_id}/pause-vendor-calls

Response: {
  "success": true,
  "message": "Vendor calling paused"
}
```

#### Cancel Vendor Calls
```typescript
POST /maintenance-requests/{request_id}/cancel-vendor-calls

Response: {
  "success": true,
  "message": "Vendor calling cancelled"
}
```

### 4. Property Settings Endpoints

#### Update Property Vendor Settings
```typescript
POST /properties/{property_id}/vendor-settings

Request Body:
{
  "auto_call_enabled": true,
  "emergency_only": false,
  "call_time_restrictions": { // optional
    "start_hour": 8,
    "end_hour": 21,
    "timezone": "America/New_York"
  }
}

Response: PropertyVendorSettings object
```

#### Get Property Vendor Settings
```typescript
GET /properties/{property_id}/vendor-settings

Response: PropertyVendorSettings object (or defaults if not configured)
```


---

## UI Components & Pages

### 1. Vendor Management Page

**Route:** `/vendors` or `/settings/vendors`

**Purpose:** Manage PM's vendor pool (PM-level, not property-specific)

**Features:**
- List all vendors for the PM with filters (service type, active status)
- Create new vendor button (vendor is added to PM's pool)
- Edit/Delete vendor actions
- Opt-out status indicator
- Search functionality
- **Optional Enhancement:** Show which properties each vendor is assigned to

**Component Structure:**
```
VendorManagementPage
├── PageHeader
│   ├── Title: "Vendor Management"
│   └── Description: "Manage your vendor pool. Vendors can be assigned to multiple properties."
├── VendorList
│   ├── VendorCard (for each vendor)
│   │   ├── VendorInfo
│   │   ├── ServiceTypeBadge
│   │   ├── OptOutBadge (if opted out)
│   │   ├── AssignedPropertiesCount (optional: "Assigned to 3 properties")
│   │   └── ActionButtons (Edit, Delete, Opt-Out)
│   └── CreateVendorButton
└── VendorFormModal
    ├── BasicInfoSection
    ├── ContactInfoSection
    ├── OperatingHoursSection
    └── EmergencyAvailabilityToggle
    └── Note: "This vendor will be added to your vendor pool. Assign it to properties later."
```

### 2. Property Vendor Configuration Page

**Route:** `/properties/{propertyId}/vendors`

**Purpose:** Assign vendors from PM's pool to THIS specific property

**Features:**
- List vendors linked to THIS property only
- Group by service type
- Show priority order (per property)
- Add vendor from PM's pool
- Remove vendor from property (doesn't delete vendor, just unlinks)
- Edit priority (property-specific)
- **Key Point:** Same vendor can appear multiple times with different service types

**Component Structure:**
```
PropertyVendorPage
├── PageHeader
│   ├── Title: "Property Vendors"
│   ├── PropertyName/Address
│   └── Description: "Assign vendors to this property. Configure priority and service types."
├── ServiceTypeTabs (Electrician, Plumber, etc.)
│   └── VendorPriorityList
│       ├── VendorPriorityItem (draggable for reordering)
│       │   ├── PriorityNumber (1st call, 2nd call, etc.)
│       │   ├── VendorName
│       │   ├── VendorContact
│       │   ├── PriorityIndicator
│       │   └── ActionButtons (Edit Priority, Remove)
│       └── AddVendorButton
│           └── Opens modal to select from PM's vendor pool
└── PropertyVendorSettingsCard
    ├── AutoCallToggle
    ├── EmergencyOnlyToggle
    └── CallTimeRestrictions
```

**Add Vendor Modal:**
```
AddVendorToPropertyModal
├── VendorSelector (dropdown of PM's vendors)
├── ServiceTypeSelector
├── PriorityInput (1, 2, 3, etc.)
├── NotesInput (optional)
└── SubmitButton
```

### 3. Maintenance Request Detail Page (Enhanced)

**Route:** `/maintenance-requests/{requestId}`

**New Sections to Add:**

#### Vendor Calling Section
```
VendorCallingSection
├── VendorCallStatusCard
│   ├── StatusBadge (calling, accepted, declined, etc.)
│   ├── AssignedVendorInfo (if assigned)
│   └── ActionButtons (Start, Pause, Cancel)
├── CallQueueCard
│   ├── QueueStatus
│   ├── CurrentVendorIndicator
│   └── VendorQueueList
└── CallAttemptsTimeline
    ├── CallAttemptCard (for each attempt)
    │   ├── VendorInfo
    │   ├── CallStatus
    │   ├── Outcome
    │   ├── ResponseDetails (time, cost, notes)
    │   ├── TranscriptButton
    │   └── RecordingButton
    └── EmptyState (if no attempts)
```

### 4. Vendor Selection Modal

**Component:** Used when PM wants to manually assign a vendor

```
VendorSelectionModal
├── ServiceTypeFilter
├── VendorList
│   └── VendorOptionCard
│       ├── VendorInfo
│       ├── AvailabilityStatus
│       ├── OperatingHours
│       └── SelectButton
└── SelectedVendorSummary
```

---

## State Management

### Recommended State Structure

```typescript
// Vendor Management State
interface VendorState {
  vendors: Vendor[];
  selectedVendor: Vendor | null;
  loading: boolean;
  error: string | null;
  filters: {
    serviceType?: string;
    isActive?: boolean;
  };
}

// Property Vendor State
interface PropertyVendorState {
  propertyVendors: Record<number, PropertyVendor[]>; // keyed by property_id
  settings: Record<number, PropertyVendorSettings>; // keyed by property_id
  loading: boolean;
}

// Vendor Calling State
interface VendorCallingState {
  queues: Record<number, VendorCallQueue>; // keyed by maintenance_request_id
  attempts: Record<number, VendorCallAttempt[]>; // keyed by maintenance_request_id
  activeCalls: Set<number>; // maintenance_request_ids with active calls
  loading: boolean;
}
```

### Redux/Context Actions

```typescript
// Vendor Actions
- fetchVendors()
- createVendor(vendorData)
- updateVendor(vendorId, updates)
- deleteVendor(vendorId)
- optOutVendor(vendorId)
- clearOptOut(vendorId)

// Property Vendor Actions
- fetchPropertyVendors(propertyId)
- linkVendorToProperty(propertyId, vendorId, serviceType, priority)
- unlinkVendorFromProperty(propertyId, propertyVendorId)
- updatePropertyVendorSettings(propertyId, settings)

// Vendor Calling Actions
- startVendorCalls(maintenanceRequestId)
- fetchVendorCallStatus(maintenanceRequestId)
- pauseVendorCalls(maintenanceRequestId)
- cancelVendorCalls(maintenanceRequestId)
```

---

## Integration Steps

### Step 1: Add Vendor Management to Settings

**Vendors are PM-level (not property-specific at creation)**

1. Create `/settings/vendors` route
2. Implement vendor list component
   - Shows all vendors for the PM
   - Can filter by service type
   - Shows which properties each vendor is assigned to (optional enhancement)
3. Add create/edit vendor form
   - Vendor is created at PM level
   - No property selection during creation
4. Integrate with `GET /vendors` and `POST /vendors` endpoints
   - These endpoints return all vendors for the PM
   - Same vendor can later be assigned to multiple properties

### Step 2: Add Property Vendor Configuration

**This is where vendors are assigned to specific properties**

1. Add "Vendors" tab to property detail page (`/properties/{propertyId}/vendors`)
2. Implement property vendor list component
   - Shows only vendors assigned to THIS property
   - Group by service type
   - Show priority order per service type
3. Add "Link Vendor" functionality
   - Modal to select from PM's vendor pool
   - Select vendor, service type, and priority
   - Same vendor can be added multiple times with different service types
4. Implement priority reordering (drag-and-drop or up/down buttons)
   - Priority is per property (same vendor can have different priority for different properties)
5. Integrate with property vendor endpoints
   - `GET /properties/{property_id}/vendors` - Get vendors for this property
   - `POST /properties/{property_id}/vendors` - Assign vendor to this property
   - `DELETE /properties/{property_id}/vendors/{property_vendor_id}` - Remove vendor from this property

### Step 3: Enhance Maintenance Request Page

**Maintenance request already has property_id - vendors are matched from that property**

1. Add "Vendor Calling" section to maintenance request detail page
   - Section should show which property this request is for
   - Display property address/name for context
2. Display vendor call status badge
   - Status reflects the calling process for vendors assigned to this property
3. Show call queue and attempts
   - Queue shows vendors from the property this request is for
   - Attempts show calls to vendors assigned to this property
4. Add action buttons (Start, Pause, Cancel)
   - When starting calls, system automatically uses property_id from maintenance request
   - No need to specify property - it's already linked
5. Integrate with vendor calling endpoints
   - All endpoints use maintenance_request_id
   - Backend automatically uses property_id from maintenance request for vendor matching

### Step 5: Add Real-time Updates

1. Implement polling for active vendor calls
2. Update call status every 5-10 seconds for active calls
3. Show loading states during calls
4. Display new call attempts as they occur

### Step 6: Add Notifications

1. Show toast notifications when:
   - Vendor accepts
   - Vendor declines
   - All vendors exhausted
   - Call fails
2. Update maintenance request status in real-time

---

## Important Implementation Notes

### Vendor Assignment Flow

1. **PM creates vendors** (PM-level, reusable)
   - Vendor is added to PM's vendor pool
   - Not yet assigned to any property

2. **PM assigns vendors to properties** (property-specific)
   - Go to property detail page → Vendors tab
   - Select vendor from PM's pool
   - Set service type and priority for THIS property
   - Same vendor can be assigned to multiple properties with different priorities

3. **Tenant submits maintenance request**
   - Request already has `property_id` (from tenant record)
   - System automatically finds vendors assigned to that property

4. **System matches and calls vendors**
   - Uses `property_id` from maintenance request
   - Finds PropertyVendor records for that property
   - Calls vendors in priority order

### Key UI Considerations

- **Vendor Management Page**: Shows all PM's vendors (not property-specific)
- **Property Vendor Page**: Shows vendors assigned to THIS property
- **Maintenance Request Page**: Shows vendors being called for THIS property (auto-matched)
- **Vendor can appear in multiple properties**: Same vendor, different priorities/configurations

## Code Examples

### Example 1: Fetch and Display Vendors (PM-Level)

**This shows all vendors for the PM (not property-specific)**

```typescript
// React Component Example
import { useState, useEffect } from 'react';
import { fetchVendors } from '../api/vendors';

const VendorList = () => {
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    serviceType: '',
    isActive: true
  });

  useEffect(() => {
    loadVendors();
  }, [filters]);

  const loadVendors = async () => {
    try {
      setLoading(true);
      // This fetches ALL vendors for the PM (not property-specific)
      const response = await fetchVendors(filters);
      setVendors(response.vendors);
    } catch (error) {
      console.error('Failed to load vendors:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <h1>Vendor Management</h1>
        <p>Manage your vendor pool. Vendors can be assigned to multiple properties.</p>
      </div>
      <VendorFilters filters={filters} onChange={setFilters} />
      {loading ? (
        <LoadingSpinner />
      ) : (
        <div className="vendor-grid">
          {vendors.map(vendor => (
            <VendorCard 
              key={vendor.vendor_id} 
              vendor={vendor}
              // Optional: Show which properties this vendor is assigned to
              showPropertyCount={true}
            />
          ))}
        </div>
      )}
    </div>
  );
};
```

### Example 1b: Fetch and Display Property Vendors

**This shows vendors assigned to a specific property**

```typescript
// React Component Example
const PropertyVendorList = ({ propertyId }) => {
  const [propertyVendors, setPropertyVendors] = useState<PropertyVendor[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadPropertyVendors();
  }, [propertyId]);

  const loadPropertyVendors = async () => {
    try {
      setLoading(true);
      // This fetches vendors assigned to THIS property only
      const response = await fetch(
        `${API_BASE_URL}/properties/${propertyId}/vendors`,
        {
          headers: {
            'Authorization': `Bearer ${getAuthToken()}`
          }
        }
      );
      const data = await response.json();
      setPropertyVendors(data.property_vendors);
    } catch (error) {
      console.error('Failed to load property vendors:', error);
    } finally {
      setLoading(false);
    }
  };

  // Group by service type
  const vendorsByService = propertyVendors.reduce((acc, pv) => {
    if (!acc[pv.service_type]) {
      acc[pv.service_type] = [];
    }
    acc[pv.service_type].push(pv);
    return acc;
  }, {});

  return (
    <div>
      <div className="page-header">
        <h1>Property Vendors</h1>
        <p>Vendors assigned to this property. Configure priority and service types.</p>
      </div>
      {Object.entries(vendorsByService).map(([serviceType, vendors]) => (
        <ServiceTypeSection 
          key={serviceType}
          serviceType={serviceType}
          vendors={vendors}
          onPriorityChange={handlePriorityChange}
        />
      ))}
    </div>
  );
};
```

### Example 2: Create Vendor (PM-Level)

**Note:** Vendor is created at PM level. It's not yet assigned to any property.

```typescript
// API Service
export const createVendor = async (vendorData: Partial<Vendor>) => {
  const response = await fetch(`${API_BASE_URL}/vendors`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${getAuthToken()}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(vendorData)
  });

  if (!response.ok) {
    throw new Error('Failed to create vendor');
  }

  return response.json();
};

// React Component
const CreateVendorForm = ({ onSuccess }) => {
  const [formData, setFormData] = useState({
    name: '',
    service_type: 'plumber',
    phone_number: '',
    email: '',
    operating_hours_start: '09:00',
    operating_hours_end: '17:00',
    emergency_available: false
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      // Vendor is created at PM level (not property-specific)
      const vendor = await createVendor(formData);
      showSuccessToast('Vendor created. Assign it to properties in property settings.');
      onSuccess(vendor);
      // Reset form or close modal
    } catch (error) {
      showErrorToast('Failed to create vendor');
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <div className="info-banner">
        <p>This vendor will be added to your vendor pool. You can assign it to properties later.</p>
      </div>
      {/* Form fields */}
    </form>
  );
};
```

### Example 2b: Assign Vendor to Property

**This links an existing vendor to a specific property**

```typescript
// API Service
export const linkVendorToProperty = async (
  propertyId: number,
  vendorId: number,
  serviceType: string,
  priority: number,
  notes?: string
) => {
  const response = await fetch(`${API_BASE_URL}/properties/${propertyId}/vendors`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${getAuthToken()}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      vendor_id: vendorId,
      service_type: serviceType,
      priority: priority,
      notes: notes
    })
  });

  if (!response.ok) {
    throw new Error('Failed to link vendor to property');
  }

  return response.json();
};

// React Component
const AssignVendorToPropertyModal = ({ propertyId, onSuccess }) => {
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [selectedVendorId, setSelectedVendorId] = useState<number | null>(null);
  const [serviceType, setServiceType] = useState('plumber');
  const [priority, setPriority] = useState(1);

  useEffect(() => {
    // Load PM's vendor pool
    loadVendors();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedVendorId) return;

    try {
      await linkVendorToProperty(propertyId, selectedVendorId, serviceType, priority);
      showSuccessToast('Vendor assigned to property');
      onSuccess();
    } catch (error) {
      showErrorToast('Failed to assign vendor');
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <div className="form-group">
        <label>Select Vendor</label>
        <select 
          value={selectedVendorId || ''} 
          onChange={(e) => setSelectedVendorId(Number(e.target.value))}
        >
          <option value="">Choose a vendor...</option>
          {vendors.map(vendor => (
            <option key={vendor.vendor_id} value={vendor.vendor_id}>
              {vendor.name} ({vendor.service_type})
            </option>
          ))}
        </select>
      </div>
      <div className="form-group">
        <label>Service Type for This Property</label>
        <select value={serviceType} onChange={(e) => setServiceType(e.target.value)}>
          <option value="plumber">Plumber</option>
          <option value="electrician">Electrician</option>
          <option value="carpenter">Carpenter</option>
          <option value="hvac">HVAC</option>
          <option value="general">General</option>
          <option value="emergency">Emergency</option>
        </select>
      </div>
      <div className="form-group">
        <label>Priority (1 = first call, 2 = second call, etc.)</label>
        <input 
          type="number" 
          min="1" 
          value={priority} 
          onChange={(e) => setPriority(Number(e.target.value))}
        />
      </div>
      <button type="submit">Assign Vendor to Property</button>
    </form>
  );
};
```

### Example 3: Start Vendor Calls

**Note:** The maintenance request already has property_id. The backend automatically uses it to find vendors.

```typescript
// API Service
export const startVendorCalls = async (maintenanceRequestId: number) => {
  const response = await fetch(
    `${API_BASE_URL}/maintenance-requests/${maintenanceRequestId}/start-vendor-calls`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${getAuthToken()}`,
        'Content-Type': 'application/json'
      }
    }
  );

  if (!response.ok) {
    throw new Error('Failed to start vendor calls');
  }

  return response.json();
};

// React Component
const VendorCallingSection = ({ maintenanceRequest, maintenanceRequestId }) => {
  const [callStatus, setCallStatus] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleStartCalls = async () => {
    try {
      setLoading(true);
      // Backend automatically uses maintenanceRequest.property_id to find vendors
      // No need to pass property_id - it's already in the maintenance request
      const result = await startVendorCalls(maintenanceRequestId);
      showSuccessToast('Vendor calls started');
      loadCallStatus(); // Refresh status
    } catch (error) {
      showErrorToast('Failed to start vendor calls');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="property-context">
        <p>Property: {maintenanceRequest.property_address}</p>
        <p>Vendors will be called from vendors assigned to this property.</p>
      </div>
      <button 
        onClick={handleStartCalls} 
        disabled={loading}
      >
        {loading ? 'Starting...' : 'Start Vendor Calls'}
      </button>
      {/* Display call status */}
    </div>
  );
};
```

### Example 4: Display Call Attempts Timeline (Enhanced with New Features)

```typescript
const CallAttemptsTimeline = ({ attempts }: { attempts: VendorCallAttempt[] }) => {
  return (
    <div className="timeline">
      {attempts.map((attempt, index) => (
        <div key={attempt.attempt_id} className="timeline-item">
          <div className="timeline-marker">
            <StatusIcon status={attempt.call_status} />
          </div>
          <div className="timeline-content">
            <div className="attempt-header">
              <span className="vendor-name">{attempt.vendor_name}</span>
              <span className="attempt-number">Attempt #{attempt.attempt_number}</span>
            </div>
            <div className="attempt-status">
              <StatusBadge status={attempt.call_status} />
              {attempt.outcome && (
                <OutcomeBadge outcome={attempt.outcome} />
              )}
            </div>
            
            {attempt.is_available !== null && (
              <div className="availability">
                Available: {attempt.is_available ? 'Yes' : 'No'}
              </div>
            )}
            {attempt.earliest_available_time && (
              <div className="time">
                Earliest: {attempt.earliest_available_time}
              </div>
            )}
            {attempt.estimated_cost_range && (
              <div className="cost">
                Cost: {attempt.estimated_cost_range}
              </div>
            )}
            {attempt.vendor_notes && (
              <div className="notes">
                Notes: {attempt.vendor_notes}
              </div>
            )}
            <div className="attempt-actions">
              {attempt.call_transcript && (
                <button onClick={() => showTranscript(attempt)}>
                  View Transcript
                </button>
              )}
              {attempt.call_recording_url && (
                <a href={attempt.call_recording_url} target="_blank">
                  Listen to Recording
                </a>
              )}
            </div>
            <div className="attempt-time">
              {new Date(attempt.initiated_at).toLocaleString()}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};
```

### Example 5: Polling for Call Status Updates

```typescript
const useVendorCallStatus = (maintenanceRequestId: number, isActive: boolean) => {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isActive) return;

    const fetchStatus = async () => {
      try {
        const response = await fetch(
          `${API_BASE_URL}/maintenance-requests/${maintenanceRequestId}/vendor-call-status`,
          {
            headers: {
              'Authorization': `Bearer ${getAuthToken()}`
            }
          }
        );
        const data = await response.json();
        setStatus(data);
      } catch (error) {
        console.error('Failed to fetch call status:', error);
      } finally {
        setLoading(false);
      }
    };

    // Initial fetch
    fetchStatus();

    // Poll every 5 seconds if call is active
    const interval = setInterval(() => {
      if (status?.vendor_call_status === 'calling') {
        fetchStatus();
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [maintenanceRequestId, isActive, status?.vendor_call_status]);

  return { status, loading };
};
```

---

## Real-time Updates

### Polling Strategy

For active vendor calls, poll the status endpoint every 5-10 seconds:

```typescript
// Polling hook
const usePolling = (callback, delay, condition) => {
  useEffect(() => {
    if (!condition) return;

    const interval = setInterval(callback, delay);
    return () => clearInterval(interval);
  }, [callback, delay, condition]);
};

// Usage
const VendorCallingSection = ({ maintenanceRequestId }) => {
  const [callStatus, setCallStatus] = useState(null);

  usePolling(
    async () => {
      const status = await fetchVendorCallStatus(maintenanceRequestId);
      setCallStatus(status);
    },
    5000, // 5 seconds
    callStatus?.vendor_call_status === 'calling'
  );

  // ...
};
```

### WebSocket Alternative (Future)

If you implement WebSockets, listen for vendor call events:
- `vendor_call_started`
- `vendor_call_answered`
- `vendor_call_declined`
- `vendor_call_completed`
- `vendor_assigned`

---

## Error Handling

### API Error Responses

All endpoints return standard error format:
```typescript
{
  "detail": "Error message here"
}
```

### Error Handling Example

```typescript
const handleApiCall = async (apiFunction, errorMessage) => {
  try {
    return await apiFunction();
  } catch (error) {
    if (error.response?.status === 403) {
      showErrorToast('You do not have permission to perform this action');
    } else if (error.response?.status === 404) {
      showErrorToast('Resource not found');
    } else if (error.response?.status === 400) {
      showErrorToast(error.response.data.detail || errorMessage);
    } else {
      showErrorToast(errorMessage || 'An error occurred');
    }
    throw error;
  }
};
```

### User-Friendly Error Messages

```typescript
const ERROR_MESSAGES = {
  VENDOR_NOT_FOUND: 'Vendor not found',
  PROPERTY_NOT_FOUND: 'Property not found',
  MAINTENANCE_REQUEST_NOT_FOUND: 'Maintenance request not found',
  NO_VENDORS_AVAILABLE: 'No vendors available for this property and service type',
  ALL_VENDORS_OPTED_OUT: 'All vendors have opted out of automated calls',
  CALL_ALREADY_IN_PROGRESS: 'Vendor calling is already in progress',
  CALL_ALREADY_COMPLETED: 'Vendor calling has already been completed'
};
```

---

## Testing Checklist

### Vendor Management
- [ ] Create vendor with all fields
- [ ] Create vendor with minimal fields
- [ ] Update vendor information
- [ ] Delete vendor (soft delete)
- [ ] Filter vendors by service type
- [ ] Filter vendors by active status
- [ ] Opt-out vendor
- [ ] Clear vendor opt-out
- [ ] Display opted-out vendors correctly

### Property Vendor Configuration
- [ ] Link vendor to property
- [ ] Unlink vendor from property
- [ ] Update vendor priority
- [ ] Display vendors grouped by service type
- [ ] Show multiple vendors per service type
- [ ] Update property vendor settings
- [ ] Toggle auto-call enabled
- [ ] Toggle emergency-only mode
- [ ] Configure call time restrictions

### Vendor Calling
- [ ] Start vendor calls manually
- [ ] View call queue status
- [ ] View call attempts timeline
- [ ] Pause vendor calls
- [ ] Cancel vendor calls
- [ ] Display call status badges correctly
- [ ] Show vendor responses (availability, time, cost)
- [ ] Display call transcripts
- [ ] Play call recordings
- [ ] Handle real-time status updates
- [ ] Show loading states during calls
- [ ] Handle call failures gracefully

### Edge Cases
- [ ] No vendors configured for property
- [ ] No vendors assigned to property (vendor exists but not linked)
- [ ] All vendors opted out
- [ ] Vendor declines
- [ ] No answer from vendor
- [ ] Call queue exhausted
- [ ] Network errors during calls
- [ ] Concurrent calls to same vendor
- [ ] Invalid vendor IDs
- [ ] Invalid maintenance request IDs
- [ ] Maintenance request without property_id (shouldn't happen, but handle gracefully)
- [ ] Property has vendors but none match the service type
- [ ] Same vendor assigned to property multiple times with different service types

---

## UI/UX Recommendations

### Status Badges

Use color-coded badges for quick status recognition:

```typescript
const STATUS_COLORS = {
  'not_started': 'gray',
  'calling': 'blue',
  'vendor_accepted': 'green',
  'vendor_declined': 'orange',
  'no_response': 'yellow',
  'paused': 'purple',
  'cancelled': 'red'
};
```

### Loading States

Show loading indicators for:
- Fetching vendor list
- Creating/updating vendors
- Starting vendor calls
- Fetching call status
- Processing vendor responses

### Empty States

Provide helpful empty states:
- "No vendors configured. Add your first vendor to get started."
- "No vendors available for this service type."
- "No call attempts yet. Start vendor calls to begin."

### Confirmation Dialogs

Ask for confirmation before:
- Deleting vendor
- Opting out vendor
- Cancelling active vendor calls
- Unlinking vendor from property

### Toast Notifications

Show notifications for:
- ✅ Vendor created successfully
- ✅ Vendor calls started
- ✅ Vendor accepted
- ⚠️ Vendor declined
- ⚠️ All vendors exhausted
- ❌ Call failed
- ℹ️ Call paused/cancelled

---

## Additional Resources

### API Base URL
```
https://leasing-copilot-mvp.onrender.com
```

### Documentation
- See `VENDOR_CALLING_FEATURE.md` for backend implementation details
- See API endpoint documentation above for request/response formats

### Technical Notes

**Vendor Calling Assistant ID:**
- Configured by technical team directly in Supabase
- No frontend configuration needed
- Backend automatically uses the configured assistant ID for vendor calls

### Support
For questions or issues, contact the backend team with:
- API endpoint
- Request payload
- Response/error details
- Expected vs actual behavior

---

## Implementation Notes

### Simplified Feature Scope

This feature focuses on **core vendor calling automation**:
- ✅ Vendor management (PM-level)
- ✅ Property-vendor assignment
- ✅ Automatic vendor calling on maintenance requests
- ✅ Call status tracking and display
- ✅ Vendor response capture

**Not included in frontend:**
- ❌ Vendor calling assistant ID configuration (handled by technical team directly in Supabase)
- ❌ SMS/email notification sending (backend handles automatically, no frontend UI needed)
- ❌ Reminder systems (not part of this feature)

---

## Quick Start Checklist

1. ✅ Review this guide
2. ✅ Understand architecture: PM → Properties → Vendors per Property → Maintenance Requests (already property-linked)
3. ✅ Set up API service functions
4. ✅ Create vendor management page (PM-level vendor pool)
5. ✅ Add property vendor configuration (assign vendors to properties)
6. ✅ Enhance maintenance request page (vendors auto-matched by property)
7. ✅ Implement real-time updates
8. ✅ Add error handling
9. ✅ Test all user flows
10. ✅ Add loading states and empty states
11. ✅ Polish UI/UX

**Note:** Vendor calling assistant ID is configured by technical team in Supabase - no frontend action needed.

## Key Takeaways for Frontend Implementation

### 1. Vendor Calling Assistant ID
- **Configured by technical team** in Supabase (not in frontend)
- Backend automatically uses the configured assistant ID
- No frontend configuration or validation needed

### 2. Vendor Creation vs Assignment
- **Vendor Creation**: PM-level, done once, reusable
- **Vendor Assignment**: Property-level, done per property, configurable per property

### 3. Maintenance Request Flow
- Maintenance request **already has property_id** (from tenant)
- **No need to select property** when starting vendor calls
- Backend automatically uses `property_id` from maintenance request
- System matches vendors assigned to that property only

### 4. UI Organization
- **Vendor Management Page**: Shows all PM's vendors (not property-specific)
- **Property Detail Page → Vendors Tab**: Shows vendors for THIS property
- **Maintenance Request Page**: Shows vendors being called (auto-matched from property)

### 4. Data Relationships
```
PM
  └── Vendors (PM owns)
      └── Assigned to Properties (via PropertyVendor)
          └── Matched to Maintenance Requests (via property_id)
```

### 5. Important Notes
- Same vendor can serve multiple properties
- Same vendor can have different priorities for different properties
- Same vendor can provide different service types for different properties
- Maintenance requests automatically use the correct property's vendors

---

## Architecture Summary

### The Three-Level System

```
┌─────────────────────────────────────────────────────────┐
│ Level 1: Property Manager (PM)                         │
│ └── Vendor Pool (PM owns/manages)                      │
│     ├── Vendor A (ABC Plumbing)                          │
│     ├── Vendor B (XYZ Electric)                        │
│     └── Vendor C (Quick Fix HVAC)                      │
└─────────────────────────────────────────────────────────┘
                        │
                        │ assigns to
                        ▼
┌─────────────────────────────────────────────────────────┐
│ Level 2: Properties                                     │
│ ├── Property 1 (123 Main St)                           │
│ │   ├── Vendor A → plumber, priority 1                 │
│ │   └── Vendor B → electrician, priority 1              │
│ ├── Property 2 (456 Oak Ave)                           │
│ │   ├── Vendor A → plumber, priority 2 (same vendor!)  │
│ │   └── Vendor C → hvac, priority 1                    │
│ └── Property 3 (789 Pine Rd)                           │
│     └── Vendor B → electrician, priority 1              │
└─────────────────────────────────────────────────────────┘
                        │
                        │ tenant linked to
                        ▼
┌─────────────────────────────────────────────────────────┐
│ Level 3: Maintenance Requests                          │
│ └── Request #123                                       │
│     ├── tenant_id: 10                                  │
│     ├── property_id: Property 1 ← KEY FOR MATCHING    │
│     ├── category: "plumbing"                          │
│     └── System automatically:                          │
│         ├── Gets property_id from request              │
│         ├── Finds vendors for Property 1               │
│         ├── Matches by service type (plumber)         │
│         └── Calls Vendor A (priority 1)                │
└─────────────────────────────────────────────────────────┘
```

### Critical Understanding Points

1. **Vendors are NOT property-specific at creation**
   - Created at PM level
   - Added to PM's vendor pool
   - Can be assigned to multiple properties later

2. **Vendors BECOME property-specific when assigned**
   - Assignment happens via PropertyVendor table
   - Each assignment is property-specific
   - Same vendor can have different configs per property

3. **Maintenance requests already know the property**
   - Tenant record has `property_id`
   - Maintenance request inherits `property_id` from tenant
   - No manual property selection needed

4. **Vendor matching is automatic**
   - System uses `property_id` from maintenance request
   - Finds PropertyVendor records for that property
   - Matches by service type and priority
   - No frontend logic needed for matching

### Frontend Implementation Flow

```
User Action: PM creates vendor
  ↓
API: POST /vendors
  ↓
Result: Vendor added to PM's pool
  ↓
User Action: PM assigns vendor to Property 1
  ↓
API: POST /properties/1/vendors
  ↓
Result: Vendor linked to Property 1 with priority/service type
  ↓
User Action: Tenant submits maintenance request (for Property 1)
  ↓
System: Maintenance request created with property_id = 1
  ↓
User Action: PM starts vendor calls (or auto-starts)
  ↓
API: POST /maintenance-requests/123/start-vendor-calls
  ↓
Backend: 
  - Gets property_id from maintenance request (1)
  - Finds PropertyVendor records for property 1
  - Matches by service type
  - Calls vendors in priority order
  ↓
Result: Vendors from Property 1 are called
```

### UI Organization

| Page | Shows | Purpose |
|------|-------|---------|
| `/vendors` | All PM's vendors | Manage vendor pool |
| `/properties/{id}/vendors` | Vendors for THIS property | Assign vendors to property |
| `/maintenance-requests/{id}` | Vendors being called | View call status (auto-matched) |

Good luck with the implementation! 🚀
