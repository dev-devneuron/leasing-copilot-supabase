# Frontend Guide: Displaying Opt-Out Information

## ✅ Implementation Complete

The backend now provides detailed opt-out information including the exact transcript line that triggered the opt-out.

---

## 📋 API Response Fields

When a contact has opted out, the `/outbound-calls/candidates` endpoint now returns:

```typescript
{
  "contact_id": 123,
  "phone_number": "+16282725259",
  "name": "John",
  "opted_out": true,
  "opt_out_reason": "stop calling",  // The keyword/phrase that triggered opt-out
  "opt_out_transcript_line": "User: Please stop calling me, I'm not interested",  // Exact line from transcript
  // ... other fields
}
```

---

## 🎨 Frontend Implementation

### TypeScript Interface

```typescript
interface Candidate {
  contact_id: number;
  phone_number: string;
  name: string | null;
  email: string | null;
  opted_out: boolean;
  opt_out_reason: string | null;  // NEW
  opt_out_transcript_line: string | null;  // NEW
  // ... other fields
}
```

---

## 💡 Display Recommendations

### Option 1: Tooltip/Modal (Recommended)

Show opt-out status with a tooltip or modal that displays the exact transcript line when clicked:

```tsx
import { InfoIcon } from "lucide-react";

function OptOutBadge({ candidate }: { candidate: Candidate }) {
  if (!candidate.opted_out) return null;

  return (
    <div className="flex items-center gap-2">
      <span className="px-2 py-1 bg-red-100 text-red-800 rounded text-sm font-medium">
        Opted Out
      </span>
      {candidate.opt_out_transcript_line && (
        <Tooltip content={candidate.opt_out_transcript_line}>
          <InfoIcon className="w-4 h-4 text-gray-500 cursor-help" />
        </Tooltip>
      )}
    </div>
  );
}
```

### Option 2: Expandable Section

Show opt-out details in an expandable section:

```tsx
function OptOutDetails({ candidate }: { candidate: Candidate }) {
  if (!candidate.opted_out) return null;

  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border-l-4 border-red-500 bg-red-50 p-3 rounded">
      <div 
        className="flex items-center justify-between cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2">
          <span className="font-semibold text-red-800">Opted Out</span>
          {candidate.opt_out_reason && (
            <span className="text-sm text-red-600">
              Reason: {candidate.opt_out_reason}
            </span>
          )}
        </div>
        <ChevronDown className={`w-4 h-4 transition-transform ${expanded ? 'rotate-180' : ''}`} />
      </div>
      
      {expanded && candidate.opt_out_transcript_line && (
        <div className="mt-2 pt-2 border-t border-red-200">
          <p className="text-sm font-medium text-gray-700 mb-1">Exact transcript line:</p>
          <p className="text-sm text-gray-600 italic bg-white p-2 rounded border">
            "{candidate.opt_out_transcript_line}"
          </p>
        </div>
      )}
    </div>
  );
}
```

### Option 3: Inline Display

Show opt-out reason and transcript line directly in the contact card:

```tsx
function ContactCard({ candidate }: { candidate: Candidate }) {
  return (
    <div className="border rounded-lg p-4">
      {/* Contact info */}
      <h3>{candidate.name || "Unknown"}</h3>
      <p>{candidate.phone_number}</p>
      
      {/* Opt-out section */}
      {candidate.opted_out && (
        <div className="mt-3 p-2 bg-red-50 border border-red-200 rounded">
          <p className="text-sm font-semibold text-red-800">
            ⚠️ This contact has opted out
          </p>
          {candidate.opt_out_reason && (
            <p className="text-xs text-red-600 mt-1">
              Triggered by: "{candidate.opt_out_reason}"
            </p>
          )}
          {candidate.opt_out_transcript_line && (
            <p className="text-xs text-gray-600 mt-2 italic">
              User said: "{candidate.opt_out_transcript_line}"
            </p>
          )}
        </div>
      )}
    </div>
  );
}
```

---

## 🎯 Best Practices

1. **Always Show Context:**
   - Display the exact transcript line so users can verify the opt-out was legitimate
   - This helps identify false positives

2. **Visual Hierarchy:**
   - Use red/error colors for opt-out status
   - Make it clear but not alarming

3. **Accessibility:**
   - Include tooltips or expandable sections for detailed info
   - Don't clutter the main view with long transcript lines

4. **Action Buttons:**
   - If you have a "Clear Opt-Out" button, show it near the opt-out details
   - Link to: `POST /outbound-calls/contacts/{contact_id}/clear-opt-out`

---

## 📊 Example UI Layout

```
┌─────────────────────────────────────────┐
│ Contact: John                           │
│ Phone: +16282725259                      │
│ Email: john@gmail.com                    │
│                                         │
│ ⚠️ Opted Out                            │
│ Reason: "stop calling"                  │
│ [ℹ️] Show transcript line              │
│                                         │
│ ┌─────────────────────────────────────┐ │
│ │ Exact transcript line:               │ │
│ │ "User: Please stop calling me"      │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ [Clear Opt-Out]                         │
└─────────────────────────────────────────┘
```

---

## 🔍 Testing Checklist

- [ ] Opt-out status displays correctly
- [ ] Opt-out reason shows when available
- [ ] Transcript line displays when available
- [ ] Tooltip/modal works correctly
- [ ] Expandable section toggles properly
- [ ] Clear opt-out button works (if implemented)
- [ ] Handles null values gracefully (no errors if fields are null)

---

## 🚀 Next Steps

1. **Implement the UI component** using one of the patterns above
2. **Test with real data** from the API
3. **Add "Clear Opt-Out" functionality** if needed
4. **Monitor user feedback** on the opt-out display

---

**The backend is ready - now implement the frontend display!** 🎉
