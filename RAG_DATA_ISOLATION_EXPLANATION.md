# RAG Pipeline & Data Isolation - Complete Explanation

## How RAG Pipeline Currently Works

### 1. Data Storage Flow

```
Upload Listing File
  ↓
AI Parser (Vertex AI/Gemini) extracts structured data
  ↓
Create embeddings (768-dim vector) for each listing
  ↓
Store in apartmentlisting table:
  - text: Searchable text representation
  - listing_metadata: JSON with all property details
  - embedding: Vector(768) for similarity search
  - source_id: Links to Source (which belongs to PM or Realtor)
```

### 2. RAG Search Flow

#### 🔴 BEFORE (Security Issue - Fixed Now)

```
User asks chatbot: "Show me 2 bedroom apartments"
  ↓
VAPI calls /search_apartments/ endpoint
  ↓
rag.search_apartments(query)
  ↓
DB.db.search_apartments(query, k=5)
  ↓
SQL: SELECT listing_metadata FROM apartmentlisting
     ORDER BY embedding <=> query_embedding
     LIMIT 5
  ↓
❌ PROBLEM: Returns listings from ALL users (no filtering!)
```

#### ✅ AFTER (Fixed with Data Isolation)

```
User asks chatbot: "Show me 2 bedroom apartments"
  ↓
VAPI calls /search_apartments/ endpoint
  ↓
Backend extracts phone number → Identifies user → Gets source_ids
  ↓
rag.search_apartments(query, source_ids=[10, 11, 12])
  ↓
DB.db.search_apartments(query, source_ids=[10, 11, 12], k=5)
  ↓
SQL: SELECT listing_metadata FROM apartmentlisting
     WHERE source_id = ANY(:source_ids)  ✅ Filtering!
     ORDER BY embedding <=> query_embedding
     LIMIT 5
  ↓
✅ Returns ONLY listings user has access to
```

### 3. Data Isolation - What Was Fixed

**🔴 Before (Security Vulnerability):**
- `search_apartments()` searched ENTIRE database
- No filtering by PM/realtor
- Chatbot could see ALL listings from ALL users
- **CRITICAL SECURITY VULNERABILITY**

**✅ After (Fixed):**
- `search_apartments()` filters by user's accessible `source_ids`
- User identified from phone number in VAPI request
- PM's chatbot → Only sees that PM's listings + their realtors' listings
- Realtor's chatbot → Only sees listings assigned to that realtor
- **Proper data isolation implemented**

## How Data Ownership Works

### Source System
- Each listing has a `source_id` → links to `Source` table
- `Source` belongs to either:
  - `property_manager_id` (PM owns it)
  - `realtor_id` (Realtor owns it)

### Access Control Logic
- **Property Manager**: Can access:
  - Their own sources (PM's listings)
  - All sources from their managed realtors
  
- **Realtor**: Can only access:
  - Their own sources (listings assigned to them)

This logic is in `get_data_access_scope()` function.

## The Fix

### 1. Updated `search_apartments()` Function

**Before:**
```python
def search_apartments(query: str, k: int = 5):
    # Searches ALL listings
```

**After:**
```python
def search_apartments(query: str, source_ids: Optional[List[int]] = None, k: int = 5):
    # Filters by source_ids if provided
    if source_ids:
        WHERE source_id = ANY(:source_ids)
```

### 2. User Identification System

**New Module:** `DB/user_lookup.py`
- `get_user_from_phone_number()`: Looks up phone number in database
- Checks `realtor.twilio_contact` and `propertymanager.twilio_contact`
- Returns user info + accessible `source_ids` using `get_data_access_scope()`

**New Module:** `DB/vapi_helpers.py`
- `identify_user_from_vapi_request()`: Smart user identification
- Tries multiple methods to get phone number:
  1. Direct phone number in request body/headers
  2. Phone number from VAPI call ID (via VAPI API)
  3. Phone number from VAPI phone number ID (via VAPI API)
- Returns user info with `source_ids` for filtering

### 3. Updated VAPI Endpoints

**All three endpoints now have data isolation:**
- `/search_apartments/` - Filters apartment searches
- `/confirm_address/` - Filters address confirmation
- `/query_docs/` - Filters rule/document queries

**Each endpoint:**
1. Extracts request body and headers
2. Calls `identify_user_from_vapi_request()` to get user info
3. Extracts `source_ids` from user info
4. Passes `source_ids` to search functions for filtering
5. Logs filtering status for debugging

### 4. How VAPI Identifies the Bot

**Implementation:** Multi-method approach in `identify_user_from_vapi_request()`

**Method 1: Direct Phone Number (Primary)**
- Checks request body: `phoneNumber`, `phone_number`, `to`, `from`
- Checks headers: `x-phone-number`, `phone-number`
- Most reliable if VAPI is configured to pass it

**Method 2: From Call ID (Fallback)**
- If `callId` or `call_id` in request, fetch call from VAPI API
- Extract `phoneNumberId` from call object
- Then use Method 3 to get actual phone number

**Method 3: From Phone Number ID (Fallback)**
- If `phoneNumberId` in request, fetch phone number from VAPI API
- Get actual phone number string
- Look up in database

**Note:** If no phone number can be identified, the system logs a security warning but still allows the request (for backward compatibility during testing).

## Current Implementation Status

✅ **Completed:**
- `search_apartments()` now accepts `source_ids` filter
- `get_user_from_phone_number()` function created in `DB/user_lookup.py`
- `identify_user_from_vapi_request()` helper created in `DB/vapi_helpers.py`
- All three VAPI endpoints (`/search_apartments/`, `/confirm_address/`, `/query_docs/`) updated with data isolation
- Multi-method phone number identification (direct, call ID, phone number ID)
- Comprehensive logging for debugging

⚠️ **Needs Testing:**
- Verify VAPI passes phone number in webhook requests
- Test that data isolation works correctly (PM sees all, Realtor sees only assigned)
- Check backend logs for filtering messages
- Verify fallback methods work if direct phone number not available

## How to Verify It's Working

### 1. Check Logs
When chatbot searches, you should see:
```
🔒 Filtering listings for realtor ID: 5, source_ids: [10, 11, 12]
```
or
```
⚠️  No phone number found in request - searching all listings (SECURITY RISK)
```

### 2. Test Data Isolation
1. PM uploads listings → stored with PM's source_id
2. PM assigns some to Realtor A → listings get Realtor A's source_id
3. Realtor A's chatbot searches → should ONLY see Realtor A's listings
4. PM's chatbot searches → should see PM's + all realtors' listings

### 3. SQL Verification
```sql
-- Check which listings belong to which user
SELECT 
    al.id,
    al.source_id,
    s.realtor_id,
    s.property_manager_id,
    al.listing_metadata->>'address' as address
FROM apartmentlisting al
JOIN source s ON al.source_id = s.source_id
ORDER BY al.id DESC
LIMIT 10;
```

## Next Steps

1. **Test VAPI Integration:**
   - Send message to chatbot
   - Check backend logs for phone number extraction
   - Verify filtering messages appear

2. **If Phone Number Not Found:**
   - Check VAPI webhook configuration
   - May need to configure VAPI to pass phone number
   - Or implement Option B (Assistant ID mapping)

3. **Verify Data Isolation:**
   - Test with different PM/realtor accounts
   - Confirm each only sees their own data

