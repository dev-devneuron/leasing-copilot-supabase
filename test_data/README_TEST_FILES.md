# Test Files for Listing Upload System

This directory contains test files to verify the AI-powered listing parser is working correctly.

## Test Files Overview

### 1. `listings_test.json` ✅
**Format:** Well-formed JSON  
**Purpose:** Test standard JSON parsing  
**Features:**
- Standard field names
- Complete data with all fields
- Nested agent information
- Multiple listings

**Expected Result:** Should parse all 4 listings successfully

---

### 2. `listings_test.csv` ✅
**Format:** Standard CSV  
**Purpose:** Test CSV parsing with standard columns  
**Features:**
- Standard column names (address, price, bedrooms, etc.)
- Quoted values
- Multiple listings

**Expected Result:** Should parse all 4 listings successfully

---

### 3. `listings_test_variations.csv` ✅
**Format:** CSV with non-standard column names  
**Purpose:** Test field name mapping and normalization  
**Features:**
- Alternative column names (location, rent, beds, baths, sqft)
- Tests the parser's ability to map variations to standard fields

**Expected Result:** Should parse all 3 listings and map fields correctly

---

### 4. `listings_test.txt` ✅
**Format:** Structured text  
**Purpose:** Test text parsing with structured format  
**Features:**
- Semi-structured text with labels
- Multiple property listings
- Various formats within same file
- Agent information

**Expected Result:** Should extract all 4 listings using AI parsing

---

### 5. `listings_test_malformed.json` ⚠️
**Format:** JSON with non-standard field names  
**Purpose:** Test AI-powered field mapping  
**Features:**
- Non-standard field names (property_address, cost, bed, bath, area)
- Mixed data types (strings for numbers)
- Address components split across fields
- Tests the parser's normalization capabilities

**Expected Result:** Should parse all 3 listings and normalize field names correctly

---

### 6. `listings_test_unstructured.txt` 🤖
**Format:** Unstructured natural language  
**Purpose:** Test AI parsing of completely unstructured text  
**Features:**
- Natural language description
- No clear structure
- Mixed formats
- Tests the AI's ability to extract structured data from free text

**Expected Result:** Should extract all 4 listings using AI parsing

---

## How to Test

### Option 1: Using the Upload Endpoint

1. **Start your backend server**
   ```bash
   uvicorn vapi.app:app --reload
   ```

2. **Upload via API** (using curl or Postman):
   ```bash
   # For Realtor upload
   curl -X POST "http://localhost:8000/UploadListings" \
     -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     -F "listing_file=@test_data/listings_test.json"
   
   # For Property Manager upload
   curl -X POST "http://localhost:8000/property-manager/upload-listings" \
     -H "Authorization: Bearer YOUR_PM_JWT_TOKEN" \
     -F "listing_file=@test_data/listings_test.csv"
   ```

3. **Check the response:**
   - Should return success message
   - Should indicate number of listings parsed
   - Check database to verify listings were stored

### Option 2: Using Frontend

1. Navigate to the upload page
2. Select one of the test files
3. Click upload
4. Verify success message and check listings in database

---

## Expected Results

### JSON Files
- ✅ `listings_test.json`: 4 listings parsed
- ✅ `listings_test_malformed.json`: 3 listings parsed (with field normalization)

### CSV Files
- ✅ `listings_test.csv`: 4 listings parsed
- ✅ `listings_test_variations.csv`: 3 listings parsed (with column mapping)

### TXT Files
- ✅ `listings_test.txt`: 4 listings extracted (using AI)
- ✅ `listings_test_unstructured.txt`: 4 listings extracted (using AI)

---

## Testing Checklist

- [ ] JSON parsing works with standard format
- [ ] JSON parsing handles non-standard field names
- [ ] CSV parsing works with standard columns
- [ ] CSV parsing maps alternative column names
- [ ] TXT parsing extracts structured data
- [ ] Unstructured text is parsed correctly
- [ ] Field normalization works (e.g., "beds" → "bedrooms")
- [ ] Address construction works from components
- [ ] Price normalization handles currency symbols
- [ ] Features are extracted correctly (arrays, strings, comma-separated)
- [ ] Agent information is extracted
- [ ] All listings are stored in database
- [ ] Files are uploaded to Supabase storage

---

## Troubleshooting

### If parsing fails:

1. **Check logs** for error messages
2. **Verify AI is configured:**
   - Check if `GEMINI_API_KEY` or Vertex AI is set
   - Check application logs for "✅ Vertex AI initialized" or "✅ Using Gemini API"
3. **Check file format:**
   - Ensure JSON is valid
   - Ensure CSV has proper encoding (UTF-8)
   - Check file size (should be reasonable)

### Common Issues:

- **"AI parsing error"**: Check API keys and network connectivity
- **"Failed to parse file"**: Check file format and encoding
- **"No listings found"**: File might be empty or format not recognized

---

## Notes

- All test files use realistic but fictional data
- Addresses are generic examples
- Prices and features are for testing purposes only
- The parser should handle all variations automatically
- AI parsing is used for TXT files and when standard parsing fails

---

## Next Steps

After successful testing:
1. Try uploading your real listing data
2. Monitor parsing accuracy
3. Adjust prompts in `listing_parser.py` if needed
4. Consider adding more test cases for edge cases you encounter

