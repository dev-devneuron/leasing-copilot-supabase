"""
Simple WhatsApp test script
Run: python test_data/test_whatsapp.py
"""

import os
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_whatsapp_config():
    """Check if Messaging/Twilio environment variables are set."""
    print("=" * 60)
    print("MESSAGING CONFIGURATION CHECK (SMS/WhatsApp)")
    print("=" * 60)
    
    required_vars = [
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "VAPI_API_KEY",
        "VAPI_ASSISTANT_ID",
    ]
    
    optional_vars = [
        "TWILIO_PHONE_NUMBER",
        "TWILIO_ACCOUNT_SID2",
        "TWILIO_AUTH_TOKEN2",
        "VAPI_API_KEY2",
        "VAPI_ASSISTANT_ID2",
    ]
    
    print("\n✅ Required Variables:")
    all_set = True
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"  ✅ {var}: {'*' * min(len(value), 20)}")
        else:
            print(f"  ❌ {var}: NOT SET")
            all_set = False
    
    print("\n📋 Optional Variables:")
    for var in optional_vars:
        value = os.getenv(var)
        if value:
            print(f"  ✅ {var}: {'*' * min(len(value), 20)}")
        else:
            print(f"  ⚠️  {var}: Not set (optional)")
    
    print("\n" + "=" * 60)
    if all_set:
        print("✅ All required variables are set!")
        print("\nNext steps:")
        print("1. Configure Twilio webhook: https://leasing-copilot-mvp.onrender.com/twilio-incoming")
        print("2. Send SMS or WhatsApp to your Twilio number")
        print("3. Check backend logs for: 'Message content: [your message]'")
        print("4. Verify you receive a reply")
    else:
        print("❌ Missing required variables!")
        print("Set them in Render environment variables or .env file")
    print("=" * 60)

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    test_whatsapp_config()

