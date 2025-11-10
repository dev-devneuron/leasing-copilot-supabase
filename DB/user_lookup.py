"""
User lookup utilities for identifying PM/realtor from phone number.
"""

from typing import Optional, Dict, Any
from sqlmodel import select, Session
from .db import engine, Realtor, PropertyManager, get_data_access_scope


def get_user_from_phone_number(phone_number: str) -> Optional[Dict[str, Any]]:
    """
    Identify user (PM or Realtor) from their Twilio phone number.
    
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
        # First check if it's a realtor's number
        realtor = session.exec(
            select(Realtor).where(Realtor.twilio_contact == phone_number)
        ).first()
        
        if realtor:
            # Get realtor's accessible source_ids
            scope = get_data_access_scope("realtor", realtor.realtor_id)
            return {
                "user_type": "realtor",
                "user_id": realtor.realtor_id,
                "source_ids": scope["source_ids"],
                "realtor": realtor,
            }
        
        # Check if it's a property manager's number
        property_manager = session.exec(
            select(PropertyManager).where(PropertyManager.twilio_contact == phone_number)
        ).first()
        
        if property_manager:
            # Get PM's accessible source_ids
            scope = get_data_access_scope("property_manager", property_manager.property_manager_id)
            return {
                "user_type": "property_manager",
                "user_id": property_manager.property_manager_id,
                "source_ids": scope["source_ids"],
                "property_manager": property_manager,
            }
        
        return None
