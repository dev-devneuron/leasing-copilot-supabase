from fastapi import FastAPI, HTTPException, Form, Request,File,UploadFile,Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Union
from datetime import datetime
import json,os
import numpy as np
from fastapi.encoders import jsonable_encoder
from sqlmodel import select, Session
import httpx
from httpx import TimeoutException
from typing import List, Optional
from dotenv import load_dotenv
from fastapi.responses import FileResponse, RedirectResponse, Response, PlainTextResponse
from google_auth_oauthlib.flow import Flow
from twilio.twiml.messaging_response import MessagingResponse
from contextlib import asynccontextmanager
from db import *
from calendar_utils import GoogleCalendar
from vapi.rag import RAGEngine
from vapi.bounded_usage import MessageLimiter
from config import (
    CREDENTIALS_FILE,
    REDIRECT_URI,
    timeout,
    DAILY_LIMIT,
    TWILIO_PHONE_NUMBER,
    SCOPES
)
from sqlalchemy import update
from fastapi.middleware.cors import CORSMiddleware
from sync import sync_apartment_listings
from auth_module import get_current_realtor_id 
from fastapi import Body
from fastapi import Request
from fastapi.responses import JSONResponse
from sqlmodel import select, Session


load_dotenv()  # Load .env values

VAPI_API_KEY = os.getenv("VAPI_API_KEY")
VAPI_ASSISTANT_ID = os.getenv("VAPI_ASSISTANT_ID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")

rag = RAGEngine()  # pgvector RAG

message_limiter = MessageLimiter(DAILY_LIMIT)
session=Session(engine)

# ------------------ ToolCall Models ------------------ #
class ToolCallFunction(BaseModel):
    name: str
    arguments: Union[str, dict]

class ToolCall(BaseModel):
    id: str
    function: ToolCallFunction

class Message(BaseModel):
    toolCalls: list[ToolCall]

class VapiRequest(BaseModel):
    message: Message


@asynccontextmanager
async def lifespan(app: FastAPI):

    init_vector_db()

    yield  # This is where FastAPI app runs

    print("Shutting down fastapi app...")


app = FastAPI(lifespan=lifespan)
# set orgin here
origins = [
     "https://react-app-form.onrender.com/",
     "https://react-app-form.onrender.com",
     "https://leaseap.com",
     "https://leaseap.com/",
     "https://www.leasap.com",
     "https://www.leasap.com/",
 ]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#------------------ CreateCustomer ----------------#
@app.post("/create_customer/")
def create_customer(request: VapiRequest):
    for tool_call in request.message.toolCalls:
        if tool_call.function.name == "CreateCust":
            args = tool_call.function.arguments
            if isinstance(args, str):
                args = json.loads(args)

            name = args.get("name")
            email = args.get("email")
            contact_number = args.get("contact_number")
            if_tenant = False

            if not contact_number:
                raise HTTPException(status_code=400, detail="Contact number is required")

            # Call helper to create customer
            customer = create_customer_entry(name, email,contact_number, if_tenant)

            return {
                "results": [{
                    "toolCallId": tool_call.id,
                    "result": f"Customer created with ID {customer.id}"
                }]
            }

    raise HTTPException(status_code=400, detail="Invalid tool call")


# ------------------ Query Docs ------------------ #
@app.post("/query_docs/")
def query_docs(request: VapiRequest):


    for tool_call in request.message.toolCalls:
        if tool_call.function.name == "queryDocs":
            args = tool_call.function.arguments
            if isinstance(args, str):
                args = json.loads(args)
            question = args.get("query")
            address = args.get("address")
            if not question:
                raise HTTPException(status_code=400, detail="Missing query text")
            
    print("Address:",address)
    with Session(engine) as session:
        # Step 1: Get count of listings for the given address (case-insensitive)
        count_sql = text("""
        SELECT COUNT(*) 
        FROM apartmentlisting
        WHERE LOWER(listing_metadata->>'address') = LOWER(:addr)
    """).params(addr=address)  
    
        total_matches = session.exec(count_sql).scalar()
        
        if total_matches == 0:
            raise HTTPException(status_code=404, detail="No listings found for given address")
        # Step 2: Choose a random offset
        import random
        random_offset = random.randint(0, total_matches - 1)

        # Step 3: Fetch one random source_id using OFFSET
        source_sql = text("""
    SELECT source_id
    FROM apartmentlisting
    WHERE LOWER(listing_metadata->>'address') = LOWER(:addr)
    OFFSET :offset LIMIT 1
""").params(addr=address, offset=random_offset)

        
        row = session.exec(source_sql).first()
        if row:
            source_id = row[0]
        else:
            source_id = None

    # Step 4: Process tool call

        response = rag.query(question, source_id=source_id)
        return {"results": [{"toolCallId": tool_call.id, "result": response}]}

    raise HTTPException(status_code=400, detail="Invalid tool call")



@app.post("/confirm_address/")
def confirm_apartment(request: VapiRequest):
    for tool_call in request.message.toolCalls:
        if tool_call.function.name == "confirmAddress":
            args = tool_call.function.arguments
            query = args.strip() if isinstance(args, str) else args.get("query", "").strip()
            if not query:
                raise HTTPException(status_code=400, detail="Missing query text")

            print("Query:",query)
            listings = rag.search_apartments(query)
            return {"results": [{"toolCallId": tool_call.id, "result": listings}]}
    raise HTTPException(status_code=400, detail="Invalid tool call")

# ------------------ Search Apartments ------------------ #
@app.post("/search_apartments/")
def search_apartments(request: VapiRequest):
    for tool_call in request.message.toolCalls:
        if tool_call.function.name == "searchApartments":
            args = tool_call.function.arguments
            query = args.strip() if isinstance(args, str) else args.get("query", "").strip()
            if not query:
                raise HTTPException(status_code=400, detail="Missing query text")

            listings = rag.search_apartments(query)
            return {"results": [{"toolCallId": tool_call.id, "result": listings}]}
    raise HTTPException(status_code=400, detail="Invalid tool call")

# ------------------ Calendar Tools ------------------ #
@app.post("/get_date/")
def get_date(request: VapiRequest):
    for tool_call in request.message.toolCalls:
        if tool_call.function.name == "getDate":
            return {
                "results": [
                    {"toolCallId": tool_call.id, "result": {"date": datetime.now().date().isoformat()}}
                ]
            }
    return {"error": "Invalid tool call"}

@app.post("/book_visit/")
def book_visit(request: VapiRequest):
    print("Request:", request)

    for tool_call in request.message.toolCalls:
        if tool_call.function.name == "bookVisit":
            args = tool_call.function.arguments
            if isinstance(args, str):
                args = json.loads(args)

            contact = args.get("contact")
            email = args.get("email")
            date_str = args.get("date")
            address = args.get("address")
            print("Booking:", contact, email, date_str, address)

            if not (contact and email and date_str and address):
                raise HTTPException(status_code=400, detail="Missing required fields")

            # Parse datetime
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
                booking_date = dt.date()
                booking_time = dt.time()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD HH:MM")

            with Session(engine) as session:
                # Find the listing by matching address substring in text
                statement = select(ApartmentListing).where(ApartmentListing.text.contains(address))
                listing = session.exec(statement).first()
                if not listing:
                    raise HTTPException(status_code=404, detail="Listing not found for address")

                # Get source using source_id
                print("Source ID:", listing.source_id)
                statement = select(Source).where(Source.id == listing.source_id)
                source = session.exec(statement).first()
                if not source:
                    raise HTTPException(status_code=404, detail="Source not found")

                # Access realtor_id from source
                realtor_id = source.realtor_id
                print("Realtor ID:", realtor_id)

            # Initialize calendar client with correct token
            calendar = GoogleCalendar(realtor_id)

            # Check availability
            if not calendar.is_time_available(date_str):
                return {"results": [{"toolCallId": tool_call.id, "result": f"Time {date_str} not available."}]}

            # Create calendar event
            summary = f"Apartment Visit for: {address}"
            description = f"Apartment Visit Booking\nEmail: {email}\nAddress: {address}"
            event = calendar.create_event(date_str, summary=summary, email=email, description=description)

            try:
                created = create_booking_entry(address, booking_date, booking_time, contact)
                print("Booking created:", created)
            except Exception as e:
                print("Failed to create booking:", e)

            return {"results": [{"toolCallId": tool_call.id, "result": f"Booking confirmed! Event link: {event.get('htmlLink')}"}]}

    raise HTTPException(status_code=400, detail="Invalid tool call")


@app.post("/get_slots/")
def get_slots(request: VapiRequest):
    for tool_call in request.message.toolCalls:
        if tool_call.function.name == "getAvailableSlots":
            args = tool_call.function.arguments
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {"date": args}

            date = args.get("date")
            address=args.get("address")
            print("Address:",address)
            if not date:
                raise HTTPException(status_code=400, detail="Missing 'date' or 'address' field")
            

            # 1. Find the listing by matching address substring in text
            statement = select(ApartmentListing).where(ApartmentListing.text.contains(address))
            listing = session.exec(statement).first()
            if not listing:
                raise HTTPException(status_code=404, detail="Listing not found for address")

            # 2. Get source using the source_id
            print("Source ID (slots):", listing.source_id)
            statement = select(Source).where(Source.id == listing.source_id)
            source = session.exec(statement).first()
            if not source:
                raise HTTPException(status_code=404, detail="Source not found")

            # 3. Access the realtor_id from the source
            realtor_id = source.realtor_id
            print("Realtor ID (slots):", source.realtor_id)

            # 🧠 3. Initialize calendar client with correct token
            calendar = GoogleCalendar(realtor_id)

  
            slots = calendar.get_free_slots(date)
            return {"results": [{"toolCallId": tool_call.id, "result": f"Available slots on {date}:\n" + ", ".join(slots)}]}
    raise HTTPException(status_code=400, detail="Invalid tool call")


# temp store
temp_state_store = {}


@app.get("/authorize/")
def authorize_realtor(realtor_id: int):
    flow = Flow.from_client_secrets_file(
        CREDENTIALS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    auth_url, state = flow.authorization_url(prompt="consent", include_granted_scopes="true")
    
    temp_state_store[state] = realtor_id  
    return RedirectResponse(auth_url)

@app.get("/oauth2callback")
def oauth2callback(request: Request):
    with Session(engine) as session:
        state = request.query_params.get("state")
        realtor_id = temp_state_store.get(state)

        if not realtor_id:
            return Response(content="Invalid or expired state", status_code=400)

        flow = Flow.from_client_secrets_file(
        CREDENTIALS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
        state=state
        )

        flow.fetch_token(authorization_response=str(request.url))

   
        credentials_data = {
        "token": flow.credentials.token,
        "refresh_token": flow.credentials.refresh_token,
        "token_uri": flow.credentials.token_uri,
        "client_id": flow.credentials.client_id,
        "client_secret": flow.credentials.client_secret,
        "scopes": flow.credentials.scopes,
        "expiry": flow.credentials.expiry.isoformat() if flow.credentials.expiry else None
        }

    
        stmt = (
            update(Realtor)
            .where(Realtor.id == realtor_id)
            .values(credentials=json.dumps(credentials_data))
        )

        session.exec(stmt)
        session.commit()

        return Response(content=f"Authorization successful for realtor_id {realtor_id}.")

# ------------------ Health Check ------------------ #
@app.get("/health")
def health_check():
    return {"status": "healthy", "message": "Lease Copilot is running"}

# ------------------ Twilio WhatsApp ------------------ #

@app.post("/twilio-incoming")
async def twilio_incoming(
    request: Request,
    From: str = Form(...),
    Body: str = Form(...)
):
    if From.startswith("whatsapp:"):
        number = From.replace("whatsapp:", "")
    else:
        number = From
    
    print("Message content:", Body)
    if not message_limiter.check_message_limit(number):
            twiml = MessagingResponse()
            twiml.message(" You've reached the daily message limit. Please try again tomorrow.")
            return Response(content=str(twiml), media_type="application/xml")
    

    # Build the payload
    payload = {
        "assistantId": VAPI_ASSISTANT_ID,
        "input": Body
    }

    # If this number has an ongoing chat, include previousChatId
    prev_chat_id = get_chat_session(number)
    if prev_chat_id:
         payload["previousChatId"] = prev_chat_id

    # Send to Vapi
    #print(f"Sending message to Vapi with previousChatId={prev_chat_id}")

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                "https://api.vapi.ai/chat",
                headers={
                    "Authorization": f"Bearer {VAPI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
    except TimeoutException:
        return PlainTextResponse("Vapi took too long to respond. Please try again later.", status_code=504)
    except Exception as e:
        return PlainTextResponse(f"Unexpected error: {str(e)}", status_code=500)

    if response.status_code not in [200, 201]:
        error_details = response.text  
        #print(f"Vapi error: {response.status_code} - {error_details}")
        return PlainTextResponse(
        f"Error with Vapi: {response.status_code} - {error_details}",
        status_code=response.status_code
        )

    
    response_json = response.json()
    output = response_json.get("output", [])

    if not output or not isinstance(output, list):
        return PlainTextResponse("Vapi returned no output", status_code=500)

   
    vapi_reply = None
    for item in response_json.get("output", []):
        if item.get("role") == "assistant" and "content" in item:
            vapi_reply = item["content"]
            break

    if not vapi_reply:
        return PlainTextResponse("No content in Vapi response", status_code=500)
    

     # Save chat ID to Postgres
    chat_id = response_json.get("id")
    
    if chat_id:
        save_chat_session(number, chat_id)

    # Send reply via Twilio
    
    async with httpx.AsyncClient() as client:
        await client.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json",
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
            data={
                "From": TWILIO_PHONE_NUMBER,
                "To": From,
                "Body": vapi_reply
            }
        )
    return PlainTextResponse( status_code=200)


# ------------------- CRUD ----------------------
@app.post("/sources/", response_model=Source)
def create_source_endpoint(data: Source):
    return create_source( data.realtor_id)


@app.post("/upload_docs/")
async def upload_realtor_files(
    file: UploadFile = File(...),
    realtor_id: int = Form(...)
):
    try:
        content = await file.read()
        file_path = f"realtors/{realtor_id}/{file.filename}"
        
        response = supabase.storage.from_(BUCKET_NAME).upload(
            file_path,
            content,
            file_options={"content-type": file.content_type}
        )

        # Check if response is a dict with an error
        if isinstance(response, dict) and "error" in response:
            raise HTTPException(status_code=500, detail=response["error"]["message"])

        file_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{file_path}"
        
        return {
            "message": "File uploaded successfully",
            "file_url": file_url
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/CreateRealtor")
async def create_realtor_endpoint(
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    contact: str = Form(...),
    #files: List[UploadFile] = File(...),
    #listing_file: Optional[UploadFile] = File(None),
    #listing_api_url: Optional[str] = Form(None)
):
    try:
        # Step 1: Create Supabase Auth user
        auth_response = supabase.auth.sign_up({
            "email": email,
            "password": password
        })

        if not auth_response.user:
            raise HTTPException(status_code=400, detail="Failed to create Supabase user")

        auth_user_id = str(auth_response.user.id)  # Supabase UUID

        # Step 2: Pass auth_user_id into DB creation function
        result = create_realtor_with_files(
            auth_user_id=auth_user_id,
            name=name,
            email=email,
            contact=contact,
            #files=files,
            #listing_file=listing_file,
            #listing_api_url=listing_api_url
        )

        return JSONResponse(content=result, status_code=200)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------------
# Endpoints
# -----------------------------
@app.post("/UploadRules")
async def upload_rules(
    files: list[UploadFile] = File(...),
    realtor_id: int = Depends(get_current_realtor_id)
):
    with Session(engine) as session:
        source = session.exec(select(Source).where(Source.realtor_id == realtor_id)).first()
        if not source:
            raise HTTPException(status_code=404, detail="Source not found for realtor")
    

    uploaded_files = embed_and_store_rules(files, realtor_id, source.id)
    return JSONResponse(
        content={"message": "Rules uploaded & embedded", "files": uploaded_files},
        status_code=200
    )


@app.post("/UploadListings")
async def upload_listings(
    listing_file: UploadFile = File(None),
    listing_api_url: str = Form(None),
    realtor_id: int = Depends(get_current_realtor_id)
):
    print("Realtor Id:",realtor_id)
    embed_and_store_listings(listing_file, listing_api_url, realtor_id)
    return JSONResponse(
        content={"message": "Listings uploaded & embedded"},
        status_code=200
    )





@app.post("/sync-listings")
def run_sync():
    return sync_apartment_listings()


@app.post("/login")
async def login(response: Response, payload: dict = Body(...), request: Request = None):
    email = payload.get("email")
    password = payload.get("password")
    print("received", email, password)
    try:
        # Authenticate with Supabase
        auth_result = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        if not auth_result.user:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        uid = auth_result.user.id
        refresh_token = auth_result.session.refresh_token

        # Get realtor_id from your DB
        with Session(engine) as session:
            realtor = session.exec(
                select(Realtor).where(Realtor.auth_user_id == uid)
            ).first()

            if not realtor:
                raise HTTPException(status_code=404, detail="Realtor not found")
            print(realtor.id)

        # Store refresh token in secure cookie
            response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,  # Use HTTPS in production
            samesite="strict",
            max_age=60 * 60 * 24 * 30  # 30 days
            )
            print("login successful")
            auth_link = f"https://leasing-copilot-mvp.onrender.com/authorize?realtor_id={realtor.id}"
            

        return {
    "message": "Login successful",
    "auth_link":auth_link,
    "access_token": auth_result.session.access_token,  # or wherever your token is
    "refresh_token": refresh_token,
    "user": {
        "uid": uid,
        "realtor_id": realtor.id,
        "name": realtor.name,
        "email": realtor.email
    }
}


    except HTTPException:
        raise  # re-raise known HTTP errors as is

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"Exception during login: {e}\nTraceback:\n{tb}")
        raise HTTPException(status_code=400, detail=f"Login failed: {e}")
    
#----------------------------------------------------
#                   CRUD Operations
#----------------------------------------------------

@app.get("/apartments")
async def get_apartments(realtor_id: int = Depends(get_current_realtor_id)):
    print("apartment was hit:", realtor_id)

    with Session(engine) as session:
        # Step 1: Get source_ids for this realtor
        source_ids = session.exec(
            select(Source.id).where(Source.realtor_id == realtor_id)
        ).all()

        if not source_ids:
            return JSONResponse(content={"message": "No sources found"}, status_code=404)

        # Step 2: Get apartments for these source_ids
        apartments = session.exec(
            select(ApartmentListing).where(ApartmentListing.source_id.in_(source_ids))
        ).all()

        # Step 3: Serialize and exclude embeddings
        def serialize(obj):
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if hasattr(obj, "model_dump"):  # SQLModel / Pydantic model
                data = obj.model_dump()
                data.pop("embedding", None)  # remove embeddings field
                return {k: serialize(v) for k, v in data.items()}
            if isinstance(obj, list):
                return [serialize(i) for i in obj]
            if isinstance(obj, dict):
                obj.pop("embedding", None)
                return {k: serialize(v) for k, v in obj.items()}
            return obj

        apartments_data = serialize(apartments)
        return JSONResponse(content=apartments_data)


@app.get("/bookings")
async def get_bookings(realtor_id: int = Depends(get_current_realtor_id)):
    print("bookings endpoint hit:", realtor_id)

    with Session(engine) as session:
        # Step 1: Get bookings for this realtor directly
        bookings = session.exec(
            select(Booking).where(Booking.realtor_id == realtor_id)
        ).all()

        if not bookings:
            return JSONResponse(content={"message": "You dont have any booking at the moment."}, status_code=404)

        # Step 2: Serialize and remove embeddings if present
        def serialize(obj):
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if hasattr(obj, "model_dump"):  # SQLModel / Pydantic model
                data = obj.model_dump()
                data.pop("embedding", None)  # remove embeddings if exists
                return {k: serialize(v) for k, v in data.items()}
            if isinstance(obj, list):
                return [serialize(i) for i in obj]
            if isinstance(obj, dict):
                obj.pop("embedding", None)
                return {k: serialize(v) for k, v in obj.items()}
            return obj

        bookings_data = serialize(bookings)
        return JSONResponse(content=bookings_data)

from fastapi import Depends, Header, HTTPException
from sqlmodel import Session, select
from supabase import create_client, Client
import jwt  # PyJWT

# Supabase setup
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


TWILIO_ACCOUNT_SID2=os.getenv("TWILIO_ACCOUNT_SID2")
TWILIO_AUTH_TOKEN2=os.getenv("TWILIO_AUTH_TOKEN")
VAPI_API_KEY2=os.getenv("VAPI_API_KEY2")
VAPI_ASSISTANT_ID2=os.getenv("VAPI_ASSISTANT_ID2")

twillio_client = Client(TWILIO_ACCOUNT_SID2, TWILIO_AUTH_TOKEN)

def get_db():
    with Session(engine) as session:
        yield session


@app.post("/buy-number")
def buy_number(
    area_code: str = "412",
    authorization: str = Header(...),  # Extract JWT from frontend Authorization: Bearer <token>
    db: Session = Depends(get_db),
):
    """Buy Twilio number, link with Vapi, and save to DB."""

    # Step 1: Decode JWT → get auth user id (supabase UID)
    try:
        token = authorization.split(" ")[1]
        decoded = jwt.decode(token, options={"verify_signature": False})  # in dev, skip sig verify
        auth_user_id = decoded.get("sub")
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid auth token")

    # Step 2: Get Realtor by auth_user_id
    realtor = db.exec(select(Realtor).where(Realtor.auth_user_id == auth_user_id)).first()
    print("Realtor id recv:",realtor.id)
    if not realtor:
        raise HTTPException(status_code=404, detail="Realtor not found")

    # Step 3: Buy Twilio number
    available = twillio_client.available_phone_numbers("US").local.list(area_code=area_code, limit=1)
    if not available:
        raise HTTPException(status_code=400, detail=f"No numbers available for area code {area_code}")

    number_to_buy = available[0].phone_number

    purchased = twillio_client.incoming_phone_numbers.create(
        phone_number=number_to_buy,
        sms_url=f"https://api.vapi.ai/sms/twilio/{VAPI_ASSISTANT_ID2}",
        voice_url="https://api.vapi.ai/twilio/inbound_call",
    )

    # Step 4: Link with Vapi assistant
    payload = {
        "provider": "twilio",
        "number": purchased.phone_number,
        "twilioAccountSid": TWILIO_ACCOUNT_SID,
        "twilioAuthToken": TWILIO_AUTH_TOKEN,
        "assistantId": VAPI_ASSISTANT_ID,
        "name": f"Realtor {realtor.id} Bot Number",
    }

    response = requests.post(
        "https://api.vapi.ai/phone-number",
        headers={
            "Authorization": f"Bearer {VAPI_API_KEY2}",
            "Content-Type": "application/json",
        },
        json=payload,
    )

    # Step 5: Save to TwilioNumber table
    with Session(engine) as session:
        realtor = session.get(Realtor, realtor.id)  # fetch existing realtor by ID
        if realtor:
            realtor.twilio_number = purchased.phone_number
            realtor.twilio_sid = purchased.sid

            session.add(realtor)
            session.commit()
            session.refresh(realtor)

            return {
            "twilio_number": realtor.twilio_number,
            "twilio_sid": realtor.twilio_sid,
            "realtor_id": realtor.id,
            "vapi_response": response.json(),
            }
        else:
            return {"error": "Realtor not found"}

@app.get("/my-number")
def get_my_number(current_user: dict = Depends(get_current_realtor_id)):
    with SessionLocal() as session:
        realtor = session.query(Realtor).filter(Realtor.id == current_user["id"]).first()
        if not realtor or not realtor.twilio_number:
            raise HTTPException(status_code=404, detail="You havn't bought the number yet!")

        return {"twilio_number": realtor.twilio_number}
    
@app.middleware("http")
async def log_origin(request, call_next):
    print("Origin received:", request.headers.get("origin"))
    return await call_next(request)
