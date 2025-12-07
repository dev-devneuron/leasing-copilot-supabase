# Chat Identification Fix

## Problem
VAPI chat requests were failing to identify which Property Manager or Realtor the chat belongs to because:
1. Chats don't have phone numbers (unlike calls)
2. The assistant object doesn't contain a `phoneNumberId` for chat-only assistants
3. There was no way to map assistant IDs to users in the database

## Solution
Implemented assistant ID mapping to identify users from chat requests:

### 1. Database Schema Changes
- **PropertyManager**: Added `vapi_assistant_id` field (indexed)
- **Realtor**: Already had `vapi_assistant_id` field (no changes needed)

### 2. New Functions
- **`get_user_from_assistant_id()`** in `DB/user_lookup.py`: Looks up PM/Realtor by assistant ID
- **`_identify_user_from_assistant_metadata()`** in `DB/vapi_helpers.py`: Updated to use assistant ID lookup

### 3. Identification Flow
When a chat request comes in:
1. Try to get phone number from various sources (headers, body, etc.)
2. If no phone number found, extract assistant ID from the request
3. Look up user in database using `vapi_assistant_id` field
4. Return user info with source_ids for data isolation

## Migration Steps

### Step 1: Run Database Migration
```sql
-- Run migration_add_vapi_assistant_id_to_property_manager.sql
-- This adds the vapi_assistant_id column to PropertyManager table
```

### Step 2: Update Assistant IDs
For each Property Manager and Realtor, update their `vapi_assistant_id` field:

```sql
-- Example: Update Property Manager
UPDATE propertymanager
SET vapi_assistant_id = 'd37218d3-0b5f-4683-87ea-9ed447d925ae'
WHERE property_manager_id = 1;

-- Example: Update Realtor
UPDATE realtor
SET vapi_assistant_id = 'd37218d3-0b5f-4683-87ea-9ed447d925ae'
WHERE realtor_id = 1;
```

### Step 3: Verify Configuration
Check which users have assistant IDs configured:
```sql
-- See UPDATE_VAPI_ASSISTANT_IDS.sql for queries
```

## How to Find Assistant IDs

1. **From VAPI Dashboard**: 
   - Go to VAPI dashboard
   - Navigate to Assistants
   - Copy the Assistant ID for each assistant

2. **From Chat Request Logs**:
   - Check the logs when a chat request comes in
   - Look for: `📋 Assistant object keys: ['id', ...]`
   - The `id` field contains the assistant ID

3. **From API**:
   ```bash
   curl -X GET "https://api.vapi.ai/assistant" \
     -H "Authorization: Bearer YOUR_VAPI_API_KEY"
   ```

## Testing

After updating assistant IDs:
1. Send a chat request through VAPI
2. Check logs for: `✅ Found PM ID X via assistant ID` or `✅ Found realtor ID X via assistant ID`
3. Verify that apartment searches and other features work correctly

## Notes

- The assistant ID should be unique per user (PM or Realtor)
- If multiple users share the same assistant, only one will be identified (the first match)
- For production, ensure each PM/Realtor has their own assistant configured in VAPI
- The system will still try phone number identification first (for calls), and fall back to assistant ID (for chats)
