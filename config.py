"""
Configuration Module

Centralized configuration for the Leasap Backend application.
All environment variables and application constants are defined here.
"""

import os
from dotenv import load_dotenv
import httpx

load_dotenv()

# ============================================================================
# SUPABASE CONFIGURATION
# ============================================================================

# Supabase Storage bucket name for file uploads
BUCKET_NAME = "realtor-files"

# Supabase connection settings
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
DATABASE_URL = os.getenv("DATABASE_1_URL")  # PostgreSQL connection string
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# ============================================================================
# EMBEDDING CONFIGURATION
# ============================================================================

# Vector embedding dimensions (768 for textembedding-gecko models)
EMBED_DIM = 768

# ============================================================================
# TWILIO CONFIGURATION
# ============================================================================

# Default Twilio phone number for WhatsApp/SMS
TWILIO_PHONE_NUMBER = "whatsapp:+14155238886"

# Optional alert destinations for forwarding confirmations
FORWARDING_ALERT_NUMBER = os.getenv("FORWARDING_ALERT_NUMBER")
FORWARDING_ALERT_FROM_NUMBER = os.getenv("FORWARDING_ALERT_FROM_NUMBER")

# ============================================================================
# OAUTH & REDIRECT URLS
# ============================================================================

# Google OAuth redirect URI
REDIRECT_URI = "https://leasing-copilot-mvp.onrender.com/oauth2callback"

# ============================================================================
# FILE PATHS
# ============================================================================

# Google Calendar credentials file
CREDENTIALS_FILE = "gCalendar.json"
TOKEN_FILE = "token.pkl"

# ============================================================================
# HTTP CLIENT CONFIGURATION
# ============================================================================

# HTTP request timeout (25 seconds)
timeout = httpx.Timeout(25.0)

# ============================================================================
# RATE LIMITING
# ============================================================================

# Daily message limit per user
DAILY_LIMIT = 50

# Call forwarding toggle protection (requests per hour per user)
CALL_FORWARDING_RATE_LIMIT_PER_HOUR = int(os.getenv("CALL_FORWARDING_RATE_LIMIT_PER_HOUR", "10"))

# ============================================================================
# APPLICATION SETTINGS
# ============================================================================

# Default timezone for scheduling
DEFAULT_TIMEZONE = "Asia/Karachi"

# Working hours for appointment scheduling (24-hour format)
WORKING_HOURS = {"start": 8, "end": 21}  # 8 AM to 9 PM

# Appointment slot duration in minutes
SLOT_DURATION = 30

# ============================================================================
# ZILLOW INTEGRATION
# ============================================================================

# Zillow API base URL for property listings
ZILLOW_BASE_URL = "https://www.zillow.com/_sp/homes/for_sale/"

# Default map bounds for property search
DEFAULT_MAP_BOUNDS = {"west": -77.2, "east": -76.8, "south": 35.6, "north": 35.9}

# ============================================================================
# GOOGLE CALENDAR SETTINGS
# ============================================================================

# OAuth scopes for Google Calendar API
GOOGLE_CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]
SCOPES = ["https://www.googleapis.com/auth/calendar"]

# ============================================================================
# AI MODEL CONFIGURATION
# ============================================================================

# Embedding model name (HuggingFace model for fallback)
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-large-en-v1.5")

# LLM model name (Gemini model for fallback)
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "models/gemini-2.0-flash")

# ============================================================================
# VERTEX AI CONFIGURATION (Primary AI Platform)
# ============================================================================

# Enable/disable Vertex AI (default: true)
USE_VERTEX_AI = os.getenv("USE_VERTEX_AI", "true").lower() == "true"

# Google Cloud Platform project ID
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")

# GCP location/region (default: us-central1)
GCP_LOCATION = os.getenv("GCP_LOCATION", "us-central1")

# Vertex AI model name for text generation
# Options: gemini-2.0-flash-exp, gemini-1.5-pro, gemini-1.5-flash
VERTEX_AI_MODEL = os.getenv("VERTEX_AI_MODEL", "gemini-2.0-flash-exp")

# Vertex AI embedding model name
VERTEX_AI_EMBEDDING_MODEL = os.getenv("VERTEX_AI_EMBEDDING_MODEL", "textembedding-gecko@003")

# ============================================================================
# GEMINI API CONFIGURATION (Fallback)
# ============================================================================

# Gemini API key (used as fallback if Vertex AI is not configured)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# ============================================================================
# TEXT PROCESSING CONFIGURATION
# ============================================================================

# Chunk size for text splitting (characters)
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 800))

# Chunk overlap for text splitting (characters)
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 50))
