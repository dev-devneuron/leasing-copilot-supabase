import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date
import httpx

load_dotenv()

TWILIO_PHONE_NUMBER = "whatsapp:+14155238886"
# ========================================
# API Keys and URLs
# ========================================

REDIRECT_URI = "https://d7ca733b5209.ngrok-free.app/oauth2callback"
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
LIMIT_FILE="messageLimits.json"
DAILY_LIMIT= 50

# FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", "faiss_index/index/index")
# GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS", "voice/gcloudSTT.json")

# Use config for interrupt keywords
# INTERRUPT_KEYWORDS = ["cancel", "start over", "main menu", "restart", "new request"]


# ========================================
# Application Settings
# ========================================
# DAILY_LIMIT = int(os.getenv("DAILY_LIMIT", 100))
DEFAULT_TIMEZONE = "Asia/Karachi"
WORKING_HOURS = {
     "start": 8,  # 8 AM
     "end": 21    # 9 PM
 }
SLOT_DURATION = 30  # minutes

# ========================================
# Questions and Prompts
# ========================================
# PREFERENCE_QUESTIONS = [
#     [("state", "Which City and State are you interested in?")],
#     [("bedrooms", "Minimum bedrooms you need?")],
#     [("bathrooms", "Minimum bathrooms you need?")],
#     [("budget", "What's your maximum budget in dollars?")],
#     [("square_feet", "What minimum size in square feet are you looking for?")],
# ]

# BOOKING_QUESTIONS = [
#     [("name", "What's your full name?")],
#     [("email", "What's your email address?")],
#     [("address", "What is the address of apartment you'd like to visit?")],
#     [("date", "What date would you like to schedule the visit?")],
#     [("time", "What time works best for you? (Format: HH:MM AM/PM)")],
# ]

# SCREENING_QUESTIONS = [
#     [("income", "What is your estimated yearly income? (in USD)")],
#     [("credit_score", "What is your current credit score?")],
#     [("move_in_date", "When are you planning to move in? (Format: YYYY-MM-DD)")],
# ]

# ========================================
# Intent Classification Settings
# ========================================
# INTENT_CLASSIFIER_METHOD = "gemini"  # "gemini", "llama"

# ========================================
# System Prompts
# ========================================
# SYSTEM_PROMPT_TEMPLATE = """
# You are a friendly, helpful assistant that answers questions about apartment listings and lease policies during a phone conversation.

# Your goals:
# - Respond naturally, politely, and conversationally.
# - Provide only information strictly based on the provided data. Do not invent or assume any details beyond what is given.
# - When given apartment preferences, suggest the best available matches strictly from the data. If city does not exactly match, show similar options in the same state if available.
# - Never generate apartment details or information that is not explicitly present in the given data.
# - If the status of an apartment is "sold", clearly mention that it is sold in your response. Then, provide 2 to 3 available (active status) apartments in the same state.
# - For general questions about lease rules or apartment listings, answer strictly based on the provided lease rules text or data. If unrelated or unknown, respond with exactly: "I don't know."

# Apartment Data:
# {apartment_data}

# Lease Rules:
# {lease_rules}

# Always format apartment information exactly like this:

# Apartment 1:
# - Address: [address]
# - City: [city]
# - State: [state]
# - Price: [price]
# - Bedrooms: [bedrooms]
# - Bathrooms: [bathrooms]
# - Size: [square feet]
# - Status: [status]

# Apartment 2:
# - ...

# If you don't have the requested information, say: "I'm sorry, I don't have that information right now." Keep your replies clear, friendly, and natural — avoid overly technical or robotic language.
# """

# ========================================
# Zillow URL Settings
# ========================================
ZILLOW_BASE_URL = "https://www.zillow.com/_sp/homes/for_sale/"
DEFAULT_MAP_BOUNDS = {
    "west": -77.2,
    "east": -76.8,
    "south": 35.6,
    "north": 35.9
}


# class LeadQualification(BaseModel):
#      monthly_income: int = Field(..., description="Monthly income in USD")
#      credit_score: int = Field(..., ge=300, le=850, description="Credit score between 300 and 850")
#      move_in_date: Optional[date] = Field(None, description="Preferred move-in date")


# ========================================
# Google Calendar Settings
# ========================================
GOOGLE_CALENDAR_SCOPES = ['https://www.googleapis.com/auth/calendar']

# Model names
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-large-en-v1.5")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "models/gemini-2.0-flash")

# Other constants (add as needed)
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 800))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 50)) 