"""
Outbound Calling Module - Compliance-First Automated Calling System

This module implements a backend-controlled outbound calling system that:
- Enforces TCPA compliance (consent, opt-out, time windows, DNC)
- Maintains audit trail for legal defense
- Provides eligibility engine for call decisions
- Integrates with Vapi for call execution

Key Principle: Backend decides who to call, Vapi only executes.
"""

from typing import Optional, Dict, Any, List, Set, Union
from datetime import datetime, timedelta
import pytz
import uuid
import json
from sqlmodel import Session, select
from sqlalchemy import or_
from .db import Contact, CallRecord, PropertyTourBooking, PropertyManager, PurchasedPhoneNumber, engine
from .user_lookup import normalize_phone_number
from .vertex_ai_client import get_vertex_ai_client
import os
import re
import requests
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import threading
from queue import Queue

VAPI_BASE_URL = "https://api.vapi.ai"
VAPI_API_KEY = os.getenv("VAPI_API_KEY")
VAPI_ASSISTANT_ID = os.getenv("VAPI_ASSISTANT_ID")

# Twilio credentials for Vapi outbound calls
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
# Default Twilio phone number to use for outbound calls (if from_number not provided)
# Should be in E.164 format, e.g., "+14125551234"
DEFAULT_TWILIO_FROM_NUMBER = os.getenv("DEFAULT_TWILIO_FROM_NUMBER")

# ============================================================================
# COMPLIANCE CONFIGURATION
# ============================================================================

# Allowed calling hours (8 AM - 9 PM in contact's local timezone)
ALLOWED_CALL_START_HOUR = 8
ALLOWED_CALL_END_HOUR = 21

# Maximum outbound call attempts per contact
MAX_CALL_ATTEMPTS = 2

# Minimum cooldown between call attempts (48 hours)
MIN_CALL_COOLDOWN_HOURS = 48

# ============================================================================
# TESTING BYPASS (TEMPORARY - DISABLE BEFORE PRODUCTION!)
# ============================================================================
# Set DISABLE_ELIGIBILITY_CHECKS=true in environment to bypass all eligibility
# checks for testing purposes. This allows calls even when checks fail.
# ⚠️ WARNING: MUST BE DISABLED BEFORE PRODUCTION DEPLOYMENT!
# ============================================================================
DISABLE_ELIGIBILITY_CHECKS = os.getenv("DISABLE_ELIGIBILITY_CHECKS", "false").lower() == "true"

# ============================================================================
# ELIGIBILITY ENGINE (CORE COMPLIANCE LOGIC)
# ============================================================================

def check_eligibility(contact: Contact, session: Session) -> Dict[str, Any]:
    """
    Check if a contact is eligible for an outbound call.
    
    This is the single source of truth for call eligibility.
    ALL checks must pass for a call to be allowed.
    
    Returns:
        {
            "eligible": bool,
            "reason": str,  # Reason if not eligible
            "checks": {
                "consent": bool,
                "not_opted_out": bool,
                "not_internal_dnc": bool,
                "not_national_dnc": bool,
                "within_time_window": bool,
                "below_attempt_limit": bool,
                "cooldown_passed": bool,
                "retry_allowed": bool
            }
        }
    """
    checks = {}
    reasons = []
    
    # Check 1: Consent status
    checks["consent"] = contact.consent_status is True
    if not checks["consent"]:
        reasons.append("No consent on record")
    
    # Check 2: Not opted out
    checks["not_opted_out"] = contact.opted_out is False
    if not checks["not_opted_out"]:
        reasons.append("Contact has opted out")
    
    # Check 3: Not on internal DNC
    checks["not_internal_dnc"] = contact.internal_dnc is False
    if not checks["not_internal_dnc"]:
        reasons.append("On internal DNC list")
    
    # Check 4: Not on national DNC (if applicable)
    checks["not_national_dnc"] = contact.national_dnc is False
    if not checks["not_national_dnc"]:
        reasons.append("On national DNC registry")
    
    # Check 5: Within allowed time window (8 AM - 9 PM in contact's timezone)
    checks["within_time_window"] = _is_within_time_window(contact.timezone)
    if not checks["within_time_window"]:
        reasons.append("Outside allowed calling hours (8 AM - 9 PM)")
    
    # Check 6: Below attempt limit
    # In testing mode, bypass this check
    if DISABLE_ELIGIBILITY_CHECKS:
        checks["below_attempt_limit"] = True  # Always pass in testing
    else:
        checks["below_attempt_limit"] = contact.call_attempt_count < MAX_CALL_ATTEMPTS
        if not checks["below_attempt_limit"]:
            reasons.append(f"Exceeded maximum call attempts ({MAX_CALL_ATTEMPTS})")
    
    # Check 7: Cooldown period passed
    # In testing mode, bypass cooldown check
    if DISABLE_ELIGIBILITY_CHECKS:
        checks["cooldown_passed"] = True  # Always pass in testing
    else:
        checks["cooldown_passed"] = _has_cooldown_passed(contact)
        if not checks["cooldown_passed"]:
            hours_since = _hours_since_last_call(contact)
            reasons.append(f"Cooldown not passed (minimum {MIN_CALL_COOLDOWN_HOURS} hours, {hours_since:.1f} hours since last call)")
    
    # Check 8: Last call outcome allows retry
    checks["retry_allowed"] = _is_retry_allowed(contact)
    if not checks["retry_allowed"]:
        if contact.last_call_outcome:
            reasons.append(f"Last call outcome '{contact.last_call_outcome}' does not allow retry")
        else:
            # If no outcome recorded, allow retry (backward compatibility)
            checks["retry_allowed"] = True
    
    # All checks must pass
    eligible = all(checks.values())
    
    # ⚠️ TESTING BYPASS: If enabled, allow calls even if checks fail
    # This is for testing only - MUST be disabled in production!
    if DISABLE_ELIGIBILITY_CHECKS:
        if not eligible:
            print("⚠️  WARNING: Eligibility checks bypassed for testing! This should NOT be enabled in production!")
            print(f"   Would have been blocked by: {'; '.join(reasons)}")
        eligible = True  # Force eligible to True for testing
    
    return {
        "eligible": eligible,
        "reason": "; ".join(reasons) if reasons else "All checks passed",
        "checks": checks,
        "bypassed_for_testing": DISABLE_ELIGIBILITY_CHECKS and not all(checks.values())  # Flag if bypassed
    }


def _is_within_time_window(timezone_str: Optional[str]) -> bool:
    """Check if current time is within allowed calling hours (8 AM - 9 PM) in contact's timezone."""
    if not timezone_str:
        timezone_str = "America/New_York"  # Default timezone
    
    try:
        tz = pytz.timezone(timezone_str)
        now_local = datetime.now(tz)
        current_hour = now_local.hour
        
        return ALLOWED_CALL_START_HOUR <= current_hour < ALLOWED_CALL_END_HOUR
    except Exception as e:
        print(f"⚠️  Error checking time window for timezone {timezone_str}: {e}")
        # Default to not allowing if timezone is invalid
        return False


def _has_cooldown_passed(contact: Contact) -> bool:
    """Check if minimum cooldown period has passed since last call."""
    if not contact.last_called_at:
        return True  # Never called, so cooldown has "passed"
    
    hours_since = _hours_since_last_call(contact)
    return hours_since >= MIN_CALL_COOLDOWN_HOURS


def _hours_since_last_call(contact: Contact) -> float:
    """Calculate hours since last call."""
    if not contact.last_called_at:
        return float('inf')  # Never called
    
    delta = datetime.utcnow() - contact.last_called_at
    return delta.total_seconds() / 3600.0


def _is_retry_allowed(contact: Contact) -> bool:
    """
    Check if last call outcome allows retry.
    
    Retry allowed for:
    - 'no_answer' - No one answered
    - 'voicemail' - Went to voicemail
    
    Retry NOT allowed for:
    - 'hangup' - Caller hung up
    - 'opt_out' - Contact opted out
    - 'connected' - Connected but declined
    - 'connected_and_declined' - Explicitly declined
    
    Returns True if retry is allowed, False otherwise.
    """
    # If opt-out has been cleared for this contact, do NOT block on a historical
    # 'opt_out' value stored in last_call_outcome.
    #
    # This can happen if:
    # - Vapi/webhook previously marked the call as opt-out
    # - An admin later cleared opt-out via the API
    #
    # In that case, treat last_call_outcome as if it were not 'opt_out'.
    if not getattr(contact, "opted_out", False) and getattr(contact, "last_call_outcome", None) == "opt_out":
        print(
            f"ℹ️  Ignoring historical 'opt_out' outcome for contact {contact.id} "
            f"because opted_out=False (opt-out was cleared). Allowing retry."
        )
        return True
    
    if not contact.last_call_outcome:
        # No outcome recorded - allow retry (backward compatibility)
        return True
    
    # Retry allowed outcomes
    retry_allowed_outcomes = ['no_answer', 'voicemail']
    
    # Retry NOT allowed outcomes
    no_retry_outcomes = ['hangup', 'opt_out', 'connected', 'connected_and_declined']
    
    if contact.last_call_outcome in retry_allowed_outcomes:
        return True
    
    if contact.last_call_outcome in no_retry_outcomes:
        return False
    
    # Unknown outcome - default to not allowing retry (safer)
    print(f"⚠️  Unknown call outcome '{contact.last_call_outcome}' for contact {contact.id}, defaulting to no retry")
    return False


def determine_call_outcome(
    call_status: Optional[str],
    call_duration: Optional[int],
    transcript: Optional[str],
    opt_out_detected: bool = False
) -> str:
    """
    Determine call outcome from call data.
    
    Args:
        call_status: Call status from Vapi (e.g., 'ended', 'failed', 'no-answer', 'voicemail')
        call_duration: Call duration in seconds
        transcript: Call transcript text
        opt_out_detected: Whether opt-out was detected
    
    Returns:
        Call outcome: 'no_answer' | 'voicemail' | 'hangup' | 'connected' | 'opt_out' | 'connected_and_declined'
    """
    # Opt-out takes precedence
    if opt_out_detected:
        return "opt_out"
    
    # Normalize call status to lowercase for comparison
    status_lower = (call_status or "").lower()
    
    # Check for specific statuses
    if "no-answer" in status_lower or "no_answer" in status_lower or status_lower == "no-answer":
        return "no_answer"
    
    if "voicemail" in status_lower or status_lower == "voicemail":
        return "voicemail"
    
    if "failed" in status_lower or "busy" in status_lower:
        return "no_answer"  # Treat as no answer for retry purposes
    
    # If call ended and we have transcript, analyze it
    if transcript:
        transcript_lower = transcript.lower()
        
        # Check for decline indicators
        decline_keywords = [
            "not interested", "no thanks", "decline", "don't want", "not now",
            "maybe later", "not right now", "not at this time", "not today"
        ]
        
        if any(keyword in transcript_lower for keyword in decline_keywords):
            return "connected_and_declined"
        
        # If we have transcript and it's not a decline, it was connected
        if len(transcript.strip()) > 50:  # Substantial conversation
            return "connected"
    
    # If call ended but very short duration (< 10 seconds), likely hangup
    if call_duration and call_duration < 10:
        return "hangup"
    
    # If call ended with some duration but no transcript, might be hangup
    if call_duration and call_duration < 30 and not transcript:
        return "hangup"
    
    # If we have duration > 30 seconds, assume it was connected
    if call_duration and call_duration >= 30:
        return "connected"
    
    # Default to hangup if we can't determine (safer - no retry)
    return "hangup"


# ============================================================================
# CONTACT MANAGEMENT
# ============================================================================

def get_or_create_contact(phone_number: str, session: Session, **kwargs) -> Contact:
    """
    Get existing contact or create new one.
    
    Args:
        phone_number: E.164 format phone number
        session: Database session
        **kwargs: Additional fields to set (name, email, timezone, etc.)
    
    Returns:
        Contact object
    """
    # Normalize phone number
    normalized = normalize_phone_number(phone_number)
    
    # Try to find existing contact
    contact = session.exec(
        select(Contact).where(Contact.phone_number == normalized)
    ).first()
    
    if contact:
        # Update fields if provided
        for key, value in kwargs.items():
            if hasattr(contact, key) and value is not None:
                setattr(contact, key, value)
        contact.updated_at = datetime.utcnow()
        return contact
    
    # Create new contact
    contact = Contact(
        phone_number=normalized,
        timezone=kwargs.get("timezone", "America/New_York"),
        name=kwargs.get("name"),
        email=kwargs.get("email"),
        notes=kwargs.get("notes"),
        **{k: v for k, v in kwargs.items() if k not in ["timezone", "name", "email", "notes"]}
    )
    session.add(contact)
    session.commit()
    session.refresh(contact)
    return contact


def record_consent(
    phone_number: str,
    session: Session,
    source: str = "call",
    **kwargs
) -> Contact:
    """
    Record consent for a contact.
    
    Args:
        phone_number: E.164 format phone number
        session: Database session
        source: Consent source ('call', 'form', 'sms', 'explicit', 'existing_relationship')
        **kwargs: Additional contact fields
    
    Returns:
        Updated Contact object
    """
    contact = get_or_create_contact(phone_number, session, **kwargs)
    
    contact.consent_status = True
    contact.consent_source = source
    contact.consent_timestamp = datetime.utcnow()
    contact.updated_at = datetime.utcnow()
    
    session.add(contact)
    session.commit()
    session.refresh(contact)
    
    return contact


def record_opt_out(
    phone_number: str,
    session: Session,
    method: str = "voice",
    call_id: Optional[str] = None,
    **kwargs
) -> Contact:
    """
    Record opt-out for a contact (ZERO TOLERANCE - immediate and permanent).
    
    Args:
        phone_number: E.164 format phone number
        session: Database session
        method: Opt-out method ('voice', 'keypad', 'sms', 'web', 'manual')
        call_id: Call ID where opt-out occurred (if applicable)
        **kwargs: Additional contact fields
    
    Returns:
        Updated Contact object
    """
    contact = get_or_create_contact(phone_number, session, **kwargs)
    
    # IMMEDIATE opt-out - no exceptions
    contact.opted_out = True
    contact.opt_out_timestamp = datetime.utcnow()
    contact.opt_out_method = method
    contact.opt_out_call_id = call_id
    contact.last_call_outcome = "opt_out"  # Set outcome to prevent retry
    contact.updated_at = datetime.utcnow()
    
    session.add(contact)
    session.commit()
    session.refresh(contact)
    
    print(f"🚫 OPT-OUT RECORDED: {phone_number} via {method} (call_id: {call_id})")
    
    return contact


# ============================================================================
# TRANSCRIPT EXTRACTION
# ============================================================================

def _split_transcript(transcript: str) -> Dict[str, str]:
    """Split transcript into user/bot/all text blobs."""
    lines = transcript.splitlines()
    user_lines: List[str] = []
    bot_lines: List[str] = []
    other_lines: List[str] = []

    for line in lines:
        s = line.strip()
        if not s:
            continue
        if s.lower().startswith("user:"):
            user_lines.append(s)
        elif s.lower().startswith("bot:"):
            bot_lines.append(s)
        else:
            other_lines.append(s)

    return {
        "user": "\n".join(user_lines),
        "bot": "\n".join(bot_lines),
        "all": "\n".join(lines),
    }


def _strip_appended_summary(transcript: str) -> str:
    """
    Legacy cleanup: older stored transcripts may have had a summary appended like:
      <conversation>
      ---
      Summary: ...

    We want Gemini extraction to see only the conversation, not the summary.
    """
    if not transcript:
        return transcript
    s = transcript
    # Common marker used by our webhook code historically
    marker = "\n\n---\n\nSummary:"
    if marker in s:
        return s.split(marker, 1)[0].strip()
    return s


# ============================================================================
# 3-LAYER EXTRACTION SYSTEM (Token Optimization)
# ============================================================================

def _preprocess_transcript_layer1(transcript: str) -> str:
    """
    Layer 1: Deterministic Pre-Processor (NO AI)
    
    Goal: Remove everything AI must never see, keep only relevant lines.
    
    Removes:
    - Logs, timestamps, debug info
    - System messages
    - AI disclaimers
    
    Keeps:
    - User: lines
    - AI lines that ask for info
    - AI lines that confirm info
    """
    if not transcript:
        return ""
    
    lines = transcript.splitlines()
    cleaned_lines = []
    
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue
        
        # Remove debug/log lines
        if any(marker in line_stripped.lower() for marker in [
            "[debug]", "[log]", "[info]", "[warning]", "[error]",
            "timestamp:", "duration:", "call_id:", "metadata:"
        ]):
            continue
        
        # Remove system messages
        if line_stripped.lower().startswith(("system:", "note:", "metadata:")):
            continue
        
        # Keep user lines
        if line_stripped.lower().startswith(("user:", "customer:")):
            cleaned_lines.append(line_stripped)
            continue
        
        # Keep AI lines that ask for info, confirm info, OR mention properties/addresses
        if line_stripped.lower().startswith(("bot:", "assistant:", "ai:")):
            line_lower = line_stripped.lower()
            # Keep if AI asks for info
            if any(keyword in line_lower for keyword in [
                "what's your", "could you provide", "may i have", "can you share",
                "your name", "your email", "your phone", "your contact",
                "what area", "what city", "what location", "what property",
                "your email is", "your name is", "correct?", "right?"
            ]):
                cleaned_lines.append(line_stripped)
            # Keep if AI confirms something
            elif any(keyword in line_lower for keyword in [
                "your email is", "your name is", "i have your", "confirmed",
                "is that correct", "is that right"
            ]):
                cleaned_lines.append(line_stripped)
            # Keep if AI mentions properties/addresses (critical for property extraction)
            elif any(keyword in line_lower for keyword in [
                "found an apartment", "located at", "property at", "address", 
                "apartment at", "i found", "there's an", "available at",
                "street", "road", "avenue", "drive", "boulevard", "lane"
            ]):
                cleaned_lines.append(line_stripped)
            # Otherwise skip generic AI chatter
            continue
        
        # Keep other lines that might contain info (fallback)
        cleaned_lines.append(line_stripped)
    
    return "\n".join(cleaned_lines)


def _condense_transcript_layer2(transcript: str, max_length: int = 2000) -> str:
    """
    Layer 2: Transcript Condenser (Rule-based)
    
    For long calls: Extract only info-relevant turns.
    
    Strategy:
    - Keep lines where AI asks for info (name, email, phone, location, property, budget, tour)
    - Keep user responses within next 1-2 turns
    - Keep AI confirmations and user "yes/correct" responses
    
    Returns condensed transcript (typically 300-800 chars for long calls).
    """
    if not transcript:
        return ""
    
    # If already short, return as-is
    if len(transcript) <= max_length:
        return transcript
    
    lines = transcript.splitlines()
    relevant_lines = []
    
    # Keywords that indicate info-relevant content
    info_keywords = [
        "name", "email", "phone", "contact",
        "area", "city", "location", "property", "address",
        "budget", "price", "rent", "cost",
        "tour", "visit", "schedule", "booking", "appointment"
    ]
    
    # Track context: if AI just asked for info, keep next user response
    ai_asked_for_info = False
    keep_next_n_lines = 0
    
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        if not line_stripped:
            continue
        
        line_lower = line_stripped.lower()
        
        # Check if this line is info-relevant
        is_info_relevant = any(keyword in line_lower for keyword in info_keywords)
        
        # AI asks for info
        if line_lower.startswith(("bot:", "assistant:", "ai:")) and is_info_relevant:
            relevant_lines.append(line_stripped)
            ai_asked_for_info = True
            keep_next_n_lines = 2  # Keep next 2 lines (user response)
            continue
        
        # User responds after AI asked
        if keep_next_n_lines > 0:
            relevant_lines.append(line_stripped)
            keep_next_n_lines -= 1
            continue
        
        # AI confirms something OR mentions properties/addresses
        if line_lower.startswith(("bot:", "assistant:", "ai:")):
            # AI confirms info
            if any(phrase in line_lower for phrase in [
                "your email is", "your name is", "i have your", "correct?", "right?"
            ]):
                relevant_lines.append(line_stripped)
                keep_next_n_lines = 1  # Keep next line (user confirmation)
                continue
            # AI mentions properties/addresses (critical for extraction)
            elif any(keyword in line_lower for keyword in [
                "found an apartment", "located at", "property at", "address",
                "apartment at", "i found", "there's an", "available at",
                "street", "road", "avenue", "drive", "boulevard", "lane"
            ]):
                relevant_lines.append(line_stripped)
                continue
        
        # User provides info directly
        if line_lower.startswith(("user:", "customer:")) and is_info_relevant:
            relevant_lines.append(line_stripped)
            continue
        
        # User confirms ("yes", "correct", "that's right")
        if line_lower.startswith(("user:", "customer:")) and any(
            word in line_lower for word in ["yes", "correct", "right", "that's", "exactly"]
        ):
            relevant_lines.append(line_stripped)
            continue
    
    condensed = "\n".join(relevant_lines)
    
    # If still too long, truncate but keep structure
    if len(condensed) > max_length:
        # Keep first part (usually most important)
        condensed = condensed[:max_length].rsplit("\n", 1)[0] + "\n..."
    
    return condensed


def _is_valid_value(value: Any) -> bool:
    """
    Check if a value is valid (not null, not "N/A", not empty).
    Used to filter out invalid values before sending to Vapi.
    
    Args:
        value: Value to check
        
    Returns:
        True if value is valid (should be sent to Vapi), False otherwise
    """
    if value is None:
        return False
    
    if isinstance(value, str):
        # Remove whitespace and check
        stripped = value.strip()
        if not stripped:
            return False
        # Check for common "empty" indicators
        if stripped.lower() in ["n/a", "na", "none", "null", "undefined", ""]:
            return False
    
    return True


def _build_minimal_gemini_prompt(condensed_transcript: str) -> str:
    """
    Layer 3: Minimal Gemini Prompt
    
    Only essential rules and schema - no examples, no verbose instructions.
    Reduces token usage by ~70%.
    """
    return f"""Extract customer information from this phone call transcript.

RULES:
1. For email/name: Only extract what USER provided or explicitly confirmed.
2. For property: Extract addresses mentioned by AI (e.g., "I found an apartment at 123 Main St") - user doesn't need to confirm.
3. For purpose: Extract from user's statements (e.g., "looking for apartments", "want to book a tour").
4. For region: Extract city/state from user mentions or property addresses.
5. Never extract names from greetings or filler words ("so", "yeah", "ok").
6. Reject verbs as names: "looking", "providing", "following", "searching".
7. If a value is not clearly present, return null.
8. Output valid JSON only.

OUTPUT SCHEMA:
{{
  "email": string | null,
  "customer_name": string | null,
  "inferred_name": string | null,
  "inquiry_property": string | null,
  "inquiry_purpose": string | null,
  "region": string | null
}}

TRANSCRIPT:
<<<
{condensed_transcript}
>>>

Return ONLY valid JSON, no markdown, no code blocks, no explanations:"""
    # Fallback marker
    marker2 = "\n\nSummary:"
    if marker2 in s and s.strip().lower().startswith("summary:") is False:
        # Only strip if it's appended after some conversation text
        left, right = s.split(marker2, 1)
        if left.strip():
            return left.strip()
    return s


def _normalize_spoken_email(raw: str) -> Optional[str]:
    """
    Best-effort normalization for transcripts like:
    - "rehan at g mail dot com"
    - "rehan at gmail dot com"
    - "rehan@gmail.com"
    """
    import re

    if not raw:
        return None

    s = raw.strip().lower()
    s = s.replace(" at ", "@").replace(" dot ", ".")
    s = s.replace(" (at) ", "@").replace(" (dot) ", ".")
    s = s.replace(" g mail ", " gmail ").replace(" g-mail ", " gmail ")
    s = s.replace(" gmail ", "gmail")
    s = s.replace(" yahoo ", "yahoo").replace(" outlook ", "outlook").replace(" hotmail ", "hotmail")
    s = s.replace(" underscore ", "_").replace(" dash ", "-").replace(" hyphen ", "-")
    s = re.sub(r"\s+", "", s)

    # Basic sanity
    if "@" not in s or "." not in s.split("@")[-1]:
        return None

    # Validate with a simple email regex
    if re.fullmatch(r"[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}", s):
        return s
    return None


def _infer_name_from_email(email: str) -> Optional[str]:
    """
    Infer a name from an email address.
    Examples:
    - "john@gmail.com" -> "John"
    - "rehan.smith@gmail.com" -> "Rehan"
    - "yashan_jamal@yahoo.com" -> "Yashan"
    - "kj373@gmail.com" -> "Kj373" (if no letters, return None)
    """
    import re

    if not email or "@" not in email:
        return None
    local = email.split("@", 1)[0]
    # Remove non-letter characters but keep separators
    local = re.sub(r"[^a-zA-Z._\-]", "", local).strip("._-")
    if not local:
        return None
    
    # Prefer first segment (before first separator)
    first = re.split(r"[._\-]+", local)[0]
    if not first:
        return None
    
    # Check if it contains at least one letter (not just numbers)
    if not re.search(r"[a-zA-Z]", first):
        # If it's all numbers (like "kj373"), try to extract meaningful part
        # For "kj373", we could return None or try to find letters
        # For now, return None if no letters
        return None
    
    # Capitalize properly
    return first[:1].upper() + first[1:].lower()


# ============================================================================
# CALL RECORD CLEANUP: Filter short calls
# ============================================================================

def should_keep_call_record(call_record: CallRecord, min_duration_seconds: int = 60) -> bool:
    """
    Determine if a call record should be kept based on duration.
    
    Args:
        call_record: CallRecord to check
        min_duration_seconds: Minimum duration in seconds (default: 60 = 1 minute)
    
    Returns:
        True if call should be kept, False if it should be discarded
    """
    if not call_record.call_duration:
        # If duration is not set yet, we can't determine - keep it for now
        # Duration will be set later in webhook processing
        return True
    
    return call_record.call_duration > min_duration_seconds


def cleanup_short_call_records(
    session: Session,
    min_duration_seconds: int = 90,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Clean up existing call records that are too short.
    
    Args:
        session: Database session
        min_duration_seconds: Minimum duration to keep (default: 90 = 1 minute 30 seconds)
        dry_run: If True, only count records without deleting
    
    Returns:
        Statistics about cleanup operation
    """
    print(f"\n{'='*80}")
    print(f"🧹 CLEANUP: Removing call records with duration <= {min_duration_seconds} seconds")
    print(f"{'='*80}")
    
    # Find all call records with duration <= threshold
    short_calls = session.exec(
        select(CallRecord)
        .where(CallRecord.call_duration.isnot(None))
        .where(CallRecord.call_duration <= min_duration_seconds)
    ).all()
    
    count = len(short_calls)
    print(f"   Found {count} call records to delete (duration <= {min_duration_seconds}s)")
    
    if count == 0:
        print(f"   ✅ No short call records to clean up")
        return {
            "deleted": 0,
            "dry_run": dry_run
        }
    
    if dry_run:
        print(f"   🔍 DRY RUN: Would delete {count} call records")
        for call in short_calls[:10]:  # Show first 10 as examples
            print(f"      - Call {call.call_id[:8]}... | Duration: {call.call_duration}s | Created: {call.created_at}")
        return {
            "would_delete": count,
            "dry_run": True
        }
    
    # Delete short call records
    deleted_count = 0
    for call in short_calls:
        try:
            session.delete(call)
            deleted_count += 1
            if deleted_count % 100 == 0:
                print(f"   📊 Progress: Deleted {deleted_count}/{count} call records...")
        except Exception as e:
            print(f"   ⚠️  Error deleting call {call.call_id}: {e}")
    
    try:
        session.commit()
        print(f"   ✅ Successfully deleted {deleted_count} short call records")
    except Exception as e:
        session.rollback()
        print(f"   ❌ Error committing deletions: {e}")
        raise
    
    return {
        "deleted": deleted_count,
        "dry_run": False
    }


def cleanup_bad_contact_names(
    session: Session,
    dry_run: bool = True
) -> Dict[str, Any]:
    """
    Clean up existing contacts with bad names (verbs, filler words, bot names).
    
    Args:
        session: Database session
        dry_run: If True, only count contacts without updating
    
    Returns:
        Statistics about cleanup operation
    """
    print(f"\n{'='*80}")
    print(f"🧹 CLEANUP: Fixing bad contact names (verbs/filler words)")
    print(f"{'='*80}")
    
    # Find all contacts with names
    all_contacts = session.exec(select(Contact).where(Contact.name.isnot(None))).all()
    
    bad_contacts = []
    for contact in all_contacts:
        if contact.name and _is_bad_person_name(contact.name):
            bad_contacts.append(contact)
    
    count = len(bad_contacts)
    print(f"   Found {count} contacts with bad names")
    
    if count == 0:
        print(f"   ✅ No bad contact names to clean up")
        return {
            "fixed": 0,
            "dry_run": dry_run
        }
    
    if dry_run:
        print(f"   🔍 DRY RUN: Would fix {count} contact names")
        for contact in bad_contacts[:10]:  # Show first 10 as examples
            print(f"      - Contact {contact.id} | Phone: {contact.phone_number} | Bad name: '{contact.name}'")
        return {
            "would_fix": count,
            "dry_run": True
        }
    
    # Fix bad names by setting them to None
    fixed_count = 0
    for contact in bad_contacts:
        try:
            old_name = contact.name
            contact.name = None  # Clear bad name
            session.add(contact)
            fixed_count += 1
            if fixed_count % 100 == 0:
                print(f"   📊 Progress: Fixed {fixed_count}/{count} contact names...")
        except Exception as e:
            print(f"   ⚠️  Error fixing contact {contact.id}: {e}")
    
    try:
        session.commit()
        print(f"   ✅ Successfully fixed {fixed_count} bad contact names")
    except Exception as e:
        session.rollback()
        print(f"   ❌ Error committing fixes: {e}")
        raise
    
    return {
        "fixed": fixed_count,
        "dry_run": False
    }


def _is_bad_person_name(name: Optional[str]) -> bool:
    """
    Centralized "bad name" detection.
    Fixes cases like 'Looking' / 'Following' / 'Providing' being treated as real names.
    """
    if not name:
        return True
    s = str(name).strip()
    # Reject ultra-short tokens like "So", "Ok" etc.
    # We'll allow 1–2 character names ONLY when they come from strong patterns
    # (e.g., inferred from email like "Li" < li@..., or explicit "my name is X"),
    # but in generic context they are almost always filler/discourse markers.
    if len(s) < 3:
        return True
    lower = s.lower().strip()

    bad_names = {
        "riley", "assistant", "bot", "ai", "lease", "leasap", "speaking",
        "this is", "hi", "hello", "hey", "yes", "no", "okay", "ok", "riley speaking",
    }
    common_verbs = {
        "looking", "searching", "asking", "wanting", "trying", "calling",
        "needing", "seeking", "finding", "checking", "wondering", "thinking",
        "providing", "following",
    }
    # Common discourse markers / filler words that Gemini sometimes proposes as names
    common_words = {
        "anyway", "preferably", "should", "would", "could", "please",
        "thanks", "thank", "so", "yeah", "yep", "nope", "uh", "um", "well",
    }

    if lower in bad_names or lower in common_verbs or lower in common_words:
        return True
    if "riley" in lower:
        return True
    return False


# ============================================================================
# REAL-TIME EXTRACTION: Extract and cache intel when transcripts arrive
# ============================================================================

def get_best_recent_intel_for_phone(
    session: Session,
    phone: str,
    max_calls: int = 10,
    force_re_extract: bool = False,
) -> Dict[str, Optional[str]]:
    """
    Best-recent context strategy:
    - Start from the MOST RECENT call (highest priority).
    - If a field is missing in the most recent call, backfill it from the next most recent call, etc.
    - Always uses transcripts (not summaries). If an older transcript had a summary appended, we strip it during extraction.
    - Keeps per-call caching in CallRecord.extracted_intel up to date.
    """
    merged: Dict[str, Optional[str]] = {
        "email": None,
        "inferred_name": None,
        "region": None,
        "inquiry_property": None,
        "inquiry_purpose": None,
        "inquiry_summary": None,
        "call_summary": None,
    }

    # Get recent calls, excluding short calls (< 1 minute) and those without transcripts
    recent_calls = session.exec(
        select(CallRecord)
        .where(CallRecord.caller_number == phone)
        .where(CallRecord.transcript.isnot(None))
        .where(
            or_(
                CallRecord.call_duration.is_(None),  # Duration not set yet (keep for now)
                CallRecord.call_duration > 60  # Only calls longer than 1 minute
            )
        )
        .order_by(CallRecord.created_at.desc())
        .limit(max_calls)
    ).all()

    # Iterate newest -> oldest, fill missing fields only
    for call in recent_calls:
        intel: Optional[Dict[str, Any]] = None
        if call.extracted_intel and call.extraction_status == "completed" and not force_re_extract:
            intel = call.extracted_intel
        else:
            intel = extract_and_store_intel_for_call_record(call, session, force_re_extract=force_re_extract)

        if not isinstance(intel, dict):
            continue

        for k in ["email", "inferred_name", "region", "inquiry_property", "inquiry_purpose", "inquiry_summary", "call_summary"]:
            v = intel.get(k)
            if v is None:
                continue
            # Never propagate obviously bad names like 'Looking', 'Following', 'Providing'
            if k == "inferred_name" and _is_bad_person_name(v):
                continue
            if merged.get(k) is None:
                merged[k] = v

        # Early exit if we have everything we care about
        if all(merged.get(k) is not None for k in ["inferred_name", "region", "inquiry_property", "inquiry_purpose"]):
            # Email is optional; don't require it for early exit
            pass

    return merged

def extract_and_store_intel_for_call_record(
    call_record: CallRecord,
    session: Session,
    force_re_extract: bool = False
) -> Dict[str, Optional[str]]:
    """
    Extract intel from call record transcript and store in database.
    This is called automatically when transcripts arrive from VAPI.
    
    Args:
        call_record: The CallRecord to extract from
        session: Database session
        force_re_extract: If True, re-extract even if already extracted
        
    Returns:
        Extracted intel dictionary
    """
    print(f"\n{'='*80}")
    print(f"🔍 extract_and_store_intel_for_call_record() CALLED")
    print(f"   Call ID: {call_record.call_id}")
    print(f"   Force re-extract: {force_re_extract}")
    print(f"   Current extraction_status: {call_record.extraction_status}")
    print(f"   Has extracted_intel: {call_record.extracted_intel is not None}")
    print(f"   Transcript provided: {call_record.transcript is not None}")
    if call_record.transcript:
        print(f"   Transcript length: {len(call_record.transcript)} chars")
    print(f"{'='*80}")
    
    # Optionally limit number of extraction attempts per transcript
    # so we don't hammer Gemini forever on a bad/empty call.
    if call_record.call_metadata is None:
        call_record.call_metadata = {}
    attempts = int(call_record.call_metadata.get("extraction_attempts", 0) or 0)
    if not force_re_extract and call_record.extraction_status in ("failed", "skipped") and attempts >= 3:
        print(f"   ⏭️  Max extraction attempts reached ({attempts}) for call {call_record.call_id} - not retrying")
        return {
            "email": None,
            "inferred_name": None,
            "region": None,
            "inquiry_property": None,
            "inquiry_purpose": None,
            "inquiry_summary": None,
            "call_summary": None,
        }
    # Increment attempts before we try
    call_record.call_metadata["extraction_attempts"] = attempts + 1
    session.add(call_record)
    try:
        session.commit()
    except:
        session.rollback()

    # Skip if call is too short (< 1 minute) - don't extract from short calls
    if call_record.call_duration is not None and call_record.call_duration <= 60:
        print(f"   ⏭️  Skipping - call too short ({call_record.call_duration}s <= 60s)")
        if call_record.extraction_status != "skipped":
            call_record.extraction_status = "skipped"
            call_record.extracted_intel = None
            if call_record.transcript:
                call_record.transcript = None  # Clear transcript for short calls
            session.add(call_record)
            try:
                session.commit()
            except:
                session.rollback()
        return {
            "email": None,
            "inferred_name": None,
            "region": None,
            "inquiry_property": None,
            "inquiry_purpose": None,
            "inquiry_summary": None,
            "call_summary": None,
        }
    
    # Skip if no transcript
    if not call_record.transcript or len(call_record.transcript.strip()) < 50:
        print(f"   ⏭️  Skipping - transcript too short or missing")
        if call_record.extraction_status != "skipped":
            call_record.extraction_status = "skipped"
            session.add(call_record)
            try:
                session.commit()
            except:
                session.rollback()
        return {
            "email": None,
            "inferred_name": None,
            "region": None,
            "inquiry_property": None,
            "inquiry_purpose": None,
            "inquiry_summary": None,
            "call_summary": None,
        }
    
    # Skip if already extracted (unless force_re_extract)
    if not force_re_extract and call_record.extraction_status == "completed" and call_record.extracted_intel:
        print(f"   ✅ Using cached extraction for call {call_record.call_id}")
        print(f"   📦 Cached data:")
        cached = call_record.extracted_intel
        print(f"      - email: {cached.get('email')}")
        print(f"      - inferred_name: {cached.get('inferred_name')}")
        print(f"      - inquiry_property: {cached.get('inquiry_property')}")
        print(f"      - inquiry_purpose: {cached.get('inquiry_purpose')}")
        print(f"      - region: {cached.get('region')}")
        return call_record.extracted_intel
    
    # Mark as pending
    print(f"   🔄 Starting extraction (status: pending)...")
    call_record.extraction_status = "pending"
    session.add(call_record)
    try:
        session.commit()
    except:
        session.rollback()
    
    try:
        # Extract intel
        print(f"   🚀 Calling extract_contact_intel_from_transcript()...")
        extracted_intel = extract_contact_intel_from_transcript(call_record.transcript)
        
        # Store in database
        print(f"\n   💾 STORING EXTRACTED INTEL IN DATABASE:")
        print(f"      - email: {extracted_intel.get('email')}")
        print(f"      - inferred_name: {extracted_intel.get('inferred_name')}")
        print(f"      - inquiry_property: {extracted_intel.get('inquiry_property')}")
        print(f"      - inquiry_purpose: {extracted_intel.get('inquiry_purpose')}")
        print(f"      - region: {extracted_intel.get('region')}")
        
        call_record.extracted_intel = extracted_intel
        call_record.extracted_intel_updated_at = datetime.utcnow()
        call_record.extraction_status = "completed"
        session.add(call_record)
        try:
            session.commit()
            print(f"   ✅ Successfully stored extracted intel for call {call_record.call_id}")
        except Exception as e:
            session.rollback()
            print(f"   ❌ Failed to store extracted intel: {e}")
            import traceback
            traceback.print_exc()
        
        return extracted_intel
        
    except Exception as e:
        print(f"   ❌ Extraction failed for call {call_record.call_id}: {e}")
        import traceback
        traceback.print_exc()
        call_record.extraction_status = "failed"
        session.add(call_record)
        try:
            session.commit()
        except:
            session.rollback()
        
        # Return empty dict on failure
        return {
            "email": None,
            "inferred_name": None,
            "region": None,
            "inquiry_property": None,
            "inquiry_purpose": None,
            "inquiry_summary": None,
            "call_summary": None,
        }


# ============================================================================
# ASYNC EXTRACTION QUEUE (Latency Optimization)
# ============================================================================

_extraction_queue: "Queue[str]" = Queue()
_extraction_worker_started: bool = False
_extraction_in_flight: Set[str] = set()
_extraction_lock: Lock = Lock()


def _run_extraction_job(call_record_id: Union[str]) -> None:
    """
    Run extraction for a single call record.
    This is executed in a background worker thread.
    """
    try:
        with Session(engine) as session:
            call_record = session.get(CallRecord, call_record_id)
            if not call_record:
                print(f"   ⚠️  Extraction job: CallRecord {call_record_id} not found")
                return

            # Only extract for calls we have decided to keep:
            # - Has non-empty transcript
            # - Not too short (duration > 60s if duration known)
            if not call_record.transcript or not str(call_record.transcript).strip():
                print(f"   ⏭️  Extraction job: Call {call_record.call_id} has no usable transcript, skipping")
                return

            if call_record.call_duration is not None and call_record.call_duration <= 60:
                print(
                    f"   ⏭️  Extraction job: Call {call_record.call_id} duration "
                    f"{call_record.call_duration}s <= 60s, skipping"
                )
                return

            # Decide whether to force re-extract:
            # - Outbound calls: we want the freshest data → force_re_extract=True
            # - Inbound calls: respect existing cache/attempt logic
            force_re_extract = (call_record.call_direction == "outbound")

            print(
                f"   🚀 Extraction job starting for call {call_record.call_id} "
                f"(direction={call_record.call_direction}, force_re_extract={force_re_extract})"
            )
            extracted_intel = extract_and_store_intel_for_call_record(
                call_record, session, force_re_extract=force_re_extract
            )

            # Update contact if we found useful intel
            if call_record.contact_id and extracted_intel:
                try:
                    contact = session.get(Contact, call_record.contact_id)
                    if contact:
                        updated_contact = False

                        # Update email if contact has none
                        if extracted_intel.get("email") and not contact.email:
                            contact.email = extracted_intel["email"]
                            updated_contact = True

                        # Update name if inferred_name is good and existing name is bad
                        inferred_name = extracted_intel.get("inferred_name")
                        if inferred_name:
                            from DB.outbound_calling import _is_bad_person_name  # type: ignore

                            proposed = inferred_name
                            # Only overwrite if existing name is bad and proposed is good
                            if not _is_bad_person_name(proposed) and (
                                not contact.name or _is_bad_person_name(contact.name)
                            ):
                                contact.name = proposed
                                updated_contact = True

                        if updated_contact:
                            session.add(contact)
                            session.commit()
                            print(
                                f"   ✅ Extraction job: Updated contact {contact.id} "
                                f"from extracted intel (call_id={call_record.call_id})"
                            )
                except Exception as e:
                    session.rollback()
                    print(f"   ⚠️  Extraction job: Failed updating contact from intel: {e}")

    except Exception as e:
        print(f"   ❌ Extraction job failed for CallRecord {call_record_id}: {e}")


def _extraction_worker_loop() -> None:
    """
    Background worker loop that processes extraction jobs from the queue.
    """
    print("🚀 Extraction worker started")
    while True:
        call_record_id = _extraction_queue.get()
        try:
            _run_extraction_job(call_record_id)
        finally:
            with _extraction_lock:
                _extraction_in_flight.discard(str(call_record_id))
            _extraction_queue.task_done()


def _ensure_extraction_worker_started() -> None:
    """
    Ensure the background extraction worker thread is started once.
    """
    global _extraction_worker_started
    with _extraction_lock:
        if not _extraction_worker_started:
            worker = threading.Thread(target=_extraction_worker_loop, daemon=True)
            worker.start()
            _extraction_worker_started = True


def enqueue_extraction_job(call_record_id: Union[str]) -> None:
    """
    Enqueue an extraction job for a given CallRecord ID.

    - Safe to call from webhooks or background tasks.
    - Deduplicates jobs so the same call isn't processed multiple times concurrently.
    """
    _ensure_extraction_worker_started()
    with _extraction_lock:
        key = str(call_record_id)
        if key in _extraction_in_flight:
            # Already queued or running
            return
        _extraction_in_flight.add(key)
        _extraction_queue.put(key)


def trigger_background_extraction(property_manager_id: Optional[int] = None):
    """
    Background task to extract intel from all pending call records.
    This is called automatically on login to pre-extract data.
    
    Args:
        property_manager_id: Optional PM ID to filter calls
    """
    print(f"\n{'='*80}")
    print(f"🚀 BACKGROUND EXTRACTION TASK STARTED")
    print(f"{'='*80}")
    
    with Session(engine) as session:
        # Get all call records that need extraction
        query = select(CallRecord).where(
            CallRecord.transcript.isnot(None),
            or_(
                CallRecord.extraction_status.is_(None),
                CallRecord.extraction_status == "pending",
                CallRecord.extraction_status == "failed"
            )
        )
        
        if property_manager_id:
            # Filter by PM's phone numbers if needed
            pm_numbers = session.exec(
                select(PurchasedPhoneNumber.phone_number)
                .where(PurchasedPhoneNumber.property_manager_id == property_manager_id)
            ).all()
            if pm_numbers:
                query = query.where(CallRecord.realtor_number.in_(pm_numbers))
        
        pending_calls = session.exec(
            query.order_by(CallRecord.created_at.desc()).limit(100)  # Process up to 100 at a time
        ).all()
        
        print(f"   Found {len(pending_calls)} call records needing extraction")
        
        if len(pending_calls) == 0:
            print(f"   ✅ No pending extractions")
            return
        
        # Instead of running extraction synchronously here (which adds latency),
        # enqueue jobs for the async extraction worker.
        enqueued = 0
        for cr in pending_calls:
            enqueue_extraction_job(str(cr.id))
            enqueued += 1
        
        print(f"   ✅ Background extraction: enqueued {enqueued} jobs for async worker")
    
    print(f"{'='*80}\n")


def extract_contact_intel_from_transcript(transcript: Optional[str]) -> Dict[str, Optional[str]]:
    """
    Extract **caller email first**, then infer name, plus last-call purpose and property/address.

    EXTRACTION STRATEGY:
    - GEMINI AI ONLY - Uses Gemini API for accurate extraction
    - If Gemini fails or is unavailable, returns empty/null values
    
    We prioritize accuracy - using only AI extraction to avoid mistakes.

    Returns:
        {
          "email": str|None,
          "inferred_name": str|None,
          "region": str|None,
          "inquiry_property": str|None,
          "inquiry_purpose": str|None,
          "inquiry_summary": str|None,
        }
    """
    import re
    
    print(f"\n🚀 extract_contact_intel_from_transcript() CALLED")
    print(f"   Transcript provided: {transcript is not None}")
    if transcript:
        print(f"   Transcript length: {len(transcript)} chars")

    if not transcript or not transcript.strip():
        print(f"   ⚠️  Empty transcript - returning empty result")
        return {
            "email": None,
            "inferred_name": None,
            "region": None,
            "inquiry_property": None,
            "inquiry_purpose": None,
            "inquiry_summary": None,
            "call_summary": None,
        }

    # Ensure Gemini sees conversation only (strip any appended summary)
    transcript = _strip_appended_summary(transcript)
    parts = _split_transcript(transcript)
    user_text = parts["user"] or parts["all"]
    all_text = parts["all"]

    # Initialize all fields
    email: Optional[str] = None
    inferred_name: Optional[str] = None
    inquiry_property: Optional[str] = None
    inquiry_purpose: Optional[str] = None
    region: Optional[str] = None
    ai_success = False

    # ============================================================================
    # STEP 1: GEMINI AI EXTRACTION (PRIMARY - MUST TRY FIRST)
    # ============================================================================
    print(f"\n{'='*80}")
    print(f"🔍 GEMINI AI EXTRACTION - STARTING")
    print(f"{'='*80}")
    print(f"Transcript length: {len(transcript)} chars")
    print(f"Transcript preview (first 500 chars):\n{transcript[:500]}\n...")
    
    try:
        ai_client = get_vertex_ai_client()
        print(f"AI Client available: {ai_client is not None}")
        if ai_client:
            print(f"AI Client is_available(): {ai_client.is_available()}")
            print(f"AI Client use_vertex_ai: {getattr(ai_client, 'use_vertex_ai', 'N/A')}")
        
        if ai_client and ai_client.is_available():
            print(f"✅ Gemini AI client is available - proceeding with extraction")
            
            # ========================================================================
            # 3-LAYER EXTRACTION SYSTEM (Token Optimization)
            # ========================================================================
            
            # Layer 1: Pre-processor - Remove logs, debug, system messages
            preprocessed = _preprocess_transcript_layer1(transcript)
            print(f"📄 Layer 1 (Pre-processor): {len(transcript)} → {len(preprocessed)} chars ({100*(1-len(preprocessed)/max(len(transcript),1)):.1f}% reduction)")
            
            # Layer 2: Condenser - Extract only info-relevant turns (for long calls)
            condensed = _condense_transcript_layer2(preprocessed, max_length=2000)
            print(f"📄 Layer 2 (Condenser): {len(preprocessed)} → {len(condensed)} chars ({100*(1-len(condensed)/max(len(preprocessed),1)):.1f}% reduction)")
            
            # Layer 3: Minimal prompt - Only essential rules and schema
            prompt = _build_minimal_gemini_prompt(condensed)
            
            print(f"\n📤 SENDING OPTIMIZED PROMPT TO GEMINI:")
            print(f"   Original transcript: {len(transcript)} chars")
            print(f"   Final prompt: {len(prompt)} chars")
            print(f"   Token reduction: ~{100*(1-len(prompt)/max(len(transcript)*2,1)):.0f}%")
            print(f"   Condensed transcript preview (first 500 chars):\n{condensed[:500]}\n...")
            
            try:
                resp = ai_client.generate_content(prompt).strip()
                print(f"\n📥 GEMINI RESPONSE RECEIVED:")
                print(f"   Response length: {len(resp)} chars")
                print(f"   FULL RESPONSE:\n{resp}")
                print(f"\n{'='*80}")
            except Exception as e:
                print(f"\n❌ ERROR CALLING GEMINI:")
                print(f"   Error type: {type(e).__name__}")
                print(f"   Error message: {str(e)}")
                import traceback
                traceback.print_exc()
                raise
            
            # Extract JSON from response (try multiple methods)
            json_data = None
            
            # Method 1: Find JSON object
            start = resp.find("{")
            end = resp.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    json_str = resp[start:end]
                    json_data = json.loads(json_str)
                    print(f"   ✅ Successfully parsed JSON from response")
                except json.JSONDecodeError as e:
                    print(f"   ⚠️  JSON parse error: {e}")
                    print(f"   JSON string: {json_str[:500]}")
            
            # Method 2: Try parsing entire response as JSON
            if not json_data:
                try:
                    json_data = json.loads(resp)
                    print(f"   ✅ Successfully parsed entire response as JSON")
                except:
                    pass
            
            if json_data:
                print(f"   📊 Extracted data: {json.dumps(json_data, indent=2)}")
                
                # Extract email from AI - also check for email patterns in transcript if null
                ai_email = json_data.get("email")
                if ai_email:
                    ai_email = str(ai_email).strip().lower()
                    # Validate email format
                    if re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", ai_email):
                        email = ai_email
                        print(f"   ✅ Extracted email: {email}")
                    else:
                        print(f"   ⚠️  Invalid email format: {ai_email}")
                
                # POST-PROCESSING: If Gemini returned null for email, try to find it in FULL transcript
                # Use full transcript (not condensed) for post-processing to ensure we don't miss anything
                if not email:
                    # Look for email patterns in the FULL transcript
                    email_patterns_in_transcript = re.findall(
                        r'\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b',
                        transcript,  # Use full transcript, not condensed
                        re.IGNORECASE
                    )
                    if email_patterns_in_transcript:
                        # Use the first valid email found
                        potential_email = email_patterns_in_transcript[0].lower().strip()
                        if re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", potential_email):
                            email = potential_email
                            print(f"   ✅ Found email in transcript post-processing: {email}")
                    
                    # Also look for spoken email patterns
                    if not email:
                        spoken_email_patterns = [
                            r'(\w+)\s+at\s+(\w+)\s+dot\s+(\w+)',  # "john at gmail dot com"
                            r'(\w+)\s+@\s+(\w+)\s+\.\s+(\w+)',  # "john @ gmail . com"
                        ]
                        for pattern in spoken_email_patterns:
                            matches = re.findall(pattern, transcript, re.IGNORECASE)  # Use full transcript
                            if matches:
                                for match in matches:
                                    if len(match) == 3:
                                        potential_email = f"{match[0]}@{match[1]}.{match[2]}".lower()
                                        if re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", potential_email):
                                            email = potential_email
                                            print(f"   ✅ Found spoken email in transcript: {email}")
                                            break
                                if email:
                                    break
                
                # Extract customer name from AI (check BOTH customer_name AND inferred_name fields)
                # Try customer_name first, then inferred_name, then infer from email
                ai_customer_name = json_data.get("customer_name") or json_data.get("inferred_name")
                if ai_customer_name:
                    ai_customer_name = str(ai_customer_name).strip()
                    # AGGRESSIVE bot name and verb filtering
                    bad_names = {
                        "riley", "assistant", "bot", "ai", "lease", "leasap", "speaking", 
                        "this is", "hi", "hello", "hey", "yes", "no", "okay", "ok",
                        "riley speaking", "this is riley", "i'm riley", "my name is riley"
                    }
                    # Common verbs that should NOT be extracted as names
                    common_verbs = {
                        "looking", "searching", "asking", "wanting", "trying", "calling", 
                        "needing", "seeking", "finding", "checking", "wondering", "thinking",
                        "preferably", "anyway", "should", "would", "could", "please", 
                        "thanks", "thank", "thanks", "appreciate"
                    }
                    name_lower = ai_customer_name.lower().strip()
                    
                    # Check if it's a bot name or a verb
                    is_bot_name = (
                        name_lower in bad_names or 
                        name_lower in common_verbs or
                        "riley" in name_lower or 
                        name_lower.startswith("riley") or
                        len(ai_customer_name) < 2
                    )
                    
                    # Use centralized bad name detection
                    if not _is_bad_person_name(ai_customer_name):
                        inferred_name = ai_customer_name
                        print(f"   ✅ Extracted name: {inferred_name}")
                    else:
                        print(f"   ❌ Rejected bad name (verb/filler): '{ai_customer_name}'")
                        inferred_name = None
                
                # Fallback to email inference if AI didn't find name but found email
                # ALWAYS try to infer name from email - be aggressive
                if not inferred_name and email:
                    inferred_name = _infer_name_from_email(email)
                    if inferred_name:
                        print(f"   ✅ Inferred name from email: {inferred_name}")
                    else:
                        # Even if _infer_name_from_email returns None, try a more aggressive approach
                        # Extract any letters from email username
                        email_local = email.split("@")[0] if "@" in email else ""
                        if email_local:
                            # Try to extract meaningful name parts
                            import re
                            # Find all letter sequences
                            letter_parts = re.findall(r"[a-zA-Z]+", email_local)
                            if letter_parts:
                                # Use the longest letter sequence as potential name
                                longest_part = max(letter_parts, key=len)
                                if len(longest_part) >= 2:
                                    inferred_name = longest_part[:1].upper() + longest_part[1:].lower()
                                    print(f"   ✅ Aggressively inferred name from email: {inferred_name} (from '{email_local}')")
                
                # POST-PROCESSING: If Gemini returned null for name, try to find it in FULL transcript
                # Use full transcript (not condensed) for post-processing to ensure we don't miss anything
                if not inferred_name:
                    # Look for name patterns in the FULL transcript
                    name_patterns_in_transcript = [
                        r'(?:my name is|I\'m|I am|this is|call me|name\'s|I go by)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
                        r'(?:Hi|Hello),?\s+([A-Z][a-z]+)',
                        r'Thank you,?\s+([A-Z][a-z]+)',
                        r'Hello,?\s+([A-Z][a-z]+)',
                    ]
                    for pattern in name_patterns_in_transcript:
                        matches = re.findall(pattern, transcript, re.IGNORECASE)  # Use full transcript
                        if matches:
                            for match in matches:
                                potential_name = match.strip() if isinstance(match, str) else match[0].strip() if match else None
                                if potential_name:
                                    potential_name_lower = potential_name.lower()
                                    # Reject bot names and common verbs
                                    bad_names = {"riley", "assistant", "bot", "ai", "lease", "leasap"}
                                    common_verbs = {
                                        "looking", "searching", "asking", "wanting", "trying", "calling",
                                        "needing", "seeking", "finding", "checking", "wondering", "thinking",
                                        "preferably", "anyway", "should", "would", "could", "please"
                                    }
                                    # Use centralized bad name detection
                                    if not _is_bad_person_name(potential_name) and len(potential_name) >= 2:
                                        # Take first name if full name
                                        first_name = potential_name.split()[0] if " " in potential_name else potential_name
                                        inferred_name = first_name[:1].upper() + first_name[1:].lower()
                                        print(f"   ✅ Found name in transcript post-processing: {inferred_name}")
                                        break
                            if inferred_name:
                                break
                
                # Extract property (with SMART validation - very lenient)
                ai_property = json_data.get("inquiry_property")
                if ai_property:
                    ai_property = str(ai_property).strip()
                    # SMART validation - reject bot text but accept partial addresses
                    bot_patterns = [
                        "searches", "visits booking", "general apartment inquiries",
                        "apartment searches visits", "how can i assist", "searches, visits",
                        "apartment searches", "or general", "visits booking", "general inquiries",
                        "apartment", "inquiries"  # Reject if it's just these words
                    ]
                    property_lower = ai_property.lower()
                    
                    # Check if it's bot text
                    is_bot_text = any(pattern in property_lower for pattern in bot_patterns)
                    
                    # Very lenient validation:
                    # - Must not be bot text
                    # - Must be at least 8 characters (very lenient)
                    # - Should contain letters (not just numbers/punctuation)
                    has_letters = re.search(r"[a-zA-Z]", ai_property)
                    is_substantial = len(ai_property) >= 8  # Very lenient - just 8 chars
                    
                    # Also check if it looks like a real address (has street name, city, etc.)
                    looks_like_address = (
                        any(word in property_lower for word in ["road", "street", "st", "ave", "avenue", "drive", "dr", "lane", "ln", "way", "blvd", "boulevard"]) or
                        any(word in property_lower for word in ["santa", "san", "sunnyvale", "california", "ca", "fremont", "palo", "mountain"]) or
                        re.search(r"\d+", ai_property)  # Has a number (street number)
                    )
                    
                    if not is_bot_text and is_substantial and has_letters:
                        # Accept if it meets basic criteria OR looks like an address
                        if looks_like_address or len(ai_property) >= 10:
                            inquiry_property = ai_property
                            print(f"   ✅ Extracted property: {inquiry_property}")
                        else:
                            print(f"   ⚠️  Property seems short but accepting: '{ai_property}'")
                            inquiry_property = ai_property  # Accept anyway - be aggressive
                    else:
                        print(f"   ❌ Rejected invalid property: '{ai_property}' (is_bot={is_bot_text}, substantial={is_substantial}, has_letters={bool(has_letters)})")
                
                # Extract purpose (with validation)
                ai_purpose = json_data.get("inquiry_purpose")
                if ai_purpose:
                    ai_purpose = str(ai_purpose).strip()
                    # Validate it's not bot text
                    bot_phrases = [
                        "searches", "visits booking", "general apartment inquiries",
                        "apartment searches visits", "how can i assist", "searches, visits"
                    ]
                    if not any(phrase in ai_purpose.lower() for phrase in bot_phrases):
                        inquiry_purpose = ai_purpose
                        print(f"   ✅ Extracted purpose: {inquiry_purpose}")
                    else:
                        print(f"   ❌ Rejected bot purpose: '{ai_purpose}'")

                # Fallback purpose: if Gemini returns "general information" but the user is clearly searching,
                # normalize to a more useful purpose.
                # Use full transcript (not condensed) for fallback extraction
                if (not inquiry_purpose) or (isinstance(inquiry_purpose, str) and inquiry_purpose.strip().lower() == "general information"):
                    t = transcript.lower()  # Use full transcript
                    if ("apart" in t and ("looking for" in t or "search" in t or "find" in t or "availability" in t or "beds" in t or "baths" in t or "$" in t or "dollars" in t)):
                        inquiry_purpose = "availability inquiry"
                        print(f"   ✅ Fallback purpose inferred from transcript: {inquiry_purpose}")
                
                # Extract region (with validation) - also try to extract from property if not found
                ai_region = json_data.get("region")
                if ai_region:
                    ai_region = str(ai_region).strip()
                    # Validate region - should be a location name
                    # Reject if it's too short or looks like bot text
                    if len(ai_region) >= 2 and not any(bad in ai_region.lower() for bad in ["riley", "assistant", "bot", "ai"]):
                        region = ai_region
                        print(f"   ✅ Extracted region: {region}")
                    else:
                        print(f"   ❌ Rejected invalid region: '{ai_region}'")

                # Fallback property extraction: grab the strongest "located at ..." address if Gemini missed it.
                # Use full transcript (not condensed) for fallback extraction
                if not inquiry_property:
                    m = re.search(r"(?i)\b(?:it's\s+)?located at\s+(.+?)(?:\.\s|\.?$|\n)", transcript)  # Use full transcript
                    if m:
                        candidate_addr = m.group(1).strip()
                        if candidate_addr and len(candidate_addr) >= 8:
                            inquiry_property = candidate_addr
                            print(f"   ✅ Fallback property extracted from transcript: {inquiry_property}")
                
                # Fallback: Extract region from property address if not found
                if not region and inquiry_property:
                    # Look for city/state patterns in property address
                    import re
                    # Common patterns: "City, State", "City State", "City, ST"
                    city_state_patterns = [
                        r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",  # "Santa Clara, California"
                        r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+([A-Z][a-z]+)",  # "Santa Clara California"
                        r",\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)$",  # ", California" at end
                    ]
                    for pattern in city_state_patterns:
                        match = re.search(pattern, inquiry_property)
                        if match:
                            if len(match.groups()) == 2:
                                # City and state
                                region = f"{match.group(1)}, {match.group(2)}"
                            else:
                                # Just state
                                region = match.group(1)
                            print(f"   ✅ Extracted region from property address: {region}")
                            break

                # Fallback region: if user said city/state but we still have none, try to build "City, State"
                if not region:
                    city = None
                    state = None
                    # Use full transcript (not condensed) for region extraction
                    m_city = re.search(r"(?i)\bapart(?:ment)?s?\s+in\s+([A-Z][a-z]+)\b", transcript)  # Use full transcript
                    if m_city:
                        city = m_city.group(1).strip()
                    m_state = re.search(r"(?m)^User:\s*([A-Z][a-z]{2,})\s*\.?\s*$", transcript)  # Use full transcript
                    if m_state:
                        state = m_state.group(1).strip()
                    if city and state:
                        region = f"{city}, {state}"
                        print(f"   ✅ Fallback region built from user lines: {region}")
                    elif state:
                        region = state
                        print(f"   ✅ Fallback region from user line: {region}")
                
                # Final sanity check on inferred_name before we mark success
                # This is CRITICAL - reject any bad names that slipped through
                if inferred_name and _is_bad_person_name(inferred_name):
                    print(f"   ❌ REJECTING bad inferred_name at finalization: '{inferred_name}' (this is a verb/filler word, not a name)")
                    inferred_name = None

                ai_success = True
                print(f"\n✅ GEMINI AI EXTRACTION COMPLETE:")
                print(f"   - Email: {email or 'None'}")
                print(f"   - Name: {inferred_name or 'None'}")
                print(f"   - Property: {inquiry_property or 'None'}")
                print(f"   - Purpose: {inquiry_purpose or 'None'}")
                print(f"   - Region: {region or 'None'}")
                
                # Check if we got null for critical fields
                has_email_or_name = bool(email or inferred_name)
                has_any_data = bool(email or inferred_name or inquiry_property or inquiry_purpose)
                
                if not has_email_or_name:
                    print(f"   ⚠️  WARNING: No email or name extracted from this transcript")
                    if has_any_data:
                        print(f"   ℹ️  But we did find inquiry context (property/purpose) - will continue searching for email/name")
                    else:
                        print(f"   ❌ No useful data extracted - this call transcript may not contain customer info")
                else:
                    print(f"   ✅ Successfully extracted email or name!")
                
                print(f"{'='*80}\n")
            else:
                print(f"\n❌ FAILED TO EXTRACT JSON FROM GEMINI RESPONSE")
                print(f"   Full response received:\n{resp}")
                print(f"   Response type: {type(resp)}")
                print(f"   Response length: {len(resp)}")
                print(f"{'='*80}\n")
                ai_success = False
        else:
            print(f"\n⚠️  AI CLIENT NOT AVAILABLE")
            if not ai_client:
                print(f"   Reason: ai_client is None")
            elif not ai_client.is_available():
                print(f"   Reason: ai_client.is_available() returned False")
            print(f"   Extraction will return empty values")
            print(f"{'='*80}\n")
            ai_success = False
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        print(f"\n❌ GEMINI AI EXTRACTION FAILED WITH EXCEPTION:")
        print(f"   Error type: {error_type}")
        print(f"   Error message: {error_msg}")
        
        # Provide helpful guidance for common errors
        if "PermissionDenied" in error_type or "403" in error_msg or "leaked" in error_msg.lower():
            print(f"\n   🔑 ACTION REQUIRED: API Key Issue")
            print(f"   Your Gemini API key has been flagged. Please:")
            print(f"   1. Generate a new API key: https://aistudio.google.com/app/apikey")
            print(f"   2. Update GEMINI_API_KEY in your deployment environment variables")
            print(f"   3. Redeploy your backend")
            print(f"   Extraction will return empty values until API key is fixed.")
        elif "NotFound" in error_type or "404" in error_msg:
            print(f"\n   📦 Model not available - extraction will return empty values.")
        else:
            print(f"\n   Extraction will return empty values due to error.")
        
        import traceback
        traceback.print_exc()
        print(f"{'='*80}\n")
        ai_success = False

    # ============================================================================
    # NO FALLBACK - Only use Gemini AI extraction
    # ============================================================================
    if not ai_success:
        print("⚠️  Gemini AI extraction failed - returning empty values")

    # Extract summary from transcript (if present)
    # Summaries are often at the end of transcripts with markers like "Summary:", "---", etc.
    call_summary: Optional[str] = None
    if transcript:
        # Look for summary markers
        summary_markers = [
            "Summary:",
            "---\nSummary:",
            "Call Summary:",
            "Summary",
            "=== Summary ===",
            "SUMMARY:"
        ]
        transcript_lower = transcript.lower()
        for marker in summary_markers:
            marker_lower = marker.lower()
            if marker_lower in transcript_lower:
                # Extract text after the marker
                marker_index = transcript_lower.find(marker_lower)
                if marker_index >= 0:
                    summary_start = marker_index + len(marker)
                    summary_text = transcript[summary_start:].strip()
                    # Take up to 500 chars or until next section
                    if summary_text:
                        # Stop at common section markers
                        for stop_marker in ["\n---", "\n===", "\nNotes:", "\nTranscript:", "\n\n\n"]:
                            stop_index = summary_text.find(stop_marker)
                            if stop_index > 0:
                                summary_text = summary_text[:stop_index].strip()
                        call_summary = summary_text[:500].strip() if summary_text else None
                        if call_summary:
                            print(f"   ✅ Extracted call summary: {call_summary[:100]}...")
                            break
    
    # Build inquiry summary (structured summary of extracted fields)
    # Include ALL available fields for comprehensive overview
    summary_parts = []
    if inquiry_purpose:
        summary_parts.append(f"Purpose: {inquiry_purpose}")
    if inquiry_property:
        summary_parts.append(f"Property: {inquiry_property}")
    if inferred_name:
        summary_parts.append(f"Name: {inferred_name}")
    if email:
        summary_parts.append(f"Email: {email}")
    if region:
        summary_parts.append(f"Region: {region}")
    inquiry_summary = " | ".join(summary_parts) if summary_parts else None
    
    if inquiry_summary:
        print(f"   ✅ Built inquiry_summary: {inquiry_summary}")
    else:
        print(f"   ⚠️  No inquiry_summary - no fields to summarize")

    return {
        "email": email,
        "inferred_name": inferred_name,
        "region": region,
        "inquiry_property": inquiry_property,
        "inquiry_purpose": inquiry_purpose,
        "inquiry_summary": inquiry_summary,
        "call_summary": call_summary,  # Full summary from transcript if available
    }


# ============================================================================
# CANDIDATE IDENTIFICATION
# ============================================================================

def identify_follow_up_candidates(session: Session, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Identify ALL unique contacts who have called Leasap (inbound or outbound).
    
    This creates a comprehensive candidate pool for outbound calling.
    In testing mode, shows ALL contacts regardless of:
    - Booking status
    - Opt-out status
    - Call attempt count
    - Cooldown period
    
    Args:
        session: Database session
        limit: Maximum number of candidates to return (0 = no limit)
    
    Returns:
        List of candidate contacts with metadata
    """
    # Get ALL calls (inbound and outbound) to find unique phone numbers
    # This ensures we capture everyone who has interacted with Leasap
    from sqlalchemy import or_, func
    
    # Get all calls with caller numbers (both inbound and outbound)
    # For inbound: caller_number is the person who called
    # For outbound: caller_number is the person we called
    all_calls = session.exec(
        select(CallRecord)
        .where(CallRecord.caller_number.isnot(None))
        .order_by(CallRecord.created_at.desc())
    ).all()
    
    candidates = []
    seen_phones = set()  # Track unique phone numbers
    phone_to_latest_call = {}  # Track the most recent call for each phone
    
    # First pass: collect all unique phone numbers and their latest call info
    for call in all_calls:
        if not call.caller_number:
            continue
        
        try:
            phone = normalize_phone_number(call.caller_number)
        except Exception as e:
            # Skip calls with invalid phone numbers
            print(f"⚠️  Skipping call {call.call_id} with invalid phone number {call.caller_number}: {e}")
            continue
        
        # Track unique phones and keep the most recent call info
        if phone not in seen_phones:
            seen_phones.add(phone)
            phone_to_latest_call[phone] = {
                "call": call,
                "call_id": call.call_id,
                "call_at": call.created_at,
                "transcript": call.transcript,
                "direction": call.call_direction or "inbound"  # Default to inbound for legacy
            }
        else:
            # Update if this call is more recent
            existing_call_time = phone_to_latest_call[phone]["call_at"]
            if call.created_at > existing_call_time:
                phone_to_latest_call[phone] = {
                    "call": call,
                    "call_id": call.call_id,
                    "call_at": call.created_at,
                    "transcript": call.transcript,
                    "direction": call.call_direction or "inbound"
                }
    
    # Second pass: get or create contacts and extract intel (with parallelization)
    # Use ThreadPoolExecutor for parallel extraction to improve latency
    def process_candidate(phone_and_info):
        """Process a single candidate - can be run in parallel"""
        phone, call_info = phone_and_info
        print(f"\n{'='*80}")
        print(f"🔍 PROCESSING CANDIDATE: {phone}")
        print(f"{'='*80}")
        try:
            with Session(engine) as candidate_session:
                # Get or create contact
                contact = candidate_session.exec(
                    select(Contact).where(Contact.phone_number == phone)
                ).first()
                
                if not contact:
                    # Create contact with consent from previous call
                    try:
                        print(f"   📝 Creating new contact for {phone}...")
                        contact = get_or_create_contact(
                            phone,
                            candidate_session,
                            timezone="America/New_York"  # Default, can be updated
                        )
                        # Record consent from previous call
                        record_consent(phone, candidate_session, source="call")
                        candidate_session.commit()
                        print(f"   ✅ Created contact ID: {contact.id}")
                    except Exception as e:
                        print(f"   ⚠️  Error creating contact for {phone}: {e}")
                        return None  # Skip this candidate
                else:
                    print(f"   ✅ Found existing contact ID: {contact.id}")
                    print(f"      - Current name: {contact.name}")
                    print(f"      - Current email: {contact.email}")
                
                # BEST-RECENT STRATEGY:
                # Use the MOST RECENT call first; if fields are missing, backfill from older calls.
                print(f"   🔍 Building best-recent extracted context for {phone} (most recent call first)...")
                extracted_info = get_best_recent_intel_for_phone(
                    session=candidate_session,
                    phone=phone,
                    max_calls=10,
                    force_re_extract=False,
                )
                
                # ALWAYS rebuild inquiry_summary from the final merged data.
                # Otherwise you can end up with stale partial summaries like "Purpose: booking a tour"
                # even after we backfill email/name from an older call.
                summary_parts = []
                if extracted_info.get("inquiry_purpose"):
                    summary_parts.append(f"Purpose: {extracted_info['inquiry_purpose']}")
                if extracted_info.get("inquiry_property"):
                    summary_parts.append(f"Property: {extracted_info['inquiry_property']}")
                if extracted_info.get("inferred_name"):
                    summary_parts.append(f"Name: {extracted_info['inferred_name']}")
                if extracted_info.get("email"):
                    summary_parts.append(f"Email: {extracted_info['email']}")
                if extracted_info.get("region"):
                    summary_parts.append(f"Region: {extracted_info['region']}")
                extracted_info["inquiry_summary"] = " | ".join(summary_parts) if summary_parts else None
                if extracted_info["inquiry_summary"]:
                    print(f"   ✅ Rebuilt inquiry_summary from merged data: {extracted_info['inquiry_summary']}")
                
                print(f"\n   📋 FINAL EXTRACTED INFO SUMMARY:")
                print(f"      - email: {extracted_info.get('email')}")
                print(f"      - inferred_name: {extracted_info.get('inferred_name')}")
                print(f"      - inquiry_property: {extracted_info.get('inquiry_property')}")
                print(f"      - inquiry_purpose: {extracted_info.get('inquiry_purpose')}")
                print(f"      - region: {extracted_info.get('region')}")
                print(f"      - inquiry_summary: {extracted_info.get('inquiry_summary')}")
                print(f"      - call_summary: {extracted_info.get('call_summary')[:100] if extracted_info.get('call_summary') else None}...")
                
                # Update contact with extracted data
                print(f"\n   💾 UPDATING CONTACT WITH EXTRACTED DATA:")
                print(f"      - Current contact.email: {contact.email}")
                print(f"      - Current contact.name: {contact.name}")
                print(f"      - Extracted email: {extracted_info.get('email')}")
                print(f"      - Extracted inferred_name: {extracted_info.get('inferred_name')}")
                
                if extracted_info.get("email") or extracted_info.get("inferred_name"):
                    updated = False
                    if extracted_info.get("email") and not contact.email:
                        print(f"      ✅ Updating contact.email: {contact.email} → {extracted_info['email']}")
                        contact.email = extracted_info["email"]
                        candidate_session.add(contact)
                        updated = True
                    elif extracted_info.get("email"):
                        print(f"      ⏭️  Skipping email update - contact already has email: {contact.email}")
                    
                    if extracted_info.get("inferred_name"):
                        proposed = extracted_info["inferred_name"]
                        if not _is_bad_person_name(proposed):
                            # Update if current name missing OR current name is also bad (e.g., "Looking")
                            if _is_bad_person_name(contact.name):
                                print(f"      ✅ Updating contact.name: {contact.name} → {proposed}")
                                contact.name = proposed
                                candidate_session.add(contact)
                                updated = True
                            else:
                                print(f"      ⏭️  Skipping name update - contact already has good name: {contact.name}")
                        else:
                            print(f"      ⏭️  Skipping name update - inferred name is bad: {proposed}")
                    
                    if updated:
                        try:
                            candidate_session.commit()
                            print(f"      ✅ Contact updated successfully in database")
                        except Exception as e:
                            candidate_session.rollback()
                            print(f"      ❌ Error committing contact update: {e}")
                    else:
                        print(f"      ⏭️  No contact updates needed")
                else:
                    print(f"      ⏭️  No email or name to update contact with")
                
                # Eagerly access all needed attributes to load them into object state
                # This prevents DetachedInstanceError when object is used in different session
                print(f"\n   🔄 Loading contact attributes for return...")
                contact_id = contact.id
                phone_number = contact.phone_number
                name = contact.name
                email = contact.email
                timezone = contact.timezone
                consent_status = contact.consent_status
                opted_out = contact.opted_out
                call_attempt_count = contact.call_attempt_count
                last_called_at = contact.last_called_at
                last_call_outcome = getattr(contact, "last_call_outcome", None)
                last_booking_at = getattr(contact, "last_booking_at", None)
                
                # Refresh to ensure all attributes are loaded
                candidate_session.refresh(contact)
                
                result = {
                    "contact_id": contact_id,  # Return ID for reloading in main session
                    "last_call_id": call_info["call_id"],
                    "last_call_at": call_info["call_at"],
                    "call_transcript": call_info.get("transcript"),
                    "call_direction": call_info["direction"],
                    "extracted_email": extracted_info.get("email"),
                    "inferred_name": extracted_info.get("inferred_name"),
                    "extracted_region": extracted_info.get("region"),
                    "inquiry_property": extracted_info.get("inquiry_property"),
                    "inquiry_purpose": extracted_info.get("inquiry_purpose"),
                    "inquiry_summary": extracted_info.get("inquiry_summary"),
                    "call_summary": extracted_info.get("call_summary"),
                }
                
                print(f"\n   📤 RETURNING RESULT:")
                print(f"      - contact_id: {result['contact_id']}")
                print(f"      - extracted_email: {result['extracted_email']}")
                print(f"      - inferred_name: {result['inferred_name']}")
                print(f"      - inquiry_purpose: {result['inquiry_purpose']}")
                print(f"      - inquiry_property: {result['inquiry_property']}")
                print(f"{'='*80}\n")
                
                return result
        except Exception as e:
            print(f"⚠️  Error processing candidate {phone}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    # Process candidates in parallel (max 10 workers to avoid overwhelming Gemini API)
    max_workers = min(10, len(phone_to_latest_call))
    candidates = []
    
    if max_workers > 1 and len(phone_to_latest_call) > 1:
        print(f"🚀 Processing {len(phone_to_latest_call)} candidates in parallel (max {max_workers} workers)...")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_phone = {
                executor.submit(process_candidate, (phone, info)): phone 
                for phone, info in phone_to_latest_call.items()
            }
            
            for future in as_completed(future_to_phone):
                phone = future_to_phone[future]
                try:
                    result = future.result()
                    if result:
                        candidates.append(result)
                        # Apply limit if specified
                        if limit > 0 and len(candidates) >= limit:
                            # Cancel remaining futures
                            for f in future_to_phone:
                                f.cancel()
                            break
                except Exception as e:
                    print(f"⚠️  Error processing candidate {phone}: {e}")
    else:
        # Sequential processing for small batches
        print(f"📋 Processing {len(phone_to_latest_call)} candidates sequentially...")
        for phone, call_info in phone_to_latest_call.items():
            result = process_candidate((phone, call_info))
            if result:
                candidates.append(result)
                if limit > 0 and len(candidates) >= limit:
                    break
    
    print(f"✅ Found {len(candidates)} unique candidate contacts from {len(seen_phones)} unique phone numbers")
    return candidates


# ============================================================================
# VAPI CALL TRIGGERING
# ============================================================================

def get_pm_twilio_number(property_manager_id: int, session: Session) -> Optional[str]:
    """
    Get the Property Manager's assigned Twilio phone number.
    
    Checks in order:
    1. Purchased phone number (via purchased_phone_number_id)
    2. Direct twilio_contact (if not "TBD")
    
    Args:
        property_manager_id: Property Manager ID
        session: Database session
    
    Returns:
        Twilio phone number in E.164 format, or None if not found
    """
    pm = session.get(PropertyManager, property_manager_id)
    if not pm:
        return None
    
    # First, try purchased phone number
    if pm.purchased_phone_number_id:
        purchased = session.get(PurchasedPhoneNumber, pm.purchased_phone_number_id)
        if purchased and purchased.phone_number:
            return normalize_phone_number(purchased.phone_number)
    
    # Fall back to direct twilio_contact (if not "TBD")
    if pm.twilio_contact and pm.twilio_contact.upper() != "TBD":
        return normalize_phone_number(pm.twilio_contact)
    
    return None


def trigger_outbound_call(
    contact: Contact,
    assistant_id: Optional[str] = None,
    from_number: Optional[str] = None,
    property_manager_id: Optional[int] = None,
    session: Session = None,
    metadata: Optional[Dict[str, Any]] = None,
    bypass_eligibility: bool = False  # For vendor calls and urgent maintenance requests
) -> Dict[str, Any]:
    """
    Trigger an outbound call via Vapi API.
    
    This is the ONLY place where outbound calls are initiated.
    Eligibility must be checked BEFORE calling this function.
    
    Args:
        contact: Contact to call
        assistant_id: VAPI assistant ID (defaults to VAPI_ASSISTANT_ID)
        from_number: Twilio number to call from (optional)
        session: Database session (optional, will create if not provided)
        metadata: Additional metadata to pass to Vapi
    
    Returns:
        {
            "success": bool,
            "call_id": str,  # VAPI call ID if successful
            "error": str,  # Error message if failed
            "contact_id": int
        }
    """
    # Track if we created the session (need to close it on error)
    session_created = False
    if not session:
        session = Session(engine)
        session_created = True
    
    print(f"🔍 [OUTBOUND CALLING] trigger_outbound_call called:")
    print(f"   Contact ID: {contact.id}, Phone: {contact.phone_number}")
    print(f"   Assistant ID provided: {assistant_id}")
    print(f"   Property Manager ID: {property_manager_id}")
    print(f"   From Number provided: {from_number}")
    print(f"   Bypass Eligibility: {bypass_eligibility}")
    print(f"   Metadata vendorCall: {metadata.get('vendorCall') if metadata else None}")
    
    # Get outbound assistant ID from property manager if not provided
    if not assistant_id and property_manager_id:
        try:
            pm = session.get(PropertyManager, property_manager_id)
            if pm:
                # Check metadata to determine call type (backup logic if assistant_id not passed explicitly)
                is_vendor_call = metadata and metadata.get("vendorCall") == True
                
                if is_vendor_call:
                    # Prefer vendor calling assistant
                    assistant_id = pm.vapi_vendor_calling_assistant_id
                    if not assistant_id:
                        print(f"⚠️  No vendor calling assistant configured for PM {property_manager_id}, falling back to outbound assistant")
                        assistant_id = pm.vapi_outbound_assistant_id
                    else:
                        print(f"✅ Using vendor calling assistant ID from PropertyManager {property_manager_id}: {assistant_id}")
                else:
                    # Customer re-engagement call
                    assistant_id = pm.vapi_outbound_assistant_id
                    if assistant_id:
                        print(f"✅ Using outbound assistant ID from PropertyManager {property_manager_id}: {assistant_id}")
                    else:
                        print(f"⚠️  PropertyManager {property_manager_id} has no vapi_outbound_assistant_id configured")
            else:
                print(f"⚠️  PropertyManager {property_manager_id} not found")
        except Exception as e:
            print(f"⚠️  Error loading PropertyManager {property_manager_id}: {e}")
    
    # Fallback to environment variable if still not set
    if not assistant_id:
        assistant_id = VAPI_ASSISTANT_ID
        if assistant_id:
            print(f"⚠️  Using fallback VAPI_ASSISTANT_ID from environment (should use PM's outbound assistant ID)")
    
    if not assistant_id:
        error_msg = "No VAPI outbound assistant ID configured. Please set vapi_outbound_assistant_id for the PropertyManager or set VAPI_ASSISTANT_ID environment variable."
        print(f"❌ [OUTBOUND CALLING] {error_msg}")
        return {
            "success": False,
            "error": error_msg,
            "contact_id": contact.id
        }
    
    # Validate Twilio credentials
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        error_msg = "Twilio credentials not configured (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN required)"
        print(f"❌ [OUTBOUND CALLING] {error_msg}")
        return {
            "success": False,
            "error": error_msg,
            "contact_id": contact.id
        }
    
    # Use provided from_number, or get PM's assigned Twilio number, or fall back to environment default
    # For outbound calls, we need a Twilio number to call FROM
    if not from_number:
        # Try to get PM's assigned number
        if property_manager_id:
            from_number = get_pm_twilio_number(property_manager_id, session)
        
        # Fall back to environment default if still not found
        if not from_number:
            from_number = DEFAULT_TWILIO_FROM_NUMBER
    
    if not from_number:
        error_msg = "from_number is required for outbound calls."
        if property_manager_id:
            error_msg += f" Property Manager {property_manager_id} does not have an assigned Twilio number."
        error_msg += " Provide it in the API call, assign a number to the PM, or set DEFAULT_TWILIO_FROM_NUMBER in environment (Twilio phone number in E.164 format, e.g., '+14125551234')"
        print(f"❌ [OUTBOUND CALLING] {error_msg}")
        return {
            "success": False,
            "error": error_msg,
            "contact_id": contact.id
        }
    
    print(f"✅ [OUTBOUND CALLING] All prerequisites met:")
    print(f"   Assistant ID: {assistant_id}")
    print(f"   From Number: {from_number}")
    print(f"   To Number: {contact.phone_number}")
    print(f"   Proceeding to make VAPI API call...")
    
    # Load extracted intelligence from latest call for this contact
    # This provides context for personalized re-engagement
    extracted_intel = None
    context_message = None
    
    try:
        # Get the most recent call record with extracted intelligence
        latest_call = session.exec(
            select(CallRecord)
            .where(CallRecord.caller_number == contact.phone_number)
            .where(CallRecord.extracted_intel.isnot(None))
            .where(CallRecord.extraction_status == "completed")
            .order_by(CallRecord.created_at.desc())
        ).first()
        
        if latest_call and latest_call.extracted_intel:
            extracted_intel = latest_call.extracted_intel
            print(f"📋 Loaded extracted intelligence for re-engagement:")
            print(f"   - Email: {extracted_intel.get('email')}")
            print(f"   - Name: {extracted_intel.get('inferred_name')}")
            print(f"   - Property: {extracted_intel.get('inquiry_property')}")
            print(f"   - Purpose: {extracted_intel.get('inquiry_purpose')}")
            print(f"   - Region: {extracted_intel.get('region')}")
            
            # Build context message for assistant.messages (RECOMMENDED METHOD)
            # Format: Natural, conversational, no mention of "records", "database", "system"
            # ⚠️ PRIVACY RULE: Do NOT include email in conversational context
            # Email should ONLY be in metadata, not in assistant.messages
            # ✅ Name CAN be included in conversational context (natural to use)
            # Only include non-null fields to avoid confusing Vapi
            context_parts = []
            
            # Add customer name if available (OK to include in context)
            # Filter out null/N/A/empty values
            customer_name = extracted_intel.get("inferred_name") or contact.name
            if _is_valid_value(customer_name):
                context_parts.append(f"The customer's name is {customer_name}.")
            
            # Build a concise, non-repetitive context message
            # Combine property and purpose into one natural sentence
            # Filter out null/N/A/empty values
            property_addr = extracted_intel.get("inquiry_property")
            if not _is_valid_value(property_addr):
                property_addr = None
            
            purpose = extracted_intel.get("inquiry_purpose")
            if not _is_valid_value(purpose):
                purpose = None
            
            region = extracted_intel.get("region")
            if not _is_valid_value(region):
                region = None
            
            # Build main context sentence (property + purpose combined)
            if property_addr and purpose:
                # Combine property and purpose naturally
                if purpose == "booking a tour":
                    context_parts.append(f"When they last reached out, they were interested in booking a tour for {property_addr}.")
                elif purpose == "availability inquiry":
                    context_parts.append(f"They previously asked about availability at {property_addr}.")
                elif purpose == "pricing inquiry":
                    context_parts.append(f"They previously inquired about pricing for {property_addr}.")
                elif purpose == "viewing request":
                    context_parts.append(f"They previously requested a viewing for {property_addr}.")
                else:
                    context_parts.append(f"They previously inquired about {purpose} for {property_addr}.")
            elif property_addr:
                # Only property, no purpose
                context_parts.append(f"When they last reached out, they were asking about {property_addr}.")
            elif purpose:
                # Only purpose, no property
                if purpose == "booking a tour":
                    context_parts.append("They were previously interested in booking a tour.")
                elif purpose == "availability inquiry":
                    context_parts.append("They were previously asking about availability.")
                elif purpose == "pricing inquiry":
                    context_parts.append("They were previously asking about pricing.")
                elif purpose == "viewing request":
                    context_parts.append("They previously requested a viewing.")
                else:
                    context_parts.append(f"They were previously inquiring about {purpose}.")
            
            # Add region only if it's different from property location (avoid repetition)
            if region and property_addr:
                # Check if region is already mentioned in property address
                region_in_property = region.lower() in property_addr.lower()
                if not region_in_property:
                    context_parts.append(f"They were looking in {region}.")
            elif region:
                # Only region, no property
                context_parts.append(f"They were looking in {region}.")
            
            # Build the context message (only if we have useful data)
            if context_parts:
                context_message = " ".join(context_parts)
                # Add instruction for natural usage
                context_message += " Use this information naturally in conversation. Do not mention 'records', 'database', 'system', or 'logs'. Reference it casually, as if you remember the previous conversation."
                print(f"✅ Built context message for assistant (email excluded for privacy, name included):")
                print(f"   {context_message}")
            else:
                print(f"⚠️  No useful context to send (all fields are null)")
        else:
            print(f"ℹ️  No extracted intelligence found for this contact - proceeding without context")
    except Exception as e:
        print(f"⚠️  Error loading extracted intelligence: {e}")
        import traceback
        traceback.print_exc()
        # Continue without context if there's an error
    
    # Prepare Vapi API request with correct structure (following Vapi best practices)
    # Vapi expects: phoneNumber.twilioPhoneNumber, phoneNumber.twilioAccountSid, phoneNumber.twilioAuthToken
    # and customer.number (not phoneNumber.to)
    # Best practice: Include customer.name if available for better personalization
    customer_name = contact.name or (extracted_intel.get("inferred_name") if extracted_intel else None)
    
    # VAPI API endpoint: POST https://api.vapi.ai/call
    # This is the correct endpoint for creating outbound calls
    payload = {
        "assistantId": assistant_id,
        "phoneNumber": {
            "twilioPhoneNumber": from_number,  # Twilio number to call FROM
            "twilioAccountSid": TWILIO_ACCOUNT_SID,
            "twilioAuthToken": TWILIO_AUTH_TOKEN
        },
        "customer": {
            "number": contact.phone_number,  # Recipient's phone number (TO) - E.164 format
        },
        "metadata": {
            "contactId": str(contact.id),
            "campaign": "no_booking_followup" if not (metadata and metadata.get("vendorCall")) else "vendor_maintenance_request",
            "callDirection": "outbound"
        }
    }
    
    # Add customer name if available (best practice: include in customer object)
    # Filter out null/N/A/empty values
    if _is_valid_value(customer_name):
        payload["customer"]["name"] = customer_name
    
    # Add context to metadata (Vapi best practice: use metadata for context)
    # The assistant's system prompt should be configured to read from metadata.callContext
    # Alternative: Use assistantOverrides.variableValues for structured variables
    # Filter out null/N/A/empty values
    if _is_valid_value(context_message):
        payload["metadata"]["callContext"] = context_message
        print(f"📤 Added call context to metadata")
    
    # Also add structured variables via assistantOverrides for easier prompt reference
    # This allows the assistant to use {{customerName}}, {{inquiryProperty}}, etc. in prompts
    # Filter out null/N/A/empty values - only send valid data
    if extracted_intel:
        variable_values = {}
        
        # Only add valid (non-null, non-empty, non-"N/A") values
        if _is_valid_value(customer_name):
            variable_values["customerName"] = customer_name
        
        inquiry_property = extracted_intel.get("inquiry_property")
        if _is_valid_value(inquiry_property):
            variable_values["inquiryProperty"] = inquiry_property
        
        inquiry_purpose = extracted_intel.get("inquiry_purpose")
        if _is_valid_value(inquiry_purpose):
            variable_values["inquiryPurpose"] = inquiry_purpose
        
        customer_region = extracted_intel.get("region")
        if _is_valid_value(customer_region):
            variable_values["customerRegion"] = customer_region
        
        # Only add assistantOverrides if we have at least one valid variable
        if variable_values:
            payload["assistantOverrides"] = {
                "variableValues": variable_values
            }
            print(f"📤 Added structured variables via assistantOverrides: {list(variable_values.keys())}")
        else:
            print(f"⚠️  No valid variables to add (all values were null/empty/N/A)")
    
    # Merge additional metadata (keep for backward compatibility)
    # Filter out null/N/A/empty values from metadata to avoid confusing Vapi
    if metadata:
        payload["metadata"].update(metadata)
        # Filter out null, "N/A", empty strings, etc.
        payload["metadata"] = {
            k: v for k, v in payload["metadata"].items() 
            if _is_valid_value(v)
        }
        print(f"📤 Merged additional metadata (filtered nulls/N/A/empty): {list(payload['metadata'].keys())}")
    
    # Make API call to Vapi
    try:
        headers = {
            "Authorization": f"Bearer {VAPI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Log the full payload being sent to Vapi (for debugging)
        is_vendor_call = metadata and metadata.get("vendorCall") == True
        call_type = "VENDOR CALL" if is_vendor_call else "CUSTOMER RE-ENGAGEMENT"
        print(f"\n📤 SENDING PAYLOAD TO VAPI ({call_type}):")
        print(f"   Assistant ID: {assistant_id}")
        print(f"   From Number: {from_number}")
        print(f"   To Number: {contact.phone_number}")
        if bypass_eligibility:
            print(f"   ⚠️  BYPASSING ELIGIBILITY CHECKS (vendor call or urgent request)")
        if payload.get("metadata", {}).get("callContext"):
            print(f"   ✅ Call context in metadata: {payload['metadata']['callContext'][:200]}...")
        else:
            print(f"   ⚠️  No call context (no extracted intelligence available)")
        print(f"   Metadata keys: {list(payload.get('metadata', {}).keys())}")
        print(f"   Full payload (metadata only): {json.dumps(payload.get('metadata', {}), indent=2)}")
        
        # VAPI API endpoint: POST https://api.vapi.ai/call
        # This is the correct endpoint according to VAPI documentation
        # Endpoint: /call (not /calls)
        # Method: POST
        # Headers: Authorization: Bearer {VAPI_API_KEY}
        api_url = f"{VAPI_BASE_URL}/call"
        print(f"🌐 [OUTBOUND CALLING] Making POST request to: {api_url}")
        
        response = requests.post(
            api_url,
            headers=headers,
            json=payload,
            timeout=30  # Increased timeout for vendor calls
        )
        
        print(f"📥 [OUTBOUND CALLING] VAPI API response status: {response.status_code}")
        
        if response.status_code not in [200, 201]:
            error_msg = response.text
            print(f"❌ [OUTBOUND CALLING] Vapi API error: {response.status_code}")
            print(f"   Error response: {error_msg}")
            print(f"   Request URL: {api_url}")
            print(f"   Request payload keys: {list(payload.keys())}")
            return {
                "success": False,
                "error": f"Vapi API error ({response.status_code}): {error_msg}",
                "contact_id": contact.id,
                "status_code": response.status_code
            }
        
        try:
            result = response.json()
            print(f"✅ [OUTBOUND CALLING] VAPI API call successful")
            print(f"   Response keys: {list(result.keys())}")
        except Exception as e:
            print(f"❌ [OUTBOUND CALLING] Failed to parse VAPI response as JSON: {e}")
            print(f"   Response text: {response.text[:500]}")
            return {
                "success": False,
                "error": f"Invalid JSON response from VAPI: {str(e)}",
                "contact_id": contact.id
            }
        
        call_id = result.get("id") or result.get("callId")
        
        if not call_id:
            print(f"❌ [OUTBOUND CALLING] No call ID in VAPI response")
            print(f"   Response: {json.dumps(result, indent=2)}")
            return {
                "success": False,
                "error": "No call ID returned from Vapi",
                "contact_id": contact.id,
                "response": result
            }
        
        print(f"✅ [OUTBOUND CALLING] Call ID received: {call_id}")
        
        # Create call record with explicit UUID generation
        call_record = CallRecord(
            id=uuid.uuid4(),  # Generate UUID for primary key
            call_id=call_id,
            realtor_number=from_number or "unknown",
            caller_number=contact.phone_number,
            call_direction="outbound",
            contact_id=contact.id,
            assistant_id=assistant_id,
            call_status="initiated",
            call_metadata=payload.get("metadata", {})
        )
        session.add(call_record)
        
        # Update contact call tracking
        contact.call_attempt_count += 1
        contact.last_called_at = datetime.utcnow()
        contact.updated_at = datetime.utcnow()
        session.add(contact)
        
        # Ensure call record is linked to contact
        call_record.contact_id = contact.id
        
        try:
            session.commit()
        except Exception as commit_error:
            # Rollback on commit failure
            session.rollback()
            print(f"❌ Database commit error: {commit_error}")
            import traceback
            traceback.print_exc()
            raise commit_error
        
        print(f"✅ Outbound call triggered: {contact.phone_number} (call_id: {call_id})")
        
        return {
            "success": True,
            "call_id": call_id,
            "contact_id": contact.id
        }
        
    except Exception as e:
        # Ensure session is rolled back on any error
        if session:
            try:
                session.rollback()
            except Exception:
                pass  # Ignore rollback errors
        
        # Close session if we created it
        if session_created and session:
            try:
                session.close()
            except Exception:
                pass  # Ignore close errors
        
        print(f"❌ Error triggering outbound call: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e),
            "contact_id": contact.id if 'contact' in locals() and contact else None
        }


# ============================================================================
# CALL SCHEDULING
# ============================================================================

def process_outbound_call_queue(session: Session, batch_size: int = 10, property_manager_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Process a batch of eligible contacts for outbound calling.
    
    This function:
    1. Identifies follow-up candidates
    2. Checks eligibility for each
    3. Triggers calls for eligible contacts
    
    Args:
        session: Database session
        batch_size: Maximum number of calls to trigger in this batch
    
    Returns:
        {
            "processed": int,
            "called": int,
            "skipped": int,
            "errors": int,
            "results": List[Dict]
        }
    """
    # Get candidates
    candidates = identify_follow_up_candidates(session, limit=batch_size * 2)
    
    results = []
    called = 0
    skipped = 0
    errors = 0
    
    for candidate in candidates:
        contact = candidate["contact"]
        
        # Check eligibility
        eligibility = check_eligibility(contact, session)
        
        # Skip if not eligible (unless bypass is enabled for testing)
        if not eligibility["eligible"]:
            if DISABLE_ELIGIBILITY_CHECKS:
                # Testing mode: allow the call anyway but log the warning
                print(f"⚠️  TESTING MODE: Processing call despite eligibility failure for {contact.phone_number}: {eligibility['reason']}")
            else:
                skipped += 1
                results.append({
                    "contact_id": contact.id,
                    "phone_number": contact.phone_number,
                    "status": "skipped",
                    "reason": eligibility["reason"]
                })
                continue
        
        # Trigger call (will use PM's assigned Twilio number if property_manager_id provided)
        call_result = trigger_outbound_call(
            contact,
            property_manager_id=property_manager_id,
            session=session
        )
        
        if call_result["success"]:
            called += 1
            results.append({
                "contact_id": contact.id,
                "phone_number": contact.phone_number,
                "status": "called",
                "call_id": call_result.get("call_id")
            })
        else:
            errors += 1
            results.append({
                "contact_id": contact.id,
                "phone_number": contact.phone_number,
                "status": "error",
                "error": call_result.get("error")
            })
        
        # Stop if we've reached batch size
        if called >= batch_size:
            break
    
    return {
        "processed": len(candidates),
        "called": called,
        "skipped": skipped,
        "errors": errors,
        "results": results
    }
