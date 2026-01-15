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
from sqlmodel import Session, select
from sqlalchemy import or_
from .db import Contact, CallRecord, PropertyTourBooking, engine
from .user_lookup import normalize_phone_number
import os
import requests

VAPI_BASE_URL = "https://api.vapi.ai"
VAPI_API_KEY = os.getenv("VAPI_API_KEY")
VAPI_ASSISTANT_ID = os.getenv("VAPI_ASSISTANT_ID")

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
    checks["below_attempt_limit"] = contact.call_attempt_count < MAX_CALL_ATTEMPTS
    if not checks["below_attempt_limit"]:
        reasons.append(f"Exceeded maximum call attempts ({MAX_CALL_ATTEMPTS})")
    
    # Check 7: Cooldown period passed
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
# CANDIDATE IDENTIFICATION
# ============================================================================

def identify_follow_up_candidates(session: Session, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Identify contacts who:
    - Called Leasap before (inbound call exists)
    - Asked for information (transcript indicates inquiry)
    - Did NOT book a tour
    - Did NOT opt out
    
    This creates the candidate pool for outbound calling.
    
    Args:
        session: Database session
        limit: Maximum number of candidates to return
    
    Returns:
        List of candidate contacts with metadata
    """
    # Find callers who haven't booked
    # Strategy: Get all inbound calls, check if they have bookings
    
    # Get all inbound calls with caller numbers
    # Include NULL call_direction (legacy calls default to inbound)
    from sqlalchemy import or_
    inbound_calls = session.exec(
        select(CallRecord)
        .where(or_(
            CallRecord.call_direction == "inbound",
            CallRecord.call_direction.is_(None)  # Legacy calls without direction
        ))
        .where(CallRecord.caller_number.isnot(None))
        .order_by(CallRecord.created_at.desc())
        .limit(limit * 2)  # Get more to filter
    ).all()
    
    candidates = []
    seen_phones = set()
    
    for call in inbound_calls:
        if not call.caller_number:
            continue
        
        phone = normalize_phone_number(call.caller_number)
        
        # Skip if already processed
        if phone in seen_phones:
            continue
        seen_phones.add(phone)
        
        # Check if they have a booking
        has_booking = session.exec(
            select(PropertyTourBooking)
            .where(PropertyTourBooking.visitor_phone == phone)
            .where(PropertyTourBooking.status.in_(["approved", "pending"]))
        ).first() is not None
        
        if has_booking:
            continue  # Skip if they already booked
        
        # Get or create contact
        contact = session.exec(
            select(Contact).where(Contact.phone_number == phone)
        ).first()
        
        if not contact:
            # Create contact with consent from previous call
            contact = get_or_create_contact(
                phone,
                session,
                timezone="America/New_York"  # Default, can be updated
            )
            # Record consent from previous inbound call
            record_consent(phone, session, source="call")
        
        # Check if already opted out
        if contact.opted_out:
            continue
        
        # Add to candidates
        candidates.append({
            "contact": contact,
            "last_call_id": call.call_id,
            "last_call_at": call.created_at,
            "call_transcript": call.transcript,
        })
        
        if len(candidates) >= limit:
            break
    
    return candidates


# ============================================================================
# VAPI CALL TRIGGERING
# ============================================================================

def trigger_outbound_call(
    contact: Contact,
    assistant_id: Optional[str] = None,
    from_number: Optional[str] = None,
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
    if not session:
        session = Session(engine)
    
    # Use default assistant if not provided
    if not assistant_id:
        assistant_id = VAPI_ASSISTANT_ID
    
    if not assistant_id:
        return {
            "success": False,
            "error": "No VAPI assistant ID configured",
            "contact_id": contact.id
        }
    
    # Prepare Vapi API request
    payload = {
        "assistantId": assistant_id,
        "phoneNumber": {
            "to": contact.phone_number
        },
        "metadata": {
            "contactId": str(contact.id),
            "campaign": "no_booking_followup",
            "callDirection": "outbound"
        }
    }
    
    # Add from number if provided
    if from_number:
        payload["phoneNumber"]["from"] = from_number
    
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
        
        # Create call record
        call_record = CallRecord(
            id=None,  # Will be auto-generated
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
        
        session.commit()
        
        print(f"✅ Outbound call triggered: {contact.phone_number} (call_id: {call_id})")
        
        return {
            "success": True,
            "call_id": call_id,
            "contact_id": contact.id
        }
        
    except Exception as e:
        print(f"❌ Error triggering outbound call: {e}")
        return {
            "success": False,
            "error": str(e),
            "contact_id": contact.id
        }


# ============================================================================
# CALL SCHEDULING
# ============================================================================

def process_outbound_call_queue(session: Session, batch_size: int = 10) -> Dict[str, Any]:
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
        
        # Trigger call
        call_result = trigger_outbound_call(contact, session=session)
        
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
