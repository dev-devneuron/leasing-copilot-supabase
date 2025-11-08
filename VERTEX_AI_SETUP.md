# Vertex AI Setup Guide

This guide explains how to configure Google Cloud Vertex AI for enhanced ML capabilities in the listing parser and embeddings.

## Overview

The system now uses **Vertex AI** (preferred) for:
- **Text Generation**: Gemini models for parsing unstructured listing data
- **Text Embeddings**: Gecko models for RAG and similarity search
- **Advanced ML Features**: Access to latest Gemini models and Vertex AI capabilities

**Fallback**: If Vertex AI is not configured, the system automatically falls back to the Gemini API.

## Benefits of Vertex AI

✅ **More Robust Models**: Access to latest Gemini models (gemini-2.0-flash-exp, gemini-1.5-pro, etc.)  
✅ **Better Performance**: Optimized inference with lower latency  
✅ **Enterprise Features**: Better rate limits, monitoring, and control  
✅ **Cost Optimization**: More efficient token usage  
✅ **Advanced Embeddings**: textembedding-gecko@003 for better semantic understanding  

## Prerequisites

1. **Google Cloud Project** with billing enabled
2. **Vertex AI API** enabled in your GCP project
3. **Service Account** with Vertex AI permissions
4. **Authentication** configured (Application Default Credentials or service account key)

## Setup Steps

### 1. Enable Vertex AI API

```bash
# Using gcloud CLI
gcloud services enable aiplatform.googleapis.com

# Or via GCP Console:
# Navigate to: APIs & Services > Library > Search "Vertex AI API" > Enable
```

### 2. Create Service Account (Recommended)

```bash
# Create service account
gcloud iam service-accounts create vertex-ai-service \
    --display-name="Vertex AI Service Account"

# Grant Vertex AI User role
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:vertex-ai-service@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/aiplatform.user"

# Create and download key
gcloud iam service-accounts keys create vertex-ai-key.json \
    --iam-account=vertex-ai-service@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

### 3. Set Environment Variables

Add these to your `.env` file:

```bash
# Vertex AI Configuration (Recommended)
USE_VERTEX_AI=true
GCP_PROJECT_ID=your-gcp-project-id
GCP_LOCATION=us-central1  # or us-east1, europe-west1, etc.
VERTEX_AI_MODEL=gemini-2.0-flash-exp  # or gemini-1.5-pro, gemini-1.5-flash
VERTEX_AI_EMBEDDING_MODEL=textembedding-gecko@003

# Fallback: Gemini API (if Vertex AI not configured)
GEMINI_API_KEY=your-gemini-api-key  # Optional, used as fallback
```

### 4. Authentication Setup

**Option A: Application Default Credentials (Recommended for local dev)**

```bash
# Set the service account key
export GOOGLE_APPLICATION_CREDENTIALS="path/to/vertex-ai-key.json"

# Or use gcloud auth
gcloud auth application-default login
```

**Option B: Service Account Key File**

The system will automatically use `GOOGLE_APPLICATION_CREDENTIALS` if set.

### 5. Install Dependencies

```bash
pip install google-cloud-aiplatform>=1.38.0 vertexai>=1.38.0

# Or using poetry
poetry add google-cloud-aiplatform>=1.38.0 vertexai>=1.38.0
```

## Configuration Options

### Available Models

**Text Generation Models:**
- `gemini-2.0-flash-exp` (default) - Latest experimental model, fastest
- `gemini-1.5-pro` - Most capable, best for complex parsing
- `gemini-1.5-flash` - Balanced performance and cost

**Embedding Models:**
- `textembedding-gecko@003` (default) - Latest, best quality
- `textembedding-gecko@002` - Previous version
- `textembedding-gecko-multilingual@001` - For multilingual support

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `USE_VERTEX_AI` | Enable Vertex AI (true/false) | `true` |
| `GCP_PROJECT_ID` | Your GCP project ID | Required |
| `GCP_LOCATION` | GCP region for Vertex AI | `us-central1` |
| `VERTEX_AI_MODEL` | Text generation model | `gemini-2.0-flash-exp` |
| `VERTEX_AI_EMBEDDING_MODEL` | Embedding model | `textembedding-gecko@003` |
| `GEMINI_API_KEY` | Fallback API key | Optional |

## Verification

After setup, start your application and check the logs:

```
✅ Vertex AI initialized: Project=your-project, Location=us-central1
   Model: gemini-2.0-flash-exp, Embedding: textembedding-gecko@003
✅ Using Vertex AI for embeddings
```

If Vertex AI is not available, you'll see:

```
⚠️  Vertex AI not available, falling back to Gemini API
✅ Using Gemini API (fallback): models/gemini-2.0-flash-exp
```

## Troubleshooting

### Issue: "Vertex AI initialization failed"

**Solutions:**
1. Verify `GCP_PROJECT_ID` is correct
2. Check that Vertex AI API is enabled
3. Verify authentication credentials
4. Ensure service account has `roles/aiplatform.user` role

### Issue: "Permission denied"

**Solutions:**
1. Grant `roles/aiplatform.user` to your service account
2. Check IAM permissions in GCP Console
3. Verify service account key is valid

### Issue: "Model not found"

**Solutions:**
1. Check model name spelling (e.g., `gemini-2.0-flash-exp`)
2. Verify model is available in your region
3. Some models may require allowlisting - check GCP Console

### Issue: "Billing not enabled"

**Solutions:**
1. Enable billing in your GCP project
2. Vertex AI requires a billing account (even for free tier)

## Cost Considerations

- **Vertex AI**: Pay-per-use pricing, typically cheaper than API for high volume
- **Gemini API**: Simpler pricing, good for low-medium volume
- **Free Tier**: Check current GCP free tier limits

## Migration from Gemini API

If you're currently using Gemini API, the system will automatically:
1. Try Vertex AI first (if configured)
2. Fall back to Gemini API if Vertex AI fails
3. No code changes needed - just set environment variables

## Support

For issues or questions:
- Check GCP Vertex AI documentation: https://cloud.google.com/vertex-ai/docs
- Review application logs for detailed error messages
- Ensure all environment variables are set correctly

