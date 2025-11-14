"""
User lookup utilities for identifying PM/realtor from phone number.
"""

from typing import Optional, Dict, Any
from sqlmodel import select, Session
from .db import engine, Realtor, PropertyManager, PurchasedPhoneNumber, get_data_access_scope


def normalize_phone_number(phone_number: str) -> str:
    """
    Normalize phone number to E.164 format (+14128992517).
    Handles various formats: "+1 (412) 899 2517", "14128992517", "+14128992517", etc.
    """
    # Remove whatsapp: prefix if present
    if phone_number.startswith("whatsapp:"):
        phone_number = phone_number.replace("whatsapp:", "")
    
    # Remove all non-digit characters except +
    normalized = ""
    for char in phone_number:
        if char.isdigit() or char == "+":
            normalized += char
    
    # Ensure it starts with +
    if normalized.startswith("+"):
        return normalized
    elif normalized.startswith("1") and len(normalized) == 11:
        # US number without + prefix
        return f"+{normalized}"
    elif len(normalized) == 10:
        # US number without country code
        return f"+1{normalized}"
    else:
        # Return as-is if we can't normalize
        return phone_number.strip()


def get_user_from_phone_number(phone_number: str) -> Optional[Dict[str, Any]]:
    """
    Identify user (PM or Realtor) from their Twilio phone number.
    Works with both direct twilio_contact and purchased phone numbers.
    
    Args:
        phone_number: Twilio phone number (with or without whatsapp: prefix)
    
    Returns:
        Dict with user_type, user_id, and accessible source_ids, or None if not found
    """
    # Normalize phone number to E.164 format
    phone_number = normalize_phone_number(phone_number)
    print(f"🔍 Looking up user for normalized phone number: {phone_number}")
    
    with Session(engine) as session:
        # Method 1: Check direct twilio_contact (for backward compatibility)
        # Try exact match first (most common case - numbers should be stored normalized)
        realtor = session.exec(
            select(Realtor).where(Realtor.twilio_contact == phone_number)
        ).first()
        
        if not realtor:
            # Try with normalization - check all realtors and normalize their numbers
            # This handles cases where numbers might be stored in different formats
            realtors = session.exec(select(Realtor)).all()
            for r in realtors:
                if r.twilio_contact:
                    normalized_realtor_phone = normalize_phone_number(r.twilio_contact)
                    if normalized_realtor_phone == phone_number:
                        realtor = r
                        break
        
        if realtor:
            scope = get_data_access_scope("realtor", realtor.realtor_id)
            print(f"✅ Found realtor ID {realtor.realtor_id} with source_ids: {scope['source_ids']}")
            return {
                "user_type": "realtor",
                "user_id": realtor.realtor_id,
                "source_ids": scope["source_ids"],
                "realtor": realtor,
            }
        
        # Check Property Managers
        property_manager = session.exec(
            select(PropertyManager).where(PropertyManager.twilio_contact == phone_number)
        ).first()
        
        if not property_manager:
            # Try with normalization
            pms = session.exec(select(PropertyManager)).all()
            for pm in pms:
                if pm.twilio_contact:
                    normalized_pm_phone = normalize_phone_number(pm.twilio_contact)
                    if normalized_pm_phone == phone_number:
                        property_manager = pm
                        break
        
        if property_manager:
            scope = get_data_access_scope("property_manager", property_manager.property_manager_id)
            print(f"✅ Found PM ID {property_manager.property_manager_id} with source_ids: {scope['source_ids']}")
            return {
                "user_type": "property_manager",
                "user_id": property_manager.property_manager_id,
                "source_ids": scope["source_ids"],
                "property_manager": property_manager,
            }
        
        # Method 2: Check purchased phone numbers (new system)
        # Try exact match first
        purchased_number = session.exec(
            select(PurchasedPhoneNumber).where(
                PurchasedPhoneNumber.phone_number == phone_number,
                PurchasedPhoneNumber.status == "assigned"
            )
        ).first()
        
        if not purchased_number:
            # Try with normalization
            purchased_numbers = session.exec(
                select(PurchasedPhoneNumber).where(PurchasedPhoneNumber.status == "assigned")
            ).all()
            for pn in purchased_numbers:
                if pn.phone_number:
                    normalized_purchased = normalize_phone_number(pn.phone_number)
                    if normalized_purchased == phone_number:
                        purchased_number = pn
                        break
        
        if purchased_number and purchased_number.status == "assigned":
            if purchased_number.assigned_to_type == "realtor" and purchased_number.assigned_to_id:
                realtor = session.get(Realtor, purchased_number.assigned_to_id)
                if realtor:
                    scope = get_data_access_scope("realtor", realtor.realtor_id)
                    print(f"✅ Found realtor ID {realtor.realtor_id} via purchased number with source_ids: {scope['source_ids']}")
                    return {
                        "user_type": "realtor",
                        "user_id": realtor.realtor_id,
                        "source_ids": scope["source_ids"],
                        "realtor": realtor,
                    }
            elif purchased_number.assigned_to_type == "property_manager" and purchased_number.assigned_to_id:
                pm = session.get(PropertyManager, purchased_number.assigned_to_id)
                if pm:
                    scope = get_data_access_scope("property_manager", pm.property_manager_id)
                    print(f"✅ Found PM ID {pm.property_manager_id} via purchased number with source_ids: {scope['source_ids']}")
                    return {
                        "user_type": "property_manager",
                        "user_id": pm.property_manager_id,
                        "source_ids": scope["source_ids"],
                        "property_manager": pm,
                    }
        
        print(f"❌ No user found for phone number: {phone_number}")
        return None
