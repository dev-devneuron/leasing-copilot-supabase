"""
Helper functions to identify user from VAPI call context.
"""

from typing import Optional, Dict, Any
import os
import requests
from .user_lookup import get_user_from_phone_number

VAPI_API_KEY = os.getenv("VAPI_API_KEY") or os.getenv("VAPI_API_KEY2")
VAPI_BASE_URL = "https://api.vapi.ai"


def get_phone_number_from_vapi_call(call_id: Optional[str] = None) -> Optional[str]:
    """
    Get phone number from VAPI call ID.
    
    Args:
        call_id: VAPI call ID (if available in request)
    
    Returns:
        Phone number or None
    """
    if not call_id:
        return None
    
    try:
        headers = {"Authorization": f"Bearer {VAPI_API_KEY}"}
        response = requests.get(
            f"{VAPI_BASE_URL}/call/{call_id}",
            headers=headers
        )
        if response.status_code == 200:
            call_data = response.json()
            # VAPI call object may have phoneNumberId
            phone_number_id = call_data.get("phoneNumberId")
            if phone_number_id:
                return get_phone_number_from_id(phone_number_id)
    except Exception as e:
        print(f"Error getting phone number from VAPI call: {e}")
    
    return None


def get_phone_number_from_id(phone_number_id: str) -> Optional[str]:
    """
    Get phone number from VAPI phone number ID.
    
    Args:
        phone_number_id: VAPI phone number ID
    
    Returns:
        Phone number or None
    """
    try:
        headers = {"Authorization": f"Bearer {VAPI_API_KEY}"}
        response = requests.get(
            f"{VAPI_BASE_URL}/phone-number/{phone_number_id}",
            headers=headers
        )
        if response.status_code == 200:
            phone_data = response.json()
            return phone_data.get("number")
    except Exception as e:
        print(f"Error getting phone number from ID: {e}")
    
    return None


def identify_user_from_vapi_request(request_body: Dict[str, Any], request_headers: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """
    Identify user from VAPI request by trying multiple methods.
    
    Methods tried:
    1. Direct phone number in request body/headers
    2. Phone number from call ID
    3. Phone number from phone number ID
    
    Args:
        request_body: Request body as dict
        request_headers: Request headers as dict
    
    Returns:
        User info dict with source_ids, or None
    """
    from .user_lookup import get_user_from_phone_number
    
    print(f"🔍 Identifying user from VAPI request...")
    print(f"   Request body keys: {list(request_body.keys())}")
    print(f"   Request headers keys: {list(request_headers.keys())}")
    
    # Method 1: Direct phone number
    phone_number = (
        request_body.get("phoneNumber") or
        request_body.get("phone_number") or
        request_body.get("to") or
        request_body.get("from") or
        request_headers.get("x-phone-number") or
        request_headers.get("phone-number")
    )
    
    if phone_number:
        print(f"   📞 Found phone number in request: {phone_number}")
        return get_user_from_phone_number(phone_number)
    
    # Method 2: From call ID
    call_id = request_body.get("callId") or request_body.get("call_id")
    if call_id:
        print(f"   📞 Found call ID: {call_id}, fetching phone number...")
        phone_number = get_phone_number_from_vapi_call(call_id)
        if phone_number:
            print(f"   📞 Got phone number from call ID: {phone_number}")
            return get_user_from_phone_number(phone_number)
        else:
            print(f"   ⚠️  Could not get phone number from call ID")
    
    # Method 3: From phone number ID
    phone_number_id = request_body.get("phoneNumberId") or request_body.get("phone_number_id")
    if phone_number_id:
        print(f"   📞 Found phone number ID: {phone_number_id}, fetching phone number...")
        phone_number = get_phone_number_from_id(phone_number_id)
        if phone_number:
            print(f"   📞 Got phone number from phone number ID: {phone_number}")
            return get_user_from_phone_number(phone_number)
        else:
            print(f"   ⚠️  Could not get phone number from phone number ID")
    
    print(f"   ❌ Could not identify user - no phone number found in request")
    return None

