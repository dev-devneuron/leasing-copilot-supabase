# Vapi Payload Filtering - No Null/N/A/Empty Values

## ✅ Implementation Complete

All null, "N/A", empty strings, and invalid values are now filtered out before sending to Vapi.

---

## 🔧 What Was Fixed

### 1. **Helper Function Added**
Created `_is_valid_value()` function that checks:
- ❌ `None` values
- ❌ Empty strings (`""`)
- ❌ Whitespace-only strings
- ❌ "N/A", "na", "none", "null", "undefined" (case-insensitive)

### 2. **Context Message Filtering**
**Before:**
```python
if customer_name:
    context_parts.append(...)
```

**After:**
```python
if _is_valid_value(customer_name):
    context_parts.append(...)
```

**Applied to:**
- `customer_name` (inferred_name or contact.name)
- `property_addr` (inquiry_property)
- `purpose` (inquiry_purpose)
- `region` (extracted region)

---

### 3. **Customer Name Filtering**
**Before:**
```python
if customer_name:
    payload["customer"]["name"] = customer_name
```

**After:**
```python
if _is_valid_value(customer_name):
    payload["customer"]["name"] = customer_name
```

---

### 4. **Context Message Filtering**
**Before:**
```python
if context_message:
    payload["metadata"]["callContext"] = context_message
```

**After:**
```python
if _is_valid_value(context_message):
    payload["metadata"]["callContext"] = context_message
```

---

### 5. **Structured Variables Filtering**
**Before:**
```python
if extracted_intel.get("inquiry_property"):
    variable_values["inquiryProperty"] = extracted_intel["inquiry_property"]
```

**After:**
```python
inquiry_property = extracted_intel.get("inquiry_property")
if _is_valid_value(inquiry_property):
    variable_values["inquiryProperty"] = inquiry_property
```

**Applied to:**
- `customerName`
- `inquiryProperty`
- `inquiryPurpose`
- `customerRegion`

**Result:** `assistantOverrides.variableValues` is only added if at least one valid variable exists.

---

### 6. **Metadata Filtering**
**Before:**
```python
payload["metadata"] = {k: v for k, v in payload["metadata"].items() if v is not None}
```

**After:**
```python
payload["metadata"] = {
    k: v for k, v in payload["metadata"].items() 
    if _is_valid_value(v)
}
```

**Now filters:**
- `None` values
- Empty strings
- "N/A" strings
- Whitespace-only strings

---

## 📋 What Gets Sent to Vapi

### ✅ Always Sent:
- `assistantId` (required)
- `phoneNumber` (required)
- `customer.number` (required)
- `metadata.contactId` (required)
- `metadata.campaign` (required)
- `metadata.callDirection` (required)

### ✅ Conditionally Sent (only if valid):
- `customer.name` - Only if not null/empty/N/A
- `metadata.callContext` - Only if context message was built (has valid data)
- `assistantOverrides.variableValues` - Only if at least one valid variable exists

### ❌ Never Sent:
- `email` - Privacy: Email is never sent to Vapi (only logged internally)
- `null` values
- `"N/A"` strings
- Empty strings
- Whitespace-only strings

---

## 🔍 Example Payloads

### Example 1: Full Data Available
```json
{
  "assistantId": "assistant_123",
  "phoneNumber": {...},
  "customer": {
    "number": "+1234567890",
    "name": "John"  // ✅ Valid - sent
  },
  "metadata": {
    "contactId": "123",
    "campaign": "no_booking_followup",
    "callDirection": "outbound",
    "callContext": "The customer's name is John. When they last reached out, they were interested in booking a tour for 123 Main St."  // ✅ Valid - sent
  },
  "assistantOverrides": {
    "variableValues": {
      "customerName": "John",  // ✅ Valid - sent
      "inquiryProperty": "123 Main St",  // ✅ Valid - sent
      "inquiryPurpose": "booking a tour"  // ✅ Valid - sent
    }
  }
}
```

### Example 2: Partial Data (Some Nulls)
```json
{
  "assistantId": "assistant_123",
  "phoneNumber": {...},
  "customer": {
    "number": "+1234567890"
    // ❌ No "name" - was null/empty/N/A, not sent
  },
  "metadata": {
    "contactId": "123",
    "campaign": "no_booking_followup",
    "callDirection": "outbound",
    "callContext": "They were previously asking about availability."  // ✅ Valid - sent (only purpose, no name/property)
  },
  "assistantOverrides": {
    "variableValues": {
      "inquiryPurpose": "availability inquiry"  // ✅ Valid - sent
      // ❌ No customerName - was null/empty/N/A
      // ❌ No inquiryProperty - was null/empty/N/A
    }
  }
}
```

### Example 3: No Valid Data
```json
{
  "assistantId": "assistant_123",
  "phoneNumber": {...},
  "customer": {
    "number": "+1234567890"
    // ❌ No "name" - was null/empty/N/A
  },
  "metadata": {
    "contactId": "123",
    "campaign": "no_booking_followup",
    "callDirection": "outbound"
    // ❌ No "callContext" - all fields were null/empty/N/A
  }
  // ❌ No "assistantOverrides" - no valid variables
}
```

---

## 🛡️ Privacy Protection

### Email Handling:
- ✅ Email is **loaded** from `extracted_intel` for internal logging
- ❌ Email is **NOT** sent in `metadata.callContext` (privacy)
- ❌ Email is **NOT** sent in `assistantOverrides.variableValues` (privacy)
- ❌ Email is **NOT** sent in `metadata` (privacy)

**Reason:** Email should never be in conversational context for outbound calls.

---

## ✅ Verification Checklist

- [x] Helper function `_is_valid_value()` created
- [x] Context message parts filtered (name, property, purpose, region)
- [x] Customer name filtered before adding to payload
- [x] Context message filtered before adding to metadata
- [x] Structured variables filtered (customerName, inquiryProperty, inquiryPurpose, customerRegion)
- [x] Metadata values filtered (null, empty, "N/A")
- [x] Email never sent to Vapi (privacy)
- [x] `assistantOverrides` only added if at least one valid variable exists
- [x] All filtering applied consistently

---

## 🎉 Result

**Vapi now receives only valid, non-empty data!**

- ✅ No null values
- ✅ No "N/A" strings
- ✅ No empty strings
- ✅ No whitespace-only strings
- ✅ Email never sent (privacy)
- ✅ Clean, valid payloads only

**Ready for production!** 🚀
