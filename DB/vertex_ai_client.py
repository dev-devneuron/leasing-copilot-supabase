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
        self.use_vertex_ai = USE_VERTEX_AI and VERTEX_AI_AVAILABLE and GCP_PROJECT_ID
        self.model = None
        self.embedding_model = None
        
        if self.use_vertex_ai:
            try:
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
            self._init_gemini_api()
    
    def _init_gemini_api(self):
        """Initialize Gemini API as fallback."""
        if GEMINI_API_AVAILABLE and GEMINI_API_KEY:
            try:
                genai.configure(api_key=GEMINI_API_KEY)
                # Convert Vertex AI model name to Gemini API format
                model_name = VERTEX_AI_MODEL
                if not model_name.startswith("models/"):
                    if model_name.startswith("gemini-"):
                        model_name = f"models/{model_name}"
                    else:
                        model_name = f"models/{model_name}"
                self.model = genai.GenerativeModel(model_name)
                print(f"✅ Using Gemini API (fallback): {model_name}")
            except Exception as e:
                print(f"⚠️  Gemini API initialization failed: {e}")
                # Try default model
                try:
                    self.model = genai.GenerativeModel("models/gemini-2.0-flash-exp")
                    print("✅ Using default Gemini model: models/gemini-2.0-flash-exp")
                except:
                    self.model = None
        else:
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
                response = self.model.generate_content(prompt)
                return response.text
        except Exception as e:
            print(f"Error generating content: {e}")
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
        _vertex_ai_client = VertexAIClient()
    return _vertex_ai_client

