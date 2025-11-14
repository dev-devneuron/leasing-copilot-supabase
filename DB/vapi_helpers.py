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
            headers=headers,
            timeout=5  # Add timeout to avoid hanging
        )
        if response.status_code == 200:
            call_data = response.json()
            print(f"   📋 Call data keys: {list(call_data.keys())}")
            
            # Try to get phone number directly from call data first
            phone_number = call_data.get("phoneNumber") or call_data.get("phone_number")
            if phone_number:
                print(f"   ✅ Found phone number directly in call data: {phone_number}")
                return phone_number
            
            # Fallback: Get phone number via phoneNumberId
            phone_number_id = call_data.get("phoneNumberId") or call_data.get("phone_number_id")
            if phone_number_id:
                print(f"   📋 Found phoneNumberId: {phone_number_id}, fetching phone number...")
                phone_number = get_phone_number_from_id(phone_number_id)
                if phone_number:
                    print(f"   ✅ Got phone number from phoneNumberId: {phone_number}")
                    return phone_number
            else:
                print(f"   ⚠️  No phoneNumberId found in call data")
        else:
            print(f"   ⚠️  Vapi API returned status {response.status_code}: {response.text}")
    except requests.exceptions.Timeout:
        print(f"   ⚠️  Timeout fetching call data from Vapi API")
    except Exception as e:
        print(f"   ⚠️  Error getting phone number from VAPI call: {e}")
    
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


# Import the cache from vapi.app (will be set at runtime)
_call_phone_cache: Dict[str, str] = {}

def set_call_phone_cache(cache: Dict[str, str]) -> None:
    """Set the call phone cache from the main app."""
    global _call_phone_cache
    _call_phone_cache = cache

def identify_user_from_vapi_request(request_body: Dict[str, Any], request_headers: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """
    Identify user from VAPI request by trying multiple methods.
    
    Methods tried (in priority order):
    1. Twilio destination number (twilio.to for calls, twilio.To for SMS) - MOST RELIABLE
    2. Direct phone number in request body/headers
    3. Phone number from call ID
    4. Phone number from phone number ID
    
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
    
    # Method 1: Custom headers from Vapi tool configuration (MOST RELIABLE)
    # These are auto-populated by Vapi using {{call.toNumber}}, {{call.fromNumber}}, {{call.id}}
    # FastAPI normalizes headers to lowercase, so check both variations
    call_to_number = None
    for header_key in ["x-call-to-number", "X-Call-To-Number", "X-CALL-TO-NUMBER"]:
        if header_key in request_headers:
            call_to_number = request_headers[header_key]
            break
    if call_to_number:
        print(f"   📞 Found destination number in X-Call-To-Number header: {call_to_number}")
        user_info = get_user_from_phone_number(call_to_number)
        if user_info:
            return user_info
        else:
            print(f"   ⚠️  Destination number {call_to_number} not found in database")
    
    # Also store call ID from header for cache lookup
    call_id_from_header = None
    for header_key in ["x-call-id", "X-Call-ID", "X-CALL-ID"]:
        if header_key in request_headers:
            call_id_from_header = request_headers[header_key]
            break
    if call_id_from_header and call_id_from_header in _call_phone_cache:
        cached_number = _call_phone_cache[call_id_from_header]
        print(f"   📞 Found phone number from cached call ID: {cached_number}")
        user_info = get_user_from_phone_number(cached_number)
        if user_info:
            return user_info
    
    # Method 2: Twilio destination number (from webhook events)
    # This is the number that was called/texted (YOUR number), which identifies the PM/Realtor
    twilio_data = request_body.get("twilio", {})
    if isinstance(twilio_data, dict):
        # For calls: twilio.to
        # For SMS: twilio.To
        destination_number = twilio_data.get("to") or twilio_data.get("To")
        if destination_number:
            print(f"   📞 Found destination number in twilio.to/To: {destination_number}")
            user_info = get_user_from_phone_number(destination_number)
            if user_info:
                return user_info
            else:
                print(f"   ⚠️  Destination number {destination_number} not found in database")
    
    # Method 2: Direct phone number in request body/headers
    # Check tool call arguments first (toNumber/fromNumber from Vapi tool parameters)
    tool_call_args = None
    if isinstance(request_body.get("message"), dict):
        tool_calls = request_body["message"].get("toolCalls") or request_body["message"].get("toolCallList") or []
        if tool_calls and len(tool_calls) > 0:
            # Get arguments from first tool call
            tool_call = tool_calls[0]
            if isinstance(tool_call, dict):
                tool_call_args = tool_call.get("function", {}).get("arguments")
                if isinstance(tool_call_args, str):
                    import json
                    try:
                        tool_call_args = json.loads(tool_call_args)
                    except:
                        pass
    
    phone_number = (
        # Check tool call arguments (toNumber is the destination number - what we need!)
        (tool_call_args and tool_call_args.get("toNumber")) if tool_call_args else None or
        (tool_call_args and tool_call_args.get("to_number")) if tool_call_args else None or
        # Direct in request body
        request_body.get("phoneNumber") or
        request_body.get("phone_number") or
        request_body.get("toNumber") or
        request_body.get("to_number") or
        request_body.get("to") or
        request_body.get("from") or
        request_headers.get("x-phone-number") or
        request_headers.get("phone-number")
    )
    
    if phone_number:
        print(f"   📞 Found phone number in request: {phone_number}")
        return get_user_from_phone_number(phone_number)
    
    # Method 3: From call ID (check body, headers, and cache)
    # Try multiple locations in the request body
    call_id = (
        request_body.get("callId") or 
        request_body.get("call_id") or 
        request_body.get("call") or
        (request_body.get("call") and request_body["call"].get("id")) if isinstance(request_body.get("call"), dict) else None or
        request_body.get("callId") or  # Top level
        request_body.get("id") or  # Top level ID (might be call ID)
        # Check inside message object
        (request_body.get("message") and request_body["message"].get("callId")) if isinstance(request_body.get("message"), dict) else None or
        (request_body.get("message") and request_body["message"].get("call_id")) if isinstance(request_body.get("message"), dict) else None or
        # Check headers
        request_headers.get("x-call-id") or
        request_headers.get("call-id") or
        request_headers.get("vapi-call-id") or
        request_headers.get("x-vapi-call-id")
    )
    
    if call_id:
        print(f"   📞 Found call ID: {call_id}")
        
        # First check in-memory cache (fastest)
        if call_id in _call_phone_cache:
            phone_number = _call_phone_cache[call_id]
            print(f"   ✅ Got phone number from cache: {phone_number}")
            user_info = get_user_from_phone_number(phone_number)
            if user_info:
                return user_info
        
        # Fallback: Fetch from Vapi API
        print(f"   📞 Call ID not in cache, fetching from Vapi API...")
        phone_number = get_phone_number_from_vapi_call(call_id)
        if phone_number:
            print(f"   ✅ Got phone number from Vapi API: {phone_number}")
            # Store in cache for future requests
            _call_phone_cache[call_id] = phone_number
            user_info = get_user_from_phone_number(phone_number)
            if user_info:
                return user_info
            else:
                print(f"   ⚠️  Phone number {phone_number} not found in database")
        else:
            print(f"   ⚠️  Could not get phone number from call ID {call_id}")
    else:
        print(f"   ⚠️  No call ID found in request body or headers")
    
    # Method 4: From phone number ID (check cache first, then API)
    phone_number_id = (
        request_body.get("phoneNumberId") or 
        request_body.get("phone_number_id") or
        (request_body.get("message") and request_body["message"].get("phoneNumberId")) if isinstance(request_body.get("message"), dict) else None
    )
    if phone_number_id:
        print(f"   📞 Found phone number ID: {phone_number_id}")
        
        # Check cache first (from webhook)
        if phone_number_id in _call_phone_cache:  # Reuse the same cache dict
            phone_number = _call_phone_cache[phone_number_id]
            print(f"   ✅ Got phone number from cache: {phone_number}")
            user_info = get_user_from_phone_number(phone_number)
            if user_info:
                return user_info
        
        # Fallback: Fetch from API
        print(f"   📞 Phone number ID not in cache, fetching from Vapi API...")
        phone_number = get_phone_number_from_id(phone_number_id)
        if phone_number:
            print(f"   ✅ Got phone number from phone number ID: {phone_number}")
            # Store in cache
            _call_phone_cache[phone_number_id] = phone_number
            user_info = get_user_from_phone_number(phone_number)
            if user_info:
                return user_info
        else:
            print(f"   ⚠️  Could not get phone number from phone number ID")
    
    print(f"   ❌ Could not identify user - no phone number found in request")
    return None

