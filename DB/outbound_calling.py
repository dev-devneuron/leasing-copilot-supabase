"""
Outbound Calling Module - Compliance-First Automated Calling System

This module implements a backend-controlled outbound calling system that:
- Enforces TCPA compliance (consent, opt-out, time windows, DNC)
- Maintains audit trail for legal defense
- Provides eligibility engine for call decisions
- Integrates with Vapi for call execution

Key Principle: Backend decides who to call, Vapi only executes.
"""

from typing import Optional, Dict, Any, List
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
import requests

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
    import re

    if not email or "@" not in email:
        return None
    local = email.split("@", 1)[0]
    local = re.sub(r"[^a-zA-Z._\-]", "", local).strip("._-")
    if not local:
        return None
    # prefer first segment
    first = re.split(r"[._\-]+", local)[0]
    if not first:
        return None
    return first[:1].upper() + first[1:].lower()


def extract_contact_intel_from_transcript(transcript: Optional[str]) -> Dict[str, Optional[str]]:
    """
    Extract **caller email first**, then infer name, plus last-call purpose and property/address.

    Regex-first. Uses AI (Vertex/Gemini) only as a fallback when regex can't find anything useful.

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

    if not transcript or not transcript.strip():
        return {
            "email": None,
            "inferred_name": None,
            "region": None,
            "inquiry_property": None,
            "inquiry_purpose": None,
            "inquiry_summary": None,
        }

    parts = _split_transcript(transcript)
    user_text = parts["user"] or parts["all"]
    all_text = parts["all"]

    # 1) EMAIL (priority #1)
    email: Optional[str] = None

    # direct email
    m = re.search(r"([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})", user_text)
    if m:
        email = m.group(1).strip().lower()

    # spoken email patterns
    if not email:
        # capture a window around "email" or "at ... dot ..."
        candidates = []
        for mm in re.finditer(r"(my email is|email is)\s+(.{0,80})", user_text, re.IGNORECASE):
            candidates.append(mm.group(2))
        # generic "xxx at yyy dot com"
        for mm in re.finditer(r"([a-zA-Z0-9._\-\s]+)\s+at\s+([a-zA-Z0-9\-\s]+)\s+(dot\s+[a-zA-Z0-9\-\s]+)", user_text, re.IGNORECASE):
            candidates.append(mm.group(0))
        for c in candidates:
            normalized = _normalize_spoken_email(c)
            if normalized:
                email = normalized
                break

    inferred_name = _infer_name_from_email(email) if email else None

    # 2) PROPERTY / ADDRESS
    inquiry_property: Optional[str] = None
    # common US-ish address
    addr_match = re.search(
        r"\b(\d{1,6}\s+[A-Za-z0-9.\s]{2,60}\s+(?:Street|St|Road|Rd|Avenue|Ave|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Way|Wy|Parkway|Pkwy)\b(?:[^\n]{0,80})?)",
        all_text,
        re.IGNORECASE,
    )
    if addr_match:
        inquiry_property = addr_match.group(1).strip()
    else:
        # "address or location ..." phrases
        m2 = re.search(r"(?:address|property|apartment)\s+(?:at|is)?\s*[:,]?\s*([^\n]{10,120})", all_text, re.IGNORECASE)
        if m2:
            inquiry_property = m2.group(1).strip()

    # 3) PURPOSE (simple rules)
    inquiry_purpose: Optional[str] = None
    t = all_text.lower()
    if any(k in t for k in ["book", "booking", "tour", "visit", "schedule"]):
        inquiry_purpose = "booking a tour"
    elif any(k in t for k in ["availability", "available", "vacancy", "vacant"]):
        inquiry_purpose = "availability inquiry"
    elif any(k in t for k in ["price", "rent", "cost", "how much"]):
        inquiry_purpose = "pricing inquiry"
    elif any(k in t for k in ["maintenance", "repair", "broken", "leak"]):
        inquiry_purpose = "maintenance request"
    elif any(k in t for k in ["info", "information", "details", "tell me about"]):
        inquiry_purpose = "general information"

    # 4) REGION (lightweight)
    region: Optional[str] = None
    city_state = re.search(r"\b([A-Z][a-zA-Z\s]+,\s*[A-Z][a-zA-Z\s]+)\b", all_text)
    if city_state:
        region = city_state.group(1).strip()
    else:
        state = re.search(r"\b(California|Texas|Florida|New York|New Jersey|Virginia|Washington)\b", all_text, re.IGNORECASE)
        if state:
            region = state.group(1).strip()

    # 5) SUMMARY
    summary_parts = []
    if inquiry_purpose:
        summary_parts.append(f"Purpose: {inquiry_purpose}")
    if inquiry_property:
        summary_parts.append(f"Property: {inquiry_property}")
    if email:
        summary_parts.append(f"Email: {email}")
    inquiry_summary = " | ".join(summary_parts) if summary_parts else None

    # 6) AI fallback (second priority)
    if not email and not inquiry_property and not inquiry_purpose:
        try:
            ai_client = get_vertex_ai_client()
            if ai_client and ai_client.is_available():
                prompt = f"""Extract customer intent from this transcript.
Return ONLY JSON with keys: email, inquiry_property, inquiry_purpose, region.
If unknown, use null.

Transcript:
{transcript[:2500]}
"""
                resp = ai_client.generate_content(prompt).strip()
                # find JSON
                start = resp.find("{")
                end = resp.rfind("}") + 1
                if start >= 0 and end > start:
                    data = json.loads(resp[start:end])
                    email = email or (data.get("email") or None)
                    inquiry_property = inquiry_property or (data.get("inquiry_property") or None)
                    inquiry_purpose = inquiry_purpose or (data.get("inquiry_purpose") or None)
                    region = region or (data.get("region") or None)
                    if email and not inferred_name:
                        inferred_name = _infer_name_from_email(email)
                    if not inquiry_summary:
                        parts2 = []
                        if inquiry_purpose:
                            parts2.append(f"Purpose: {inquiry_purpose}")
                        if inquiry_property:
                            parts2.append(f"Property: {inquiry_property}")
                        if email:
                            parts2.append(f"Email: {email}")
                        inquiry_summary = " | ".join(parts2) if parts2 else None
        except Exception as e:
            print(f"⚠️  AI fallback extraction failed: {e}")

    return {
        "email": email,
        "inferred_name": inferred_name,
        "region": region,
        "inquiry_property": inquiry_property,
        "inquiry_purpose": inquiry_purpose,
        "inquiry_summary": inquiry_summary,
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
    
    # Second pass: get or create contacts for each unique phone number
    for phone, call_info in phone_to_latest_call.items():
        try:
            # Get or create contact
            contact = session.exec(
                select(Contact).where(Contact.phone_number == phone)
            ).first()
            
            if not contact:
                # Create contact with consent from previous call
                try:
                    contact = get_or_create_contact(
                        phone,
                        session,
                        timezone="America/New_York"  # Default, can be updated
                    )
                    # Record consent from previous call
                    record_consent(phone, session, source="call")
                    session.commit()
                except Exception as e:
                    print(f"⚠️  Error creating contact for {phone}: {e}")
                    continue  # Skip this candidate
            
            # Extract customer intel from transcript (email-first + intent/property)
            # Only extract if transcript exists and is meaningful (at least 50 chars)
            extracted_info = {
                "email": None,
                "inferred_name": None,
                "region": None,
                "inquiry_property": None,
                "inquiry_purpose": None,
                "inquiry_summary": None,
            }
            transcript = call_info.get("transcript")
            if transcript and len(transcript.strip()) >= 50:
                try:
                    extracted_info = extract_contact_intel_from_transcript(transcript)

                    # Store email if we extracted one and contact doesn't already have it
                    if extracted_info.get("email") and not contact.email:
                        contact.email = extracted_info["email"]
                        session.add(contact)
                        try:
                            session.commit()
                        except Exception:
                            session.rollback()

                    # Store inferred name ONLY if contact has no name (and it's not a known bot name)
                    inferred_name = extracted_info.get("inferred_name")
                    if inferred_name and not contact.name:
                        bad = {"riley", "assistant", "bot", "ai", "lease", "leasap", "speaking"}
                        if inferred_name.lower().strip() not in bad and "riley" not in inferred_name.lower():
                            contact.name = inferred_name
                            session.add(contact)
                            try:
                                session.commit()
                            except Exception:
                                session.rollback()
                except Exception as e:
                    # Don't fail candidate processing if extraction fails
                    print(f"⚠️  Error extracting info from transcript: {e}")
                    import traceback
                    traceback.print_exc()
                    extracted_info = {
                        "email": None,
                        "inferred_name": None,
                        "region": None,
                        "inquiry_property": None,
                        "inquiry_purpose": None,
                        "inquiry_summary": None,
                    }
            
            # In testing mode, show ALL candidates regardless of status
            # In production, we could filter here, but for now show all
            
            # Add to candidates (show all, regardless of booking/opt-out status)
            candidates.append({
                "contact": contact,
                "last_call_id": call_info["call_id"],
                "last_call_at": call_info["call_at"],
                "call_transcript": call_info["transcript"],
                "call_direction": call_info["direction"],
                # extracted fields for frontend + outbound-call context
                "extracted_email": extracted_info.get("email"),
                "inferred_name": extracted_info.get("inferred_name"),
                "extracted_region": extracted_info.get("region"),
                "inquiry_property": extracted_info.get("inquiry_property"),
                "inquiry_purpose": extracted_info.get("inquiry_purpose"),
                "inquiry_summary": extracted_info.get("inquiry_summary"),
            })
            
            # Apply limit if specified
            if limit > 0 and len(candidates) >= limit:
                break
                
        except Exception as e:
            # Skip this candidate on any error and continue
            print(f"⚠️  Error processing candidate {phone}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
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
    metadata: Optional[Dict[str, Any]] = None
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
    
    # Use default assistant if not provided
    if not assistant_id:
        assistant_id = VAPI_ASSISTANT_ID
    
    if not assistant_id:
        return {
            "success": False,
            "error": "No VAPI assistant ID configured",
            "contact_id": contact.id
        }
    
    # Validate Twilio credentials
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        return {
            "success": False,
            "error": "Twilio credentials not configured (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN required)",
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
        return {
            "success": False,
            "error": error_msg,
            "contact_id": contact.id
        }
    
    # Prepare Vapi API request with correct structure
    # Vapi expects: phoneNumber.twilioPhoneNumber, phoneNumber.twilioAccountSid, phoneNumber.twilioAuthToken
    # and customer.number (not phoneNumber.to)
    payload = {
        "assistantId": assistant_id,
        "phoneNumber": {
            "twilioPhoneNumber": from_number,  # Twilio number to call FROM
            "twilioAccountSid": TWILIO_ACCOUNT_SID,
            "twilioAuthToken": TWILIO_AUTH_TOKEN
        },
        "customer": {
            "number": contact.phone_number  # Recipient's phone number (TO)
        },
        "metadata": {
            "contactId": str(contact.id),
            "campaign": "no_booking_followup",
            "callDirection": "outbound"
        }
    }
    
    # Merge additional metadata
    if metadata:
        payload["metadata"].update(metadata)
    
    # Make API call to Vapi
    try:
        headers = {
            "Authorization": f"Bearer {VAPI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            f"{VAPI_BASE_URL}/call",
            headers=headers,
            json=payload,
            timeout=10
        )
        
        if response.status_code not in [200, 201]:
            error_msg = response.text
            print(f"❌ Vapi API error: {response.status_code} - {error_msg}")
            return {
                "success": False,
                "error": f"Vapi API error: {error_msg}",
                "contact_id": contact.id
            }
        
        result = response.json()
        call_id = result.get("id") or result.get("callId")
        
        if not call_id:
            return {
                "success": False,
                "error": "No call ID returned from Vapi",
                "contact_id": contact.id
            }
        
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
