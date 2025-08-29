# file: twilio_number_service.py

import os
import requests
from fastapi import FastAPI
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

# Load Twilio + Vapi credentials from .env
TWILIO_ACCOUNT_SID = "ACfd1c9eecc6f1a1e119cf3ff00325a5af"
TWILIO_AUTH_TOKEN = "fd7a7291b3bb8dcc9347bc32af4f8aff"
VAPI_API_KEY = "541ffaff-3f6d-4365-9320-0bb171f12bd7"
VAPI_ASSISTANT_ID = "d37218d3-0b5f-4683-87ea-9ed447d925ae"


if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
    raise ValueError("Missing Twilio credentials in .env")

if not VAPI_API_KEY or not VAPI_ASSISTANT_ID:
    raise ValueError("Missing Vapi credentials in .env")

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
app = FastAPI()


@app.post("/buy-number")
def buy_number(area_code: str = "412"):
    """Buy a Twilio number, set Voice/SMS URLs, and link to Vapi bot."""

    # Step 1: Search number
    available = client.available_phone_numbers("US").local.list(area_code=area_code, limit=1)
    if not available:
        return {"error": f"No numbers available for area code {area_code}"}

    number_to_buy = available[0].phone_number

    # Step 2: Purchase number with SMS + Voice webhooks
    purchased = client.incoming_phone_numbers.create(
        phone_number=number_to_buy,
        sms_url=f"https://api.vapi.ai/sms/twilio/{VAPI_ASSISTANT_ID}",
        voice_url="https://api.vapi.ai/twilio/inbound_call",  # correct inbound call URL
    )

    # Step 3: Link with Vapi assistant
    payload = {
        "provider": "twilio",
        "number": purchased.phone_number,
        "twilioAccountSid": TWILIO_ACCOUNT_SID,
        "twilioAuthToken": TWILIO_AUTH_TOKEN,
        "assistantId": VAPI_ASSISTANT_ID,
        "name": "Realtor Bot Number",
    }

    response = requests.post(
        "https://api.vapi.ai/phone-number",
        headers={
            "Authorization": f"Bearer {VAPI_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
    )

    return {
        "twilio_number": purchased.phone_number,
        "twilio_sid": purchased.sid,
        "vapi_response": response.json(),
    }
