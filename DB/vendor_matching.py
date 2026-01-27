"""
Vendor Matching Module

This module handles matching vendors to maintenance requests based on:
- Property association
- Service category (plumbing, electrical, etc.)
- Priority/urgency
- Operating hours
- Emergency availability
- Priority order (1st call, 2nd call, etc.)
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, time
import pytz
from sqlmodel import Session, select
from .db import (
    Vendor,
    PropertyVendor,
    MaintenanceRequest,
    PropertyVendorSettings,
    ApartmentListing,
    engine
)


# Category mapping: maintenance request category -> vendor service type
CATEGORY_TO_SERVICE_TYPE = {
    "plumbing": "plumber",
    "plumber": "plumber",
    "water": "plumber",
    "leak": "plumber",
    "electrical": "electrician",
    "electrician": "electrician",
    "power": "electrician",
    "outlet": "electrician",
    "carpentry": "carpenter",
    "carpenter": "carpenter",
    "wood": "carpenter",
    "hvac": "hvac",
    "heating": "hvac",
    "cooling": "hvac",
    "air": "hvac",
    "appliance": "general",
    "general": "general",
    "other": "general",
    "emergency": "emergency",
}

# Keywords in issue description that indicate specific service types
# Used when category is "other" or unclear
DESCRIPTION_KEYWORDS = {
    "carpenter": ["cupboard", "cabinet", "cabinet", "furniture", "wood", "wooden", "door", "drawer", "shelf", "shelves", "cabinet door", "broken door", "broken drawer", "broken shelf", "broken cabinet", "broken cupboard"],
    "plumber": ["water", "leak", "leaking", "pipe", "faucet", "tap", "toilet", "sink", "drain", "clog", "dripping", "flood"],
    "electrician": ["power", "outlet", "switch", "light", "wiring", "circuit", "breaker", "electrical", "electric", "fuse", "spark"],
    "hvac": ["heat", "heating", "cool", "cooling", "air", "ac", "a/c", "furnace", "thermostat", "vent", "ventilation"],
}


def map_category_to_service_type(
    category: Optional[str], 
    priority: str = "normal",
    issue_description: Optional[str] = None
) -> str:
    """
    Map maintenance request category to vendor service type.
    
    Args:
        category: Maintenance request category (e.g., "plumbing", "electrical")
        priority: Request priority (if "urgent", may map to "emergency")
        issue_description: Optional issue description for keyword-based detection
    
    Returns:
        Service type string (e.g., "plumber", "electrician", "emergency")
    """
    if not category:
        # If no category, try to infer from description
        if issue_description:
            return infer_service_type_from_description(issue_description)
        return "general"
    
    category_lower = category.lower().strip()
    
    # Check for emergency priority (but only if category doesn't clearly indicate a specific service)
    if priority.lower() == "urgent" and category_lower in ["other", "general"]:
        # For "other" + urgent, try description first, then fall back to emergency
        if issue_description:
            inferred = infer_service_type_from_description(issue_description)
            if inferred != "general":
                return inferred
        return "emergency"
    
    # Direct mapping
    if category_lower in CATEGORY_TO_SERVICE_TYPE:
        mapped = CATEGORY_TO_SERVICE_TYPE[category_lower]
        # If mapped to "general" or "other", try description-based inference
        if mapped in ["general", "other"] and issue_description:
            inferred = infer_service_type_from_description(issue_description)
            if inferred != "general":
                return inferred
        return mapped
    
    # Partial matching
    for key, service_type in CATEGORY_TO_SERVICE_TYPE.items():
        if key in category_lower:
            return service_type
    
    # Fallback: try description if category didn't match
    if issue_description:
        return infer_service_type_from_description(issue_description)
    
    return "general"


def infer_service_type_from_description(description: Optional[str]) -> str:
    """
    Infer service type from issue description using keyword matching.
    
    Args:
        description: Issue description text
    
    Returns:
        Service type string (e.g., "carpenter", "plumber", "general")
    """
    if not description:
        return "general"
    
    description_lower = description.lower()
    
    # Check each service type's keywords
    for service_type, keywords in DESCRIPTION_KEYWORDS.items():
        for keyword in keywords:
            if keyword in description_lower:
                print(f"🔍 [VENDOR MATCHING] Detected '{service_type}' from description keyword: '{keyword}'")
                return service_type
    
    return "general"


def is_vendor_available_now(vendor: Vendor, timezone_str: str = "America/New_York") -> bool:
    """
    Check if vendor is currently available based on operating hours.
    
    Args:
        vendor: Vendor object
        timezone_str: Timezone string (defaults to vendor's timezone or America/New_York)
    
    Returns:
        True if vendor is currently within operating hours, False otherwise
    """
    if not vendor.operating_hours_start or not vendor.operating_hours_end:
        # No operating hours set - assume always available
        return True
    
    try:
        tz = pytz.timezone(vendor.timezone or timezone_str)
        now = datetime.now(tz).time()
        
        start_time = vendor.operating_hours_start
        end_time = vendor.operating_hours_end
        
        # Handle overnight hours (e.g., 22:00 - 06:00)
        if start_time > end_time:
            # Overnight shift
            return now >= start_time or now <= end_time
        else:
            # Normal day shift
            return start_time <= now <= end_time
    except Exception as e:
        print(f"⚠️  Error checking vendor availability: {e}")
        # On error, assume available
        return True


def get_vendors_for_property(
    property_id: int,
    service_type: str,
    session: Session,
    emergency_only: bool = False,
    include_inactive: bool = False,
    exclude_opted_out: bool = True
) -> List[Dict[str, Any]]:
    """
    Get all vendors for a property matching a service type, sorted by priority.
    
    Args:
        property_id: Property ID
        service_type: Service type to match (e.g., "plumber", "electrician")
        session: Database session
        emergency_only: If True, only return vendors with emergency_available=True
        include_inactive: If True, include inactive vendors
        exclude_opted_out: If True, exclude vendors who have opted out (default: True)
    
    Returns:
        List of vendor dictionaries with priority, sorted by priority (ascending)
    """
    print(f"🔍 [VENDOR MATCHING] get_vendors_for_property: property_id={property_id}, service_type={service_type}, emergency_only={emergency_only}, include_inactive={include_inactive}")
    
    # Build query
    query = (
        select(PropertyVendor, Vendor)
        .join(Vendor, PropertyVendor.vendor_id == Vendor.vendor_id)
        .where(PropertyVendor.property_id == property_id)
        .where(PropertyVendor.service_type == service_type)
    )
    
    if not include_inactive:
        query = query.where(PropertyVendor.is_active == True).where(Vendor.is_active == True)
    
    if emergency_only:
        query = query.where(Vendor.emergency_available == True)
    
    # Exclude opted-out vendors (unless explicitly requested)
    if exclude_opted_out:
        query = query.where(Vendor.opted_out == False)
    
    # Order by priority (lower = higher priority)
    query = query.order_by(PropertyVendor.priority.asc())
    
    results = session.exec(query).all()
    
    print(f"   Query returned {len(results)} result(s)")
    
    # Debug: Check what vendors exist for this property (any service type)
    debug_query = (
        select(PropertyVendor, Vendor)
        .join(Vendor, PropertyVendor.vendor_id == Vendor.vendor_id)
        .where(PropertyVendor.property_id == property_id)
    )
    all_property_vendors = session.exec(debug_query).all()
    print(f"   DEBUG: Total vendors linked to property {property_id}: {len(all_property_vendors)}")
    for pv, v in all_property_vendors:
        print(f"      - Vendor {v.vendor_id} ({v.name}): service_type={pv.service_type}, is_active={pv.is_active}, vendor.is_active={v.is_active}, opted_out={v.opted_out}, emergency_available={v.emergency_available}")
    
    vendors = []
    for property_vendor, vendor in results:
        vendors.append({
            "vendor_id": vendor.vendor_id,
            "vendor": vendor,
            "property_vendor": property_vendor,
            "priority": property_vendor.priority,
            "name": vendor.name,
            "phone_number": vendor.phone_number,
            "backup_phone": vendor.backup_phone,
            "email": vendor.email,
            "emergency_available": vendor.emergency_available,
            "operating_hours_start": vendor.operating_hours_start,
            "operating_hours_end": vendor.operating_hours_end,
            "timezone": vendor.timezone,
            "notes": vendor.notes,
        })
    
    return vendors


def match_vendors_to_maintenance_request(
    maintenance_request: MaintenanceRequest,
    session: Session,
    respect_operating_hours: bool = True
) -> List[Dict[str, Any]]:
    """
    Match vendors to a maintenance request based on property, category, and priority.
    
    This is the main matching function that:
    1. Maps request category to service type
    2. Fetches vendors for the property
    3. Filters by emergency availability if urgent
    4. Sorts by priority
    5. Optionally filters by current availability (operating hours)
    
    Args:
        maintenance_request: MaintenanceRequest object
        session: Database session
        respect_operating_hours: If True, filter out vendors not currently in operating hours
    
    Returns:
        List of vendor dictionaries sorted by priority, ready for call queue
    """
    print(f"🔍 [VENDOR MATCHING] Matching vendors for maintenance request {maintenance_request.maintenance_request_id}")
    print(f"   Property ID: {maintenance_request.property_id}")
    print(f"   Category: {maintenance_request.category}")
    print(f"   Priority: {maintenance_request.priority}")
    
    # Check if emergency
    is_emergency = maintenance_request.priority.lower() == "urgent"
    print(f"   Emergency: {is_emergency}")
    
    # Map category to service type (with description-based inference for better accuracy)
    service_type = map_category_to_service_type(
        maintenance_request.category,
        maintenance_request.priority,
        maintenance_request.issue_description
    )
    print(f"   Mapped service type: {service_type}")

    # Initialize vendors list so we can safely check `if not vendors` below
    vendors: list = []
    
    # If urgent mapped to "emergency" but no vendors found, try mapping without priority
    original_service_type = service_type
    if is_emergency and service_type == "emergency":
        # Try the actual category first (with description inference)
        category_service_type = map_category_to_service_type(
            maintenance_request.category,
            "normal",  # Don't use urgent priority for mapping
            maintenance_request.issue_description
        )
        if category_service_type != "emergency":
            print(f"   Also trying category-based service type: {category_service_type}")
            vendors = get_vendors_for_property(
                property_id=maintenance_request.property_id,
                service_type=category_service_type,
                session=session,
                emergency_only=False,  # More lenient
                include_inactive=False
            )
            if vendors:
                print(f"   Found {len(vendors)} vendor(s) for category-based service type '{category_service_type}'")
                service_type = category_service_type  # Use this instead
    
    # If still no vendors, try the original service type
    if not vendors:
        vendors = get_vendors_for_property(
            property_id=maintenance_request.property_id,
            service_type=original_service_type,
            session=session,
            emergency_only=is_emergency,
            include_inactive=False
        )
        print(f"   Found {len(vendors)} vendor(s) for service type '{original_service_type}' (emergency_only={is_emergency})")
        
        # If emergency request but no emergency vendors found, try without emergency filter
        if is_emergency and not vendors:
            print(f"⚠️  [VENDOR MATCHING] No emergency vendors found, trying without emergency filter")
            vendors = get_vendors_for_property(
                property_id=maintenance_request.property_id,
                service_type=original_service_type,
                session=session,
                emergency_only=False,  # More lenient: allow non-emergency vendors
                include_inactive=False
            )
            print(f"   Found {len(vendors)} vendor(s) without emergency filter")
    
    # If no vendors found for specific service type, try "general"
    if not vendors and service_type != "general":
        print(f"⚠️  [VENDOR MATCHING] No {service_type} vendors found, trying 'general' service type")
        vendors = get_vendors_for_property(
            property_id=maintenance_request.property_id,
            service_type="general",
            session=session,
            emergency_only=False,  # More lenient: don't require emergency for general
            include_inactive=False
        )
        print(f"   Found {len(vendors)} 'general' vendor(s)")
    
    # If still no vendors, ONLY try "any service type" fallback if service_type is "general" or "emergency"
    # For specific service types (carpenter, plumber, electrician, hvac), DO NOT fall back to wrong service types
    if not vendors:
        if service_type in ["general", "emergency"]:
            # Only for general/emergency: allow fallback to any vendor
            print(f"⚠️  [VENDOR MATCHING] No vendors found for '{service_type}' or 'general', trying ANY service type for property")
            from .db import PropertyVendor, Vendor
            query = (
                select(PropertyVendor, Vendor)
                .join(Vendor, PropertyVendor.vendor_id == Vendor.vendor_id)
                .where(PropertyVendor.property_id == maintenance_request.property_id)
                .where(PropertyVendor.is_active == True)
                .where(Vendor.is_active == True)
                .where(Vendor.opted_out == False)
            )
            
            query = query.order_by(PropertyVendor.priority.asc())
            results = session.exec(query).all()
            
            print(f"   Found {len(results)} vendor(s) for property (any service type)")
            
            for property_vendor, vendor in results:
                vendors.append({
                    "vendor_id": vendor.vendor_id,
                    "vendor": vendor,
                    "property_vendor": property_vendor,
                    "priority": property_vendor.priority,
                    "name": vendor.name,
                    "phone_number": vendor.phone_number,
                    "backup_phone": vendor.backup_phone,
                    "email": vendor.email,
                    "emergency_available": vendor.emergency_available,
                    "operating_hours_start": vendor.operating_hours_start,
                    "operating_hours_end": vendor.operating_hours_end,
                    "timezone": vendor.timezone,
                    "notes": vendor.notes,
                })
        else:
            # For specific service types (carpenter, plumber, etc.), DO NOT call wrong service type vendors
            print(f"❌ [VENDOR MATCHING] No {service_type} vendors found for property {maintenance_request.property_id}")
            print(f"   NOT falling back to other service types - would call wrong vendor type (e.g., plumber for carpenter job)")
            print(f"   Please add a {service_type} vendor to this property or use 'general' service type vendors")
    
    # Filter by operating hours if requested
    if respect_operating_hours:
        print(f"🕐 [VENDOR MATCHING] Filtering vendors by operating hours")
        available_vendors = []
        unavailable_vendors = []
        
        for vendor_data in vendors:
            vendor = vendor_data["vendor"]
            if is_vendor_available_now(vendor):
                available_vendors.append(vendor_data)
            else:
                unavailable_vendors.append(vendor_data)
        
        print(f"   Available now: {len(available_vendors)}, Unavailable: {len(unavailable_vendors)}")
        
        # Prioritize available vendors, but include unavailable ones at the end
        vendors = available_vendors + unavailable_vendors
    
    # Build vendor queue format
    vendor_queue = []
    for vendor_data in vendors:
        vendor_queue.append({
            "vendor_id": vendor_data["vendor_id"],
            "priority": vendor_data["priority"],
            "name": vendor_data["name"],
        })
    
    print(f"✅ [VENDOR MATCHING] Matched {len(vendors)} vendor(s) for maintenance request {maintenance_request.maintenance_request_id}")
    for i, v in enumerate(vendor_queue, 1):
        print(f"   {i}. Vendor {v['vendor_id']} ({v['name']}) - Priority: {v['priority']}")
    
    return vendors


def get_property_vendor_settings(
    property_id: int,
    session: Session
) -> Optional[PropertyVendorSettings]:
    """
    Get vendor calling settings for a property.
    
    Args:
        property_id: Property ID
        session: Database session
    
    Returns:
        PropertyVendorSettings object or None if not configured
    """
    settings = session.exec(
        select(PropertyVendorSettings).where(
            PropertyVendorSettings.property_id == property_id
        )
    ).first()
    
    return settings


def should_auto_call_vendors(
    maintenance_request: MaintenanceRequest,
    session: Session
) -> bool:
    """
    Determine if vendors should be auto-called for a maintenance request.
    
    Checks property-level settings and request priority.
    
    Args:
        maintenance_request: MaintenanceRequest object
        session: Database session
    
    Returns:
        True if auto-calling should be enabled, False otherwise
    """
    print(f"🔍 [VENDOR MATCHING] Checking if auto-calling should be enabled for request {maintenance_request.maintenance_request_id}")
    
    # Check property settings
    settings = get_property_vendor_settings(maintenance_request.property_id, session)
    
    if settings:
        print(f"   Property settings found: auto_call_enabled={settings.auto_call_enabled}, emergency_only={settings.emergency_only}")
        
        # Check if auto-call is disabled
        if not settings.auto_call_enabled:
            print(f"   ❌ Auto-calling disabled in property settings")
            return False
        
        # Check if emergency-only mode
        if settings.emergency_only:
            is_urgent = maintenance_request.priority.lower() == "urgent"
            print(f"   Emergency-only mode: request priority is '{maintenance_request.priority}' (urgent={is_urgent})")
            return is_urgent
    else:
        print(f"   No property settings found, using request-level setting")
    
    # Default: auto-call enabled (unless explicitly disabled in request)
    result = maintenance_request.vendor_call_automation_enabled
    print(f"   ✅ Auto-calling enabled: {result}")
    return result
