# Call Record Cleanup - Short Calls Filtering

## ✅ Implementation Complete

The system now automatically filters out short call records (< 1 minute) to reduce noise and improve data quality.

---

## 🎯 Requirements

1. **New calls going forward**: Only keep call records with duration **> 60 seconds (1 minute)**
2. **Existing calls cleanup**: Remove call records with duration **<= 80 seconds (1 minute 20 seconds)**

---

## 🔧 How It Works

### 1. Automatic Filtering (New Calls)

When a call record is created/updated via webhook:

- **If `call_duration <= 60 seconds`**:
  - Transcript is **cleared** (set to `None`)
  - Extracted intel is **cleared** (set to `None`)
  - Extraction status set to `"skipped"`
  - Metadata marked with `discarded_reason: "call_too_short"`
  - **No extraction is performed** (saves Gemini API calls)

### 2. Extraction Logic

The `extract_and_store_intel_for_call_record()` function now:

- **Checks call duration first** before processing
- If `call_duration <= 60 seconds`, immediately returns empty intel and marks as skipped
- This prevents wasting Gemini API calls on short/voicemail calls

### 3. Candidate Processing

When building candidate lists:

- `get_best_recent_intel_for_phone()` **excludes short calls** from search
- Only searches calls with `call_duration > 60` or `call_duration IS NULL` (not set yet)
- This ensures we only extract from meaningful conversations

---

## 🧹 Cleanup Endpoint

### POST `/admin/cleanup-short-calls`

**Parameters:**
- `dry_run` (bool, default: `True`) - If True, only counts records without deleting
- `min_duration_seconds` (int, default: `80`) - Minimum duration to keep (80s = 1m 20s)

**Example Request:**
```bash
# Dry run (safe - just counts)
POST /admin/cleanup-short-calls?dry_run=true&min_duration_seconds=80

# Actual cleanup (deletes records)
POST /admin/cleanup-short-calls?dry_run=false&min_duration_seconds=80
```

**Response:**
```json
{
  "message": "Cleanup completed",
  "result": {
    "deleted": 150,
    "dry_run": false
  }
}
```

---

## 📋 Cleanup Process

### Step 1: Run Dry Run First

```bash
POST /admin/cleanup-short-calls?dry_run=true&min_duration_seconds=80
```

This will:
- Count how many records would be deleted
- Show examples of records that would be deleted
- **Not actually delete anything**

### Step 2: Review Results

Check the response to see:
- How many call records would be deleted
- Examples of the records (first 10 shown)

### Step 3: Run Actual Cleanup

```bash
POST /admin/cleanup-short-calls?dry_run=false&min_duration_seconds=80
```

This will:
- Delete all call records with `call_duration <= 80 seconds`
- Return count of deleted records
- Commit changes to database

---

## ⚠️ Important Notes

1. **Duration Thresholds:**
   - **New calls**: Discarded if `<= 60 seconds` (1 minute)
   - **Existing cleanup**: Deleted if `<= 80 seconds` (1 minute 20 seconds)
   - The 20-second buffer for existing cleanup ensures we don't accidentally delete calls that are right at the 1-minute mark

2. **Call Records Still Created:**
   - Short calls are still **created in the database** (for tracking/audit)
   - But transcripts and extracted intel are **cleared**
   - This allows you to see that a call happened, but not waste storage on useless data

3. **Extraction Skipped:**
   - Short calls **never trigger Gemini extraction**
   - This saves API costs and improves data quality

4. **Candidate Search:**
   - Short calls are **excluded from candidate intelligence gathering**
   - Only meaningful conversations are used for re-engagement context

---

## 🔍 What Gets Deleted

The cleanup removes call records where:
- `call_duration IS NOT NULL`
- `call_duration <= 80` (seconds)

**Records NOT deleted:**
- Calls with `call_duration IS NULL` (duration not set yet - might be in progress)
- Calls with `call_duration > 80` seconds

---

## 📊 Expected Impact

After cleanup:
- **Reduced database size** (fewer call records)
- **Faster candidate processing** (fewer calls to search through)
- **Better extraction quality** (only meaningful conversations)
- **Lower Gemini API costs** (no extraction on short calls)

---

## 🚀 Next Steps

1. **Run dry run** to see how many records would be deleted:
   ```bash
   POST /admin/cleanup-short-calls?dry_run=true
   ```

2. **Review the count** and examples

3. **Run actual cleanup** when ready:
   ```bash
   POST /admin/cleanup-short-calls?dry_run=false
   ```

4. **Monitor going forward** - new short calls will be automatically filtered

---

**The system is now configured to automatically filter short calls going forward!** 🎉
