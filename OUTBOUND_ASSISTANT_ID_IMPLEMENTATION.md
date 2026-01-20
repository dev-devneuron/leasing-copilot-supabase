# Outbound Assistant ID Implementation

## ✅ Changes Made

### 1. Database Schema Updates

Added `vapi_outbound_assistant_id` field to both `PropertyManager` and `Realtor` tables:

- **PropertyManager.vapi_outbound_assistant_id** - VAPI assistant ID for outbound calls
- **Realtor.vapi_outbound_assistant_id** - VAPI assistant ID for outbound calls
- **PropertyManager.vapi_assistant_id** - Remains for inbound calls/chat (unchanged)
- **Realtor.vapi_assistant_id** - Remains for inbound calls/chat (unchanged)

### 2. Code Updates

**File: `DB/outbound_calling.py`**
- Updated `trigger_outbound_call()` to:
  1. First check if `assistant_id` is provided explicitly (allows override)
  2. If not provided, look up `vapi_outbound_assistant_id` from PropertyManager
  3. Fall back to `VAPI_ASSISTANT_ID` environment variable if PM doesn't have one configured
  4. Error if no assistant ID is found

**Logic Flow:**
```
1. If assistant_id provided → Use it (allows override)
2. If assistant_id is None AND property_manager_id provided:
   → Look up PropertyManager.vapi_outbound_assistant_id
   → Use it if found
3. If still None → Fall back to VAPI_ASSISTANT_ID env var
4. If still None → Return error
```

---

## 📋 Migration SQL

Run the migration script to add the new fields:

```sql
-- See: MIGRATION_ADD_OUTBOUND_ASSISTANT_ID.sql
```

This will:
- Add `vapi_outbound_assistant_id` column to `propertymanager` table
- Add `vapi_outbound_assistant_id` column to `realtor` table
- Create indexes for faster lookups
- Add column comments for documentation

---

## 🔧 How to Use

### Setting Outbound Assistant ID

After running the migration, update each PropertyManager's outbound assistant ID:

```sql
UPDATE propertymanager 
SET vapi_outbound_assistant_id = 'your-outbound-assistant-id-here'
WHERE property_manager_id = 1;
```

Or via your admin interface/API.

### How It Works

1. **Outbound Calls**: Use `vapi_outbound_assistant_id` from PropertyManager
2. **Inbound Calls**: Continue using `vapi_assistant_id` (unchanged)
3. **Override**: Can still pass `assistant_id` explicitly in API call if needed

---

## 📊 Example

### Before (Single Assistant)
```python
# Both inbound and outbound used same assistant
PropertyManager.vapi_assistant_id = "assistant-123"
```

### After (Separate Assistants)
```python
# Inbound calls/chat
PropertyManager.vapi_assistant_id = "assistant-123"

# Outbound calls
PropertyManager.vapi_outbound_assistant_id = "assistant-456"
```

---

## 🔍 Code Changes Summary

### Database Models (`DB/db.py`)
- ✅ Added `vapi_outbound_assistant_id` to `PropertyManager`
- ✅ Added `vapi_outbound_assistant_id` to `Realtor`
- ✅ Updated comments to clarify: `vapi_assistant_id` = inbound, `vapi_outbound_assistant_id` = outbound

### Outbound Calling (`DB/outbound_calling.py`)
- ✅ Updated `trigger_outbound_call()` to look up outbound assistant ID from PropertyManager
- ✅ Maintains backward compatibility with environment variable fallback
- ✅ Allows explicit override via `assistant_id` parameter

### API Endpoint (`vapi/app.py`)
- ✅ No changes needed - already passes `property_manager_id` correctly

---

## ⚠️ Important Notes

1. **Migration Required**: Run `MIGRATION_ADD_OUTBOUND_ASSISTANT_ID.sql` before deploying
2. **Configuration Required**: Set `vapi_outbound_assistant_id` for each PropertyManager after migration
3. **Backward Compatible**: Falls back to `VAPI_ASSISTANT_ID` env var if PM doesn't have outbound assistant configured
4. **Inbound Calls Unchanged**: All inbound call logic continues using `vapi_assistant_id`

---

## ✅ Testing Checklist

- [ ] Run migration SQL script
- [ ] Set `vapi_outbound_assistant_id` for at least one PropertyManager
- [ ] Test outbound call - should use PM's outbound assistant ID
- [ ] Test with PM that has no outbound assistant ID - should fall back to env var
- [ ] Test with explicit `assistant_id` parameter - should use provided ID
- [ ] Verify inbound calls still work (unchanged)

---

**Implementation Complete!** 🎉
