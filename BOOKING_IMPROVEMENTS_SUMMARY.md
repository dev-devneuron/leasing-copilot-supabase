# Booking System Improvements Summary

This document summarizes all the changes made to improve the booking system according to the requirements.

## Changes Overview

### 1. ✅ Store Original Customer Time (No Timezone Conversion)

**Problem:** Previously, all booking times were converted to UTC, losing the original format the customer sent.

**Solution:**
- Added two new database fields to `PropertyTourBooking`:
  - `customer_sent_start_at` (TEXT) - Stores the original time string as customer sent it
  - `customer_sent_end_at` (TEXT) - Stores the original time string as customer sent it
- Modified booking creation endpoints to store the original time strings:
  - `/vapi/bookings/request` - VAPI booking creation
  - `/api/bookings/manual` - Manual booking creation from dashboard
- The `start_at` and `end_at` fields still store UTC datetime for internal calculations, but we now preserve the original format

**Migration File:** `migration_add_original_time_fields_to_booking.sql`

### 2. ✅ Call Recording and Transcript Linking

**Status:** Already implemented! The following fields exist in the database:
- `vapi_call_id` - Links booking to VAPI call
- `call_transcript` - Stores call transcript
- `call_recording_url` - Stores MP3 recording URL

**Enhancement:** Updated all booking retrieval endpoints to include call record information in the response.

### 3. ✅ Update Booking Endpoint

**New Endpoint:** `PUT /api/bookings/{booking_id}` or `PATCH /api/bookings/{booking_id}`

**Features:**
- Allows updating visitor information (name, phone, email)
- Allows updating booking times (stores original format)
- Allows updating notes, timezone, and status
- Only the assigned approver (PM/Realtor) can update bookings
- Maintains audit log of changes

**Request Body:**
```json
{
  "visitor_name": "John Doe",
  "visitor_phone": "+1234567890",
  "visitor_email": "john@example.com",
  "start_at": "2025-12-01T16:00:00",
  "end_at": "2025-12-01T17:00:00",
  "timezone": "America/New_York",
  "notes": "Updated notes",
  "status": "approved"
}
```

### 4. ✅ Delete Booking Endpoint

**New Endpoint:** `DELETE /api/bookings/{booking_id}`

**Features:**
- Permanently deletes a booking (hard delete, different from cancel which is soft delete)
- Only the assigned approver (PM/Realtor) can delete bookings
- Removes associated availability slots
- Returns confirmation message

**Note:** This is different from the cancel endpoint (`POST /api/bookings/{booking_id}/cancel`) which performs a soft delete.

### 5. ✅ Updated Booking Retrieval Endpoints

All booking retrieval endpoints now include:
- `customerSentStartAt` - Original time as customer sent it
- `customerSentEndAt` - Original time as customer sent it
- `callRecord` - Object containing:
  - `vapiCallId`
  - `callTranscript`
  - `callRecordingUrl`

**Updated Endpoints:**
- `GET /api/bookings/{booking_id}` - Get single booking details
- `GET /api/users/{user_id}/bookings` - Get user's bookings
- `POST /vapi/bookings/by-visitor` - Get bookings by visitor (VAPI)

### 6. ✅ Frontend Component Example

Created a comprehensive React/TypeScript component example (`frontend_example/BookingManagement.tsx`) that demonstrates:

**Features:**
- ✅ Displays original customer-sent time (no conversion)
- ✅ Shows timezone confirmation notice: "The customer mentioned this time: [time]. Please confirm with the customer that this time is correct for their timezone."
- ✅ Displays call recording with audio player
- ✅ Shows call transcript with expand/collapse
- ✅ Update booking functionality with form
- ✅ Delete booking functionality with confirmation
- ✅ Proper error handling and loading states

**Key UI Elements:**
1. **Timezone Confirmation Banner:** Yellow warning box that reminds users to confirm the time with the customer
2. **Call Record Section:** Blue section showing:
   - Audio player for call recording
   - Expandable transcript
   - Call ID
3. **Edit/Delete Buttons:** Actions available for each booking
4. **Edit Form:** Inline form for updating booking details

## Database Schema Changes

### New Fields in `PropertyTourBooking`:

```python
customer_sent_start_at: Optional[str] = None  # Original time string from customer
customer_sent_end_at: Optional[str] = None  # Original time string from customer
```

### Existing Fields (Already Present):
```python
vapi_call_id: Optional[str] = None
call_transcript: Optional[str] = None
call_recording_url: Optional[str] = None
```

## API Endpoints Summary

### New Endpoints:
- `PUT /api/bookings/{booking_id}` - Update booking
- `PATCH /api/bookings/{booking_id}` - Update booking (alias)
- `DELETE /api/bookings/{booking_id}` - Delete booking

### Updated Endpoints:
- `POST /vapi/bookings/request` - Now stores original time strings
- `POST /api/bookings/manual` - Now stores original time strings
- `GET /api/bookings/{booking_id}` - Now returns original time and call record
- `GET /api/users/{user_id}/bookings` - Now returns original time and call record
- `POST /vapi/bookings/by-visitor` - Now returns original time and call record

## Migration Instructions

1. **Run the database migration:**
   ```sql
   -- Run migration_add_original_time_fields_to_booking.sql
   ```

2. **Update your frontend:**
   - Use the example component in `frontend_example/BookingManagement.tsx` as a reference
   - Update your API calls to use the new fields
   - Display `customerSentStartAt` and `customerSentEndAt` instead of converting times
   - Show the timezone confirmation message
   - Display call recordings and transcripts

## Frontend Integration Guide

### Displaying Original Time:
```typescript
// Display the time exactly as customer sent it
<div>
  <strong>Time (as customer mentioned):</strong>
  {booking.customerSentStartAt || booking.startAt}
</div>
```

### Timezone Confirmation Message:
```typescript
<div className="timezone-warning">
  ⚠️ The customer mentioned this time: {booking.customerSentStartAt}
  <br />
  Please confirm with the customer that this time is correct for their timezone ({booking.timezone}).
</div>
```

### Call Recording Display:
```typescript
{booking.callRecord?.callRecordingUrl && (
  <audio controls src={booking.callRecord.callRecordingUrl} />
)}

{booking.callRecord?.callTranscript && (
  <div>
    <button onClick={() => setShowTranscript(!showTranscript)}>
      {showTranscript ? 'Hide' : 'Show'} Transcript
    </button>
    {showTranscript && <pre>{booking.callRecord.callTranscript}</pre>}
  </div>
)}
```

### Update Booking:
```typescript
const response = await fetch(`/api/bookings/${bookingId}`, {
  method: 'PUT',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    visitor_name: 'Updated Name',
    start_at: '2025-12-01T16:00:00', // Original format
    end_at: '2025-12-01T17:00:00',
    timezone: 'America/New_York',
    notes: 'Updated notes',
  }),
});
```

### Delete Booking:
```typescript
const response = await fetch(`/api/bookings/${bookingId}`, {
  method: 'DELETE',
  headers: {
    'Authorization': `Bearer ${token}`,
  },
});
```

## Testing Checklist

- [ ] Create a booking via VAPI - verify original time is stored
- [ ] Create a manual booking - verify original time is stored
- [ ] Retrieve booking - verify original time fields are returned
- [ ] Update booking - verify original time can be updated
- [ ] Delete booking - verify booking is permanently deleted
- [ ] Display booking in frontend - verify timezone confirmation shows
- [ ] Play call recording - verify audio player works
- [ ] View transcript - verify transcript displays correctly

## Notes

1. **Time Storage:** We store both UTC datetime (for internal calculations) and original string (for display). This allows us to:
   - Keep accurate time comparisons and scheduling
   - Display exactly what the customer said
   - Avoid timezone conversion errors

2. **Backward Compatibility:** Existing bookings will have `null` for `customer_sent_start_at` and `customer_sent_end_at`. The frontend should fall back to `startAt` and `endAt` if these are not available.

3. **Call Record Linking:** Call records are automatically linked when bookings are created via VAPI phone calls. The linking happens in the booking creation endpoint by extracting call information from request headers.

4. **Permissions:** Only the assigned approver (PM or Realtor) can update or delete bookings. This ensures data integrity and proper access control.

