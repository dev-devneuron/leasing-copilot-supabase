"""
User lookup utilities for identifying PM/realtor from phone number.
Tenant lookup utilities for identifying tenants from phone, email, or name.
"""

import re
from typing import Optional, Dict, Any, List
from sqlmodel import select, Session, or_
from .db import engine, Realtor, PropertyManager, PurchasedPhoneNumber, get_data_access_scope, Tenant, ApartmentListing


def parse_spoken_phone_number(text: str) -> Optional[str]:
    """
    Parse phone numbers from spoken text.
    Handles formats like:
    - "four one two five five five one two three four"
    - "four one two dash five five five dash one two three four"
    - "four one two five five five one two three four" (all words)
    - "412-555-1234" (mixed digits and words)
    """
    import re
    
    # Dictionary for word-to-digit conversion
    word_to_digit = {
        "zero": "0", "oh": "0", "o": "0",
        "one": "1", "won": "1",
        "two": "2", "to": "2", "too": "2",
        "three": "3", "tree": "3",
        "four": "4", "for": "4", "fore": "4",
        "five": "5", "fife": "5",
        "six": "6", "sicks": "6",
        "seven": "7",
        "eight": "8", "ate": "8",
        "nine": "9", "nein": "9"
    }
    
    text_lower = text.lower().strip()
    
    # If it's already all digits, skip word parsing
    if re.match(r'^[\d\s\-\+\(\)\.]+$', text):
        return None  # Let normal normalization handle it
    
    # Try to find phone number patterns in text
    # Look for sequences of number words or digits
    words = re.findall(r'\b\w+\b', text_lower)
    
    # Convert words to digits
    digits = []
    for word in words:
        if word in word_to_digit:
            digits.append(word_to_digit[word])
        elif word.isdigit():
            digits.append(word)
        elif word in ["dash", "hyphen", "-", "dot", ".", "point"]:
            continue  # Skip separators
        else:
            # If we hit a non-number word, check if we have enough digits
            if len(digits) >= 10:
                break
            # If we have some digits but hit a non-number, might be a different context
            if len(digits) > 0 and len(digits) < 10:
                digits = []  # Reset, might not be a phone number
    
    # If we found 10 or 11 digits, return them
    if len(digits) >= 10:
        phone_digits = "".join(digits)
        if len(phone_digits) == 11 and phone_digits.startswith("1"):
            return f"+{phone_digits}"
        elif len(phone_digits) == 10:
            return f"+1{phone_digits}"
        elif len(phone_digits) > 11:
            # Take last 10 digits (in case of extra words)
            return f"+1{phone_digits[-10:]}"
    
    return None


def normalize_phone_number(phone_number: str) -> str:
    """
    Normalize phone number to E.164 format (+14128992517).
    
    Handles various formats:
    - Written: "+1 (412) 899 2517", "14128992517", "+14128992517", "(412) 555-1234"
    - Spoken: "four one two five five five one two three four"
    - Mixed: "412 five five five 1234"
    - International formats
    """
    import re
    
    if not phone_number or not isinstance(phone_number, str):
        return phone_number.strip() if phone_number else ""
    
    original = phone_number.strip()
    
    # Remove whatsapp: prefix if present
    if original.startswith("whatsapp:"):
        original = original.replace("whatsapp:", "")
    
    # Try parsing as spoken number first
    spoken_parsed = parse_spoken_phone_number(original)
    if spoken_parsed:
        return spoken_parsed
    
    # Remove common separators and words
    # Remove words like "phone", "number", "call", "at", etc.
    text = re.sub(r'\b(phone|number|call|at|extension|ext)\b', '', original, flags=re.IGNORECASE)
    
    # Extract all digits and + sign
    normalized = ""
    for char in text:
        if char.isdigit() or char == "+":
            normalized += char
    
    # Handle empty result
    if not normalized:
        return original.strip()
    
    # Ensure it starts with +
    if normalized.startswith("+"):
        # Already has +, check if valid
        if len(normalized) == 12 and normalized.startswith("+1") and normalized[2:].isdigit():
            return normalized  # Perfect format: +1XXXXXXXXXX
        elif len(normalized) == 13 and normalized.startswith("+1") and normalized[2:].isdigit():
            return normalized  # +1XXXXXXXXXXX (11 digits after +1, take last 10)
        elif len(normalized) > 13 and normalized.startswith("+1"):
            # Too many digits, take last 10
            return f"+1{normalized[-10:]}"
        else:
            return normalized  # Return as-is, might be international
    elif normalized.startswith("1") and len(normalized) == 11:
        # US number without + prefix: 1XXXXXXXXXX
        return f"+{normalized}"
    elif len(normalized) == 10:
        # US number without country code: XXXXXXXXXX
        return f"+1{normalized}"
    elif len(normalized) == 11 and normalized.startswith("1"):
        # 11 digits starting with 1: 1XXXXXXXXXX
        return f"+{normalized}"
    elif len(normalized) > 11:
        # Too many digits, try to extract valid US number
        # Look for pattern: 1 followed by 10 digits, or just 10 digits
        match = re.search(r'1?(\d{10})', normalized)
        if match:
            return f"+1{match.group(1)}"
        # Take last 10 digits
        return f"+1{normalized[-10:]}"
    else:
        # Return as-is if we can't normalize (let validation catch it)
        return original.strip()


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
    
    Enhanced with fuzzy matching and flexible phone number parsing.
    Handles spoken phone numbers, partial matches, and various formats.
    
    When a tenant calls/texts the bot, we need to identify:
    1. Who they are (tenant record)
    2. Which property they live in
    3. Which PM manages that property
    
    Args:
        phone_number: Tenant's phone number (can be spoken, written, or normalized)
        email: Tenant's email address (case-insensitive, partial match)
        name: Tenant's name (case-insensitive, partial match, handles nicknames)
        property_manager_id: Optional PM ID to limit search scope (for data isolation)
    
    Returns:
        Dict with tenant info, property info, and PM info, or None if not found
    """
    with Session(engine) as session:
        # Build query with filters
        query = select(Tenant)
        conditions = []
        
        # Phone number match (with fuzzy matching)
        if phone_number:
            # Try multiple normalization strategies
            normalized_phone = normalize_phone_number(phone_number)
            
            # Exact match
            conditions.append(Tenant.phone_number == normalized_phone)
            
            # Also try matching with normalization on database side (for stored numbers in different formats)
            # This handles cases where numbers might be stored without +1, with spaces, etc.
            # We'll do this in Python after fetching, not in SQL (for performance)
        
        # Email match (case-insensitive, partial)
        if email:
            email_clean = email.strip().lower()
            # Exact match
            conditions.append(Tenant.email.ilike(email_clean))
            # Partial match (in case of typos or extra spaces)
            conditions.append(Tenant.email.ilike(f"%{email_clean.replace(' ', '')}%"))
        
        # Name match (case-insensitive, partial, handles nicknames)
        if name:
            name_clean = name.strip()
            # Remove common titles and suffixes
            name_parts = re.sub(r'\b(mr|mrs|ms|miss|dr|prof)\b\.?\s*', '', name_clean, flags=re.IGNORECASE)
            name_parts = re.sub(r'\b(jr|sr|ii|iii|iv)\b\.?$', '', name_parts, flags=re.IGNORECASE)
            name_parts = name_parts.strip()
            
            if name_parts:
                # Full name match
                conditions.append(Tenant.name.ilike(f"%{name_parts}%"))
                # First name only (if multiple words)
                first_name = name_parts.split()[0] if name_parts.split() else name_parts
                if len(first_name) >= 2:  # Only if first name is at least 2 chars
                    conditions.append(Tenant.name.ilike(f"{first_name}%"))
                # Last name only (if multiple words)
                if len(name_parts.split()) > 1:
                    last_name = name_parts.split()[-1]
                    if len(last_name) >= 2:
                        conditions.append(Tenant.name.ilike(f"%{last_name}%"))
        
        if not conditions:
            print("❌ No identification criteria provided (phone, email, or name)")
            return None
        
        # Combine conditions with OR (match any provided criteria)
        query = query.where(or_(*conditions))
        
        # Filter by PM if provided (for data isolation)
        if property_manager_id:
            query = query.where(Tenant.property_manager_id == property_manager_id)
        
        # Filter only active tenants
        query = query.where(Tenant.is_active == True)
        
        # Execute query
        tenants = session.exec(query).all()
        
        if not tenants:
            print(f"❌ No tenant found matching criteria (phone={phone_number}, email={email}, name={name})")
            # Try fuzzy phone matching if exact match failed
            if phone_number:
                return _try_fuzzy_phone_match(phone_number, property_manager_id, session)
            return None
        
        # Score and rank matches
        scored_tenants = []
        for t in tenants:
            score = 0
            
            # Phone match scoring
            if phone_number:
                normalized_input = normalize_phone_number(phone_number)
                normalized_db = normalize_phone_number(t.phone_number) if t.phone_number else ""
                if normalized_input == normalized_db:
                    score += 100  # Exact phone match is highest priority
                elif t.phone_number and normalized_input in normalized_db or normalized_db in normalized_input:
                    score += 50  # Partial phone match
            
            # Email match scoring
            if email:
                email_clean = email.strip().lower()
                if t.email and t.email.lower() == email_clean:
                    score += 80  # Exact email match
                elif t.email and email_clean in t.email.lower() or t.email.lower() in email_clean:
                    score += 40  # Partial email match
            
            # Name match scoring
            if name:
                name_clean = name.strip().lower()
                if t.name.lower() == name_clean:
                    score += 60  # Exact name match
                elif name_clean in t.name.lower():
                    score += 30  # Partial name match (name is substring of tenant name)
                elif t.name.lower() in name_clean:
                    score += 20  # Tenant name is substring of input (nickname)
            
            scored_tenants.append((score, t))
        
        # Sort by score (highest first)
        scored_tenants.sort(key=lambda x: x[0], reverse=True)
        
        # Get best match
        best_score, tenant = scored_tenants[0]
        
        print(f"✅ Found tenant ID {tenant.tenant_id} (match score: {best_score})")
        
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
            "match_score": best_score,  # Include match confidence
        }


def _try_fuzzy_phone_match(
    phone_number: str,
    property_manager_id: Optional[int],
    session: Session
) -> Optional[Dict[str, Any]]:
    """
    Try fuzzy phone number matching when exact match fails.
    Handles cases where numbers might be stored in different formats.
    """
    normalized_input = normalize_phone_number(phone_number)
    
    # Extract just the 10 digits (without country code)
    digits_only = "".join(filter(str.isdigit, normalized_input))
    if len(digits_only) >= 10:
        last_10_digits = digits_only[-10:]  # Last 10 digits
    
        # Get all tenants (or filtered by PM)
        query = select(Tenant).where(Tenant.is_active == True)
        if property_manager_id:
            query = query.where(Tenant.property_manager_id == property_manager_id)
        
        all_tenants = session.exec(query).all()
        
        # Try to match last 10 digits
        for tenant in all_tenants:
            if tenant.phone_number:
                tenant_digits = "".join(filter(str.isdigit, tenant.phone_number))
                if len(tenant_digits) >= 10:
                    tenant_last_10 = tenant_digits[-10:]
                    if tenant_last_10 == last_10_digits:
                        print(f"✅ Found tenant via fuzzy phone match: {tenant.name}")
                        # Get property and PM info
                        property_listing = session.get(ApartmentListing, tenant.property_id)
                        pm = session.get(PropertyManager, tenant.property_manager_id)
                        
                        if property_listing and pm:
                            property_address = property_listing.listing_metadata.get("address") if property_listing.listing_metadata else None
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
                                "match_score": 90,  # High score for fuzzy match
                            }
    
    return None


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
