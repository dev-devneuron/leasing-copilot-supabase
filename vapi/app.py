"""
FastAPI Application - Main API Server

This module contains all API endpoints for:
- User authentication and profile management
- Property Manager and Realtor management
- Property listing uploads and management
- Phone number request and assignment system
- Demo booking system
- VAPI chatbot integration
- RAG (Retrieval Augmented Generation) for apartment search
"""

from fastapi import (
    FastAPI,
    HTTPException,
    Form,
    Request,
    File,
    UploadFile,
    Depends,
    Header,
    Body,
)
from fastapi.responses import (
    JSONResponse,
    FileResponse,
    RedirectResponse,
    Response,
    PlainTextResponse,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
import re
import uuid
from typing import Union, Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager
import json
import os
import jwt
import numpy as np
import httpx
from httpx import TimeoutException
from dotenv import load_dotenv
from google_auth_oauthlib.flow import Flow
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from sqlmodel import select, Session
from sqlalchemy import update, func, or_, and_
from sqlalchemy.orm.attributes import flag_modified

# Local imports
from DB.db import *
from DB.sync import sync_apartment_listings
from utils.calendar_utils import GoogleCalendar
from utils.auth_module import get_current_realtor_id, get_current_user_data
from vapi.rag import RAGEngine
from vapi.bounded_usage import MessageLimiter
from config import (
    CREDENTIALS_FILE,
    REDIRECT_URI,
    timeout,
    DAILY_LIMIT,
    TWILIO_PHONE_NUMBER,
    SCOPES,
    CALL_FORWARDING_RATE_LIMIT_PER_HOUR,
    FORWARDING_ALERT_NUMBER,
    FORWARDING_ALERT_FROM_NUMBER,
)

load_dotenv()

# ============================================================================
# FASTAPI APPLICATION INITIALIZATION
# ============================================================================

# Lifespan context manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown."""
    try:
        init_db()
        print("✅ Database initialized successfully")
    except Exception as e:
        print(f"⚠️ Database initialization failed: {e}")
        print("⚠️ Continuing without database connection...")
    
    yield  # Application runs here
    
    print("Shutting down FastAPI app...")

# CORS allowed origins
origins = [
    "https://react-app-form.onrender.com",
    "https://leaseap.com",
    "https://www.leasap.com",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:8080",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:8080",
]

# Create FastAPI application with lifespan
app = FastAPI(
    title="Leasap Backend API",
    description="Backend API for Leasap property management platform",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

# ============================================================================
# VAPI & TWILIO CONFIGURATION
# ============================================================================

# Primary VAPI/Twilio credentials
VAPI_API_KEY = os.getenv("VAPI_API_KEY")
VAPI_ASSISTANT_ID = os.getenv("VAPI_ASSISTANT_ID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
VAPI_BASE_URL = "https://api.vapi.ai"
headers = {"Authorization": f"Bearer {VAPI_API_KEY}"} if VAPI_API_KEY else {}

# Secondary VAPI/Twilio credentials (for phone number purchasing)
TWILIO_ACCOUNT_SID2 = os.getenv("TWILIO_ACCOUNT_SID2")
TWILIO_ACCOUNT_SID1 = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN2 = os.getenv("TWILIO_AUTH_TOKEN2")
TWILIO_AUTH_TOKEN1 = os.getenv("TWILIO_AUTH_TOKEN")
VAPI_API_KEY2 = os.getenv("VAPI_API_KEY2")
VAPI_ASSISTANT_ID2 = os.getenv("VAPI_ASSISTANT_ID2")

# Initialize Twilio clients (will be None if credentials not set)
twillio_client = None
twillio_client1 = None

if TWILIO_ACCOUNT_SID2 and TWILIO_AUTH_TOKEN2:
    try:
        twillio_client = Client(TWILIO_ACCOUNT_SID2, TWILIO_AUTH_TOKEN2)
        print("✅ Twilio client 2 initialized")
    except Exception as e:
        print(f"⚠️  Failed to initialize Twilio client 2: {e}")

if TWILIO_ACCOUNT_SID1 and TWILIO_AUTH_TOKEN1:
    try:
        twillio_client1 = Client(TWILIO_ACCOUNT_SID1, TWILIO_AUTH_TOKEN1)
        print("✅ Twilio client 1 initialized")
    except Exception as e:
        print(f"⚠️  Failed to initialize Twilio client 1: {e}")

# Supported carriers for call forwarding
CALL_FORWARDING_CARRIERS = [
    "AT&T",
    "T-Mobile", 
    "Mint",
    "Metro",
    "Verizon",
    "Xfinity Mobile",
    "Google Fi",
    "Consumer Cellular",
    "Ultra Mobile"
]

# Carrier code mapping - maps carrier names to their forwarding code formats
CARRIER_CODES = {
    # GSM-based carriers (support **21, **61, **25# format)
    "AT&T": {
        "type": "gsm",
        "forward_all": {
            "activate": "**21*{number}#",
            "deactivate": "##21#",
            "check": "*#21#"
        },
        "forward_no_answer": {
            "activate": "**61*{number}**25#",
            "deactivate": "##61#",
            "check": "*#61#",
            "supports_custom_seconds": True
        }
    },
    "T-Mobile": {
        "type": "gsm",
        "forward_all": {
            "activate": "**21*{number}#",
            "deactivate": "##21#",
            "check": "*#21#"
        },
        "forward_no_answer": {
            "activate": "**61*{number}**25#",
            "deactivate": "##61#",
            "check": "*#61#",
            "supports_custom_seconds": True
        }
    },
    "Mint": {
        "type": "gsm",
        "forward_all": {
            "activate": "**21*{number}#",
            "deactivate": "##21#",
            "check": "*#21#"
        },
        "forward_no_answer": {
            "activate": "**61*{number}**25#",
            "deactivate": "##61#",
            "check": "*#61#",
            "supports_custom_seconds": True
        }
    },
    "Metro": {
        "type": "gsm",
        "forward_all": {
            "activate": "**21*{number}#",
            "deactivate": "##21#",
            "check": "*#21#"
        },
        "forward_no_answer": {
            "activate": "**61*{number}**25#",
            "deactivate": "##61#",
            "check": "*#61#",
            "supports_custom_seconds": True
        }
    },
    "Consumer Cellular": {
        "type": "gsm",
        "forward_all": {
            "activate": "**21*{number}#",
            "deactivate": "##21#",
            "check": "*#21#"
        },
        "forward_no_answer": {
            "activate": "**61*{number}**25#",
            "deactivate": "##61#",
            "check": "*#61#",
            "supports_custom_seconds": True
        }
    },
    "Ultra Mobile": {
        "type": "gsm",
        "forward_all": {
            "activate": "**21*{number}#",
            "deactivate": "##21#",
            "check": "*#21#"
        },
        "forward_no_answer": {
            "activate": "**61*{number}**25#",
            "deactivate": "##61#",
            "check": "*#61#",
            "supports_custom_seconds": True
        }
    },
    # Verizon (uses *72/*73 format, no 25-second support)
    "Verizon": {
        "type": "verizon",
        "forward_all": {
            "activate": "*72 {number}",
            "deactivate": "*73",
            "check": None  # No check code available
        },
        "forward_no_answer": {
            "activate": None,  # Not supported
            "deactivate": None,
            "check": None,
            "supports_custom_seconds": False
        }
    },
    # Xfinity Mobile (uses *72/*73/*71 format, no 25-second support)
    "Xfinity Mobile": {
        "type": "xfinity",
        "forward_all": {
            "activate": "*72 {number}",
            "deactivate": "*73",
            "check": None
        },
        "forward_no_answer": {
            "activate": "*71 {number}",  # No-answer forwarding (default ring time, no custom seconds)
            "deactivate": "*73",
            "check": None,
            "supports_custom_seconds": False
        }
    },
    # Google Fi (app-only, no GSM codes)
    "Google Fi": {
        "type": "google_fi",
        "forward_all": {
            "activate": "app_only",  # Must use Google Fi app/website
            "deactivate": "app_only",
            "check": "app_only"
        },
        "forward_no_answer": {
            "activate": None,  # Not supported
            "deactivate": None,
            "check": None,
            "supports_custom_seconds": False
        }
    }
}

BOT_NUMBER_REGEX = re.compile(r"^\+1\d{10}$")

# ============================================================================
# GLOBAL SERVICES
# ============================================================================

# RAG Engine for semantic search
rag = RAGEngine()

# Message limiter for rate limiting
message_limiter = MessageLimiter(DAILY_LIMIT)

# Database session (legacy - prefer using SessionLocal in endpoints)
session = Session(engine)


# ------------------ ToolCall Models ------------------ #
class ToolCallFunction(BaseModel):
    name: str
    arguments: Union[str, dict]


class ToolCall(BaseModel):
    id: str
    function: ToolCallFunction


class Message(BaseModel):
    toolCalls: list[ToolCall]


class VapiRequest(BaseModel):
    """Request model for VAPI webhook calls."""
    message: Message


class UnassignPhoneNumberRequest(BaseModel):
    """Request model for unassigning a phone number."""
    purchased_phone_number_id: int


class CallForwardingStateUpdate(BaseModel):
    """Request model for updating call forwarding state."""
    after_hours_enabled: Optional[bool] = None
    business_forwarding_enabled: Optional[bool] = None
    realtor_id: Optional[int] = None  # Only allowed for PMs
    carrier: Optional[str] = None  # User's mobile carrier (e.g., "AT&T", "Verizon", "T-Mobile")
    notes: Optional[str] = None
    confirmation_status: Optional[str] = None  # "success", "failure", "pending"
    failure_reason: Optional[str] = None


def _get_carrier_forwarding_codes(carrier: Optional[str], bot_number: Optional[str]) -> Dict[str, Any]:
    """
    Get carrier-specific forwarding codes for a given carrier and bot number.
    
    Returns a dictionary with:
    - forward_all: {activate, deactivate, check}
    - forward_no_answer: {activate, deactivate, check, supports_custom_seconds}
    - carrier_type: "gsm", "verizon", "xfinity", "google_fi"
    - supports_25_second_forwarding: bool
    """
    if not carrier or carrier not in CARRIER_CODES:
        # Default to AT&T (GSM) if carrier not specified or unknown
        carrier = "AT&T"
    
    carrier_config = CARRIER_CODES[carrier]
    
    # If no bot_number provided, return null codes (don't generate invalid codes)
    if not bot_number:
        return {
            "carrier": carrier,
            "carrier_type": carrier_config["type"],
            "forward_all": {
                "activate": None,
                "deactivate": None,
                "check": None
            },
            "forward_no_answer": {
                "activate": None,
                "deactivate": None,
                "check": None,
                "supports_custom_seconds": carrier_config.get("forward_no_answer", {}).get("supports_custom_seconds", False)
            },
            "supports_25_second_forwarding": carrier_config.get("forward_no_answer", {}).get("supports_custom_seconds", False)
        }
    
    # For Verizon/Xfinity, remove + and format with space; for GSM, keep + and format
    if carrier in ["Verizon", "Xfinity Mobile"]:
        bot_number_clean = bot_number.replace("+", "").replace(" ", "").replace("-", "")
    else:
        bot_number_clean = bot_number
    
    codes = {
        "carrier": carrier,
        "carrier_type": carrier_config["type"],
        "forward_all": {},
        "forward_no_answer": {},
        "supports_25_second_forwarding": carrier_config.get("forward_no_answer", {}).get("supports_custom_seconds", False)
    }
    
    # Generate forward all codes
    forward_all_config = carrier_config.get("forward_all", {})
    if forward_all_config.get("activate"):
        if forward_all_config["activate"] == "app_only":
            codes["forward_all"]["activate"] = "app_only"
            codes["forward_all"]["instructions"] = "Use Google Fi app or website to set up call forwarding"
        else:
            codes["forward_all"]["activate"] = forward_all_config["activate"].format(number=bot_number_clean)
    else:
        codes["forward_all"]["activate"] = None
    
    codes["forward_all"]["deactivate"] = forward_all_config.get("deactivate")
    codes["forward_all"]["check"] = forward_all_config.get("check")
    
    # Generate forward no-answer codes
    forward_no_answer_config = carrier_config.get("forward_no_answer", {})
    if forward_no_answer_config.get("activate"):
        codes["forward_no_answer"]["activate"] = forward_no_answer_config["activate"].format(number=bot_number_clean)
    else:
        codes["forward_no_answer"]["activate"] = None
    
    codes["forward_no_answer"]["deactivate"] = forward_no_answer_config.get("deactivate")
    codes["forward_no_answer"]["check"] = forward_no_answer_config.get("check")
    codes["forward_no_answer"]["supports_custom_seconds"] = forward_no_answer_config.get("supports_custom_seconds", False)
    
    return codes


def _serialize_forwarding_state(user_record) -> Dict[str, Optional[Union[bool, str]]]:
    """Normalize forwarding state for JSON responses."""
    if not user_record:
        return {
            "carrier": None,
            "business_forwarding_enabled": False,
            "after_hours_enabled": False,
            "last_after_hours_update": None,
            "business_forwarding_active": False,
            "after_hours_active": False,
            "last_forwarding_update": None,
            "business_forwarding_confirmed_at": None,
            "after_hours_last_enabled_at": None,
            "after_hours_last_disabled_at": None,
            "forwarding_failure_reason": None,
        }
    last_update = getattr(user_record, "last_forwarding_update", None) or getattr(
        user_record, "last_after_hours_update", None
    )
    state = {
        "carrier": getattr(user_record, "carrier", None),
        "business_forwarding_enabled": bool(getattr(user_record, "business_forwarding_enabled", False)),
        "after_hours_enabled": bool(getattr(user_record, "after_hours_enabled", False)),
        "last_after_hours_update": getattr(user_record, "last_after_hours_update", None).isoformat()
        if getattr(user_record, "last_after_hours_update", None)
        else None,
        "business_forwarding_confirmed_at": getattr(user_record, "business_forwarding_confirmed_at", None).isoformat()
        if getattr(user_record, "business_forwarding_confirmed_at", None)
        else None,
        "after_hours_last_enabled_at": getattr(user_record, "after_hours_last_enabled_at", None).isoformat()
        if getattr(user_record, "after_hours_last_enabled_at", None)
        else None,
        "after_hours_last_disabled_at": getattr(user_record, "after_hours_last_disabled_at", None).isoformat()
        if getattr(user_record, "after_hours_last_disabled_at", None)
        else None,
        "forwarding_failure_reason": getattr(user_record, "forwarding_failure_reason", None),
        "last_forwarding_update": last_update.isoformat() if last_update else None,
    }
    state["business_forwarding_active"] = state["business_forwarding_enabled"]
    state["after_hours_active"] = state["after_hours_enabled"]
    return state


def _reset_forwarding_state(user_record):
    """Reset forwarding flags when numbers change."""
    if not user_record:
        return
    user_record.business_forwarding_enabled = False
    user_record.after_hours_enabled = False
    user_record.last_after_hours_update = None
    user_record.business_forwarding_confirmed_at = None
    user_record.after_hours_last_enabled_at = None
    user_record.after_hours_last_disabled_at = None
    user_record.forwarding_failure_reason = None
    user_record.last_forwarding_update = None


def _normalize_bot_number(number: Optional[Union[str, Dict[str, Any], int, float]]) -> Optional[str]:
    """Normalize phone number to E.164 format (+1XXXXXXXXXX)."""
    if number is None:
        return None
    
    original = number
    
    # Handle objects VAPI might send (dict with number fields)
    if isinstance(number, dict):
        candidate_keys = [
            "number",
            "phoneNumber",
            "value",
            "phone",
            "phone_number",
            "formatted",
            "formattedNumber",
        ]
        for key in candidate_keys:
            value = number.get(key)
            if isinstance(value, str) and value.strip():
                number = value
                break
        else:
            # Fallback to id or first non-empty string
            fallback = number.get("id") or number.get("sid")
            if isinstance(fallback, str):
                number = fallback
            else:
                # Unable to extract string - log and return None
                print(f"⚠️  _normalize_bot_number received dict without string value: {number}")
                return None
    
    # Convert non-string primitives
    if isinstance(number, (int, float)):
        number = str(int(number))
    
    if not isinstance(number, str):
        print(f"⚠️  _normalize_bot_number received unsupported type {type(original)}")
        return None
    
    stripped = number.strip()
    if not stripped or stripped.upper() == "TBD":
        return None
    
    # Remove all non-digit characters except leading +
    # This handles formats like "+1 (412) 388-2328" -> "+14123882328"
    if stripped.startswith("+1"):
        # Keep +1, then extract only digits
        digits = "".join(filter(str.isdigit, stripped[2:]))
        if len(digits) == 10:
            return f"+1{digits}"
        # If it's already in the right format, return as-is
        if len(stripped) == 12 and stripped.startswith("+1") and stripped[2:].isdigit():
            return stripped
    
    # Fallback: try to extract +1 and 10 digits from anywhere in the string
    import re
    match = re.search(r'\+1(\d{10})', stripped.replace(" ", "").replace("-", "").replace("(", "").replace(")", ""))
    if match:
        return f"+1{match.group(1)}"
    
    # If no +1 found but has 10 digits, assume US number
    digits_only = "".join(filter(str.isdigit, stripped))
    if len(digits_only) == 10:
        return f"+1{digits_only}"
    if len(digits_only) == 11 and digits_only.startswith("1"):
        return f"+{digits_only}"
    
    # Return as-is if we can't normalize (let validation catch it)
    return stripped


def _extract_caller_number(
    payload: Optional[Dict[str, Any]] = None,
    message: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    """Best-effort extraction of the caller's phone number from VAPI payloads or headers."""
    
    def _clean(value: Any) -> Optional[str]:
        if not value:
            return None
        if isinstance(value, dict):
            candidate_keys = [
                "phoneNumber",
                "number",
                "phone",
                "contactNumber",
                "contact_number",
                "value",
                "formatted",
            ]
            for key in candidate_keys:
                candidate = value.get(key)
                cleaned = _clean(candidate)
                if cleaned:
                    return cleaned
            # Look into nested contact/customer nodes
            for nested_key in ["contact", "customer", "details"]:
                cleaned = _clean(value.get(nested_key))
                if cleaned:
                    return cleaned
            return None
        if isinstance(value, list):
            for item in value:
                cleaned = _clean(item)
                if cleaned:
                    return cleaned
            return None
        if isinstance(value, (int, float)):
            value = str(int(value))
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return None
    
    candidate_values: list[Any] = []
    
    def _collect(source: Optional[Dict[str, Any]]):
        if not isinstance(source, dict):
            return
        candidate_values.extend([
            source.get("fromNumber"),
            source.get("from"),
            source.get("callerNumber"),
            source.get("customerNumber"),
            source.get("customerPhoneNumber"),
        ])
        call_obj = source.get("call")
        if isinstance(call_obj, dict):
            candidate_values.extend([
                call_obj.get("fromNumber"),
                call_obj.get("from"),
                call_obj.get("callerNumber"),
                call_obj.get("customerPhoneNumber"),
                call_obj.get("customer", {}).get("phoneNumber") if isinstance(call_obj.get("customer"), dict) else None,
            ])
        customer_obj = source.get("customer")
        if isinstance(customer_obj, dict):
            candidate_values.extend([
                customer_obj.get("phoneNumber"),
                customer_obj.get("phone"),
                customer_obj.get("number"),
                customer_obj.get("contactNumber"),
            ])
            contact_obj = customer_obj.get("contact")
            if isinstance(contact_obj, dict):
                candidate_values.extend([
                    contact_obj.get("phone"),
                    contact_obj.get("phoneNumber"),
                    contact_obj.get("number"),
                    contact_obj.get("mobile"),
                ])
        twilio_obj = source.get("twilio")
        if isinstance(twilio_obj, dict):
            candidate_values.extend([
                twilio_obj.get("from"),
                twilio_obj.get("From"),
            ])
    
    _collect(payload)
    _collect(message)
    
    if headers:
        candidate_values.extend([
            headers.get("x-vapi-from"),
            headers.get("x-vapi-caller"),
            headers.get("x-forwarded-from"),
        ])
    
    for value in candidate_values:
        cleaned = _clean(value)
        if cleaned:
            return cleaned
    return None


def _get_or_sync_twilio_number(session: Session, user_record):
    """Ensure user record has a valid Twilio number, falling back to assigned purchased numbers."""
    purchased_id = getattr(user_record, "purchased_phone_number_id", None)
    purchased = session.get(PurchasedPhoneNumber, purchased_id) if purchased_id else None

    if isinstance(user_record, PropertyManager):
        assigned_type = "property_manager"
        target_id = user_record.property_manager_id
        pm_id = user_record.property_manager_id
    else:
        assigned_type = "realtor"
        target_id = user_record.realtor_id
        pm_id = user_record.property_manager_id

    def _lookup_assigned_number():
        # First, try a simple direct lookup by assigned_to_id and property_manager_id
        # This matches what the frontend sees in /purchased-phone-numbers
        query = select(PurchasedPhoneNumber).where(
            PurchasedPhoneNumber.property_manager_id == pm_id,
            PurchasedPhoneNumber.assigned_to_id == target_id
        )
        
        # Try multiple variations of assigned_to_type matching
        # Handle: "property_manager", "Property Manager", "PROPERTY_MANAGER", etc.
        type_conditions = [
            func.lower(func.coalesce(PurchasedPhoneNumber.assigned_to_type, "")) == assigned_type,
            func.replace(func.lower(func.coalesce(PurchasedPhoneNumber.assigned_to_type, "")), " ", "_") == assigned_type,
            func.replace(func.lower(func.coalesce(PurchasedPhoneNumber.assigned_to_type, "")), "_", " ") == assigned_type.replace("_", " "),
        ]
        
        # Also try exact match (case-sensitive) in case it's stored correctly
        if assigned_type == "property_manager":
            type_conditions.extend([
                PurchasedPhoneNumber.assigned_to_type == "property_manager",
                PurchasedPhoneNumber.assigned_to_type == "Property Manager",
            ])
        elif assigned_type == "realtor":
            type_conditions.extend([
                PurchasedPhoneNumber.assigned_to_type == "realtor",
                PurchasedPhoneNumber.assigned_to_type == "Realtor",
            ])
        
        query = query.where(or_(*type_conditions))
        
        result = session.exec(query.order_by(PurchasedPhoneNumber.assigned_at.desc())).first()
        
        # CRITICAL: For realtors, verify the result is actually assigned to THIS realtor
        # and not accidentally matching a PM's number
        if result and assigned_type == "realtor":
            # Double-check: ensure assigned_to_id matches the realtor_id, not PM_id
            if result.assigned_to_id != target_id:
                print(f"⚠️  WARNING: Found number {result.phone_number} but assigned_to_id {result.assigned_to_id} doesn't match realtor_id {target_id}")
                return None
            # Ensure it's not assigned to PM
            if result.assigned_to_type and "manager" in result.assigned_to_type.lower():
                print(f"⚠️  WARNING: Found number {result.phone_number} but it's assigned to PM, not realtor")
                return None
        
        # Debug logging
        if isinstance(user_record, PropertyManager):
            all_pm_numbers = session.exec(
                select(PurchasedPhoneNumber)
                .where(PurchasedPhoneNumber.property_manager_id == pm_id)
            ).all()
            print(f"🔍 DEBUG _lookup_assigned_number for PM {pm_id}:")
            print(f"  - Looking for assigned_to_id={target_id}, assigned_to_type={assigned_type}")
            print(f"  - Found {len(all_pm_numbers)} total numbers in PM inventory")
            for pn in all_pm_numbers:
                print(f"    * {pn.phone_number}: assigned_to_type='{pn.assigned_to_type}', assigned_to_id={pn.assigned_to_id}, status={pn.status}")
            if result:
                print(f"  ✅ Found matching number: {result.phone_number}")
            else:
                print(f"  ❌ No matching number found")
        elif isinstance(user_record, Realtor):
            print(f"🔍 DEBUG _lookup_assigned_number for Realtor {target_id}:")
            print(f"  - Looking for assigned_to_id={target_id}, assigned_to_type={assigned_type}")
            if result:
                print(f"  ✅ Found matching number: {result.phone_number} (assigned_to_id={result.assigned_to_id}, assigned_to_type='{result.assigned_to_type}')")
            else:
                print(f"  ❌ No matching number found for realtor")
        
        return result

    if not purchased:
        purchased = _lookup_assigned_number()
    
    # Fallback: If still not found, try a very lenient lookup - just find ANY number
    # assigned to this PM/realtor (ignore assigned_to_type format issues)
    # IMPORTANT: Only do this for PMs, NOT for realtors (realtors must have explicit assignment)
    if not purchased and isinstance(user_record, PropertyManager):
        print(f"🔍 DEBUG: Trying lenient fallback for PM {pm_id}")
        purchased = session.exec(
            select(PurchasedPhoneNumber)
            .where(PurchasedPhoneNumber.property_manager_id == pm_id)
            .where(PurchasedPhoneNumber.assigned_to_id == target_id)
            .where(PurchasedPhoneNumber.assigned_to_type.isnot(None))
            .order_by(PurchasedPhoneNumber.assigned_at.desc())
        ).first()
        if purchased:
            # Verify it's actually assigned to PM, not a realtor
            if purchased.assigned_to_type and "realtor" in purchased.assigned_to_type.lower():
                print(f"  ⚠️  Lenient fallback found number assigned to realtor, skipping for PM")
                purchased = None
            else:
                print(f"  ✅ Lenient fallback found: {purchased.phone_number} (assigned_to_type='{purchased.assigned_to_type}')")

    # If the PM never explicitly assigned the bot number to themselves,
    # auto-promote the oldest number they own so the dashboard always has a callbot DID.
    if not purchased and isinstance(user_record, PropertyManager):
        purchased = session.exec(
            select(PurchasedPhoneNumber)
            .where(PurchasedPhoneNumber.property_manager_id == user_record.property_manager_id)
            .where(
                or_(
                    PurchasedPhoneNumber.assigned_to_type.is_(None),
                    PurchasedPhoneNumber.assigned_to_type == "property_manager",
                )
            )
            .order_by(
                PurchasedPhoneNumber.assigned_at.asc().nulls_last(),
                PurchasedPhoneNumber.purchased_at.asc(),
            )
        ).first()

        if purchased:
            purchased.assigned_to_type = "property_manager"
            purchased.assigned_to_id = user_record.property_manager_id
            purchased.status = "assigned"
            purchased.assigned_at = datetime.utcnow()

    if not purchased:
        return None

    fallback_number = _normalize_bot_number(purchased.phone_number)
    if not fallback_number:
        print(f"⚠️  DEBUG: Could not normalize phone number '{purchased.phone_number}' for PM {pm_id if isinstance(user_record, PropertyManager) else 'Realtor'}")
        return None
    if not BOT_NUMBER_REGEX.match(fallback_number):
        print(f"⚠️  DEBUG: Normalized number '{fallback_number}' (from '{purchased.phone_number}') does not match E.164 regex for PM {pm_id if isinstance(user_record, PropertyManager) else 'Realtor'}")
        return None
    print(f"✅ DEBUG: Successfully normalized and validated number '{fallback_number}' for PM {pm_id if isinstance(user_record, PropertyManager) else 'Realtor'}")

    updated = False

    if user_record.purchased_phone_number_id != purchased.purchased_phone_number_id:
        user_record.purchased_phone_number_id = purchased.purchased_phone_number_id
        updated = True

    if user_record.twilio_contact != fallback_number:
        user_record.twilio_contact = fallback_number
        updated = True

    if not getattr(user_record, "twilio_sid", None) or user_record.twilio_sid != purchased.twilio_sid:
        user_record.twilio_sid = purchased.twilio_sid
        updated = True

    if purchased.assigned_to_type != assigned_type or purchased.assigned_to_id != target_id:
        purchased.assigned_to_type = assigned_type
        purchased.assigned_to_id = target_id
        purchased.status = "assigned"
        purchased.assigned_at = datetime.utcnow()
        updated = True

    if updated:
        session.add(user_record)
        session.add(purchased)
        session.commit()
        session.refresh(user_record)

    return fallback_number


def _validate_bot_number_or_422(number: Optional[str], *, field_name: str = "bot number") -> str:
    normalized = _normalize_bot_number(number)
    if not normalized:
        raise HTTPException(status_code=422, detail=f"{field_name} is not configured")
    if not BOT_NUMBER_REGEX.match(normalized):
        raise HTTPException(
            status_code=422,
            detail=f"{field_name} must be in E.164 format (e.g., +18885551234). Got: {normalized}",
        )
    return normalized


def _log_forwarding_event(
    session: Session,
    *,
    target_user_type: str,
    target_user_id: int,
    action: str,
    initiated_by_user_type: str,
    initiated_by_user_id: int,
    event_metadata: Optional[Dict[str, Any]] = None,
):
    """Persist a CallForwardingEvent record."""
    event = CallForwardingEvent(
        target_user_type=target_user_type,
        target_user_id=target_user_id,
        action=action,
        initiated_by_user_type=initiated_by_user_type,
        initiated_by_user_id=initiated_by_user_id,
        event_metadata=event_metadata or {},
    )
    session.add(event)


def _enforce_forwarding_rate_limit(session: Session, target_type: str, target_id: int):
    """Prevent excessive toggles within a short window."""
    cutoff = datetime.utcnow() - timedelta(hours=1)
    total = session.exec(
        select(func.count(CallForwardingEvent.event_id))
        .where(CallForwardingEvent.target_user_type == target_type)
        .where(CallForwardingEvent.target_user_id == target_id)
        .where(CallForwardingEvent.created_at >= cutoff)
    ).one()
    event_count = total[0] if isinstance(total, tuple) else total
    if event_count and event_count >= CALL_FORWARDING_RATE_LIMIT_PER_HOUR:
        raise HTTPException(
            status_code=429,
            detail="Too many forwarding updates in the last hour. Please wait before trying again.",
        )


def _notify_forwarding_status_via_sms(message: str):
    """Send SMS notification to internal number when forwarding state changes."""
    if not FORWARDING_ALERT_NUMBER or not FORWARDING_ALERT_FROM_NUMBER:
        return
    client = twillio_client1 or twillio_client
    if not client:
        return
    try:
        client.messages.create(
            body=message,
            from_=FORWARDING_ALERT_FROM_NUMBER,
            to=FORWARDING_ALERT_NUMBER,
        )
    except Exception as sms_error:
        print(f"⚠️  Failed to send forwarding SMS alert: {sms_error}")


def _resolve_forwarding_target(
    session: Session,
    requester: Dict[str, Any],
    realtor_id: Optional[int] = None,
):
    """Return (record, target_type) for forwarding operations."""
    requester_type = requester.get("user_type")
    requester_id = requester.get("id")

    if realtor_id is not None:
        if requester_type != "property_manager":
            raise HTTPException(
                status_code=403,
                detail="Only Property Managers can manage realtor forwarding state",
            )
        realtor = session.get(Realtor, realtor_id)
        if not realtor:
            raise HTTPException(status_code=404, detail="Realtor not found")
        if realtor.property_manager_id != requester_id:
            raise HTTPException(
                status_code=403,
                detail="You can only manage forwarding for your own realtors",
            )
        return realtor, "realtor"

    if requester_type == "property_manager":
        record = session.get(PropertyManager, requester_id)
        if not record:
            raise HTTPException(status_code=404, detail="Property Manager not found")
        return record, "property_manager"
    elif requester_type == "realtor":
        record = session.get(Realtor, requester_id)
        if not record:
            raise HTTPException(status_code=404, detail="Realtor not found")
        return record, "realtor"

    raise HTTPException(status_code=400, detail="Unsupported user type")


# ------------------ CreateCustomer ----------------#
@app.post("/create_customer/")
def create_customer(request: VapiRequest):
    for tool_call in request.message.toolCalls:
        if tool_call.function.name == "CreateCust":
            args = tool_call.function.arguments
            if isinstance(args, str):
                args = json.loads(args)

            name = args.get("name")
            email = args.get("email")
            contact_number = args.get("contact_number")
            if_tenant = False

            if not contact_number:
                raise HTTPException(
                    status_code=400, detail="Contact number is required"
                )

            # Call helper to create customer
            customer = create_customer_entry(name, email, contact_number, if_tenant)

            return {
                "results": [
                    {
                        "toolCallId": tool_call.id,
                        "result": f"Customer created with ID {customer.id}",
                    }
                ]
            }

    raise HTTPException(status_code=400, detail="Invalid tool call")


# ------------------ Query Docs ------------------ #
@app.post("/query_docs/")
async def query_docs(request: VapiRequest, http_request: Request):
    """
    Query documents/rules with data isolation.
    Filters by user's accessible source_ids.
    """
    from DB.vapi_helpers import identify_user_from_vapi_request, set_call_phone_cache, set_phone_caches
    # Share the caches with the helper module
    set_call_phone_cache(_call_phone_cache)
    set_phone_caches(_phone_id_cache, _phone_to_id_cache)
    
    source_ids = None
    try:
        body = await http_request.json()
        # Log headers for debugging
        print(f"🔍 Query docs - Request headers: {dict(http_request.headers)}")
        user_info = identify_user_from_vapi_request(body, dict(http_request.headers))
        if user_info:
            source_ids = user_info["source_ids"]
            print(f"🔒 Filtering rules for {user_info['user_type']} ID: {user_info['user_id']}")
        else:
            print("⚠️  Could not identify user from VAPI request - returning empty results for security")
            source_ids = []  # Fail secure
    except Exception as e:
        print(f"⚠️  Error identifying user: {e} - returning empty results for security")
        import traceback
        traceback.print_exc()
        source_ids = []  # Fail secure

    for tool_call in request.message.toolCalls:
        if tool_call.function.name == "queryDocs":
            args = tool_call.function.arguments
            if isinstance(args, str):
                args = json.loads(args)
            question = args.get("query")
            address = args.get("address")
            if not question:
                raise HTTPException(status_code=400, detail="Missing query text")

    print("Address:", address)
    
    # If source_ids is an empty list, user has no data - return error
    if source_ids is not None and len(source_ids) == 0:
        raise HTTPException(
            status_code=404, 
            detail="No data available. Please upload listings first."
        )
    
    with Session(engine) as session:
        # Filter by user's accessible source_ids if available
        if source_ids and len(source_ids) > 0:
            count_sql = text(
                """
            SELECT COUNT(*) 
            FROM apartmentlisting
            WHERE LOWER(listing_metadata->>'address') = LOWER(:addr)
              AND source_id = ANY(:source_ids)
        """
            ).params(addr=address, source_ids=source_ids)
        else:
            # source_ids is None - user not identified (security risk)
            print("⚠️  No source_ids provided in query_docs - searching all listings (SECURITY RISK)")
            count_sql = text(
                """
            SELECT COUNT(*) 
            FROM apartmentlisting
            WHERE LOWER(listing_metadata->>'address') = LOWER(:addr)
        """
            ).params(addr=address)

        total_matches = session.exec(count_sql).scalar()

        if total_matches == 0:
            raise HTTPException(
                status_code=404, detail="No listings found for given address"
            )
        
        import random
        random_offset = random.randint(0, total_matches - 1)

        # Fetch source_id filtered by user's accessible sources
        if source_ids and len(source_ids) > 0:
            source_sql = text(
                """
        SELECT source_id
        FROM apartmentlisting
        WHERE LOWER(listing_metadata->>'address') = LOWER(:addr)
          AND source_id = ANY(:source_ids)
        OFFSET :offset LIMIT 1
    """
            ).params(addr=address, source_ids=source_ids, offset=random_offset)
        else:
            source_sql = text(
                """
        SELECT source_id
        FROM apartmentlisting
        WHERE LOWER(listing_metadata->>'address') = LOWER(:addr)
        OFFSET :offset LIMIT 1
    """
            ).params(addr=address, offset=random_offset)

        row = session.exec(source_sql).first()
        if row:
            source_id = row[0]
            # Verify source_id is accessible to user
            if source_ids and source_id not in source_ids:
                raise HTTPException(status_code=403, detail="Access denied to this listing")
        else:
            source_id = None

        response = rag.query(question, source_id=source_id)
        return {"results": [{"toolCallId": tool_call.id, "result": response}]}

    raise HTTPException(status_code=400, detail="Invalid tool call")


@app.post("/confirm_address/")
async def confirm_apartment(request: VapiRequest, http_request: Request):
    """
    Confirm apartment address with data isolation.
    """
    from DB.vapi_helpers import identify_user_from_vapi_request, set_call_phone_cache, set_phone_caches
    # Share the caches with the helper module
    set_call_phone_cache(_call_phone_cache)
    set_phone_caches(_phone_id_cache, _phone_to_id_cache)
    
    source_ids = None
    try:
        body = await http_request.json()
        user_info = identify_user_from_vapi_request(body, dict(http_request.headers))
        if user_info:
            source_ids = user_info["source_ids"]
            print(f"🔒 Filtering listings for {user_info['user_type']} ID: {user_info['user_id']}")
    except Exception as e:
        print(f"⚠️  Error identifying user: {e}")
    
    for tool_call in request.message.toolCalls:
        if tool_call.function.name == "confirmAddress":
            args = tool_call.function.arguments
            query = (
                args.strip() if isinstance(args, str) else args.get("query", "").strip()
            )
            if not query:
                raise HTTPException(status_code=400, detail="Missing query text")

            print("Query:", query)
            listings = rag.search_apartments(query, source_ids=source_ids)
            return {"results": [{"toolCallId": tool_call.id, "result": listings}]}
    raise HTTPException(status_code=400, detail="Invalid tool call")


# ------------------ Search Apartments ------------------ #
@app.post("/search_apartments/")
async def search_apartments(request: VapiRequest, http_request: Request):
    """
    Search apartments with data isolation based on user's phone number.
    """
    from DB.vapi_helpers import identify_user_from_vapi_request, set_call_phone_cache, set_phone_caches
    # Share the caches with the helper module
    set_call_phone_cache(_call_phone_cache)
    set_phone_caches(_phone_id_cache, _phone_to_id_cache)
    
    # Try to identify user from VAPI request
    source_ids = None
    try:
        body = await http_request.json()
        # Log headers for debugging - especially check for custom headers
        print(f"🔍 Full request headers: {dict(http_request.headers)}")
        print(f"🔍 Looking for x-vapi-to header...")
        # Check if headers contain our custom headers (case-insensitive)
        header_keys_lower = {k.lower(): v for k, v in http_request.headers.items()}
        if 'x-vapi-to' in header_keys_lower:
            to_value = header_keys_lower['x-vapi-to']
            if to_value and to_value.strip():
                print(f"   ✅ Found x-vapi-to: {to_value}")
            else:
                print(f"   ⚠️  x-vapi-to header exists but is empty: '{to_value}'")
        else:
            print(f"   ❌ x-vapi-to header NOT FOUND in request!")
        
        # Also check for x-call-id
        if 'x-call-id' in header_keys_lower:
            call_id_value = header_keys_lower['x-call-id']
            print(f"   ✅ Found x-call-id: {call_id_value}")
        else:
            print(f"   ⚠️  x-call-id header NOT FOUND in request!")
        
        print(f"   Available headers: {list(header_keys_lower.keys())}")
        user_info = identify_user_from_vapi_request(body, dict(http_request.headers))
        if user_info:
            source_ids = user_info["source_ids"]
            if source_ids and len(source_ids) > 0:
                print(f"🔒 Filtering listings for {user_info['user_type']} ID: {user_info['user_id']}, source_ids: {source_ids}")
            else:
                print(f"⚠️  User {user_info['user_type']} ID: {user_info['user_id']} has no data (empty source_ids) - will return empty results")
        else:
            print("⚠️  Could not identify user from VAPI request - returning empty results for security")
            source_ids = []  # Fail secure: return empty if we can't identify user
    except Exception as e:
        print(f"⚠️  Error identifying user: {e} - returning empty results for security")
        import traceback
        traceback.print_exc()
        source_ids = []  # Fail secure: return empty if error identifying user
    
    for tool_call in request.message.toolCalls:
        if tool_call.function.name == "searchApartments":
            args = tool_call.function.arguments
            # Parse args if it's a string
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except:
                    args = {"query": args.strip()}
            
            query = args.get("query", "").strip() if isinstance(args, dict) else str(args).strip()
            if not query:
                raise HTTPException(status_code=400, detail="Missing query text")
            
            # Log tool call arguments for debugging
            print(f"📋 Tool call arguments: {args}")

            # Search with source_ids filter for data isolation
            listings = rag.search_apartments(query, source_ids=source_ids)
            
            # Log the results for debugging
            if not listings or len(listings) == 0:
                print(f"⚠️  No listings found for query: '{query}' with source_ids: {source_ids}")
                if source_ids is not None and len(source_ids) == 0:
                    print(f"🚫 User has no data - returning empty results to chatbot")
            else:
                print(f"✅ Found {len(listings)} listings for query: '{query}'")
            
            # Enhance listings with booking-related information (property status, availability, assigned user)
            enhanced_listings = []
            with Session(engine) as session:
                for listing in listings:
                    # Get property_id from listing metadata
                    property_id = listing.get("id") or listing.get("property_id")
                    if not property_id:
                        # Try to find property by address
                        address = listing.get("address")
                        if address:
                            property_listing = session.exec(
                                select(ApartmentListing).where(
                                    ApartmentListing.text.contains(address)
                                ).limit(1)
                            ).first()
                            if property_listing:
                                property_id = property_listing.id
                    
                    if property_id:
                        # Get property listing from database
                        property_listing = session.get(ApartmentListing, property_id)
                        if property_listing:
                            meta = property_listing.listing_metadata or {}
                            
                            # Get property status
                            listing_status = meta.get("listing_status", "unknown")
                            
                            # Get assigned user (realtor if assigned, else PM)
                            assigned_user = _get_property_assigned_user(session, property_id)
                            
                            # Get near-term availability (next 24-72 hours) if property is available
                            availability_summary = None
                            if listing_status == "available" and assigned_user:
                                from_date = datetime.utcnow()
                                to_date = from_date + timedelta(hours=72)
                                try:
                                    available_slots = _compute_available_slots(
                                        session,
                                        assigned_user["user_id"],
                                        assigned_user["user_type"],
                                        from_date,
                                        to_date
                                    )
                                    availability_summary = {
                                        "hasAvailability": len(available_slots) > 0,
                                        "nextAvailableSlot": available_slots[0] if available_slots else None,
                                        "totalSlots": len(available_slots)
                                    }
                                except Exception as e:
                                    print(f"⚠️  Error computing availability for property {property_id}: {e}")
                                    availability_summary = {"hasAvailability": False, "nextAvailableSlot": None, "totalSlots": 0}
                            
                            # Enhance listing with booking info
                            enhanced_listing = {
                                **listing,  # Keep all original listing data
                                "property_id": property_id,  # Ensure property_id is included
                                "listing_status": listing_status,  # "available" | "rented" | "offline"
                                "is_available_for_tours": listing_status == "available",
                                "assigned_to": assigned_user,  # {user_id, user_type, name, phone, email} or null
                                "availability": availability_summary  # {hasAvailability, nextAvailableSlot, totalSlots} or null
                            }
                            enhanced_listings.append(enhanced_listing)
                        else:
                            # Property not found in DB, return original listing
                            enhanced_listings.append(listing)
                    else:
                        # No property_id, return original listing
                        enhanced_listings.append(listing)
            
            # Use enhanced listings if we enhanced any, otherwise use original
            final_listings = enhanced_listings if enhanced_listings else listings
            
            return {"results": [{"toolCallId": tool_call.id, "result": final_listings}]}
    raise HTTPException(status_code=400, detail="Invalid tool call")


# ------------------ Maintenance Requests ------------------ #
@app.post("/lookup_tenant/")
async def lookup_tenant(request: VapiRequest, http_request: Request):
    """
    Lookup tenant information by name, phone, or email.
    Returns tenant name and unit/apartment number for the bot to confirm with user.
    
    This is called BEFORE submitting the maintenance request to verify tenant identity.
    Similar to how search_apartments works - bot asks for info, we return data, bot confirms.
    """
    try:
        from DB.user_lookup import identify_tenant, normalize_phone_number
        from DB.db import Session, ApartmentListing
        
        # Get caller information from VAPI request
        body = await http_request.json()
        header_keys_lower = {k.lower(): v for k, v in http_request.headers.items()}
        
        # Extract caller phone number
        caller_phone = _extract_caller_number(
            payload=body,
            message=body.get("message"),
            headers=dict(http_request.headers)
        )
        
        # Also try direct extraction methods
        if not caller_phone:
            twilio_data = body.get("twilio", {})
            if isinstance(twilio_data, dict):
                caller_phone = twilio_data.get("from") or twilio_data.get("From")
        
        if not caller_phone:
            caller_phone = header_keys_lower.get("x-vapi-from")
        
        # Normalize caller phone
        if caller_phone:
            caller_phone = normalize_phone_number(caller_phone)
        
        # Check if we have tool calls
        if not hasattr(request, 'message') or not hasattr(request.message, 'toolCalls') or not request.message.toolCalls:
            raise HTTPException(
                status_code=400, 
                detail="No tool calls found in request. Expected lookupTenant function call."
            )
        
        # Process tool call
        for tool_call in request.message.toolCalls:
            if tool_call.function.name == "lookupTenant":
                args = tool_call.function.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except:
                        args = {}
                
                # Extract tenant identification info
                tenant_name = (args.get("tenant_name") or args.get("tenantName") or "").strip() or None
                tenant_email = (args.get("tenant_email") or args.get("tenantEmail") or "").strip() or None
                tenant_phone = args.get("tenant_phone") or args.get("tenantPhone") or caller_phone
                
                # Normalize phone number if provided
                if tenant_phone:
                    tenant_phone = normalize_phone_number(tenant_phone)
                
                print(f"🔍 Looking up tenant:")
                print(f"   Name: {tenant_name}")
                print(f"   Email: {tenant_email}")
                print(f"   Phone: {tenant_phone}")
                
                # Lookup tenant
                tenant_info = identify_tenant(
                    phone_number=tenant_phone,
                    email=tenant_email,
                    name=tenant_name
                )
                
                if not tenant_info:
                    # Tenant not found
                    return {
                        "results": [{
                            "toolCallId": tool_call.id,
                            "result": {
                                "found": False,
                                "message": "Tenant not found. Please verify your information or contact your property manager."
                            }
                        }]
                    }
                
                # Get property details and unit number
                with Session(engine) as session:
                    property_listing = session.get(ApartmentListing, tenant_info["property_id"])
                    property_address = property_listing.listing_metadata.get("address") if property_listing and property_listing.listing_metadata else None
                    
                    # Get unit number from tenant object
                    tenant_obj = tenant_info.get("tenant")
                    unit_number = None
                    if tenant_obj and hasattr(tenant_obj, 'unit_number'):
                        unit_number = tenant_obj.unit_number
                
                # Return tenant info for bot to confirm
                result = {
                    "found": True,
                    "tenant_name": tenant_info["tenant_name"],
                    "unit_number": unit_number,
                    "property_address": property_address or tenant_info.get("property_address"),
                    "tenant_id": tenant_info["tenant_id"],
                    "property_id": tenant_info["property_id"],
                    "message": f"Found tenant: {tenant_info['tenant_name']}" + (f" in unit {unit_number}" if unit_number else "")
                }
                
                print(f"✅ Found tenant: {result['tenant_name']} (Unit: {result.get('unit_number', 'N/A')})")
                
                return {
                    "results": [{
                        "toolCallId": tool_call.id,
                        "result": result
                    }]
                }
        
        # If we got here but didn't process any tool calls, return error
        raise HTTPException(
            status_code=400, 
            detail="No lookupTenant tool call found in request"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error in lookup_tenant: {error_msg}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {error_msg}"
        )


@app.post("/submit_maintenance_request/")
async def submit_maintenance_request(request: VapiRequest, http_request: Request):
    """
    Submit a maintenance request from a tenant via VAPI bot.
    
    Tenant identification flow:
    1. At call start: Identify tenant from caller phone number (like we do for PMs/Realtors)
    2. When maintenance tool is called: Confirm/validate with name, email, or phone from conversation
    3. If conflict: Match on any provided criteria (phone OR email OR name)
    4. Create maintenance request with confirmed tenant info
    
    This ensures we know who the tenant is from the start of the call, and can
    validate/confirm their identity when they submit the maintenance request.
    """
    try:
        from DB.vapi_helpers import identify_user_from_vapi_request, set_call_phone_cache, set_phone_caches
        from DB.user_lookup import identify_tenant, normalize_phone_number
        from DB.db import Session, Tenant, MaintenanceRequest, ApartmentListing
        # _extract_caller_number is defined in this file (vapi/app.py), not in DB.user_lookup
        
        # Share the caches with the helper module
        set_call_phone_cache(_call_phone_cache)
        set_phone_caches(_phone_id_cache, _phone_to_id_cache)
        
        # Get caller information from VAPI request
        body = await http_request.json()
        header_keys_lower = {k.lower(): v for k, v in http_request.headers.items()}
        
        # STEP 1: Identify tenant at call start (proactive identification)
        # Extract caller phone number using the same method as other endpoints
        caller_phone = _extract_caller_number(
            payload=body,
            message=body.get("message"),
            headers=dict(http_request.headers)
        )
        
        # Also try direct extraction methods
        if not caller_phone:
            twilio_data = body.get("twilio", {})
            if isinstance(twilio_data, dict):
                caller_phone = twilio_data.get("from") or twilio_data.get("From")
        
        if not caller_phone:
            caller_phone = header_keys_lower.get("x-vapi-from")
        
        # Normalize caller phone
        if caller_phone:
            caller_phone = normalize_phone_number(caller_phone)
        
        # Get call ID for transcript linking
        call_id = (
            body.get("callId") or 
            body.get("call_id") or
            header_keys_lower.get("x-call-id")
        )
        
        # Pre-identify tenant from caller phone (if available)
        pre_identified_tenant = None
        if caller_phone:
            print(f"🔍 Pre-identifying tenant from caller phone: {caller_phone}")
            pre_identified_tenant = identify_tenant(phone_number=caller_phone)
            if pre_identified_tenant:
                print(f"✅ Pre-identified tenant: {pre_identified_tenant['tenant_name']} (ID: {pre_identified_tenant['tenant_id']})")
            else:
                print(f"⚠️  Could not pre-identify tenant from phone number")
        
        # Check if we have tool calls
        if not hasattr(request, 'message') or not hasattr(request.message, 'toolCalls') or not request.message.toolCalls:
            raise HTTPException(
                status_code=400, 
                detail="No tool calls found in request. Expected submitMaintenanceRequest function call."
            )
        
        # Process tool call
        for tool_call in request.message.toolCalls:
            if tool_call.function.name == "submitMaintenanceRequest":
                args = tool_call.function.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except:
                        args = {"issue_description": args.strip()}
                
                # Extract and sanitize input
                issue_description = (args.get("issue_description") or args.get("issueDescription") or "").strip()
                tenant_name = (args.get("tenant_name") or args.get("tenantName") or "").strip() or None
                tenant_email = (args.get("tenant_email") or args.get("tenantEmail") or "").strip() or None
                tenant_phone = args.get("tenant_phone") or args.get("tenantPhone") or caller_phone
                category = (args.get("category") or "").strip().lower() or None
                location = (args.get("location") or "").strip() or None
                priority = (args.get("priority") or "normal").strip().lower()
                
                # Validate issue description
                if not issue_description:
                    raise HTTPException(status_code=400, detail="Missing issue_description")
                
                # Sanitize issue description (remove excessive whitespace, limit length)
                issue_description = " ".join(issue_description.split())  # Normalize whitespace
                if len(issue_description) > 5000:  # Reasonable limit
                    issue_description = issue_description[:5000] + "..."
                
                # Validate and normalize priority
                valid_priorities = ["low", "normal", "high", "urgent"]
                if priority not in valid_priorities:
                    # Auto-detect priority from issue description
                    issue_lower = issue_description.lower()
                    if any(word in issue_lower for word in ["urgent", "emergency", "flooding", "fire", "no heat", "no water", "gas leak"]):
                        priority = "urgent"
                    elif any(word in issue_lower for word in ["broken", "not working", "leaking", "overflowing"]):
                        priority = "high"
                    elif any(word in issue_lower for word in ["minor", "small", "cosmetic"]):
                        priority = "low"
                    else:
                        priority = "normal"
                
                # Validate category enum if provided
                valid_categories = ["plumbing", "electrical", "appliance", "heating", "hvac", "other"]
                if category and category not in valid_categories:
                    print(f"⚠️  Invalid category '{category}', will auto-detect from description")
                    category = None  # Reset to trigger auto-detection
                
                # Normalize "hvac" to "heating" (they're the same category)
                if category == "hvac":
                    category = "heating"
                
                # Auto-detect category if not provided
                if not category:
                    issue_lower = issue_description.lower()
                    if any(word in issue_lower for word in ["sink", "toilet", "faucet", "pipe", "drain", "water", "leak", "plumbing"]):
                        category = "plumbing"
                    elif any(word in issue_lower for word in ["light", "outlet", "switch", "electrical", "power", "circuit", "breaker"]):
                        category = "electrical"
                    elif any(word in issue_lower for word in ["heat", "heating", "furnace", "boiler", "radiator", "hvac", "ac", "air conditioning", "cooling"]):
                        category = "heating"
                    elif any(word in issue_lower for word in ["appliance", "refrigerator", "dishwasher", "oven", "stove", "washer", "dryer"]):
                        category = "appliance"
                    else:
                        category = "other"
                
                # Validate email format if provided
                if tenant_email:
                    import re
                    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                    if not re.match(email_pattern, tenant_email):
                        print(f"⚠️  Invalid email format: {tenant_email}, ignoring")
                        tenant_email = None
                
                # Normalize phone number if provided (handles spoken formats)
                if tenant_phone:
                    # tenant_phone might be spoken text like "four one two five five five one two three four"
                    # normalize_phone_number now handles this
                    tenant_phone = normalize_phone_number(tenant_phone)
                    print(f"   Normalized tenant phone: {tenant_phone}")
                
                print(f"🔧 Submitting maintenance request:")
                print(f"   Issue: {issue_description}")
                print(f"   Caller phone (from VAPI): {caller_phone}")
                print(f"   Tenant phone (from conversation): {tenant_phone}")
                print(f"   Tenant name (from conversation): {tenant_name}")
                print(f"   Tenant email (from conversation): {tenant_email}")
                
                # STEP 2: Identify/confirm tenant with all available information
                # Priority: Use pre-identified tenant if available, then validate with conversation data
                tenant_info = None
                
                # If we pre-identified a tenant from caller phone, use that as base
                if pre_identified_tenant:
                    tenant_info = pre_identified_tenant
                    print(f"✅ Using pre-identified tenant from caller phone")
                    
                    # Validate: Check if conversation data matches pre-identified tenant
                    # (This helps catch cases where someone else is calling from tenant's phone)
                    if tenant_phone and tenant_phone != caller_phone:
                        # Phone mismatch - re-identify with conversation phone
                        print(f"⚠️  Phone mismatch: caller={caller_phone}, conversation={tenant_phone}, re-identifying...")
                        tenant_info = identify_tenant(phone_number=tenant_phone)
                    elif tenant_email and tenant_info.get("tenant_email"):
                        # Validate email matches
                        if tenant_email.lower().strip() != tenant_info.get("tenant_email", "").lower().strip():
                            print(f"⚠️  Email mismatch, trying to re-identify with email...")
                            tenant_info = identify_tenant(phone_number=tenant_phone or caller_phone, email=tenant_email)
                    elif tenant_name and tenant_info.get("tenant_name"):
                        # Validate name matches (partial match is OK)
                        if tenant_name.lower().strip() not in tenant_info.get("tenant_name", "").lower():
                            print(f"⚠️  Name mismatch, trying to re-identify with name...")
                            tenant_info = identify_tenant(phone_number=tenant_phone or caller_phone, name=tenant_name)
                else:
                    # No pre-identification - identify from conversation data
                    # Use OR logic: match on phone OR email OR name (any match works)
                    print(f"🔍 Identifying tenant from conversation data (phone/email/name)...")
                    tenant_info = identify_tenant(
                        phone_number=tenant_phone or caller_phone,
                        email=tenant_email,
                        name=tenant_name
                    )
                
                if not tenant_info:
                    # Tenant not found - return detailed error for debugging
                    debug_info = {
                        "caller_phone_extracted": caller_phone,
                        "tenant_phone_from_conversation": tenant_phone,
                        "tenant_email_from_conversation": tenant_email,
                        "tenant_name_from_conversation": tenant_name,
                        "pre_identified": pre_identified_tenant is not None
                    }
                    
                    print(f"❌ TENANT NOT FOUND - Debug info: {debug_info}")
                    
                    # Return error message for bot to communicate
                    error_msg = "I couldn't find your tenant record in our system. "
                    if not tenant_phone and not tenant_email and not tenant_name:
                        error_msg += "Please provide your name, phone number, or email so I can identify you."
                    else:
                        error_msg += "Please contact your property manager directly to register your information."
                    
                    return {
                        "results": [{
                            "toolCallId": tool_call.id,
                            "result": {
                                "success": False,
                                "error": error_msg,
                                "tenant_not_found": True,
                                "debug_info": debug_info  # Include debug info in response
                            }
                        }]
                    }
                
                # Create maintenance request
                with Session(engine) as session:
                    # Try to get call transcript and recording URL if available (from VAPI webhook cache or API)
                    call_transcript = None
                    call_recording_url = None
                    if call_id:
                        # Check if we have transcript and recording in call records
                        from DB.db import CallRecord
                        from sqlmodel import select
                        call_record = session.exec(
                            select(CallRecord).where(CallRecord.call_id == call_id)
                        ).first()
                        if call_record:
                            if call_record.transcript:
                                call_transcript = call_record.transcript
                                print(f"📝 Found call transcript for call {call_id}")
                            if call_record.recording_url:
                                call_recording_url = call_record.recording_url
                                print(f"🎵 Found call recording URL for call {call_id}")
                    
                    maintenance_request = MaintenanceRequest(
                        tenant_id=tenant_info["tenant_id"],
                        property_id=tenant_info["property_id"],
                        property_manager_id=tenant_info["property_manager_id"],
                        issue_description=issue_description,
                        priority=priority,
                        status="pending",
                        category=category,
                        location=location,
                        tenant_name=tenant_info["tenant_name"],
                        tenant_phone=tenant_info["tenant_phone"],
                        tenant_email=tenant_info["tenant_email"],
                        submitted_via="phone" if call_id else "text",
                        vapi_call_id=call_id,
                        call_transcript=call_transcript,
                        call_recording_url=call_recording_url
                    )
                    
                    session.add(maintenance_request)
                    session.commit()
                    session.refresh(maintenance_request)
                    
                    print(f"✅ Created maintenance request ID {maintenance_request.maintenance_request_id}")
                    print(f"   Priority: {priority} (auto-detected: {priority not in args.get('priority', '')})")
                    print(f"   Category: {category} (auto-detected: {category not in args.get('category', '')})")
                    
                    # Return success message (user-friendly)
                    property_address = tenant_info.get('property_address') or "your property"
                    success_msg = (
                        f"I've successfully submitted your maintenance request for {property_address}. "
                        f"Your request ID is {maintenance_request.maintenance_request_id}. "
                        f"Your property manager will be notified and should respond soon."
                    )
                    
                    # If priority was auto-detected as urgent, mention it
                    if priority == "urgent" and "priority" not in args:
                        success_msg += " I've marked this as urgent based on your description."
                    
                    return {
                        "results": [{
                            "toolCallId": tool_call.id,
                            "result": {
                                "success": True,
                                "message": success_msg,
                                "maintenance_request_id": maintenance_request.maintenance_request_id,
                                "property_address": tenant_info["property_address"],
                                "status": "pending"
                            }
                        }]
                    }
        
        # If we got here but didn't process any tool calls, return error
        raise HTTPException(
            status_code=400, 
            detail="No submitMaintenanceRequest tool call found in request"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error in submit_maintenance_request: {error_msg}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {error_msg}"
        )


# Health check endpoint for testing (GET request)
@app.get("/submit_maintenance_request/")
async def submit_maintenance_request_get():
    """
    Health check endpoint - returns endpoint info.
    Use POST method to actually submit maintenance requests.
    """
    return {
        "message": "Maintenance request endpoint is active",
        "method": "POST",
        "endpoint": "/submit_maintenance_request/",
        "note": "This endpoint requires POST method with VapiRequest body. Use POST to submit maintenance requests."
    }


# ------------------ Calendar Tools ------------------ #
@app.post("/get_date/")
def get_date(request: VapiRequest):
    for tool_call in request.message.toolCalls:
        if tool_call.function.name == "getDate":
            return {
                "results": [
                    {
                        "toolCallId": tool_call.id,
                        "result": {"date": datetime.now().date().isoformat()},
                    }
                ]
            }
    return {"error": "Invalid tool call"}


@app.post("/book_visit/")
def book_visit(request: VapiRequest):
    print("Request:", request)

    for tool_call in request.message.toolCalls:
        if tool_call.function.name == "bookVisit":
            args = tool_call.function.arguments
            if isinstance(args, str):
                args = json.loads(args)

            contact = args.get("contact")
            email = args.get("email")
            date_str = args.get("date")
            address = args.get("address")
            print("Booking:", contact, email, date_str, address)

            if not (contact and email and date_str and address):
                raise HTTPException(status_code=400, detail="Missing required fields")

            # Parse datetime
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
                booking_date = dt.date()
                booking_time = dt.time()
            except ValueError:
                raise HTTPException(
                    status_code=400, detail="Invalid date format. Use YYYY-MM-DD HH:MM"
                )

            with Session(engine) as session:
                # Find the listing by matching address substring in text
                statement = select(ApartmentListing).where(
                    ApartmentListing.text.contains(address)
                )
                listing = session.exec(statement).first()
                if not listing:
                    raise HTTPException(
                        status_code=404, detail="Listing not found for address"
                    )

                # Get source using source_id
                print("Source ID:", listing.source_id)
                statement = select(Source).where(Source.source_id == listing.source_id)
                source = session.exec(statement).first()
                if not source:
                    raise HTTPException(status_code=404, detail="Source not found")

                # Access realtor_id from source
                realtor_id = source.realtor_id
                print("Realtor ID:", realtor_id)

            # Initialize calendar client with correct token
            calendar = GoogleCalendar(realtor_id)

            # Check availability
            if not calendar.is_time_available(date_str):
                return {
                    "results": [
                        {
                            "toolCallId": tool_call.id,
                            "result": f"Time {date_str} not available.",
                        }
                    ]
                }

            # Create calendar event
            summary = f"Apartment Visit for: {address}"
            description = f"Apartment Visit Booking\nEmail: {email}\nAddress: {address}"
            event = calendar.create_event(
                date_str, summary=summary, email=email, description=description
            )

            try:
                created = create_booking_entry(
                    address, booking_date, booking_time, contact
                )
                print("Booking created:", created)
            except Exception as e:
                print("Failed to create booking:", e)

            return {
                "results": [
                    {
                        "toolCallId": tool_call.id,
                        "result": f"Booking confirmed! Event link: {event.get('htmlLink')}",
                    }
                ]
            }

    raise HTTPException(status_code=400, detail="Invalid tool call")


@app.post("/get_slots/")
def get_slots(request: VapiRequest):
    for tool_call in request.message.toolCalls:
        if tool_call.function.name == "getAvailableSlots":
            args = tool_call.function.arguments
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {"date": args}

            date = args.get("date")
            address = args.get("address")
            print("Address:", address)
            if not date or not address:
                raise HTTPException(
                    status_code=400, detail="Missing 'date' or 'address' field"
                )

            with Session(engine) as session:
                # 1. Find the listing by matching address substring in text
                statement = select(ApartmentListing).where(
                    ApartmentListing.text.contains(address)
                )
                listing = session.exec(statement).first()
                if not listing:
                    raise HTTPException(
                        status_code=404, detail="Listing not found for address"
                    )

                # 2. Get source using the source_id
                print("Source ID (slots):", listing.source_id)
                statement = select(Source).where(Source.source_id == listing.source_id)
                source = session.exec(statement).first()
                if not source:
                    raise HTTPException(status_code=404, detail="Source not found")

                # 3. Access the realtor_id from the source
                realtor_id = source.realtor_id
                print("Realtor ID (slots):", source.realtor_id)

            # 🧠 3. Initialize calendar client with correct token
            calendar = GoogleCalendar(realtor_id)

            slots = calendar.get_free_slots(date)
            return {
                "results": [
                    {
                        "toolCallId": tool_call.id,
                        "result": f"Available slots on {date}:\n" + ", ".join(slots),
                    }
                ]
            }
    raise HTTPException(status_code=400, detail="Invalid tool call")


# temp store
temp_state_store = {}


# -------------------- Google Calendar ------------------------------------
@app.get("/authorize/")
def authorize_realtor(realtor_id: int):
    flow = Flow.from_client_secrets_file(
        CREDENTIALS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI
    )
    auth_url, state = flow.authorization_url(
        prompt="consent", include_granted_scopes="true"
    )

    temp_state_store[state] = realtor_id
    return RedirectResponse(auth_url)


@app.get("/oauth2callback")
def oauth2callback(request: Request):
    with Session(engine) as session:
        state = request.query_params.get("state")
        realtor_id = temp_state_store.get(state)

        if not realtor_id:
            return Response(content="Invalid or expired state", status_code=400)

        flow = Flow.from_client_secrets_file(
            CREDENTIALS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI, state=state
        )

        flow.fetch_token(authorization_response=str(request.url))

        credentials_data = {
            "token": flow.credentials.token,
            "refresh_token": flow.credentials.refresh_token,
            "token_uri": flow.credentials.token_uri,
            "client_id": flow.credentials.client_id,
            "client_secret": flow.credentials.client_secret,
            "scopes": flow.credentials.scopes,
            "expiry": (
                flow.credentials.expiry.isoformat() if flow.credentials.expiry else None
            ),
        }

        stmt = (
            update(Realtor)
            .where(Realtor.realtor_id == realtor_id)
            .values(credentials=json.dumps(credentials_data))
        )

        session.exec(stmt)
        session.commit()

        return Response(
            content=f"Authorization successful for realtor_id {realtor_id}."
        )


# ------------------ Health Check ------------------ #
@app.get("/health")
def health_check():
    return {"status": "healthy", "message": "Lease Copilot is running"}


# ------------------ Vapi Call Event Webhook ------------------ #
# In-memory cache to store call_id -> phone_number mapping
# This is populated when Vapi sends call events
_call_phone_cache: Dict[str, str] = {}
# Also store phone_number_id -> phone_number for quick lookup
_phone_id_cache: Dict[str, str] = {}
# Store phone_number -> phone_number_id mapping (reverse lookup)
_phone_to_id_cache: Dict[str, str] = {}


def _update_vapi_caches(
    call_id: Optional[str],
    phone_number: Optional[str],
    phone_number_id: Optional[str] = None,
):
    """Keep caches in sync for downstream data isolation helpers."""
    if call_id and phone_number:
        _call_phone_cache[call_id] = phone_number
        # Keep cache size reasonable (last 1000 calls)
        if len(_call_phone_cache) > 1000:
            oldest_key = next(iter(_call_phone_cache))
            del _call_phone_cache[oldest_key]
        print(f"✅ Stored mapping: call_id={call_id} -> phone_number={phone_number}")

    if phone_number_id and phone_number:
        _phone_id_cache[phone_number_id] = phone_number
        _phone_to_id_cache[phone_number] = phone_number_id
        print(f"✅ Stored phone_number_id mapping: {phone_number_id} <-> {phone_number}")


# ------------------ Twilio WhatsApp ------------------ #
# specifically for whatsapp chat bot
@app.post("/twilio-incoming")
async def twilio_incoming(
    request: Request, From: str = Form(...), Body: str = Form(...)
):
    if From.startswith("whatsapp:"):
        number = From.replace("whatsapp:", "")
    else:
        number = From

    print("Message content:", Body)
    if not message_limiter.check_message_limit(number):
        twiml = MessagingResponse()
        twiml.message(
            " You've reached the daily message limit. Please try again tomorrow."
        )
        return Response(content=str(twiml), media_type="application/xml")

    # Build the payload
    payload = {"assistantId": VAPI_ASSISTANT_ID, "input": Body}

    # If this number has an ongoing chat, include previousChatId
    prev_chat_id = get_chat_session(number)
    if prev_chat_id:
        payload["previousChatId"] = prev_chat_id

    # Send to Vapi

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                "https://api.vapi.ai/chat",
                headers={
                    "Authorization": f"Bearer {VAPI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
    except TimeoutException:
        return PlainTextResponse(
            "Vapi took too long to respond. Please try again later.", status_code=504
        )
    except Exception as e:
        return PlainTextResponse(f"Unexpected error: {str(e)}", status_code=500)

    if response.status_code not in [200, 201]:
        error_details = response.text
        return PlainTextResponse(
            f"Error with Vapi: {response.status_code} - {error_details}",
            status_code=response.status_code,
        )

    response_json = response.json()
    output = response_json.get("output", [])

    if not output or not isinstance(output, list):
        return PlainTextResponse("Vapi returned no output", status_code=500)

    vapi_reply = None
    for item in response_json.get("output", []):
        if item.get("role") == "assistant" and "content" in item:
            vapi_reply = item["content"]
            break

    if not vapi_reply:
        return PlainTextResponse("No content in Vapi response", status_code=500)

    # Save chat ID to Postgres
    chat_id = response_json.get("id")

    if chat_id:
        save_chat_session(number, chat_id)

    # Send reply via Twilio

    async with httpx.AsyncClient() as client:
        await client.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json",
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
            data={"From": TWILIO_PHONE_NUMBER, "To": From, "Body": vapi_reply},
        )
    return PlainTextResponse(status_code=200)


# ------------------- CRUD ----------------------
@app.post("/sources/", response_model=Source)
def create_source_endpoint(
    property_manager_id: int = Body(...),
    realtor_id: Optional[int] = Body(None),
):
    """
    Admin/utility endpoint to (re)create sources. Property manager ownership is mandatory.
    """
    return create_source(property_manager_id=property_manager_id, realtor_id=realtor_id)


@app.post("/upload_docs/")
async def upload_realtor_files(
    file: UploadFile = File(...), realtor_id: int = Form(...)
):
    try:
        content = await file.read()
        file_path = f"realtors/{realtor_id}/{file.filename}"

        response = supabase.storage.from_(BUCKET_NAME).upload(
            file_path, content, file_options={"content-type": file.content_type}
        )

        # Check if response is a dict with an error
        if isinstance(response, dict) and "error" in response:
            raise HTTPException(status_code=500, detail=response["error"]["message"])

        file_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{file_path}"

        return {"message": "File uploaded successfully", "file_url": file_url}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/CreatePropertyManager")
async def create_property_manager_endpoint(
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    contact: str = Form(...),
    company_name: str = Form(None),
):
    """Create a new Property Manager."""
    try:
        # Step 1: Create Supabase Auth user
        auth_response = supabase.auth.sign_up({"email": email, "password": password})

        if not auth_response.user:
            raise HTTPException(
                status_code=400, detail="Failed to create Supabase user"
            )

        auth_user_id = str(auth_response.user.id)  # Supabase UUID

        # Step 2: Pass auth_user_id into DB creation function
        result = create_property_manager(
            auth_user_id=auth_user_id,
            name=name,
            email=email,
            contact=contact,
            company_name=company_name,
        )

        return JSONResponse(content=result, status_code=200)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/CreateRealtor")
async def create_realtor_endpoint(
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    contact: str = Form(...),
    property_manager_id: int = Form(...),
):
    """Create a new Realtor under a Property Manager."""
    try:
        # Step 1: Create Supabase Auth user
        auth_response = supabase.auth.sign_up({"email": email, "password": password})

        if not auth_response.user:
            raise HTTPException(
                status_code=400, detail="Failed to create Supabase user"
            )

        auth_user_id = str(auth_response.user.id)  # Supabase UUID

        # Step 2: Pass auth_user_id into DB creation function
        result = create_realtor(
            auth_user_id=auth_user_id,
            name=name,
            email=email,
            contact=contact,
            property_manager_id=property_manager_id,
        )

        return JSONResponse(content=result, status_code=200)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------------
# Endpoints
# -----------------------------


@app.post("/UploadRules")
async def upload_rules(
    files: list[UploadFile] = File(...),
    realtor_id: int = Depends(get_current_realtor_id),
):
    with Session(engine) as session:
        source = session.exec(
            select(Source).where(Source.realtor_id == realtor_id)
        ).first()
        if not source:
            raise HTTPException(status_code=404, detail="Source not found for realtor")

    uploaded_files = embed_and_store_rules(files, realtor_id, source.source_id)
    return JSONResponse(
        content={"message": "Rules uploaded & embedded", "files": uploaded_files},
        status_code=200,
    )


@app.post("/UploadListings")
async def upload_listings(
    listing_file: UploadFile = File(None),
    listing_api_url: str = Form(None),
    realtor_id: int = Depends(get_current_realtor_id),
):
    raise HTTPException(
        status_code=403,
        detail="Direct realtor uploads are disabled. Please have your Property Manager upload listings on your behalf.",
    )


@app.post("/sync-listings")
def run_sync():
    return sync_apartment_listings()


@app.options("/login")
async def options_login(request: Request):
    """Handle CORS preflight for login endpoint."""
    origin = request.headers.get("Origin", "*")
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": origin if origin in origins else origins[0] if origins else "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Credentials": "true",
        }
    )

@app.post("/login")
async def login_realtor(response: Response, payload: dict = Body(...), request: Request = None):
    """Login endpoint for Realtors (must belong to a Property Manager)."""
    email = payload.get("email")
    password = payload.get("password")
    print("Realtor login attempt:", email)
    
    try:
        result = authenticate_realtor(email, password)
        
        # Store refresh token in secure cookie
        response.set_cookie(
            key="refresh_token",
            value=result["refresh_token"],
            httponly=True,
            secure=False,  # Set to False for HTTP, True for HTTPS in production
            samesite="lax",  # Changed from "strict" to "lax" for better compatibility
            max_age=60 * 60 * 24 * 30,  # 30 days
        )
        
        print("Realtor login successful")
        return result

    except HTTPException:
        raise  # re-raise known HTTP errors as is

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"Exception during realtor login: {e}\nTraceback:\n{tb}")
        raise HTTPException(status_code=400, detail=f"Realtor login failed: {e}")


@app.options("/property-manager-login")
async def options_property_manager_login(request: Request):
    """Handle CORS preflight for property manager login endpoint."""
    origin = request.headers.get("Origin", "*")
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": origin if origin in origins else origins[0] if origins else "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Credentials": "true",
        }
    )

@app.post("/property-manager-login")
async def login_property_manager(response: Response, payload: dict = Body(...), request: Request = None):
    """Login endpoint for Property Managers."""
    email = payload.get("email")
    password = payload.get("password")
    print("Property Manager login attempt:", email)
    
    try:
        result = authenticate_property_manager(email, password)
        
        # Store refresh token in secure cookie
        response.set_cookie(
            key="refresh_token",
            value=result["refresh_token"],
            httponly=True,
            secure=False,  # Set to False for HTTP, True for HTTPS in production
            samesite="lax",  # Changed from "strict" to "lax" for better compatibility
            max_age=60 * 60 * 24 * 30,  # 30 days
        )
        
        print("Property Manager login successful")
        return result

    except HTTPException:
        raise  # re-raise known HTTP errors as is

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"Exception during property manager login: {e}\nTraceback:\n{tb}")
        raise HTTPException(status_code=400, detail=f"Property Manager login failed: {e}")


# ----------------------------------------------------
#                   CRUD Operations
# ----------------------------------------------------


@app.get("/apartments")
async def get_apartments(user_data: dict = Depends(get_current_user_data)):
    """Get apartments based on user type and data access scope.
    
    - Property Managers: See all properties from their own Source + all managed realtors' Sources
    - Realtors: See only properties from their own Source
    """
    user_type = user_data["user_type"]
    user_id = user_data["id"]
    
    print(f"Getting apartments for {user_type} ID: {user_id}")

    # Get data access scope
    access_scope = get_data_access_scope(user_type, user_id)
    source_ids = access_scope["source_ids"]

    if not source_ids:
        return JSONResponse(
            content={"message": "No sources found for this user", "apartments": []}, status_code=200
        )

    with Session(engine) as session:
        # Get apartments for accessible source_ids
        apartments = session.exec(
            select(ApartmentListing).where(ApartmentListing.source_id.in_(source_ids))
        ).all()
        
        # Get all relevant sources in one query
        sources = session.exec(
            select(Source).where(Source.source_id.in_(source_ids))
        ).all()
        
        # Create a mapping of source_id to source for quick lookup
        source_map = {s.source_id: s for s in sources}

        # Transform into frontend-friendly shape with ownership info
        result = []
        for apt in apartments:
            meta = apt.listing_metadata or {}
            source = source_map.get(apt.source_id)
            
            # Get owner information
            owner_info = {}
            if source and source.property_manager_id:
                pm = session.exec(
                    select(PropertyManager).where(PropertyManager.property_manager_id == source.property_manager_id)
                ).first()
                if pm:
                    owner_info = {
                        "owner_type": "property_manager",
                        "owner_id": pm.property_manager_id,
                        "owner_name": pm.name,
                        "owner_email": pm.email,
                    }
            
            if source and source.realtor_id:
                realtor = session.exec(
                    select(Realtor).where(Realtor.realtor_id == source.realtor_id)
                ).first()
                if realtor:
                    owner_info = {
                        "owner_type": "realtor",
                        "owner_id": realtor.realtor_id,
                        "owner_name": realtor.name,
                        "owner_email": realtor.email,
                        "property_manager_id": realtor.property_manager_id,
                    }
            
            # Include all metadata fields + essential info
            property_result = {
                "id": apt.id,
                "source_id": apt.source_id,
                # Core property information
                "listing_id": meta.get("listing_id"),
                "address": meta.get("address"),
                "price": meta.get("price"),
                "bedrooms": meta.get("bedrooms"),
                "bathrooms": meta.get("bathrooms"),
                "square_feet": meta.get("square_feet"),
                "lot_size_sqft": meta.get("lot_size_sqft"),
                "year_built": meta.get("year_built"),
                "property_type": meta.get("property_type"),
                "listing_status": meta.get("listing_status"),
                "days_on_market": meta.get("days_on_market"),
                "listing_date": meta.get("listing_date"),
                # Agent information
                "agent": meta.get("agent"),
                # Features array
                "features": meta.get("features", []),
                # Legacy fields (for backward compatibility)
                "description": meta.get("description"),
                "image_url": meta.get("image_url"),
                # Owner/assignment information
                **owner_info,
                "is_assigned": True if owner_info.get("owner_type") == "realtor" else False,
                "assigned_to_realtor_id": owner_info.get("owner_id") if owner_info.get("owner_type") == "realtor" else None,
                "assigned_to_realtor_name": owner_info.get("owner_name") if owner_info.get("owner_type") == "realtor" else None,
                # Full metadata (if needed for advanced use cases)
                "full_metadata": meta
            }
            result.append(property_result)

        return JSONResponse(content=result)


@app.get("/maintenance-requests")
async def get_maintenance_requests(
    user_data: dict = Depends(get_current_user_data),
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """
    Get maintenance requests for the authenticated user.
    
    - Property Managers: See all maintenance requests for their properties
    - Realtors: See maintenance requests assigned to them (if any)
    
    Query Parameters:
    - status: Filter by status (pending, in_progress, completed, cancelled)
    - limit: Number of results to return (default: 50, max: 100)
    - offset: Pagination offset (default: 0)
    """
    from DB.db import MaintenanceRequest, Tenant, ApartmentListing, PropertyManager, Realtor
    
    user_type = user_data["user_type"]
    user_id = user_data["id"]
    
    with Session(engine) as session:
        # Build query based on user type
        query = select(MaintenanceRequest)
        
        if user_type == "property_manager":
            # PMs see all requests for their properties
            query = query.where(MaintenanceRequest.property_manager_id == user_id)
        elif user_type == "realtor":
            # Realtors see requests assigned to them OR for properties they manage
            # First, get the realtor's PM to find their properties
            realtor = session.get(Realtor, user_id)
            if not realtor:
                raise HTTPException(status_code=404, detail="Realtor not found")
            
            # Get properties managed by this realtor (via Source)
            from DB.db import Source
            realtor_sources = session.exec(
                select(Source).where(Source.realtor_id == user_id)
            ).all()
            realtor_source_ids = [s.source_id for s in realtor_sources]
            
            # Get property IDs from these sources
            if realtor_source_ids:
                realtor_properties = session.exec(
                    select(ApartmentListing).where(ApartmentListing.source_id.in_(realtor_source_ids))
                ).all()
                realtor_property_ids = [p.id for p in realtor_properties]
            else:
                realtor_property_ids = []
            
            # Query: assigned to realtor OR for realtor's properties
            from sqlmodel import or_
            query = query.where(
                or_(
                    MaintenanceRequest.assigned_to_realtor_id == user_id,
                    MaintenanceRequest.property_id.in_(realtor_property_ids) if realtor_property_ids else False
                )
            )
        else:
            raise HTTPException(status_code=403, detail="Unauthorized user type")
        
        # Filter by status if provided
        if status:
            query = query.where(MaintenanceRequest.status == status)
        
        # Order by submitted_at (newest first)
        query = query.order_by(MaintenanceRequest.submitted_at.desc())
        
        # Get total count (execute count query separately)
        count_query = select(MaintenanceRequest)
        if user_type == "property_manager":
            count_query = count_query.where(MaintenanceRequest.property_manager_id == user_id)
        elif user_type == "realtor":
            realtor = session.get(Realtor, user_id)
            if realtor:
                from DB.db import Source
                realtor_sources = session.exec(
                    select(Source).where(Source.realtor_id == user_id)
                ).all()
                realtor_source_ids = [s.source_id for s in realtor_sources]
                if realtor_source_ids:
                    realtor_properties = session.exec(
                        select(ApartmentListing).where(ApartmentListing.source_id.in_(realtor_source_ids))
                    ).all()
                    realtor_property_ids = [p.id for p in realtor_properties]
                else:
                    realtor_property_ids = []
                count_query = count_query.where(
                    or_(
                        MaintenanceRequest.assigned_to_realtor_id == user_id,
                        MaintenanceRequest.property_id.in_(realtor_property_ids) if realtor_property_ids else False
                    )
                )
        if status:
            count_query = count_query.where(MaintenanceRequest.status == status)
        total = len(session.exec(count_query).all())
        
        # Apply pagination
        query = query.limit(min(limit, 100)).offset(offset)
        
        # Execute query
        requests = session.exec(query).all()
        
        # Format results
        result = []
        for req in requests:
            # Get property address
            property_listing = session.get(ApartmentListing, req.property_id)
            property_address = property_listing.listing_metadata.get("address") if property_listing and property_listing.listing_metadata else None
            
            # Get assigned realtor name if assigned
            assigned_realtor_name = None
            if req.assigned_to_realtor_id:
                assigned_realtor = session.get(Realtor, req.assigned_to_realtor_id)
                assigned_realtor_name = assigned_realtor.name if assigned_realtor else None
            
            result.append({
                "maintenance_request_id": req.maintenance_request_id,
                "tenant_id": req.tenant_id,
                "tenant_name": req.tenant_name,
                "tenant_phone": req.tenant_phone,
                "tenant_email": req.tenant_email,
                "property_id": req.property_id,
                "property_address": property_address,
                "issue_description": req.issue_description,
                "priority": req.priority,
                "status": req.status,
                "category": req.category,
                "location": req.location,
                "submitted_via": req.submitted_via,
                "vapi_call_id": req.vapi_call_id,
                "call_transcript": req.call_transcript,
                "call_recording_url": req.call_recording_url,
                "submitted_at": req.submitted_at.isoformat() if req.submitted_at else None,
                "updated_at": req.updated_at.isoformat() if req.updated_at else None,
                "completed_at": req.completed_at.isoformat() if req.completed_at else None,
                "assigned_to_realtor_id": req.assigned_to_realtor_id,
                "assigned_to_realtor_name": assigned_realtor_name,
                "pm_notes": req.pm_notes,
                "resolution_notes": req.resolution_notes,
            })
        
        return JSONResponse(content={
            "maintenance_requests": result,
            "total": total,
            "limit": limit,
            "offset": offset
        })


@app.get("/maintenance-requests/{request_id}")
async def get_maintenance_request(
    request_id: int,
    user_data: dict = Depends(get_current_user_data)
):
    """
    Get a specific maintenance request by ID.
    Only accessible by the PM who manages the property or assigned realtor.
    """
    from DB.db import MaintenanceRequest, Tenant, ApartmentListing, PropertyManager, Realtor
    
    user_type = user_data["user_type"]
    user_id = user_data["id"]
    
    with Session(engine) as session:
        request = session.get(MaintenanceRequest, request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Maintenance request not found")
        
        # Check authorization
        if user_type == "property_manager":
            if request.property_manager_id != user_id:
                raise HTTPException(status_code=403, detail="Not authorized to view this request")
        elif user_type == "realtor":
            if request.assigned_to_realtor_id != user_id:
                # Check if realtor manages the property
                realtor = session.get(Realtor, user_id)
                if not realtor:
                    raise HTTPException(status_code=404, detail="Realtor not found")
                
                from DB.db import Source
                property_listing = session.get(ApartmentListing, request.property_id)
                if not property_listing:
                    raise HTTPException(status_code=404, detail="Property not found")
                
                realtor_sources = session.exec(
                    select(Source).where(Source.realtor_id == user_id)
                ).all()
                realtor_source_ids = [s.source_id for s in realtor_sources]
                
                if property_listing.source_id not in realtor_source_ids:
                    raise HTTPException(status_code=403, detail="Not authorized to view this request")
        else:
            raise HTTPException(status_code=403, detail="Unauthorized user type")
        
        # Get related data
        property_listing = session.get(ApartmentListing, request.property_id)
        property_address = property_listing.listing_metadata.get("address") if property_listing and property_listing.listing_metadata else None
        
        tenant = session.get(Tenant, request.tenant_id)
        assigned_realtor = session.get(Realtor, request.assigned_to_realtor_id) if request.assigned_to_realtor_id else None
        
        # If we have a vapi_call_id but no recording URL stored, try to fetch it from CallRecord
        call_recording_url = request.call_recording_url
        if request.vapi_call_id and not call_recording_url:
            from DB.db import CallRecord
            from sqlmodel import select
            call_record = session.exec(
                select(CallRecord).where(CallRecord.call_id == request.vapi_call_id)
            ).first()
            if call_record and call_record.recording_url:
                call_recording_url = call_record.recording_url
                # Optionally update the maintenance request with the recording URL for future requests
                request.call_recording_url = call_recording_url
                session.add(request)
                session.commit()
        
        # If we have a vapi_call_id but no transcript stored, try to fetch it from CallRecord
        call_transcript = request.call_transcript
        if request.vapi_call_id and not call_transcript:
            from DB.db import CallRecord
            from sqlmodel import select
            call_record = session.exec(
                select(CallRecord).where(CallRecord.call_id == request.vapi_call_id)
            ).first()
            if call_record and call_record.transcript:
                call_transcript = call_record.transcript
                # Optionally update the maintenance request with the transcript for future requests
                request.call_transcript = call_transcript
                session.add(request)
                session.commit()
        
        return JSONResponse(content={
            "maintenance_request_id": request.maintenance_request_id,
            "tenant_id": request.tenant_id,
            "tenant_name": request.tenant_name,
            "tenant_phone": request.tenant_phone,
            "tenant_email": request.tenant_email,
            "tenant_unit_number": tenant.unit_number if tenant else None,
            "property_id": request.property_id,
            "property_address": property_address,
            "issue_description": request.issue_description,
            "priority": request.priority,
            "status": request.status,
            "category": request.category,
            "location": request.location,
            "submitted_via": request.submitted_via,
            "vapi_call_id": request.vapi_call_id,
            "call_transcript": call_transcript,
            "call_recording_url": call_recording_url,
            "submitted_at": request.submitted_at.isoformat() if request.submitted_at else None,
            "updated_at": request.updated_at.isoformat() if request.updated_at else None,
            "completed_at": request.completed_at.isoformat() if request.completed_at else None,
            "assigned_to_realtor_id": request.assigned_to_realtor_id,
            "assigned_to_realtor_name": assigned_realtor.name if assigned_realtor else None,
            "pm_notes": request.pm_notes,
            "resolution_notes": request.resolution_notes,
        })


@app.delete("/maintenance-requests/{request_id}")
async def delete_maintenance_request(
    request_id: int,
    user_data: dict = Depends(get_current_user_data)
):
    """
    Delete a maintenance request.
    
    - Property Managers: Can delete any request for their properties
    - Realtors: Can delete requests assigned to them or for their properties
    
    Note: This is a soft delete - the request is permanently removed from the database.
    """
    from DB.db import MaintenanceRequest, Realtor, ApartmentListing, Source
    from sqlmodel import or_
    
    user_type = user_data["user_type"]
    user_id = user_data["id"]
    
    with Session(engine) as session:
        # Get the maintenance request
        request = session.get(MaintenanceRequest, request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Maintenance request not found")
        
        # Check permissions
        if user_type == "property_manager":
            # PMs can delete requests for their properties
            if request.property_manager_id != user_id:
                raise HTTPException(status_code=403, detail="You can only delete maintenance requests for your properties")
        elif user_type == "realtor":
            # Realtors can delete requests assigned to them or for their properties
            realtor = session.get(Realtor, user_id)
            if not realtor:
                raise HTTPException(status_code=404, detail="Realtor not found")
            
            # Get properties managed by this realtor
            realtor_sources = session.exec(
                select(Source).where(Source.realtor_id == user_id)
            ).all()
            realtor_source_ids = [s.source_id for s in realtor_sources]
            
            if realtor_source_ids:
                realtor_properties = session.exec(
                    select(ApartmentListing).where(ApartmentListing.source_id.in_(realtor_source_ids))
                ).all()
                realtor_property_ids = [p.id for p in realtor_properties]
            else:
                realtor_property_ids = []
            
            # Check if request is assigned to realtor OR for realtor's property
            can_delete = (
                request.assigned_to_realtor_id == user_id or
                request.property_id in realtor_property_ids
            )
            
            if not can_delete:
                raise HTTPException(
                    status_code=403, 
                    detail="You can only delete maintenance requests assigned to you or for your properties"
                )
        else:
            raise HTTPException(status_code=403, detail="Unauthorized user type")
        
        # Delete the request
        session.delete(request)
        session.commit()
        
        return JSONResponse(content={
            "message": "Maintenance request deleted successfully",
            "maintenance_request_id": request_id
        })


@app.patch("/maintenance-requests/{request_id}")
async def update_maintenance_request(
    request_id: int,
    update_data: dict = Body(...),
    user_data: dict = Depends(get_current_user_data)
):
    """
    Update a maintenance request (status, notes, assignment, etc.).
    Only PMs can update all fields. Realtors can only update status and notes for assigned requests.
    """
    from DB.db import MaintenanceRequest, Realtor
    from datetime import datetime
    
    user_type = user_data["user_type"]
    user_id = user_data["id"]
    
    with Session(engine) as session:
        request = session.get(MaintenanceRequest, request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Maintenance request not found")
        
        # Check authorization
        if user_type == "property_manager":
            if request.property_manager_id != user_id:
                raise HTTPException(status_code=403, detail="Not authorized to update this request")
        elif user_type == "realtor":
            if request.assigned_to_realtor_id != user_id:
                raise HTTPException(status_code=403, detail="Not authorized to update this request")
        else:
            raise HTTPException(status_code=403, detail="Unauthorized user type")
        
        # Update fields
        if "status" in update_data:
            new_status = update_data["status"]
            if new_status not in ["pending", "in_progress", "completed", "cancelled"]:
                raise HTTPException(status_code=400, detail="Invalid status")
            request.status = new_status
            
            # Set completed_at if status is completed
            if new_status == "completed" and not request.completed_at:
                request.completed_at = datetime.utcnow()
            elif new_status != "completed":
                request.completed_at = None
        
        # Only PMs can update these fields
        if user_type == "property_manager":
            if "assigned_to_realtor_id" in update_data:
                realtor_id = update_data["assigned_to_realtor_id"]
                if realtor_id:
                    # Verify realtor belongs to this PM
                    realtor = session.get(Realtor, realtor_id)
                    if not realtor or realtor.property_manager_id != user_id:
                        raise HTTPException(status_code=400, detail="Invalid realtor assignment")
                request.assigned_to_realtor_id = realtor_id
            
            if "priority" in update_data:
                if update_data["priority"] not in ["low", "normal", "high", "urgent"]:
                    raise HTTPException(status_code=400, detail="Invalid priority")
                request.priority = update_data["priority"]
            
            if "category" in update_data:
                request.category = update_data["category"]
            
            if "location" in update_data:
                request.location = update_data["location"]
        
        # Both PMs and Realtors can update notes
        if "pm_notes" in update_data and user_type == "property_manager":
            request.pm_notes = update_data["pm_notes"]
        
        if "resolution_notes" in update_data:
            request.resolution_notes = update_data["resolution_notes"]
        
        request.updated_at = datetime.utcnow()
        
        session.add(request)
        session.commit()
        session.refresh(request)
        
        return JSONResponse(content={
            "message": "Maintenance request updated successfully",
            "maintenance_request_id": request.maintenance_request_id,
            "status": request.status
        })


@app.post("/tenants")
async def create_tenant_endpoint(
    payload: dict = Body(...),
    user_data: dict = Depends(get_current_user_data)
):
    """
    Create a new tenant and automatically mark the property as "Rented".
    
    Only Property Managers can create tenants.
    When a tenant is created, the property's listing_status is automatically
    updated to "Rented" to mark it as unavailable.
    """
    from DB.db import create_tenant_entry, ApartmentListing
    from datetime import datetime
    
    user_type = user_data["user_type"]
    property_manager_id = user_data["id"]
    
    if user_type != "property_manager":
        raise HTTPException(
            status_code=403,
            detail="Only Property Managers can create tenants"
        )
    
    # Extract required fields
    name = payload.get("name")
    property_id = payload.get("property_id")
    
    if not name or not property_id:
        raise HTTPException(
            status_code=400,
            detail="Missing required fields: name, property_id"
        )
    
    # Extract optional fields
    phone_number = payload.get("phone_number")
    email = payload.get("email")
    realtor_id = payload.get("realtor_id")
    unit_number = payload.get("unit_number")
    lease_start_date_str = payload.get("lease_start_date")
    lease_end_date_str = payload.get("lease_end_date")
    notes = payload.get("notes")
    
    # Parse dates if provided
    lease_start_date = None
    lease_end_date = None
    if lease_start_date_str:
        try:
            lease_start_date = datetime.fromisoformat(lease_start_date_str.replace('Z', '+00:00')).date()
        except:
            raise HTTPException(status_code=400, detail="Invalid lease_start_date format (use YYYY-MM-DD)")
    
    if lease_end_date_str:
        try:
            lease_end_date = datetime.fromisoformat(lease_end_date_str.replace('Z', '+00:00')).date()
        except:
            raise HTTPException(status_code=400, detail="Invalid lease_end_date format (use YYYY-MM-DD)")
    
    try:
        tenant = create_tenant_entry(
            name=name,
            property_id=property_id,
            property_manager_id=property_manager_id,
            phone_number=phone_number,
            email=email,
            realtor_id=realtor_id,
            unit_number=unit_number,
            lease_start_date=lease_start_date,
            lease_end_date=lease_end_date,
            notes=notes
        )
        
        # Get property address for response
        with Session(engine) as session:
            property_listing = session.get(ApartmentListing, property_id)
            property_address = property_listing.listing_metadata.get("address") if property_listing and property_listing.listing_metadata else None
        
        return JSONResponse(content={
            "message": "Tenant created successfully and property marked as Rented",
            "tenant": {
                "tenant_id": tenant.tenant_id,
                "name": tenant.name,
                "phone_number": tenant.phone_number,
                "email": tenant.email,
                "property_id": tenant.property_id,
                "property_address": property_address,
                "realtor_id": tenant.realtor_id,
                "unit_number": tenant.unit_number,
                "lease_start_date": tenant.lease_start_date.isoformat() if tenant.lease_start_date else None,
                "lease_end_date": tenant.lease_end_date.isoformat() if tenant.lease_end_date else None,
                "is_active": tenant.is_active
            }
        }, status_code=201)
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to create tenant: {str(e)}")


@app.get("/tenants")
async def get_tenants_endpoint(
    user_data: dict = Depends(get_current_user_data),
    property_id: Optional[int] = None,
    is_active: Optional[bool] = None
):
    """
    Get tenants for the authenticated user.
    
    - Property Managers: See all tenants for their properties
    - Realtors: See tenants for properties they manage (if any)
    """
    from DB.db import Tenant, ApartmentListing, Source, Realtor
    
    user_type = user_data["user_type"]
    user_id = user_data["id"]
    
    with Session(engine) as session:
        query = select(Tenant)
        
        if user_type == "property_manager":
            query = query.where(Tenant.property_manager_id == user_id)
        elif user_type == "realtor":
            # Realtors see tenants for properties they manage
            realtor = session.get(Realtor, user_id)
            if not realtor:
                raise HTTPException(status_code=404, detail="Realtor not found")
            
            # Get properties managed by this realtor
            realtor_sources = session.exec(
                select(Source).where(Source.realtor_id == user_id)
            ).all()
            realtor_source_ids = [s.source_id for s in realtor_sources]
            
            if realtor_source_ids:
                realtor_properties = session.exec(
                    select(ApartmentListing).where(ApartmentListing.source_id.in_(realtor_source_ids))
                ).all()
                realtor_property_ids = [p.id for p in realtor_properties]
                
                # Also include tenants assigned to this realtor
                query = query.where(
                    or_(
                        Tenant.property_id.in_(realtor_property_ids),
                        Tenant.realtor_id == user_id
                    )
                )
            else:
                # No properties, only show tenants assigned to this realtor
                query = query.where(Tenant.realtor_id == user_id)
        else:
            raise HTTPException(status_code=403, detail="Unauthorized user type")
        
        # Filter by property_id if provided
        if property_id:
            query = query.where(Tenant.property_id == property_id)
        
        # Filter by is_active if provided
        if is_active is not None:
            query = query.where(Tenant.is_active == is_active)
        
        tenants = session.exec(query).all()
        
        # Format results
        result = []
        for tenant in tenants:
            property_listing = session.get(ApartmentListing, tenant.property_id)
            property_address = property_listing.listing_metadata.get("address") if property_listing and property_listing.listing_metadata else None
            
            result.append({
                "tenant_id": tenant.tenant_id,
                "name": tenant.name,
                "phone_number": tenant.phone_number,
                "email": tenant.email,
                "property_id": tenant.property_id,
                "property_address": property_address,
                "property_manager_id": tenant.property_manager_id,
                "realtor_id": tenant.realtor_id,
                "unit_number": tenant.unit_number,
                "lease_start_date": tenant.lease_start_date.isoformat() if tenant.lease_start_date else None,
                "lease_end_date": tenant.lease_end_date.isoformat() if tenant.lease_end_date else None,
                "is_active": tenant.is_active,
                "notes": tenant.notes,
                "created_at": tenant.created_at.isoformat() if tenant.created_at else None
            })
        
        return JSONResponse(content={"tenants": result})


@app.patch("/tenants/{tenant_id}")
async def update_tenant_endpoint(
    tenant_id: int,
    payload: dict = Body(...),
    user_data: dict = Depends(get_current_user_data)
):
    """
    Update a tenant (e.g., mark as inactive when they move out, update lease dates).
    When a tenant is marked as inactive, the property status can be updated back to "Available".
    """
    from DB.db import Tenant, ApartmentListing
    from sqlalchemy.orm.attributes import flag_modified
    from datetime import datetime
    
    user_type = user_data["user_type"]
    user_id = user_data["id"]
    
    with Session(engine) as session:
        tenant = session.get(Tenant, tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        # Check authorization
        if user_type == "property_manager":
            if tenant.property_manager_id != user_id:
                raise HTTPException(status_code=403, detail="Not authorized to update this tenant")
        elif user_type == "realtor":
            # Realtors can only update tenants they helped rent
            if tenant.realtor_id != user_id:
                raise HTTPException(status_code=403, detail="Not authorized to update this tenant")
        else:
            raise HTTPException(status_code=403, detail="Unauthorized user type")
        
        # Track if we need to update property status
        was_active = tenant.is_active
        new_is_active = payload.get("is_active")
        
        # Update fields
        if "name" in payload:
            tenant.name = payload["name"]
        if "phone_number" in payload:
            from DB.user_lookup import normalize_phone_number
            tenant.phone_number = normalize_phone_number(payload["phone_number"]) if payload["phone_number"] else None
        if "email" in payload:
            tenant.email = payload["email"]
        if "unit_number" in payload:
            tenant.unit_number = payload["unit_number"]
        if "notes" in payload:
            tenant.notes = payload["notes"]
        if "lease_start_date" in payload:
            if payload["lease_start_date"]:
                try:
                    tenant.lease_start_date = datetime.fromisoformat(payload["lease_start_date"].replace('Z', '+00:00')).date()
                except:
                    raise HTTPException(status_code=400, detail="Invalid lease_start_date format")
            else:
                tenant.lease_start_date = None
        if "lease_end_date" in payload:
            if payload["lease_end_date"]:
                try:
                    tenant.lease_end_date = datetime.fromisoformat(payload["lease_end_date"].replace('Z', '+00:00')).date()
                except:
                    raise HTTPException(status_code=400, detail="Invalid lease_end_date format")
            else:
                tenant.lease_end_date = None
        if new_is_active is not None:
            tenant.is_active = new_is_active
        
        tenant.updated_at = datetime.utcnow()
        
        # If tenant is being marked as inactive and property has no other active tenants,
        # update property status back to "Available"
        if was_active and new_is_active == False:
            # Check if property has any other active tenants
            other_active_tenants = session.exec(
                select(Tenant).where(
                    Tenant.property_id == tenant.property_id,
                    Tenant.tenant_id != tenant_id,
                    Tenant.is_active == True
                )
            ).first()
            
            if not other_active_tenants:
                # No other active tenants, mark property as available
                property_listing = session.get(ApartmentListing, tenant.property_id)
                if property_listing:
                    meta = dict(property_listing.listing_metadata) if property_listing.listing_metadata else {}
                    meta["listing_status"] = "Available"
                    property_listing.listing_metadata = meta
                    flag_modified(property_listing, "listing_metadata")
                    print(f"✅ Marked property {tenant.property_id} as Available (tenant moved out)")
        
        session.add(tenant)
        session.commit()
        session.refresh(tenant)
        
        return JSONResponse(content={
            "message": "Tenant updated successfully",
            "tenant_id": tenant.tenant_id,
            "is_active": tenant.is_active
        })


@app.get("/managed-realtors")
async def get_managed_realtors_endpoint(user_data: dict = Depends(get_current_user_data)):
    """Get managed realtors (only for Property Managers)."""
    user_type = user_data["user_type"]
    user_id = user_data["id"]
    
    if user_type != "property_manager":
        raise HTTPException(
            status_code=403, 
            detail="Only Property Managers can access this endpoint"
        )
    
    from DB.db import get_managed_realtors as fetch_managed_realtors
    realtors = fetch_managed_realtors(user_id)
    return JSONResponse(content={"managed_realtors": realtors})


@app.get("/property-manager/realtors")
async def get_property_manager_realtors(user_data: dict = Depends(get_current_user_data)):
    """Get managed realtors for Property Managers (frontend endpoint)."""
    user_type = user_data["user_type"]
    user_id = user_data["id"]
    
    if user_type != "property_manager":
        raise HTTPException(
            status_code=403, 
            detail="Only Property Managers can access this endpoint"
        )
    
    from DB.db import get_managed_realtors as fetch_managed_realtors
    realtors = fetch_managed_realtors(user_id)
    # Transform to match frontend expectations
    realtors_data = [
        {
            "id": r["id"],
            "name": r["name"],
            "email": r["email"],
            "contact": r.get("contact", "N/A"),
            "status": "active",  # Default status
        }
        for r in realtors
    ]
    return JSONResponse(content={"realtors": realtors_data})


@app.post("/property-manager/add-realtor")
async def add_realtor_endpoint(
    payload: dict = Body(...),
    user_data: dict = Depends(get_current_user_data)
):
    """Add a new realtor under a Property Manager."""
    user_type = user_data["user_type"]
    property_manager_id = user_data["id"]
    
    if user_type != "property_manager":
        raise HTTPException(
            status_code=403, 
            detail="Only Property Managers can add realtors"
        )
    
    name = payload.get("name")
    email = payload.get("email")
    password = payload.get("password")
    
    if not all([name, email, password]):
        raise HTTPException(
            status_code=400,
            detail="Missing required fields: name, email, password"
        )
    
    # Use a default contact if not provided
    contact = payload.get("contact", "TBD")
    
    try:
        # Step 1: Create Supabase Auth user
        auth_response = supabase.auth.sign_up({"email": email, "password": password})
        
        if not auth_response.user:
            raise HTTPException(
                status_code=400, detail="Failed to create Supabase user"
            )
        
        auth_user_id = str(auth_response.user.id)  # Supabase UUID
        
        # Step 2: Create realtor in database under this property manager
        from DB.db import create_realtor
        result = create_realtor(
            auth_user_id=auth_user_id,
            name=name,
            email=email,
            contact=contact,
            property_manager_id=property_manager_id,
        )
        
        return JSONResponse(content={
            "message": "Realtor added successfully!",
            "realtor": result.get("realtor", {})
        }, status_code=200)
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"Exception adding realtor: {e}\nTraceback:\n{tb}")
        raise HTTPException(status_code=500, detail=f"Failed to add realtor: {str(e)}")


@app.get("/user-profile")
async def get_user_profile(user_data: dict = Depends(get_current_user_data)):
    """Get current user's profile information including calendar preferences."""
    user_id = user_data["id"]
    user_type = user_data["user_type"]
    
    with Session(engine) as session:
        # Get calendar preferences
        prefs = _get_user_calendar_preferences(session, user_id, user_type)
        
        # Return user data with calendar preferences
        return JSONResponse(content={
            "user": {
                **user_data,
                "timezone": prefs["timezone"],
                "calendar_preferences": {
                    "defaultSlotLengthMins": prefs["defaultSlotLengthMins"],
                    "workingHours": prefs["workingHours"]
                }
            }
        })


# Get Calendar Preferences
@app.get("/api/users/{user_id}/calendar-preferences")
async def get_calendar_preferences(
    user_id: int,
    user_type: str,
    user_data: dict = Depends(get_current_user_data)
):
    """Get user's calendar preferences (timezone, working hours, slot length)."""
    # Verify user can only access their own preferences
    if user_data.get("user_type") != user_type or user_data.get("id") != user_id:
        raise HTTPException(
            status_code=403,
            detail="You can only access your own calendar preferences"
        )
    
    with Session(engine) as session:
        prefs = _get_user_calendar_preferences(session, user_id, user_type)
        return JSONResponse(content=prefs)


# Update Calendar Preferences
@app.patch("/api/users/{user_id}/calendar-preferences")
async def update_calendar_preferences(
    user_id: int,
    user_type: str,
    timezone: Optional[str] = Body(None),
    default_slot_length_mins: Optional[int] = Body(None),
    working_hours_start: Optional[str] = Body(None),  # Format: "HH:MM"
    working_hours_end: Optional[str] = Body(None),  # Format: "HH:MM"
    working_days: Optional[List[int]] = Body(None),  # List of day numbers: 0=Monday, 6=Sunday
    user_data: dict = Depends(get_current_user_data)
):
    """Update user's calendar preferences (timezone, working hours, slot length)."""
    # Verify user can only update their own preferences
    if user_data.get("user_type") != user_type or user_data.get("id") != user_id:
        raise HTTPException(
            status_code=403,
            detail="You can only update your own calendar preferences"
        )
    
    with Session(engine) as session:
        # Get user
        if user_type == "property_manager":
            user = session.get(PropertyManager, user_id)
        elif user_type == "realtor":
            user = session.get(Realtor, user_id)
        else:
            raise HTTPException(status_code=400, detail="Invalid user_type")
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Update timezone if provided
        if timezone is not None:
            user.timezone = timezone
        
        # Get or initialize calendar_preferences
        prefs = user.calendar_preferences or {}
        
        # Update default slot length if provided
        if default_slot_length_mins is not None:
            if default_slot_length_mins < 15 or default_slot_length_mins > 120:
                raise HTTPException(
                    status_code=400,
                    detail="default_slot_length_mins must be between 15 and 120 minutes"
                )
            prefs["defaultSlotLengthMins"] = default_slot_length_mins
        
        # Update working hours if provided
        if working_hours_start is not None or working_hours_end is not None:
            working_hours = prefs.get("workingHours", {"start": "09:00", "end": "17:00"})
            
            if working_hours_start is not None:
                # Validate format
                try:
                    datetime.strptime(working_hours_start, "%H:%M")
                except ValueError:
                    raise HTTPException(
                        status_code=400,
                        detail="working_hours_start must be in HH:MM format (e.g., '09:00')"
                    )
                working_hours["start"] = working_hours_start
            
            if working_hours_end is not None:
                # Validate format
                try:
                    datetime.strptime(working_hours_end, "%H:%M")
                except ValueError:
                    raise HTTPException(
                        status_code=400,
                        detail="working_hours_end must be in HH:MM format (e.g., '17:00')"
                    )
                working_hours["end"] = working_hours_end
            
            # Validate that end is after start
            start_time = datetime.strptime(working_hours["start"], "%H:%M").time()
            end_time = datetime.strptime(working_hours["end"], "%H:%M").time()
            if end_time <= start_time:
                raise HTTPException(
                    status_code=400,
                    detail="working_hours_end must be after working_hours_start"
                )
            
            prefs["workingHours"] = working_hours
        
        # Update working days if provided
        if working_days is not None:
            # Validate working_days is a list
            if not isinstance(working_days, list):
                raise HTTPException(
                    status_code=400,
                    detail="working_days must be a list of integers (0=Monday, 6=Sunday)"
                )
            
            # Validate all values are integers between 0-6
            valid_days = set(range(7))  # 0-6
            if not all(isinstance(day, int) and day in valid_days for day in working_days):
                raise HTTPException(
                    status_code=400,
                    detail="working_days must contain integers between 0 (Monday) and 6 (Sunday)"
                )
            
            # Remove duplicates and sort
            working_days_unique = sorted(list(set(working_days)))
            prefs["workingDays"] = working_days_unique
        
        # Update calendar_preferences - create a new dict to ensure change detection
        user.calendar_preferences = dict(prefs)
        
        # Mark JSONB field as modified (required for SQLAlchemy to detect changes)
        flag_modified(user, "calendar_preferences")
        
        try:
            session.add(user)
            session.commit()
            session.refresh(user)
            
            # Expire the object to force a fresh query
            session.expire(user)
            
            # Re-fetch the user to ensure we have the latest data
            if user_type == "property_manager":
                user = session.get(PropertyManager, user_id)
            elif user_type == "realtor":
                user = session.get(Realtor, user_id)
            
            # Return updated preferences
            updated_prefs = _get_user_calendar_preferences(session, user_id, user_type)
            return JSONResponse(content={
                "message": "Calendar preferences updated successfully",
                "preferences": updated_prefs
            })
        except Exception as e:
            session.rollback()
            error_msg = str(e) if isinstance(e, (str, Exception)) else repr(e)
            print(f"⚠️  Error updating calendar preferences: {error_msg}")
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update calendar preferences: {error_msg}"
            )


@app.get("/property-manager/properties-by-realtor")
async def get_properties_by_realtor(user_data: dict = Depends(get_current_user_data)):
    """Get properties grouped by realtor (Property Managers only).
    
    Returns properties organized by which realtor they belong to,
    plus properties directly owned by the Property Manager.
    """
    user_type = user_data["user_type"]
    property_manager_id = user_data["id"]
    
    if user_type != "property_manager":
        raise HTTPException(
            status_code=403, 
            detail="Only Property Managers can access this endpoint"
        )
    
    with Session(engine) as session:
        # Get all managed realtors
        realtors = session.exec(
            select(Realtor).where(Realtor.property_manager_id == property_manager_id)
        ).all()
        
        result = {
            "property_manager_properties": [],
            "realtor_properties": {},
            "summary": {
                "total_properties": 0,
                "property_manager_count": 0,
                "realtor_counts": {}
            }
        }
        
        # Get Property Manager's own properties
        pm_sources = session.exec(
            select(Source).where(Source.property_manager_id == property_manager_id)
        ).all()
        
        pm_source_ids = [s.source_id for s in pm_sources]
        if pm_source_ids:
            pm_apartments = session.exec(
                select(ApartmentListing).where(ApartmentListing.source_id.in_(pm_source_ids))
            ).all()
            
            for apt in pm_apartments:
                meta = apt.listing_metadata or {}
                result["property_manager_properties"].append({
                    "id": apt.id,
                    "source_id": apt.source_id,
                    "listing_id": meta.get("listing_id"),
                    "address": meta.get("address"),
                    "price": meta.get("price"),
                    "bedrooms": meta.get("bedrooms"),
                    "bathrooms": meta.get("bathrooms"),
                    "square_feet": meta.get("square_feet"),
                    "lot_size_sqft": meta.get("lot_size_sqft"),
                    "year_built": meta.get("year_built"),
                    "property_type": meta.get("property_type"),
                    "listing_status": meta.get("listing_status"),
                    "days_on_market": meta.get("days_on_market"),
                    "listing_date": meta.get("listing_date"),
                    "agent": meta.get("agent"),
                    "features": meta.get("features", []),
                    "description": meta.get("description"),
                    "image_url": meta.get("image_url"),
                })
        
        result["summary"]["property_manager_count"] = len(result["property_manager_properties"])
        
        # Get properties for each realtor
        for realtor in realtors:
            realtor_sources = session.exec(
                select(Source).where(Source.realtor_id == realtor.realtor_id)
            ).all()
            
            realtor_source_ids = [s.source_id for s in realtor_sources]
            if realtor_source_ids:
                realtor_apartments = session.exec(
                    select(ApartmentListing).where(ApartmentListing.source_id.in_(realtor_source_ids))
                ).all()
                
                realtor_props = []
                for apt in realtor_apartments:
                    meta = apt.listing_metadata or {}
                    realtor_props.append({
                        "id": apt.id,
                        "source_id": apt.source_id,
                        "listing_id": meta.get("listing_id"),
                        "address": meta.get("address"),
                        "price": meta.get("price"),
                        "bedrooms": meta.get("bedrooms"),
                        "bathrooms": meta.get("bathrooms"),
                        "square_feet": meta.get("square_feet"),
                        "lot_size_sqft": meta.get("lot_size_sqft"),
                        "year_built": meta.get("year_built"),
                        "property_type": meta.get("property_type"),
                        "listing_status": meta.get("listing_status"),
                        "days_on_market": meta.get("days_on_market"),
                        "listing_date": meta.get("listing_date"),
                        "agent": meta.get("agent"),
                        "features": meta.get("features", []),
                        "description": meta.get("description"),
                        "image_url": meta.get("image_url"),
                    })
                
                result["realtor_properties"][str(realtor.realtor_id)] = {
                    "realtor_id": realtor.realtor_id,
                    "realtor_name": realtor.name,
                    "realtor_email": realtor.email,
                    "properties": realtor_props,
                    "count": len(realtor_props),
                }
                
                result["summary"]["realtor_counts"][str(realtor.realtor_id)] = {
                    "realtor_name": realtor.name,
                    "count": len(realtor_props),
                }
        
        result["summary"]["total_properties"] = (
            result["summary"]["property_manager_count"] + 
            sum(rp["count"] for rp in result["realtor_properties"].values())
        )
        
        return JSONResponse(content=result)


@app.get("/property-manager/assignments")
async def get_property_assignments(user_data: dict = Depends(get_current_user_data)):
    """Get property assignments view for Property Managers.
    
    Shows all properties with clear assignment information:
    - Properties owned by PM (unassigned)
    - Properties assigned to each realtor
    """
    user_type = user_data["user_type"]
    property_manager_id = user_data["id"]
    
    if user_type != "property_manager":
        raise HTTPException(
            status_code=403,
            detail="Only Property Managers can access this endpoint"
        )
    
    with Session(engine) as session:
        # Get all managed realtors
        realtors = session.exec(
            select(Realtor).where(Realtor.property_manager_id == property_manager_id)
        ).all()
        
        # Get PM's sources - split into unassigned (no realtor) and assigned (has realtor)
        pm_sources = session.exec(
            select(Source).where(Source.property_manager_id == property_manager_id)
        ).all()
        
        # Unassigned sources: PM owns them, no realtor assigned
        unassigned_sources = [s for s in pm_sources if s.realtor_id is None]
        unassigned_source_ids = [s.source_id for s in unassigned_sources]
        
        # All PM sources (for getting all properties)
        pm_source_ids = [s.source_id for s in pm_sources]
        
        # Get all properties (PM's + all realtors')
        all_source_ids = pm_source_ids.copy()
        realtor_sources_map = {}  # realtor_id -> [source_ids]
        
        for realtor in realtors:
            realtor_sources = session.exec(
                select(Source).where(Source.realtor_id == realtor.realtor_id)
            ).all()
            realtor_source_ids = [s.source_id for s in realtor_sources]
            realtor_sources_map[realtor.realtor_id] = realtor_source_ids
            all_source_ids.extend(realtor_source_ids)
        
        if not all_source_ids:
            return JSONResponse(content={
                "unassigned_properties": [],
                "assigned_properties": {},
                "summary": {
                    "total_properties": 0,
                    "unassigned_count": 0,
                    "assigned_count": 0,
                    "realtor_counts": {}
                }
            })
        
        # Get all properties
        all_properties = session.exec(
            select(ApartmentListing).where(ApartmentListing.source_id.in_(all_source_ids))
        ).all()
        
        # Categorize properties
        unassigned_properties = []
        assigned_properties = {}  # realtor_id -> [properties]
        
        for prop in all_properties:
            meta = prop.listing_metadata or {}
            
            property_data = {
                "id": prop.id,
                "source_id": prop.source_id,
                # Core property information
                "listing_id": meta.get("listing_id"),
                "address": meta.get("address"),
                "price": meta.get("price"),
                "bedrooms": meta.get("bedrooms"),
                "bathrooms": meta.get("bathrooms"),
                "square_feet": meta.get("square_feet"),
                "lot_size_sqft": meta.get("lot_size_sqft"),
                "year_built": meta.get("year_built"),
                "property_type": meta.get("property_type"),
                "listing_status": meta.get("listing_status"),
                "days_on_market": meta.get("days_on_market"),
                "listing_date": meta.get("listing_date"),
                # Agent information
                "agent": meta.get("agent"),
                # Features array
                "features": meta.get("features", []),
                # Legacy fields
                "description": meta.get("description"),
                "image_url": meta.get("image_url"),
            }
            
            # Check if property belongs to PM and is unassigned (no realtor)
            if prop.source_id in unassigned_source_ids:
                unassigned_properties.append(property_data)
            else:
                # Find which realtor this belongs to
                for realtor_id, source_ids in realtor_sources_map.items():
                    if prop.source_id in source_ids:
                        if realtor_id not in assigned_properties:
                            assigned_properties[realtor_id] = []
                        assigned_properties[realtor_id].append(property_data)
                        break
        
        # Format assigned properties with realtor info
        assigned_properties_formatted = {}
        for realtor in realtors:
            if realtor.realtor_id in assigned_properties:
                assigned_properties_formatted[realtor.realtor_id] = {
                    "realtor_id": realtor.realtor_id,
                    "realtor_name": realtor.name,
                    "realtor_email": realtor.email,
                    "properties": assigned_properties[realtor.realtor_id],
                    "count": len(assigned_properties[realtor.realtor_id])
                }
        
        # Summary
        summary = {
            "total_properties": len(all_properties),
            "unassigned_count": len(unassigned_properties),
            "assigned_count": sum(len(props) for props in assigned_properties.values()),
            "realtor_counts": {
                str(realtor.realtor_id): {
                    "realtor_name": realtor.name,
                    "count": len(assigned_properties.get(realtor.realtor_id, []))
                }
                for realtor in realtors
            }
        }
        
        return JSONResponse(content={
            "unassigned_properties": unassigned_properties,
            "assigned_properties": assigned_properties_formatted,
            "summary": summary
        })


# ---------------------- PROPERTY ASSIGNMENT AND UPLOAD ----------------------

@app.get("/check-properties")
async def check_properties(user_data: dict = Depends(get_current_user_data)):
    """Check existing properties for the current user (PM or Realtor)."""
    user_type = user_data["user_type"]
    user_id = user_data["id"]
    
    with Session(engine) as session:
        if user_type == "property_manager":
            # Get PM's own properties
            pm_sources = session.exec(
                select(Source).where(Source.property_manager_id == user_id)
            ).all()
            pm_source_ids = [s.source_id for s in pm_sources]
            
            # Get managed realtors' sources
            realtors = session.exec(
                select(Realtor).where(Realtor.property_manager_id == user_id)
            ).all()
            realtor_source_ids = []
            for realtor in realtors:
                realtor_sources = session.exec(
                    select(Source).where(Source.realtor_id == realtor.realtor_id)
                ).all()
                realtor_source_ids.extend([s.source_id for s in realtor_sources])
            
            all_source_ids = pm_source_ids + realtor_source_ids
        else:  # realtor
            sources = session.exec(
                select(Source).where(Source.realtor_id == user_id)
            ).all()
            all_source_ids = [s.source_id for s in sources]
        
        if not all_source_ids:
            return JSONResponse(content={
                "user_type": user_type,
                "user_id": user_id,
                "total_properties": 0,
                "properties": [],
                "sources": []
            })
        
        properties = session.exec(
            select(ApartmentListing).where(ApartmentListing.source_id.in_(all_source_ids))
        ).all()
        
        # Get source info
        sources = session.exec(
            select(Source).where(Source.source_id.in_(all_source_ids))
        ).all()
        
        source_info = []
        for s in sources:
            owner_type = "property_manager" if s.property_manager_id else "realtor"
            owner_id = s.property_manager_id if s.property_manager_id else s.realtor_id
            
            if s.property_manager_id:
                pm = session.exec(
                    select(PropertyManager).where(PropertyManager.property_manager_id == s.property_manager_id)
                ).first()
                owner_name = pm.name if pm else "Unknown"
            else:
                r = session.exec(
                    select(Realtor).where(Realtor.realtor_id == s.realtor_id)
                ).first()
                owner_name = r.name if r else "Unknown"
            
            source_info.append({
                "source_id": s.source_id,
                "owner_type": owner_type,
                "owner_id": owner_id,
                "owner_name": owner_name,
                "property_count": len([p for p in properties if p.source_id == s.source_id])
            })
        
        return JSONResponse(content={
            "user_type": user_type,
            "user_id": user_id,
            "total_properties": len(properties),
            "sources": source_info,
            "properties_by_source": {
                str(s.source_id): [
                    {
                        "id": p.id,
                        "address": (p.listing_metadata or {}).get("address"),
                        "price": (p.listing_metadata or {}).get("price"),
                    }
                    for p in properties if p.source_id == s.source_id
                ]
                for s in sources
            }
        })


@app.post("/property-manager/upload-listings")
async def property_manager_upload_listings(
    listing_file: UploadFile = File(None),
    listing_api_url: str = Form(None),
    assign_to_realtor_id: int = Form(None),  # Optional: assign to specific realtor
    user_data: dict = Depends(get_current_user_data)
):
    """Property Manager uploads listings to their own source or assigns to a realtor."""
    user_type = user_data["user_type"]
    property_manager_id = user_data["id"]
    
    if user_type != "property_manager":
        raise HTTPException(
            status_code=403,
            detail="Only Property Managers can upload listings"
        )
    
    with Session(engine) as session:
        source_id = None
        
        if assign_to_realtor_id:
            # Verify realtor is managed by this PM
            realtor = session.exec(
                select(Realtor).where(
                    Realtor.realtor_id == assign_to_realtor_id,
                    Realtor.property_manager_id == property_manager_id
                )
            ).first()
            
            if not realtor:
                raise HTTPException(
                    status_code=404,
                    detail="Realtor not found or not managed by this Property Manager"
                )
            
            # Get realtor's source
            source = session.exec(
                select(Source).where(
                    Source.realtor_id == assign_to_realtor_id,
                    Source.property_manager_id == property_manager_id,
                )
            ).first()
            
            if not source:
                source = create_source(
                    property_manager_id=property_manager_id,
                    realtor_id=assign_to_realtor_id,
                )
            
            source_id = source.source_id
        else:
            # Upload to PM's own source
            source = session.exec(
                select(Source).where(
                    Source.property_manager_id == property_manager_id,
                    Source.realtor_id == None,  # noqa: E711
                )
            ).first()
            
            if not source:
                source = create_source(property_manager_id=property_manager_id)
            
            source_id = source.source_id
        
        # Use the new direct insert function
        from DB.db import embed_and_store_listings_for_source
        result = embed_and_store_listings_for_source(
            listing_file=listing_file,
            listing_api_url=listing_api_url,
            source_id=source_id
        )
        
        return JSONResponse(content={
            "message": "Listings uploaded successfully",
            "assigned_to": "realtor" if assign_to_realtor_id else "property_manager",
            "realtor_id": assign_to_realtor_id if assign_to_realtor_id else None,
            "source_id": source_id,
            **result
        })


@app.post("/property-manager/assign-properties")
async def assign_properties_to_realtor(
    payload: dict = Body(...),
    user_data: dict = Depends(get_current_user_data)
):
    """Property Manager assigns existing properties to a specific realtor.
    
    Body:
    {
        "realtor_id": 123,  // Realtor ID (integer)
        "property_ids": [1, 2, 3, 4, 5]  // List of apartment listing IDs
    }
    """
    user_type = user_data["user_type"]
    property_manager_id = user_data["id"]
    
    if user_type != "property_manager":
        raise HTTPException(
            status_code=403,
            detail="Only Property Managers can assign properties"
        )
    
    realtor_id = payload.get("realtor_id")
    property_ids = payload.get("property_ids", [])  # List of apartment listing IDs
    
    if not realtor_id or not property_ids:
        raise HTTPException(
            status_code=400,
            detail="Missing required fields: realtor_id, property_ids"
        )
    
    with Session(engine) as session:
        # Verify realtor is managed by this PM
        realtor = session.exec(
            select(Realtor).where(
                Realtor.realtor_id == realtor_id,
                Realtor.property_manager_id == property_manager_id
            )
        ).first()
        
        if not realtor:
            raise HTTPException(
                status_code=404,
                detail="Realtor not found or not managed by this Property Manager"
            )
        
        # Get realtor's source
        realtor_source = session.exec(
            select(Source).where(Source.realtor_id == realtor_id)
        ).first()
        
        if not realtor_source:
            raise HTTPException(
                status_code=404,
                detail="Source not found for realtor"
            )
        
        # Get PM's unassigned sources (no realtor) to verify property ownership
        # Only unassigned properties can be assigned to realtors
        pm_unassigned_sources = session.exec(
            select(Source).where(
                Source.property_manager_id == property_manager_id,
                Source.realtor_id.is_(None)  # Only unassigned sources
            )
        ).all()
        pm_unassigned_source_ids = [s.source_id for s in pm_unassigned_sources]
        
        if not pm_unassigned_source_ids:
            raise HTTPException(
                status_code=400,
                detail="No unassigned properties available. All properties are already assigned to realtors."
            )
        
        # Get the properties and verify they belong to PM and are unassigned
        properties = session.exec(
            select(ApartmentListing).where(
                ApartmentListing.id.in_(property_ids),
                ApartmentListing.source_id.in_(pm_unassigned_source_ids)
            )
        ).all()
        
        if len(properties) != len(property_ids):
            raise HTTPException(
                status_code=400,
                detail=f"Some properties not found or already assigned. Found {len(properties)} unassigned properties out of {len(property_ids)} requested."
            )
        
        # Move properties to realtor's source
        for prop in properties:
            prop.source_id = realtor_source.source_id
        
        session.commit()
        
        return JSONResponse(content={
            "message": f"Successfully assigned {len(properties)} properties to realtor",
            "realtor_id": realtor_id,
            "realtor_name": realtor.name,
            "realtor_email": realtor.email,
            "property_count": len(properties),
            "assigned_property_ids": [p.id for p in properties]
        })


@app.post("/property-manager/bulk-assign-properties")
async def bulk_assign_properties_to_realtors(
    payload: dict = Body(...),
    user_data: dict = Depends(get_current_user_data)
):
    """Property Manager assigns multiple properties to multiple realtors in one call.
    
    Body:
    {
        "assignments": [
            {
                "realtor_id": 1,
                "property_ids": [1, 2, 3]
            },
            {
                "realtor_id": 2,
                "property_ids": [4, 5, 6]
            }
        ]
    }
    """
    user_type = user_data["user_type"]
    property_manager_id = user_data["id"]
    
    if user_type != "property_manager":
        raise HTTPException(
            status_code=403,
            detail="Only Property Managers can assign properties"
        )
    
    assignments = payload.get("assignments", [])
    
    if not assignments:
        raise HTTPException(
            status_code=400,
            detail="No assignments provided"
        )
    
    results = []
    
    with Session(engine) as session:
        # Get PM's sources to verify property ownership
        pm_sources = session.exec(
            select(Source).where(Source.property_manager_id == property_manager_id)
        ).all()
        pm_source_ids = [s.source_id for s in pm_sources]
        
        for assignment in assignments:
            realtor_id = assignment.get("realtor_id")
            property_ids = assignment.get("property_ids", [])
            
            if not realtor_id or not property_ids:
                results.append({
                    "realtor_id": realtor_id,
                    "status": "skipped",
                    "message": "Missing realtor_id or property_ids"
                })
                continue
            
            # Verify realtor is managed by this PM
            realtor = session.exec(
                select(Realtor).where(
                    Realtor.realtor_id == realtor_id,
                    Realtor.property_manager_id == property_manager_id
                )
            ).first()
            
            if not realtor:
                results.append({
                    "realtor_id": realtor_id,
                    "status": "error",
                    "message": "Realtor not found or not managed by this Property Manager"
                })
                continue
            
            # Get realtor's source
            realtor_source = session.exec(
                select(Source).where(Source.realtor_id == realtor_id)
            ).first()
            
            if not realtor_source:
                results.append({
                    "realtor_id": realtor_id,
                    "status": "error",
                    "message": "Source not found for realtor"
                })
                continue
            
            # Get the properties and verify they belong to PM
            properties = session.exec(
                select(ApartmentListing).where(
                    ApartmentListing.id.in_(property_ids),
                    ApartmentListing.source_id.in_(pm_source_ids)
                )
            ).all()
            
            if len(properties) != len(property_ids):
                results.append({
                    "realtor_id": realtor_id,
                    "realtor_name": realtor.name,
                    "status": "partial",
                    "message": f"Only {len(properties)} of {len(property_ids)} properties found and assigned",
                    "assigned_count": len(properties),
                    "requested_count": len(property_ids)
                })
            else:
                # Move properties to realtor's source
                for prop in properties:
                    prop.source_id = realtor_source.source_id
                
                session.commit()
                
                results.append({
                    "realtor_id": realtor_id,
                    "realtor_name": realtor.name,
                    "realtor_email": realtor.email,
                    "status": "success",
                    "message": f"Successfully assigned {len(properties)} properties",
                    "assigned_count": len(properties),
                    "assigned_property_ids": [p.id for p in properties]
                })
        
        return JSONResponse(content={
            "message": "Bulk assignment completed",
            "total_assignments": len(assignments),
            "results": results
        })


@app.post("/property-manager/unassign-properties")
async def unassign_properties_from_realtor(
    payload: dict = Body(...),
    user_data: dict = Depends(get_current_user_data)
):
    """Property Manager unassigns properties from a realtor back to themselves.
    
    Body:
    {
        "property_ids": [1, 2, 3, 4, 5]  // List of apartment listing IDs to unassign
    }
    """
    user_type = user_data["user_type"]
    property_manager_id = user_data["id"]
    
    if user_type != "property_manager":
        raise HTTPException(
            status_code=403,
            detail="Only Property Managers can unassign properties"
        )
    
    property_ids = payload.get("property_ids", [])
    
    if not property_ids:
        raise HTTPException(
            status_code=400,
            detail="Missing required field: property_ids"
        )
    
    with Session(engine) as session:
        # Get PM's sources
        pm_sources = session.exec(
            select(Source).where(Source.property_manager_id == property_manager_id)
        ).all()
        pm_source_ids = [s.source_id for s in pm_sources]
        
        if not pm_source_ids:
            raise HTTPException(
                status_code=404,
                detail="Source not found for Property Manager"
            )
        
        # Get all managed realtors' sources to verify properties belong to them
        realtors = session.exec(
            select(Realtor).where(Realtor.property_manager_id == property_manager_id)
        ).all()
        
        realtor_source_ids = []
        for realtor in realtors:
            realtor_sources = session.exec(
                select(Source).where(Source.realtor_id == realtor.realtor_id)
            ).all()
            realtor_source_ids.extend([s.source_id for s in realtor_sources])
        
        # Get the properties - they should belong to one of the realtors managed by this PM
        properties = session.exec(
            select(ApartmentListing).where(
                ApartmentListing.id.in_(property_ids),
                ApartmentListing.source_id.in_(realtor_source_ids)
            )
        ).all()
        
        if len(properties) != len(property_ids):
            raise HTTPException(
                status_code=400,
                detail="Some properties not found or don't belong to realtors managed by this Property Manager"
            )
        
        # Move properties back to PM's source (use first available PM source)
        pm_source_id = pm_source_ids[0]
        for prop in properties:
            prop.source_id = pm_source_id
        
        session.commit()
        
        return JSONResponse(content={
            "message": f"Successfully unassigned {len(properties)} properties from realtors",
            "property_count": len(properties),
            "unassigned_property_ids": [p.id for p in properties]
        })


@app.patch("/properties/{property_id}/status")
async def update_property_status(
    property_id: int,
    payload: dict = Body(...),
    user_data: dict = Depends(get_current_user_data)
):
    """Update property listing status.
    
    Allowed statuses: "Available", "For Sale", "For Rent", "Sold", "Rented"
    
    Body:
    {
        "listing_status": "Sold"  // New status value
    }
    """
    listing_status = payload.get("listing_status")
    
    if not listing_status:
        raise HTTPException(
            status_code=400,
            detail="Missing required field: listing_status"
        )
    
    # Validate status
    valid_statuses = ["Available", "For Sale", "For Rent", "Sold", "Rented"]
    if listing_status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
        )
    
    user_type = user_data["user_type"]
    user_id = user_data["id"]
    
    with Session(engine) as session:
        # Get property
        property_obj = session.exec(
            select(ApartmentListing).where(ApartmentListing.id == property_id)
        ).first()
        
        if not property_obj:
            raise HTTPException(
                status_code=404,
                detail="Property not found"
            )
        
        # Check access permissions
        source = session.exec(
            select(Source).where(Source.source_id == property_obj.source_id)
        ).first()
        
        if not source:
            raise HTTPException(
                status_code=404,
                detail="Source not found for property"
            )
        
        # Verify user has access to this property
        has_access = False
        if user_type == "property_manager":
            if source.property_manager_id == user_id:
                has_access = True
            else:
                # Check if it belongs to a realtor under this PM
                if source.realtor_id:
                    realtor = session.exec(
                        select(Realtor).where(Realtor.realtor_id == source.realtor_id)
                    ).first()
                    if realtor and realtor.property_manager_id == user_id:
                        has_access = True
        else:  # realtor
            if source.realtor_id == user_id:
                has_access = True
        
        if not has_access:
            raise HTTPException(
                status_code=403,
                detail="You don't have access to update this property"
            )
        
        # Update metadata
        meta = dict(property_obj.listing_metadata) if property_obj.listing_metadata else {}
        meta["listing_status"] = listing_status
        
        # If status is Sold or Rented, update days_on_market to current if available
        if listing_status in ["Sold", "Rented"] and meta.get("days_on_market") is not None:
            # Keep existing days_on_market, or you could calculate final days
            pass
        
        property_obj.listing_metadata = dict(meta)
        flag_modified(property_obj, "listing_metadata")
        session.commit()
        session.refresh(property_obj)
        
        return JSONResponse(content={
            "message": f"Property status updated to {listing_status}",
            "property_id": property_id,
            "new_status": listing_status,
            "updated_metadata": meta
        })


@app.patch("/properties/{property_id}/agent")
async def update_property_agent(
    property_id: int,
    payload: dict = Body(...),
    user_data: dict = Depends(get_current_user_data)
):
    """Update or remove agent information for a property.
    
    To remove agent, send: {"agent": null}
    To update agent, send: {
        "agent": {
            "name": "John Doe",
            "phone": "555-0123",
            "email": "john@example.com"
        }
    }
    """
    agent_data = payload.get("agent")
    
    user_type = user_data["user_type"]
    user_id = user_data["id"]
    
    with Session(engine) as session:
        # Get property
        property_obj = session.exec(
            select(ApartmentListing).where(ApartmentListing.id == property_id)
        ).first()
        
        if not property_obj:
            raise HTTPException(
                status_code=404,
                detail="Property not found"
            )
        
        # Check access permissions
        source = session.exec(
            select(Source).where(Source.source_id == property_obj.source_id)
        ).first()
        
        if not source:
            raise HTTPException(
                status_code=404,
                detail="Source not found for property"
            )
        
        # Verify user has access to this property
        has_access = False
        if user_type == "property_manager":
            if source.property_manager_id == user_id:
                has_access = True
            else:
                # Check if it belongs to a realtor under this PM
                if source.realtor_id:
                    realtor = session.exec(
                        select(Realtor).where(Realtor.realtor_id == source.realtor_id)
                    ).first()
                    if realtor and realtor.property_manager_id == user_id:
                        has_access = True
        else:  # realtor
            if source.realtor_id == user_id:
                has_access = True
        
        if not has_access:
            raise HTTPException(
                status_code=403,
                detail="You don't have access to update this property"
            )
        
        # Update metadata
        meta = dict(property_obj.listing_metadata) if property_obj.listing_metadata else {}
        
        if agent_data is None:
            # Remove agent
            meta.pop("agent", None)
        else:
            # Validate agent data structure
            if not isinstance(agent_data, dict):
                raise HTTPException(
                    status_code=400,
                    detail="Agent must be an object with name, phone, and email fields"
                )
            
            # Update agent
            meta["agent"] = {
                "name": agent_data.get("name", ""),
                "phone": agent_data.get("phone", ""),
                "email": agent_data.get("email", "")
            }
        
        property_obj.listing_metadata = dict(meta)
        flag_modified(property_obj, "listing_metadata")
        session.commit()
        session.refresh(property_obj)
        
        action = "removed" if agent_data is None else "updated"
        return JSONResponse(content={
            "message": f"Property agent {action} successfully",
            "property_id": property_id,
            "agent": meta.get("agent"),
            "updated_metadata": meta
        })


@app.patch("/properties/{property_id}")
async def update_property_details(
    property_id: int,
    payload: dict = Body(...),
    user_data: dict = Depends(get_current_user_data)
):
    """Update various property details (status, agent, or other metadata fields).
    
    Supports partial updates - only send fields you want to change.
    
    Body examples:
    {
        "listing_status": "Sold",
        "agent": null,  // or agent object to update/remove
        "days_on_market": 25,
        "price": 2500,
        "address": "123 Main St",
        // ... any other metadata fields
    }
    """
    try:
        user_type = user_data["user_type"]
        user_id = user_data["id"]
        
        # Validate payload is not empty
        if not payload:
            raise HTTPException(
                status_code=400,
                detail="Request body cannot be empty"
            )
        
        with Session(engine) as session:
            # Get property
            property_obj = session.exec(
                select(ApartmentListing).where(ApartmentListing.id == property_id)
            ).first()
            
            if not property_obj:
                raise HTTPException(
                    status_code=404,
                    detail=f"Property with ID {property_id} not found"
                )
            
            # Check access permissions
            source = session.exec(
                select(Source).where(Source.source_id == property_obj.source_id)
            ).first()
            
            if not source:
                raise HTTPException(
                    status_code=404,
                    detail="Source not found for property"
                )
            
            # Verify user has access to this property
            has_access = False
            if user_type == "property_manager":
                if source.property_manager_id == user_id:
                    has_access = True
                else:
                    # Check if it belongs to a realtor under this PM
                    if source.realtor_id:
                        realtor = session.exec(
                            select(Realtor).where(Realtor.realtor_id == source.realtor_id)
                        ).first()
                        if realtor and realtor.property_manager_id == user_id:
                            has_access = True
            else:  # realtor
                if source.realtor_id == user_id:
                    has_access = True
            
            if not has_access:
                raise HTTPException(
                    status_code=403,
                    detail="You don't have access to update this property"
                )
            
            # Get existing metadata (create new dict if None)
            meta = dict(property_obj.listing_metadata) if property_obj.listing_metadata else {}
            
            # Track updated fields
            updated_fields = []
            
            # Handle listing_status update with validation
            if "listing_status" in payload:
                new_status = payload["listing_status"]
                valid_statuses = ["Available", "For Sale", "For Rent", "Sold", "Rented"]
                if new_status not in valid_statuses:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid status '{new_status}'. Must be one of: {', '.join(valid_statuses)}"
                    )
                meta["listing_status"] = new_status
                updated_fields.append("listing_status")
            
            # Handle agent update/removal
            if "agent" in payload:
                agent_data = payload["agent"]
                if agent_data is None:
                    meta.pop("agent", None)
                    updated_fields.append("agent")
                else:
                    if not isinstance(agent_data, dict):
                        raise HTTPException(
                            status_code=400,
                            detail="Agent must be an object with name, phone, and email fields"
                        )
                    meta["agent"] = {
                        "name": agent_data.get("name", ""),
                        "phone": agent_data.get("phone", ""),
                        "email": agent_data.get("email", "")
                    }
                    updated_fields.append("agent")
            
            # Update other metadata fields (price, days_on_market, etc.)
            updatable_fields = [
                "price", "bedrooms", "bathrooms", "square_feet", "lot_size_sqft",
                "year_built", "property_type", "days_on_market", "listing_date",
                "features", "description", "image_url", "address", "listing_id"
            ]
            
            for field in updatable_fields:
                if field in payload:
                    value = payload[field]
                    # Only update if value is not None (allow empty strings and 0)
                    if value is not None:
                        meta[field] = value
                        if field not in updated_fields:
                            updated_fields.append(field)
            
            # Update the property object with new metadata dict
            # Create a new dict to ensure SQLAlchemy detects the change
            property_obj.listing_metadata = dict(meta)
            
            # Mark the JSONB field as modified so SQLAlchemy detects the change
            flag_modified(property_obj, "listing_metadata")
            
            # Add to session and commit
            session.add(property_obj)
            session.commit()
            session.refresh(property_obj)
            
            # Get updated metadata for response
            updated_meta = property_obj.listing_metadata or {}
            
            # Return response with updated property data
            return JSONResponse(content={
                "message": "Property updated successfully",
                "property_id": property_id,
                "updated_fields": updated_fields,
                "property": {
                    "id": property_obj.id,
                    "address": updated_meta.get("address"),
                    "price": updated_meta.get("price"),
                    "bedrooms": updated_meta.get("bedrooms"),
                    "bathrooms": updated_meta.get("bathrooms"),
                    "square_feet": updated_meta.get("square_feet"),
                    "lot_size_sqft": updated_meta.get("lot_size_sqft"),
                    "year_built": updated_meta.get("year_built"),
                    "property_type": updated_meta.get("property_type"),
                    "listing_status": updated_meta.get("listing_status"),
                    "days_on_market": updated_meta.get("days_on_market"),
                    "listing_date": updated_meta.get("listing_date"),
                    "listing_id": updated_meta.get("listing_id"),
                    "features": updated_meta.get("features", []),
                    "description": updated_meta.get("description"),
                    "image_url": updated_meta.get("image_url"),
                    "agent": updated_meta.get("agent")
                }
            }, status_code=200)
            
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Log unexpected errors
        import traceback
        print(f"Error updating property {property_id}: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error while updating property: {str(e)}"
        )


@app.delete("/properties/{property_id}")
async def delete_property(
    property_id: int,
    user_data: dict = Depends(get_current_user_data)
):
    """Delete a property. Only Property Managers can delete properties (their own or from their realtors)."""
    user_type = user_data["user_type"]
    user_id = user_data["id"]
    
    if user_type != "property_manager":
        raise HTTPException(
            status_code=403,
            detail="Only Property Managers can delete properties"
        )
    
    with Session(engine) as session:
        # Get property
        property_obj = session.exec(
            select(ApartmentListing).where(ApartmentListing.id == property_id)
        ).first()
        
        if not property_obj:
            raise HTTPException(
                status_code=404,
                detail="Property not found"
            )
        
        # Check access permissions - PM can delete their own properties or properties from their realtors
        source = session.exec(
            select(Source).where(Source.source_id == property_obj.source_id)
        ).first()
        
        if not source:
            raise HTTPException(
                status_code=404,
                detail="Source not found for property"
            )
        
        # Verify PM has access to this property
        has_access = False
        if source.property_manager_id == user_id:
            has_access = True
        else:
            # Check if it belongs to a realtor under this PM
            if source.realtor_id:
                realtor = session.exec(
                    select(Realtor).where(Realtor.realtor_id == source.realtor_id)
                ).first()
                if realtor and realtor.property_manager_id == user_id:
                    has_access = True
        
        if not has_access:
            raise HTTPException(
                status_code=403,
                detail="You don't have access to delete this property"
            )
        
        # Get property details for response
        meta = property_obj.listing_metadata or {}
        property_address = meta.get("address", f"Property #{property_id}")
        
        # Delete the property
        session.delete(property_obj)
        session.commit()
        
        return JSONResponse(content={
            "message": f"Property '{property_address}' deleted successfully",
            "property_id": property_id,
            "deleted_address": property_address
        })


@app.delete("/property-manager/realtors/{realtor_id}")
async def delete_realtor(
    realtor_id: int,
    user_data: dict = Depends(get_current_user_data)
):
    """Property Manager deletes a realtor/agent.
    
    When a realtor is deleted:
    1. All properties assigned to them become unassigned (moved back to PM)
    2. All bookings are unassigned (realtor_id set to NULL)
    3. All sources belonging to the realtor are deleted (after properties are moved)
    4. All rule chunks for those sources are deleted
    5. The realtor record is deleted from the database
    
    Note: This does NOT delete the user from Supabase Auth (they can still login but won't have access to the system).
    """
    user_type = user_data["user_type"]
    property_manager_id = user_data["id"]
    
    if user_type != "property_manager":
        raise HTTPException(
            status_code=403,
            detail="Only Property Managers can delete realtors"
        )
    
    with Session(engine) as session:
        # Verify realtor is managed by this PM
        realtor = session.exec(
            select(Realtor).where(
                Realtor.realtor_id == realtor_id,
                Realtor.property_manager_id == property_manager_id
            )
        ).first()
        
        if not realtor:
            raise HTTPException(
                status_code=404,
                detail="Realtor not found or not managed by this Property Manager"
            )
        
        realtor_name = realtor.name
        realtor_email = realtor.email
        
        # Step 1: Get all sources belonging to this realtor
        realtor_sources = session.exec(
            select(Source).where(Source.realtor_id == realtor_id)
        ).all()
        realtor_source_ids = [s.source_id for s in realtor_sources]
        
        # Step 2: Get PM's sources (to move properties back)
        pm_sources = session.exec(
            select(Source).where(Source.property_manager_id == property_manager_id)
        ).all()
        
        if not pm_sources:
            raise HTTPException(
                status_code=404,
                detail="Property Manager source not found. Cannot reassign properties."
            )
        
        pm_source_id = pm_sources[0].source_id  # Use first PM source
        
        # Step 3: Get all properties assigned to this realtor and move them to PM
        properties_to_reassign = []
        if realtor_source_ids:
            properties = session.exec(
                select(ApartmentListing).where(ApartmentListing.source_id.in_(realtor_source_ids))
            ).all()
            
            for prop in properties:
                prop.source_id = pm_source_id
                properties_to_reassign.append(prop.id)
        
        # Step 4: Unassign bookings (set realtor_id to NULL)
        bookings = session.exec(
            select(Booking).where(Booking.realtor_id == realtor_id)
        ).all()
        
        bookings_unassigned = []
        for booking in bookings:
            booking.realtor_id = None
            bookings_unassigned.append(booking.id)
        
        # Step 5: Delete rule chunks for realtor's sources
        rule_chunks_deleted = 0
        if realtor_source_ids:
            rule_chunks = session.exec(
                select(RuleChunk).where(RuleChunk.source_id.in_(realtor_source_ids))
            ).all()
            
            for chunk in rule_chunks:
                session.delete(chunk)
                rule_chunks_deleted += 1
        
        # Step 6: Delete sources belonging to the realtor
        sources_deleted = len(realtor_sources)
        for source in realtor_sources:
            session.delete(source)
        
        # Step 7: Delete the realtor record
        session.delete(realtor)
        
        # Commit all changes
        session.commit()
        
        return JSONResponse(content={
            "message": f"Realtor '{realtor_name}' deleted successfully",
            "realtor_id": realtor_id,
            "realtor_name": realtor_name,
            "realtor_email": realtor_email,
            "summary": {
                "properties_reassigned": len(properties_to_reassign),
                "properties_reassigned_ids": properties_to_reassign,
                "bookings_unassigned": len(bookings_unassigned),
                "bookings_unassigned_ids": bookings_unassigned,
                "rule_chunks_deleted": rule_chunks_deleted,
                "sources_deleted": sources_deleted
            },
            "note": "The user account in Supabase Auth still exists. They cannot access the system but their auth account remains."
        })


@app.patch("/property-manager/realtors/{realtor_id}")
async def update_realtor(
    realtor_id: int,
    payload: dict = Body(...),
    user_data: dict = Depends(get_current_user_data)
):
    """Property Manager updates a realtor's details (name, contact, email, password)."""
    user_type = user_data["user_type"]
    property_manager_id = user_data["id"]
    
    if user_type != "property_manager":
        raise HTTPException(
            status_code=403,
            detail="Only Property Managers can update realtors"
        )
    
    with Session(engine) as session:
        # Verify realtor is managed by this PM
        realtor = session.exec(
            select(Realtor).where(
                Realtor.realtor_id == realtor_id,
                Realtor.property_manager_id == property_manager_id
            )
        ).first()
        
        if not realtor:
            raise HTTPException(
                status_code=404,
                detail="Realtor not found or not managed by this Property Manager"
            )
        
        # Track what was updated
        updated_fields = []
        auth_user_id = str(realtor.auth_user_id)
        
        # Update name if provided
        if "name" in payload and payload["name"]:
            realtor.name = payload["name"]
            updated_fields.append("name")
        
        # Update contact if provided
        if "contact" in payload and payload["contact"]:
            realtor.contact = payload["contact"]
            updated_fields.append("contact")
        
        # Update email if provided (requires Supabase update)
        if "email" in payload and payload["email"]:
            new_email = payload["email"]
            if new_email != realtor.email:
                try:
                    # Update email in Supabase Auth using Admin API
                    from config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
                    update_data = {"email": new_email}
                    response = httpx.put(
                        f"{SUPABASE_URL}/auth/v1/admin/users/{auth_user_id}",
                        headers={
                            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
                            "apikey": SUPABASE_SERVICE_ROLE_KEY,
                            "Content-Type": "application/json"
                        },
                        json=update_data,
                        timeout=10.0
                    )
                    if response.status_code not in [200, 201]:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Failed to update email in authentication: {response.text}"
                        )
                    realtor.email = new_email
                    updated_fields.append("email")
                except Exception as e:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Failed to update email in authentication: {str(e)}"
                    )
        
        # Update password if provided (requires Supabase update)
        if "password" in payload and payload["password"]:
            new_password = payload["password"]
            try:
                # Update password in Supabase Auth using Admin API
                from config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
                update_data = {"password": new_password}
                response = httpx.put(
                    f"{SUPABASE_URL}/auth/v1/admin/users/{auth_user_id}",
                    headers={
                        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
                        "apikey": SUPABASE_SERVICE_ROLE_KEY,
                        "Content-Type": "application/json"
                    },
                    json=update_data,
                    timeout=10.0
                )
                if response.status_code not in [200, 201]:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Failed to update password in authentication: {response.text}"
                    )
                updated_fields.append("password")
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to update password in authentication: {str(e)}"
                )
        
        # Update timestamp
        realtor.updated_at = datetime.utcnow()
        
        # Commit database changes
        session.add(realtor)
        session.commit()
        session.refresh(realtor)
        
        return JSONResponse(content={
            "message": f"Realtor updated successfully",
            "realtor_id": realtor_id,
            "updated_fields": updated_fields,
            "realtor": {
                "id": realtor.realtor_id,
                "name": realtor.name,
                "email": realtor.email,
                "contact": realtor.contact
            }
        })


# ---------------------- TEST USER MANAGEMENT ----------------------

@app.post("/create-test-team")
async def create_test_team():
    """Create a test team: 1 Property Manager + 2 Realtors (for development only)."""
    try:
        from utils.password_manager import PasswordManager
        password_manager = PasswordManager()
        
        result = password_manager.create_test_team()
        
        if result["success"]:
            return JSONResponse(content={
                "message": "Test team created successfully!",
                "created_users": result["created_users"],
                "total_users": result["total_users"],
                "test_credentials": result["test_credentials"]
            })
        else:
            return JSONResponse(
                content={"error": "Failed to create test team", "details": result},
                status_code=500
            )
            
    except Exception as e:
        return JSONResponse(
            content={"error": f"Failed to create test team: {str(e)}"},
            status_code=500
        )


@app.get("/test-users")
async def list_test_users():
    """List all test users with their credentials (for development only)."""
    try:
        from utils.password_manager import PasswordManager
        password_manager = PasswordManager()
        
        users = password_manager.list_all_test_users()
        
        return JSONResponse(content={
            "test_users": users,
            "count": len(users)
        })
        
    except Exception as e:
        return JSONResponse(
            content={"error": f"Failed to list test users: {str(e)}"},
            status_code=500
        )


@app.post("/reset-test-users")
async def reset_test_users():
    """Reset all test users (for development only)."""
    try:
        from utils.password_manager import PasswordManager
        password_manager = PasswordManager()
        
        password_manager.reset_test_users()
        
        return JSONResponse(content={
            "message": "All test users have been reset successfully!"
        })
        
    except Exception as e:
        return JSONResponse(
            content={"error": f"Failed to reset test users: {str(e)}"},
            status_code=500
        )


@app.get("/bookings")
async def get_bookings(user_data: dict = Depends(get_current_user_data)):
    """Get bookings based on user type and data access scope."""
    user_type = user_data["user_type"]
    user_id = user_data["id"]
    
    print(f"Getting bookings for {user_type} ID: {user_id}")

    with Session(engine) as session:
        if user_type == "property_manager":
            # Property managers can see bookings from all their realtors
            realtors = session.exec(
                select(Realtor).where(Realtor.property_manager_id == user_id)
            ).all()
            realtor_ids = [r.realtor_id for r in realtors]
            
            if not realtor_ids:
                return JSONResponse(content={"bookings": []})
            
            bookings = session.exec(
                select(Booking).where(Booking.realtor_id.in_(realtor_ids))
            ).all()
        else:
            # Realtors can only see their own bookings
            bookings = session.exec(
                select(Booking).where(Booking.realtor_id == user_id)
            ).all()

        # Transform bookings for response
        result = []
        for booking in bookings:
            result.append({
                "id": booking.id,
                "address": booking.address,
                "date": booking.date.isoformat() if booking.date else None,
                "time": booking.time.isoformat() if booking.time else None,
                "visited": booking.visited,
                "customer_feedback": booking.cust_feedback,
                "customer_id": booking.cust_id,
                "realtor_id": booking.realtor_id,
            })

        return JSONResponse(content={"bookings": result})


def get_db():
    with Session(engine) as session:
        yield session


# ============================================================================
# DEMO REQUEST SYSTEM (Public - No Auth Required)
# ============================================================================
# Replaces sign-up with "Book a Demo" functionality

@app.post("/book-demo")
def book_demo(
    name: str = Body(...),
    email: str = Body(...),
    phone: str = Body(...),
    company_name: Optional[str] = Body(None),
    preferred_date: Optional[str] = Body(None),  # ISO format: "2024-01-15"
    preferred_time: Optional[str] = Body(None),  # e.g., "10:00 AM"
    timezone: Optional[str] = Body(None),  # e.g., "America/New_York"
    notes: Optional[str] = Body(None),
):
    """
    Public endpoint to book a demo. No authentication required.
    Anyone can submit a demo request.
    """
    from datetime import date as date_type
    
    try:
        # Parse preferred_date if provided
        parsed_date = None
        if preferred_date:
            try:
                parsed_date = datetime.strptime(preferred_date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid date format. Use YYYY-MM-DD format."
                )
        
        with Session(engine) as session:
            # Create demo request
            demo_request = DemoRequest(
                name=name,
                email=email,
                phone=phone,
                company_name=company_name,
                preferred_date=parsed_date,
                preferred_time=preferred_time,
                timezone=timezone,
                notes=notes,
                status="pending"
            )
            
            session.add(demo_request)
            session.commit()
            session.refresh(demo_request)
            
            return JSONResponse(content={
                "message": "Thank you for your interest! We've received your demo request and will contact you soon to schedule a time.",
                "demo_request_id": demo_request.demo_request_id,
                "status": demo_request.status,
                "requested_at": demo_request.requested_at.isoformat() if demo_request.requested_at else None,
            })
            
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error creating demo request: {error_msg}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error submitting demo request: {error_msg}"
        )


@app.get("/demo-requests")
def get_demo_requests(
    status: Optional[str] = None,  # Filter by status: pending, scheduled, completed, cancelled, converted
    # In production, add admin authentication here
):
    """
    Admin endpoint to view all demo requests.
    In production, this should be protected with admin authentication.
    """
    with Session(engine) as session:
        query = select(DemoRequest)
        if status:
            query = query.where(DemoRequest.status == status)
        query = query.order_by(DemoRequest.requested_at.desc())
        
        requests = session.exec(query).all()
        
        return JSONResponse(content={
            "demo_requests": [
                {
                    "demo_request_id": req.demo_request_id,
                    "name": req.name,
                    "email": req.email,
                    "phone": req.phone,
                    "company_name": req.company_name,
                    "preferred_date": req.preferred_date.isoformat() if req.preferred_date else None,
                    "preferred_time": req.preferred_time,
                    "timezone": req.timezone,
                    "notes": req.notes,
                    "status": req.status,
                    "scheduled_at": req.scheduled_at.isoformat() if req.scheduled_at else None,
                    "completed_at": req.completed_at.isoformat() if req.completed_at else None,
                    "converted_to_pm_id": req.converted_to_pm_id,
                    "converted_at": req.converted_at.isoformat() if req.converted_at else None,
                    "requested_at": req.requested_at.isoformat() if req.requested_at else None,
                }
                for req in requests
            ]
        })


@app.patch("/demo-requests/{demo_request_id}")
def update_demo_request(
    demo_request_id: int,
    status: Optional[str] = Body(None),
    scheduled_at: Optional[str] = Body(None),  # ISO format datetime
    completed_at: Optional[str] = Body(None),  # ISO format datetime
    converted_to_pm_id: Optional[int] = Body(None),
    notes: Optional[str] = Body(None),
    # In production, add admin authentication here
):
    """
    Admin endpoint to update demo request status.
    In production, this should be protected with admin authentication.
    """
    with Session(engine) as session:
        demo_request = session.get(DemoRequest, demo_request_id)
        if not demo_request:
            raise HTTPException(status_code=404, detail="Demo request not found")
        
        # Update status
        if status:
            if status not in ["pending", "scheduled", "completed", "cancelled", "converted"]:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid status. Must be: pending, scheduled, completed, cancelled, or converted"
                )
            demo_request.status = status
        
        # Update scheduled_at
        if scheduled_at:
            try:
                demo_request.scheduled_at = datetime.fromisoformat(scheduled_at.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid scheduled_at format. Use ISO format datetime."
                )
        
        # Update completed_at
        if completed_at:
            try:
                demo_request.completed_at = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid completed_at format. Use ISO format datetime."
                )
        
        # Update converted_to_pm_id
        if converted_to_pm_id is not None:
            # Verify PM exists
            pm = session.get(PropertyManager, converted_to_pm_id)
            if not pm:
                raise HTTPException(status_code=404, detail="Property Manager not found")
            demo_request.converted_to_pm_id = converted_to_pm_id
            demo_request.converted_at = datetime.utcnow()
            demo_request.status = "converted"
        
        # Update notes
        if notes is not None:
            demo_request.notes = notes
        
        demo_request.updated_at = datetime.utcnow()
        
        session.add(demo_request)
        session.commit()
        session.refresh(demo_request)
        
        return JSONResponse(content={
            "message": "Demo request updated successfully",
            "demo_request_id": demo_request.demo_request_id,
            "status": demo_request.status,
            "scheduled_at": demo_request.scheduled_at.isoformat() if demo_request.scheduled_at else None,
            "completed_at": demo_request.completed_at.isoformat() if demo_request.completed_at else None,
            "converted_to_pm_id": demo_request.converted_to_pm_id,
        })


# ============================================================================
# PHONE NUMBER REQUEST & ASSIGNMENT SYSTEM
# ============================================================================
# New system: PM requests numbers, tech team purchases, PM assigns to self/realtors

@app.post("/request-phone-number")
def request_phone_number(
    country_code: Optional[str] = Body(None),
    area_code: Optional[str] = Body(None),
    notes: Optional[str] = Body(None),
    user_data: dict = Depends(get_current_user_data),
):
    """
    Property Manager requests a phone number.
    Returns message that number will be available in 24 hours.
    """
    user_type = user_data.get("user_type")
    user_id = user_data.get("id")
    
    if user_type != "property_manager":
        raise HTTPException(
            status_code=403,
            detail="Only Property Managers can request phone numbers"
        )
    
    with Session(engine) as session:
        pm = session.get(PropertyManager, user_id)
        if not pm:
            raise HTTPException(status_code=404, detail="Property Manager not found")
        
        # Normalize country code (remove + if present, keep it consistent)
        normalized_country_code = None
        if country_code:
            # Remove + and spaces, keep just digits
            normalized_country_code = country_code.replace("+", "").strip()
            if normalized_country_code:
                # Add + back for display consistency
                normalized_country_code = f"+{normalized_country_code}"
        
        # Create request
        request = PhoneNumberRequest(
            property_manager_id=user_id,
            country_code=normalized_country_code,
            area_code=area_code,
            notes=notes,
            status="pending"
        )
        
        session.add(request)
        session.commit()
        session.refresh(request)
        
        return JSONResponse(content={
            "message": "Your phone number request has been submitted successfully. A new number will be available in your portal within 24 hours.",
            "request_id": request.request_id,
            "country_code": request.country_code,
            "area_code": request.area_code,
            "status": request.status,
            "requested_at": request.requested_at.isoformat() if request.requested_at else None,
        })


@app.get("/my-phone-number-requests")
def get_my_phone_number_requests(
    user_data: dict = Depends(get_current_user_data),
):
    """Get all phone number requests for the current Property Manager."""
    user_type = user_data.get("user_type")
    user_id = user_data.get("id")
    
    if user_type != "property_manager":
        raise HTTPException(
            status_code=403,
            detail="Only Property Managers can view phone number requests"
        )
    
    with Session(engine) as session:
        requests = session.exec(
            select(PhoneNumberRequest)
            .where(PhoneNumberRequest.property_manager_id == user_id)
            .order_by(PhoneNumberRequest.requested_at.desc())
        ).all()
        
        return JSONResponse(content={
            "requests": [
                {
                    "request_id": req.request_id,
                    "country_code": req.country_code,
                    "area_code": req.area_code,
                    "status": req.status,
                    "notes": req.notes,
                    "requested_at": req.requested_at.isoformat() if req.requested_at else None,
                    "fulfilled_at": req.fulfilled_at.isoformat() if req.fulfilled_at else None,
                }
                for req in requests
            ]
        })


@app.get("/purchased-phone-numbers")
def get_purchased_phone_numbers(
    user_data: dict = Depends(get_current_user_data),
):
    """
    Get all purchased phone numbers available for assignment.
    Only shows numbers for the current Property Manager.
    """
    user_type = user_data.get("user_type")
    user_id = user_data.get("id")
    
    if user_type != "property_manager":
        raise HTTPException(
            status_code=403,
            detail="Only Property Managers can view purchased phone numbers"
        )
    
    with Session(engine) as session:
        # Get all purchased numbers for this PM
        purchased_numbers = session.exec(
            select(PurchasedPhoneNumber)
            .where(PurchasedPhoneNumber.property_manager_id == user_id)
            .order_by(PurchasedPhoneNumber.purchased_at.desc())
        ).all()
        
        # Get realtors for assignment options
        realtors = session.exec(
            select(Realtor)
            .where(Realtor.property_manager_id == user_id)
        ).all()
        
        return JSONResponse(content={
            "purchased_numbers": [
                {
                    "purchased_phone_number_id": pn.purchased_phone_number_id,
                    "phone_number": pn.phone_number,
                    "status": pn.status,
                    "assigned_to_type": pn.assigned_to_type,
                    "assigned_to_id": pn.assigned_to_id,
                    "purchased_at": pn.purchased_at.isoformat() if pn.purchased_at else None,
                    "assigned_at": pn.assigned_at.isoformat() if pn.assigned_at else None,
                }
                for pn in purchased_numbers
            ],
            "available_for_assignment": [
                {
                    "purchased_phone_number_id": pn.purchased_phone_number_id,
                    "phone_number": pn.phone_number,
                    "purchased_at": pn.purchased_at.isoformat() if pn.purchased_at else None,
                }
                for pn in purchased_numbers
                if pn.status == "available"
            ],
            "realtors": [
                {
                    "realtor_id": r.realtor_id,
                    "name": r.name,
                    "email": r.email,
                    "twilio_number": _normalize_bot_number(r.twilio_contact),
                    "forwarding_state": _serialize_forwarding_state(r),
                }
                for r in realtors
            ],
        })


@app.post("/assign-phone-number")
def assign_phone_number(
    purchased_phone_number_id: int = Body(...),
    assign_to_type: str = Body(...),  # "property_manager" or "realtor"
    assign_to_id: Optional[int] = Body(None),  # Required if assign_to_type is "realtor"
    user_data: dict = Depends(get_current_user_data),
):
    """
    Property Manager assigns a purchased phone number to themselves or a realtor.
    """
    user_type = user_data.get("user_type")
    user_id = user_data.get("id")
    
    if user_type != "property_manager":
        raise HTTPException(
            status_code=403,
            detail="Only Property Managers can assign phone numbers"
        )
    
    if assign_to_type not in ["property_manager", "realtor"]:
        raise HTTPException(
            status_code=400,
            detail="assign_to_type must be 'property_manager' or 'realtor'"
        )
    
    if assign_to_type == "realtor" and not assign_to_id:
        raise HTTPException(
            status_code=400,
            detail="assign_to_id is required when assign_to_type is 'realtor'"
        )
    
    with Session(engine) as session:
        target_forwarding_owner = None
        # Verify the purchased number belongs to this PM
        purchased_number = session.get(PurchasedPhoneNumber, purchased_phone_number_id)
        if not purchased_number:
            raise HTTPException(status_code=404, detail="Purchased phone number not found")
        
        if purchased_number.property_manager_id != user_id:
            raise HTTPException(
                status_code=403,
                detail="You can only assign phone numbers that belong to you"
            )
        
        if purchased_number.status != "available":
            raise HTTPException(
                status_code=400,
                detail=f"Phone number is not available for assignment (current status: {purchased_number.status})"
            )
        validated_number = _validate_bot_number_or_422(
            purchased_number.phone_number,
            field_name="Purchased phone number",
        )
        
        # Unassign any previous assignment
        if assign_to_type == "property_manager":
            # Unassign from any realtor first
            if purchased_number.assigned_to_type == "realtor" and purchased_number.assigned_to_id:
                old_realtor = session.get(Realtor, purchased_number.assigned_to_id)
                if old_realtor:
                    old_realtor.purchased_phone_number_id = None
                    old_realtor.twilio_contact = "TBD"
                    old_realtor.twilio_sid = None
                    session.add(old_realtor)
            
            # Assign to PM
            pm = session.get(PropertyManager, user_id)
            if pm:
                # Unassign from old number if any
                if pm.purchased_phone_number_id:
                    old_pn = session.get(PurchasedPhoneNumber, pm.purchased_phone_number_id)
                    if old_pn:
                        old_pn.status = "available"
                        old_pn.assigned_to_type = None
                        old_pn.assigned_to_id = None
                        old_pn.assigned_at = None
                        session.add(old_pn)
                
                pm.purchased_phone_number_id = purchased_phone_number_id
                pm.twilio_contact = validated_number
                pm.twilio_sid = purchased_number.twilio_sid
                _reset_forwarding_state(pm)
                target_forwarding_owner = pm
                session.add(pm)
                # Mark the object as modified to ensure SQLAlchemy detects the change
                flag_modified(pm, "twilio_contact")
                flag_modified(pm, "purchased_phone_number_id")
            
            purchased_number.status = "assigned"
            purchased_number.assigned_to_type = "property_manager"
            purchased_number.assigned_to_id = user_id
            purchased_number.assigned_at = datetime.utcnow()
            
        elif assign_to_type == "realtor":
            # Verify realtor belongs to this PM
            realtor = session.get(Realtor, assign_to_id)
            if not realtor:
                raise HTTPException(status_code=404, detail="Realtor not found")
            
            if realtor.property_manager_id != user_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only assign numbers to your own realtors"
                )
            
            # Unassign from PM if assigned
            if purchased_number.assigned_to_type == "property_manager" and purchased_number.assigned_to_id:
                old_pm = session.get(PropertyManager, purchased_number.assigned_to_id)
                if old_pm:
                    old_pm.purchased_phone_number_id = None
                    old_pm.twilio_contact = "TBD"
                    old_pm.twilio_sid = None
                    session.add(old_pm)
            
            # Unassign from old number if realtor has one
            if realtor.purchased_phone_number_id:
                old_pn = session.get(PurchasedPhoneNumber, realtor.purchased_phone_number_id)
                if old_pn:
                    old_pn.status = "available"
                    old_pn.assigned_to_type = None
                    old_pn.assigned_to_id = None
                    old_pn.assigned_at = None
                    session.add(old_pn)
            
            # Assign to realtor
            realtor.purchased_phone_number_id = purchased_phone_number_id
            realtor.twilio_contact = validated_number
            realtor.twilio_sid = purchased_number.twilio_sid
            _reset_forwarding_state(realtor)
            target_forwarding_owner = realtor
            session.add(realtor)
            # Mark the object as modified to ensure SQLAlchemy detects the change
            flag_modified(realtor, "twilio_contact")
            flag_modified(realtor, "purchased_phone_number_id")
            flag_modified(realtor, "twilio_sid")
            
            purchased_number.status = "assigned"
            purchased_number.assigned_to_type = "realtor"
            purchased_number.assigned_to_id = assign_to_id
            purchased_number.assigned_at = datetime.utcnow()
        
        session.add(purchased_number)
        
        try:
            session.commit()
            # Refresh both objects to ensure they're up to date
            session.refresh(purchased_number)
            if assign_to_type == "realtor" and realtor:
                session.refresh(realtor)
                # Double-check that the update persisted
                if realtor.twilio_contact != purchased_number.phone_number:
                    print(f"⚠️  Warning: Realtor twilio_contact not updated. Expected: {purchased_number.phone_number}, Got: {realtor.twilio_contact}")
                    # Try to fix it
                    realtor.twilio_contact = purchased_number.phone_number
                    flag_modified(realtor, "twilio_contact")
                    session.add(realtor)
                    session.commit()
                    session.refresh(realtor)
            elif assign_to_type == "property_manager" and pm:
                session.refresh(pm)
                # Double-check that the update persisted
                if pm.twilio_contact != purchased_number.phone_number:
                    print(f"⚠️  Warning: PM twilio_contact not updated. Expected: {purchased_number.phone_number}, Got: {pm.twilio_contact}")
                    # Try to fix it
                    pm.twilio_contact = purchased_number.phone_number
                    flag_modified(pm, "twilio_contact")
                    session.add(pm)
                    session.commit()
                    session.refresh(pm)
        except Exception as commit_error:
            session.rollback()
            print(f"❌ Database commit error during assign: {commit_error}")
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail=f"Database error: Failed to save assignment. {str(commit_error)}"
            )
        
        return JSONResponse(content={
            "message": f"Phone number {purchased_number.phone_number} has been successfully assigned",
            "purchased_phone_number_id": purchased_phone_number_id,
            "phone_number": purchased_number.phone_number,
            "assigned_to_type": purchased_number.assigned_to_type,
            "assigned_to_id": purchased_number.assigned_to_id,
            "assigned_at": purchased_number.assigned_at.isoformat() if purchased_number.assigned_at else None,
            "forwarding_state": _serialize_forwarding_state(target_forwarding_owner) if target_forwarding_owner else None,
        })


@app.post("/unassign-phone-number")
def unassign_phone_number(
    request: UnassignPhoneNumberRequest,
    user_data: dict = Depends(get_current_user_data),
):
    """
    Property Manager unassigns a phone number, making it available again.
    
    This will:
    - Remove the number from the current assignee (PM or Realtor)
    - Set the number status back to "available"
    - Clear assignment details
    """
    try:
        # Validate user_data
        if not user_data:
            raise HTTPException(
                status_code=401,
                detail="User authentication failed"
            )
        
        user_type = user_data.get("user_type")
        user_id = user_data.get("id")
        
        if not user_type or not user_id:
            raise HTTPException(
                status_code=401,
                detail="Invalid user data"
            )
        
        if user_type != "property_manager":
            raise HTTPException(
                status_code=403,
                detail="Only Property Managers can unassign phone numbers"
            )
        
        with Session(engine) as session:
            # Verify the purchased number belongs to this PM
            purchased_phone_number_id = request.purchased_phone_number_id
            purchased_number = session.get(PurchasedPhoneNumber, purchased_phone_number_id)
            if not purchased_number:
                raise HTTPException(status_code=404, detail="Purchased phone number not found")
            
            if purchased_number.property_manager_id != user_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only unassign phone numbers that belong to you"
                )
            
            if purchased_number.status != "assigned":
                raise HTTPException(
                    status_code=400,
                    detail=f"Phone number is not currently assigned (status: {purchased_number.status})"
                )
            
            # Unassign from current assignee
            phone_number_str = str(purchased_number.phone_number)
            previous_assignee_name = None
            
            if purchased_number.assigned_to_type == "property_manager" and purchased_number.assigned_to_id:
                pm = session.get(PropertyManager, purchased_number.assigned_to_id)
                if pm:
                    pm.purchased_phone_number_id = None
                    pm.twilio_contact = "TBD"
                    pm.twilio_sid = None
                    _reset_forwarding_state(pm)
                    session.add(pm)
                    previous_assignee_name = pm.name
            
            elif purchased_number.assigned_to_type == "realtor" and purchased_number.assigned_to_id:
                realtor = session.get(Realtor, purchased_number.assigned_to_id)
                if realtor:
                    # Verify realtor belongs to this PM
                    if realtor.property_manager_id != user_id:
                        raise HTTPException(
                            status_code=403,
                            detail="Cannot unassign number from a realtor that doesn't belong to you"
                        )
                    realtor.purchased_phone_number_id = None
                    realtor.twilio_contact = "TBD"
                    realtor.twilio_sid = None
                    _reset_forwarding_state(realtor)
                    session.add(realtor)
                    previous_assignee_name = realtor.name
            
            # Mark number as available
            purchased_number.status = "available"
            purchased_number.assigned_to_type = None
            purchased_number.assigned_to_id = None
            purchased_number.assigned_at = None
            session.add(purchased_number)
            
            try:
                session.commit()
                session.refresh(purchased_number)
            except Exception as db_error:
                session.rollback()
                print(f"❌ Database error during unassign: {db_error}")
                import traceback
                traceback.print_exc()
                raise HTTPException(
                    status_code=500,
                    detail=f"Database error: Failed to save changes. {str(db_error)}"
                )
            
            # Return response matching the format of assign-phone-number endpoint
            # Ensure all values are JSON-serializable
            response_data = {
                "message": f"Phone number {phone_number_str} has been unassigned and is now available",
                "purchased_phone_number_id": int(purchased_phone_number_id),
                "phone_number": str(phone_number_str),
                "status": "available",
                "previous_assignee": previous_assignee_name,  # Who it was assigned to before
            }
            
            return JSONResponse(
                content=response_data,
                status_code=200,
                media_type="application/json"
            )
            
    except HTTPException as he:
        # Re-raise HTTPExceptions as-is (FastAPI handles these properly)
        raise he
    except Exception as e:
        # Log the full error for debugging
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ Unexpected error in unassign_phone_number: {error_trace}")
        
        # Return a properly formatted error response
        error_message = str(e) if e else "Unknown error occurred"
        raise HTTPException(
            status_code=500,
            detail=f"Error unassigning phone number: {error_message}"
        )


# ============================================================================
# SYNC ENDPOINT (Fix Data Inconsistency)
# ============================================================================

@app.post("/sync-realtor-phone-number")
def sync_realtor_phone_number(
    realtor_id: int = Body(...),
    user_data: dict = Depends(get_current_user_data),
):
    """
    Sync realtor's twilio_contact from their assigned purchased phone number.
    This fixes cases where the assignment worked but twilio_contact wasn't updated.
    """
    user_type = user_data.get("user_type")
    user_id = user_data.get("id")
    
    if user_type != "property_manager":
        raise HTTPException(
            status_code=403,
            detail="Only Property Managers can sync realtor phone numbers"
        )
    
    with Session(engine) as session:
        # Get realtor
        realtor = session.get(Realtor, realtor_id)
        if not realtor:
            raise HTTPException(status_code=404, detail="Realtor not found")
        
        # Verify realtor belongs to this PM
        if realtor.property_manager_id != user_id:
            raise HTTPException(
                status_code=403,
                detail="You can only sync phone numbers for your own realtors"
            )
        
        # Check if realtor has an assigned phone number
        if not realtor.purchased_phone_number_id:
            raise HTTPException(
                status_code=400,
                detail="Realtor does not have an assigned phone number"
            )
        
        # Get the purchased phone number
        purchased_number = session.get(PurchasedPhoneNumber, realtor.purchased_phone_number_id)
        if not purchased_number:
            raise HTTPException(
                status_code=404,
                detail="Assigned phone number not found"
            )
        
        # Sync the contact number
        realtor.twilio_contact = purchased_number.phone_number
        realtor.twilio_sid = purchased_number.twilio_sid
        flag_modified(realtor, "twilio_contact")
        flag_modified(realtor, "twilio_sid")
        session.add(realtor)
        
        try:
            session.commit()
            session.refresh(realtor)
        except Exception as e:
            session.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to sync phone number: {str(e)}"
            )
        
        return JSONResponse(content={
            "message": f"Realtor {realtor.name}'s phone number has been synced",
            "realtor_id": realtor_id,
            "realtor_name": realtor.name,
            "phone_number": realtor.twilio_contact,
        })


# ============================================================================
# ADMIN ENDPOINTS (For Tech Team)
# ============================================================================

@app.post("/admin/add-purchased-number")
def admin_add_purchased_number(
    property_manager_id: int = Body(...),
    phone_number: str = Body(...),  # E.164 format: +14125551234
    twilio_sid: Optional[str] = Body(None),  # Twilio SID (optional - if purchased from Twilio)
    vapi_phone_number_id: Optional[str] = Body(None),  # VAPI phone number ID (optional - if registered with VAPI)
    notes: Optional[str] = Body(None),
    # In production, add admin authentication here
):
    """
    Simple endpoint for tech team to add a purchased phone number to the database.
    Tech team can purchase from any platform (Twilio, other providers, etc.) and then
    add the number details here. The number will appear as "available" for the PM to assign.
    
    This is simpler than /admin/purchase-phone-number which actually purchases from Twilio.
    Use this when you've already purchased the number from another platform.
    """
    with Session(engine) as session:
        # Verify PM exists
        pm = session.get(PropertyManager, property_manager_id)
        if not pm:
            raise HTTPException(status_code=404, detail="Property Manager not found")
        
        # Validate phone number format (basic check)
        phone_number = phone_number.strip()
        if not phone_number.startswith("+"):
            # Try to add + if missing
            if phone_number.startswith("1") and len(phone_number) == 11:
                phone_number = f"+{phone_number}"
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Phone number should be in E.164 format (e.g., +14125551234)"
                )
        
        # Check if phone number already exists
        existing = session.exec(
            select(PurchasedPhoneNumber).where(PurchasedPhoneNumber.phone_number == phone_number)
        ).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Phone number {phone_number} already exists in database"
            )
        
        # Create purchased number record
        # Generate a unique SID if not provided (for non-Twilio numbers)
        final_twilio_sid = twilio_sid or f"MANUAL_{phone_number.replace('+', '').replace('-', '').replace(' ', '')}"
        
        purchased_number = PurchasedPhoneNumber(
            property_manager_id=property_manager_id,
            phone_number=phone_number,
            twilio_sid=final_twilio_sid,
            vapi_phone_number_id=vapi_phone_number_id,
            status="available",
            notes=notes or f"Added manually by tech team",
        )
        
        session.add(purchased_number)
        
        # Mark any pending requests as fulfilled
        pending_requests = session.exec(
            select(PhoneNumberRequest)
            .where(
                PhoneNumberRequest.property_manager_id == property_manager_id,
                PhoneNumberRequest.status == "pending"
            )
        ).all()
        
        for req in pending_requests:
            req.status = "fulfilled"
            req.fulfilled_at = datetime.utcnow()
            session.add(req)
        
        session.commit()
        session.refresh(purchased_number)
        
        return JSONResponse(content={
            "message": f"Phone number {phone_number} added successfully and is now available for assignment",
            "purchased_phone_number_id": purchased_number.purchased_phone_number_id,
            "phone_number": purchased_number.phone_number,
            "status": purchased_number.status,
            "property_manager_id": property_manager_id,
            "pm_name": pm.name,
            "pm_email": pm.email,
        })


@app.post("/admin/purchase-phone-number")
def admin_purchase_phone_number(
    property_manager_id: int = Body(...),
    area_code: Optional[str] = Body(None),
    notes: Optional[str] = Body(None),
    # In production, add admin authentication here
):
    """
    Admin endpoint for tech team to purchase a phone number for a PM.
    This should be protected with admin authentication in production.
    """
    # Check if Twilio credentials are configured
    if not TWILIO_ACCOUNT_SID2 or not TWILIO_AUTH_TOKEN2:
        raise HTTPException(
            status_code=500,
            detail="Twilio credentials not configured"
        )
    
    if not twillio_client:
        raise HTTPException(
            status_code=500,
            detail="Twilio client not initialized"
        )
    
    if not VAPI_API_KEY2 or not VAPI_ASSISTANT_ID2:
        raise HTTPException(
            status_code=500,
            detail="VAPI credentials not configured"
        )
    
    with Session(engine) as session:
        pm = session.get(PropertyManager, property_manager_id)
        if not pm:
            raise HTTPException(status_code=404, detail="Property Manager not found")
        
        try:
            # Search for available numbers
            search_area_code = area_code or "412"
            print(f"🔍 Searching for available numbers in area code {search_area_code}...")
            available = twillio_client.available_phone_numbers("US").local.list(
                area_code=search_area_code, limit=1
            )
            
            if not available:
                raise HTTPException(
                    status_code=400,
                    detail=f"No numbers available for area code {search_area_code}"
                )
            
            number_to_buy = available[0].phone_number
            print(f"📞 Found available number: {number_to_buy}")
            
            # Purchase from Twilio
            print(f"💰 Purchasing number from Twilio...")
            purchased = twillio_client.incoming_phone_numbers.create(
                phone_number=number_to_buy,
                sms_url=f"https://api.vapi.ai/sms/twilio/{VAPI_ASSISTANT_ID2}",
                voice_url="https://api.vapi.ai/twilio/inbound_call",
            )
            print(f"✅ Successfully purchased: {purchased.phone_number} (SID: {purchased.sid})")
            
            # Register with VAPI
            print(f"🔗 Linking with VAPI...")
            payload = {
                "provider": "twilio",
                "number": purchased.phone_number,
                "twilioAccountSid": TWILIO_ACCOUNT_SID2,
                "twilioAuthToken": TWILIO_AUTH_TOKEN2,
                "assistantId": VAPI_ASSISTANT_ID2,
                "name": f"PM {property_manager_id} - {purchased.phone_number}",
            }
            
            response = requests.post(
                "https://api.vapi.ai/phone-number",
                headers={
                    "Authorization": f"Bearer {VAPI_API_KEY2}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30.0
            )
            
            if response.status_code not in [200, 201]:
                # Clean up Twilio number
                try:
                    twillio_client.incoming_phone_numbers(purchased.sid).delete()
                except:
                    pass
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to register with VAPI: {response.text}"
                )
            
            vapi_response = response.json()
            vapi_phone_number_id = vapi_response.get("id")
            print(f"✅ Successfully registered with VAPI")
            
            # Save to database
            purchased_number = PurchasedPhoneNumber(
                property_manager_id=property_manager_id,
                phone_number=purchased.phone_number,
                twilio_sid=purchased.sid,
                vapi_phone_number_id=vapi_phone_number_id,
                status="available",
                notes=notes,
            )
            
            session.add(purchased_number)
            
            # Mark any pending requests as fulfilled
            pending_requests = session.exec(
                select(PhoneNumberRequest)
                .where(
                    PhoneNumberRequest.property_manager_id == property_manager_id,
                    PhoneNumberRequest.status == "pending"
                )
            ).all()
            
            for req in pending_requests:
                req.status = "fulfilled"
                req.fulfilled_at = datetime.utcnow()
                session.add(req)
            
            session.commit()
            session.refresh(purchased_number)
            
            return JSONResponse(content={
                "message": "Phone number purchased and registered successfully",
                "purchased_phone_number_id": purchased_number.purchased_phone_number_id,
                "phone_number": purchased_number.phone_number,
                "status": purchased_number.status,
                "property_manager_id": property_manager_id,
                "vapi_response": vapi_response,
            })
            
        except HTTPException:
            raise
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Error purchasing number: {error_msg}")
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail=f"Error purchasing number: {error_msg}"
            )


@app.get("/admin/all-phone-number-requests")
def admin_get_all_phone_number_requests(
    status: Optional[str] = None,  # Filter by status: pending, fulfilled, cancelled
    # In production, add admin authentication here
):
    """Admin endpoint to view all phone number requests."""
    with Session(engine) as session:
        query = select(PhoneNumberRequest)
        if status:
            query = query.where(PhoneNumberRequest.status == status)
        query = query.order_by(PhoneNumberRequest.requested_at.desc())
        
        requests = session.exec(query).all()
        
        return JSONResponse(content={
            "requests": [
                {
                    "request_id": req.request_id,
                    "property_manager_id": req.property_manager_id,
                    "country_code": req.country_code,
                    "area_code": req.area_code,
                    "status": req.status,
                    "notes": req.notes,
                    "requested_at": req.requested_at.isoformat() if req.requested_at else None,
                    "fulfilled_at": req.fulfilled_at.isoformat() if req.fulfilled_at else None,
                }
                for req in requests
            ]
        })


@app.get("/admin/all-purchased-numbers")
def admin_get_all_purchased_numbers(
    property_manager_id: Optional[int] = None,
    status: Optional[str] = None,
    # In production, add admin authentication here
):
    """Admin endpoint to view all purchased phone numbers."""
    with Session(engine) as session:
        query = select(PurchasedPhoneNumber)
        if property_manager_id:
            query = query.where(PurchasedPhoneNumber.property_manager_id == property_manager_id)
        if status:
            query = query.where(PurchasedPhoneNumber.status == status)
        query = query.order_by(PurchasedPhoneNumber.purchased_at.desc())
        
        numbers = session.exec(query).all()
        
        return JSONResponse(content={
            "purchased_numbers": [
                {
                    "purchased_phone_number_id": pn.purchased_phone_number_id,
                    "property_manager_id": pn.property_manager_id,
                    "phone_number": pn.phone_number,
                    "twilio_sid": pn.twilio_sid,
                    "vapi_phone_number_id": pn.vapi_phone_number_id,
                    "status": pn.status,
                    "assigned_to_type": pn.assigned_to_type,
                    "assigned_to_id": pn.assigned_to_id,
                    "purchased_at": pn.purchased_at.isoformat() if pn.purchased_at else None,
                    "assigned_at": pn.assigned_at.isoformat() if pn.assigned_at else None,
                    "notes": pn.notes,
                }
                for pn in numbers
            ]
        })


@app.get("/my-number")
def get_my_number(user_data: dict = Depends(get_current_user_data)):
    """Get the phone number for the current user (Property Manager or Realtor)."""
    user_type = user_data.get("user_type")
    user_id = user_data.get("id")
    
    if not user_type or not user_id:
        raise HTTPException(status_code=400, detail="Invalid user data")
    
    with Session(engine) as session:
        if user_type == "realtor":
            user_record = session.get(Realtor, user_id)
        elif user_type == "property_manager":
            user_record = session.get(PropertyManager, user_id)
        else:
            raise HTTPException(status_code=400, detail=f"Invalid user type: {user_type}")
        
        if not user_record:
            raise HTTPException(status_code=404, detail=f"{user_type.title()} not found")
        
        bot_number = _get_or_sync_twilio_number(session, user_record)
        if not bot_number:
            # Debug: Check what's actually in the database
            if isinstance(user_record, PropertyManager):
                pm_id = user_record.property_manager_id
                assigned_numbers = session.exec(
                    select(PurchasedPhoneNumber)
                    .where(PurchasedPhoneNumber.property_manager_id == pm_id)
                    .where(PurchasedPhoneNumber.assigned_to_id == pm_id)
                ).all()
                print(f"🔍 DEBUG: PM {pm_id} - Found {len(assigned_numbers)} assigned numbers in inventory")
                for pn in assigned_numbers:
                    print(f"  - Number: {pn.phone_number}, assigned_to_type: {pn.assigned_to_type}, assigned_to_id: {pn.assigned_to_id}")
            
            raise HTTPException(
                status_code=404,
                detail="You haven't purchased a phone number yet! Use the /buy-number endpoint to purchase one."
            )

        return JSONResponse(content={
            "twilio_number": bot_number,
            "twilio_sid": user_record.twilio_sid,
            "user_type": user_type,
            "user_id": user_id,
            "forwarding_state": _serialize_forwarding_state(user_record),
        })


@app.get("/call-forwarding-state")
def get_call_forwarding_state(
    realtor_id: Optional[int] = None,
    user_data: dict = Depends(get_current_user_data),
):
    """Return forwarding state for current user or a managed realtor."""
    with Session(engine) as session:
        target_record, target_type = _resolve_forwarding_target(session, user_data, realtor_id)
        target_id = (
            target_record.property_manager_id
            if target_type == "property_manager"
            else target_record.realtor_id
        )

        bot_number = _get_or_sync_twilio_number(session, target_record)
        
        # For realtors, if no number is assigned, return None (don't fall back to PM's number)
        if target_type == "realtor" and not bot_number:
            # Verify the realtor truly has no assigned number
            realtor = target_record
            purchased_id = getattr(realtor, "purchased_phone_number_id", None)
            if not purchased_id:
                # Check if there's any number assigned to this realtor in PurchasedPhoneNumber
                assigned_number = session.exec(
                    select(PurchasedPhoneNumber)
                    .where(PurchasedPhoneNumber.property_manager_id == realtor.property_manager_id)
                    .where(PurchasedPhoneNumber.assigned_to_id == realtor.realtor_id)
                    .where(
                        or_(
                            func.lower(func.coalesce(PurchasedPhoneNumber.assigned_to_type, "")) == "realtor",
                            PurchasedPhoneNumber.assigned_to_type == "realtor",
                            PurchasedPhoneNumber.assigned_to_type == "Realtor",
                        )
                    )
                ).first()
                
                if not assigned_number:
                    # Realtor has no number assigned - return None explicitly
                    bot_number = None
                    carrier = getattr(target_record, "carrier", None)
                    forwarding_codes = _get_carrier_forwarding_codes(carrier, None)
                    
                    return JSONResponse(content={
                        "user_type": target_type,
                        "user_id": target_id,
                        "twilio_number": None,
                        "twilio_sid": None,
                        "forwarding_state": _serialize_forwarding_state(target_record),
                        "forwarding_codes": forwarding_codes,
                        "message": "No phone number assigned to this realtor. Please assign a number first."
                    })
        
        if bot_number and not BOT_NUMBER_REGEX.match(bot_number):
            raise HTTPException(
                status_code=422,
                detail=f"Twilio number must be in E.164 format. Got: {bot_number}",
            )

        carrier = getattr(target_record, "carrier", None)
        forwarding_codes = _get_carrier_forwarding_codes(carrier, bot_number)
        
        return JSONResponse(content={
            "user_type": target_type,
            "user_id": target_id,
            "twilio_number": bot_number,
            "twilio_sid": target_record.twilio_sid,
            "forwarding_state": _serialize_forwarding_state(target_record),
            "forwarding_codes": forwarding_codes,
        })


@app.get("/call-forwarding-carriers")
def list_call_forwarding_carriers():
    """
    Provide the list of supported carriers and their capabilities.
    Returns carrier information including which features are supported.
    """
    carrier_info = []
    for carrier_name in CALL_FORWARDING_CARRIERS:
        if carrier_name in CARRIER_CODES:
            config = CARRIER_CODES[carrier_name]
            carrier_info.append({
                "name": carrier_name,
                "type": config["type"],
                "supports_forward_all": config.get("forward_all", {}).get("activate") is not None and config.get("forward_all", {}).get("activate") != "app_only",
                "supports_25_second_forwarding": config.get("forward_no_answer", {}).get("supports_custom_seconds", False),
                "requires_app": config.get("forward_all", {}).get("activate") == "app_only",
                "notes": _get_carrier_notes(carrier_name)
            })
    
    return JSONResponse(content={
        "carriers": CALL_FORWARDING_CARRIERS,
        "carrier_details": carrier_info
    })


def _get_carrier_notes(carrier_name: str) -> str:
    """Get human-readable notes about carrier limitations."""
    notes_map = {
        "Verizon": "Only supports unconditional forwarding (*72). 25-second forwarding not available.",
        "Xfinity Mobile": "Uses *72/*73/*71 codes. No-answer forwarding available but no custom seconds.",
        "Google Fi": "Must configure forwarding through Google Fi app or website. No GSM codes supported.",
    }
    return notes_map.get(carrier_name, "")


@app.patch("/call-forwarding-state")
def update_call_forwarding_state(
    payload: CallForwardingStateUpdate,
    user_data: dict = Depends(get_current_user_data),
):
    """Persist the UI state for business-hours and after-hours forwarding."""
    if (
        payload.after_hours_enabled is None
        and payload.business_forwarding_enabled is None
        and payload.confirmation_status is None
        and payload.carrier is None
    ):
        raise HTTPException(
            status_code=400,
            detail="Provide at least one of: after_hours_enabled, business_forwarding_enabled, confirmation_status, or carrier",
        )

    requester_type = user_data.get("user_type")
    requester_id = user_data.get("id")

    confirmation_status = None
    if payload.confirmation_status:
        normalized_status = payload.confirmation_status.lower()
        if normalized_status not in {"success", "failure", "pending"}:
            raise HTTPException(
                status_code=400,
                detail="confirmation_status must be one of: success, failure, pending",
            )
        confirmation_status = normalized_status

    with Session(engine) as session:
        target_record, target_type = _resolve_forwarding_target(session, user_data, payload.realtor_id)
        target_id = (
            target_record.property_manager_id
            if target_type == "property_manager"
            else target_record.realtor_id
        )

        _enforce_forwarding_rate_limit(session, target_type, target_id)

        state_changes: Dict[str, Any] = {}
        now = datetime.utcnow()

        # Update carrier if provided
        if payload.carrier is not None:
            if payload.carrier not in CALL_FORWARDING_CARRIERS and payload.carrier:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported carrier: {payload.carrier}. Supported carriers: {', '.join(CALL_FORWARDING_CARRIERS)}"
                )
            # Use getattr with None default in case carrier column doesn't exist yet (migration not run)
            current_carrier = getattr(target_record, "carrier", None)
            if current_carrier != payload.carrier:
                target_record.carrier = payload.carrier
                state_changes["carrier"] = payload.carrier

        if payload.business_forwarding_enabled is not None:
            if target_record.business_forwarding_enabled != payload.business_forwarding_enabled:
                target_record.business_forwarding_enabled = payload.business_forwarding_enabled
                if not payload.business_forwarding_enabled:
                    target_record.business_forwarding_confirmed_at = None
                state_changes["business_forwarding_enabled"] = payload.business_forwarding_enabled

        if payload.after_hours_enabled is not None:
            if target_record.after_hours_enabled != payload.after_hours_enabled:
                target_record.after_hours_enabled = payload.after_hours_enabled
                target_record.last_after_hours_update = now
                state_changes["after_hours_enabled"] = payload.after_hours_enabled
                state_changes["last_after_hours_update"] = now.isoformat()
                if not payload.after_hours_enabled:
                    target_record.after_hours_last_disabled_at = now
                    state_changes["after_hours_last_disabled_at"] = now.isoformat()

        sms_message = None
        if confirmation_status is not None:
            state_changes["confirmation_status"] = confirmation_status

            if confirmation_status == "success":
                target_record.forwarding_failure_reason = None
                if target_record.business_forwarding_enabled:
                    target_record.business_forwarding_confirmed_at = now
                    state_changes["business_forwarding_confirmed_at"] = now.isoformat()
                if target_record.after_hours_enabled:
                    target_record.after_hours_last_enabled_at = now
                    state_changes["after_hours_last_enabled_at"] = now.isoformat()
                sms_message = (
                    f"✅ Forwarding success for {target_type} "
                    f"{getattr(target_record, 'name', target_id)} at {now.isoformat()}."
                )
            elif confirmation_status == "failure":
                failure_reason = payload.failure_reason or "Carrier did not confirm forwarding."
                target_record.forwarding_failure_reason = failure_reason
                state_changes["forwarding_failure_reason"] = failure_reason
                sms_message = (
                    f"⚠️ Forwarding failure for {target_type} "
                    f"{getattr(target_record, 'name', target_id)}: {failure_reason}"
                )
                _log_forwarding_event(
                    session,
                    target_user_type=target_type,
                    target_user_id=target_id,
                    action="forwarding_state_error",
                    initiated_by_user_type=requester_type,
                    initiated_by_user_id=requester_id,
                    event_metadata={
                        "notes": payload.notes,
                        "failure_reason": failure_reason,
                        "for_realtor_id": payload.realtor_id,
                    },
                )
            else:
                # Pending state keeps previous confirmation timestamps but notes the new intent
                if payload.failure_reason:
                    target_record.forwarding_failure_reason = payload.failure_reason
                    state_changes["forwarding_failure_reason"] = payload.failure_reason

        if not state_changes:
            return JSONResponse(content={
                "message": "No changes applied",
                "user_type": target_type,
                "user_id": target_id,
                "forwarding_state": _serialize_forwarding_state(target_record),
            })

        target_record.last_forwarding_update = now
        state_changes["last_forwarding_update"] = now.isoformat()

        session.add(target_record)
        _log_forwarding_event(
            session,
            target_user_type=target_type,
            target_user_id=target_id,
            action="forwarding_state_update",
            initiated_by_user_type=requester_type,
            initiated_by_user_id=requester_id,
            event_metadata={
                "changes": state_changes,
                "notes": payload.notes,
                "for_realtor_id": payload.realtor_id,
            },
        )

        session.commit()
        session.refresh(target_record)

        if sms_message:
            _notify_forwarding_status_via_sms(sms_message)

        bot_number = _get_or_sync_twilio_number(session, target_record)
        carrier = getattr(target_record, "carrier", None)
        forwarding_codes = _get_carrier_forwarding_codes(carrier, bot_number)

        return JSONResponse(content={
            "message": "Forwarding state updated",
            "user_type": target_type,
            "user_id": target_id,
            "forwarding_state": _serialize_forwarding_state(target_record),
            "forwarding_codes": forwarding_codes,
        })


def _fetch_phone_number_from_vapi(phone_number_id: str) -> Optional[str]:
    """Fetch phone number from VAPI API using phoneNumberId."""
    if not VAPI_API_KEY or not phone_number_id:
        return None
    
    try:
        response = requests.get(
            f"{VAPI_BASE_URL}/phone-number/{phone_number_id}",
            headers={"Authorization": f"Bearer {VAPI_API_KEY}"},
            timeout=10.0
        )
        if response.status_code == 200:
            phone_data = response.json()
            number = phone_data.get("number") or phone_data.get("phoneNumber")
            return _normalize_bot_number(number) if number else None
    except Exception as e:
        print(f"⚠️  Failed to fetch phone number {phone_number_id} from VAPI: {e}")
    return None


def _fetch_call_details_from_vapi(call_id: str) -> Optional[dict]:
    """
    Fetch full call details from VAPI API including recording URL and transcript.
    This is needed because recordings are NOT sent in webhooks.
    """
    if not VAPI_API_KEY or not call_id:
        return None
    
    try:
        # Try /calls/{callId} first (as per user specification), then other variations as fallback
        endpoints = [
            f"{VAPI_BASE_URL}/calls/{call_id}",  # Primary: GET https://api.vapi.ai/calls/{callId}
            f"{VAPI_BASE_URL}/v1/call/{call_id}",
            f"{VAPI_BASE_URL}/call/{call_id}",
        ]
        
        for url in endpoints:
            try:
                response = requests.get(
                    url,
                    headers={"Authorization": f"Bearer {VAPI_API_KEY}"},
                    timeout=10.0
                )
                if response.status_code == 200:
                    return response.json()
            except Exception as e:
                print(f"⚠️  Failed to fetch from {url}: {e}")
                continue
        
        print(f"⚠️  Could not fetch call {call_id} from any VAPI endpoint")
        return None
    except Exception as e:
        print(f"⚠️  Error fetching call details for {call_id}: {e}")
        return None


def _derive_duration_from_recording(recording_url: str) -> Optional[int]:
    """
    Derive recording duration using metadata headers so we avoid downloading the full file.
    Primary approach is HEAD, with a tiny ranged GET fallback.
    """
    if not recording_url:
        return None
    
    candidate_headers = [
        "x-recording-duration",
        "x-amz-meta-duration",
        "x-amz-meta-recording-duration",
        "content-duration",
    ]
    
    def _extract_duration(headers: Dict[str, str]) -> Optional[int]:
        lowered = {k.lower(): v for k, v in headers.items()}
        for key in candidate_headers:
            value = lowered.get(key.lower())
            if value:
                try:
                    seconds = int(float(value))
                    return seconds
                except ValueError:
                    continue
        return None
    
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.head(recording_url, follow_redirects=True)
            if response.status_code < 400:
                duration = _extract_duration(response.headers)
                if duration:
                    print(f"⏱️  Derived recording duration {duration}s from HEAD metadata")
                    return duration
    except Exception as e:
        print(f"⚠️  Failed HEAD duration lookup: {e}")
    
    # Fallback: request a single byte to prompt signed URLs to return metadata headers
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(
                recording_url,
                headers={"Range": "bytes=0-1"},
                follow_redirects=True,
            )
            if response.status_code in (200, 206):
                duration = _extract_duration(response.headers)
                if duration:
                    print(f"⏱️  Derived recording duration {duration}s from ranged GET metadata")
                    return duration
    except Exception as e:
        print(f"⚠️  Failed ranged GET duration lookup: {e}")
    
    print("⚠️  Unable to derive recording duration from recording metadata")
    return None


def _import_call_from_vapi_data(call_data: dict, session: Session) -> Optional[CallRecord]:
    """Import a single call from VAPI API response into database."""
    call_id = call_data.get("id") or call_data.get("callId")
    if not call_id:
        print("⚠️  Skipping call without ID")
        return None
    
    # Check if already exists
    existing = session.exec(
        select(CallRecord).where(CallRecord.call_id == call_id)
    ).first()
    
    if existing:
        # Update existing record with any new data
        updated = False
        
        # Update transcript if available and not already set
        transcript = call_data.get("transcript")
        if transcript and not existing.transcript:
            existing.transcript = transcript
            updated = True
        
        # Update recording URL if available and not already set
        recording_url = call_data.get("recordingUrl") or call_data.get("recording")
        if recording_url and not existing.recording_url:
            existing.recording_url = recording_url
            updated = True
        
        if existing.recording_url and not existing.call_duration:
            derived_duration = _derive_duration_from_recording(existing.recording_url)
            if derived_duration:
                existing.call_duration = derived_duration
                if existing.call_metadata is None:
                    existing.call_metadata = {}
                existing.call_metadata["duration_source"] = "recording_headers"
                updated = True
        
        # Update other fields
        if call_data.get("status") and call_data["status"] != existing.call_status:
            existing.call_status = call_data["status"]
            updated = True
        
        if call_data.get("duration") and call_data["duration"] != existing.call_duration:
            existing.call_duration = call_data["duration"]
            if existing.call_metadata is None:
                existing.call_metadata = {}
            existing.call_metadata["duration_source"] = "payload"
            updated = True
        
        if updated:
            existing.updated_at = datetime.utcnow()
            session.add(existing)
            session.commit()
            session.refresh(existing)
        
        return existing
    
    # Extract phone number
    realtor_number = None
    
    # Try direct fields
    realtor_number = call_data.get("toNumber") or call_data.get("to") or call_data.get("phoneNumber")
    
    # Try phoneNumberId lookup
    if not realtor_number:
        phone_number_id = call_data.get("phoneNumberId")
        if phone_number_id:
            realtor_number = _fetch_phone_number_from_vapi(phone_number_id)
    
    # Try nested phoneNumber object
    if not realtor_number:
        phone_number_obj = call_data.get("phoneNumber")
        if isinstance(phone_number_obj, dict):
            realtor_number = phone_number_obj.get("number") or phone_number_obj.get("phoneNumber")
        elif isinstance(phone_number_obj, str):
            realtor_number = phone_number_obj
    
    # Normalize
    realtor_number = _normalize_bot_number(realtor_number) if realtor_number else "unknown"
    
    # Extract other data
    transcript = call_data.get("transcript")
    recording_url = call_data.get("recordingUrl") or call_data.get("recording")
    call_status = call_data.get("status", "ended")
    call_duration = call_data.get("duration")
    duration_source = "payload" if call_duration else None
    caller_number_raw = _extract_caller_number(call_data, call_data)
    caller_number = _normalize_bot_number(caller_number_raw) if caller_number_raw else None
    
    # If recording URL is missing, try to fetch from VAPI API
    if not recording_url and call_id:
        print(f"📞 Fetching recording URL for call {call_id} from VAPI API...")
        call_details = _fetch_call_details_from_vapi(call_id)
        if call_details:
            recording_url = call_details.get("recordingUrl") or call_details.get("recording")
            # Also update transcript if missing
            if not transcript:
                transcript = call_details.get("transcript")
            # Update other fields if missing
            if not call_duration:
                call_duration = call_details.get("duration")
                if call_duration:
                    duration_source = "vapi_api"
            if not caller_number:
                details_caller = _extract_caller_number(call_details, call_details)
                caller_number = _normalize_bot_number(details_caller) if details_caller else None
    
    if not call_duration and recording_url:
        derived_duration = _derive_duration_from_recording(recording_url)
        if derived_duration:
            call_duration = derived_duration
            duration_source = "recording_headers"
    
    # Parse created_at if available
    created_at = datetime.utcnow()
    if call_data.get("createdAt"):
        try:
            created_at_str = str(call_data["createdAt"])
            # Handle ISO format: "2024-01-15T10:30:00Z" or "2024-01-15T10:30:00.000Z"
            if "Z" in created_at_str:
                created_at_str = created_at_str.replace("Z", "+00:00")
            elif "+" not in created_at_str and "-" in created_at_str[-6:]:
                # Already has timezone
                pass
            created_at = datetime.fromisoformat(created_at_str)
        except Exception as e:
            print(f"⚠️  Could not parse createdAt '{call_data.get('createdAt')}': {e}")
            # Keep default datetime.utcnow()
    
    # Create new record
    call_record = CallRecord(
        id=uuid.uuid4(),
        call_id=call_id,
        realtor_number=realtor_number,
        transcript=transcript,
        recording_url=recording_url,
        call_status=call_status,
        call_duration=call_duration,
        caller_number=_normalize_bot_number(caller_number) if caller_number else None,
        call_metadata={
            "imported_from_vapi": True,
            "imported_at": datetime.utcnow().isoformat(),
            "vapi_data": {k: v for k, v in call_data.items() if k not in ["id", "callId", "transcript", "recordingUrl", "recording"]},
        },
        created_at=created_at,
    )
    if duration_source:
        call_record.call_metadata["duration_source"] = duration_source
    
    session.add(call_record)
    session.commit()
    session.refresh(call_record)
    
    return call_record


@app.post("/admin/import-vapi-calls")
def import_vapi_calls(
    limit: Optional[int] = 100,
    offset: Optional[int] = 0,
    # In production, add admin authentication here
):
    """
    Admin endpoint to import historical calls from VAPI API.
    Fetches calls from VAPI and imports them into the database.
    """
    if not VAPI_API_KEY:
        raise HTTPException(status_code=500, detail="VAPI_API_KEY not configured")
    
    try:
        # Fetch calls from VAPI API
        # Try /v1/calls first (as per user example), fallback to /v1/call if needed
        url = f"{VAPI_BASE_URL}/v1/calls"
        params = {"limit": min(limit, 100), "offset": offset}
        headers = {"Authorization": f"Bearer {VAPI_API_KEY}"}
        
        print(f"📞 Fetching calls from VAPI (limit={params['limit']}, offset={params['offset']})...")
        response = requests.get(url, headers=headers, params=params, timeout=30.0)
        
        if response.status_code != 200:
            # Try alternative endpoint if /v1/calls fails
            if response.status_code == 404 and "/v1/calls" in url:
                print("⚠️  /v1/calls not found, trying /v1/call...")
                url = f"{VAPI_BASE_URL}/v1/call"
                response = requests.get(url, headers=headers, params=params, timeout=30.0)
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"VAPI API error: {response.text}"
                )
        
        calls_data = response.json()
        
        # Handle both array and object responses
        if isinstance(calls_data, dict):
            calls = calls_data.get("calls", []) or calls_data.get("data", [])
            total = calls_data.get("total") or len(calls)
        else:
            calls = calls_data if isinstance(calls_data, list) else []
            total = len(calls)
        
        imported_count = 0
        updated_count = 0
        skipped_count = 0
        errors = []
        
        with Session(engine) as session:
            for call_data in calls:
                try:
                    existing = session.exec(
                        select(CallRecord).where(CallRecord.call_id == (call_data.get("id") or call_data.get("callId")))
                    ).first()
                    
                    result = _import_call_from_vapi_data(call_data, session)
                    if result:
                        if existing:
                            updated_count += 1
                        else:
                            imported_count += 1
                    else:
                        skipped_count += 1
                except Exception as e:
                    error_msg = f"Error importing call {call_data.get('id', 'unknown')}: {str(e)}"
                    print(f"❌ {error_msg}")
                    errors.append(error_msg)
                    skipped_count += 1
        
        return JSONResponse(content={
            "message": "Import completed",
            "total_fetched": len(calls),
            "total_available": total,
            "imported": imported_count,
            "updated": updated_count,
            "skipped": skipped_count,
            "errors": errors[:10],  # Limit error messages
        })
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error importing VAPI calls: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@app.post("/vapi-webhook")
async def vapi_webhook_hyphen(request: Request):
    """
    VAPI webhook endpoint (with hyphen) - receives end-of-call-report with transcript.
    This is the actual endpoint VAPI calls: https://leasing-copilot-mvp.onrender.com/vapi-webhook
    
    VAPI sends transcripts in end-of-call-report webhooks.
    Audio recordings are NOT sent in webhooks - must be fetched from VAPI API.
    
    Payload structure:
    {
      "message": {
        "type": "end-of-call-report",
        "artifact": {
          "messages": [...]  // Array of conversation messages
        },
        "analysis": {
          "summary": "..."
        }
      }
    }
    """
    try:
        payload = await request.json()
        headers_lower = {k.lower(): v for k, v in request.headers.items()}
        
        # Extract call ID from headers first (VAPI sends it in x-call-id header)
        call_id = request.headers.get("x-call-id") or request.headers.get("X-Call-Id")
        
        # Extract message object (VAPI wraps in "message")
        message = payload.get("message", {})
        if not message:
            # Fallback: maybe payload is the message itself
            message = payload
        
        phone_number_id = (
            payload.get("phoneNumberId")
            or message.get("phoneNumberId")
            or (
                payload.get("phoneNumber", {}).get("id")
                if isinstance(payload.get("phoneNumber"), dict)
                else None
            )
            or (
                message.get("phoneNumber", {}).get("id")
                if isinstance(message.get("phoneNumber"), dict)
                else None
            )
        )
        
        artifact = message.get("artifact") if isinstance(message, dict) else None
        if not isinstance(artifact, dict):
            artifact = {}
        artifact_messages = artifact.get("messages", []) if artifact else []
        has_artifact_messages = bool(artifact_messages)
        message_transcript = message.get("transcript")
        message_summary = message.get("summary") or message.get("analysis", {}).get("summary")
        duration_seconds = (
            message.get("durationSeconds")
            or message.get("duration")
            or (
                (message.get("durationMs") or message.get("duration_ms")) / 1000.0
                if (message.get("durationMs") or message.get("duration_ms"))
                else None
            )
        )

        caller_number_raw = _extract_caller_number(payload, message, headers_lower)
        
        # Debug: Log message structure
        print(f"🔍 Message object keys: {list(message.keys()) if isinstance(message, dict) else 'not a dict'}")
        if isinstance(message, dict) and "type" in message:
            print(f"✅ Found type in message: {message.get('type')}")
        else:
            print(f"⚠️  Type not found in message. Top-level payload keys: {list(payload.keys())}")
            # Try to find type in payload
            if "type" in payload:
                print(f"✅ Found type in payload: {payload.get('type')}")
        
        message_type = message.get("type", "") or payload.get("type", "")
        print(f"📞 VAPI webhook received - Event type: {message_type or 'unknown'}, Call ID: {call_id or 'not found'}")
        
        # Only process end-of-call-report for transcript extraction
        # VAPI sends multiple webhook events during a call so:
        # - Status Update, Conversation Update, Speech Update (no transcripts)
        # - End Of Call Report (contains transcript in artifact.messages)
        # VAPI uses "End Of Call Report" (with spaces and capitals) in the type field
        # We identify end-of-call-report by: type contains "end" and "call" and "report" OR presence of artifact
        message_type_lower = message_type.lower() if message_type else ""
        is_end_of_call = (
            ("end" in message_type_lower and "call" in message_type_lower and "report" in message_type_lower) or
            message_type_lower == "end-of-call-report" or  # Fallback for hyphenated format
            (not message_type and has_artifact_messages)
        )
        
        if not is_end_of_call:
            if message_type:
                print(f"ℹ️  Skipping transcript extraction for event type: {message_type} (not End Of Call Report)")
            else:
                print(f"ℹ️  Skipping transcript extraction - no type and no artifact found")
            return {"status": "ok", "call_id": call_id, "event_type": message_type or "unknown", "message": "Not an End Of Call Report event"}
        
        # This is an End Of Call Report - process transcript extraction
        print(f"✅ Processing End Of Call Report for call {call_id}")
        
        # Extract call ID from payload if not in headers
        if not call_id:
            call_id = (
                payload.get("id") or 
                payload.get("callId") or 
                message.get("id") or 
                message.get("callId") or
                payload.get("call_id") or
                message.get("call_id")
            )
        
        # If no call_id, try to extract from artifact or fetch from VAPI
        if not call_id:
            # Check if we can get it from the messages or metadata
            artifact = message.get("artifact", {})
            if artifact:
                # Try to get from first message metadata or other fields
                messages = artifact.get("messages", [])
                if messages:
                    # Check if any message has call_id
                    for msg in messages:
                        if msg.get("callId") or msg.get("call_id"):
                            call_id = msg.get("callId") or msg.get("call_id")
                            break
        
        if not call_id:
            print("⚠️  VAPI webhook received without call_id - will try to match by phone number")
            # We'll try to match by phone number and timestamp later
        
        # Extract transcript from message.artifact.messages
        transcript = None
        transcript_parts = []
        summary = None
        
        # Debug: Print message structure to understand what we're receiving
        if isinstance(message, dict):
            print(f"🔍 Full message structure - Keys: {list(message.keys())}")
            if "artifact" in message:
                print(f"✅ Artifact found in message")
            else:
                print(f"⚠️  No 'artifact' key in message. Available keys: {list(message.keys())[:10]}")
        
        if message_transcript and isinstance(message_transcript, str) and message_transcript.strip():
            transcript = message_transcript.strip()
            print(f"📄 Using transcript field from message: {len(transcript)} chars")
        elif artifact:
            print(f"📋 Found artifact with {len(artifact_messages)} messages")
            if artifact_messages:
                allowed_roles = {"user", "bot", "assistant"}
                system_messages = []
                for msg in artifact_messages:
                    role = (msg.get("role") or "").lower()
                    msg_text = msg.get("message") or msg.get("text")
                    if not msg_text:
                        continue
                    if role in allowed_roles:
                        transcript_parts.append(f"{role.capitalize()}: {msg_text.strip()}")
                    elif role == "system":
                        # store system prompts separately to avoid bloating transcript
                        system_messages.append(msg_text.strip())
                if transcript_parts:
                    transcript = "\n\n".join(transcript_parts)
                    print(f"📄 Extracted transcript from {len(transcript_parts)} conversational turns: {len(transcript)} chars")
                elif system_messages:
                    transcript = "\n\n".join(system_messages)
                    print(f"⚠️  No user/bot messages; storing system text ({len(system_messages)} entries)")
                else:
                    print(f"⚠️  No transcript parts extracted from {len(artifact_messages)} messages")
            else:
                print(f"⚠️  Artifact found but messages array is empty")
        else:
            print(f"⚠️  No artifact found in message object")
        
        # Extract summary from analysis
        analysis = message.get("analysis", {})
        if not analysis and message_summary:
            summary = message_summary
            print(f"📋 Using summary field from message: {len(summary)} chars")
        elif analysis:
            summary = analysis.get("summary", "")
            if summary:
                print(f"📋 Extracted summary: {len(summary)} chars")
            else:
                print(f"⚠️  Analysis found but no summary")
        else:
            print(f"⚠️  No analysis found in message object")
        
        # Combine transcript and summary
        if transcript and summary:
            full_transcript = f"{transcript}\n\n---\n\nSummary: {summary}"
        elif transcript:
            full_transcript = transcript
        elif summary:
            full_transcript = f"Summary: {summary}"
        else:
            full_transcript = None
        
        # Extract phone number - try multiple locations
        realtor_number = None
        realtor_number = (
            payload.get("toNumber") or 
            payload.get("to") or 
            payload.get("phoneNumber") or
            message.get("toNumber") or
            message.get("to") or
            message.get("phoneNumber")
        )
        
        if not realtor_number:
            phone_number_id = payload.get("phoneNumberId") or message.get("phoneNumberId")
            if phone_number_id:
                phone_number_obj = payload.get("phoneNumber") or message.get("phoneNumber")
                if isinstance(phone_number_obj, dict):
                    realtor_number = phone_number_obj.get("number") or phone_number_obj.get("phoneNumber")
                elif isinstance(phone_number_obj, str):
                    realtor_number = phone_number_obj
                else:
                    realtor_number = _fetch_phone_number_from_vapi(phone_number_id)
        
        realtor_number = _normalize_bot_number(realtor_number) if realtor_number else "unknown"
        _update_vapi_caches(call_id, None if realtor_number == "unknown" else realtor_number, phone_number_id)
        
        # If we don't have call_id, try to find recent call by phone number and timestamp
        # or fetch from VAPI API
        if not call_id and realtor_number != "unknown":
            # Try to find most recent call for this number without a transcript
            # This is a fallback - ideally VAPI should send call_id
            print(f"⚠️  No call_id provided, attempting to match by phone number: {realtor_number}")
            # We'll create a temporary call_id or try to fetch from VAPI
            # For now, we'll use a timestamp-based ID as fallback
            call_id = f"webhook_{int(datetime.utcnow().timestamp() * 1000)}"
        
        with Session(engine) as session:
            # Try to find existing call record
            call_record = None
            if call_id and not call_id.startswith("webhook_"):
                call_record = session.exec(
                    select(CallRecord).where(CallRecord.call_id == call_id)
                ).first()
            
            # If not found and we have phone number, try to find by phone number and recent timestamp
            if not call_record and realtor_number != "unknown":
                # Find most recent call for this number without transcript (within last hour)
                recent_cutoff = datetime.utcnow() - timedelta(hours=1)
                recent_call = session.exec(
                    select(CallRecord)
                    .where(CallRecord.realtor_number == realtor_number)
                    .where(CallRecord.created_at >= recent_cutoff)
                    .where(CallRecord.transcript.is_(None))
                    .order_by(CallRecord.created_at.desc())
                    .limit(1)
                ).first()
                if recent_call:
                    call_record = recent_call
                    call_id = call_record.call_id
                    print(f"✅ Matched call by phone number: {call_id}")
            
            # Create new record if still not found
            if not call_record:
                call_record = CallRecord(
                    id=uuid.uuid4(),
                    call_id=call_id,
                    realtor_number=realtor_number,
                    live_transcript_chunks=[],
                )
                session.add(call_record)
            
            now = datetime.utcnow()
            updated = False
            
            # Store transcript from end-of-call-report
            if full_transcript:
                print(f"📄 Storing transcript for call {call_id}: {len(full_transcript)} chars")
                call_record.transcript = full_transcript
                updated = True
            
            # Store call status and other metadata
            call_record.call_status = message.get("status") or payload.get("status", "ended")
            if duration_seconds is not None:
                call_record.call_duration = int(duration_seconds)
                if call_record.call_metadata is None:
                    call_record.call_metadata = {}
                call_record.call_metadata["duration_source"] = "webhook_payload"
            
            # Extract duration from message timestamp if available
            timestamp = message.get("timestamp")
            if timestamp:
                # Convert milliseconds to seconds if needed
                if timestamp > 1e12:  # Likely milliseconds
                    timestamp = timestamp / 1000
                # Store in metadata
                if call_record.call_metadata is None:
                    call_record.call_metadata = {}
                call_record.call_metadata["webhook_timestamp"] = timestamp
            
            if caller_number_raw and not call_record.caller_number:
                normalized_caller = _normalize_bot_number(caller_number_raw)
                if normalized_caller:
                    call_record.caller_number = normalized_caller
                    if call_record.call_metadata is None:
                        call_record.call_metadata = {}
                    call_record.call_metadata["caller_source"] = "webhook_payload"
                    updated = True
            
            # Fetch recording URL and call_id from VAPI API if we don't have it
            if not call_record.recording_url or (call_id and call_id.startswith("webhook_")):
                # Try to fetch call details from VAPI
                # If we have phone number, we might be able to find the call
                if realtor_number != "unknown":
                    print(f"🎙️  Fetching call details from VAPI API for number {realtor_number}...")
                    # Note: We'd need to list calls and match, but for now we'll try with call_id if we have it
                    if call_id and not call_id.startswith("webhook_"):
                        call_details = _fetch_call_details_from_vapi(call_id)
                        if call_details:
                            recording_url = call_details.get("recordingUrl") or call_details.get("recording")
                            if recording_url:
                                call_record.recording_url = recording_url
                                print(f"✅ Recording URL fetched: {recording_url}")
                                updated = True
                            # Update call_id if we got a real one
                            real_call_id = call_details.get("id") or call_details.get("callId")
                            if real_call_id and call_id.startswith("webhook_"):
                                call_record.call_id = real_call_id
                                call_id = real_call_id
                                updated = True
                            # Also update transcript if it wasn't in webhook
                            if not call_record.transcript:
                                api_transcript = call_details.get("transcript")
                                if api_transcript:
                                    call_record.transcript = api_transcript
                                    updated = True
                            # Update duration if missing
                            if not call_record.call_duration:
                                api_duration = (
                                    call_details.get("durationSeconds")
                                    or call_details.get("duration")
                                    or (
                                        (call_details.get("durationMs") or call_details.get("duration_ms")) / 1000.0
                                        if (call_details.get("durationMs") or call_details.get("duration_ms"))
                                        else None
                                    )
                                )
                                if api_duration:
                                    call_record.call_duration = int(api_duration)
                                    if call_record.call_metadata is None:
                                        call_record.call_metadata = {}
                                    call_record.call_metadata["duration_source"] = "vapi_api"
                                    updated = True
                            if not call_record.caller_number:
                                details_caller_raw = _extract_caller_number(call_details, call_details)
                                normalized_caller = _normalize_bot_number(details_caller_raw) if details_caller_raw else None
                                if normalized_caller:
                                    call_record.caller_number = normalized_caller
                                    if call_record.call_metadata is None:
                                        call_record.call_metadata = {}
                                    call_record.call_metadata["caller_source"] = "vapi_api"
                                    updated = True
            
            if call_record.recording_url and not call_record.call_duration:
                derived_duration = _derive_duration_from_recording(call_record.recording_url)
                if derived_duration:
                    call_record.call_duration = derived_duration
                    if call_record.call_metadata is None:
                        call_record.call_metadata = {}
                    call_record.call_metadata["duration_source"] = "recording_headers"
                    print(f"⏱️  Derived duration from recording headers: {derived_duration}s")
                    updated = True
            
            # Store metadata
            if call_record.call_metadata is None:
                call_record.call_metadata = {}
            call_record.call_metadata.update({
                "webhook_type": "end-of-call-report",
                "last_webhook_at": now.isoformat(),
                "message_type": message_type,
                "has_summary": bool(summary),
                "message_count": len(artifact_messages),
                "system_message_count": sum(1 for msg in artifact_messages if (msg.get('role') or '').lower() == 'system'),
            })
            # Store full payload for debugging (limit size)
            payload_str = json.dumps(payload)
            if len(payload_str) < 10000:  # Only store if reasonable size
                call_record.call_metadata["webhook_payload"] = payload
            
            call_record.updated_at = now
            updated = True
            
            if updated:
                session.commit()
                session.refresh(call_record)
        
        return {"status": "ok", "call_id": call_id, "transcript_stored": bool(full_transcript)}
    
    except Exception as e:
        print(f"❌ Error processing VAPI webhook: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


@app.post("/vapi/webhook")
async def vapi_webhook(request: Request):
    """
    VAPI webhook endpoint (alternative path) to receive call events.
    This endpoint handles various event types including real-time transcripts.
    
    VAPI webhook payload structure:
    - Top-level: {"type": "event.type", "data": {...}}
    - Or direct call object: {"id": "...", "phoneNumberId": "...", ...}
    
    Note: End-of-call-report with transcript is sent to /vapi-webhook (with hyphen).
    """
    try:
        payload = await request.json()
        
        # Handle two possible payload structures
        if "type" in payload and "data" in payload:
            # Standard webhook event format
            event_type = payload.get("type")
            data = payload.get("data", {})
            call_id = data.get("callId") or data.get("id") or payload.get("callId")
        else:
            # Direct call object (might be sent directly)
            event_type = payload.get("type", "call.updated")
            data = payload
            call_id = data.get("callId") or data.get("id")
        
        caller_number_raw = _extract_caller_number(data, data)
        
        # Extract phone number - VAPI uses phoneNumberId or phoneNumber object
        realtor_number = None
        
        # Try direct number fields first
        realtor_number = data.get("toNumber") or data.get("to") or data.get("phoneNumber")
        
        # Try phoneNumberId - if it's an ID, look it up from VAPI or extract from phoneNumber object
        if not realtor_number:
            phone_number_id = data.get("phoneNumberId") or payload.get("phoneNumberId")
            if phone_number_id:
                # Try to extract from phoneNumber object first
                phone_number_obj = data.get("phoneNumber") or payload.get("phoneNumber")
                if isinstance(phone_number_obj, dict):
                    realtor_number = phone_number_obj.get("number") or phone_number_obj.get("phoneNumber")
                elif isinstance(phone_number_obj, str):
                    realtor_number = phone_number_obj
                
                # If still no number, fetch from VAPI API
                if not realtor_number:
                    realtor_number = _fetch_phone_number_from_vapi(phone_number_id)
        
        # Try from nested objects
        if not realtor_number:
            phone_number_obj = data.get("phoneNumber")
            if isinstance(phone_number_obj, dict):
                realtor_number = phone_number_obj.get("number") or phone_number_obj.get("phoneNumber")
        
        # Normalize the phone number
        realtor_number = _normalize_bot_number(realtor_number) if realtor_number else None
        
        if not call_id:
            print("⚠️  VAPI webhook received without call_id, ignoring")
            return {"status": "ok", "message": "No call_id provided"}
        
        if not realtor_number:
            print(f"⚠️  VAPI webhook for call {call_id} received without realtor_number, storing with unknown")
            realtor_number = "unknown"
        
        with Session(engine) as session:
            # Find or create call record
            call_record = session.exec(
                select(CallRecord).where(CallRecord.call_id == call_id)
            ).first()
            
            if not call_record:
                call_record = CallRecord(
                    id=uuid.uuid4(),
                    call_id=call_id,
                    realtor_number=realtor_number,
                    live_transcript_chunks=[],
                )
                session.add(call_record)
            
            now = datetime.utcnow()
            updated = False
            
            if caller_number_raw and not call_record.caller_number:
                normalized_caller = _normalize_bot_number(caller_number_raw)
                if normalized_caller:
                    call_record.caller_number = normalized_caller
                    updated = True
            
            # Handle different event types
            if event_type == "transcript.created":
                # Real-time transcript chunk
                text = data.get("text") or data.get("transcript")
                if text:
                    print(f"📝 Live Transcript for call {call_id}: {text[:100]}...")
                    if call_record.live_transcript_chunks is None:
                        call_record.live_transcript_chunks = []
                    call_record.live_transcript_chunks.append(text)
                    call_record.updated_at = now
                    updated = True
            
            elif event_type == "call.ended":
                # Final transcript when call ends
                final_transcript = data.get("transcript") or data.get("finalTranscript")
                if final_transcript:
                    print(f"📄 Final Transcript for call {call_id}: {len(final_transcript)} chars")
                    call_record.transcript = final_transcript
                    call_record.updated_at = now
                    updated = True
                
                # Store call status and duration
                call_record.call_status = "ended"
                call_record.call_duration = data.get("duration") or data.get("callDuration")
                if caller_number_raw:
                    call_record.caller_number = _normalize_bot_number(caller_number_raw)
                call_record.updated_at = now
                updated = True
                
                # Fetch recording URL from VAPI API (recordings are NOT in webhooks)
                if not call_record.recording_url:
                    print(f"🎙️  Fetching recording URL for call {call_id} from VAPI API...")
                    call_details = _fetch_call_details_from_vapi(call_id)
                    if call_details:
                        recording_url = call_details.get("recordingUrl") or call_details.get("recording")
                        if recording_url:
                            call_record.recording_url = recording_url
                            print(f"✅ Recording URL fetched: {recording_url}")
                            updated = True
                        # Also update transcript if it wasn't in webhook
                        if not call_record.transcript:
                            call_record.transcript = call_details.get("transcript")
                            updated = True
            
            elif event_type == "recording.ready":
                # Audio recording URL
                recording_url = data.get("url") or data.get("recordingUrl")
                if recording_url:
                    print(f"🎙️  Recording ready for call {call_id}: {recording_url}")
                    call_record.recording_url = recording_url
                    call_record.updated_at = now
                    updated = True
            
            elif event_type == "call.started":
                # Call started
                call_record.call_status = "started"
                call_record.caller_number = data.get("from") or data.get("callerNumber")
                call_record.updated_at = now
                updated = True
            
            # Store any additional metadata
            if data:
                if call_record.call_metadata is None:
                    call_record.call_metadata = {}
                call_record.call_metadata.update({
                    "last_event_type": event_type,
                    "last_event_at": now.isoformat(),
                    **{k: v for k, v in data.items() if k not in ["callId", "id", "to", "from", "transcript", "url", "recordingUrl"]}
                })
                updated = True
            
            if updated:
                session.commit()
                session.refresh(call_record)
        
        return {"status": "ok", "event_type": event_type, "call_id": call_id}
    
    except Exception as e:
        print(f"❌ Error processing VAPI webhook: {e}")
        import traceback
        traceback.print_exc()
        # Still return 200 to prevent VAPI from retrying
        return {"status": "error", "message": str(e)}


def _get_accessible_bot_numbers(session: Session, user_type: str, user_id: int) -> List[str]:
    """Return a list of bot numbers the current user is allowed to access."""
    accessible_numbers: List[str] = []
    
    if user_type == "property_manager":
        pm = session.get(PropertyManager, user_id)
        if not pm:
            raise HTTPException(status_code=404, detail="Property Manager not found")
        
        pm_bot = _get_or_sync_twilio_number(session, pm)
        if pm_bot:
            accessible_numbers.append(pm_bot)
        
        realtors = session.exec(
            select(Realtor).where(Realtor.property_manager_id == user_id)
        ).all()
        for realtor in realtors:
            realtor_bot = _get_or_sync_twilio_number(session, realtor)
            if realtor_bot:
                accessible_numbers.append(realtor_bot)
    
    elif user_type == "realtor":
        realtor = session.get(Realtor, user_id)
        if not realtor:
            raise HTTPException(status_code=404, detail="Realtor not found")
        
        realtor_bot = _get_or_sync_twilio_number(session, realtor)
        if realtor_bot:
            accessible_numbers.append(realtor_bot)
    
    return accessible_numbers


@app.get("/call-records")
def get_call_records(
    user_data: dict = Depends(get_current_user_data),
    limit: Optional[int] = 50,
    offset: Optional[int] = 0,
):
    """
    Get call records for the current user (PM or Realtor).
    - PMs see all calls for themselves AND their realtors
    - Realtors see only calls for their assigned number
    """
    user_type = user_data.get("user_type")
    user_id = user_data.get("id")
    
    if not user_type or not user_id:
        raise HTTPException(status_code=400, detail="Invalid user data")
    
    with Session(engine) as session:
        accessible_numbers = _get_accessible_bot_numbers(session, user_type, user_id)
        
        if not accessible_numbers:
            return JSONResponse(content={
                "call_records": [],
                "total": 0,
                "limit": limit,
                "offset": offset,
            })
        
        base_query = select(CallRecord).where(
            CallRecord.realtor_number.in_(accessible_numbers)
        )
        
        from sqlalchemy import func
        total_query = select(func.count(CallRecord.id)).where(
            CallRecord.realtor_number.in_(accessible_numbers)
        )
        total = session.exec(total_query).one()
        
        call_records = session.exec(
            base_query.order_by(CallRecord.created_at.desc()).limit(limit).offset(offset)
        ).all()
        
        return JSONResponse(content={
            "call_records": [
                {
                    "id": str(cr.id),
                    "call_id": cr.call_id,
                    "realtor_number": cr.realtor_number,
                    "recording_url": cr.recording_url,
                    "transcript": cr.transcript,
                    "call_duration": cr.call_duration,
                    "call_status": cr.call_status,
                    "caller_number": cr.caller_number,
                    "created_at": cr.created_at.isoformat() if cr.created_at else None,
                    "updated_at": cr.updated_at.isoformat() if cr.updated_at else None,
                }
                for cr in call_records
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        })


@app.get("/call-records/{call_id}")
def get_call_record_detail(
    call_id: str,
    user_data: dict = Depends(get_current_user_data),
):
    """
    Get detailed information about a specific call record.
    Includes full transcript and live transcript chunks.
    """
    user_type = user_data.get("user_type")
    user_id = user_data.get("id")
    
    if not user_type or not user_id:
        raise HTTPException(status_code=400, detail="Invalid user data")
    
    with Session(engine) as session:
        call_record = session.exec(
            select(CallRecord).where(CallRecord.call_id == call_id)
        ).first()
        
        if not call_record:
            raise HTTPException(status_code=404, detail="Call record not found")
        
        accessible_numbers = _get_accessible_bot_numbers(session, user_type, user_id)
        
        if call_record.realtor_number not in accessible_numbers:
            raise HTTPException(status_code=403, detail="Access denied to this call record")
        
        return JSONResponse(content={
            "id": str(call_record.id),
            "call_id": call_record.call_id,
            "realtor_number": call_record.realtor_number,
            "recording_url": call_record.recording_url,
            "transcript": call_record.transcript,
            "live_transcript_chunks": call_record.live_transcript_chunks or [],
            "call_duration": call_record.call_duration,
            "call_status": call_record.call_status,
            "caller_number": call_record.caller_number,
            "metadata": call_record.call_metadata,
            "created_at": call_record.created_at.isoformat() if call_record.created_at else None,
            "updated_at": call_record.updated_at.isoformat() if call_record.updated_at else None,
        })


@app.delete("/call-records/{call_id}")
def delete_call_record(
    call_id: str,
    hard_delete: bool = False,
    user_data: dict = Depends(get_current_user_data),
):
    """
    Delete a call record or purge its sensitive assets.
    - Default (hard_delete=false): Keep record metadata but remove transcript, live transcript chunks, and recording URL.
    - hard_delete=true: Permanently delete the call record row.
    
    Note: The call_id parameter should be the VAPI call_id (string), not the database UUID id.
    Use the 'call_id' field from GET /call-records response, not the 'id' field.
    """
    from urllib.parse import unquote
    
    user_type = user_data.get("user_type")
    user_id = user_data.get("id")
    
    if not user_type or not user_id:
        raise HTTPException(status_code=400, detail="Invalid user data")
    
    # URL decode the call_id in case it was encoded
    call_id = unquote(call_id).strip()
    
    if not call_id:
        raise HTTPException(status_code=400, detail="Invalid call_id: cannot be empty")
    
    with Session(engine) as session:
        # Try to find by call_id first (this is the correct field)
        call_record = session.exec(
            select(CallRecord).where(CallRecord.call_id == call_id)
        ).first()
        
        # If not found, check if they accidentally used the UUID id instead
        if not call_record:
            try:
                # Check if it's a UUID (database id)
                import uuid as uuid_lib
                uuid_obj = uuid_lib.UUID(call_id)
                # If it's a valid UUID, try to find by id
                call_record_by_id = session.get(CallRecord, uuid_obj)
                if call_record_by_id:
                    # They used the wrong field - provide helpful error
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid call_id: '{call_id}' appears to be a database UUID. Please use the 'call_id' field from the GET /call-records response, not the 'id' field. The correct call_id for this record is: '{call_record_by_id.call_id}'"
                    )
            except (ValueError, AttributeError):
                # Not a UUID, so it's just not found
                pass
        
        if not call_record:
            # Provide helpful debugging info
            # Check if there are any call records at all for this user
            accessible_numbers = _get_accessible_bot_numbers(session, user_type, user_id)
            if accessible_numbers:
                sample_records = session.exec(
                    select(CallRecord)
                    .where(CallRecord.realtor_number.in_(accessible_numbers))
                    .limit(1)
                ).all()
                if sample_records:
                    sample_call_id = sample_records[0].call_id
                    raise HTTPException(
                        status_code=404,
                        detail=f"Call record not found with call_id: '{call_id}'. Make sure you're using the 'call_id' field from GET /call-records response. Example call_id format: '{sample_call_id}'"
                    )
                else:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Call record not found with call_id: '{call_id}'. No call records found for your account."
                    )
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f"Call record not found with call_id: '{call_id}'. You don't have access to any call records."
                )
        
        accessible_numbers = _get_accessible_bot_numbers(session, user_type, user_id)
        if call_record.realtor_number not in accessible_numbers:
            raise HTTPException(status_code=403, detail="Access denied to this call record")
        
        if hard_delete:
            session.delete(call_record)
            session.commit()
            return {"message": "Call record permanently deleted", "call_id": call_id, "hard_delete": True}
        
        # Soft delete: remove sensitive assets but keep metadata for auditing
        call_record.transcript = None
        call_record.live_transcript_chunks = None
        call_record.recording_url = None
        call_record.updated_at = datetime.utcnow()
        if call_record.call_metadata is None:
            call_record.call_metadata = {}
        call_record.call_metadata["content_deleted_at"] = call_record.updated_at.isoformat()
        call_record.call_metadata["content_deleted_by"] = {
            "user_type": user_type,
            "user_id": user_id,
        }
        
        session.add(call_record)
        session.commit()
        session.refresh(call_record)
        
        return {
            "message": "Call transcript and recording removed",
            "call_id": call_id,
            "hard_delete": False,
        }


@app.get("/recordings")
def get_recordings(realtor_id: int = Depends(get_current_realtor_id)):
    recordings = []

    # Step 1: Look up the realtor in DB to get their Twilio number
    with Session(engine) as session:
        realtor = session.exec(select(Realtor).where(Realtor.realtor_id == realtor_id)).first()

        if not realtor:
            raise HTTPException(status_code=404, detail="Realtor not found")

        if not realtor.twilio_contact:
            raise HTTPException(
                status_code=400,
                detail="Realtor does not have a Twilio contact configured",
            )

        twilio_number = realtor.twilio_contact
        print("from supabse got twilio contact:", twilio_number)

    # Step 2: Fetch all calls from VAPI
    resp = requests.get(f"{VAPI_BASE_URL}/call", headers=headers)
    calls = resp.json()

    for call in calls:
        # Step 3: Get the phoneNumberId from the call
        phone_number_id = call.get("phoneNumberId")
        print("phone from vapi call id", phone_number_id)
        if not phone_number_id:
            continue

        # Step 4: Look up the number against the phoneNumberId
        pn_resp = requests.get(
            f"{VAPI_BASE_URL}/phone-number/{phone_number_id}", headers=headers
        )
        if pn_resp.status_code != 200:
            continue

        bot_number = pn_resp.json().get("number")
        print("bot number from vapi", bot_number)

        # Step 5: Match with realtor’s Twilio contact
        if bot_number != twilio_number:
            continue

        # Step 7: Extract recordings if available
        recording_url = call.get("artifact", {}).get("recordingUrl")

        if recording_url:
            recordings.append({"url": recording_url})

    return {"recordings": recordings}


@app.get("/chat-history")
async def get_all_chats_endpoint(realtor_id: int = Depends(get_current_realtor_id)):
    with Session(engine) as session:
        realtor = session.get(Realtor, realtor_id)
        realtor_number = realtor.twilio_contact
        realtor_number = "+14155238886"

    chats = get_all_chats(realtor_number)
    return chats


def get_all_chats(realtor_number: str):
    # Ensure WhatsApp format
    if not realtor_number.startswith("whatsapp:"):
        realtor_number = f"whatsapp:{realtor_number}"

    print(f"Fetching chats for {realtor_number}...")

    # Fetch all incoming and outgoing messages (pagination will be handled automatically by Twilio)
    incoming = twillio_client1.messages.list(to=realtor_number)
    outgoing = twillio_client1.messages.list(from_=realtor_number)
    messages = incoming + outgoing

    # Sort by date
    messages = sorted(messages, key=lambda m: m.date_sent or datetime.min)

    # Group messages by customer
    chats = {}
    for msg in messages:
        if msg.from_ == realtor_number:
            customer_number = msg.to
            sender = "realtor"
        else:
            customer_number = msg.from_
            sender = "customer"

        if customer_number not in chats:
            chats[customer_number] = []

        chats[customer_number].append(
            {
                "sender": sender,  # realtor / customer
                "message": msg.body,
                "timestamp": msg.date_sent.isoformat() if msg.date_sent else None,
            }
        )

    return {"chats": chats}


# ============================================================================
# PROPERTY TOUR BOOKING SYSTEM
# ============================================================================

def _send_sms_notification(phone_number: str, message: str):
    """Send SMS notification via Twilio."""
    client = twillio_client1 or twillio_client
    if not client:
        print(f"⚠️  Twilio client not available, skipping SMS to {phone_number}")
        return False
    
    try:
        client.messages.create(
            body=message,
            from_=FORWARDING_ALERT_FROM_NUMBER or TWILIO_PHONE_NUMBER.replace("whatsapp:", ""),
            to=phone_number,
        )
        return True
    except Exception as e:
        print(f"⚠️  Failed to send SMS to {phone_number}: {e}")
        return False


def _get_user_calendar_preferences(session: Session, user_id: int, user_type: str) -> Dict[str, Any]:
    """Get user's calendar preferences with defaults."""
    if user_type == "property_manager":
        user = session.get(PropertyManager, user_id)
    elif user_type == "realtor":
        user = session.get(Realtor, user_id)
    else:
        return {
            "timezone": "America/New_York",
            "defaultSlotLengthMins": 30,
            "workingHours": {"start": "09:00", "end": "17:00"},
            "workingDays": [0, 1, 2, 3, 4]  # Default: Monday-Friday
        }
    
    if not user:
        return {
            "timezone": "America/New_York",
            "defaultSlotLengthMins": 30,
            "workingHours": {"start": "09:00", "end": "17:00"},
            "workingDays": [0, 1, 2, 3, 4]  # Default: Monday-Friday
        }
    
    prefs = user.calendar_preferences or {}
    timezone = user.timezone or "America/New_York"
    
    return {
        "timezone": timezone,
        "defaultSlotLengthMins": prefs.get("defaultSlotLengthMins", 30),
        "workingHours": prefs.get("workingHours", {"start": "09:00", "end": "17:00"}),
        "workingDays": prefs.get("workingDays", [0, 1, 2, 3, 4])  # Default: Monday-Friday
    }


def _compute_available_slots(
    session: Session,
    user_id: int,
    user_type: str,
    from_date: datetime,
    to_date: datetime
) -> List[Dict[str, Any]]:
    """
    Compute available time slots for a user.
    
    Algorithm:
    1. Get user's working hours and timezone
    2. Generate all possible slots in date range based on working hours
    3. Subtract unavailable/busy slots
    4. Subtract existing approved bookings
    5. Return remaining available slots
    """
    try:
        from pytz import timezone as pytz_timezone
        import pytz
    except ImportError:
        # Fallback if pytz is not available - use simpler timezone handling
        print("⚠️  pytz not available, using UTC for timezone calculations")
        pytz = None
        pytz_timezone = None
    
    # Get user preferences
    prefs = _get_user_calendar_preferences(session, user_id, user_type)
    user_tz = pytz_timezone(prefs["timezone"])
    working_hours = prefs["workingHours"]
    slot_length = prefs["defaultSlotLengthMins"]
    
    # Parse working hours
    work_start = datetime.strptime(working_hours["start"], "%H:%M").time()
    work_end = datetime.strptime(working_hours["end"], "%H:%M").time()
    
    # Get all unavailable/busy slots
    busy_slots = session.exec(
        select(AvailabilitySlot).where(
            AvailabilitySlot.user_id == user_id,
            AvailabilitySlot.user_type == user_type,
            AvailabilitySlot.slot_type.in_(["unavailable", "busy", "booking"]),
            AvailabilitySlot.start_at >= from_date,
            AvailabilitySlot.end_at <= to_date
        )
    ).all()
    
    # Get all approved bookings
    approved_bookings = session.exec(
        select(PropertyTourBooking).where(
            PropertyTourBooking.assigned_to_user_id == user_id,
            PropertyTourBooking.assigned_to_user_type == user_type,
            PropertyTourBooking.status == "approved",
            PropertyTourBooking.start_at >= from_date,
            PropertyTourBooking.end_at <= to_date
        )
    ).all()
    
    # Generate available slots
    available_slots = []
    current_date = from_date.replace(hour=0, minute=0, second=0, microsecond=0)
    
    while current_date <= to_date:
        # Convert to user's timezone
        current_date_tz = pytz.utc.localize(current_date).astimezone(user_tz)
        work_start_dt = current_date_tz.replace(hour=work_start.hour, minute=work_start.minute, second=0, microsecond=0)
        work_end_dt = current_date_tz.replace(hour=work_end.hour, minute=work_end.minute, second=0, microsecond=0)
        
        # Convert back to UTC for comparison
        work_start_utc = work_start_dt.astimezone(pytz.utc).replace(tzinfo=None)
        work_end_utc = work_end_dt.astimezone(pytz.utc).replace(tzinfo=None)
        
        # Generate slots for this day
        slot_start = work_start_utc
        while slot_start < work_end_utc:
            slot_end = slot_start + timedelta(minutes=slot_length)
            if slot_end > work_end_utc:
                break
            
            # Check if slot conflicts with busy slots
            is_busy = False
            for busy in busy_slots:
                if not (slot_end <= busy.start_at or slot_start >= busy.end_at):
                    is_busy = True
                    break
            
            # Check if slot conflicts with approved bookings
            if not is_busy:
                for booking in approved_bookings:
                    if not (slot_end <= booking.start_at or slot_start >= booking.end_at):
                        is_busy = True
                        break
            
            if not is_busy:
                available_slots.append({
                    "startAt": slot_start.isoformat() + "Z",
                    "endAt": slot_end.isoformat() + "Z"
                })
            
            slot_start = slot_end
        
        current_date += timedelta(days=1)
    
    return available_slots


def _get_property_assigned_user(session: Session, property_id: int) -> Dict[str, Any]:
    """Get the assigned user (realtor or PM) for a property."""
    property_listing = session.get(ApartmentListing, property_id)
    if not property_listing:
        return None
    
    source = session.get(Source, property_listing.source_id)
    if not source:
        return None
    
    # If realtor is assigned, return realtor
    if source.realtor_id:
        realtor = session.get(Realtor, source.realtor_id)
        if realtor:
            return {
                "user_id": realtor.realtor_id,
                "user_type": "realtor",
                "name": realtor.name,
                "phone": realtor.contact,
                "email": realtor.email
            }
    
    # Otherwise return PM
    pm = session.get(PropertyManager, source.property_manager_id)
    if pm:
        return {
            "user_id": pm.property_manager_id,
            "user_type": "property_manager",
            "name": pm.name,
            "phone": pm.contact,
            "email": pm.email
        }
    
    return None


def _add_audit_log(booking: PropertyTourBooking, actor_id: int, action: str, reason: Optional[str] = None):
    """Add an entry to the booking's audit log."""
    if booking.audit_log is None:
        booking.audit_log = []
    
    booking.audit_log.append({
        "actorId": actor_id,
        "action": action,
        "timestamp": datetime.utcnow().isoformat(),
        "reason": reason
    })


# Property Search Endpoint (for VAPI)
@app.get("/api/search/properties")
async def search_properties(
    q: str,
    limit: int = 10,
    user_data: Optional[dict] = Depends(get_current_user_data)
):
    """
    Search properties by address for VAPI.
    Returns propertyId, status, assignedTo, and short availability summary.
    """
    with Session(engine) as session:
        # Use semantic search to find properties
        from vapi.rag import RAGEngine
        rag = RAGEngine()
        
        # Search for properties
        results = rag.search_apartments(q, limit=limit)
        
        property_results = []
        for result in results:
            property_id = result.get("id")
            if not property_id:
                continue
            
            property_listing = session.get(ApartmentListing, property_id)
            if not property_listing:
                continue
            
            # Get property status
            meta = property_listing.listing_metadata or {}
            listing_status = meta.get("listing_status", "unknown")
            
            # Get assigned user
            assigned_user = _get_property_assigned_user(session, property_id)
            
            # Get near-term availability (next 24-72 hours)
            if assigned_user:
                from_date = datetime.utcnow()
                to_date = from_date + timedelta(hours=72)
                available_slots = _compute_available_slots(
                    session,
                    assigned_user["user_id"],
                    assigned_user["user_type"],
                    from_date,
                    to_date
                )
                availability_summary = {
                    "hasAvailability": len(available_slots) > 0,
                    "nextAvailableSlot": available_slots[0] if available_slots else None,
                    "totalSlots": len(available_slots)
                }
            else:
                availability_summary = {"hasAvailability": False, "nextAvailableSlot": None, "totalSlots": 0}
            
            property_results.append({
                "propertyId": property_id,
                "address": meta.get("address", "Unknown"),
                "status": listing_status,
                "assignedTo": assigned_user,
                "availability": availability_summary
            })
        
        return JSONResponse(content={"properties": property_results})


# Get Property Details
@app.get("/api/properties/{property_id}")
async def get_property_details(
    property_id: int,
    user_data: dict = Depends(get_current_user_data)
):
    """Get property details including assigned PM/realtor and availability summary."""
    with Session(engine) as session:
        property_listing = session.get(ApartmentListing, property_id)
        if not property_listing:
            raise HTTPException(status_code=404, detail="Property not found")
        
        meta = property_listing.listing_metadata or {}
        source = session.get(Source, property_listing.source_id)
        
        # Get PM info
        pm = None
        if source and source.property_manager_id:
            pm_obj = session.get(PropertyManager, source.property_manager_id)
            if pm_obj:
                pm = {"id": pm_obj.property_manager_id, "name": pm_obj.name, "phone": pm_obj.contact, "email": pm_obj.email}
        
        # Get Realtor info
        realtor = None
        if source and source.realtor_id:
            realtor_obj = session.get(Realtor, source.realtor_id)
            if realtor_obj:
                realtor = {"id": realtor_obj.realtor_id, "name": realtor_obj.name, "phone": realtor_obj.contact, "email": realtor_obj.email}
        
        # Get assigned user for availability
        assigned_user = _get_property_assigned_user(session, property_id)
        availability_summary = None
        if assigned_user:
            from_date = datetime.utcnow()
            to_date = from_date + timedelta(days=7)
            available_slots = _compute_available_slots(
                session,
                assigned_user["user_id"],
                assigned_user["user_type"],
                from_date,
                to_date
            )
            availability_summary = {
                "hasAvailability": len(available_slots) > 0,
                "nextAvailableSlot": available_slots[0] if available_slots else None,
                "totalSlots": len(available_slots)
            }
        
        return JSONResponse(content={
            "property": {
                "id": property_listing.id,
                "address": meta.get("address", "Unknown"),
                "status": meta.get("listing_status", "unknown"),
                "metadata": meta
            },
            "pm": pm,
            "realtor": realtor,
            "availability": availability_summary
        })


# Get User Availability
@app.get("/api/users/{user_id}/availability")
async def get_user_availability(
    user_id: int,
    from_date: str,  # ISO format
    to_date: str,  # ISO format
    user_type: str,  # 'property_manager' | 'realtor'
    user_data: Optional[dict] = Depends(get_current_user_data)
):
    """Get computed available slots for a user in the date range."""
    try:
        from_dt = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
        to_dt = datetime.fromisoformat(to_date.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format.")
    
    with Session(engine) as session:
        # Verify user exists
        if user_type == "property_manager":
            user = session.get(PropertyManager, user_id)
        elif user_type == "realtor":
            user = session.get(Realtor, user_id)
        else:
            raise HTTPException(status_code=400, detail="Invalid user_type")
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        prefs = _get_user_calendar_preferences(session, user_id, user_type)
        available_slots = _compute_available_slots(session, user_id, user_type, from_dt, to_dt)
        
        return JSONResponse(content={
            "userId": user_id,
            "timezone": prefs["timezone"],
            "availableSlots": available_slots
        })


# Get Properties List for Dropdown (for manual event creation)
@app.get("/api/users/{user_id}/properties")
async def get_user_properties_for_dropdown(
    user_id: int,
    user_data: dict = Depends(get_current_user_data)
):
    """
    Get list of properties for dropdown selection when creating manual events.
    Returns properties accessible to the user (PM or Realtor).
    """
    authenticated_user_id = user_data["id"]
    user_type = user_data["user_type"]
    
    # Verify user can only view their own properties
    if authenticated_user_id != user_id:
        raise HTTPException(
            status_code=403, 
            detail="You can only view your own properties"
        )
    
    with Session(engine) as session:
        properties = []
        
        if user_type == "property_manager":
            # Get PM's own properties
            pm_sources = session.exec(
                select(Source).where(Source.property_manager_id == user_id)
            ).all()
            pm_source_ids = [s.source_id for s in pm_sources]
            
            # Get managed realtors' properties
            realtors = session.exec(
                select(Realtor).where(Realtor.property_manager_id == user_id)
            ).all()
            realtor_source_ids = []
            for realtor in realtors:
                realtor_sources = session.exec(
                    select(Source).where(Source.realtor_id == realtor.realtor_id)
                ).all()
                realtor_source_ids.extend([s.source_id for s in realtor_sources])
            
            all_source_ids = pm_source_ids + realtor_source_ids
        else:  # realtor
            sources = session.exec(
                select(Source).where(Source.realtor_id == user_id)
            ).all()
            all_source_ids = [s.source_id for s in sources]
        
        if all_source_ids:
            apartments = session.exec(
                select(ApartmentListing).where(ApartmentListing.source_id.in_(all_source_ids))
            ).all()
            
            for apt in apartments:
                meta = apt.listing_metadata or {}
                address = meta.get("address") or f"Property {apt.id}"
                properties.append({
                    "id": apt.id,
                    "address": address,
                    "price": meta.get("price"),
                    "bedrooms": meta.get("bedrooms"),
                    "bathrooms": meta.get("bathrooms"),
                    "listing_status": meta.get("listing_status", "unknown")
                })
        
        return JSONResponse(content={
            "properties": properties,
            "total": len(properties)
        })


# Create Manual Availability Slot (including holidays/off days)
@app.post("/api/users/{user_id}/availability")
async def create_availability_slot(
    user_id: int,
    user_type: str = Body(...),
    start_at: str = Body(...),  # ISO format
    end_at: str = Body(...),  # ISO format
    slot_type: str = Body(...),  # 'available' | 'unavailable' | 'busy' | 'personal' | 'holiday' | 'off_day'
    is_full_day: Optional[bool] = Body(False),  # If true, spans entire day(s)
    notes: Optional[str] = Body(None),  # Optional notes/reason
    user_data: dict = Depends(get_current_user_data)
):
    """
    Create manual availability/unavailability slot (PM/Realtor updates their own calendar).
    
    Supports:
    - Regular time slots (start_at to end_at)
    - Full-day events (holidays, off days) - set is_full_day=true and provide date
    - Busy periods, personal time, etc.
    """
    # Verify user can only update their own calendar
    if user_data.get("user_type") != user_type or user_data.get("id") != user_id:
        raise HTTPException(
            status_code=403, 
            detail="You can only update your own calendar"
        )
    
    # Validate required fields
    if not start_at or not start_at.strip():
        raise HTTPException(
            status_code=400,
            detail="start_at is required and cannot be empty"
        )
    
    if not end_at or not end_at.strip():
        raise HTTPException(
            status_code=400,
            detail="end_at is required and cannot be empty"
        )
    
    if not slot_type or not slot_type.strip():
        raise HTTPException(
            status_code=400,
            detail="slot_type is required and cannot be empty"
        )
    
    # Robust datetime parsing
    try:
        start_dt = _parse_datetime_robust(start_at, "start_at")
        end_dt = _parse_datetime_robust(end_at, "end_at")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error parsing dates: {str(e)}. Please use ISO format (e.g., 2025-12-01T16:00:00Z)."
        )
    
    if slot_type not in ["available", "unavailable", "busy", "personal", "holiday", "off_day"]:
        raise HTTPException(
            status_code=400, 
            detail="Invalid slot_type. Must be: available, unavailable, busy, personal, holiday, or off_day"
        )
    
    # For full-day events, adjust to start of day and end of day
    if is_full_day:
        # Set start to beginning of day (00:00:00)
        start_dt = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        # Set end to end of day (23:59:59)
        end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    if end_dt <= start_dt:
        raise HTTPException(
            status_code=400, 
            detail="end_at must be after start_at"
        )
    
    with Session(engine) as session:
        try:
            slot = AvailabilitySlot(
                user_id=user_id,
                user_type=user_type,
                start_at=start_dt,
                end_at=end_dt,
                slot_type=slot_type,
                source="manual"
            )
            session.add(slot)
            session.commit()
            session.refresh(slot)
            
            return JSONResponse(content={
                "slotId": slot.slot_id,
                "startAt": slot.start_at.isoformat(),
                "endAt": slot.end_at.isoformat(),
                "slotType": slot.slot_type,
                "isFullDay": is_full_day,
                "message": "Availability slot created successfully"
            })
        except Exception as e:
            session.rollback()
            error_msg = str(e) if isinstance(e, (str, Exception)) else repr(e)
            print(f"⚠️  Error creating availability slot: {error_msg}")
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create availability slot: {error_msg}"
            )


# Create Manual Booking/Tour (from dashboard)
@app.post("/api/bookings/manual")
async def create_manual_booking(
    property_id: int = Body(...),
    visitor_name: str = Body(...),
    visitor_phone: str = Body(...),
    visitor_email: Optional[str] = Body(None),
    start_at: str = Body(...),  # ISO format
    end_at: str = Body(...),  # ISO format
    timezone: Optional[str] = Body("America/New_York"),
    notes: Optional[str] = Body(None),
    user_data: dict = Depends(get_current_user_data)
):
    """
    Create a manual booking/tour from the dashboard.
    
    PM/Realtor can manually create a booking for a property.
    The booking is automatically approved (status='approved') since it's created by the approver.
    """
    user_type = user_data.get("user_type")
    user_id = user_data.get("id")
    
    # Validate required fields
    if not property_id:
        raise HTTPException(status_code=400, detail="property_id is required")
    if not visitor_name or not visitor_name.strip():
        raise HTTPException(status_code=400, detail="visitor_name is required and cannot be empty")
    if not visitor_phone or not visitor_phone.strip():
        raise HTTPException(status_code=400, detail="visitor_phone is required and cannot be empty")
    if not start_at or not start_at.strip():
        raise HTTPException(status_code=400, detail="start_at is required and cannot be empty")
    if not end_at or not end_at.strip():
        raise HTTPException(status_code=400, detail="end_at is required and cannot be empty")
    
    try:
        start_dt = _parse_datetime_robust(start_at, "start_at")
        end_dt = _parse_datetime_robust(end_at, "end_at")
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e) if isinstance(e, (str, Exception)) else repr(e)
        raise HTTPException(
            status_code=400,
            detail=f"Invalid date format: {error_msg}. Use ISO format (e.g., 2025-12-01T16:00:00Z)"
        )
    
    if end_dt <= start_dt:
        raise HTTPException(
            status_code=400,
            detail="end_at must be after start_at"
        )
    
    # Validate duration (max 8 hours)
    duration_hours = (end_dt - start_dt).total_seconds() / 3600
    if duration_hours > 8:
        raise HTTPException(
            status_code=400,
            detail=f"Booking duration ({duration_hours:.1f} hours) exceeds maximum allowed (8 hours)"
        )
    
    # Normalize phone number
    try:
        normalized_phone = _normalize_phone_robust(visitor_phone, "visitor_phone")
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e) if isinstance(e, (str, Exception)) else repr(e)
        raise HTTPException(
            status_code=400,
            detail=f"Invalid phone number format: {error_msg}"
        )
    
    with Session(engine) as session:
        # Verify property exists and user has access
        property_listing = session.get(ApartmentListing, property_id)
        if not property_listing:
            raise HTTPException(status_code=404, detail="Property not found")
        
        # Check if user has access to this property
        source = session.get(Source, property_listing.source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Property source not found")
        
        has_access = False
        if user_type == "property_manager":
            has_access = (source.property_manager_id == user_id)
        elif user_type == "realtor":
            has_access = (source.realtor_id == user_id)
        
        if not has_access:
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this property"
            )
        
        # Get assigned user for the property
        assigned_user = _get_property_assigned_user(session, property_id)
        if not assigned_user:
            raise HTTPException(
                status_code=400,
                detail="Property has no assigned PM or Realtor"
            )
        
        # Check for conflicts (approved bookings or busy slots)
        conflicting_bookings = session.exec(
            select(PropertyTourBooking).where(
                PropertyTourBooking.assigned_to_user_id == assigned_user["user_id"],
                PropertyTourBooking.assigned_to_user_type == assigned_user["user_type"],
                PropertyTourBooking.status == "approved",
                PropertyTourBooking.deleted_at.is_(None),
                or_(
                    and_(
                        PropertyTourBooking.start_at < end_dt,
                        PropertyTourBooking.end_at > start_dt
                    )
                )
            )
        ).first()
        
        if conflicting_bookings:
            raise HTTPException(
                status_code=409,
                detail=f"Time slot conflicts with existing approved booking (ID: {conflicting_bookings.booking_id})"
            )
        
        # Create the booking (automatically approved since created by approver)
        booking = PropertyTourBooking(
            property_id=property_id,
            assigned_to_user_id=assigned_user["user_id"],
            assigned_to_user_type=assigned_user["user_type"],
            visitor_name=visitor_name,
            visitor_phone=normalized_phone,
            visitor_email=visitor_email,
            requested_at=datetime.utcnow(),
            start_at=start_dt,
            end_at=end_dt,
            timezone=timezone or "America/New_York",
            status="approved",  # Auto-approved since created by approver
            created_by="ui",  # Manual creation from UI
            notes=notes,
            audit_log=[{
                "action": "created_manually",
                "actor_id": user_id,
                "actor_type": user_type,
                "timestamp": datetime.utcnow().isoformat()
            }]
        )
        try:
            session.add(booking)
            session.commit()
            session.refresh(booking)
            
            # Create blocking availability slot
            blocking_slot = AvailabilitySlot(
                user_id=assigned_user["user_id"],
                user_type=assigned_user["user_type"],
                start_at=start_dt,
                end_at=end_dt,
                slot_type="booking",
                source="booking",
                booking_id=booking.booking_id
            )
            session.add(blocking_slot)
            session.commit()
            session.refresh(blocking_slot)
        except Exception as db_error:
            session.rollback()
            error_msg = str(db_error) if isinstance(db_error, (str, Exception)) else repr(db_error)
            print(f"⚠️  Error creating booking: {error_msg}")
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create booking: {error_msg}"
            )
        
        # Send notification to visitor (if phone/email provided)
        if normalized_phone:
            try:
                property_meta = property_listing.listing_metadata or {}
                property_address = property_meta.get("address", f"Property {property_id}")
                message = f"Your tour for {property_address} has been scheduled for {start_dt.strftime('%B %d, %Y at %I:%M %p')}."
                _send_sms_notification(normalized_phone, message)
            except Exception as sms_error:
                error_msg = str(sms_error) if isinstance(sms_error, (str, Exception)) else repr(sms_error)
                print(f"⚠️  Failed to send SMS notification: {error_msg}")
                # Don't fail if SMS fails - booking is already created
        
        return JSONResponse(content={
            "bookingId": booking.booking_id,
            "status": booking.status,
            "propertyId": property_id,
            "visitorName": visitor_name,
            "startAt": booking.start_at.isoformat(),
            "endAt": booking.end_at.isoformat(),
            "message": "Manual booking created and approved successfully"
        }, status_code=201)


# Create Booking Request
# Create Booking Request (VAPI) - No property_id, only property_name
@app.post("/vapi/bookings/request")
async def create_booking_request_vapi(
    http_request: Request,  # FastAPI will inject this - must be first
    request: Optional[VapiRequest] = None,
    property_name: Optional[str] = Body(None),
    visitor_name: Optional[str] = Body(None),
    visitor_phone: Optional[str] = Body(None),
    visitor_email: Optional[str] = Body(None),
    requested_start_at: Optional[str] = Body(None),
    requested_end_at: Optional[str] = Body(None),
    timezone: Optional[str] = Body(None),
    notes: Optional[str] = Body(None)
):
    """
    Create a booking request (called by VAPI or other clients).
    Creates booking with status 'pending' - never auto-approves.
    
    Accepts BOTH formats:
    1. VapiRequest format with toolCalls (from VAPI)
    2. Regular JSON body with direct parameters (from other clients)
    
    No property_id needed - only property_name (user-provided).
    """
    # Parse request body once (can only be read once)
    request_body = {}
    request_headers = {}
    tool_call_id = None
    
    if http_request:
        try:
            request_body = await http_request.json()
            request_headers = dict(http_request.headers)
            # Extract toolCallId from body if present
            if request_body.get("message") and request_body["message"].get("toolCalls"):
                tool_calls = request_body["message"]["toolCalls"]
                if tool_calls and len(tool_calls) > 0:
                    tool_call_id = tool_calls[0].get("id")
        except Exception as e:
            print(f"⚠️  Error parsing request body: {e}")
            # Continue with empty body if parsing fails
    
    # Extract parameters from VapiRequest toolCalls if provided
    if request and hasattr(request, 'message') and hasattr(request.message, 'toolCalls') and request.message.toolCalls:
        for tool_call in request.message.toolCalls:
            if tool_call.function.name in ["createBooking", "requestTour", "bookTour", "createBookingRequest"]:
                tool_call_id = tool_call.id
                args = tool_call.function.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except:
                        args = {}
                
                property_name = property_name or args.get("property_name") or args.get("propertyName")
                visitor_name = visitor_name or args.get("visitor_name") or args.get("visitorName")
                visitor_phone = visitor_phone or args.get("visitor_phone") or args.get("visitorPhone")
                visitor_email = visitor_email or args.get("visitor_email") or args.get("visitorEmail")
                requested_start_at = requested_start_at or args.get("requested_start_at") or args.get("requestedStartAt")
                requested_end_at = requested_end_at or args.get("requested_end_at") or args.get("requestedEndAt")
                timezone = timezone or args.get("timezone") or "America/New_York"
                notes = notes or args.get("notes")
                break
    
    # If still missing, try to get from request body directly (already parsed above)
    if not property_name or not visitor_name or not visitor_phone:
        property_name = property_name or request_body.get("property_name") or request_body.get("propertyName")
        visitor_name = visitor_name or request_body.get("visitor_name") or request_body.get("visitorName")
        visitor_phone = visitor_phone or request_body.get("visitor_phone") or request_body.get("visitorPhone")
        visitor_email = visitor_email or request_body.get("visitor_email") or request_body.get("visitorEmail")
        requested_start_at = requested_start_at or request_body.get("requested_start_at") or request_body.get("requestedStartAt")
        requested_end_at = requested_end_at or request_body.get("requested_end_at") or request_body.get("requestedEndAt")
        timezone = timezone or request_body.get("timezone") or "America/New_York"
        notes = notes or request_body.get("notes")
    
    # Set defaults
    if not timezone:
        timezone = "America/New_York"
    
    # Validate required fields - property_name is required (no property_id from VAPI)
    if not property_name or not property_name.strip():
        raise HTTPException(
            status_code=400,
            detail="property_name is required. Please provide the property name or address."
        )
    
    if not visitor_name or not visitor_name.strip():
        raise HTTPException(
            status_code=400,
            detail="visitor_name is required and cannot be empty."
        )
    
    if not visitor_phone or not visitor_phone.strip():
        raise HTTPException(
            status_code=400,
            detail="visitor_phone is required. Please provide a valid phone number."
        )
    
    # Validate required datetime fields
    if not requested_start_at or not requested_start_at.strip():
        raise HTTPException(
            status_code=400,
            detail="requested_start_at is required. Please provide the requested start time in ISO format (e.g., 2025-12-01T16:00:00Z)."
        )
    
    if not requested_end_at or not requested_end_at.strip():
        raise HTTPException(
            status_code=400,
            detail="requested_end_at is required. Please provide the requested end time in ISO format (e.g., 2025-12-01T16:30:00Z)."
        )
    
    # Robust datetime parsing
    try:
        start_dt = _parse_datetime_robust(requested_start_at, "requested_start_at")
        end_dt = _parse_datetime_robust(requested_end_at, "requested_end_at")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error parsing dates: {str(e)}. Please use ISO format (e.g., 2025-12-01T16:00:00Z)"
        )
    
    # Validate time constraints
    now = datetime.utcnow().replace(tzinfo=timezone.utc)
    two_weeks_from_now = now + timedelta(days=14)
    
    if start_dt < now:
        hours_ago = (now - start_dt).total_seconds() / 3600
        raise HTTPException(
            status_code=400,
            detail=f"Requested start time cannot be in the past. The time was {hours_ago:.1f} hours ago."
        )
    
    if start_dt > two_weeks_from_now:
        days_ahead = (start_dt - now).days
        raise HTTPException(
            status_code=400,
            detail=f"Tour requests must be within 2 weeks. The requested time is {days_ahead} days away."
        )
    
    if end_dt <= start_dt:
        raise HTTPException(
            status_code=400,
            detail="End time must be after start time."
        )
    
    # Validate duration
    duration_minutes = (end_dt - start_dt).total_seconds() / 60
    if duration_minutes < 15:
        raise HTTPException(
            status_code=400,
            detail=f"Tour duration is too short ({duration_minutes:.0f} minutes). Minimum is 15 minutes."
        )
    if duration_minutes > 120:
        raise HTTPException(
            status_code=400,
            detail=f"Tour duration is too long ({duration_minutes:.0f} minutes). Maximum is 2 hours."
        )
    
    # Robust phone normalization
    try:
        normalized_phone = _normalize_phone_robust(visitor_phone, "visitor_phone")
    except HTTPException:
        raise
    
    with Session(engine) as session:
        # Get source_ids for property search if needed (using already parsed body)
        source_ids = None
        if http_request:
            try:
                from DB.vapi_helpers import identify_user_from_vapi_request
                user_info = identify_user_from_vapi_request(request_body, request_headers)
                source_ids = user_info.get("source_ids") if user_info else None
            except Exception as e:
                print(f"⚠️  Error identifying user from VAPI request: {e}")
                pass
        
        # Robust property finding - only use property_name (no property_id)
        property_listing, found_property_id, error_msg = _find_property_robust(
            session, None, property_name, source_ids  # No property_id, only property_name
        )
        
        if not property_listing:
            raise HTTPException(status_code=404, detail=error_msg or "Property not found.")
        
        property_id = found_property_id  # Use found property_id
        
        meta = property_listing.listing_metadata or {}
        listing_status = meta.get("listing_status", "unknown")
        if listing_status != "available":
            raise HTTPException(
                status_code=409,
                detail=f"Property is not available for tours. Current status: {listing_status}. Only properties with status 'available' can accept tour bookings."
            )
        
        # Get assigned user (realtor if assigned, else PM)
        assigned_user = _get_property_assigned_user(session, property_id)
        if not assigned_user:
            raise HTTPException(
                status_code=400,
                detail="Property has no assigned PM or Realtor. Please assign a user to the property before creating bookings."
            )
        
        # Extract call record information from headers (if booking came from VAPI call)
        vapi_call_id = None
        call_transcript = None
        call_recording_url = None
        
        if http_request:
            try:
                # Use already parsed headers
                header_keys_lower = {k.lower(): v for k, v in request_headers.items()}
                
                # Extract call_id from headers
                vapi_call_id = header_keys_lower.get("x-call-id") or header_keys_lower.get("x-vapi-call-id")
                
                # If we have a call_id, try to get call record from database
                if vapi_call_id:
                    call_record = session.exec(
                        select(CallRecord).where(CallRecord.call_id == vapi_call_id)
                    ).first()
                    
                    if call_record:
                        call_transcript = call_record.transcript
                        call_recording_url = call_record.recording_url
                        print(f"✅ Linked booking to call record: {vapi_call_id}")
            except Exception as e:
                print(f"⚠️  Error extracting call record info: {e}")
                # Don't fail the booking creation if call record linking fails
        
        # Create booking
        booking = PropertyTourBooking(
            property_id=property_id,
            assigned_to_user_id=assigned_user["user_id"],
            assigned_to_user_type=assigned_user["user_type"],
            visitor_name=visitor_name,
            visitor_phone=normalized_phone,
            visitor_email=visitor_email,
            requested_at=datetime.utcnow(),
            start_at=start_dt,
            end_at=end_dt,
            timezone=timezone,
            status="pending",
            created_by="vapi",  # Always "vapi" for VAPI endpoint
            notes=notes,
            vapi_call_id=vapi_call_id,
            call_transcript=call_transcript,
            call_recording_url=call_recording_url,
            audit_log=[{
                "actorId": None,
                "action": "created",
                "timestamp": datetime.utcnow().isoformat(),
                "reason": "Created by vapi"
            }]
        )
        
        session.add(booking)
        session.commit()
        session.refresh(booking)
        
        # Notify assigned user (don't fail booking creation if SMS fails)
        try:
            if assigned_user.get("phone"):
                notification_msg = f"New tour booking request from {visitor_name} ({normalized_phone}) for {meta.get('address', 'property')} on {start_dt.strftime('%Y-%m-%d %H:%M')}"
                _send_sms_notification(assigned_user["phone"], notification_msg)
        except Exception as e:
            print(f"⚠️  Failed to send SMS notification: {str(e)}")
        
        # Also notify PM if different from assigned user
        try:
            source = session.get(Source, property_listing.source_id)
            if source and source.property_manager_id != assigned_user["user_id"]:
                pm = session.get(PropertyManager, source.property_manager_id)
                if pm and pm.contact:
                    notification_msg = f"New tour booking request from {visitor_name} ({normalized_phone}) for {meta.get('address', 'property')} on {start_dt.strftime('%Y-%m-%d %H:%M')}"
                    _send_sms_notification(pm.contact, notification_msg)
        except Exception as e:
            print(f"⚠️  Failed to send PM SMS notification: {str(e)}")
        
        result_data = {
            "bookingId": booking.booking_id,
            "status": "pending",
            "message": "Booking request created successfully. Awaiting approval."
        }
        
        # Return in VAPI format if toolCallId is present, otherwise return direct JSON
        if tool_call_id:
            return {"results": [{"toolCallId": tool_call_id, "result": result_data}]}
        else:
            return JSONResponse(content=result_data, status_code=201)


# Get Booking Details
@app.get("/api/bookings/{booking_id}")
async def get_booking_details(
    booking_id: int,
    user_data: dict = Depends(get_current_user_data)
):
    """Get booking details."""
    with Session(engine) as session:
        booking = session.get(PropertyTourBooking, booking_id)
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        
        # Check permissions
        user_type = user_data["user_type"]
        user_id = user_data["id"]
        
        # User can view if they're the approver or PM managing the property
        can_view = (
            booking.assigned_to_user_id == user_id and booking.assigned_to_user_type == user_type
        )
        
        if not can_view and user_type == "property_manager":
            # Check if PM owns the property
            property_listing = session.get(ApartmentListing, booking.property_id)
            if property_listing:
                source = session.get(Source, property_listing.source_id)
                if source and source.property_manager_id == user_id:
                    can_view = True
        
        if not can_view:
            raise HTTPException(status_code=403, detail="Access denied")
        
        return JSONResponse(content={
            "bookingId": booking.booking_id,
            "propertyId": booking.property_id,
            "assignedTo": {
                "userId": booking.assigned_to_user_id,
                "userType": booking.assigned_to_user_type
            },
            "visitor": {
                "name": booking.visitor_name,
                "phone": booking.visitor_phone,
                "email": booking.visitor_email
            },
            "requestedAt": booking.requested_at.isoformat(),
            "startAt": booking.start_at.isoformat(),
            "endAt": booking.end_at.isoformat(),
            "timezone": booking.timezone,
            "status": booking.status,
            "createdBy": booking.created_by,
            "notes": booking.notes,
            "proposedSlots": booking.proposed_slots,
            "auditLog": booking.audit_log,
            "callRecord": {
                "vapiCallId": booking.vapi_call_id,
                "callTranscript": booking.call_transcript,
                "callRecordingUrl": booking.call_recording_url
            } if booking.vapi_call_id else None,
            "createdAt": booking.created_at.isoformat(),
            "updatedAt": booking.updated_at.isoformat()
        })


# Get All Calendar Events (Bookings + Availability Slots)
@app.get("/api/users/{user_id}/calendar-events")
async def get_calendar_events(
    user_id: int,
    from_date: str,  # ISO format
    to_date: str,  # ISO format
    user_data: dict = Depends(get_current_user_data)
):
    """
    Get all calendar events for a user (bookings + availability slots).
    Returns both bookings and manual availability slots for calendar display.
    """
    authenticated_user_id = user_data["id"]
    user_type = user_data["user_type"]
    
    # Verify user can only view their own calendar
    if authenticated_user_id != user_id:
        raise HTTPException(
            status_code=403, 
            detail="You can only view your own calendar"
        )
    
    try:
        from_dt = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
        to_dt = datetime.fromisoformat(to_date.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format.")
    
    with Session(engine) as session:
        # Get bookings
        bookings_query = select(PropertyTourBooking).where(
            PropertyTourBooking.assigned_to_user_id == user_id,
            PropertyTourBooking.assigned_to_user_type == user_type,
            PropertyTourBooking.deleted_at.is_(None),
            PropertyTourBooking.start_at >= from_dt,
            PropertyTourBooking.end_at <= to_dt
        )
        
        # If PM, also include bookings for properties they manage
        if user_type == "property_manager":
            properties = session.exec(
                select(ApartmentListing).join(Source).where(
                    Source.property_manager_id == user_id
                )
            ).all()
            property_ids = [p.id for p in properties]
            if property_ids:
                bookings_query = select(PropertyTourBooking).where(
                    or_(
                        and_(
                            PropertyTourBooking.assigned_to_user_id == user_id,
                            PropertyTourBooking.assigned_to_user_type == user_type
                        ),
                        PropertyTourBooking.property_id.in_(property_ids)
                    ),
                    PropertyTourBooking.deleted_at.is_(None),
                    PropertyTourBooking.start_at >= from_dt,
                    PropertyTourBooking.end_at <= to_dt
                )
        
        bookings = session.exec(bookings_query).all()
        
        # Get availability slots (manual events, holidays, off days, etc.)
        slots_query = select(AvailabilitySlot).where(
            AvailabilitySlot.user_id == user_id,
            AvailabilitySlot.user_type == user_type,
            AvailabilitySlot.start_at >= from_dt,
            AvailabilitySlot.end_at <= to_dt
        )
        slots = session.exec(slots_query).all()
        
        # Format bookings
        booking_events = []
        for booking in bookings:
            property_listing = session.get(ApartmentListing, booking.property_id)
            property_meta = property_listing.listing_metadata or {} if property_listing else {}
            
            booking_events.append({
                "id": f"booking_{booking.booking_id}",
                "type": "booking",
                "bookingId": booking.booking_id,
                "propertyId": booking.property_id,
                "propertyAddress": property_meta.get("address", f"Property {booking.property_id}"),
                "visitorName": booking.visitor_name,
                "visitorPhone": booking.visitor_phone,
                "visitorEmail": booking.visitor_email,
                "startAt": booking.start_at.isoformat(),
                "endAt": booking.end_at.isoformat(),
                "status": booking.status,
                "timezone": booking.timezone,
                "notes": booking.notes,
                "createdBy": booking.created_by,
                "callRecord": {
                    "vapiCallId": booking.vapi_call_id,
                    "callTranscript": booking.call_transcript,
                    "callRecordingUrl": booking.call_recording_url
                } if booking.vapi_call_id else None
            })
        
        # Format availability slots
        slot_events = []
        for slot in slots:
            slot_events.append({
                "id": f"slot_{slot.slot_id}",
                "type": "availability_slot",
                "slotId": slot.slot_id,
                "startAt": slot.start_at.isoformat(),
                "endAt": slot.end_at.isoformat(),
                "slotType": slot.slot_type,
                "source": slot.source,
                "isFullDay": (
                    slot.start_at.hour == 0 and slot.start_at.minute == 0 and
                    slot.end_at.hour == 23 and slot.end_at.minute == 59
                )
            })
        
        # Combine and sort by start time
        all_events = booking_events + slot_events
        all_events.sort(key=lambda x: x["startAt"])
        
        return JSONResponse(content={
            "userId": user_id,
            "userType": user_type,
            "fromDate": from_date,
            "toDate": to_date,
            "events": all_events,
            "bookings": booking_events,
            "availabilitySlots": slot_events,
            "total": len(all_events)
        })


# Get User's Bookings
@app.get("/api/users/{user_id}/bookings")
async def get_user_bookings(
    user_id: int,
    status: Optional[str] = None,
    from_date: Optional[str] = None,
    user_data: dict = Depends(get_current_user_data)
):
    """
    Get bookings for a user (for dashboards).
    Derives user_type from authenticated user_data instead of requiring it as parameter.
    """
    # Get user_type from authenticated user data
    user_type = user_data["user_type"]
    authenticated_user_id = user_data["id"]
    
    # Verify user can only view their own bookings
    if authenticated_user_id != user_id:
        raise HTTPException(
            status_code=403, 
            detail="You can only view your own bookings"
        )
    
    with Session(engine) as session:
        # Build query - filter by assigned user
        query = select(PropertyTourBooking).where(
            PropertyTourBooking.assigned_to_user_id == user_id,
            PropertyTourBooking.assigned_to_user_type == user_type,
            PropertyTourBooking.deleted_at.is_(None)  # Exclude deleted bookings
        )
        
        # If PM, also include bookings for properties they manage (even if assigned to realtor)
        if user_type == "property_manager":
            # Get all properties managed by this PM
            properties = session.exec(
                select(ApartmentListing).join(Source).where(
                    Source.property_manager_id == user_id
                )
            ).all()
            property_ids = [p.id for p in properties]
            
            if property_ids:
                # Include bookings for PM's properties, even if assigned to a realtor
                query = select(PropertyTourBooking).where(
                    or_(
                        # Bookings assigned directly to PM
                        and_(
                            PropertyTourBooking.assigned_to_user_id == user_id,
                            PropertyTourBooking.assigned_to_user_type == "property_manager"
                        ),
                        # Bookings for PM's properties (assigned to realtors)
                        and_(
                            PropertyTourBooking.property_id.in_(property_ids),
                            PropertyTourBooking.assigned_to_user_type == "realtor"
                        )
                    ),
                    PropertyTourBooking.deleted_at.is_(None)
                )
        
        if status:
            query = query.where(PropertyTourBooking.status == status)
        
        if from_date:
            try:
                from_dt = _parse_datetime_robust(from_date, "from_date")
                query = query.where(PropertyTourBooking.start_at >= from_dt)
            except HTTPException:
                raise
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid from_date format. Use ISO format (e.g., 2025-12-01T00:00:00Z)")
        
        bookings = session.exec(query.order_by(PropertyTourBooking.start_at.desc())).all()
        
        # Get property details for each booking
        result_bookings = []
        for b in bookings:
            property_listing = session.get(ApartmentListing, b.property_id)
            property_address = None
            if property_listing:
                meta = property_listing.listing_metadata or {}
                property_address = meta.get("address", "Unknown")
            
            result_bookings.append({
                "bookingId": b.booking_id,
                "propertyId": b.property_id,
                "propertyAddress": property_address,
                "visitor": {
                    "name": b.visitor_name,
                    "phone": b.visitor_phone,
                    "email": b.visitor_email
                },
                "startAt": b.start_at.isoformat(),
                "endAt": b.end_at.isoformat(),
                "timezone": b.timezone,
                "status": b.status,
                "createdBy": b.created_by,
                "notes": b.notes,
                "assignedTo": {
                    "userId": b.assigned_to_user_id,
                    "userType": b.assigned_to_user_type
                },
                "requestedAt": b.requested_at.isoformat() if b.requested_at else None,
                "createdAt": b.created_at.isoformat() if b.created_at else None,
                "updatedAt": b.updated_at.isoformat() if b.updated_at else None
            })
        
        return JSONResponse(content={
            "bookings": result_bookings,
            "total": len(result_bookings)
        })


# Approve Booking
@app.post("/api/bookings/{booking_id}/approve")
async def approve_booking(
    booking_id: int,
    approver_id: int = Body(...),
    note: Optional[str] = Body(None),
    user_data: dict = Depends(get_current_user_data)
):
    """
    Approve a booking request.
    Atomically checks for conflicts and creates blocking availability slot.
    """
    user_type = user_data["user_type"]
    user_id = user_data["id"]
    
    with Session(engine) as session:
        # Start transaction
        booking = session.get(PropertyTourBooking, booking_id)
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        
        # Verify caller is the approver
        if booking.assigned_to_user_id != user_id or booking.assigned_to_user_type != user_type:
            raise HTTPException(status_code=403, detail="Only the assigned approver can approve this booking")
        
        if booking.status != "pending":
            raise HTTPException(status_code=400, detail=f"Booking is not pending (current status: {booking.status})")
        
        # Atomically check for conflicts
        conflicting_bookings = session.exec(
            select(PropertyTourBooking).where(
                PropertyTourBooking.assigned_to_user_id == user_id,
                PropertyTourBooking.assigned_to_user_type == user_type,
                PropertyTourBooking.status == "approved",
                PropertyTourBooking.booking_id != booking_id,
                or_(
                    and_(
                        PropertyTourBooking.start_at < booking.end_at,
                        PropertyTourBooking.end_at > booking.start_at
                    )
                )
            )
        ).all()
        
        if conflicting_bookings:
            raise HTTPException(
                status_code=409,
                detail="Time slot conflicts with an existing approved booking"
            )
        
        # Check property status
        property_listing = session.get(ApartmentListing, booking.property_id)
        if property_listing:
            meta = property_listing.listing_metadata or {}
            if meta.get("listing_status") != "available":
                raise HTTPException(
                    status_code=409,
                    detail=f"Property is no longer available (status: {meta.get('listing_status')})"
                )
        
        # Update booking status
        booking.status = "approved"
        booking.updated_at = datetime.utcnow()
        _add_audit_log(booking, user_id, "approved", note)
        
        # Create blocking availability slot
        blocking_slot = AvailabilitySlot(
            user_id=user_id,
            user_type=user_type,
            start_at=booking.start_at,
            end_at=booking.end_at,
            slot_type="booking",
            source="booking",
            booking_id=booking.booking_id
        )
        session.add(blocking_slot)
        session.commit()
        session.refresh(blocking_slot)
        session.refresh(booking)
        
        # Send confirmation to visitor
        property_listing = session.get(ApartmentListing, booking.property_id)
        property_address = "the property"
        if property_listing:
            meta = property_listing.listing_metadata or {}
            property_address = meta.get("address", "the property")
        
        confirmation_msg = f"Your tour booking for {property_address} is confirmed for {booking.start_at.strftime('%Y-%m-%d at %H:%M')}. We look forward to showing you around!"
        _send_sms_notification(booking.visitor_phone, confirmation_msg)
        
        return JSONResponse(content={
            "bookingId": booking.booking_id,
            "status": "approved",
            "blockedSlotId": blocking_slot.slot_id,
            "message": "Booking approved successfully"
        })


# Deny Booking
@app.post("/api/bookings/{booking_id}/deny")
async def deny_booking(
    booking_id: int,
    approver_id: int = Body(...),
    reason: Optional[str] = Body(None),
    user_data: dict = Depends(get_current_user_data)
):
    """Deny a booking request."""
    user_type = user_data["user_type"]
    user_id = user_data["id"]
    
    with Session(engine) as session:
        booking = session.get(PropertyTourBooking, booking_id)
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        
        if booking.assigned_to_user_id != user_id or booking.assigned_to_user_type != user_type:
            raise HTTPException(status_code=403, detail="Only the assigned approver can deny this booking")
        
        if booking.status != "pending":
            raise HTTPException(status_code=400, detail=f"Booking is not pending (current status: {booking.status})")
        
        booking.status = "denied"
        booking.updated_at = datetime.utcnow()
        _add_audit_log(booking, user_id, "denied", reason)
        session.add(booking)
        session.commit()
        
        # Notify visitor
        denial_msg = f"Unfortunately, your tour booking request could not be accommodated. {reason or 'Please try selecting a different time slot.'}"
        _send_sms_notification(booking.visitor_phone, denial_msg)
        
        return JSONResponse(content={
            "bookingId": booking.booking_id,
            "status": "denied",
            "message": "Booking denied successfully"
        })


# Reschedule Booking
@app.post("/api/bookings/{booking_id}/reschedule")
async def reschedule_booking(
    booking_id: int,
    proposed_slots: List[Dict[str, str]] = Body(...),  # Array of {startAt, endAt}
    approver_id: int = Body(...),
    note: Optional[str] = Body(None),
    user_data: dict = Depends(get_current_user_data)
):
    """Reschedule a booking - approver suggests alternative slots."""
    user_type = user_data["user_type"]
    user_id = user_data["id"]
    
    with Session(engine) as session:
        booking = session.get(PropertyTourBooking, booking_id)
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        
        if booking.assigned_to_user_id != user_id or booking.assigned_to_user_type != user_type:
            raise HTTPException(status_code=403, detail="Only the assigned approver can reschedule this booking")
        
        if booking.status not in ["pending", "rescheduled"]:
            raise HTTPException(status_code=400, detail=f"Cannot reschedule booking with status: {booking.status}")
        
        # Validate proposed slots
        validated_slots = []
        for slot in proposed_slots:
            try:
                start_dt = datetime.fromisoformat(slot["startAt"].replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(slot["endAt"].replace("Z", "+00:00"))
                validated_slots.append({"startAt": start_dt.isoformat() + "Z", "endAt": end_dt.isoformat() + "Z"})
            except (KeyError, ValueError):
                raise HTTPException(status_code=400, detail="Invalid slot format. Each slot must have startAt and endAt in ISO format.")
        
        booking.status = "rescheduled"
        booking.proposed_slots = validated_slots
        booking.updated_at = datetime.utcnow()
        _add_audit_log(booking, user_id, "rescheduled", note)
        session.add(booking)
        session.commit()
        
        # Notify visitor
        reschedule_msg = f"Your tour booking has been rescheduled. Please select from the available time slots we've proposed. {note or ''}"
        _send_sms_notification(booking.visitor_phone, reschedule_msg)
        
        return JSONResponse(content={
            "bookingId": booking.booking_id,
            "status": "rescheduled",
            "proposedSlots": validated_slots,
            "message": "Booking rescheduled successfully"
        })


# Cancel Booking
@app.post("/api/bookings/{booking_id}/cancel")
async def cancel_booking(
    booking_id: int,
    reason: Optional[str] = Body(None),
    user_data: dict = Depends(get_current_user_data)
):
    """Cancel a booking (either party can cancel)."""
    user_type = user_data["user_type"]
    user_id = user_data["id"]
    
    with Session(engine) as session:
        booking = session.get(PropertyTourBooking, booking_id)
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        
        # Check if user is the approver or visitor (by phone)
        is_approver = (
            booking.assigned_to_user_id == user_id and booking.assigned_to_user_type == user_type
        )
        is_visitor = False  # In a real system, you'd verify visitor identity
        
        if not is_approver and not is_visitor:
            raise HTTPException(status_code=403, detail="You don't have permission to cancel this booking")
        
        if booking.status in ["cancelled", "denied"]:
            raise HTTPException(status_code=400, detail=f"Booking is already {booking.status}")
        
        old_status = booking.status
        booking.status = "cancelled"
        booking.updated_at = datetime.utcnow()
        _add_audit_log(booking, user_id, "cancelled", reason)
        
        # If booking was approved, remove the blocking slot
        if old_status == "approved":
            blocking_slot = session.exec(
                select(AvailabilitySlot).where(
                    AvailabilitySlot.booking_id == booking_id,
                    AvailabilitySlot.slot_type == "booking"
                )
            ).first()
            if blocking_slot:
                session.delete(blocking_slot)
        
        session.add(booking)
        session.commit()
        
        # Notify the other party
        if is_approver:
            _send_sms_notification(booking.visitor_phone, f"Your tour booking has been cancelled. {reason or ''}")
        else:
            # Notify approver
            if booking.assigned_to_user_type == "property_manager":
                approver = session.get(PropertyManager, booking.assigned_to_user_id)
            else:
                approver = session.get(Realtor, booking.assigned_to_user_id)
            if approver:
                _send_sms_notification(approver.contact, f"Tour booking has been cancelled by visitor. {reason or ''}")
        
        return JSONResponse(content={
            "bookingId": booking.booking_id,
            "status": "cancelled",
            "message": "Booking cancelled successfully"
        })


# Assign Property to Realtor
@app.post("/api/properties/{property_id}/assign")
async def assign_property(
    property_id: int,
    to_user_id: Optional[int] = Body(None),  # Realtor ID, or None to unassign
    to_user_type: str = Body(default="realtor"),  # 'realtor' | 'property_manager'
    reason: Optional[str] = Body(None),
    user_data: dict = Depends(get_current_user_data)
):
    """PM can assign/unassign property to realtor."""
    if user_data["user_type"] != "property_manager":
        raise HTTPException(status_code=403, detail="Only Property Managers can assign properties")
    
    pm_id = user_data["id"]
    
    with Session(engine) as session:
        property_listing = session.get(ApartmentListing, property_id)
        if not property_listing:
            raise HTTPException(status_code=404, detail="Property not found")
        
        source = session.get(Source, property_listing.source_id)
        if not source or source.property_manager_id != pm_id:
            raise HTTPException(status_code=403, detail="You don't own this property")
        
        from_user_id = source.realtor_id
        from_user_type = "realtor" if from_user_id else None
        
        # If assigning to realtor, verify realtor is managed by this PM
        if to_user_id and to_user_type == "realtor":
            realtor = session.get(Realtor, to_user_id)
            if not realtor or realtor.property_manager_id != pm_id:
                raise HTTPException(status_code=403, detail="Realtor not found or not managed by you")
            
            # Get or create realtor's source
            realtor_source = session.exec(
                select(Source).where(Source.realtor_id == to_user_id)
            ).first()
            
            if not realtor_source:
                # Create source for realtor
                realtor_source = Source(
                    property_manager_id=pm_id,
                    realtor_id=to_user_id
                )
                session.add(realtor_source)
                session.commit()
                session.refresh(realtor_source)
            
            # Update property's source
            property_listing.source_id = realtor_source.source_id
        else:
            # Unassign - move back to PM's source
            pm_source = session.exec(
                select(Source).where(
                    Source.property_manager_id == pm_id,
                    Source.realtor_id.is_(None)
                )
            ).first()
            
            if not pm_source:
                # Create PM source
                pm_source = Source(property_manager_id=pm_id, realtor_id=None)
                session.add(pm_source)
                session.commit()
                session.refresh(pm_source)
            
            property_listing.source_id = pm_source.source_id
            to_user_id = None
            to_user_type = None
        
        session.add(property_listing)
        
        # Create assignment audit record
        assignment = PropertyAssignment(
            property_id=property_id,
            from_user_id=from_user_id,
            from_user_type=from_user_type,
            to_user_id=to_user_id,
            to_user_type=to_user_type,
            reason=reason,
            changed_by_user_id=pm_id,
            changed_by_user_type="property_manager"
        )
        session.add(assignment)
        session.commit()
        
        # Notify new assignee
        if to_user_id:
            realtor = session.get(Realtor, to_user_id)
            if realtor:
                notification_msg = f"You have been assigned a new property. {reason or ''}"
                _send_sms_notification(realtor.contact, notification_msg)
        
        return JSONResponse(content={
            "message": "Property assigned successfully",
            "propertyId": property_id,
            "assignedTo": {
                "userId": to_user_id,
                "userType": to_user_type
            } if to_user_id else None
        })


# User Lookup (for VAPI)
@app.get("/api/users/lookup")
async def lookup_user(
    phone: str,
    user_data: Optional[dict] = Depends(get_current_user_data)
):
    """Lookup user (visitor or staff) by phone number."""
    with Session(engine) as session:
        # Normalize phone number
        normalized_phone = phone.replace("+", "").replace("-", "").replace(" ", "")
        
        # Search in PropertyManager
        pms = session.exec(
            select(PropertyManager).where(PropertyManager.contact.like(f"%{normalized_phone}%"))
        ).all()
        
        # Search in Realtor
        realtors = session.exec(
            select(Realtor).where(Realtor.contact.like(f"%{normalized_phone}%"))
        ).all()
        
        results = []
        for pm in pms:
            results.append({
                "userId": pm.property_manager_id,
                "userType": "property_manager",
                "name": pm.name,
                "phone": pm.contact,
                "email": pm.email
            })
        
        for realtor in realtors:
            results.append({
                "userId": realtor.realtor_id,
                "userType": "realtor",
                "name": realtor.name,
                "phone": realtor.contact,
                "email": realtor.email
            })
        
        return JSONResponse(content={"users": results})


# ============================================================================
# VAPI-SPECIFIC ENDPOINTS FOR BOOKING SYSTEM
# ============================================================================
# These endpoints are designed for VAPI to call with minimal context
# VAPI will have: property_id, visitor phone, and can identify PM/Realtor from call

# Get Availability for Property's Assigned User (VAPI) - POST only, no property_id needed
# Also support check-availability endpoint name for VAPI compatibility
@app.post("/vapi/properties/check-availability")
async def check_property_availability_vapi(
    http_request: Request  # FastAPI will inject this - must be first
):
    """
    VAPI endpoint to check property availability.
    Accepts BOTH formats:
    1. VapiRequest format with toolCalls (from VAPI)
    2. Regular JSON body with direct parameters (from other clients)
    """
    # Parse the request body manually
    property_name = None
    from_date = None
    to_date = None
    body = None
    tool_call_id = None
    
    try:
        body = await http_request.json()
        
        # Check if body has message.toolCalls structure (VAPI format)
        if body.get("message") and body["message"].get("toolCalls"):
            tool_calls = body["message"]["toolCalls"]
            for tool_call in tool_calls:
                func = tool_call.get("function", {})
                func_name = func.get("name", "")
                
                if func_name in ["checkPropertyAvailability", "getAvailability", "checkAvailability", "getPropertyAvailability"]:
                    # Extract toolCallId
                    tool_call_id = tool_call.get("id")
                    args = func.get("arguments", {})
                    
                    # Handle both string and object formats
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except:
                            args = {}
                    elif not isinstance(args, dict):
                        args = {}
                    
                    property_name = args.get("property_name") or args.get("propertyName")
                    from_date = args.get("from_date") or args.get("fromDate")
                    to_date = args.get("to_date") or args.get("toDate")
                    break
        
        # If not found in toolCalls, try direct body parameters
        if not property_name:
            property_name = body.get("property_name") or body.get("propertyName")
            from_date = body.get("from_date") or body.get("fromDate")
            to_date = body.get("to_date") or body.get("toDate")
            
    except Exception as e:
        print(f"⚠️  Error parsing request body: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid request format. Error: {str(e)}"
        )
    
    if not property_name:
        raise HTTPException(
            status_code=400,
            detail="property_name is required. Please provide the property name or address."
        )
    
    # Call the shared handler function with extracted parameters and parsed body
    result = await _handle_property_availability(http_request, property_name, from_date, to_date, body)
    
    # If we have a toolCallId and result is JSONResponse, convert to VAPI format
    if tool_call_id and isinstance(result, JSONResponse):
        result_data = json.loads(result.body.decode())
        return {"results": [{"toolCallId": tool_call_id, "result": result_data}]}
    
    return result


@app.post("/vapi/properties/availability")
async def get_property_availability_vapi(
    http_request: Request,  # FastAPI will inject this - must be first
    request: Optional[VapiRequest] = None,
    property_name: Optional[str] = Body(None),
    from_date: Optional[str] = Body(None),
    to_date: Optional[str] = Body(None)
):
    """
    Get availability for the user assigned to a property.
    
    Accepts BOTH formats:
    1. VapiRequest format with toolCalls (from VAPI)
    2. Regular JSON body with direct parameters (from other clients)
    
    VAPI calls this after finding a property to check available slots.
    No property_id needed - only property_name (user-provided).
    If from_date/to_date not provided, defaults to next 2 weeks.
    """
    # Extract parameters from VapiRequest if provided
    if request and hasattr(request, 'message') and hasattr(request.message, 'toolCalls'):
        for tool_call in request.message.toolCalls:
            if tool_call.function.name in ["getAvailability", "checkAvailability", "getPropertyAvailability", "checkPropertyAvailability"]:
                args = tool_call.function.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except:
                        args = {}
                
                property_name = property_name or args.get("property_name") or args.get("propertyName")
                from_date = from_date or args.get("from_date") or args.get("fromDate")
                to_date = to_date or args.get("to_date") or args.get("toDate")
                break
    
    # If still no property_name, try to get from request body directly
    body = None
    if not property_name:
        try:
            body = await http_request.json()
            property_name = property_name or body.get("property_name") or body.get("propertyName")
            from_date = from_date or body.get("from_date") or body.get("fromDate")
            to_date = to_date or body.get("to_date") or body.get("toDate")
        except:
            pass  # Body might not be JSON or already consumed
    
    # Call shared handler function
    return await _handle_property_availability(http_request, property_name, from_date, to_date, body)


# Shared handler function for property availability logic
async def _handle_property_availability(
    http_request: Request,
    property_name: Optional[str],
    from_date: Optional[str],
    to_date: Optional[str],
    body: Optional[dict] = None
):
    """
    Shared logic for handling property availability requests.
    """
    # Validate property_name
    if not property_name or not property_name.strip():
        raise HTTPException(
            status_code=400,
            detail="property_name is required. Please provide the property name or address."
        )
    
    # Default date range to next 2 weeks if not provided
    now = datetime.utcnow().replace(tzinfo=timezone.utc)
    if not from_date:
        from_date = now.isoformat()
    if not to_date:
        to_date = (now + timedelta(days=14)).isoformat()
    
    # Robust datetime parsing
    try:
        from_dt = _parse_datetime_robust(from_date, "from_date")
        to_dt = _parse_datetime_robust(to_date, "to_date")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error parsing dates: {str(e)}. Please use ISO format (e.g., 2025-12-01T00:00:00Z)"
        )
    
    # Validate date range
    if to_dt <= from_dt:
        raise HTTPException(
            status_code=400,
            detail="to_date must be after from_date. Please provide a valid date range."
        )
    
    # Validate range is not too large (max 30 days)
    days_diff = (to_dt - from_dt).days
    if days_diff > 30:
        raise HTTPException(
            status_code=400,
            detail=f"Date range is too large ({days_diff} days). Maximum allowed range is 30 days. Please use a smaller date range."
        )
    
    with Session(engine) as session:
        # Get source_ids for property search
        source_ids = None
        if http_request:
            try:
                from DB.vapi_helpers import identify_user_from_vapi_request
                # Use provided body if available, otherwise try to get from request
                request_body = body
                if request_body is None:
                    try:
                        request_body = await http_request.json() if hasattr(http_request, 'json') else {}
                    except:
                        request_body = {}
                headers = dict(http_request.headers) if http_request else {}
                user_info = identify_user_from_vapi_request(request_body, headers)
                source_ids = user_info.get("source_ids") if user_info else None
            except:
                pass
        
        # Robust property finding - only use property_name (no property_id)
        property_listing, found_property_id, error_msg = _find_property_robust(
            session, None, property_name, source_ids  # No property_id, only property_name
        )
        
        if not property_listing:
            raise HTTPException(status_code=404, detail=error_msg or "Property not found.")
        
        property_id = found_property_id  # Use found property_id
        
        # Get assigned user
        assigned_user = _get_property_assigned_user(session, property_id)
        if not assigned_user:
            raise HTTPException(
                status_code=400,
                detail="Property has no assigned PM or Realtor. Please assign a user to the property first."
            )
        
        # Get availability
        prefs = _get_user_calendar_preferences(session, assigned_user["user_id"], assigned_user["user_type"])
        available_slots = _compute_available_slots(
            session,
            assigned_user["user_id"],
            assigned_user["user_type"],
            from_dt,
            to_dt
        )
        
        return JSONResponse(content={
            "propertyId": property_id,
            "assignedUser": {
                "userId": assigned_user["user_id"],
                "userType": assigned_user["user_type"],
                "name": assigned_user["name"]
            },
            "timezone": prefs["timezone"],
            "availableSlots": available_slots
        })


# ============================================================================
# ROBUST HELPER FUNCTIONS FOR VAPI ENDPOINTS
# ============================================================================

def _parse_datetime_robust(date_str: str, field_name: str = "date") -> datetime:
    """
    Robust datetime parsing that handles multiple formats and provides helpful errors.
    """
    if not date_str or not isinstance(date_str, str):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field_name}: must be a string in ISO format (e.g., 2025-12-01T16:00:00Z or 2025-12-01T16:00:00+00:00)"
        )
    
    date_str = date_str.strip()
    
    # Try multiple formats
    formats = [
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M",
    ]
    
    # First try replacing Z with +00:00
    if date_str.endswith("Z"):
        date_str_utc = date_str.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(date_str_utc)
            # Ensure timezone-aware (should already be, but double-check)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            pass
    
    # Try ISO format directly
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        # If no timezone info, assume UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        pass
    
    # Try other formats
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            # If no timezone info, assume UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    
    # If all formats fail, provide helpful error
    raise HTTPException(
        status_code=400,
        detail=f"Invalid {field_name} format: '{date_str}'. Please use ISO format like '2025-12-01T16:00:00Z' or '2025-12-01T16:00:00+00:00'"
    )


def _normalize_phone_robust(phone: str, field_name: str = "phone") -> str:
    """
    Robust phone number normalization with helpful errors.
    """
    if not phone:
        raise HTTPException(
            status_code=400,
            detail=f"Missing {field_name} number. Please provide a valid phone number."
        )
    
    if not isinstance(phone, str):
        phone = str(phone)
    
    # Use existing normalization function
    from DB.user_lookup import normalize_phone_number
    normalized = normalize_phone_number(phone)
    
    # Validate normalized result
    if not normalized or len(normalized) < 10:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field_name} number: '{phone}'. Please provide a valid phone number (e.g., +14125551234 or (412) 555-1234)"
        )
    
    return normalized


def _find_property_robust(session: Session, property_id: Optional[int] = None, 
                          property_name: Optional[str] = None, 
                          source_ids: Optional[List[int]] = None) -> tuple[Optional[ApartmentListing], Optional[int], Optional[str]]:
    """
    Robust property finding that tries multiple methods and provides helpful errors.
    Returns: (property_listing, property_id, error_message)
    """
    property_listing = None
    found_property_id = property_id
    error_msg = None
    
    # Method 1: Try property_id if provided
    if property_id:
        property_listing = session.get(ApartmentListing, property_id)
        if property_listing:
            return property_listing, property_id, None
        else:
            error_msg = f"Property with ID {property_id} not found."
    
    # Method 2: Try property_name search
    if property_name and not property_listing:
        from vapi.rag import RAGEngine
        rag = RAGEngine()
        
        try:
            # Try exact search first
            search_results = rag.search_apartments(property_name, source_ids=source_ids, k=3)
            
            if search_results and len(search_results) > 0:
                # Try to find exact match first
                for result in search_results:
                    result_address = result.get("address", "").lower()
                    search_name = property_name.lower()
                    
                    # Check if addresses match closely
                    if search_name in result_address or result_address in search_name:
                        found_property_id = result.get("id") or result.get("property_id")
                        if found_property_id:
                            property_listing = session.get(ApartmentListing, found_property_id)
                            if property_listing:
                                return property_listing, found_property_id, None
                
                # If no exact match, use first result
                found_property_id = search_results[0].get("id") or search_results[0].get("property_id")
                if found_property_id:
                    property_listing = session.get(ApartmentListing, found_property_id)
                    if property_listing:
                        # Provide suggestion if address doesn't match exactly
                        result_address = search_results[0].get("address", "")
                        if property_name.lower() not in result_address.lower():
                            error_msg = f"Found property '{result_address}' (ID: {found_property_id}) for search '{property_name}'. Is this the correct property?"
                        return property_listing, found_property_id, error_msg
        except Exception as e:
            print(f"⚠️  Error searching for property '{property_name}': {e}")
            error_msg = f"Error searching for property '{property_name}': {str(e)}"
    
    # If still not found, provide helpful error
    if not property_listing:
        if property_id and property_name:
            error_msg = f"Property not found. ID {property_id} doesn't exist, and search for '{property_name}' returned no results."
        elif property_id:
            error_msg = f"Property with ID {property_id} not found. Please check the property ID."
        elif property_name:
            error_msg = f"No property found matching '{property_name}'. Please check the property name or address."
        else:
            error_msg = "Either property_id or property_name must be provided."
    
    return property_listing, found_property_id, error_msg


# Validate Tour Request and Get Alternatives
@app.post("/vapi/properties/validate-tour-request")
async def validate_tour_request(
    http_request: Request,  # FastAPI will inject this - must be first
    request: Optional[VapiRequest] = None,
    property_name: Optional[str] = Body(None),
    requested_start_at: Optional[str] = Body(None),
    requested_end_at: Optional[str] = Body(None)
):
    """
    Validate a tour request for a specific time slot.
    
    Accepts BOTH formats:
    1. VapiRequest format with toolCalls (from VAPI)
    2. Regular JSON body with direct parameters (from other clients)
    
    VAPI sends: property_name (required) + requested time
    Backend checks if that time is available for the property's assigned PM/Realtor.
    
    Returns:
    - If available: {isAvailable: true, canBook: true, requestedSlot: {...}}
    - If not available: {isAvailable: false, canBook: false, suggestedSlots: [2-3 alternatives]}
    
    The PM/Realtor is identified from the call's destination number (via headers).
    Only suggests slots within 2 weeks from now.
    
    No property_id needed - only property_name (user-provided).
    """
    from DB.vapi_helpers import identify_user_from_vapi_request
    
    # Parse request body once (can only be read once)
    request_body = {}
    tool_call_id = None
    
    # First, try to parse the raw JSON body to extract toolCallId and parameters
    try:
        request_body = await http_request.json()
        # Check if body has message.toolCalls structure (VAPI format)
        if request_body.get("message") and request_body["message"].get("toolCalls"):
            tool_calls = request_body["message"]["toolCalls"]
            for tool_call in tool_calls:
                func = tool_call.get("function", {})
                func_name = func.get("name", "")
                
                if func_name in ["validateTourRequest", "checkTourAvailability", "validateTour", "validateTourBooking"]:
                    tool_call_id = tool_call.get("id")
                    args = func.get("arguments", {})
                    
                    # Handle both string and object formats
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except:
                            args = {}
                    elif not isinstance(args, dict):
                        args = {}
                    
                    property_name = property_name or args.get("property_name") or args.get("propertyName")
                    requested_start_at = requested_start_at or args.get("requested_start_at") or args.get("requestedStartAt")
                    requested_end_at = requested_end_at or args.get("requested_end_at") or args.get("requestedEndAt")
                    break
    except Exception as e:
        print(f"⚠️  Error parsing request body: {e}")
        # Continue - will try VapiRequest object next
    
    # Extract parameters from VapiRequest toolCalls if provided (fallback)
    if request and hasattr(request, 'message') and hasattr(request.message, 'toolCalls') and request.message.toolCalls:
        for tool_call in request.message.toolCalls:
            if tool_call.function.name in ["validateTourRequest", "checkTourAvailability", "validateTour", "validateTourBooking"]:
                if not tool_call_id:
                    tool_call_id = tool_call.id
                args = tool_call.function.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except:
                        args = {}
                
                property_name = property_name or args.get("property_name") or args.get("propertyName")
                requested_start_at = requested_start_at or args.get("requested_start_at") or args.get("requestedStartAt")
                requested_end_at = requested_end_at or args.get("requested_end_at") or args.get("requestedEndAt")
                break
    
    # If still missing, try to get from request body directly (already parsed above)
    if not property_name or not requested_start_at or not requested_end_at:
        if request_body:
            # Try direct body parameters as fallback
            property_name = property_name or request_body.get("property_name") or request_body.get("propertyName")
            requested_start_at = requested_start_at or request_body.get("requested_start_at") or request_body.get("requestedStartAt")
            requested_end_at = requested_end_at or request_body.get("requested_end_at") or request_body.get("requestedEndAt")
    
    # Validate property_name is provided
    if not property_name or not property_name.strip():
        raise HTTPException(
            status_code=400,
            detail="property_name is required. Please provide the property name or address."
        )
    
    # Validate required datetime fields
    if not requested_start_at or not requested_start_at.strip():
        raise HTTPException(
            status_code=400,
            detail="requested_start_at is required. Please provide the requested start time in ISO format (e.g., 2025-12-01T16:00:00Z)."
        )
    
    if not requested_end_at or not requested_end_at.strip():
        raise HTTPException(
            status_code=400,
            detail="requested_end_at is required. Please provide the requested end time in ISO format (e.g., 2025-12-01T16:30:00Z)."
        )
    
    # Robust datetime parsing
    try:
        requested_start = _parse_datetime_robust(requested_start_at, "requested_start_at")
        requested_end = _parse_datetime_robust(requested_end_at, "requested_end_at")
    except HTTPException:
        raise  # Re-raise HTTPException as-is
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error parsing dates: {str(e)}. Please use ISO format (e.g., 2025-12-01T16:00:00Z)"
        )
    
    # Validate time range (must be within 2 weeks)
    now = datetime.utcnow().replace(tzinfo=timezone.utc)
    two_weeks_from_now = now + timedelta(days=14)
    
    if requested_start < now:
        hours_ago = (now - requested_start).total_seconds() / 3600
        raise HTTPException(
            status_code=400,
            detail=f"Requested time cannot be in the past. The requested time was {hours_ago:.1f} hours ago. Please select a future time."
        )
    
    if requested_start > two_weeks_from_now:
        days_ahead = (requested_start - now).days
        raise HTTPException(
            status_code=400,
            detail=f"Tour requests must be within 2 weeks from now. The requested time is {days_ahead} days away. Please select a time within the next 14 days."
        )
    
    if requested_end <= requested_start:
        duration = (requested_end - requested_start).total_seconds() / 60
        raise HTTPException(
            status_code=400,
            detail=f"End time must be after start time. The duration is {duration:.0f} minutes. Please ensure end time is after start time."
        )
    
    # Validate duration (reasonable tour duration: 15 minutes to 2 hours)
    duration_minutes = (requested_end - requested_start).total_seconds() / 60
    if duration_minutes < 15:
        raise HTTPException(
            status_code=400,
            detail=f"Tour duration is too short ({duration_minutes:.0f} minutes). Minimum duration is 15 minutes."
        )
    if duration_minutes > 120:
        raise HTTPException(
            status_code=400,
            detail=f"Tour duration is too long ({duration_minutes:.0f} minutes). Maximum duration is 2 hours."
        )
    
    with Session(engine) as session:
        # Try to identify user for data isolation
        source_ids = None
        if http_request:
            try:
                # Use already parsed request_body if available
                body = request_body if request_body else {}
                headers = dict(http_request.headers) if http_request else {}
                user_info = identify_user_from_vapi_request(body, headers)
                source_ids = user_info.get("source_ids") if user_info else None
            except Exception as e:
                print(f"⚠️  Error identifying user: {e}")
                pass
        
        # Robust property finding - only use property_name (no property_id)
        property_listing, found_property_id, error_msg = _find_property_robust(
            session, None, property_name, source_ids  # No property_id, only property_name
        )
        
        if not property_listing:
            raise HTTPException(status_code=404, detail=error_msg or "Property not found.")
        
        property_id = found_property_id  # Use found property_id
        
        # Check property status
        meta = property_listing.listing_metadata or {}
        listing_status = meta.get("listing_status", "unknown")
        
        if listing_status != "available":
            result_data = {
                "isAvailable": False,
                "canBook": False,
                "reason": f"Property is {listing_status} and not available for tours",
                "suggestedSlots": []
            }
            if tool_call_id:
                return {"results": [{"toolCallId": tool_call_id, "result": result_data}]}
            else:
                return JSONResponse(content=result_data)
        
        # Get assigned user (realtor if assigned, else PM)
        assigned_user = _get_property_assigned_user(session, property_id)
        if not assigned_user:
            result_data = {
                "isAvailable": False,
                "canBook": False,
                "reason": "Property has no assigned PM or Realtor",
                "suggestedSlots": []
            }
            if tool_call_id:
                return {"results": [{"toolCallId": tool_call_id, "result": result_data}]}
            else:
                return JSONResponse(content=result_data)
        
        # Verify the call is for the correct PM/Realtor (optional validation)
        # This ensures the booking is for the right person
        if http_request:
            try:
                # Use already parsed request_body if available, otherwise try to get from request
                body = request_body if request_body else {}
                headers = dict(http_request.headers)
                user_info = identify_user_from_vapi_request(body, headers)
                
                if user_info:
                    # Verify the assigned user matches the call's destination
                    call_user_id = user_info.get("user_id")
                    call_user_type = user_info.get("user_type")
                    
                    if (call_user_id != assigned_user["user_id"] or 
                        call_user_type != assigned_user["user_type"]):
                        # This is a warning but not a blocker - the property might be assigned to someone else
                        print(f"⚠️  Warning: Call is for {call_user_type} {call_user_id}, but property is assigned to {assigned_user['user_type']} {assigned_user['user_id']}")
            except Exception as e:
                print(f"⚠️  Could not verify call user: {e}")
        
        # Get user's calendar preferences
        prefs = _get_user_calendar_preferences(session, assigned_user["user_id"], assigned_user["user_type"])
        
        # Check if requested time slot is available
        # Get all available slots for the next 2 weeks
        from_date = now
        to_date = two_weeks_from_now
        available_slots = _compute_available_slots(
            session,
            assigned_user["user_id"],
            assigned_user["user_type"],
            from_date,
            to_date
        )
        
        # Check if requested slot overlaps with any available slot
        requested_slot_available = False
        for slot in available_slots:
            slot_start_str = slot["startAt"].replace("Z", "+00:00")
            slot_end_str = slot["endAt"].replace("Z", "+00:00")
            slot_start = datetime.fromisoformat(slot_start_str)
            slot_end = datetime.fromisoformat(slot_end_str)
            
            # Ensure timezone-aware (default to UTC if naive)
            if slot_start.tzinfo is None:
                slot_start = slot_start.replace(tzinfo=timezone.utc)
            if slot_end.tzinfo is None:
                slot_end = slot_end.replace(tzinfo=timezone.utc)
            
            # Check if requested time fits within this available slot
            if slot_start <= requested_start and requested_end <= slot_end:
                requested_slot_available = True
                break
        
        # Prepare result data
        if requested_slot_available:
            # Requested time is available - can book
            result_data = {
                "isAvailable": True,
                "canBook": True,
                "propertyId": property_id,
                "propertyName": meta.get("address", property_name or "Unknown"),
                "requestedSlot": {
                    "startAt": requested_start_at,
                    "endAt": requested_end_at
                },
                "assignedUser": {
                    "userId": assigned_user["user_id"],
                    "userType": assigned_user["user_type"],
                    "name": assigned_user["name"]
                },
                "timezone": prefs["timezone"],
                "message": "Requested time slot is available"
            }
        else:
            # Requested time is not available - suggest alternatives
            # Get 2-3 next available slots (prefer slots close to requested time)
            
            # Sort slots by how close they are to requested time
            def slot_distance(slot):
                slot_start_str = slot["startAt"].replace("Z", "+00:00")
                slot_start = datetime.fromisoformat(slot_start_str)
                # Ensure timezone-aware (default to UTC if naive)
                if slot_start.tzinfo is None:
                    slot_start = slot_start.replace(tzinfo=timezone.utc)
                return abs((slot_start - requested_start).total_seconds())
            
            sorted_slots = sorted(available_slots, key=slot_distance)
            
            # Take up to 3 suggestions
            suggested_slots = sorted_slots[:3]
            
            result_data = {
                "isAvailable": False,
                "canBook": False,
                "propertyId": property_id,
                "propertyName": meta.get("address", property_name or "Unknown"),
                "reason": "Requested time slot is not available",
                "requestedSlot": {
                    "startAt": requested_start_at,
                    "endAt": requested_end_at
                },
                "suggestedSlots": suggested_slots,
                "assignedUser": {
                    "userId": assigned_user["user_id"],
                    "userType": assigned_user["user_type"],
                    "name": assigned_user["name"]
                },
                "timezone": prefs["timezone"],
                "message": f"Requested time is not available. Here are {len(suggested_slots)} alternative options."
            }
        
        # Return in VAPI format if toolCallId is present, otherwise return direct JSON
        if tool_call_id:
            return {"results": [{"toolCallId": tool_call_id, "result": result_data}]}
        else:
            return JSONResponse(content=result_data)


# Get Bookings by Visitor (VAPI) - POST only, no property_id needed
@app.post("/vapi/bookings/by-visitor")
async def get_bookings_by_visitor_vapi(
    http_request: Request,  # FastAPI will inject this - must be first
    request: Optional[VapiRequest] = None,
    visitor_phone: Optional[str] = Body(None),
    visitor_name: Optional[str] = Body(None),
    status: Optional[str] = Body(None)
):
    """
    Get bookings for a visitor by their phone number or name.
    
    Accepts BOTH formats:
    1. VapiRequest format with toolCalls (from VAPI)
    2. Regular JSON body with direct parameters (from other clients)
    
    VAPI calls this to check booking status or get booking details.
    No property_id needed - only user-provided info (name, phone).
    """
    # Parse request body once
    request_body = {}
    tool_call_id = None
    
    # Extract parameters from VapiRequest toolCalls if provided
    if request and hasattr(request, 'message') and hasattr(request.message, 'toolCalls') and request.message.toolCalls:
        for tool_call in request.message.toolCalls:
            if tool_call.function.name in ["getBookingStatus", "checkBooking", "getBookings", "getBookingsByVisitor"]:
                tool_call_id = tool_call.id
                args = tool_call.function.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except:
                        args = {}
                
                visitor_phone = visitor_phone or args.get("visitor_phone") or args.get("visitorPhone")
                visitor_name = visitor_name or args.get("visitor_name") or args.get("visitorName")
                status = status or args.get("status")
                break
    
    # If still missing, try to get from request body directly
    if not visitor_phone and not visitor_name:
        try:
            request_body = await http_request.json()
            # Extract toolCallId from body if present
            if not tool_call_id and request_body.get("message") and request_body["message"].get("toolCalls"):
                tool_calls = request_body["message"]["toolCalls"]
                if tool_calls and len(tool_calls) > 0:
                    tool_call_id = tool_calls[0].get("id")
            
            visitor_phone = visitor_phone or request_body.get("visitor_phone") or request_body.get("visitorPhone")
            visitor_name = visitor_name or request_body.get("visitor_name") or request_body.get("visitorName")
            status = status or request_body.get("status")
        except:
            pass  # Body might not be JSON or already consumed
    
    if not visitor_phone and not visitor_name:
        raise HTTPException(
            status_code=400,
            detail="Either visitor_phone or visitor_name must be provided."
        )
    
    with Session(engine) as session:
        bookings = []
        
        # Method 1: Search by phone number (preferred)
        if visitor_phone:
            try:
                normalized_phone = _normalize_phone_robust(visitor_phone, "visitor_phone")
                
                # Try exact match first
                query = select(PropertyTourBooking).where(
                    PropertyTourBooking.visitor_phone == normalized_phone,
                    PropertyTourBooking.deleted_at.is_(None)  # Not deleted
                )
                
                if status:
                    query = query.where(PropertyTourBooking.status == status)
                
                bookings = session.exec(query.order_by(PropertyTourBooking.start_at.desc())).all()
                
                # If no exact match, try partial match (last 10 digits)
                if not bookings and len(normalized_phone) >= 10:
                    last_10 = normalized_phone[-10:]
                    query = select(PropertyTourBooking).where(
                        PropertyTourBooking.visitor_phone.like(f"%{last_10}%"),
                        PropertyTourBooking.deleted_at.is_(None)
                    )
                    if status:
                        query = query.where(PropertyTourBooking.status == status)
                    bookings = session.exec(query.order_by(PropertyTourBooking.start_at.desc())).all()
                
            except HTTPException:
                raise
            except Exception as e:
                print(f"⚠️  Error searching bookings by phone '{visitor_phone}': {e}")
        
        # Method 2: Search by name (fallback or if name provided)
        if not bookings and visitor_name:
            visitor_name_clean = visitor_name.strip().lower()
            
            query = select(PropertyTourBooking).where(
                PropertyTourBooking.visitor_name.ilike(f"%{visitor_name_clean}%"),
                PropertyTourBooking.deleted_at.is_(None)
            )
            
            if status:
                query = query.where(PropertyTourBooking.status == status)
            
            bookings = session.exec(query.order_by(PropertyTourBooking.start_at.desc())).all()
        
        # Prepare response with helpful information
        response_data = {
            "visitorPhone": visitor_phone,
            "visitorName": visitor_name,
            "bookings": [{
                "bookingId": b.booking_id,
                "propertyId": b.property_id,
                "visitor": {
                    "name": b.visitor_name,
                    "phone": b.visitor_phone,
                    "email": b.visitor_email
                },
                "startAt": b.start_at.isoformat(),
                "endAt": b.end_at.isoformat(),
                "timezone": b.timezone,
                "status": b.status,
                "createdBy": b.created_by,
                "notes": b.notes,
                "proposedSlots": b.proposed_slots,
                "requestedAt": b.requested_at.isoformat(),
                "createdAt": b.created_at.isoformat(),
                "updatedAt": b.updated_at.isoformat(),
                "deletedAt": b.deleted_at.isoformat() if b.deleted_at else None,
                "deletionReason": b.deletion_reason
            } for b in bookings]
        }
        
        # Add helpful message if no bookings found
        if not bookings:
            search_terms = []
            if visitor_phone:
                search_terms.append(f"phone '{visitor_phone}'")
            if visitor_name:
                search_terms.append(f"name '{visitor_name}'")
            
            response_data["message"] = f"No bookings found for {', '.join(search_terms)}."
            response_data["suggestions"] = [
                "Check if the phone number or name is correct",
                "Try searching with a different format (e.g., +1XXXXXXXXXX or (XXX) XXX-XXXX)",
                "The booking might be under a different name or phone number"
            ]
        else:
            response_data["message"] = f"Found {len(bookings)} booking(s)"
        
        # Return in VAPI format if toolCallId is present, otherwise return direct JSON
        if tool_call_id:
            return {"results": [{"toolCallId": tool_call_id, "result": response_data}]}
        else:
            return JSONResponse(content=response_data)


# Cancel/Delete Booking by Visitor (VAPI) - Handles both bookings and pending requests
@app.post("/vapi/bookings/cancel")
async def cancel_booking_vapi(
    http_request: Request,  # FastAPI will inject this - must be first
    request: Optional[VapiRequest] = None,
    property_name: Optional[str] = Body(None),
    visitor_phone: Optional[str] = Body(None),
    visitor_name: Optional[str] = Body(None),
    reason: Optional[str] = Body(None)
):
    """
    Cancel or delete a booking/tour request by visitor information.
    
    Accepts BOTH formats:
    1. VapiRequest format with toolCalls (from VAPI)
    2. Regular JSON body with direct parameters (from other clients)
    
    Flow:
    1. First checks for existing bookings (pending/approved) by visitor name and phone
    2. If found, cancels them (soft delete with deleted_at)
    3. If not found, checks for pending requests and deletes them permanently (soft delete)
    4. Stores all cancellations in DB with reason so PM/realtor can see what was cancelled
    
    VAPI should call this when user wants to cancel a tour booking.
    No property_id needed - only user-provided info (name, phone, property_name).
    """
    # Parse request body once
    request_body = {}
    tool_call_id = None
    
    # Extract parameters from VapiRequest toolCalls if provided
    if request and hasattr(request, 'message') and hasattr(request.message, 'toolCalls') and request.message.toolCalls:
        for tool_call in request.message.toolCalls:
            if tool_call.function.name in ["cancelBooking", "cancelTour", "deleteTourRequest", "cancelBookingRequest"]:
                tool_call_id = tool_call.id
                args = tool_call.function.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except:
                        args = {}
                
                property_name = property_name or args.get("property_name") or args.get("propertyName")
                visitor_phone = visitor_phone or args.get("visitor_phone") or args.get("visitorPhone")
                visitor_name = visitor_name or args.get("visitor_name") or args.get("visitorName")
                reason = reason or args.get("reason")
                break
    
    # If still missing, try to get from request body directly
    if not visitor_phone and not visitor_name:
        try:
            request_body = await http_request.json()
            # Extract toolCallId from body if present
            if not tool_call_id and request_body.get("message") and request_body["message"].get("toolCalls"):
                tool_calls = request_body["message"]["toolCalls"]
                if tool_calls and len(tool_calls) > 0:
                    tool_call_id = tool_calls[0].get("id")
            
            property_name = property_name or request_body.get("property_name") or request_body.get("propertyName")
            visitor_phone = visitor_phone or request_body.get("visitor_phone") or request_body.get("visitorPhone")
            visitor_name = visitor_name or request_body.get("visitor_name") or request_body.get("visitorName")
            reason = reason or request_body.get("reason")
        except:
            pass  # Body might not be JSON or already consumed
    
    if not visitor_phone and not visitor_name:
        raise HTTPException(
            status_code=400,
            detail="Either visitor_phone or visitor_name must be provided."
        )
    
    with Session(engine) as session:
        # Normalize phone if provided
        normalized_phone = None
        if visitor_phone:
            try:
                normalized_phone = _normalize_phone_robust(visitor_phone, "visitor_phone")
            except HTTPException:
                raise
            except Exception:
                normalized_phone = visitor_phone.replace("+", "").replace("-", "").replace(" ", "").strip()
        
        # Step 1: Check for existing bookings (pending or approved) by name and phone
        bookings_query = select(PropertyTourBooking).where(
            PropertyTourBooking.deleted_at.is_(None)  # Not already deleted
        )
        
        if normalized_phone:
            bookings_query = bookings_query.where(
                or_(
                    PropertyTourBooking.visitor_phone == normalized_phone,
                    PropertyTourBooking.visitor_phone.like(f"%{normalized_phone[-10:]}%")
                )
            )
        
        if visitor_name:
            visitor_name_clean = visitor_name.strip().lower()
            bookings_query = bookings_query.where(
                PropertyTourBooking.visitor_name.ilike(f"%{visitor_name_clean}%")
            )
        
        # Filter by property if provided
        if property_name:
            # Find property first
            property_listing, found_property_id, _ = _find_property_robust(session, None, property_name, None)
            if found_property_id:
                bookings_query = bookings_query.where(PropertyTourBooking.property_id == found_property_id)
        
        # Get pending or approved bookings
        bookings_query = bookings_query.where(
            PropertyTourBooking.status.in_(["pending", "approved"])
        ).order_by(PropertyTourBooking.start_at.desc())
        
        bookings = session.exec(bookings_query).all()
        
        cancelled_bookings = []
        deleted_requests = []
        
        if bookings:
            # Step 2: Cancel existing bookings (soft delete)
            for booking in bookings:
                if booking.status in ["cancelled", "denied"]:
                    continue
                
                old_status = booking.status
                booking.status = "cancelled"
                booking.deleted_at = datetime.utcnow()
                booking.deletion_reason = reason or "Cancelled by visitor via VAPI"
                booking.deleted_by = "visitor"
                booking.updated_at = datetime.utcnow()
                _add_audit_log(booking, None, "cancelled_by_visitor", reason or "Cancelled via VAPI")
                
                # If booking was approved, remove the blocking slot
                if old_status == "approved":
                    blocking_slot = session.exec(
                        select(AvailabilitySlot).where(
                            AvailabilitySlot.booking_id == booking.booking_id,
                            AvailabilitySlot.slot_type == "booking"
                        )
                    ).first()
                    if blocking_slot:
                        session.delete(blocking_slot)
                
                session.add(booking)
                cancelled_bookings.append(booking)
        else:
            # Step 3: No bookings found - check for pending requests to delete
            # (This handles the case where user wants to delete a pending request)
            pending_query = select(PropertyTourBooking).where(
                PropertyTourBooking.deleted_at.is_(None),
                PropertyTourBooking.status == "pending"
            )
            
            if normalized_phone:
                pending_query = pending_query.where(
                    or_(
                        PropertyTourBooking.visitor_phone == normalized_phone,
                        PropertyTourBooking.visitor_phone.like(f"%{normalized_phone[-10:]}%")
                    )
                )
            
            if visitor_name:
                visitor_name_clean = visitor_name.strip().lower()
                pending_query = pending_query.where(
                    PropertyTourBooking.visitor_name.ilike(f"%{visitor_name_clean}%")
                )
            
            if property_name:
                property_listing, found_property_id, _ = _find_property_robust(session, None, property_name, None)
                if found_property_id:
                    pending_query = pending_query.where(PropertyTourBooking.property_id == found_property_id)
            
            pending_requests = session.exec(pending_query.order_by(PropertyTourBooking.start_at.desc())).all()
            
            for request_booking in pending_requests:
                # Soft delete the pending request
                request_booking.deleted_at = datetime.utcnow()
                request_booking.deletion_reason = reason or "Deleted by visitor via VAPI"
                request_booking.deleted_by = "visitor"
                request_booking.updated_at = datetime.utcnow()
                _add_audit_log(request_booking, None, "deleted_by_visitor", reason or "Deleted via VAPI")
                
                session.add(request_booking)
                deleted_requests.append(request_booking)
        
        session.commit()
        
        # Notify approver for cancelled bookings
        for booking in cancelled_bookings:
            if booking.assigned_to_user_type == "property_manager":
                approver = session.get(PropertyManager, booking.assigned_to_user_id)
            else:
                approver = session.get(Realtor, booking.assigned_to_user_id)
            
            if approver:
                property_listing = session.get(ApartmentListing, booking.property_id)
                property_address = "the property"
                if property_listing:
                    meta = property_listing.listing_metadata or {}
                    property_address = meta.get("address", "the property")
                
                notification_msg = f"Tour booking cancelled by {booking.visitor_name} ({booking.visitor_phone}) for {property_address} on {booking.start_at.strftime('%Y-%m-%d %H:%M')}. {reason or ''}"
                _send_sms_notification(approver.contact, notification_msg)
        
        # Prepare response
        total_processed = len(cancelled_bookings) + len(deleted_requests)
        
        if total_processed == 0:
            search_info = []
            if visitor_phone:
                search_info.append(f"phone '{visitor_phone}'")
            if visitor_name:
                search_info.append(f"name '{visitor_name}'")
            if property_name:
                search_info.append(f"property '{property_name}'")
            
            raise HTTPException(
                status_code=404,
                detail=f"No pending or approved bookings found for {', '.join(search_info)}. Please check the information and try again."
            )
        
        # Get property addresses for response
        for booking in cancelled_bookings + deleted_requests:
            property_listing = session.get(ApartmentListing, booking.property_id)
            if property_listing:
                meta = property_listing.listing_metadata or {}
                booking.property_address = meta.get("address", "Unknown")
            else:
                booking.property_address = "Unknown"
        
        response_data = {
            "message": f"Successfully processed {total_processed} booking(s)",
            "cancelledBookings": [{
                "bookingId": b.booking_id,
                "status": b.status,
                "propertyId": b.property_id,
                "propertyName": getattr(b, 'property_address', 'Unknown'),
                "action": "cancelled",
                "deletedAt": b.deleted_at.isoformat() if b.deleted_at else None,
                "deletionReason": b.deletion_reason
            } for b in cancelled_bookings],
            "deletedRequests": [{
                "bookingId": b.booking_id,
                "status": b.status,
                "propertyId": b.property_id,
                "propertyName": getattr(b, 'property_address', 'Unknown'),
                "action": "deleted",
                "deletedAt": b.deleted_at.isoformat() if b.deleted_at else None,
                "deletionReason": b.deletion_reason
            } for b in deleted_requests]
        }
        
        # Return in VAPI format if toolCallId is present, otherwise return direct JSON
        if tool_call_id:
            return {"results": [{"toolCallId": tool_call_id, "result": response_data}]}
        else:
            return JSONResponse(content=response_data)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
