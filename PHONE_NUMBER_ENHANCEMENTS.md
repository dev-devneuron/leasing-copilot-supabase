# Phone Number Parsing & System Robustness Enhancements

## Overview

Enhanced the maintenance request system with robust phone number parsing, intelligent tenant identification, and improved error handling.

## Key Enhancements

### 1. **Spoken Phone Number Parsing**

The system now handles phone numbers in various spoken formats:

#### Supported Formats:
- **Written formats**: `+1 (412) 555-1234`, `14125551234`, `(412) 555-1234`
- **Spoken formats**: 
  - `"four one two five five five one two three four"`
  - `"four one two dash five five five dash one two three four"`
  - `"412 five five five 1234"` (mixed digits and words)
- **International formats**: Handles numbers with country codes

#### Implementation:
- `parse_spoken_phone_number()`: Converts spoken number words to digits
- Word-to-digit mapping: "zero", "one", "two", etc. → 0, 1, 2, etc.
- Handles common variations: "oh" → 0, "to/too" → 2, "for" → 4, etc.
- Extracts 10-digit US numbers from longer sequences

### 2. **Enhanced Phone Number Normalization**

`normalize_phone_number()` now:
- Parses spoken phone numbers automatically
- Handles multiple formats (E.164, US format, international)
- Extracts digits from formatted strings
- Handles edge cases (too many digits, missing country code)
- Returns standardized E.164 format: `+1XXXXXXXXXX`

### 3. **Intelligent Tenant Identification**

`identify_tenant()` now features:

#### Fuzzy Matching:
- **Phone matching**: Exact match → partial match → fuzzy match (last 10 digits)
- **Email matching**: Exact match → partial match (handles typos/spaces)
- **Name matching**: 
  - Full name match
  - First name only
  - Last name only
  - Handles titles (Mr, Mrs, Dr) and suffixes (Jr, Sr, II, III)

#### Scoring System:
- **Phone match**: 100 points (exact), 50 points (partial)
- **Email match**: 80 points (exact), 40 points (partial)
- **Name match**: 60 points (exact), 30 points (partial), 20 points (nickname)
- Returns best match based on highest score

#### Active Tenant Filtering:
- Only searches active tenants (`is_active == True`)
- Prevents matching with old/inactive tenant records

### 4. **Auto-Detection Features**

#### Priority Auto-Detection:
Automatically detects priority from issue description:
- **Urgent**: "urgent", "emergency", "flooding", "fire", "no heat", "no water", "gas leak"
- **High**: "broken", "not working", "leaking", "overflowing"
- **Low**: "minor", "small", "cosmetic"
- **Normal**: Default for all other cases

#### Category Auto-Detection:
Automatically categorizes issues:
- **Plumbing**: "sink", "toilet", "faucet", "pipe", "drain", "water", "leak"
- **Electrical**: "light", "outlet", "switch", "electrical", "power", "circuit", "breaker"
- **Heating/HVAC**: "heat", "heating", "furnace", "boiler", "radiator", "hvac", "ac", "air conditioning", "cooling"
- **Appliance**: "appliance", "refrigerator", "dishwasher", "oven", "stove", "washer", "dryer"
- **Other**: Default category

### 5. **Input Validation & Sanitization**

#### Issue Description:
- Trims whitespace
- Normalizes multiple spaces to single space
- Limits length to 5000 characters (truncates with "...")
- Required field validation

#### Email Validation:
- Validates email format using regex
- Case-insensitive matching
- Ignores invalid emails (logs warning)

#### Phone Number:
- Normalizes to E.164 format
- Handles spoken formats
- Validates format before use

### 6. **Enhanced Error Handling**

#### Tenant Not Found:
- Detailed debug information in logs
- Returns helpful error messages to bot
- Suggests providing name, phone, or email if missing

#### Debug Information:
- Logs caller phone extraction
- Logs conversation data (phone, email, name)
- Logs pre-identification status
- Logs match scores for tenant identification

### 7. **Call Transcript Integration**

- Automatically retrieves call transcript from `CallRecord` if available
- Links transcript to maintenance request via `vapi_call_id`
- Stores transcript in `call_transcript` field for PM review

### 8. **Improved Logging**

Enhanced logging throughout:
- `🔍` Pre-identification attempts
- `✅` Successful matches with scores
- `⚠️` Warnings (mismatches, invalid data)
- `❌` Errors with debug info
- `📝` Transcript retrieval
- `🔧` Request submission details

## Usage Examples

### Spoken Phone Number:
```
Input: "four one two five five five one two three four"
Output: "+14125551234"
```

### Auto-Detection:
```
Input: "My sink is leaking and flooding the kitchen!"
Auto-detected:
  - Priority: "urgent" (contains "flooding")
  - Category: "plumbing" (contains "sink", "leaking")
```

### Fuzzy Matching:
```
Input: Phone: "412-555-1234", Name: "John"
Database: Phone: "+14125551234", Name: "John Smith"
Result: ✅ Match (phone normalized, name partial match)
```

## Testing Recommendations

1. **Test spoken phone numbers**:
   - "four one two five five five one two three four"
   - "412 five five five 1234"
   - "four one two dash five five five dash one two three four"

2. **Test fuzzy matching**:
   - Phone: "(412) 555-1234" vs stored "+14125551234"
   - Name: "John" vs stored "John Smith"
   - Email: "john@email.com" vs stored "John@Email.com"

3. **Test auto-detection**:
   - "My AC is broken" → Category: "heating", Priority: "high"
   - "Minor cosmetic issue" → Priority: "low"
   - "URGENT: Gas leak!" → Priority: "urgent"

4. **Test edge cases**:
   - Invalid email format
   - Phone number with too many digits
   - Name with titles/suffixes
   - Multiple tenants with similar names

## Performance Considerations

- Phone normalization is O(n) where n is phone number length
- Tenant identification uses database indexes on phone_number, email, name
- Fuzzy matching only runs if exact match fails (performance optimization)
- Scoring system prioritizes exact matches (fastest path)

## Future Enhancements

1. **Machine Learning**: Train model to better detect priority/category
2. **Phone Number Validation**: Use phone number validation library (phonenumbers)
3. **Name Normalization**: Handle nicknames, aliases, and common variations
4. **Multi-language Support**: Parse phone numbers in other languages
5. **Confidence Scores**: Return confidence scores for tenant matches

