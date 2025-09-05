from twilio.rest import Client
from collections import defaultdict
import os
from dotenv import load_dotenv
load_dotenv()

# Load your Twilio creds from env or hardcode for testing
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

def get_all_chats(realtor_number: str):
    # Ensure WhatsApp format
    if not realtor_number.startswith("whatsapp:"):
        realtor_number = f"whatsapp:{realtor_number}"

    print(f"Fetching chats for {realtor_number}...")

    # Fetch all incoming and outgoing messages
    incoming = client.messages.list(to=realtor_number)   # no limit
    print(f"Got {len(incoming)} incoming")

    outgoing = client.messages.list(from_=realtor_number)  # no limit
    print(f"Got {len(outgoing)} outgoing")

    messages = incoming + outgoing
    print(f"Total messages fetched: {len(messages)}")

    # Sort messages by sent date
    messages = sorted(messages, key=lambda m: m.date_sent or datetime.min)

    # Group messages by customer
    chats = {}
    for msg in messages:
        if msg.from_ == realtor_number:
            customer_number = msg.to
        else:
            customer_number = msg.from_

        if customer_number not in chats:
            chats[customer_number] = []

        chats[customer_number].append({
            "from": msg.from_,
            "to": msg.to,
            "body": msg.body,
            "date": msg.date_sent.isoformat() if msg.date_sent else None
        })

    return chats

if __name__ == "__main__":
    chats = get_all_chats("+14155238886")  # sandbox number
    if not chats:
        print("No chats found.")
    else:
        for customer, msgs in chats.items():
            print(f"\n--- Chat with {customer} ---")
            for m in msgs:
                print(f"[{m['date']}] {m['from']} -> {m['to']}: {m['body']}")
