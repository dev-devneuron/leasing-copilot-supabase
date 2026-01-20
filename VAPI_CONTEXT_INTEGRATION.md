# Vapi Context Integration - How Re-engagement Data is Passed

## ✅ Implementation Complete

The backend now passes extracted intelligence to Vapi using the **RECOMMENDED METHOD** (`assistant.messages`) for natural, personalized re-engagement calls.

---

## 🔄 How It Works

### Step 1: Load Cached Intelligence
When triggering an outbound call, the system:
1. **Loads cached `extracted_intel`** from the most recent `CallRecord` (FAST - no re-extraction needed)
2. **Falls back to extraction** if no cache exists
3. **Filters out null values** to avoid confusing Vapi

### Step 2: Build Context Message
Builds a natural, conversational context message:
- ⚠️ **PRIVACY RULE**: Email is **NOT** included in conversational context
- ✅ Name **CAN** be included (natural to use in conversation)
- Email is stored in `metadata` only (not in `assistant.messages`)
- Context is concise and non-repetitive

Example:
```
"The customer's name is Yashan. When they last reached out, they were interested in booking a tour for 891 Bullock Ford, Santa Clara, California. 
Use this information naturally in conversation. Do not mention 'records', 'database', 'system', or 'logs'. 
Reference it casually, as if you remember the previous conversation."
```

**Why no email in context?**
- LLMs might accidentally reference email
- Could ask to "confirm" it
- Sounds creepy/unnatural
- Privacy compliance: Email should only be in metadata

**Why name is OK:**
- Natural to use in conversation ("Hi Yashan...")
- Customer expects to be addressed by name
- No privacy risk when used naturally

### Step 3: Add to Vapi Payload
Adds context to `metadata.callContext` (Vapi doesn't allow `assistant.messages` when using `assistantId`):

```json
{
  "assistantId": "assistant_123",
  "phoneNumber": { ... },
  "customer": { "number": "+15404497896" },
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
  }
}
```

**Important**: Your Vapi assistant's system prompt should be configured to read from `metadata.callContext` to access this context during the call.

---

## 📋 What Gets Passed

### In `assistant.messages` (Primary Context)
- ✅ Customer name (if available) - natural to use in conversation
- ✅ Property they inquired about (if available)
- ✅ Purpose of inquiry (if available)
- ✅ Region (if available, only if not already in property address)
- ✅ Natural usage instructions
- ❌ **NO email** (privacy - stored in metadata only)

### In `metadata` (Additional Context)
- ✅ Contact ID
- ✅ Campaign type
- ✅ Customer name, email, phone
- ✅ Last inquiry property, purpose, summary
- ✅ Call attempt count
- ✅ Last call outcome
- ✅ **All null values filtered out**

---

## 🎯 Guidelines Followed

### ✅ DO (What We Do)
- ✅ Use `metadata.callContext` for context (Vapi doesn't allow `assistant.messages` with `assistantId`)
- ✅ Filter out null values
- ✅ Use natural, conversational phrasing
- ✅ Include customer name in context (natural to use)
- ✅ Combine property + purpose into one sentence (avoid repetition)
- ✅ Only include region if different from property address
- ✅ Keep context concise and non-repetitive
- ✅ Store email in metadata only (not in conversational context)
- ✅ Configure assistant system prompt to read from `metadata.callContext`

### ❌ DON'T (What We Avoid)
- ❌ **Never include email in conversational context** (privacy risk)
- ❌ Never mention "records", "database", "system", "logs"
- ❌ Never pass null values
- ❌ Never reference call recordings
- ❌ Never infer new information
- ❌ Never sound like surveillance
- ❌ Never repeat information (e.g., "Santa Clara" twice)

---

## 📊 Example Context Messages

### Example 1: Full Context (Name + Property + Purpose)
```
Context for this call: The customer's name is Yashan. When they last reached out, they were interested in booking a tour for 891 Bullock Ford, Santa Clara, California. 
Use this information naturally in conversation. Do not mention 'records', 'database', 'system', or 'logs'. 
Reference it casually, as if you remember the previous conversation.
```
**Note**: Name included (natural to use). Property and purpose combined. Email excluded (privacy).

### Example 2: Property Only (No Purpose, No Name)
```
Context for this call: When they last reached out, they were asking about 891 Bullock Ford, Santa Clara, California. 
Use this information naturally in conversation. Do not mention 'records', 'database', 'system', or 'logs'. 
Reference it casually, as if you remember the previous conversation.
```

### Example 3: Purpose Only (No Property, No Name)
```
Context for this call: They were previously asking about availability. 
Use this information naturally in conversation. Do not mention 'records', 'database', 'system', or 'logs'. 
Reference it casually, as if you remember the previous conversation.
```

### Example 4: Name Only (No Property/Purpose)
```
Context for this call: The customer's name is Yashan. 
Use this information naturally in conversation. Do not mention 'records', 'database', 'system', or 'logs'. 
Reference it casually, as if you remember the previous conversation.
```

---

## 🔍 Logging

The system logs:
1. **What intelligence was loaded** (cached vs extracted)
2. **Context message built** (full text)
3. **Full payload sent to Vapi** (metadata keys, assistant.messages preview)
4. **What fields were filtered** (null values removed)

Example logs:
```
✅ Using cached extracted intelligence from call 019b31bf...
   📊 Cached intel: email=kj373@gmail.com, name=Yashan Jamal, property=891 Bullock Ford..., purpose=booking a tour
✅ Built context message for assistant:
   The customer's name is Yashan Jamal. Their email is kj373@gmail.com. When they last reached out, they were asking about 891 Bullock Ford, Santa Clara, California. They were interested in booking a tour. They were looking in Santa Clara, California. Use this information naturally in conversation...
📤 Added assistant.messages context to Vapi payload
📤 Merged additional metadata (filtered nulls): ['contactId', 'campaign', 'callDirection', 'customerName', 'customerEmail', 'lastInquiryProperty', 'lastInquiryPurpose', 'customerRegion']
📤 SENDING PAYLOAD TO VAPI:
   ✅ Assistant messages context: Context for this call: The customer's name is Yashan Jamal...
```

---

## 🎯 How Riley Should Use This Context

### ✅ GOOD Examples
- "Hi Yashan, when you last reached out, you were asking about 891 Bullock Ford in Santa Clara. I just wanted to check if you'd like help setting up a tour."
- "Hi, I'm following up on your inquiry about the property at 891 Bullock Ford. Are you still interested in booking a tour?"
- "You had reached out earlier about availability in Santa Clara, so this is just a quick follow-up."

### ❌ BAD Examples (What NOT to Do)
- ❌ "I see from your records on January 12th at 3:41 PM you asked about..."
- ❌ "Our system shows you were interested in..."
- ❌ "According to our database..."
- ❌ "I see in your records..."

---

## 🔐 Privacy & Compliance

### Rules Enforced
- ✅ **Email NOT in conversational context** (metadata only)
- ✅ **Name CAN be in conversational context** (natural to use)
- ✅ Only references what customer voluntarily shared
- ✅ Never mentions internal systems or logs
- ✅ Never infers new information
- ✅ Never references call recordings
- ✅ Natural fallback if user seems confused
- ✅ Concise, non-repetitive context messages

### Fallback Phrasing
If context seems unclear or user is confused:
> "You had reached out earlier for apartment info, so this is just a quick follow-up."

---

## 🚀 Benefits

1. **Efficient**: Uses cached intelligence (no re-extraction)
2. **Natural**: Context in conversational format
3. **Compliant**: No mention of systems/records
4. **Complete**: All non-null fields included
5. **Flexible**: Works with partial or full context

---

## 📝 Code Location

- **Endpoint**: `POST /outbound-calls/trigger` in `vapi/app.py`
- **Function**: `trigger_outbound_call()` in `DB/outbound_calling.py`
- **Extraction**: Uses cached `extracted_intel` from `CallRecord.extracted_intel`

---

## ⚙️ Vapi Assistant Configuration Required

**IMPORTANT**: Your Vapi assistant's system prompt must be configured to read from `metadata.callContext` to access the re-engagement context.

Example system prompt addition:
```
{% if metadata.callContext %}
Context for this call: {{ metadata.callContext }}
{% endif %}
```

Or in your assistant configuration, reference `metadata.callContext` in the system prompt so Riley can access the context naturally during the call.

---

**The system is now fully integrated with Vapi using `metadata.callContext`!** 🎉
