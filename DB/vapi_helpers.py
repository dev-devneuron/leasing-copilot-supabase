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


def get_phone_number_from_vapi_chat(chat_id: Optional[str] = None) -> Optional[str]:
    """
    Get phone number from VAPI chat ID.
    Tries multiple methods:
    1. VAPI API (if available)
    2. Database reverse lookup (chat_id -> phone number via ChatSession)
    
    Args:
        chat_id: VAPI chat ID (if available in request)
    
    Returns:
        Phone number or None
    """
    if not chat_id:
        return None
    
    # Method 1: Try VAPI API (may not be available for chats)
    try:
        headers = {"Authorization": f"Bearer {VAPI_API_KEY}"}
        response = requests.get(
            f"{VAPI_BASE_URL}/chat/{chat_id}",
            headers=headers,
            timeout=5  # Add timeout to avoid hanging
        )
        if response.status_code == 200:
            chat_data = response.json()
            print(f"   📋 Chat data keys: {list(chat_data.keys())}")
            
            # Try to get phone number directly from chat data first
            phone_number = chat_data.get("phoneNumber") or chat_data.get("phone_number")
            if phone_number:
                print(f"   ✅ Found phone number directly in chat data: {phone_number}")
                return phone_number
            
            # Fallback: Get phone number via phoneNumberId
            phone_number_id = chat_data.get("phoneNumberId") or chat_data.get("phone_number_id")
            if phone_number_id:
                print(f"   📋 Found phoneNumberId in chat: {phone_number_id}, fetching phone number...")
                phone_number = get_phone_number_from_id(phone_number_id)
                if phone_number:
                    print(f"   ✅ Got phone number from phoneNumberId: {phone_number}")
                    return phone_number
        elif response.status_code == 404:
            print(f"   ⚠️  VAPI chat API endpoint not available (404) - trying database lookup...")
        else:
            print(f"   ⚠️  Vapi API returned status {response.status_code}: {response.text}")
    except requests.exceptions.Timeout:
        print(f"   ⚠️  Timeout fetching chat data from Vapi API - trying database lookup...")
    except Exception as e:
        print(f"   ⚠️  Error calling VAPI chat API: {e} - trying database lookup...")
    
    # Method 2: Database reverse lookup (chat_id -> phone number)
    try:
        from .db import Session, ChatSession, Customer, engine
        from sqlmodel import select
        
        with Session(engine) as session:
            # Find chat session by chat_id
            chat_session = session.exec(
                select(ChatSession).where(ChatSession.chat_id == chat_id)
            ).first()
            
            if chat_session:
                # Get customer from chat session
                customer = session.get(Customer, chat_session.cust_id)
                if customer and customer.contact:
                    print(f"   ✅ Found phone number from database chat session: {customer.contact}")
                    return customer.contact
                else:
                    print(f"   ⚠️  Chat session found but no customer contact")
            else:
                print(f"   ⚠️  No chat session found in database for chat_id: {chat_id}")
    except Exception as e:
        print(f"   ⚠️  Error looking up chat in database: {e}")
    
    return None


# Import the cache from vapi.app (will be set at runtime)
_call_phone_cache: Dict[str, str] = {}
_phone_id_cache: Dict[str, str] = {}
_phone_to_id_cache: Dict[str, str] = {}

def set_call_phone_cache(cache: Dict[str, str]) -> None:
    """Set the call phone cache from the main app."""
    global _call_phone_cache
    _call_phone_cache = cache

def set_phone_caches(phone_id_cache: Dict[str, str], phone_to_id_cache: Dict[str, str]) -> None:
    """Set the phone ID caches from the main app."""
    global _phone_id_cache, _phone_to_id_cache
    _phone_id_cache = phone_id_cache
    _phone_to_id_cache = phone_to_id_cache

def identify_user_from_vapi_request(request_body: Dict[str, Any], request_headers: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """
    Identify user from VAPI request by trying multiple methods.
    Supports both calls and chats.
    
    Methods tried (in priority order):
    1. Custom headers from Vapi phone number inbound settings (x-vapi-to) - MOST RELIABLE
    2. Phone number from call ID (x-call-id header or in body)
    3. Phone number from chat ID (x-chat-id header or in body) - FOR CHATS
    4. Twilio destination number (twilio.to for calls, twilio.To for SMS)
    5. Direct phone number in request body/headers
    6. Phone number from phone number ID
    
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
    
    # Log full request body structure for debugging (limit size)
    import json
    try:
        body_str = json.dumps(request_body, default=str)
        if len(body_str) > 1000:
            print(f"   Request body (first 1000 chars): {body_str[:1000]}...")
        else:
            print(f"   Request body: {body_str}")
    except:
        print(f"   Request body (could not serialize): {request_body}")
    
    # Method 1: Custom headers from Vapi phone number inbound settings (MOST RELIABLE)
    # These are set at phone number level: x-vapi-to={{to}}, x-vapi-from={{from}}
    # FastAPI/Starlette normalizes headers to lowercase, so check lowercase
    header_keys_lower = {k.lower(): v for k, v in request_headers.items()}
    call_to_number = header_keys_lower.get("x-vapi-to")
    
    # Check if header exists but is empty (template variable not populated)
    if call_to_number and call_to_number.strip():
        print(f"   📞 Found destination number in x-vapi-to header: {call_to_number}")
        user_info = get_user_from_phone_number(call_to_number)
        if user_info:
            return user_info
        else:
            print(f"   ⚠️  Destination number {call_to_number} not found in database")
    elif "x-vapi-to" in header_keys_lower:
        print(f"   ⚠️  x-vapi-to header exists but is empty (template variable {{to}} not populated)")
    
    # Method 1b: Use x-call-id header to fetch phone number from Vapi API
    # This is a fallback when x-vapi-to is empty (for calls)
    call_id_from_header = header_keys_lower.get("x-call-id")
    if call_id_from_header:
        print(f"   📞 Found x-call-id header: {call_id_from_header}")
        
        # First check cache
        if call_id_from_header in _call_phone_cache:
            cached_number = _call_phone_cache[call_id_from_header]
            print(f"   ✅ Found phone number from cached call ID: {cached_number}")
            user_info = get_user_from_phone_number(cached_number)
            if user_info:
                return user_info
        
        # Fallback: Fetch from Vapi API
        print(f"   📞 Call ID not in cache, fetching phone number from Vapi API...")
        phone_number = get_phone_number_from_vapi_call(call_id_from_header)
        if phone_number:
            print(f"   ✅ Got phone number from Vapi API using call ID: {phone_number}")
            # Store in cache
            _call_phone_cache[call_id_from_header] = phone_number
            user_info = get_user_from_phone_number(phone_number)
            if user_info:
                return user_info
            else:
                print(f"   ⚠️  Phone number {phone_number} not found in database")
    
    # Method 1c: Check for phoneNumberId in request (works for both calls and chats)
    # This is often available in chat requests
    message_obj_temp = request_body.get("message")
    phone_number_id = (
        request_body.get("phoneNumberId") or 
        request_body.get("phone_number_id") or
        (message_obj_temp and message_obj_temp.get("phoneNumberId")) if isinstance(message_obj_temp, dict) else None or
        (message_obj_temp and message_obj_temp.get("phone_number_id")) if isinstance(message_obj_temp, dict) else None or
        # Check in chat object inside message
        (message_obj_temp and isinstance(message_obj_temp.get("chat"), dict) and message_obj_temp["chat"].get("phoneNumberId")) or
        (message_obj_temp and isinstance(message_obj_temp.get("chat"), dict) and message_obj_temp["chat"].get("phone_number_id")) or
        # Check if phoneNumber is an object with id
        (message_obj_temp and isinstance(message_obj_temp.get("phoneNumber"), dict) and message_obj_temp["phoneNumber"].get("id")) or
        (message_obj_temp and isinstance(message_obj_temp.get("chat"), dict) and isinstance(message_obj_temp["chat"].get("phoneNumber"), dict) and message_obj_temp["chat"]["phoneNumber"].get("id"))
    )
    if phone_number_id:
        print(f"   📞 Found phone number ID: {phone_number_id}")
        
        # Check cache first (from webhook)
        if phone_number_id in _phone_id_cache:
            phone_number = _phone_id_cache[phone_number_id]
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
            _phone_id_cache[phone_number_id] = phone_number
            _phone_to_id_cache[phone_number] = phone_number_id
            user_info = get_user_from_phone_number(phone_number)
            if user_info:
                return user_info
        else:
            print(f"   ⚠️  Could not get phone number from phone number ID")
    
    # Method 1d: Use x-chat-id header to fetch phone number from Vapi API (FOR CHATS)
    # This handles chat-based requests where users interact via chat instead of calls
    chat_id_from_header = header_keys_lower.get("x-chat-id")
    if chat_id_from_header:
        print(f"   💬 Found x-chat-id header: {chat_id_from_header}")
        
        # First check cache (can reuse call_phone_cache since it's just ID -> phone mapping)
        if chat_id_from_header in _call_phone_cache:
            cached_number = _call_phone_cache[chat_id_from_header]
            print(f"   ✅ Found phone number from cached chat ID: {cached_number}")
            user_info = get_user_from_phone_number(cached_number)
            if user_info:
                return user_info
        
        # Fallback: Try to get phone number from chat (API or database)
        print(f"   💬 Chat ID not in cache, trying to get phone number from chat...")
        phone_number = get_phone_number_from_vapi_chat(chat_id_from_header)
        if phone_number:
            print(f"   ✅ Got phone number from chat (API or database): {phone_number}")
            # Store in cache (reuse call_phone_cache for both calls and chats)
            _call_phone_cache[chat_id_from_header] = phone_number
            user_info = get_user_from_phone_number(phone_number)
            if user_info:
                return user_info
            else:
                print(f"   ⚠️  Phone number {phone_number} not found in database")
        else:
            print(f"   ⚠️  Could not get phone number from chat ID {chat_id_from_header} (tried API and database)")
    
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
    # Check message object thoroughly for phone number info
    message_obj = request_body.get("message")
    if isinstance(message_obj, dict):
        print(f"   📋 Checking message object for phone number...")
        print(f"   📋 Message object keys: {list(message_obj.keys())}")
        
        # Check message object for phone number fields
        message_phone = (
            message_obj.get("phoneNumber") or
            message_obj.get("phone_number") or
            message_obj.get("toNumber") or
            message_obj.get("to_number") or
            message_obj.get("to") or
            message_obj.get("from") or
            message_obj.get("fromNumber") or
            message_obj.get("from_number")
        )
        if message_phone:
            print(f"   📞 Found phone number in message object: {message_phone}")
            user_info = get_user_from_phone_number(message_phone)
            if user_info:
                return user_info
        
        # Check if phoneNumber is an object in message
        message_phone_obj = message_obj.get("phoneNumber")
        if isinstance(message_phone_obj, dict):
            print(f"   📋 Found phoneNumber object in message, checking...")
            message_phone_from_obj = (
                message_phone_obj.get("number") or
                message_phone_obj.get("phoneNumber") or
                message_phone_obj.get("id")  # Might be ID, we'll resolve it
            )
            if message_phone_from_obj:
                # If it looks like a phone number (has + or digits), use it directly
                if isinstance(message_phone_from_obj, str) and ('+' in message_phone_from_obj or message_phone_from_obj.replace('-', '').replace(' ', '').isdigit()):
                    print(f"   📞 Found phone number in phoneNumber object: {message_phone_from_obj}")
                    user_info = get_user_from_phone_number(message_phone_from_obj)
                    if user_info:
                        return user_info
                # Otherwise might be an ID
                elif isinstance(message_phone_from_obj, str):
                    print(f"   📋 phoneNumber object has ID, will check phoneNumberId extraction above")
        
        # Check chat object inside message
        chat_obj = message_obj.get("chat")
        if isinstance(chat_obj, dict):
            print(f"   📋 Found chat object in message, checking for phone number...")
            print(f"   📋 Chat object keys: {list(chat_obj.keys())}")
            
            # Log chat object structure for debugging
            try:
                import json
                chat_str = json.dumps(chat_obj, default=str)
                if len(chat_str) > 1000:
                    print(f"   📋 Chat object (first 1000 chars): {chat_str[:1000]}...")
                else:
                    print(f"   📋 Chat object: {chat_str}")
            except Exception as e:
                print(f"   ⚠️  Could not serialize chat object: {e}")
            
            # Try to get phone number from chat object
            chat_phone = (
                chat_obj.get("phoneNumber") or
                chat_obj.get("phone_number") or
                chat_obj.get("toNumber") or
                chat_obj.get("to_number") or
                chat_obj.get("to") or
                chat_obj.get("from") or
                chat_obj.get("fromNumber") or
                chat_obj.get("from_number")
            )
            if chat_phone:
                # If phoneNumber is an object, extract the number
                if isinstance(chat_phone, dict):
                    chat_phone = chat_phone.get("number") or chat_phone.get("phoneNumber") or chat_phone.get("id")
                
                if chat_phone and isinstance(chat_phone, str):
                    print(f"   📞 Found phone number in chat object: {chat_phone}")
                    user_info = get_user_from_phone_number(chat_phone)
                    if user_info:
                        return user_info
            
            # Try to get phoneNumberId from chat object and resolve it
            chat_phone_number_id = (
                chat_obj.get("phoneNumberId") or
                chat_obj.get("phone_number_id") or
                (chat_obj.get("phoneNumber", {}).get("id") if isinstance(chat_obj.get("phoneNumber"), dict) else None)
            )
            if chat_phone_number_id:
                print(f"   📋 Found phoneNumberId in chat object: {chat_phone_number_id}")
                # Check cache first
                if chat_phone_number_id in _phone_id_cache:
                    phone_number = _phone_id_cache[chat_phone_number_id]
                    print(f"   ✅ Got phone number from cache via phoneNumberId: {phone_number}")
                    user_info = get_user_from_phone_number(phone_number)
                    if user_info:
                        return user_info
                
                # Fetch from API
                phone_number = get_phone_number_from_id(chat_phone_number_id)
                if phone_number:
                    print(f"   ✅ Got phone number from phoneNumberId: {phone_number}")
                    _phone_id_cache[chat_phone_number_id] = phone_number
                    _phone_to_id_cache[phone_number] = chat_phone_number_id
                    user_info = get_user_from_phone_number(phone_number)
                    if user_info:
                        return user_info
        
        # Check assistant object inside message (might have phone number info)
        assistant_obj = message_obj.get("assistant")
        if isinstance(assistant_obj, dict):
            print(f"   📋 Found assistant object in message, checking for phone number...")
            assistant_phone = (
                assistant_obj.get("phoneNumber") or
                assistant_obj.get("phone_number") or
                assistant_obj.get("toNumber") or
                assistant_obj.get("to_number")
            )
            if assistant_phone:
                if isinstance(assistant_phone, dict):
                    assistant_phone = assistant_phone.get("number") or assistant_phone.get("phoneNumber")
                if assistant_phone:
                    print(f"   📞 Found phone number in assistant object: {assistant_phone}")
                    user_info = get_user_from_phone_number(assistant_phone)
                    if user_info:
                        return user_info
    
    # Check tool call arguments (toNumber/fromNumber from Vapi tool parameters)
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
        # Check headers (already checked above, but check again for body-based IDs)
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
    
    # Method 3b: From chat ID (check body, headers, and cache) - FOR CHATS
    # Try multiple locations in the request body
    chat_id = (
        request_body.get("chatId") or 
        request_body.get("chat_id") or 
        request_body.get("chat") or
        (request_body.get("chat") and request_body["chat"].get("id")) if isinstance(request_body.get("chat"), dict) else None or
        # Check inside message object
        (request_body.get("message") and request_body["message"].get("chatId")) if isinstance(request_body.get("message"), dict) else None or
        (request_body.get("message") and request_body["message"].get("chat_id")) if isinstance(request_body.get("message"), dict) else None or
        # Check headers (already checked above, but check again for body-based IDs)
        request_headers.get("x-chat-id") or
        request_headers.get("chat-id") or
        request_headers.get("vapi-chat-id") or
        request_headers.get("x-vapi-chat-id")
    )
    
    if chat_id:
        print(f"   💬 Found chat ID: {chat_id}")
        
        # First check in-memory cache (fastest) - reuse call_phone_cache
        if chat_id in _call_phone_cache:
            phone_number = _call_phone_cache[chat_id]
            print(f"   ✅ Got phone number from cache: {phone_number}")
            user_info = get_user_from_phone_number(phone_number)
            if user_info:
                return user_info
        
        # Fallback: Fetch from Vapi API
        print(f"   💬 Chat ID not in cache, fetching from Vapi API...")
        phone_number = get_phone_number_from_vapi_chat(chat_id)
        if phone_number:
            print(f"   ✅ Got phone number from Vapi API: {phone_number}")
            # Store in cache for future requests (reuse call_phone_cache)
            _call_phone_cache[chat_id] = phone_number
            user_info = get_user_from_phone_number(phone_number)
            if user_info:
                return user_info
            else:
                print(f"   ⚠️  Phone number {phone_number} not found in database")
        else:
            print(f"   ⚠️  Could not get phone number from chat ID {chat_id}")
    else:
        print(f"   ⚠️  No call ID or chat ID found in request body or headers")
    
    # Method 4: From phone number ID (check cache first, then API)
    phone_number_id = (
        request_body.get("phoneNumberId") or 
        request_body.get("phone_number_id") or
        (request_body.get("message") and request_body["message"].get("phoneNumberId")) if isinstance(request_body.get("message"), dict) else None
    )
    if phone_number_id:
        print(f"   📞 Found phone number ID: {phone_number_id}")
        
        # Check cache first (from webhook)
        if phone_number_id in _phone_id_cache:
            phone_number = _phone_id_cache[phone_number_id]
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
            _phone_id_cache[phone_number_id] = phone_number
            _phone_to_id_cache[phone_number] = phone_number_id
            user_info = get_user_from_phone_number(phone_number)
            if user_info:
                return user_info
        else:
            print(f"   ⚠️  Could not get phone number from phone number ID")
    
    print(f"   ❌ Could not identify user - no phone number found in request")
    return None

