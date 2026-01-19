"""
Vertex AI Client for ML Models

This module provides a robust interface to Google Cloud Vertex AI for:
- Text generation (Gemini models)
- Text embeddings
- Advanced ML capabilities

Supports both Vertex AI (recommended) and Gemini API (fallback).
"""

import os
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from config import (
    USE_VERTEX_AI,
    GCP_PROJECT_ID,
    GCP_LOCATION,
    VERTEX_AI_MODEL,
    VERTEX_AI_EMBEDDING_MODEL,
    GEMINI_API_KEY,
)

load_dotenv()

# Try to import Vertex AI, fallback to Gemini API if not available
try:
    import vertexai
    from vertexai.generative_models import GenerativeModel, Part
    from vertexai.language_models import TextEmbeddingModel
    VERTEX_AI_AVAILABLE = True
except ImportError:
    VERTEX_AI_AVAILABLE = False
    print("Warning: Vertex AI not available. Install with: pip install google-cloud-aiplatform vertexai")

# Fallback to Gemini API
try:
    import google.generativeai as genai
    GEMINI_API_AVAILABLE = True
except ImportError:
    GEMINI_API_AVAILABLE = False
    print("Warning: Google Generative AI not available.")


class VertexAIClient:
    """
    Client for interacting with Vertex AI models.
    Automatically falls back to Gemini API if Vertex AI is not configured.
    """
    
    def __init__(self):
        print(f"\n[VertexAIClient] __init__ called")
        print(f"   USE_VERTEX_AI: {USE_VERTEX_AI}")
        print(f"   VERTEX_AI_AVAILABLE: {VERTEX_AI_AVAILABLE}")
        print(f"   GCP_PROJECT_ID: {GCP_PROJECT_ID}")
        print(f"   GEMINI_API_KEY present: {bool(GEMINI_API_KEY)}")
        
        self.use_vertex_ai = USE_VERTEX_AI and VERTEX_AI_AVAILABLE and GCP_PROJECT_ID
        print(f"   Will use Vertex AI: {self.use_vertex_ai}")
        
        self.model = None
        self.embedding_model = None
        
        if self.use_vertex_ai:
            try:
                print(f"   Attempting to initialize Vertex AI...")
                # Initialize Vertex AI
                vertexai.init(project=GCP_PROJECT_ID, location=GCP_LOCATION)
                self.model = GenerativeModel(VERTEX_AI_MODEL)
                self.embedding_model = TextEmbeddingModel.from_pretrained(VERTEX_AI_EMBEDDING_MODEL)
                print(f"✅ Vertex AI initialized: Project={GCP_PROJECT_ID}, Location={GCP_LOCATION}")
                print(f"   Model: {VERTEX_AI_MODEL}, Embedding: {VERTEX_AI_EMBEDDING_MODEL}")
            except Exception as e:
                print(f"⚠️  Vertex AI initialization failed: {e}")
                print("   Falling back to Gemini API...")
                self.use_vertex_ai = False
                self._init_gemini_api()
        else:
            print(f"   Using Gemini API (USE_VERTEX_AI={USE_VERTEX_AI} or Vertex AI not configured)")
            self._init_gemini_api()
    
    def _init_gemini_api(self):
        """Initialize Gemini API as fallback. Uses cheapest model (gemini-1.5-flash) by default."""
        print(f"\n[VertexAIClient] Initializing Gemini API...")
        print(f"   GEMINI_API_AVAILABLE: {GEMINI_API_AVAILABLE}")
        print(f"   GEMINI_API_KEY present: {bool(GEMINI_API_KEY)}")
        if GEMINI_API_KEY:
            print(f"   GEMINI_API_KEY preview: {GEMINI_API_KEY[:10]}...{GEMINI_API_KEY[-5:]}")
        
        if GEMINI_API_AVAILABLE and GEMINI_API_KEY:
            try:
                print(f"   Configuring genai with API key...")
                genai.configure(api_key=GEMINI_API_KEY)
                print(f"   ✅ genai.configure() successful")
                
                # Use cheapest model for Gemini API: gemini-1.5-flash
                # This is perfect for transcript extraction and costs less
                # NOTE: For Gemini API Python SDK, use model name WITHOUT "models/" prefix
                model_name = VERTEX_AI_MODEL
                print(f"   VERTEX_AI_MODEL from config (raw): {model_name}")
                
                # FORCE remove "models/" prefix if present (Python SDK doesn't need it)
                if model_name.startswith("models/"):
                    model_name = model_name.replace("models/", "")
                    print(f"   ✅ Removed 'models/' prefix: {model_name}")
                
                # Ensure we use the cheapest AVAILABLE model for Gemini API
                # NOTE: gemini-1.5-flash models are RETIRED - use gemini-2.0-flash-lite-001 (cheapest) or gemini-2.0-flash-001
                expensive_models = ["gemini-2.0-flash-exp", "gemini-1.5-pro", "gemini-2.5-pro", "models/gemini-2.0-flash-exp", "models/gemini-1.5-pro"]
                retired_models = ["gemini-1.5-flash", "gemini-1.5-flash-001", "gemini-1.5-flash-002", "gemini-1.5-pro"]
                
                # Replace retired models or expensive models with cheapest available
                if model_name in expensive_models or model_name in retired_models or any(model_name.startswith(m.replace("models/", "")) for m in expensive_models + retired_models if "models/" in m):
                    # Use cheapest available model: gemini-2.0-flash-lite-001 (cheapest stable model)
                    model_name = "gemini-2.0-flash-lite-001"
                    print(f"💡 Overriding to cheapest available Gemini model: {model_name}")
                elif model_name.startswith("gemini-1.5"):
                    # All 1.5 models are retired - replace with 2.0 flash lite
                    model_name = "gemini-2.0-flash-lite-001"
                    print(f"💡 Replacing retired 1.5 model with: {model_name}")
                
                # FINAL CHECK: Ensure no "models/" prefix (critical for Python SDK)
                if model_name.startswith("models/"):
                    print(f"   ⚠️  WARNING: Model name still has 'models/' prefix! Removing...")
                    model_name = model_name.replace("models/", "")
                
                print(f"   🎯 FINAL model name (for Python SDK): '{model_name}'")
                print(f"   Creating GenerativeModel with: {model_name}")
                
                # CRITICAL: Pass model name WITHOUT "models/" prefix to Python SDK
                # The SDK will handle the API path internally
                self.model = genai.GenerativeModel(model_name)
                print(f"✅ Gemini API initialized successfully: {model_name}")
                print(f"   Model object type: {type(self.model)}")
            except Exception as e:
                print(f"⚠️  Gemini API initialization failed: {e}")
                print(f"   Error type: {type(e).__name__}")
                import traceback
                traceback.print_exc()
                # Try fallback models (without models/ prefix for Python SDK)
                # Use stable, available models (gemini-1.5 models are RETIRED)
                fallback_models = [
                    "gemini-2.0-flash-lite-001",  # Cheapest available
                    "gemini-2.0-flash-001",       # Stable alternative
                    "gemini-2.5-flash",           # Newest stable
                    "gemini-2.0-flash"            # Alias (if supported)
                ]
                fallback_success = False
                for fallback_model in fallback_models:
                    try:
                        print(f"   Trying fallback model: {fallback_model}")
                        self.model = genai.GenerativeModel(fallback_model)
                        print(f"✅ Using Gemini model (fallback): {fallback_model}")
                        fallback_success = True
                        break
                    except Exception as fallback_error:
                        print(f"   ❌ Fallback model {fallback_model} failed: {fallback_error}")
                        continue
                
                if not fallback_success:
                    print(f"❌ All fallback models failed")
                    self.model = None
        else:
            if not GEMINI_API_AVAILABLE:
                print("⚠️  GEMINI_API_AVAILABLE is False - google.generativeai not imported")
            if not GEMINI_API_KEY:
                print("⚠️  GEMINI_API_KEY is not set")
            print("⚠️  No AI model available. Set GEMINI_API_KEY or configure Vertex AI.")
    
    def generate_content(
        self, 
        prompt: str, 
        generation_config: Optional[Dict[str, Any]] = None,
        safety_settings: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Generate content using Vertex AI or Gemini API.
        
        Args:
            prompt: The input prompt
            generation_config: Optional generation configuration
            safety_settings: Optional safety settings
            
        Returns:
            Generated text response
        """
        if not self.model:
            raise ValueError("No AI model available. Please configure Vertex AI or Gemini API.")
        
        try:
            if self.use_vertex_ai:
                # Vertex AI generation
                config = generation_config or {
                    "temperature": 0.4,
                    "top_p": 0.95,
                    "top_k": 40,
                    "max_output_tokens": 8192,
                }
                response = self.model.generate_content(
                    prompt,
                    generation_config=config,
                    safety_settings=safety_settings
                )
                return response.text
            else:
                # Gemini API generation
                print(f"   [VertexAIClient] Calling Gemini API generate_content...")
                print(f"   [VertexAIClient] Model: {self.model}")
                response = self.model.generate_content(prompt)
                print(f"   [VertexAIClient] Response type: {type(response)}")
                print(f"   [VertexAIClient] Response object: {response}")
                
                # Handle different response formats
                if hasattr(response, 'text'):
                    result = response.text
                    print(f"   [VertexAIClient] Response.text length: {len(result)} chars")
                    print(f"   [VertexAIClient] Response.text preview: {result[:200]}...")
                elif hasattr(response, 'candidates') and len(response.candidates) > 0:
                    # Alternative response format
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'content'):
                        if hasattr(candidate.content, 'parts'):
                            result = candidate.content.parts[0].text
                        else:
                            result = str(candidate.content)
                    else:
                        result = str(candidate)
                    print(f"   [VertexAIClient] Extracted from candidates, length: {len(result)} chars")
                else:
                    result = str(response)
                    print(f"   [VertexAIClient] Converted response to string, length: {len(result)} chars")
                
                return result
        except Exception as e:
            print(f"❌ [VertexAIClient] Error generating content: {e}")
            print(f"   Error type: {type(e).__name__}")
            import traceback
            traceback.print_exc()
            raise
    
    def embed_text(self, text: str, task_type: str = "retrieval_document") -> List[float]:
        """
        Generate embeddings for text using Vertex AI or Gemini API.
        
        Args:
            text: Text to embed
            task_type: Task type for embeddings (retrieval_document, retrieval_query, etc.)
            
        Returns:
            List of embedding values
        """
        if self.use_vertex_ai and self.embedding_model:
            try:
                # Vertex AI embeddings
                embeddings = self.embedding_model.get_embeddings([text])
                return embeddings[0].values
            except Exception as e:
                print(f"Vertex AI embedding error: {e}, falling back to Gemini API...")
                return self._gemini_embed(text, task_type)
        else:
            return self._gemini_embed(text, task_type)
    
    def _gemini_embed(self, text: str, task_type: str) -> List[float]:
        """Fallback to Gemini API embeddings."""
        if not GEMINI_API_AVAILABLE or not GEMINI_API_KEY:
            raise ValueError("No embedding model available. Configure Vertex AI or Gemini API.")
        
        try:
            import google.generativeai as genai
            result = genai.embed_content(
                model="models/embedding-001",
                content=text,
                task_type=task_type
            )
            return result["embedding"]
        except Exception as e:
            print(f"Gemini API embedding error: {e}")
            raise
    
    def embed_documents(self, texts: List[str], task_type: str = "retrieval_document") -> List[List[float]]:
        """
        Generate embeddings for multiple documents.
        
        Args:
            texts: List of texts to embed
            task_type: Task type for embeddings
            
        Returns:
            List of embedding vectors
        """
        if self.use_vertex_ai and self.embedding_model:
            try:
                # Vertex AI batch embeddings
                embeddings = self.embedding_model.get_embeddings(texts)
                return [emb.values for emb in embeddings]
            except Exception as e:
                print(f"Vertex AI batch embedding error: {e}, falling back to individual calls...")
                return [self.embed_text(text, task_type) for text in texts]
        else:
            return [self.embed_text(text, task_type) for text in texts]
    
    def is_available(self) -> bool:
        """Check if AI models are available."""
        return self.model is not None


# Global client instance
_vertex_ai_client = None

def get_vertex_ai_client() -> VertexAIClient:
    """Get or create the global Vertex AI client instance."""
    global _vertex_ai_client
    if _vertex_ai_client is None:
        print(f"\n[get_vertex_ai_client] Creating new VertexAIClient instance...")
        _vertex_ai_client = VertexAIClient()
    else:
        print(f"\n[get_vertex_ai_client] Reusing existing VertexAIClient instance")
        # Verify the model is still valid
        if _vertex_ai_client.model:
            model_info = str(_vertex_ai_client.model)
            if "models/" in model_info and not _vertex_ai_client.use_vertex_ai:
                print(f"   ⚠️  WARNING: Model object has 'models/' prefix but using Gemini API!")
                print(f"   Model info: {model_info}")
    return _vertex_ai_client

def reset_vertex_ai_client():
    """Reset the global Vertex AI client instance (useful for testing/debugging)."""
    global _vertex_ai_client
    print(f"\n[reset_vertex_ai_client] Resetting global client instance...")
    _vertex_ai_client = None
    return get_vertex_ai_client()

