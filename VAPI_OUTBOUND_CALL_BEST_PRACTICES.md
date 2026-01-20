# Vapi Outbound Call Best Practices - Implementation Summary

## ✅ Current Implementation (Following Best Practices)

Based on Vapi's official documentation and community best practices, our implementation follows these guidelines:

---

## 📋 Payload Structure

### Core Fields (Required)
```json
{
  "assistantId": "assistant-uuid",           // ✅ Persistent assistant (best practice)
  "phoneNumber": {                          // ✅ Twilio integration
    "twilioPhoneNumber": "+14125551234",
    "twilioAccountSid": "...",
    "twilioAuthToken": "..."
  },
  "customer": {
    "number": "+15404497896",               // ✅ Required
    "name": "Yashan"                        // ✅ Best practice: include name
  }
}
```

### Context & Metadata (Recommended)
```json
{
  "metadata": {
    "contactId": "5",
    "campaign": "no_booking_followup",
    "callDirection": "outbound",
    "callContext": "The customer's name is Yashan. When they last reached out, they were interested in booking a tour for 891 Bullock Ford, Santa Clara, California. Use this information naturally..."
  },
  "assistantOverrides": {
    "variableValues": {
      "customerName": "Yashan",
      "inquiryProperty": "891 Bullock Ford, Santa Clara, California",
      "inquiryPurpose": "booking a tour",
      "customerRegion": "Santa Clara, California"
    }
  }
}
```

---

## 🎯 Best Practices We Follow

### 1. ✅ Use Persistent Assistant (`assistantId`)
- **Why**: Ensures consistency, easier updates, reusable configuration
- **Our Implementation**: Using `assistantId` to reference saved assistant
- **Alternative**: Transient assistant (`assistant` object) only for one-off customizations

### 2. ✅ Pass Context via Metadata
- **Why**: Metadata is designed for tracking and context
- **Our Implementation**: 
  - `metadata.callContext` - Full natural language context
  - `metadata.customerName`, `metadata.lastInquiryProperty`, etc. - Structured fields

### 3. ✅ Use `assistantOverrides.variableValues` for Structured Data
- **Why**: Allows assistant to reference variables in prompts using `{{variableName}}` syntax
- **Our Implementation**: Passing structured variables:
  - `customerName`
  - `inquiryProperty`
  - `inquiryPurpose`
  - `customerRegion`

### 4. ✅ Include Customer Name in Customer Object
- **Why**: Better personalization, Vapi can use it naturally
- **Our Implementation**: Adding `customer.name` when available

### 5. ✅ Filter Null Values
- **Why**: Prevents confusion, cleaner payloads
- **Our Implementation**: Filtering all null values from metadata

### 6. ✅ Privacy Compliance
- **Email**: Stored in metadata only (NOT in conversational context)
- **Name**: Included in context (natural to use in conversation)

---

## 🔧 How Assistant Can Access Context

### Method 1: Via Metadata (Full Context)
The assistant's system prompt can reference:
```
{% if metadata.callContext %}
Context: {{ metadata.callContext }}
{% endif %}
```

### Method 2: Via Variable Values (Structured)
The assistant's system prompt can reference:
```
Hello {{ customerName }}, I'm following up on your inquiry about {{ inquiryProperty }}.
You were interested in {{ inquiryPurpose }}.
```

### Method 3: Via Customer Object
The assistant automatically has access to:
- `customer.name` - Customer's name
- `customer.number` - Customer's phone number

---

## 📊 Complete Example Payload

```json
{
  "assistantId": "assistant-123",
  "phoneNumber": {
    "twilioPhoneNumber": "+14125551234",
    "twilioAccountSid": "AC...",
    "twilioAuthToken": "..."
  },
  "customer": {
    "number": "+15404497896",
    "name": "Yashan"
  },
  "metadata": {
    "contactId": "5",
    "campaign": "no_booking_followup",
    "callDirection": "outbound",
    "callContext": "The customer's name is Yashan. When they last reached out, they were interested in booking a tour for 891 Bullock Ford, Santa Clara, California. Use this information naturally in conversation. Do not mention 'records', 'database', 'system', or 'logs'. Reference it casually, as if you remember the previous conversation.",
    "customerName": "Yashan",
    "customerEmail": "kj373@gmail.com",
    "lastInquiryProperty": "891 Bullock Ford, Santa Clara, California",
    "lastInquiryPurpose": "booking a tour",
    "customerRegion": "Santa Clara, California"
  },
  "assistantOverrides": {
    "variableValues": {
      "customerName": "Yashan",
      "inquiryProperty": "891 Bullock Ford, Santa Clara, California",
      "inquiryPurpose": "booking a tour",
      "customerRegion": "Santa Clara, California"
    }
  }
}
```

---

## 🚫 What We DON'T Do (Common Mistakes)

### ❌ Don't Use `assistant.messages` with `assistantId`
- **Why**: Vapi doesn't allow this - causes "assistant.property messages should not exist" error
- **Our Solution**: Use `metadata.callContext` instead

### ❌ Don't Pass Null Values
- **Why**: Can confuse the assistant, clutter payloads
- **Our Solution**: Filter all null values before sending

### ❌ Don't Include Email in Conversational Context
- **Why**: Privacy risk, LLMs might accidentally reference it
- **Our Solution**: Email only in metadata, not in `callContext`

### ❌ Don't Use Transient Assistant for Standard Calls
- **Why**: Increases payload size, harder to maintain
- **Our Solution**: Use persistent assistant (`assistantId`)

---

## 📝 Assistant System Prompt Configuration

Your Vapi assistant's system prompt should be configured to use the context. Example:

```
You are Riley, a helpful apartment leasing assistant.

{% if metadata.callContext %}
Context for this call: {{ metadata.callContext }}
{% endif %}

{% if assistantOverrides.variableValues.customerName %}
The customer's name is {{ assistantOverrides.variableValues.customerName }}.
{% endif %}

Use this information naturally in conversation. Do not mention 'records', 'database', 'system', or 'logs'.
Reference it casually, as if you remember the previous conversation.
```

---

## ✅ Summary

Our implementation follows Vapi's best practices:
- ✅ Persistent assistant (`assistantId`)
- ✅ Metadata for context (`metadata.callContext`)
- ✅ Structured variables (`assistantOverrides.variableValues`)
- ✅ Customer name in customer object
- ✅ Privacy compliance (email excluded from context)
- ✅ Null value filtering
- ✅ Natural, concise context messages

**The system is production-ready and follows all recommended best practices!** 🎉
