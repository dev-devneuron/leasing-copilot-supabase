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
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import threading

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


# ============================================================================
# REAL-TIME EXTRACTION: Extract and cache intel when transcripts arrive
# ============================================================================

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
        
        # Process in parallel (max 5 workers to avoid overwhelming Gemini API)
        completed = 0
        failed = 0
        lock = Lock()  # Thread-safe counter
        
        def extract_one(call_record_id):
            """Extract intel for a single call record (thread-safe)."""
            try:
                with Session(engine) as call_session:
                    # Get the call record in this session
                    call_record = call_session.get(CallRecord, call_record_id)
                    if call_record:
                        extract_and_store_intel_for_call_record(
                            call_record, call_session, force_re_extract=False
                        )
                        with lock:
                            completed += 1
                        return True
                    else:
                        with lock:
                            failed += 1
                        return False
            except Exception as e:
                with lock:
                    failed += 1
                print(f"   ⚠️  Extraction failed for call record {call_record_id}: {e}")
                return False
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(extract_one, call_record.id) for call_record in pending_calls]
            
            processed = 0
            for future in as_completed(futures):
                try:
                    future.result()
                    processed += 1
                    if processed % 10 == 0:
                        with lock:
                            current_completed = completed
                            current_failed = failed
                        print(f"   📊 Progress: {processed}/{len(pending_calls)} calls processed ({current_completed} succeeded, {current_failed} failed)...")
                except Exception as e:
                    print(f"   ⚠️  Future error: {e}")
        
        print(f"   ✅ Background extraction completed: {completed} succeeded, {failed} failed out of {len(pending_calls)} total")
    
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
            
            # Use full transcript (up to 8000 chars for Gemini 1.5-flash)
            transcript_snippet = transcript[:8000] if len(transcript) > 8000 else transcript
            print(f"Using transcript snippet: {len(transcript_snippet)} chars")
            
            # Log transcript analysis
            print(f"\n📄 TRANSCRIPT ANALYSIS:")
            print(f"   Full transcript length: {len(transcript)} chars")
            print(f"   Snippet length (sent to Gemini): {len(transcript_snippet)} chars")
            print(f"   Transcript truncated: {len(transcript) > 8000}")
            
            # Analyze transcript content
            user_lines = [line for line in transcript_snippet.split('\n') if line.strip().startswith(('User:', 'Customer:'))]
            bot_lines = [line for line in transcript_snippet.split('\n') if line.strip().startswith(('Bot:', 'Assistant:', 'AI:')) or 'Riley' in line]
            
            print(f"   User/Customer lines found: {len(user_lines)}")
            print(f"   Bot/Assistant lines found: {len(bot_lines)}")
            
            if user_lines:
                print(f"   Sample user lines (first 3):")
                for i, line in enumerate(user_lines[:3], 1):
                    print(f"      {i}. {line[:100]}..." if len(line) > 100 else f"      {i}. {line}")
            
            # Check for email patterns in transcript
            email_patterns = [
                r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b',  # Standard email
                r'\b\w+\s+at\s+\w+\s+dot\s+\w+\b',  # Spoken email
                r'\b\w+\s+@\s+\w+\s+\.\s+\w+\b',  # Spoken with @
            ]
            found_email_patterns = []
            for pattern in email_patterns:
                matches = re.findall(pattern, transcript_snippet, re.IGNORECASE)
                if matches:
                    found_email_patterns.extend(matches)
            
            if found_email_patterns:
                print(f"   ⚠️  Potential email patterns found in transcript: {found_email_patterns[:5]}")
            else:
                print(f"   ℹ️  No obvious email patterns detected in transcript")
            
            # Check for name patterns
            name_patterns = [
                r'\b(?:my name is|I\'m|I am|this is|call me|name\'s)\s+([A-Z][a-z]+)\b',
                r'\b(?:Hi|Hello),?\s+([A-Z][a-z]+)\b',
            ]
            found_name_patterns = []
            for pattern in name_patterns:
                matches = re.findall(pattern, transcript_snippet, re.IGNORECASE)
                if matches:
                    found_name_patterns.extend([m for m in matches if m.lower() not in ['riley', 'assistant', 'bot', 'ai']])
            
            if found_name_patterns:
                print(f"   ⚠️  Potential name patterns found: {found_name_patterns[:5]}")
            else:
                print(f"   ℹ️  No obvious name patterns detected")
            
            print(f"\n   📋 FULL ORIGINAL TRANSCRIPT BEING SENT TO GEMINI:")
            print(f"   {'='*80}")
            print(f"   {transcript_snippet}")
            print(f"   {'='*80}")
            
            # Build PERFECTED prompt with enhanced extraction rules
            prompt = f"""You are an expert data extraction specialist. Extract ONLY customer information from a phone call transcript.

⚠️ CRITICAL RULES:
1. The AI assistant is named "Riley" - IGNORE EVERYTHING Riley/Bot/Assistant says EXCEPT when Riley confirms customer info
2. ONLY extract from CUSTOMER/USER statements (lines starting with "User:", "Customer:", or direct customer speech)
3. EXCEPTION: If AI confirms customer email/name and customer says "yes" or "correct", extract from AI's confirmation
   Example: AI: "Your email is john@gmail.com, correct?" User: "Yes" → Extract "john@gmail.com"
4. Be thorough - extract ALL available information, even if partially mentioned
5. Normalize spoken formats (e.g., "at" = @, "dot" = .)

TRANSCRIPT FORMAT IDENTIFICATION:
- "User:" or "Customer:" lines = CUSTOMER SPEECH (EXTRACT FROM THESE)
- "Bot:", "Assistant:", "AI:", or lines containing "Riley" = AI ASSISTANT (IGNORE COMPLETELY)
- If format unclear, identify customer speech by context (questions, requests, personal info)

DETAILED EXTRACTION RULES:

1. EMAIL (CRITICAL PRIORITY - EXTRACT IF POSSIBLE):
   - Extract ANY email mentioned: "my email is X", "email X", "X at Y dot com", "X@Y.com", "email address X"
   - Normalize spoken: "at" → @, "dot" → ., remove spaces
   - Accept partial emails if reconstructable (e.g., "rehan at gmail" → "rehan@gmail.com")
   - Look for email patterns even in indirect speech: "send to X", "contact at X", "reach me at X"
   - Check if AI assistant asks for email and customer provides it (even if not explicitly labeled)
   - If customer says "yes" or "correct" after AI confirms email, extract from AI's confirmation
   - Return null ONLY if absolutely no email mentioned anywhere in entire transcript

2. CUSTOMER_NAME (CRITICAL PRIORITY - EXTRACT IF POSSIBLE):
   - Look for: "my name is X", "I'm X", "this is X", "call me X", "I am X", "name's X", "I go by X"
   - Extract FIRST NAME if full name given (e.g., "John Smith" → "John")
   - MUST be a real person name (2+ characters, not generic words)
   - REJECT: "Riley", "assistant", "bot", "AI", "speaking", "this is", "hi", "hello", "yes", "no"
   - If AI assistant says "Thank you, [Name]" or "Hi [Name]", extract the name from AI's speech
   - If customer confirms their name when AI asks, extract from context
   - If name unclear but email found, infer from email username if reasonable (e.g., "john@gmail.com" → "John")
   - Return null ONLY if no name mentioned and cannot infer from email

3. INQUIRY_PROPERTY (MEDIUM PRIORITY):
   - Extract ANY property address mentioned, even if partial
   - Look for: street numbers + street names, apartment numbers, building names
   - Examples: "188 Alexandra Road", "123 Main St", "Apartment 5B at 456 Oak Ave"
   - Include city/state if mentioned together (e.g., "188 Alexandra Road, Santa Clara, California")
   - REJECT: Generic phrases like "apartment searches", "visits booking", "general inquiries"
   - Return null ONLY if no specific address mentioned

4. INQUIRY_PURPOSE (MEDIUM PRIORITY):
   - Extract customer's intent from their statements
   - Options: "booking a tour", "availability inquiry", "pricing inquiry", "maintenance request", "general information", "viewing request", "application inquiry"
   - Look for keywords: "book", "tour", "visit", "view", "available", "price", "rent", "cost", "maintenance", "repair"
   - Infer from context if not explicitly stated
   - REJECT: Bot greeting phrases, generic "how can I help"
   - Return null ONLY if intent completely unclear

5. REGION (LOW PRIORITY):
   - Extract state, city, or city+state if mentioned
   - Examples: "California", "Santa Clara", "Santa Clara, California", "CA"
   - Look in property address or separate mentions
   - Return null if not mentioned

OUTPUT FORMAT (STRICT JSON):
{{
  "email": "customer@email.com" or null,
  "customer_name": "ActualCustomerName" or null,
  "inferred_name": "ActualCustomerName" or null,
  "inquiry_property": "123 Street Address, City, State" or null,
  "inquiry_purpose": "booking a tour" or null,
  "region": "California" or null
}}

NOTE: Both "customer_name" and "inferred_name" should contain the same value (the customer's name).

EXAMPLES:
- Customer: "Hi, I'm Rehan, my email is rehan@gmail.com, I want to book a tour for 188 Alexandra Road, Santa Clara"
  → {{"email": "rehan@gmail.com", "customer_name": "Rehan", "inferred_name": "Rehan", "inquiry_property": "188 Alexandra Road, Santa Clara", "inquiry_purpose": "booking a tour", "region": "Santa Clara"}}

- Customer: "Yeah, my name is John and email is john at gmail dot com"
  → {{"email": "john@gmail.com", "customer_name": "John", "inferred_name": "John", "inquiry_property": null, "inquiry_purpose": null, "region": null}}

- AI: "Could you provide your email?" Customer: "Yes, it's john@gmail.com"
  → {{"email": "john@gmail.com", "customer_name": null, "inferred_name": "John", "inquiry_property": null, "inquiry_purpose": null, "region": null}}

- AI: "Thank you, Rehan. Your email is rehan@gmail.com, correct?" Customer: "Yes"
  → {{"email": "rehan@gmail.com", "customer_name": "Rehan", "inferred_name": "Rehan", "inquiry_property": null, "inquiry_purpose": null, "region": null}}

- Only bot speaks: "Riley speaking, how can I help?"
  → {{"email": null, "customer_name": null, "inferred_name": null, "inquiry_property": null, "inquiry_purpose": null, "region": null}}

TRANSCRIPT TO ANALYZE:
{transcript_snippet}

Return ONLY valid JSON, no markdown, no code blocks, no explanations:"""
            
            print(f"\n📤 SENDING PROMPT TO GEMINI:")
            print(f"   Prompt length: {len(prompt)} chars")
            print(f"   Prompt preview (first 1000 chars):\n{prompt[:1000]}\n...")
            
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
                
                # Extract email from AI
                ai_email = json_data.get("email")
                if ai_email:
                    ai_email = str(ai_email).strip().lower()
                    # Validate email format
                    if re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", ai_email):
                        email = ai_email
                        print(f"   ✅ Extracted email: {email}")
                    else:
                        print(f"   ⚠️  Invalid email format: {ai_email}")
                
                # Extract customer name from AI (AGGRESSIVE filtering)
                ai_customer_name = json_data.get("customer_name")
                if ai_customer_name:
                    ai_customer_name = str(ai_customer_name).strip()
                    # AGGRESSIVE bot name filtering
                    bad_names = {
                        "riley", "assistant", "bot", "ai", "lease", "leasap", "speaking", 
                        "this is", "hi", "hello", "hey", "yes", "no", "okay", "ok",
                        "riley speaking", "this is riley", "i'm riley", "my name is riley"
                    }
                    name_lower = ai_customer_name.lower().strip()
                    
                    # Check if it's a bot name
                    is_bot_name = (
                        name_lower in bad_names or 
                        "riley" in name_lower or 
                        name_lower.startswith("riley") or
                        len(ai_customer_name) < 2
                    )
                    
                    if not is_bot_name:
                        inferred_name = ai_customer_name
                        print(f"   ✅ Extracted name: {inferred_name}")
                    else:
                        print(f"   ❌ Rejected bot name: '{ai_customer_name}'")
                
                # Fallback to email inference if AI didn't find name but found email
                if not inferred_name and email:
                    inferred_name = _infer_name_from_email(email)
                    if inferred_name:
                        print(f"   ✅ Inferred name from email: {inferred_name}")
                
                # Extract property (with STRICT validation)
                ai_property = json_data.get("inquiry_property")
                if ai_property:
                    ai_property = str(ai_property).strip()
                    # STRICT validation - must be a real address
                    bot_patterns = [
                        "searches", "visits", "booking", "general apartment inquiries",
                        "apartment searches", "or general", "how can i assist", "visits booking",
                        "apartment searches visits", "or general apartment", "apartment", "inquiries"
                    ]
                    property_lower = ai_property.lower()
                    
                    # Must contain a number AND not be bot text AND be substantial
                    has_number = re.search(r"\d", ai_property)
                    is_bot_text = any(pattern in property_lower for pattern in bot_patterns)
                    is_substantial = len(ai_property) > 15  # Real addresses are longer
                    
                    if has_number and not is_bot_text and is_substantial:
                        inquiry_property = ai_property
                        print(f"   ✅ Extracted property: {inquiry_property}")
                    else:
                        print(f"   ❌ Rejected invalid property: '{ai_property}' (has_number={has_number}, is_bot={is_bot_text}, substantial={is_substantial})")
                
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
                
                # Extract region
                ai_region = json_data.get("region")
                if ai_region:
                    region = str(ai_region).strip()
                    print(f"   ✅ Extracted region: {region}")
                
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
    summary_parts = []
    if inquiry_purpose:
        summary_parts.append(f"Purpose: {inquiry_purpose}")
    if inquiry_property:
        summary_parts.append(f"Property: {inquiry_property}")
    if email:
        summary_parts.append(f"Email: {email}")
    inquiry_summary = " | ".join(summary_parts) if summary_parts else None

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
                
                # MULTI-CALL FALLBACK: Check multiple recent calls if last call has no data
                extracted_info = {
                    "email": None,
                    "inferred_name": None,
                    "region": None,
                    "inquiry_property": None,
                    "inquiry_purpose": None,
                    "inquiry_summary": None,
                    "call_summary": None,
                }
                
                # Get recent calls for this phone number (up to 10 most recent to find email/name)
                print(f"   🔍 Searching for recent calls with transcripts for {phone}...")
                recent_calls = candidate_session.exec(
                    select(CallRecord)
                    .where(CallRecord.caller_number == phone)
                    .where(CallRecord.transcript.isnot(None))
                    .order_by(CallRecord.created_at.desc())
                    .limit(10)  # Increased from 5 to 10 to find email/name in older calls
                ).all()
                
                print(f"   📊 Found {len(recent_calls)} recent call(s) with transcripts")
                for idx, call in enumerate(recent_calls, 1):
                    transcript_len = len(call.transcript) if call.transcript else 0
                    has_cache = call.extracted_intel is not None
                    cache_status = call.extraction_status
                    print(f"      {idx}. Call {call.call_id[:8]}... | Transcript: {transcript_len} chars | Cache: {has_cache} ({cache_status})")
                
                # Try each recent call until we find one with extractable data
                # PRIORITY: Email and name are more important than inquiry_purpose
                # Continue searching if we only found inquiry_purpose but no email/name
                for recent_call in recent_calls:
                    # Use cached extraction if available
                    if recent_call.extracted_intel and recent_call.extraction_status == "completed":
                        cached_intel = recent_call.extracted_intel
                        # Check if cached intel has high-priority data (email or name)
                        has_priority_data = (
                            cached_intel.get("email") or
                            cached_intel.get("inferred_name")
                        )
                        # Check if cached intel has any useful data
                        has_any_data = (
                            has_priority_data or
                            cached_intel.get("inquiry_property") or
                            cached_intel.get("inquiry_purpose")
                        )
                        
                        if has_priority_data:
                            # Found email or name - this is high priority, use it
                            print(f"   ✅ Using cached extraction from call {recent_call.call_id} for {phone} (has email/name)")
                            extracted_info = cached_intel
                            call_info["call_id"] = recent_call.call_id
                            call_info["call_at"] = recent_call.created_at
                            break
                        elif has_any_data and not extracted_info.get("email") and not extracted_info.get("inferred_name"):
                            # Found inquiry_purpose but no email/name yet - store it but keep searching
                            # Also try re-extracting this call if it has a transcript (might have been cached with old prompt)
                            print(f"   📝 Found inquiry context in call {recent_call.call_id} for {phone}, but no email/name - continuing search...")
                            if not extracted_info.get("inquiry_purpose"):
                                # Only update if we don't have inquiry_purpose yet
                                extracted_info.update({
                                    "inquiry_property": cached_intel.get("inquiry_property"),
                                    "inquiry_purpose": cached_intel.get("inquiry_purpose"),
                                    "inquiry_summary": cached_intel.get("inquiry_summary"),
                                    "call_summary": cached_intel.get("call_summary"),
                                    "region": cached_intel.get("region"),
                                })
                                call_info["call_id"] = recent_call.call_id
                                call_info["call_at"] = recent_call.created_at
                            
                            # Try re-extracting this call if it has a transcript (might find email/name with better prompt)
                            if recent_call.transcript and len(recent_call.transcript.strip()) >= 50:
                                try:
                                    print(f"   🔄 Re-extracting call {recent_call.call_id} to look for email/name...")
                                    temp_extracted = extract_and_store_intel_for_call_record(
                                        recent_call, candidate_session, force_re_extract=True
                                    )
                                    if temp_extracted.get("email") or temp_extracted.get("inferred_name"):
                                        print(f"   ✅ Found email/name after re-extraction!")
                                        extracted_info.update({
                                            "email": temp_extracted.get("email"),
                                            "inferred_name": temp_extracted.get("inferred_name"),
                                            "region": temp_extracted.get("region") or extracted_info.get("region"),
                                        })
                                        break  # Found what we need, stop searching
                                except Exception as e:
                                    print(f"   ⚠️  Re-extraction failed: {e}")
                            
                            continue  # Keep searching for email/name
                    
                    # If no cache or cache is empty, extract now
                    if recent_call.transcript and len(recent_call.transcript.strip()) >= 50:
                        print(f"      🔍 No cache - extracting from transcript now...")
                        try:
                            # Extract intel (will use cache if available)
                            temp_extracted = extract_and_store_intel_for_call_record(
                                recent_call, candidate_session, force_re_extract=False
                            )
                            
                            print(f"      📊 Extraction results:")
                            print(f"         - email: {temp_extracted.get('email')}")
                            print(f"         - inferred_name: {temp_extracted.get('inferred_name')}")
                            print(f"         - inquiry_property: {temp_extracted.get('inquiry_property')}")
                            print(f"         - inquiry_purpose: {temp_extracted.get('inquiry_purpose')}")
                            print(f"         - region: {temp_extracted.get('region')}")
                            
                            # Check if we got high-priority data (email or name)
                            has_priority_data = (
                                temp_extracted.get("email") or
                                temp_extracted.get("inferred_name")
                            )
                            # Check if we got any useful data
                            has_any_data = (
                                has_priority_data or
                                temp_extracted.get("inquiry_property") or
                                temp_extracted.get("inquiry_purpose")
                            )
                            
                            print(f"      🔍 Analysis:")
                            print(f"         - Has priority data (email/name): {has_priority_data}")
                            print(f"         - Has any data: {has_any_data}")
                            print(f"         - Current extracted_info has email/name: {bool(extracted_info.get('email') or extracted_info.get('inferred_name'))}")
                            
                            if has_priority_data:
                                # Found email or name - this is high priority, use it
                                print(f"      ✅ PRIORITY DATA FOUND! Using extraction (has email/name)")
                                print(f"      🎯 Stopping search - we have what we need")
                                extracted_info = temp_extracted
                                call_info["call_id"] = recent_call.call_id
                                call_info["call_at"] = recent_call.created_at
                                break
                            elif has_any_data and not extracted_info.get("email") and not extracted_info.get("inferred_name"):
                                # Found inquiry_purpose but no email/name yet - store it but keep searching
                                print(f"      📝 Found inquiry context but NO email/name - storing and continuing search...")
                                if not extracted_info.get("inquiry_purpose"):
                                    # Only update if we don't have inquiry_purpose yet
                                    print(f"      💾 Storing inquiry context from this call...")
                                    extracted_info.update({
                                        "inquiry_property": temp_extracted.get("inquiry_property"),
                                        "inquiry_purpose": temp_extracted.get("inquiry_purpose"),
                                        "inquiry_summary": temp_extracted.get("inquiry_summary"),
                                        "call_summary": temp_extracted.get("call_summary"),
                                        "region": temp_extracted.get("region"),
                                    })
                                    call_info["call_id"] = recent_call.call_id
                                    call_info["call_at"] = recent_call.created_at
                                    print(f"      ✅ Stored inquiry context, continuing to next call...")
                                else:
                                    print(f"      ⏭️  Already have inquiry context, skipping...")
                                print(f"      ➡️  MOVING TO NEXT CALL TRANSCRIPT - searching for email/name...")
                                continue  # Keep searching for email/name
                            else:
                                print(f"      ⚠️  No extractable data in this call transcript")
                                print(f"      📋 Extraction returned all null values:")
                                print(f"         - email: {temp_extracted.get('email')}")
                                print(f"         - inferred_name: {temp_extracted.get('inferred_name')}")
                                print(f"         - inquiry_property: {temp_extracted.get('inquiry_property')}")
                                print(f"         - inquiry_purpose: {temp_extracted.get('inquiry_purpose')}")
                                print(f"      ➡️  MOVING TO NEXT CALL TRANSCRIPT for {phone}...")
                        except Exception as e:
                            print(f"      ❌ Error extracting from call {recent_call.call_id}: {e}")
                            import traceback
                            traceback.print_exc()
                            continue
                    else:
                        transcript_len = len(recent_call.transcript) if recent_call.transcript else 0
                        print(f"      ⏭️  Skipping - transcript too short ({transcript_len} chars, need 50+)")
                
                # Print final extracted_info summary
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
                        bad_names = {"riley", "assistant", "bot", "ai", "lease", "leasap", "speaking", "this is", "hi", "hello", "riley speaking"}
                        name_lower = extracted_info["inferred_name"].lower().strip()
                        if name_lower not in bad_names and "riley" not in name_lower:
                            if not contact.name or contact.name.lower() in bad_names:
                                print(f"      ✅ Updating contact.name: {contact.name} → {extracted_info['inferred_name']}")
                                contact.name = extracted_info["inferred_name"]
                                candidate_session.add(contact)
                                updated = True
                            else:
                                print(f"      ⏭️  Skipping name update - contact already has good name: {contact.name}")
                        else:
                            print(f"      ⏭️  Skipping name update - inferred name is bad: {extracted_info['inferred_name']}")
                    
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
