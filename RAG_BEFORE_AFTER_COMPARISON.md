# RAG Pipeline: Before vs After Data Isolation

## 🔴 BEFORE (Security Issue - No Data Isolation)

### How It Worked

```
User (PM or Realtor) calls chatbot
  ↓
VAPI sends webhook to /search_apartments/
  ↓
Backend receives query: "Show me 2 bedroom apartments"
  ↓
rag.search_apartments(query)
  ↓
DB.db.search_apartments(query, k=5)
  ↓
SQL Query:
  SELECT listing_metadata 
  FROM apartmentlisting
  ORDER BY embedding <=> query_embedding
  LIMIT 5
  ↓
❌ PROBLEM: Returns listings from ENTIRE database
  - PM's chatbot can see ALL listings (from all PMs)
  - Realtor's chatbot can see ALL listings (from all realtors)
  - No filtering by user identity
  - No data isolation whatsoever
```

### Code Flow (Before)

**`vapi/app.py` - `/search_apartments/` endpoint:**
```python
@app.post("/search_apartments/")
def search_apartments(request: VapiRequest):
    # No user identification
    # No phone number extraction
    # No filtering
    
    for tool_call in request.message.toolCalls:
        if tool_call.function.name == "searchApartments":
            query = args.get("query")
            listings = rag.search_apartments(query)  # ❌ No filtering
            return {"results": [{"toolCallId": tool_call.id, "result": listings}]}
```

**`DB/db.py` - `search_apartments()` function:**
```python
def search_apartments(query: str, k: int = 5) -> List[Dict]:
    qvec = embed_text(query)
    qvec_str = "[" + ",".join(f"{x:.6f}" for x in qvec) + "]"
    
    # ❌ No WHERE clause filtering
    sql = text(
        f"""
        SELECT listing_metadata FROM apartmentlisting
        ORDER BY embedding <=> '{qvec_str}'::vector
        LIMIT :k
        """
    )
    # Returns ALL listings from database
```

### Security Issues

1. **No User Identification**: Backend had no idea which PM/realtor was calling
2. **No Access Control**: All searches returned results from entire database
3. **Data Leakage**: 
   - PM A could see PM B's listings
   - Realtor X could see Realtor Y's listings
   - Complete violation of data privacy

### Example Scenario (Before)

**Setup:**
- PM1 has 10 listings
- PM2 has 15 listings
- Realtor A (under PM1) has 3 assigned listings

**When Realtor A's chatbot searches:**
- Query: "Show me apartments"
- Result: Returns ALL 25 listings (PM1's + PM2's)
- ❌ Should only see 3 assigned listings

---

## ✅ AFTER (Fixed - With Data Isolation)

### How It Works Now

```
User (PM or Realtor) calls chatbot
  ↓
VAPI sends webhook to /search_apartments/
  ↓
Backend extracts phone number from request:
  - Method 1: Direct phone number in body/headers
  - Method 2: From VAPI call ID (API lookup)
  - Method 3: From VAPI phone number ID (API lookup)
  ↓
identify_user_from_vapi_request() → get_user_from_phone_number()
  ↓
Database lookup:
  - Check realtor.twilio_contact
  - Check propertymanager.twilio_contact
  ↓
get_data_access_scope(user_type, user_id)
  ↓
Returns accessible source_ids:
  - PM: All their sources + all realtors' sources
  - Realtor: Only their assigned sources
  ↓
rag.search_apartments(query, source_ids=[10, 11, 12])
  ↓
DB.db.search_apartments(query, source_ids=[10, 11, 12], k=5)
  ↓
SQL Query:
  SELECT listing_metadata 
  FROM apartmentlisting
  WHERE source_id = ANY(:source_ids)  ✅ Filtering!
  ORDER BY embedding <=> query_embedding
  LIMIT 5
  ↓
✅ Returns ONLY listings user has access to
```

### Code Flow (After)

**`vapi/app.py` - `/search_apartments/` endpoint:**
```python
@app.post("/search_apartments/")
async def search_apartments(request: VapiRequest, http_request: Request):
    from DB.vapi_helpers import identify_user_from_vapi_request
    
    # ✅ Extract phone number and identify user
    body = await http_request.json()
    user_info = identify_user_from_vapi_request(body, dict(http_request.headers))
    
    source_ids = None
    if user_info:
        source_ids = user_info["source_ids"]  # ✅ Get accessible source_ids
        print(f"🔒 Filtering listings for {user_info['user_type']} ID: {user_info['user_id']}")
    
    for tool_call in request.message.toolCalls:
        if tool_call.function.name == "searchApartments":
            query = args.get("query")
            # ✅ Pass source_ids for filtering
            listings = rag.search_apartments(query, source_ids=source_ids)
            return {"results": [{"toolCallId": tool_call.id, "result": listings}]}
```

**`DB/db.py` - `search_apartments()` function:**
```python
def search_apartments(query: str, source_ids: Optional[List[int]] = None, k: int = 5) -> List[Dict]:
    qvec = embed_text(query)
    qvec_str = "[" + ",".join(f"{x:.6f}" for x in qvec) + "]"
    
    # ✅ Filter by source_ids if provided
    if source_ids and len(source_ids) > 0:
        sql = text(
            f"""
            SELECT listing_metadata FROM apartmentlisting
            WHERE source_id = ANY(:source_ids)  ✅ Filtering!
            ORDER BY embedding <=> '{qvec_str}'::vector
            LIMIT :k
            """
        )
        params = {"source_ids": source_ids, "k": k}
    else:
        # Fallback: no filtering (logs security warning)
        sql = text(
            f"""
            SELECT listing_metadata FROM apartmentlisting
            ORDER BY embedding <=> '{qvec_str}'::vector
            LIMIT :k
            """
        )
        params = {"k": k}
    
    # Returns only filtered listings
```

**New Module: `DB/user_lookup.py`**
```python
def get_user_from_phone_number(phone_number: str) -> Optional[Dict]:
    """Identify user from phone number and return their accessible source_ids"""
    # Look up in realtor table
    # Look up in propertymanager table
    # Get data access scope
    # Return user info + source_ids
```

**New Module: `DB/vapi_helpers.py`**
```python
def identify_user_from_vapi_request(request_body, request_headers):
    """Smart phone number extraction with multiple fallback methods"""
    # Try direct phone number
    # Try from call ID
    # Try from phone number ID
    # Return user info
```

### Security Improvements

1. **User Identification**: Backend identifies which PM/realtor is calling from phone number
2. **Access Control**: All searches filtered by user's accessible `source_ids`
3. **Data Isolation**:
   - PM A only sees PM A's listings + their realtors' listings
   - Realtor X only sees listings assigned to them
   - Complete data privacy protection

### Example Scenario (After)

**Setup:**
- PM1 has 10 listings (source_ids: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
- PM2 has 15 listings (source_ids: [11, 12, 13, ..., 25])
- Realtor A (under PM1) has 3 assigned listings (source_ids: [1, 2, 3])

**When Realtor A's chatbot searches:**
- Query: "Show me apartments"
- Phone number extracted: "+1234567890"
- User identified: Realtor A
- Accessible source_ids: [1, 2, 3]
- SQL: `WHERE source_id = ANY([1, 2, 3])`
- Result: Returns ONLY 3 assigned listings ✅

**When PM1's chatbot searches:**
- Query: "Show me apartments"
- Phone number extracted: "+0987654321"
- User identified: PM1
- Accessible source_ids: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] (PM1's + all realtors' under PM1)
- SQL: `WHERE source_id = ANY([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])`
- Result: Returns PM1's listings + all realtors' listings ✅

---

## Key Differences Summary

| Aspect | Before | After |
|--------|--------|-------|
| **User Identification** | ❌ None | ✅ From phone number |
| **SQL Filtering** | ❌ No WHERE clause | ✅ `WHERE source_id = ANY(:source_ids)` |
| **Data Access** | ❌ All listings | ✅ Only accessible listings |
| **PM Access** | ❌ All PMs' data | ✅ Own data + realtors' data |
| **Realtor Access** | ❌ All realtors' data | ✅ Only assigned listings |
| **Security** | ❌ Critical vulnerability | ✅ Proper data isolation |
| **Logging** | ❌ No visibility | ✅ Logs filtering status |

---

## Files Changed

### Modified Files:
1. **`DB/db.py`**: Added `source_ids` parameter to `search_apartments()`
2. **`vapi/rag.py`**: Updated to pass `source_ids` through
3. **`vapi/app.py`**: Updated 3 endpoints with user identification and filtering

### New Files:
1. **`DB/user_lookup.py`**: User identification from phone number
2. **`DB/vapi_helpers.py`**: Smart phone number extraction from VAPI requests

---

## Testing the Fix

### Before (What You'd See):
```bash
# Realtor A searches
Query: "2 bedroom apartments"
Results: 25 listings (from all PMs) ❌
```

### After (What You Should See):
```bash
# Realtor A searches
Query: "2 bedroom apartments"
🔒 Filtering listings for realtor ID: 5, source_ids: [1, 2, 3]
Results: 3 listings (only assigned ones) ✅
```

### If Phone Number Not Found:
```bash
⚠️  Could not identify user from VAPI request - searching all listings (SECURITY RISK)
```
This warning tells you that phone number identification failed and you need to check VAPI webhook configuration.

