import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date
import httpx

load_dotenv()


# ---------------------------------------------------------------------
#                    SUPABASE CONFIG
# ---------------------------------------------------------------------
BUCKET_NAME = "realtor-files"

# for bucket collection
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
DATABASE_URL = os.getenv("DATABASE_1_URL")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
# --------------------------------------------------------------------

# Embedding dimensions
EMBED_DIM = 768


TWILIO_PHONE_NUMBER = "whatsapp:+14155238886"
# ========================================
# API Keys and URLs
# ========================================

REDIRECT_URI = "https://leasing-copilot-mvp.onrender.com/oauth2callback"
# ========================================
# File Paths
# ========================================
CREDENTIALS_FILE = "gCalendar.json"
TOKEN_FILE = "token.pkl"
LIMIT_FILE = "messageLimits.json"
RULES_FILE = os.getenv("RULES_FILE", "Rules.txt")
DATA_FILE = os.getenv("DATA_FILE", "data.json")
CHAT_SESSIONS_FILE = "chat_session.json"
timeout = httpx.Timeout(25.0)
LIMIT_FILE = "messageLimits.json"
DAILY_LIMIT = 50


# ========================================
# Application Settings
# ========================================
DEFAULT_TIMEZONE = "Asia/Karachi"
WORKING_HOURS = {"start": 8, "end": 21}  # 8 AM  # 9 PM
SLOT_DURATION = 30  # minutes


# ========================================
# Zillow URL Settings
# ========================================
ZILLOW_BASE_URL = "https://www.zillow.com/_sp/homes/for_sale/"
DEFAULT_MAP_BOUNDS = {"west": -77.2, "east": -76.8, "south": 35.6, "north": 35.9}


# ========================================
# Google Calendar Settings
# ========================================
GOOGLE_CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]
SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Model names
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-large-en-v1.5")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "models/gemini-2.0-flash")

# Other constants (add as needed)
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 800))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 50))
