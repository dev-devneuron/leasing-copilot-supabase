"""
User lookup utilities for identifying PM/realtor from phone number.
"""

from typing import Optional, Dict, Any
from sqlmodel import select, Session
from .db import engine, Realtor, PropertyManager, PurchasedPhoneNumber, get_data_access_scope


def get_user_from_phone_number(phone_number: str) -> Optional[Dict[str, Any]]:
    """
    Identify user (PM or Realtor) from their Twilio phone number.
    Works with both direct twilio_contact and purchased phone numbers.
    
    Args:
        phone_number: Twilio phone number (with or without whatsapp: prefix)
    
    Returns:
        Dict with user_type, user_id, and accessible source_ids, or None if not found
    """
    # Clean phone number
    if phone_number.startswith("whatsapp:"):
        phone_number = phone_number.replace("whatsapp:", "")
    phone_number = phone_number.strip()
    
    with Session(engine) as session:
        # Method 1: Check direct twilio_contact (for backward compatibility)
        realtor = session.exec(
            select(Realtor).where(Realtor.twilio_contact == phone_number)
        ).first()
        
        if realtor:
            scope = get_data_access_scope("realtor", realtor.realtor_id)
            return {
                "user_type": "realtor",
                "user_id": realtor.realtor_id,
                "source_ids": scope["source_ids"],
                "realtor": realtor,
            }
        
        property_manager = session.exec(
            select(PropertyManager).where(PropertyManager.twilio_contact == phone_number)
        ).first()
        
        if property_manager:
            scope = get_data_access_scope("property_manager", property_manager.property_manager_id)
            return {
                "user_type": "property_manager",
                "user_id": property_manager.property_manager_id,
                "source_ids": scope["source_ids"],
                "property_manager": property_manager,
            }
        
        # Method 2: Check purchased phone numbers (new system)
        purchased_number = session.exec(
            select(PurchasedPhoneNumber).where(PurchasedPhoneNumber.phone_number == phone_number)
        ).first()
        
        if purchased_number and purchased_number.status == "assigned":
            if purchased_number.assigned_to_type == "realtor" and purchased_number.assigned_to_id:
                realtor = session.get(Realtor, purchased_number.assigned_to_id)
                if realtor:
                    scope = get_data_access_scope("realtor", realtor.realtor_id)
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
                    return {
                        "user_type": "property_manager",
                        "user_id": pm.property_manager_id,
                        "source_ids": scope["source_ids"],
                        "property_manager": pm,
                    }
        
        return None
