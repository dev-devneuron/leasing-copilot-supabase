"""
Automated Vendor Calling Module

This module handles:
- Creating and managing vendor call queues for maintenance requests
- Triggering automated calls to vendors
- Handling call outcomes (accepted, declined, no answer)
- Retry logic and fallback to next vendor
- Integration with VAPI outbound calling system
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import json
from sqlmodel import Session, select
from .db import (
    Vendor,
    VendorCallQueue,
    VendorCallAttempt,
    MaintenanceRequest,
    PropertyManager,
    engine
)
from .vendor_matching import (
    match_vendors_to_maintenance_request,
    should_auto_call_vendors
)
from .outbound_calling import trigger_outbound_call, get_or_create_contact
from .user_lookup import normalize_phone_number


def create_vendor_call_queue(
    maintenance_request: MaintenanceRequest,
    session: Session,
    auto_start: bool = False
) -> VendorCallQueue:
    """
    Create a vendor call queue for a maintenance request.
    
    Args:
        maintenance_request: MaintenanceRequest object
        session: Database session
        auto_start: If True, start calling immediately
    
    Returns:
        VendorCallQueue object
    """
    # Check if queue already exists
    existing_queue = session.exec(
        select(VendorCallQueue).where(
            VendorCallQueue.maintenance_request_id == maintenance_request.maintenance_request_id
        )
    ).first()
    
    if existing_queue:
        return existing_queue
    
    # Match vendors to request (automatically excludes opted-out vendors)
    matched_vendors = match_vendors_to_maintenance_request(maintenance_request, session)
    
    if not matched_vendors:
        raise ValueError("No vendors found for this maintenance request")
    
    # Double-check: Filter out any opted-out vendors (safety check)
    matched_vendors = [v for v in matched_vendors if not v["vendor"].opted_out]
    
    if not matched_vendors:
        raise ValueError("No available vendors found for this maintenance request (all vendors have opted out)")
    
    # Build vendor queue (list of vendor IDs in priority order)
    vendor_queue = []
    for vendor_data in matched_vendors:
        vendor_queue.append({
            "vendor_id": vendor_data["vendor_id"],
            "priority": vendor_data["priority"],
            "name": vendor_data["name"],
        })
    
    # Create queue
    queue = VendorCallQueue(
        maintenance_request_id=maintenance_request.maintenance_request_id,
        status="pending" if not auto_start else "calling",
        current_vendor_index=0,
        vendor_queue=vendor_queue,
        max_retries_per_vendor=2,
        retry_delay_minutes=15,
        started_at=datetime.utcnow() if auto_start else None
    )
    
    session.add(queue)
    session.commit()
    session.refresh(queue)
    
    # Update maintenance request
    maintenance_request.vendor_call_status = "calling" if auto_start else "not_started"
    session.add(maintenance_request)
    session.commit()
    
    # Start calling if auto_start
    if auto_start:
        start_vendor_calling(maintenance_request.maintenance_request_id, session)
    
    return queue


def start_vendor_calling(
    maintenance_request_id: int,
    session: Session
) -> Dict[str, Any]:
    """
    Start the vendor calling process for a maintenance request.
    
    Args:
        maintenance_request_id: Maintenance request ID
        session: Database session
    
    Returns:
        Result dictionary with success status and details
    """
    # Get maintenance request
    maintenance_request = session.get(MaintenanceRequest, maintenance_request_id)
    if not maintenance_request:
        return {
            "success": False,
            "error": "Maintenance request not found"
        }
    
    # Get or create queue
    queue = session.exec(
        select(VendorCallQueue).where(
            VendorCallQueue.maintenance_request_id == maintenance_request_id
        )
    ).first()
    
    if not queue:
        # Create queue
        queue = create_vendor_call_queue(maintenance_request, session, auto_start=True)
    
    if queue.status == "completed":
        return {
            "success": False,
            "error": "Vendor calling already completed for this request"
        }
    
    if queue.status == "calling":
        return {
            "success": False,
            "error": "Vendor calling already in progress"
        }
    
    # Update queue status
    queue.status = "calling"
    queue.started_at = datetime.utcnow()
    session.add(queue)
    session.commit()
    
    # Update maintenance request
    maintenance_request.vendor_call_status = "calling"
    session.add(maintenance_request)
    session.commit()
    
    # Call next vendor
    return call_next_vendor(maintenance_request_id, session)


def call_next_vendor(
    maintenance_request_id: int,
    session: Session
) -> Dict[str, Any]:
    """
    Call the next vendor in the queue.
    
    Args:
        maintenance_request_id: Maintenance request ID
        session: Database session
    
    Returns:
        Result dictionary with call status
    """
    # Get queue
    queue = session.exec(
        select(VendorCallQueue).where(
            VendorCallQueue.maintenance_request_id == maintenance_request_id
        )
    ).first()
    
    if not queue:
        return {
            "success": False,
            "error": "Vendor call queue not found"
        }
    
    if queue.status != "calling":
        return {
            "success": False,
            "error": f"Queue status is {queue.status}, not 'calling'"
        }
    
    # Get vendor queue
    vendor_queue = queue.vendor_queue or []
    
    if queue.current_vendor_index >= len(vendor_queue):
        # No more vendors
        queue.status = "completed"
        queue.completed_at = datetime.utcnow()
        session.add(queue)
        
        maintenance_request = session.get(MaintenanceRequest, maintenance_request_id)
        if maintenance_request:
            maintenance_request.vendor_call_status = "no_response"
            session.add(maintenance_request)
        
        session.commit()
        
        return {
            "success": False,
            "error": "No more vendors in queue",
            "status": "completed"
        }
    
    # Get current vendor
    current_vendor_data = vendor_queue[queue.current_vendor_index]
    vendor_id = current_vendor_data["vendor_id"]
    vendor = session.get(Vendor, vendor_id)
    
    if not vendor:
        # Skip invalid vendor
        queue.current_vendor_index += 1
        session.add(queue)
        session.commit()
        return call_next_vendor(maintenance_request_id, session)
    
    # Check if vendor has opted out
    if vendor.opted_out:
        print(f"🚫 Vendor {vendor_id} ({vendor.name}) has opted out - skipping")
        # Skip opted-out vendor and move to next
        queue.current_vendor_index += 1
        session.add(queue)
        session.commit()
        return call_next_vendor(maintenance_request_id, session)
    
    # Check if we've exceeded retries for this vendor
    attempt_count = session.exec(
        select(VendorCallAttempt)
        .where(VendorCallAttempt.maintenance_request_id == maintenance_request_id)
        .where(VendorCallAttempt.vendor_id == vendor_id)
    ).all()
    
    if len(attempt_count) >= queue.max_retries_per_vendor:
        # Move to next vendor
        queue.current_vendor_index += 1
        session.add(queue)
        session.commit()
        return call_next_vendor(maintenance_request_id, session)
    
    # Create call attempt record
    attempt = VendorCallAttempt(
        maintenance_request_id=maintenance_request_id,
        vendor_id=vendor_id,
        call_status="initiated",
        attempt_number=len(attempt_count) + 1
    )
    session.add(attempt)
    session.commit()
    
    # Get maintenance request for context
    maintenance_request = session.get(MaintenanceRequest, maintenance_request_id)
    
    # Prepare call metadata
    call_metadata = {
        "maintenance_request_id": maintenance_request_id,
        "vendor_id": vendor_id,
        "vendor_call_attempt_id": attempt.attempt_id,
        "issue_description": maintenance_request.issue_description,
        "category": maintenance_request.category,
        "priority": maintenance_request.priority,
        "location": maintenance_request.location,
        "property_id": maintenance_request.property_id,
        "tenant_name": maintenance_request.tenant_name,
        "tenant_unit": None,  # Will be filled if available
    }
    
    # Get tenant unit number if available
    from .db import Tenant
    tenant = session.get(Tenant, maintenance_request.tenant_id)
    if tenant and tenant.unit_number:
        call_metadata["tenant_unit"] = tenant.unit_number
    
    # Get property address if available
    from .db import ApartmentListing
    property_listing = session.get(ApartmentListing, maintenance_request.property_id)
    if property_listing and property_listing.listing_metadata:
        address = property_listing.listing_metadata.get("address")
        if address:
            call_metadata["property_address"] = address
    
    # Normalize vendor phone number
    try:
        vendor_phone = normalize_phone_number(vendor.phone_number)
    except Exception as e:
        print(f"❌ Error normalizing vendor phone number: {e}")
        # Move to next vendor
        queue.current_vendor_index += 1
        session.add(queue)
        session.commit()
        return call_next_vendor(maintenance_request_id, session)
    
    # Get or create contact for vendor
    try:
        contact = get_or_create_contact(
            phone_number=vendor_phone,
            name=vendor.name,
            email=vendor.email,
            session=session
        )
    except Exception as e:
        print(f"❌ Error creating contact for vendor: {e}")
        # Move to next vendor
        queue.current_vendor_index += 1
        session.add(queue)
        session.commit()
        return call_next_vendor(maintenance_request_id, session)
    
    # Trigger outbound call
    try:
        result = trigger_outbound_call(
            contact=contact,
            property_manager_id=maintenance_request.property_manager_id,
            session=session,
            metadata={
                "callContext": json.dumps(call_metadata),
                "vendorCall": True,
                "maintenanceRequestId": maintenance_request_id,
                "vendorId": vendor_id,
                "vendorCallAttemptId": attempt.attempt_id,
            }
        )
        
        if result["success"]:
            # Update attempt with VAPI call ID
            attempt.vapi_call_id = result.get("call_id")
            attempt.call_status = "initiated"
            session.add(attempt)
            session.commit()
            
            return {
                "success": True,
                "call_id": result.get("call_id"),
                "vendor_id": vendor_id,
                "vendor_name": vendor.name,
                "attempt_id": attempt.attempt_id
            }
        else:
            # Call failed
            attempt.call_status = "failed"
            attempt.completed_at = datetime.utcnow()
            session.add(attempt)
            
            # Move to next vendor after delay
            queue.current_vendor_index += 1
            session.add(queue)
            session.commit()
            
            return {
                "success": False,
                "error": result.get("error", "Call failed"),
                "vendor_id": vendor_id,
                "will_retry": queue.current_vendor_index < len(vendor_queue)
            }
    
    except Exception as e:
        print(f"❌ Error triggering vendor call: {e}")
        import traceback
        traceback.print_exc()
        
        # Update attempt
        attempt.call_status = "failed"
        attempt.completed_at = datetime.utcnow()
        session.add(attempt)
        
        # Move to next vendor
        queue.current_vendor_index += 1
        session.add(queue)
        session.commit()
        
        return {
            "success": False,
            "error": str(e),
            "vendor_id": vendor_id
        }


def handle_vendor_call_outcome(
    vendor_call_attempt_id: int,
    outcome: str,
    session: Session,
    call_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Handle the outcome of a vendor call attempt.
    
    Called from webhook when call completes.
    
    Args:
        vendor_call_attempt_id: VendorCallAttempt ID
        outcome: "accepted", "declined", "no_response", "voicemail"
        session: Database session
        call_data: Optional call data (transcript, recording, etc.)
    
    Returns:
        Result dictionary
    """
    # Get attempt
    attempt = session.get(VendorCallAttempt, vendor_call_attempt_id)
    if not attempt:
        return {
            "success": False,
            "error": "Vendor call attempt not found"
        }
    
    # Update attempt
    attempt.outcome = outcome
    attempt.completed_at = datetime.utcnow()
    
    if call_data:
        if "transcript" in call_data:
            attempt.call_transcript = call_data["transcript"]
        if "recording_url" in call_data:
            attempt.call_recording_url = call_data["recording_url"]
        if "duration" in call_data:
            attempt.call_duration_seconds = call_data["duration"]
        if "is_available" in call_data:
            attempt.is_available = call_data["is_available"]
        if "earliest_available_time" in call_data:
            attempt.earliest_available_time = call_data["earliest_available_time"]
        if "estimated_cost_range" in call_data:
            attempt.estimated_cost_range = call_data["estimated_cost_range"]
        if "vendor_notes" in call_data:
            attempt.vendor_notes = call_data["vendor_notes"]
    
    # Update call status based on outcome
    if outcome == "accepted":
        attempt.call_status = "answered"
        attempt.is_available = True
    elif outcome == "declined":
        attempt.call_status = "answered"
        attempt.is_available = False
    elif outcome == "no_response":
        attempt.call_status = "no_answer"
    elif outcome == "voicemail":
        attempt.call_status = "voicemail"
    
    session.add(attempt)
    
    # Get queue
    queue = session.exec(
        select(VendorCallQueue).where(
            VendorCallQueue.maintenance_request_id == attempt.maintenance_request_id
        )
    ).first()
    
    maintenance_request = session.get(MaintenanceRequest, attempt.maintenance_request_id)
    
    if outcome == "accepted":
        # Vendor accepted - assign to maintenance request
        maintenance_request.assigned_vendor_id = attempt.vendor_id
        maintenance_request.vendor_call_status = "vendor_accepted"
        maintenance_request.status = "in_progress"
        
        # Complete queue
        if queue:
            queue.status = "completed"
            queue.completed_at = datetime.utcnow()
            session.add(queue)
        
        session.add(maintenance_request)
        session.commit()
        
        return {
            "success": True,
            "outcome": "accepted",
            "vendor_id": attempt.vendor_id,
            "maintenance_request_id": attempt.maintenance_request_id
        }
    
    elif outcome == "declined":
        # Vendor declined - move to next vendor
        if queue:
            queue.current_vendor_index += 1
            session.add(queue)
            session.commit()
            
            # Call next vendor
            return call_next_vendor(attempt.maintenance_request_id, session)
        else:
            session.commit()
            return {
                "success": True,
                "outcome": "declined",
                "message": "Vendor declined, but no queue found to continue"
            }
    
    elif outcome in ["no_response", "voicemail"]:
        # No response - check if we should retry
        if queue and attempt.attempt_number < queue.max_retries_per_vendor:
            # Retry same vendor after delay
            session.commit()
            # Note: Actual retry would be handled by a background job or scheduled task
            # For now, we'll move to next vendor
            queue.current_vendor_index += 1
            session.add(queue)
            session.commit()
            return call_next_vendor(attempt.maintenance_request_id, session)
        else:
            # Move to next vendor
            if queue:
                queue.current_vendor_index += 1
                session.add(queue)
                session.commit()
                return call_next_vendor(attempt.maintenance_request_id, session)
            else:
                session.commit()
                return {
                    "success": True,
                    "outcome": outcome,
                    "message": "No response, but no queue found to continue"
                }
    
    else:
        session.commit()
        return {
            "success": True,
            "outcome": outcome,
            "message": "Outcome recorded"
        }


def pause_vendor_calling(
    maintenance_request_id: int,
    session: Session
) -> Dict[str, Any]:
    """
    Pause vendor calling for a maintenance request.
    
    Args:
        maintenance_request_id: Maintenance request ID
        session: Database session
    
    Returns:
        Result dictionary
    """
    queue = session.exec(
        select(VendorCallQueue).where(
            VendorCallQueue.maintenance_request_id == maintenance_request_id
        )
    ).first()
    
    if not queue:
        return {
            "success": False,
            "error": "Vendor call queue not found"
        }
    
    queue.status = "paused"
    session.add(queue)
    
    maintenance_request = session.get(MaintenanceRequest, maintenance_request_id)
    if maintenance_request:
        maintenance_request.vendor_call_status = "paused"
        session.add(maintenance_request)
    
    session.commit()
    
    return {
        "success": True,
        "message": "Vendor calling paused"
    }


def cancel_vendor_calling(
    maintenance_request_id: int,
    session: Session
) -> Dict[str, Any]:
    """
    Cancel vendor calling for a maintenance request.
    
    Args:
        maintenance_request_id: Maintenance request ID
        session: Database session
    
    Returns:
        Result dictionary
    """
    queue = session.exec(
        select(VendorCallQueue).where(
            VendorCallQueue.maintenance_request_id == maintenance_request_id
        )
    ).first()
    
    if not queue:
        return {
            "success": False,
            "error": "Vendor call queue not found"
        }
    
    queue.status = "cancelled"
    queue.completed_at = datetime.utcnow()
    session.add(queue)
    
    maintenance_request = session.get(MaintenanceRequest, maintenance_request_id)
    if maintenance_request:
        maintenance_request.vendor_call_status = "cancelled"
        session.add(maintenance_request)
    
    session.commit()
    
    return {
        "success": True,
        "message": "Vendor calling cancelled"
    }
