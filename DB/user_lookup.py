"""
User lookup utilities for identifying PM/realtor from phone number.
Tenant lookup utilities for identifying tenants from phone, email, or name.
"""

from typing import Optional, Dict, Any, List
from sqlmodel import select, Session, or_
from .db import engine, Realtor, PropertyManager, PurchasedPhoneNumber, get_data_access_scope, Tenant, ApartmentListing


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


def identify_tenant(
    phone_number: Optional[str] = None,
    email: Optional[str] = None,
    name: Optional[str] = None,
    property_manager_id: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """
    Identify a tenant by phone number, email, or name.
    
    When a tenant calls/texts the bot, we need to identify:
    1. Who they are (tenant record)
    2. Which property they live in
    3. Which PM manages that property
    
    Args:
        phone_number: Tenant's phone number (normalized to E.164)
        email: Tenant's email address
        name: Tenant's name (partial match supported)
        property_manager_id: Optional PM ID to limit search scope (for data isolation)
    
    Returns:
        Dict with tenant info, property info, and PM info, or None if not found
    """
    with Session(engine) as session:
        # Build query with filters
        query = select(Tenant)
        conditions = []
        
        # Phone number match (exact, normalized)
        if phone_number:
            normalized_phone = normalize_phone_number(phone_number)
            conditions.append(Tenant.phone_number == normalized_phone)
        
        # Email match (case-insensitive)
        if email:
            conditions.append(Tenant.email.ilike(email.strip().lower()))
        
        # Name match (case-insensitive, partial)
        if name:
            name_clean = name.strip()
            conditions.append(Tenant.name.ilike(f"%{name_clean}%"))
        
        if not conditions:
            print("❌ No identification criteria provided (phone, email, or name)")
            return None
        
        # Combine conditions with OR (match any provided criteria)
        query = query.where(or_(*conditions))
        
        # Filter by PM if provided (for data isolation)
        if property_manager_id:
            query = query.where(Tenant.property_manager_id == property_manager_id)
        
        # Execute query
        tenants = session.exec(query).all()
        
        if not tenants:
            print(f"❌ No tenant found matching criteria (phone={phone_number}, email={email}, name={name})")
            return None
        
        # If multiple matches, prefer exact phone match, then exact email match
        tenant = None
        if phone_number:
            normalized_phone = normalize_phone_number(phone_number)
            for t in tenants:
                if t.phone_number == normalized_phone:
                    tenant = t
                    break
        
        if not tenant and email:
            email_lower = email.strip().lower()
            for t in tenants:
                if t.email and t.email.lower() == email_lower:
                    tenant = t
                    break
        
        # If still no match, use first result
        if not tenant:
            tenant = tenants[0]
        
        # Get property and PM info
        property_listing = session.get(ApartmentListing, tenant.property_id)
        pm = session.get(PropertyManager, tenant.property_manager_id)
        
        if not property_listing or not pm:
            print(f"⚠️  Tenant found but property or PM not found (property_id={tenant.property_id}, pm_id={tenant.property_manager_id})")
            return None
        
        # Get property address from metadata
        property_address = property_listing.listing_metadata.get("address") if property_listing.listing_metadata else None
        
        print(f"✅ Found tenant ID {tenant.tenant_id} for property {property_address} (PM: {pm.name})")
        
        return {
            "tenant": tenant,
            "tenant_id": tenant.tenant_id,
            "tenant_name": tenant.name,
            "tenant_phone": tenant.phone_number,
            "tenant_email": tenant.email,
            "property_id": tenant.property_id,
            "property_address": property_address,
            "property_manager_id": tenant.property_manager_id,
            "property_manager_name": pm.name,
            "property_manager_email": pm.email,
        }


def get_tenant_properties(tenant_id: int) -> List[Dict[str, Any]]:
    """
    Get all properties associated with a tenant (in case tenant has multiple properties).
    
    Args:
        tenant_id: Tenant ID
    
    Returns:
        List of property dicts
    """
    with Session(engine) as session:
        tenant = session.get(Tenant, tenant_id)
        if not tenant:
            return []
        
        # Get all properties for this tenant
        properties = session.exec(
            select(ApartmentListing).where(ApartmentListing.id == tenant.property_id)
        ).all()
        
        result = []
        for prop in properties:
            result.append({
                "property_id": prop.id,
                "address": prop.listing_metadata.get("address") if prop.listing_metadata else None,
                "metadata": prop.listing_metadata,
            })
        
        return result
