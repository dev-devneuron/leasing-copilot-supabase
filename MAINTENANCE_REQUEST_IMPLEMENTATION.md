# Maintenance Request Logging Feature - Implementation Summary

## Overview

This document summarizes the implementation of the maintenance request logging feature, which allows tenants to call or text the AI bot to submit maintenance or repair requests.

## What Was Implemented

### 1. Database Models (`DB/db.py`)

#### Tenant Model
- Stores tenant information (name, phone, email)
- Links tenants to properties (ApartmentListing)
- Links tenants to Property Managers (for data isolation)
- Supports unit numbers and notes

#### MaintenanceRequest Model
- Stores maintenance request details
- Links to tenant, property, and Property Manager
- Tracks status (pending, in_progress, completed, cancelled)
- Tracks priority (low, normal, high, urgent)
- Stores category, location, and issue description
- Captures submission method (phone, text, email)
- Links to VAPI call ID and transcript (if available)
- Supports assignment to realtors
- Stores PM notes and resolution notes


### 2. Tenant Identification (`DB/user_lookup.py`)

#### `identify_tenant()` Function
- Identifies tenants by phone number, email, or name
- Supports partial name matching
- Returns tenant info, property info, and PM info
- Handles data isolation by PM

#### `get_tenant_properties()` Function
- Gets all properties for a tenant (for future multi-property support)

### 3. VAPI Bot Integration (`vapi/app.py`)

#### `/submit_maintenance_request/` Endpoint
- Public endpoint called by VAPI bot
- Identifies tenant from caller phone number
- Creates maintenance request record
- Returns success/error message for bot to communicate to tenant
- Handles tenant not found scenarios gracefully

### 4. Dashboard Endpoints (`vapi/app.py`)

#### `GET /maintenance-requests`
- Lists maintenance requests for authenticated user
- Supports filtering by status
- Supports pagination
- Data isolation: PMs see all their requests, Realtors see assigned requests

#### `GET /maintenance-requests/{request_id}`
- Gets detailed information about a specific request
- Includes tenant info, property info, and request details

#### `PATCH /maintenance-requests/{request_id}`
- Updates maintenance request (status, priority, assignment, notes)
- Different permissions for PMs vs Realtors
- Automatically sets completed_at when status is "completed"

### 5. Database Migration (`migration_maintenance_requests.sql`)

- Creates `tenant` table with indexes
- Creates `maintenancerequest` table with indexes
- Adds proper foreign key constraints
- Includes helpful comments

### 6. Documentation (`FRONTEND_BACKEND_INTEGRATION.md`)

- Complete API documentation for all endpoints
- VAPI function tool definition
- Frontend implementation examples
- UI requirements and best practices

## How It Works

### Tenant Submission Flow

1. **Tenant calls/texts the bot** from their registered phone number
2. **Bot identifies tenant** using:
   - Phone number (from caller ID) - primary method
   - Email (if provided during conversation)
   - Name (if phone/email not available)
3. **Bot collects issue description** through conversation
4. **Bot calls `/submit_maintenance_request/`** with issue details
5. **Backend creates maintenance request** linked to tenant's property
6. **Bot confirms submission** to tenant with request ID

### PM Dashboard Flow

1. **PM logs into dashboard**
2. **PM views maintenance requests** via `GET /maintenance-requests`
3. **PM can filter by status** (pending, in_progress, completed, cancelled)
4. **PM views request details** via `GET /maintenance-requests/{id}`
5. **PM updates request** via `PATCH /maintenance-requests/{id}`:
   - Change status
   - Assign to realtor
   - Set priority
   - Add notes
   - Mark as completed

## Setup Instructions

### 1. Run Database Migration

```bash
# Connect to your Supabase Postgres database
psql -h <your-db-host> -U <your-user> -d <your-database>

# Run the migration
\i migration_maintenance_requests.sql
```

Or execute the SQL directly in your Supabase SQL editor.

### 2. Configure VAPI Assistant

Add the `submitMaintenanceRequest` function tool to your VAPI assistant configuration. See the function definition in `FRONTEND_BACKEND_INTEGRATION.md`.

**Function Tool URL:** `https://your-backend-url.com/submit_maintenance_request/`

### 3. Register Tenants

Before tenants can submit requests, they must be registered in the system. You can:

- **Option A:** Add tenants via SQL:
  ```sql
  INSERT INTO tenant (name, phone_number, email, property_id, property_manager_id, unit_number)
  VALUES ('John Smith', '+14125551234', 'john@example.com', 10, 1, 'Apt 3B');
  ```

- **Option B:** Create an admin interface (future enhancement)

### 4. Test the Flow

1. **Register a test tenant** with a phone number
2. **Call the bot** from that phone number
3. **Say something like:** "I need to report a maintenance issue. My kitchen sink is leaking."
4. **Bot should:** Identify you, collect details, submit the request, and confirm
5. **Check dashboard:** Log in as PM and verify the request appears

## Data Model Relationships

```
PropertyManager
  ├── Properties (ApartmentListing via Source)
  │     └── Tenants
  │           └── MaintenanceRequests
  └── Realtors
        └── (can be assigned MaintenanceRequests)
```

## Security & Data Isolation

- **Tenant identification:** Uses phone number, email, or name matching
- **PM data isolation:** PMs only see requests for their properties
- **Realtor data isolation:** Realtors only see requests assigned to them or for their properties
- **Authentication:** Dashboard endpoints require JWT authentication
- **Authorization:** Users can only update requests they have access to

## Future Enhancements

1. **Tenant Registration API:** Allow PMs to register tenants via API/dashboard
2. **Email Notifications:** Send email notifications to PMs when requests are submitted
3. **SMS Notifications:** Send SMS updates to tenants when request status changes
4. **Photo Attachments:** Allow tenants to attach photos of issues
5. **Vendor Integration:** Assign requests to external vendors/contractors
6. **Request History:** Show tenant's previous requests
7. **Automated Categorization:** Use AI to automatically categorize requests
8. **Priority Auto-Detection:** Use AI to detect urgent issues (e.g., "no heat", "water leak")

## Troubleshooting

### Tenant Not Found Error

**Problem:** Bot says "I couldn't find your tenant record"

**Solution:**
1. Verify tenant is registered in database
2. Check phone number format (should be E.164: +14125551234)
3. Ensure tenant's `property_manager_id` matches the PM who owns the phone number
4. Try providing name or email during the call

### Requests Not Appearing in Dashboard

**Problem:** PM doesn't see requests in dashboard

**Solution:**
1. Verify `property_manager_id` on the request matches PM's ID
2. Check request status filter (might be filtering out requests)
3. Verify PM is logged in with correct account

### VAPI Function Not Working

**Problem:** Bot doesn't call the function

**Solution:**
1. Verify function is added to VAPI assistant configuration
2. Check function URL is correct
3. Verify function name matches exactly: `submitMaintenanceRequest`
4. Check VAPI logs for errors

## API Endpoints Summary

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/submit_maintenance_request/` | POST | None | VAPI bot submits request |
| `/maintenance-requests` | GET | Required | List requests (with filters) |
| `/maintenance-requests/{id}` | GET | Required | Get request details |
| `/maintenance-requests/{id}` | PATCH | Required | Update request |

## Files Modified/Created

### Created:
- `migration_maintenance_requests.sql` - Database migration
- `MAINTENANCE_REQUEST_IMPLEMENTATION.md` - This file

### Modified:
- `DB/db.py` - Added Tenant and MaintenanceRequest models
- `DB/user_lookup.py` - Added tenant identification functions
- `vapi/app.py` - Added maintenance request endpoints
- `FRONTEND_BACKEND_INTEGRATION.md` - Added API documentation

## Testing Checklist

- [ ] Database migration runs successfully
- [ ] Tenant can be identified by phone number
- [ ] Tenant can be identified by email
- [ ] Tenant can be identified by name
- [ ] Maintenance request is created successfully
- [ ] PM can view requests in dashboard
- [ ] PM can filter requests by status
- [ ] PM can update request status
- [ ] PM can assign request to realtor
- [ ] Realtor can view assigned requests
- [ ] Error handling works (tenant not found)
- [ ] Data isolation works (PMs only see their requests)

