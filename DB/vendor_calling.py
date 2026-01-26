"""
Automated Vendor Calling Module

This module handles:
- Creating and managing vendor call queues for maintenance requests
- Triggering automated calls to vendors
- Handling call outcomes (accepted, declined, no answer)
- Retry logic and fallback to next vendor
- Integration with VAPI outbound calling system
- Background workers for retry delays and callback scheduling
- Webhook timeout handling
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import json
import threading
import queue as queue_module
from sqlmodel import Session, select, or_
from .db import (
    Vendor,
    VendorCallQueue,
    VendorCallAttempt,
    MaintenanceRequest,
    PropertyManager,
    VendorCallbackSchedule,
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
    
    # Get vendor calling assistant ID from Property Manager
    from .db import PropertyManager
    pm = session.get(PropertyManager, maintenance_request.property_manager_id)
    vendor_assistant_id = None
    if pm:
        vendor_assistant_id = pm.vapi_vendor_calling_assistant_id
        if not vendor_assistant_id:
            # Fallback to outbound assistant if vendor assistant not configured
            vendor_assistant_id = pm.vapi_outbound_assistant_id
            if vendor_assistant_id:
                print(f"⚠️  No vendor calling assistant configured for PM {maintenance_request.property_manager_id}, using outbound assistant")
        else:
            print(f"✅ Using vendor calling assistant ID: {vendor_assistant_id}")
    
    if not vendor_assistant_id:
        print(f"❌ No assistant ID available for vendor calls (PM {maintenance_request.property_manager_id})")
        # Move to next vendor
        queue.current_vendor_index += 1
        session.add(queue)
        session.commit()
        return call_next_vendor(maintenance_request_id, session)
    
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
    
    # Trigger outbound call with explicit vendor calling assistant ID
    try:
        result = trigger_outbound_call(
            contact=contact,
            assistant_id=vendor_assistant_id,  # ✅ EXPLICIT: Vendor calling assistant
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
        
        # Send notification to vendor
        try:
            vendor = session.get(Vendor, attempt.vendor_id)
            if vendor:
                # Build notification message
                message_content = {
                    "subject": "Maintenance Job Assignment Confirmation",
                    "body": f"Hello {vendor.name},\n\nYou have been assigned to maintenance request #{attempt.maintenance_request_id}. "
                           f"Please review the details and confirm your availability.\n\n"
                           f"Issue: {maintenance_request.issue_description}\n"
                           f"Location: {maintenance_request.location}\n"
                           f"Priority: {maintenance_request.priority}\n\n"
                           f"Thank you!"
                }
                
                # Try SMS first, fallback to email
                result = send_vendor_notification(
                    vendor_id=attempt.vendor_id,
                    maintenance_request_id=attempt.maintenance_request_id,
                    notification_type="job_assignment",
                    delivery_method="sms",
                    message_content=message_content,
                    session=session
                )
                
                if not result.get("success") and vendor.email:
                    # Fallback to email if SMS failed
                    result = send_vendor_notification(
                        vendor_id=attempt.vendor_id,
                        maintenance_request_id=attempt.maintenance_request_id,
                        notification_type="job_assignment",
                        delivery_method="email",
                        message_content=message_content,
                        session=session
                    )
        except Exception as e:
            print(f"⚠️  Failed to send notification to vendor: {e}")
            # Don't fail assignment if notification fails
        
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
            # Schedule retry after delay
            session.commit()
            enqueue_retry_job(
                attempt_id=attempt.attempt_id,
                maintenance_request_id=attempt.maintenance_request_id,
                retry_delay_minutes=queue.retry_delay_minutes
            )
            print(f"⏳ Scheduled retry for attempt {attempt.attempt_id} in {queue.retry_delay_minutes} minutes")
            return {
                "success": True,
                "outcome": outcome,
                "message": f"Retry scheduled in {queue.retry_delay_minutes} minutes"
            }
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


# ============================================================================
# Background Workers for Retry Delays and Callback Scheduling
# ============================================================================

# Retry queue and worker
_retry_queue = queue_module.Queue()
_retry_in_flight = set()
_retry_lock = threading.Lock()
_retry_worker_started = False


def _retry_worker_loop() -> None:
    """
    Background worker loop that processes retry jobs for vendor calls.
    Waits for retry_delay_minutes before retrying a vendor call.
    """
    print("🚀 Vendor call retry worker started")
    while True:
        try:
            job = _retry_queue.get(timeout=60)  # Check queue every minute
            if job is None:
                continue
            
            attempt_id = job.get("attempt_id")
            maintenance_request_id = job.get("maintenance_request_id")
            retry_delay_minutes = job.get("retry_delay_minutes", 15)
            
            print(f"⏳ Retry job queued for attempt {attempt_id}, waiting {retry_delay_minutes} minutes...")
            
            # Wait for retry delay
            import time
            time.sleep(retry_delay_minutes * 60)
            
            # Check if attempt still needs retry
            with Session(engine) as session:
                attempt = session.get(VendorCallAttempt, attempt_id)
                if not attempt:
                    print(f"⚠️  Attempt {attempt_id} not found, skipping retry")
                    continue
                
                # Check if outcome already determined
                if attempt.outcome and attempt.outcome not in ["no_response", "voicemail"]:
                    print(f"✅ Attempt {attempt_id} already has outcome {attempt.outcome}, skipping retry")
                    continue
                
                # Check if queue still active
                queue = session.exec(
                    select(VendorCallQueue).where(
                        VendorCallQueue.maintenance_request_id == maintenance_request_id
                    )
                ).first()
                
                if not queue or queue.status != "calling":
                    print(f"⚠️  Queue for request {maintenance_request_id} is not active, skipping retry")
                    continue
                
                # Retry the same vendor
                print(f"🔄 Retrying vendor call for attempt {attempt_id}")
                call_next_vendor(maintenance_request_id, session)
            
        except queue_module.Empty:
            continue
        except Exception as e:
            print(f"❌ Error in retry worker: {e}")
            import traceback
            traceback.print_exc()
        finally:
            with _retry_lock:
                if attempt_id:
                    _retry_in_flight.discard(str(attempt_id))
            _retry_queue.task_done()


def _ensure_retry_worker_started() -> None:
    """Ensure the retry worker thread is started once."""
    global _retry_worker_started
    with _retry_lock:
        if not _retry_worker_started:
            worker = threading.Thread(target=_retry_worker_loop, daemon=True)
            worker.start()
            _retry_worker_started = True


def enqueue_retry_job(attempt_id: int, maintenance_request_id: int, retry_delay_minutes: int) -> None:
    """
    Enqueue a retry job for a vendor call attempt.
    
    Args:
        attempt_id: VendorCallAttempt ID to retry
        maintenance_request_id: Maintenance request ID
        retry_delay_minutes: Minutes to wait before retry
    """
    _ensure_retry_worker_started()
    with _retry_lock:
        key = str(attempt_id)
        if key in _retry_in_flight:
            return  # Already queued
        _retry_in_flight.add(key)
        _retry_queue.put({
            "attempt_id": attempt_id,
            "maintenance_request_id": maintenance_request_id,
            "retry_delay_minutes": retry_delay_minutes
        })
        print(f"✅ Enqueued retry job for attempt {attempt_id} (delay: {retry_delay_minutes} min)")


# Callback scheduling queue and worker
_callback_queue = queue_module.Queue()
_callback_in_flight = set()
_callback_lock = threading.Lock()
_callback_worker_started = False


def _callback_worker_loop() -> None:
    """
    Background worker loop that processes scheduled callbacks.
    Checks for due callbacks and triggers vendor calls.
    """
    print("🚀 Vendor callback scheduler worker started")
    while True:
        try:
            # Check for due callbacks every minute
            import time
            time.sleep(60)
            
            with Session(engine) as session:
                now = datetime.utcnow()
                
                # Find callbacks that are due (within next 2 minutes to account for processing time)
                due_callbacks = session.exec(
                    select(VendorCallbackSchedule).where(
                        VendorCallbackSchedule.status == "scheduled",
                        VendorCallbackSchedule.callback_datetime <= now + timedelta(minutes=2)
                    )
                ).all()
                
                for callback in due_callbacks:
                    if callback.callback_datetime > now:
                        continue  # Not quite due yet
                    
                    print(f"📞 Executing scheduled callback {callback.callback_id} for maintenance request {callback.maintenance_request_id}")
                    
                    # Update callback status
                    callback.status = "completed"
                    callback.completed_at = datetime.utcnow()
                    session.add(callback)
                    
                    # Trigger vendor call
                    try:
                        call_next_vendor(callback.maintenance_request_id, session)
                        session.commit()
                        print(f"✅ Callback {callback.callback_id} executed successfully")
                    except Exception as e:
                        print(f"❌ Error executing callback {callback.callback_id}: {e}")
                        callback.status = "failed"
                        session.commit()
                        import traceback
                        traceback.print_exc()
                
        except Exception as e:
            print(f"❌ Error in callback worker: {e}")
            import traceback
            traceback.print_exc()


def _ensure_callback_worker_started() -> None:
    """Ensure the callback worker thread is started once."""
    global _callback_worker_started
    with _callback_lock:
        if not _callback_worker_started:
            worker = threading.Thread(target=_callback_worker_loop, daemon=True)
            worker.start()
            _callback_worker_started = True


def schedule_vendor_callback(
    maintenance_request_id: int,
    vendor_id: int,
    callback_date: str,
    callback_time: str,
    callback_reason: str,
    notes_for_next_call: Optional[str] = None,
    vendor_call_attempt_id: Optional[int] = None,
    session: Optional[Session] = None
) -> VendorCallbackSchedule:
    """
    Schedule a callback with a vendor.
    
    Args:
        maintenance_request_id: Maintenance request ID
        vendor_id: Vendor ID
        callback_date: Date in YYYY-MM-DD format
        callback_time: Time in HH:MM format (24-hour)
        callback_reason: Reason for callback
        notes_for_next_call: Optional notes
        vendor_call_attempt_id: Optional attempt ID that requested callback
        session: Database session
    
    Returns:
        VendorCallbackSchedule object
    """
    if not session:
        session = Session(engine)
    
    # Parse callback datetime
    try:
        callback_datetime_str = f"{callback_date} {callback_time}"
        callback_datetime = datetime.strptime(callback_datetime_str, "%Y-%m-%d %H:%M")
        # Assume local timezone, convert to UTC (simplified - should use proper timezone)
        # For now, assume callback time is in PM's timezone
    except ValueError as e:
        raise ValueError(f"Invalid callback date/time format: {e}")
    
    callback = VendorCallbackSchedule(
        maintenance_request_id=maintenance_request_id,
        vendor_id=vendor_id,
        vendor_call_attempt_id=vendor_call_attempt_id,
        callback_date=callback_date,
        callback_time=callback_time,
        callback_reason=callback_reason,
        notes_for_next_call=notes_for_next_call,
        callback_datetime=callback_datetime,
        status="scheduled"
    )
    
    session.add(callback)
    session.commit()
    session.refresh(callback)
    
    # Ensure callback worker is running
    _ensure_callback_worker_started()
    
    print(f"✅ Scheduled callback {callback.callback_id} for {callback_date} at {callback_time}")
    
    return callback


# ============================================================================
# Webhook Timeout Handling
# ============================================================================

def check_and_handle_stuck_attempts(session: Optional[Session] = None) -> Dict[str, Any]:
    """
    Check for vendor call attempts that are stuck in "initiated" state
    and poll VAPI API to get their status.
    
    Args:
        session: Database session (optional)
    
    Returns:
        Dict with statistics about processed attempts
    """
    if not session:
        session = Session(engine)
    
    # Find attempts that are stuck (initiated > 5 minutes ago, no outcome)
    timeout_threshold = datetime.utcnow() - timedelta(minutes=5)
    
    stuck_attempts = session.exec(
        select(VendorCallAttempt).where(
            VendorCallAttempt.call_status == "initiated",
            VendorCallAttempt.outcome.is_(None),
            VendorCallAttempt.initiated_at <= timeout_threshold,
            VendorCallAttempt.vapi_call_id.isnot(None)
        )
    ).all()
    
    if not stuck_attempts:
        return {
            "checked": 0,
            "processed": 0,
            "errors": 0
        }
    
    print(f"🔍 Found {len(stuck_attempts)} stuck vendor call attempts, checking VAPI status...")
    
    processed = 0
    errors = 0
    
    # Import VAPI API client
    import os
    import httpx
    VAPI_API_KEY = os.getenv("VAPI_API_KEY")
    VAPI_BASE_URL = os.getenv("VAPI_BASE_URL", "https://api.vapi.ai")
    
    if not VAPI_API_KEY:
        print("⚠️  VAPI_API_KEY not configured, cannot check stuck attempts")
        return {
            "checked": len(stuck_attempts),
            "processed": 0,
            "errors": len(stuck_attempts)
        }
    
    for attempt in stuck_attempts:
        try:
            # Poll VAPI API for call status
            url = f"{VAPI_BASE_URL}/v1/call/{attempt.vapi_call_id}"
            headers = {"Authorization": f"Bearer {VAPI_API_KEY}"}
            
            with httpx.Client(timeout=10.0) as client:
                response = client.get(url, headers=headers)
                
                if response.status_code == 200:
                    call_data = response.json()
                    call_status = call_data.get("status", "unknown")
                    
                    # Determine outcome from VAPI status
                    outcome = None
                    if call_status == "ended":
                        duration = call_data.get("duration", 0)
                        if duration and duration > 30:
                            outcome = "accepted"  # Assume accepted if call had duration
                        else:
                            outcome = "declined"
                    elif call_status in ["no-answer", "busy"]:
                        outcome = "no_response"
                    elif call_status == "voicemail":
                        outcome = "voicemail"
                    else:
                        outcome = "no_response"
                    
                    # Update attempt with outcome
                    attempt.call_status = call_status
                    attempt.outcome = outcome
                    attempt.completed_at = datetime.utcnow()
                    
                    # Get transcript and recording if available
                    if call_data.get("transcript"):
                        attempt.call_transcript = call_data.get("transcript")
                    if call_data.get("recordingUrl") or call_data.get("recording"):
                        attempt.call_recording_url = call_data.get("recordingUrl") or call_data.get("recording")
                    if call_data.get("duration"):
                        attempt.call_duration_seconds = call_data.get("duration")
                    
                    session.add(attempt)
                    session.commit()
                    
                    # Process outcome (escalate or assign)
                    handle_vendor_call_outcome(
                        vendor_call_attempt_id=attempt.attempt_id,
                        outcome=outcome,
                        session=session,
                        call_data={
                            "transcript": attempt.call_transcript,
                            "recording_url": attempt.call_recording_url,
                            "duration": attempt.call_duration_seconds
                        }
                    )
                    
                    processed += 1
                    print(f"✅ Processed stuck attempt {attempt.attempt_id}: {outcome}")
                else:
                    print(f"⚠️  VAPI API returned {response.status_code} for call {attempt.vapi_call_id}")
                    errors += 1
                    
        except Exception as e:
            print(f"❌ Error checking stuck attempt {attempt.attempt_id}: {e}")
            errors += 1
            import traceback
            traceback.print_exc()
    
    return {
        "checked": len(stuck_attempts),
        "processed": processed,
        "errors": errors
    }


# ============================================================================
# Notification Sending
# ============================================================================

def send_vendor_notification(
    vendor_id: int,
    maintenance_request_id: int,
    notification_type: str,
    delivery_method: str,
    message_content: Dict[str, Any],
    session: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Send notification to vendor via SMS or email.
    
    Args:
        vendor_id: Vendor ID
        maintenance_request_id: Maintenance request ID
        notification_type: Type of notification (job_assignment, details_confirmation, etc.)
        delivery_method: How to send (sms, email)
        message_content: Message content with subject/body
        session: Database session
    
    Returns:
        Dict with success status and details
    """
    if not session:
        session = Session(engine)
    
    vendor = session.get(Vendor, vendor_id)
    if not vendor:
        return {
            "success": False,
            "error": "Vendor not found"
        }
    
    maintenance_request = session.get(MaintenanceRequest, maintenance_request_id)
    if not maintenance_request:
        return {
            "success": False,
            "error": "Maintenance request not found"
        }
    
    # Build message
    subject = message_content.get("subject", "")
    body = message_content.get("body", "")
    
    if delivery_method == "sms":
        # Send SMS via Twilio
        try:
            from vapi.app import _send_sms_notification
            phone_number = vendor.phone_number
            if not phone_number:
                return {
                    "success": False,
                    "error": "Vendor phone number not available"
                }
            
            # Normalize phone number
            phone_number = normalize_phone_number(phone_number)
            
            # Send SMS
            success = _send_sms_notification(phone_number, body)
            
            if success:
                print(f"✅ Sent SMS notification to vendor {vendor_id} ({vendor.name})")
                return {
                    "success": True,
                    "method": "sms",
                    "vendor_id": vendor_id
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to send SMS"
                }
        except Exception as e:
            print(f"❌ Error sending SMS to vendor {vendor_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    elif delivery_method == "email":
        # Send email (requires email service integration)
        if not vendor.email:
            return {
                "success": False,
                "error": "Vendor email not available"
            }
        
        # TODO: Integrate with email service (SendGrid, Resend, etc.)
        print(f"⚠️  Email sending not yet implemented for vendor {vendor_id}")
        return {
            "success": False,
            "error": "Email sending not yet implemented"
        }
    
    else:
        return {
            "success": False,
            "error": f"Unsupported delivery method: {delivery_method}"
        }
