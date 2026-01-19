# spaCy Setup for Hybrid CRF/NER Extraction

This guide explains how to set up spaCy for the hybrid CRF/NER fallback extraction system.

---

## 🎯 Why spaCy?

The backend uses a **hybrid extraction approach** when Gemini AI fails:

- **Email**: Regex (best for structured patterns)
- **Name**: CRF/NER via spaCy (better for natural speech & noise)
- **Property**: Hybrid Regex + NER (handles variations better)
- **Region**: Hybrid Regex + NER

spaCy provides Named Entity Recognition (NER) capabilities that use neural networks (similar to CRF) to extract entities from text, making it much better than regex alone for handling natural speech patterns.

---

## 📦 Installation

### Step 1: Install spaCy

```bash
pip install spacy>=3.7.0
```

Or if using requirements.txt (already added):
```bash
pip install -r requirements.txt
```

### Step 2: Download English Model

The backend needs the English language model for NER:

```bash
python -m spacy download en_core_web_sm
```

**Note:** The `en_core_web_sm` model is small (~12MB) and fast, perfect for production use.

---

## ✅ Verification

After installation, the backend will automatically:
1. Load the spaCy model on first use (lazy loading)
2. Use it for hybrid extraction when AI fails
3. Log: `✅ spaCy NER model loaded for hybrid extraction`

---

## 🔧 How It Works

### Extraction Priority:

1. **Gemini AI** (Primary)
   - Tries first for all fields
   - Most accurate, understands context

2. **Hybrid CRF/NER + Regex** (Fallback)
   - Only used if AI fails or is unavailable
   - **Email**: Regex patterns
   - **Name**: spaCy NER (PERSON entities)
   - **Property**: Regex first, then NER (LOC/GPE/FAC entities)
   - **Purpose**: Keyword matching
   - **Region**: Regex + NER (GPE entities)

### Example:

```python
# If AI fails, hybrid extraction kicks in:
# - Finds email with regex: "rehan@gmail.com"
# - Finds name with NER: "Rehan" (from PERSON entity)
# - Finds property with hybrid: "188 Alexandra Road" (regex) or NER fallback
```

---

## 🐛 Troubleshooting

### Issue: "spaCy model 'en_core_web_sm' not found"

**Solution:**
```bash
python -m spacy download en_core_web_sm
```

### Issue: "spaCy not installed"

**Solution:**
```bash
pip install spacy>=3.7.0
```

### Issue: Model download fails

**Alternative:** The backend will gracefully fall back to regex-only extraction if spaCy is unavailable. However, accuracy for names and properties will be reduced.

---

## 📊 Performance

- **Model Size**: ~12MB (en_core_web_sm)
- **Load Time**: ~1-2 seconds (first use only, then cached)
- **Extraction Speed**: ~50-100ms per transcript
- **Memory**: ~50MB additional RAM

---

## 🚀 Production Deployment

### Render.com / Cloud Platforms

Add to your build/startup script:

```bash
# In your build script or startup command
pip install spacy>=3.7.0
python -m spacy download en_core_web_sm
```

Or add to your Dockerfile:
```dockerfile
RUN pip install spacy>=3.7.0 && python -m spacy download en_core_web_sm
```

---

## 📝 Notes

- The spaCy model is **lazy loaded** - it only loads when needed
- If spaCy is unavailable, the system falls back to regex-only (still works, just less accurate)
- The hybrid approach gives you the **best of both worlds**: regex speed for emails, NER accuracy for names/properties

---

The backend is ready to use hybrid extraction once spaCy is installed!
