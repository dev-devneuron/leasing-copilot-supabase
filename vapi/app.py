from fastapi import (
    FastAPI,
    HTTPException,
    Form,
    Request,
    File,
    UploadFile,
    Depends,
    Header,
)
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Union
from datetime import datetime
import json, os
import numpy as np
from fastapi.encoders import jsonable_encoder
from sqlmodel import select, Session
import httpx
from httpx import TimeoutException
from dotenv import load_dotenv
from fastapi.responses import (
    FileResponse,
    RedirectResponse,
    Response,
    PlainTextResponse,
)
from google_auth_oauthlib.flow import Flow
from twilio.twiml.messaging_response import MessagingResponse
from contextlib import asynccontextmanager
from DB.db import *
from utils.calendar_utils import GoogleCalendar
from vapi.rag import RAGEngine
from vapi.bounded_usage import MessageLimiter
from config import (
    CREDENTIALS_FILE,
    REDIRECT_URI,
    timeout,
    DAILY_LIMIT,
    TWILIO_PHONE_NUMBER,
    SCOPES,
)
from sqlalchemy import update
from fastapi.middleware.cors import CORSMiddleware
from DB.sync import sync_apartment_listings
from utils.auth_module import get_current_realtor_id, get_current_user_data
from fastapi import Body
from fastapi import Request
from fastapi.responses import JSONResponse
from sqlmodel import select, Session
import jwt
from twilio.rest import Client


load_dotenv()  # Load .env values


VAPI_API_KEY = os.getenv("VAPI_API_KEY")
VAPI_ASSISTANT_ID = os.getenv("VAPI_ASSISTANT_ID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
VAPI_BASE_URL = "https://api.vapi.ai"
headers = {"Authorization": f"Bearer {VAPI_API_KEY}"}


# --------------------------------------------------------------------------------
# --------------------------------------------------------------------------------
# ----------------- For Automatic Number Buying from Twilio ---------------------
TWILIO_ACCOUNT_SID2 = os.getenv("TWILIO_ACCOUNT_SID2")
TWILIO_ACCOUNT_SID1 = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN2 = os.getenv("TWILIO_AUTH_TOKEN2")
TWILIO_AUTH_TOKEN1 = os.getenv("TWILIO_AUTH_TOKEN")
VAPI_API_KEY2 = os.getenv("VAPI_API_KEY2")
VAPI_ASSISTANT_ID2 = os.getenv("VAPI_ASSISTANT_ID2")

twillio_client = Client(TWILIO_ACCOUNT_SID2, TWILIO_AUTH_TOKEN2)
twillio_client1 = Client(TWILIO_ACCOUNT_SID1, TWILIO_AUTH_TOKEN1)

# ---------------------------------------------------------------------
# ---------------------------------------------------------------------


rag = RAGEngine()  # pgvector RAG

message_limiter = MessageLimiter(DAILY_LIMIT)
session = Session(engine)


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
    try:
        init_db()
        print("✅ Database initialized successfully")
    except Exception as e:
        print(f"⚠️ Database initialization failed: {e}")
        print("⚠️ Continuing without database connection...")

    yield  # This is where FastAPI app runs

    print("Shutting down fastapi app...")


app = FastAPI(lifespan=lifespan)

# set origin here
origins = [
    "https://react-app-form.onrender.com",
    "https://leaseap.com",
    "https://www.leasap.com",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:8080",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:8080",
    # Add your frontend URL here if it's different from the above
]

# Add CORS middleware with proper configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)


# ------------------ CreateCustomer ----------------#
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
                raise HTTPException(
                    status_code=400, detail="Contact number is required"
                )

            # Call helper to create customer
            customer = create_customer_entry(name, email, contact_number, if_tenant)

            return {
                "results": [
                    {
                        "toolCallId": tool_call.id,
                        "result": f"Customer created with ID {customer.id}",
                    }
                ]
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

    print("Address:", address)
    with Session(engine) as session:
        # Step 1: Get count of listings for the given address (case-insensitive)
        count_sql = text(
            """
        SELECT COUNT(*) 
        FROM apartmentlisting
        WHERE LOWER(listing_metadata->>'address') = LOWER(:addr)
    """
        ).params(addr=address)

        total_matches = session.exec(count_sql).scalar()

        if total_matches == 0:
            raise HTTPException(
                status_code=404, detail="No listings found for given address"
            )
        # Step 2: Choose a random offset
        import random

        random_offset = random.randint(0, total_matches - 1)

        # Step 3: Fetch one random source_id using OFFSET
        source_sql = text(
            """
    SELECT source_id
    FROM apartmentlisting
    WHERE LOWER(listing_metadata->>'address') = LOWER(:addr)
    OFFSET :offset LIMIT 1
"""
        ).params(addr=address, offset=random_offset)

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
            query = (
                args.strip() if isinstance(args, str) else args.get("query", "").strip()
            )
            if not query:
                raise HTTPException(status_code=400, detail="Missing query text")

            print("Query:", query)
            listings = rag.search_apartments(query)
            return {"results": [{"toolCallId": tool_call.id, "result": listings}]}
    raise HTTPException(status_code=400, detail="Invalid tool call")


# ------------------ Search Apartments ------------------ #
@app.post("/search_apartments/")
def search_apartments(request: VapiRequest):
    for tool_call in request.message.toolCalls:
        if tool_call.function.name == "searchApartments":
            args = tool_call.function.arguments
            query = (
                args.strip() if isinstance(args, str) else args.get("query", "").strip()
            )
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
                    {
                        "toolCallId": tool_call.id,
                        "result": {"date": datetime.now().date().isoformat()},
                    }
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
                raise HTTPException(
                    status_code=400, detail="Invalid date format. Use YYYY-MM-DD HH:MM"
                )

            with Session(engine) as session:
                # Find the listing by matching address substring in text
                statement = select(ApartmentListing).where(
                    ApartmentListing.text.contains(address)
                )
                listing = session.exec(statement).first()
                if not listing:
                    raise HTTPException(
                        status_code=404, detail="Listing not found for address"
                    )

                # Get source using source_id
                print("Source ID:", listing.source_id)
                statement = select(Source).where(Source.source_id == listing.source_id)
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
                return {
                    "results": [
                        {
                            "toolCallId": tool_call.id,
                            "result": f"Time {date_str} not available.",
                        }
                    ]
                }

            # Create calendar event
            summary = f"Apartment Visit for: {address}"
            description = f"Apartment Visit Booking\nEmail: {email}\nAddress: {address}"
            event = calendar.create_event(
                date_str, summary=summary, email=email, description=description
            )

            try:
                created = create_booking_entry(
                    address, booking_date, booking_time, contact
                )
                print("Booking created:", created)
            except Exception as e:
                print("Failed to create booking:", e)

            return {
                "results": [
                    {
                        "toolCallId": tool_call.id,
                        "result": f"Booking confirmed! Event link: {event.get('htmlLink')}",
                    }
                ]
            }

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
            address = args.get("address")
            print("Address:", address)
            if not date:
                raise HTTPException(
                    status_code=400, detail="Missing 'date' or 'address' field"
                )

            # 1. Find the listing by matching address substring in text
            statement = select(ApartmentListing).where(
                ApartmentListing.text.contains(address)
            )
            listing = session.exec(statement).first()
            if not listing:
                raise HTTPException(
                    status_code=404, detail="Listing not found for address"
                )

            # 2. Get source using the source_id
            print("Source ID (slots):", listing.source_id)
            statement = select(Source).where(Source.source_id == listing.source_id)
            source = session.exec(statement).first()
            if not source:
                raise HTTPException(status_code=404, detail="Source not found")

            # 3. Access the realtor_id from the source
            realtor_id = source.realtor_id
            print("Realtor ID (slots):", source.realtor_id)

            # 🧠 3. Initialize calendar client with correct token
            calendar = GoogleCalendar(realtor_id)

            slots = calendar.get_free_slots(date)
            return {
                "results": [
                    {
                        "toolCallId": tool_call.id,
                        "result": f"Available slots on {date}:\n" + ", ".join(slots),
                    }
                ]
            }
    raise HTTPException(status_code=400, detail="Invalid tool call")


# temp store
temp_state_store = {}


# -------------------- Google Calendar ------------------------------------
@app.get("/authorize/")
def authorize_realtor(realtor_id: int):
    flow = Flow.from_client_secrets_file(
        CREDENTIALS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI
    )
    auth_url, state = flow.authorization_url(
        prompt="consent", include_granted_scopes="true"
    )

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
            CREDENTIALS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI, state=state
        )

        flow.fetch_token(authorization_response=str(request.url))

        credentials_data = {
            "token": flow.credentials.token,
            "refresh_token": flow.credentials.refresh_token,
            "token_uri": flow.credentials.token_uri,
            "client_id": flow.credentials.client_id,
            "client_secret": flow.credentials.client_secret,
            "scopes": flow.credentials.scopes,
            "expiry": (
                flow.credentials.expiry.isoformat() if flow.credentials.expiry else None
            ),
        }

        stmt = (
            update(Realtor)
            .where(Realtor.realtor_id == realtor_id)
            .values(credentials=json.dumps(credentials_data))
        )

        session.exec(stmt)
        session.commit()

        return Response(
            content=f"Authorization successful for realtor_id {realtor_id}."
        )


# ------------------ Health Check ------------------ #
@app.get("/health")
def health_check():
    return {"status": "healthy", "message": "Lease Copilot is running"}


# ------------------ Twilio WhatsApp ------------------ #
# specifically for whatsapp chat bot
@app.post("/twilio-incoming")
async def twilio_incoming(
    request: Request, From: str = Form(...), Body: str = Form(...)
):
    if From.startswith("whatsapp:"):
        number = From.replace("whatsapp:", "")
    else:
        number = From

    print("Message content:", Body)
    if not message_limiter.check_message_limit(number):
        twiml = MessagingResponse()
        twiml.message(
            " You've reached the daily message limit. Please try again tomorrow."
        )
        return Response(content=str(twiml), media_type="application/xml")

    # Build the payload
    payload = {"assistantId": VAPI_ASSISTANT_ID, "input": Body}

    # If this number has an ongoing chat, include previousChatId
    prev_chat_id = get_chat_session(number)
    if prev_chat_id:
        payload["previousChatId"] = prev_chat_id

    # Send to Vapi

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                "https://api.vapi.ai/chat",
                headers={
                    "Authorization": f"Bearer {VAPI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
    except TimeoutException:
        return PlainTextResponse(
            "Vapi took too long to respond. Please try again later.", status_code=504
        )
    except Exception as e:
        return PlainTextResponse(f"Unexpected error: {str(e)}", status_code=500)

    if response.status_code not in [200, 201]:
        error_details = response.text
        return PlainTextResponse(
            f"Error with Vapi: {response.status_code} - {error_details}",
            status_code=response.status_code,
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
            data={"From": TWILIO_PHONE_NUMBER, "To": From, "Body": vapi_reply},
        )
    return PlainTextResponse(status_code=200)


# ------------------- CRUD ----------------------
@app.post("/sources/", response_model=Source)
def create_source_endpoint(data: Source):
    return create_source(data.realtor_id)


@app.post("/upload_docs/")
async def upload_realtor_files(
    file: UploadFile = File(...), realtor_id: int = Form(...)
):
    try:
        content = await file.read()
        file_path = f"realtors/{realtor_id}/{file.filename}"

        response = supabase.storage.from_(BUCKET_NAME).upload(
            file_path, content, file_options={"content-type": file.content_type}
        )

        # Check if response is a dict with an error
        if isinstance(response, dict) and "error" in response:
            raise HTTPException(status_code=500, detail=response["error"]["message"])

        file_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{file_path}"

        return {"message": "File uploaded successfully", "file_url": file_url}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/CreatePropertyManager")
async def create_property_manager_endpoint(
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    contact: str = Form(...),
    company_name: str = Form(None),
):
    """Create a new Property Manager."""
    try:
        # Step 1: Create Supabase Auth user
        auth_response = supabase.auth.sign_up({"email": email, "password": password})

        if not auth_response.user:
            raise HTTPException(
                status_code=400, detail="Failed to create Supabase user"
            )

        auth_user_id = str(auth_response.user.id)  # Supabase UUID

        # Step 2: Pass auth_user_id into DB creation function
        result = create_property_manager(
            auth_user_id=auth_user_id,
            name=name,
            email=email,
            contact=contact,
            company_name=company_name,
        )

        return JSONResponse(content=result, status_code=200)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/CreateRealtor")
async def create_realtor_endpoint(
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    contact: str = Form(...),
    property_manager_id: int = Form(None),
):
    """Create a new Realtor (standalone or under a Property Manager)."""
    try:
        # Step 1: Create Supabase Auth user
        auth_response = supabase.auth.sign_up({"email": email, "password": password})

        if not auth_response.user:
            raise HTTPException(
                status_code=400, detail="Failed to create Supabase user"
            )

        auth_user_id = str(auth_response.user.id)  # Supabase UUID

        # Step 2: Pass auth_user_id into DB creation function
        result = create_realtor(
            auth_user_id=auth_user_id,
            name=name,
            email=email,
            contact=contact,
            property_manager_id=property_manager_id,
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
    realtor_id: int = Depends(get_current_realtor_id),
):
    with Session(engine) as session:
        source = session.exec(
            select(Source).where(Source.realtor_id == realtor_id)
        ).first()
        if not source:
            raise HTTPException(status_code=404, detail="Source not found for realtor")

    uploaded_files = embed_and_store_rules(files, realtor_id, source.source_id)
    return JSONResponse(
        content={"message": "Rules uploaded & embedded", "files": uploaded_files},
        status_code=200,
    )


@app.post("/UploadListings")
async def upload_listings(
    listing_file: UploadFile = File(None),
    listing_api_url: str = Form(None),
    realtor_id: int = Depends(get_current_realtor_id),
):
    print("Realtor Id:", realtor_id)
    embed_and_store_listings(listing_file, listing_api_url, realtor_id)
    return JSONResponse(
        content={"message": "Listings uploaded & embedded"}, status_code=200
    )


@app.post("/sync-listings")
def run_sync():
    return sync_apartment_listings()


@app.options("/login")
async def options_login(request: Request):
    """Handle CORS preflight for login endpoint."""
    origin = request.headers.get("Origin", "*")
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": origin if origin in origins else origins[0] if origins else "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Credentials": "true",
        }
    )

@app.post("/login")
async def login_realtor(response: Response, payload: dict = Body(...), request: Request = None):
    """Login endpoint for Realtors (standalone or managed)."""
    email = payload.get("email")
    password = payload.get("password")
    print("Realtor login attempt:", email)
    
    try:
        result = authenticate_realtor(email, password)
        
        # Store refresh token in secure cookie
        response.set_cookie(
            key="refresh_token",
            value=result["refresh_token"],
            httponly=True,
            secure=False,  # Set to False for HTTP, True for HTTPS in production
            samesite="lax",  # Changed from "strict" to "lax" for better compatibility
            max_age=60 * 60 * 24 * 30,  # 30 days
        )
        
        print("Realtor login successful")
        return result

    except HTTPException:
        raise  # re-raise known HTTP errors as is

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"Exception during realtor login: {e}\nTraceback:\n{tb}")
        raise HTTPException(status_code=400, detail=f"Realtor login failed: {e}")


@app.options("/property-manager-login")
async def options_property_manager_login(request: Request):
    """Handle CORS preflight for property manager login endpoint."""
    origin = request.headers.get("Origin", "*")
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": origin if origin in origins else origins[0] if origins else "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Credentials": "true",
        }
    )

@app.post("/property-manager-login")
async def login_property_manager(response: Response, payload: dict = Body(...), request: Request = None):
    """Login endpoint for Property Managers."""
    email = payload.get("email")
    password = payload.get("password")
    print("Property Manager login attempt:", email)
    
    try:
        result = authenticate_property_manager(email, password)
        
        # Store refresh token in secure cookie
        response.set_cookie(
            key="refresh_token",
            value=result["refresh_token"],
            httponly=True,
            secure=False,  # Set to False for HTTP, True for HTTPS in production
            samesite="lax",  # Changed from "strict" to "lax" for better compatibility
            max_age=60 * 60 * 24 * 30,  # 30 days
        )
        
        print("Property Manager login successful")
        return result

    except HTTPException:
        raise  # re-raise known HTTP errors as is

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"Exception during property manager login: {e}\nTraceback:\n{tb}")
        raise HTTPException(status_code=400, detail=f"Property Manager login failed: {e}")


# ----------------------------------------------------
#                   CRUD Operations
# ----------------------------------------------------


@app.get("/apartments")
async def get_apartments(user_data: dict = Depends(get_current_user_data)):
    """Get apartments based on user type and data access scope.
    
    - Property Managers: See all properties from their own Source + all managed realtors' Sources
    - Realtors: See only properties from their own Source
    """
    user_type = user_data["user_type"]
    user_id = user_data["id"]
    
    print(f"Getting apartments for {user_type} ID: {user_id}")

    # Get data access scope
    access_scope = get_data_access_scope(user_type, user_id)
    source_ids = access_scope["source_ids"]

    if not source_ids:
        return JSONResponse(
            content={"message": "No sources found for this user", "apartments": []}, status_code=200
        )

    with Session(engine) as session:
        # Get apartments for accessible source_ids
        apartments = session.exec(
            select(ApartmentListing).where(ApartmentListing.source_id.in_(source_ids))
        ).all()
        
        # Get all relevant sources in one query
        sources = session.exec(
            select(Source).where(Source.source_id.in_(source_ids))
        ).all()
        
        # Create a mapping of source_id to source for quick lookup
        source_map = {s.source_id: s for s in sources}

        # Transform into frontend-friendly shape with ownership info
        result = []
        for apt in apartments:
            meta = apt.listing_metadata or {}
            source = source_map.get(apt.source_id)
            
            # Get owner information
            owner_info = {}
            if source and source.property_manager_id:
                pm = session.exec(
                    select(PropertyManager).where(PropertyManager.property_manager_id == source.property_manager_id)
                ).first()
                if pm:
                    owner_info = {
                        "owner_type": "property_manager",
                        "owner_id": pm.property_manager_id,
                        "owner_name": pm.name,
                        "owner_email": pm.email,
                    }
            
            if source and source.realtor_id:
                realtor = session.exec(
                    select(Realtor).where(Realtor.realtor_id == source.realtor_id)
                ).first()
                if realtor:
                    owner_info = {
                        "owner_type": "realtor",
                        "owner_id": realtor.realtor_id,
                        "owner_name": realtor.name,
                        "owner_email": realtor.email,
                        "is_standalone": realtor.is_standalone,
                        "property_manager_id": realtor.property_manager_id,
                    }
            
            # Include all metadata fields + essential info
            property_result = {
                "id": apt.id,
                "source_id": apt.source_id,
                # Core property information
                "listing_id": meta.get("listing_id"),
                "address": meta.get("address"),
                "price": meta.get("price"),
                "bedrooms": meta.get("bedrooms"),
                "bathrooms": meta.get("bathrooms"),
                "square_feet": meta.get("square_feet"),
                "lot_size_sqft": meta.get("lot_size_sqft"),
                "year_built": meta.get("year_built"),
                "property_type": meta.get("property_type"),
                "listing_status": meta.get("listing_status"),
                "days_on_market": meta.get("days_on_market"),
                "listing_date": meta.get("listing_date"),
                # Agent information
                "agent": meta.get("agent"),
                # Features array
                "features": meta.get("features", []),
                # Legacy fields (for backward compatibility)
                "description": meta.get("description"),
                "image_url": meta.get("image_url"),
                # Owner/assignment information
                **owner_info,
                "is_assigned": True if owner_info.get("owner_type") == "realtor" else False,
                "assigned_to_realtor_id": owner_info.get("owner_id") if owner_info.get("owner_type") == "realtor" else None,
                "assigned_to_realtor_name": owner_info.get("owner_name") if owner_info.get("owner_type") == "realtor" else None,
                # Full metadata (if needed for advanced use cases)
                "full_metadata": meta
            }
            result.append(property_result)

        return JSONResponse(content=result)


@app.get("/managed-realtors")
async def get_managed_realtors_endpoint(user_data: dict = Depends(get_current_user_data)):
    """Get managed realtors (only for Property Managers)."""
    user_type = user_data["user_type"]
    user_id = user_data["id"]
    
    if user_type != "property_manager":
        raise HTTPException(
            status_code=403, 
            detail="Only Property Managers can access this endpoint"
        )
    
    from DB.db import get_managed_realtors as fetch_managed_realtors
    realtors = fetch_managed_realtors(user_id)
    return JSONResponse(content={"managed_realtors": realtors})


@app.get("/property-manager/realtors")
async def get_property_manager_realtors(user_data: dict = Depends(get_current_user_data)):
    """Get managed realtors for Property Managers (frontend endpoint)."""
    user_type = user_data["user_type"]
    user_id = user_data["id"]
    
    if user_type != "property_manager":
        raise HTTPException(
            status_code=403, 
            detail="Only Property Managers can access this endpoint"
        )
    
    from DB.db import get_managed_realtors as fetch_managed_realtors
    realtors = fetch_managed_realtors(user_id)
    # Transform to match frontend expectations
    realtors_data = [
        {
            "id": r["id"],
            "name": r["name"],
            "email": r["email"],
            "status": "active",  # Default status
        }
        for r in realtors
    ]
    return JSONResponse(content={"realtors": realtors_data})


@app.post("/property-manager/add-realtor")
async def add_realtor_endpoint(
    payload: dict = Body(...),
    user_data: dict = Depends(get_current_user_data)
):
    """Add a new realtor under a Property Manager."""
    user_type = user_data["user_type"]
    property_manager_id = user_data["id"]
    
    if user_type != "property_manager":
        raise HTTPException(
            status_code=403, 
            detail="Only Property Managers can add realtors"
        )
    
    name = payload.get("name")
    email = payload.get("email")
    password = payload.get("password")
    
    if not all([name, email, password]):
        raise HTTPException(
            status_code=400,
            detail="Missing required fields: name, email, password"
        )
    
    # Use a default contact if not provided
    contact = payload.get("contact", "TBD")
    
    try:
        # Step 1: Create Supabase Auth user
        auth_response = supabase.auth.sign_up({"email": email, "password": password})
        
        if not auth_response.user:
            raise HTTPException(
                status_code=400, detail="Failed to create Supabase user"
            )
        
        auth_user_id = str(auth_response.user.id)  # Supabase UUID
        
        # Step 2: Create realtor in database under this property manager
        from DB.db import create_realtor
        result = create_realtor(
            auth_user_id=auth_user_id,
            name=name,
            email=email,
            contact=contact,
            property_manager_id=property_manager_id,
        )
        
        return JSONResponse(content={
            "message": "Realtor added successfully!",
            "realtor": result.get("realtor", {})
        }, status_code=200)
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"Exception adding realtor: {e}\nTraceback:\n{tb}")
        raise HTTPException(status_code=500, detail=f"Failed to add realtor: {str(e)}")


@app.get("/user-profile")
async def get_user_profile(user_data: dict = Depends(get_current_user_data)):
    """Get current user's profile information."""
    return JSONResponse(content={"user": user_data})


@app.get("/property-manager/properties-by-realtor")
async def get_properties_by_realtor(user_data: dict = Depends(get_current_user_data)):
    """Get properties grouped by realtor (Property Managers only).
    
    Returns properties organized by which realtor they belong to,
    plus properties directly owned by the Property Manager.
    """
    user_type = user_data["user_type"]
    property_manager_id = user_data["id"]
    
    if user_type != "property_manager":
        raise HTTPException(
            status_code=403, 
            detail="Only Property Managers can access this endpoint"
        )
    
    with Session(engine) as session:
        # Get all managed realtors
        realtors = session.exec(
            select(Realtor).where(Realtor.property_manager_id == property_manager_id)
        ).all()
        
        result = {
            "property_manager_properties": [],
            "realtor_properties": {},
            "summary": {
                "total_properties": 0,
                "property_manager_count": 0,
                "realtor_counts": {}
            }
        }
        
        # Get Property Manager's own properties
        pm_sources = session.exec(
            select(Source).where(Source.property_manager_id == property_manager_id)
        ).all()
        
        pm_source_ids = [s.source_id for s in pm_sources]
        if pm_source_ids:
            pm_apartments = session.exec(
                select(ApartmentListing).where(ApartmentListing.source_id.in_(pm_source_ids))
            ).all()
            
            for apt in pm_apartments:
                meta = apt.listing_metadata or {}
                result["property_manager_properties"].append({
                    "id": apt.id,
                    "source_id": apt.source_id,
                    "listing_id": meta.get("listing_id"),
                    "address": meta.get("address"),
                    "price": meta.get("price"),
                    "bedrooms": meta.get("bedrooms"),
                    "bathrooms": meta.get("bathrooms"),
                    "square_feet": meta.get("square_feet"),
                    "lot_size_sqft": meta.get("lot_size_sqft"),
                    "year_built": meta.get("year_built"),
                    "property_type": meta.get("property_type"),
                    "listing_status": meta.get("listing_status"),
                    "days_on_market": meta.get("days_on_market"),
                    "listing_date": meta.get("listing_date"),
                    "agent": meta.get("agent"),
                    "features": meta.get("features", []),
                    "description": meta.get("description"),
                    "image_url": meta.get("image_url"),
                })
        
        result["summary"]["property_manager_count"] = len(result["property_manager_properties"])
        
        # Get properties for each realtor
        for realtor in realtors:
            realtor_sources = session.exec(
                select(Source).where(Source.realtor_id == realtor.realtor_id)
            ).all()
            
            realtor_source_ids = [s.source_id for s in realtor_sources]
            if realtor_source_ids:
                realtor_apartments = session.exec(
                    select(ApartmentListing).where(ApartmentListing.source_id.in_(realtor_source_ids))
                ).all()
                
                realtor_props = []
                for apt in realtor_apartments:
                    meta = apt.listing_metadata or {}
                    realtor_props.append({
                        "id": apt.id,
                        "source_id": apt.source_id,
                        "listing_id": meta.get("listing_id"),
                        "address": meta.get("address"),
                        "price": meta.get("price"),
                        "bedrooms": meta.get("bedrooms"),
                        "bathrooms": meta.get("bathrooms"),
                        "square_feet": meta.get("square_feet"),
                        "lot_size_sqft": meta.get("lot_size_sqft"),
                        "year_built": meta.get("year_built"),
                        "property_type": meta.get("property_type"),
                        "listing_status": meta.get("listing_status"),
                        "days_on_market": meta.get("days_on_market"),
                        "listing_date": meta.get("listing_date"),
                        "agent": meta.get("agent"),
                        "features": meta.get("features", []),
                        "description": meta.get("description"),
                        "image_url": meta.get("image_url"),
                    })
                
                result["realtor_properties"][str(realtor.realtor_id)] = {
                    "realtor_id": realtor.realtor_id,
                    "realtor_name": realtor.name,
                    "realtor_email": realtor.email,
                    "properties": realtor_props,
                    "count": len(realtor_props),
                }
                
                result["summary"]["realtor_counts"][str(realtor.realtor_id)] = {
                    "realtor_name": realtor.name,
                    "count": len(realtor_props),
                }
        
        result["summary"]["total_properties"] = (
            result["summary"]["property_manager_count"] + 
            sum(rp["count"] for rp in result["realtor_properties"].values())
        )
        
        return JSONResponse(content=result)


@app.get("/property-manager/assignments")
async def get_property_assignments(user_data: dict = Depends(get_current_user_data)):
    """Get property assignments view for Property Managers.
    
    Shows all properties with clear assignment information:
    - Properties owned by PM (unassigned)
    - Properties assigned to each realtor
    """
    user_type = user_data["user_type"]
    property_manager_id = user_data["id"]
    
    if user_type != "property_manager":
        raise HTTPException(
            status_code=403,
            detail="Only Property Managers can access this endpoint"
        )
    
    with Session(engine) as session:
        # Get all managed realtors
        realtors = session.exec(
            select(Realtor).where(Realtor.property_manager_id == property_manager_id)
        ).all()
        
        # Get PM's sources
        pm_sources = session.exec(
            select(Source).where(Source.property_manager_id == property_manager_id)
        ).all()
        pm_source_ids = [s.source_id for s in pm_sources]
        
        # Get all properties (PM's + all realtors')
        all_source_ids = pm_source_ids.copy()
        realtor_sources_map = {}  # realtor_id -> [source_ids]
        
        for realtor in realtors:
            realtor_sources = session.exec(
                select(Source).where(Source.realtor_id == realtor.realtor_id)
            ).all()
            realtor_source_ids = [s.source_id for s in realtor_sources]
            realtor_sources_map[realtor.realtor_id] = realtor_source_ids
            all_source_ids.extend(realtor_source_ids)
        
        if not all_source_ids:
            return JSONResponse(content={
                "unassigned_properties": [],
                "assigned_properties": {},
                "summary": {
                    "total_properties": 0,
                    "unassigned_count": 0,
                    "assigned_count": 0,
                    "realtor_counts": {}
                }
            })
        
        # Get all properties
        all_properties = session.exec(
            select(ApartmentListing).where(ApartmentListing.source_id.in_(all_source_ids))
        ).all()
        
        # Categorize properties
        unassigned_properties = []
        assigned_properties = {}  # realtor_id -> [properties]
        
        for prop in all_properties:
            meta = prop.listing_metadata or {}
            
            property_data = {
                "id": prop.id,
                "source_id": prop.source_id,
                # Core property information
                "listing_id": meta.get("listing_id"),
                "address": meta.get("address"),
                "price": meta.get("price"),
                "bedrooms": meta.get("bedrooms"),
                "bathrooms": meta.get("bathrooms"),
                "square_feet": meta.get("square_feet"),
                "lot_size_sqft": meta.get("lot_size_sqft"),
                "year_built": meta.get("year_built"),
                "property_type": meta.get("property_type"),
                "listing_status": meta.get("listing_status"),
                "days_on_market": meta.get("days_on_market"),
                "listing_date": meta.get("listing_date"),
                # Agent information
                "agent": meta.get("agent"),
                # Features array
                "features": meta.get("features", []),
                # Legacy fields
                "description": meta.get("description"),
                "image_url": meta.get("image_url"),
            }
            
            # Check if property belongs to PM (unassigned)
            if prop.source_id in pm_source_ids:
                unassigned_properties.append(property_data)
            else:
                # Find which realtor this belongs to
                for realtor_id, source_ids in realtor_sources_map.items():
                    if prop.source_id in source_ids:
                        if realtor_id not in assigned_properties:
                            assigned_properties[realtor_id] = []
                        assigned_properties[realtor_id].append(property_data)
                        break
        
        # Format assigned properties with realtor info
        assigned_properties_formatted = {}
        for realtor in realtors:
            if realtor.realtor_id in assigned_properties:
                assigned_properties_formatted[realtor.realtor_id] = {
                    "realtor_id": realtor.realtor_id,
                    "realtor_name": realtor.name,
                    "realtor_email": realtor.email,
                    "properties": assigned_properties[realtor.realtor_id],
                    "count": len(assigned_properties[realtor.realtor_id])
                }
        
        # Summary
        summary = {
            "total_properties": len(all_properties),
            "unassigned_count": len(unassigned_properties),
            "assigned_count": sum(len(props) for props in assigned_properties.values()),
            "realtor_counts": {
                str(realtor.realtor_id): {
                    "realtor_name": realtor.name,
                    "count": len(assigned_properties.get(realtor.realtor_id, []))
                }
                for realtor in realtors
            }
        }
        
        return JSONResponse(content={
            "unassigned_properties": unassigned_properties,
            "assigned_properties": assigned_properties_formatted,
            "summary": summary
        })


# ---------------------- PROPERTY ASSIGNMENT AND UPLOAD ----------------------

@app.get("/check-properties")
async def check_properties(user_data: dict = Depends(get_current_user_data)):
    """Check existing properties for the current user (PM or Realtor)."""
    user_type = user_data["user_type"]
    user_id = user_data["id"]
    
    with Session(engine) as session:
        if user_type == "property_manager":
            # Get PM's own properties
            pm_sources = session.exec(
                select(Source).where(Source.property_manager_id == user_id)
            ).all()
            pm_source_ids = [s.source_id for s in pm_sources]
            
            # Get managed realtors' sources
            realtors = session.exec(
                select(Realtor).where(Realtor.property_manager_id == user_id)
            ).all()
            realtor_source_ids = []
            for realtor in realtors:
                realtor_sources = session.exec(
                    select(Source).where(Source.realtor_id == realtor.realtor_id)
                ).all()
                realtor_source_ids.extend([s.source_id for s in realtor_sources])
            
            all_source_ids = pm_source_ids + realtor_source_ids
        else:  # realtor
            sources = session.exec(
                select(Source).where(Source.realtor_id == user_id)
            ).all()
            all_source_ids = [s.source_id for s in sources]
        
        if not all_source_ids:
            return JSONResponse(content={
                "user_type": user_type,
                "user_id": user_id,
                "total_properties": 0,
                "properties": [],
                "sources": []
            })
        
        properties = session.exec(
            select(ApartmentListing).where(ApartmentListing.source_id.in_(all_source_ids))
        ).all()
        
        # Get source info
        sources = session.exec(
            select(Source).where(Source.source_id.in_(all_source_ids))
        ).all()
        
        source_info = []
        for s in sources:
            owner_type = "property_manager" if s.property_manager_id else "realtor"
            owner_id = s.property_manager_id if s.property_manager_id else s.realtor_id
            
            if s.property_manager_id:
                pm = session.exec(
                    select(PropertyManager).where(PropertyManager.property_manager_id == s.property_manager_id)
                ).first()
                owner_name = pm.name if pm else "Unknown"
            else:
                r = session.exec(
                    select(Realtor).where(Realtor.realtor_id == s.realtor_id)
                ).first()
                owner_name = r.name if r else "Unknown"
            
            source_info.append({
                "source_id": s.source_id,
                "owner_type": owner_type,
                "owner_id": owner_id,
                "owner_name": owner_name,
                "property_count": len([p for p in properties if p.source_id == s.source_id])
            })
        
        return JSONResponse(content={
            "user_type": user_type,
            "user_id": user_id,
            "total_properties": len(properties),
            "sources": source_info,
            "properties_by_source": {
                str(s.source_id): [
                    {
                        "id": p.id,
                        "address": (p.listing_metadata or {}).get("address"),
                        "price": (p.listing_metadata or {}).get("price"),
                    }
                    for p in properties if p.source_id == s.source_id
                ]
                for s in sources
            }
        })


@app.post("/property-manager/upload-listings")
async def property_manager_upload_listings(
    listing_file: UploadFile = File(None),
    listing_api_url: str = Form(None),
    assign_to_realtor_id: int = Form(None),  # Optional: assign to specific realtor
    user_data: dict = Depends(get_current_user_data)
):
    """Property Manager uploads listings to their own source or assigns to a realtor."""
    user_type = user_data["user_type"]
    property_manager_id = user_data["id"]
    
    if user_type != "property_manager":
        raise HTTPException(
            status_code=403,
            detail="Only Property Managers can upload listings"
        )
    
    with Session(engine) as session:
        source_id = None
        
        if assign_to_realtor_id:
            # Verify realtor is managed by this PM
            realtor = session.exec(
                select(Realtor).where(
                    Realtor.realtor_id == assign_to_realtor_id,
                    Realtor.property_manager_id == property_manager_id
                )
            ).first()
            
            if not realtor:
                raise HTTPException(
                    status_code=404,
                    detail="Realtor not found or not managed by this Property Manager"
                )
            
            # Get realtor's source
            source = session.exec(
                select(Source).where(Source.realtor_id == assign_to_realtor_id)
            ).first()
            
            if not source:
                raise HTTPException(
                    status_code=404,
                    detail="Source not found for realtor"
                )
            
            source_id = source.source_id
        else:
            # Upload to PM's own source
            source = session.exec(
                select(Source).where(Source.property_manager_id == property_manager_id)
            ).first()
            
            if not source:
                raise HTTPException(
                    status_code=404,
                    detail="Source not found for Property Manager"
                )
            
            source_id = source.source_id
        
        # Use the new direct insert function
        from DB.db import embed_and_store_listings_for_source
        result = embed_and_store_listings_for_source(
            listing_file=listing_file,
            listing_api_url=listing_api_url,
            source_id=source_id
        )
        
        return JSONResponse(content={
            "message": "Listings uploaded successfully",
            "assigned_to": "realtor" if assign_to_realtor_id else "property_manager",
            "realtor_id": assign_to_realtor_id if assign_to_realtor_id else None,
            "source_id": source_id,
            **result
        })


@app.post("/property-manager/assign-properties")
async def assign_properties_to_realtor(
    payload: dict = Body(...),
    user_data: dict = Depends(get_current_user_data)
):
    """Property Manager assigns existing properties to a specific realtor.
    
    Body:
    {
        "realtor_id": 123,  // Realtor ID (integer)
        "property_ids": [1, 2, 3, 4, 5]  // List of apartment listing IDs
    }
    """
    user_type = user_data["user_type"]
    property_manager_id = user_data["id"]
    
    if user_type != "property_manager":
        raise HTTPException(
            status_code=403,
            detail="Only Property Managers can assign properties"
        )
    
    realtor_id = payload.get("realtor_id")
    property_ids = payload.get("property_ids", [])  # List of apartment listing IDs
    
    if not realtor_id or not property_ids:
        raise HTTPException(
            status_code=400,
            detail="Missing required fields: realtor_id, property_ids"
        )
    
    with Session(engine) as session:
        # Verify realtor is managed by this PM
        realtor = session.exec(
            select(Realtor).where(
                Realtor.realtor_id == realtor_id,
                Realtor.property_manager_id == property_manager_id
            )
        ).first()
        
        if not realtor:
            raise HTTPException(
                status_code=404,
                detail="Realtor not found or not managed by this Property Manager"
            )
        
        # Get realtor's source
        realtor_source = session.exec(
            select(Source).where(Source.realtor_id == realtor_id)
        ).first()
        
        if not realtor_source:
            raise HTTPException(
                status_code=404,
                detail="Source not found for realtor"
            )
        
        # Get PM's sources to verify property ownership
        pm_sources = session.exec(
            select(Source).where(Source.property_manager_id == property_manager_id)
        ).all()
        pm_source_ids = [s.source_id for s in pm_sources]
        
        # Get the properties and verify they belong to PM
        properties = session.exec(
            select(ApartmentListing).where(
                ApartmentListing.id.in_(property_ids),
                ApartmentListing.source_id.in_(pm_source_ids)
            )
        ).all()
        
        if len(properties) != len(property_ids):
            raise HTTPException(
                status_code=400,
                detail="Some properties not found or don't belong to this Property Manager"
            )
        
        # Move properties to realtor's source
        for prop in properties:
            prop.source_id = realtor_source.source_id
        
        session.commit()
        
        return JSONResponse(content={
            "message": f"Successfully assigned {len(properties)} properties to realtor",
            "realtor_id": realtor_id,
            "realtor_name": realtor.name,
            "realtor_email": realtor.email,
            "property_count": len(properties),
            "assigned_property_ids": [p.id for p in properties]
        })


@app.post("/property-manager/bulk-assign-properties")
async def bulk_assign_properties_to_realtors(
    payload: dict = Body(...),
    user_data: dict = Depends(get_current_user_data)
):
    """Property Manager assigns multiple properties to multiple realtors in one call.
    
    Body:
    {
        "assignments": [
            {
                "realtor_id": 1,
                "property_ids": [1, 2, 3]
            },
            {
                "realtor_id": 2,
                "property_ids": [4, 5, 6]
            }
        ]
    }
    """
    user_type = user_data["user_type"]
    property_manager_id = user_data["id"]
    
    if user_type != "property_manager":
        raise HTTPException(
            status_code=403,
            detail="Only Property Managers can assign properties"
        )
    
    assignments = payload.get("assignments", [])
    
    if not assignments:
        raise HTTPException(
            status_code=400,
            detail="No assignments provided"
        )
    
    results = []
    
    with Session(engine) as session:
        # Get PM's sources to verify property ownership
        pm_sources = session.exec(
            select(Source).where(Source.property_manager_id == property_manager_id)
        ).all()
        pm_source_ids = [s.source_id for s in pm_sources]
        
        for assignment in assignments:
            realtor_id = assignment.get("realtor_id")
            property_ids = assignment.get("property_ids", [])
            
            if not realtor_id or not property_ids:
                results.append({
                    "realtor_id": realtor_id,
                    "status": "skipped",
                    "message": "Missing realtor_id or property_ids"
                })
                continue
            
            # Verify realtor is managed by this PM
            realtor = session.exec(
                select(Realtor).where(
                    Realtor.realtor_id == realtor_id,
                    Realtor.property_manager_id == property_manager_id
                )
            ).first()
            
            if not realtor:
                results.append({
                    "realtor_id": realtor_id,
                    "status": "error",
                    "message": "Realtor not found or not managed by this Property Manager"
                })
                continue
            
            # Get realtor's source
            realtor_source = session.exec(
                select(Source).where(Source.realtor_id == realtor_id)
            ).first()
            
            if not realtor_source:
                results.append({
                    "realtor_id": realtor_id,
                    "status": "error",
                    "message": "Source not found for realtor"
                })
                continue
            
            # Get the properties and verify they belong to PM
            properties = session.exec(
                select(ApartmentListing).where(
                    ApartmentListing.id.in_(property_ids),
                    ApartmentListing.source_id.in_(pm_source_ids)
                )
            ).all()
            
            if len(properties) != len(property_ids):
                results.append({
                    "realtor_id": realtor_id,
                    "realtor_name": realtor.name,
                    "status": "partial",
                    "message": f"Only {len(properties)} of {len(property_ids)} properties found and assigned",
                    "assigned_count": len(properties),
                    "requested_count": len(property_ids)
                })
            else:
                # Move properties to realtor's source
                for prop in properties:
                    prop.source_id = realtor_source.source_id
                
                session.commit()
                
                results.append({
                    "realtor_id": realtor_id,
                    "realtor_name": realtor.name,
                    "realtor_email": realtor.email,
                    "status": "success",
                    "message": f"Successfully assigned {len(properties)} properties",
                    "assigned_count": len(properties),
                    "assigned_property_ids": [p.id for p in properties]
                })
        
        return JSONResponse(content={
            "message": "Bulk assignment completed",
            "total_assignments": len(assignments),
            "results": results
        })


@app.post("/property-manager/unassign-properties")
async def unassign_properties_from_realtor(
    payload: dict = Body(...),
    user_data: dict = Depends(get_current_user_data)
):
    """Property Manager unassigns properties from a realtor back to themselves.
    
    Body:
    {
        "property_ids": [1, 2, 3, 4, 5]  // List of apartment listing IDs to unassign
    }
    """
    user_type = user_data["user_type"]
    property_manager_id = user_data["id"]
    
    if user_type != "property_manager":
        raise HTTPException(
            status_code=403,
            detail="Only Property Managers can unassign properties"
        )
    
    property_ids = payload.get("property_ids", [])
    
    if not property_ids:
        raise HTTPException(
            status_code=400,
            detail="Missing required field: property_ids"
        )
    
    with Session(engine) as session:
        # Get PM's sources
        pm_sources = session.exec(
            select(Source).where(Source.property_manager_id == property_manager_id)
        ).all()
        pm_source_ids = [s.source_id for s in pm_sources]
        
        if not pm_source_ids:
            raise HTTPException(
                status_code=404,
                detail="Source not found for Property Manager"
            )
        
        # Get all managed realtors' sources to verify properties belong to them
        realtors = session.exec(
            select(Realtor).where(Realtor.property_manager_id == property_manager_id)
        ).all()
        
        realtor_source_ids = []
        for realtor in realtors:
            realtor_sources = session.exec(
                select(Source).where(Source.realtor_id == realtor.realtor_id)
            ).all()
            realtor_source_ids.extend([s.source_id for s in realtor_sources])
        
        # Get the properties - they should belong to one of the realtors managed by this PM
        properties = session.exec(
            select(ApartmentListing).where(
                ApartmentListing.id.in_(property_ids),
                ApartmentListing.source_id.in_(realtor_source_ids)
            )
        ).all()
        
        if len(properties) != len(property_ids):
            raise HTTPException(
                status_code=400,
                detail="Some properties not found or don't belong to realtors managed by this Property Manager"
            )
        
        # Move properties back to PM's source (use first available PM source)
        pm_source_id = pm_source_ids[0]
        for prop in properties:
            prop.source_id = pm_source_id
        
        session.commit()
        
        return JSONResponse(content={
            "message": f"Successfully unassigned {len(properties)} properties from realtors",
            "property_count": len(properties),
            "unassigned_property_ids": [p.id for p in properties]
        })


@app.patch("/properties/{property_id}/status")
async def update_property_status(
    property_id: int,
    payload: dict = Body(...),
    user_data: dict = Depends(get_current_user_data)
):
    """Update property listing status.
    
    Allowed statuses: "Available", "For Sale", "For Rent", "Sold", "Rented"
    
    Body:
    {
        "listing_status": "Sold"  // New status value
    }
    """
    listing_status = payload.get("listing_status")
    
    if not listing_status:
        raise HTTPException(
            status_code=400,
            detail="Missing required field: listing_status"
        )
    
    # Validate status
    valid_statuses = ["Available", "For Sale", "For Rent", "Sold", "Rented"]
    if listing_status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
        )
    
    user_type = user_data["user_type"]
    user_id = user_data["id"]
    
    with Session(engine) as session:
        # Get property
        property_obj = session.exec(
            select(ApartmentListing).where(ApartmentListing.id == property_id)
        ).first()
        
        if not property_obj:
            raise HTTPException(
                status_code=404,
                detail="Property not found"
            )
        
        # Check access permissions
        source = session.exec(
            select(Source).where(Source.source_id == property_obj.source_id)
        ).first()
        
        if not source:
            raise HTTPException(
                status_code=404,
                detail="Source not found for property"
            )
        
        # Verify user has access to this property
        has_access = False
        if user_type == "property_manager":
            if source.property_manager_id == user_id:
                has_access = True
            else:
                # Check if it belongs to a realtor under this PM
                if source.realtor_id:
                    realtor = session.exec(
                        select(Realtor).where(Realtor.realtor_id == source.realtor_id)
                    ).first()
                    if realtor and realtor.property_manager_id == user_id:
                        has_access = True
        else:  # realtor
            if source.realtor_id == user_id:
                has_access = True
        
        if not has_access:
            raise HTTPException(
                status_code=403,
                detail="You don't have access to update this property"
            )
        
        # Update metadata
        meta = property_obj.listing_metadata or {}
        meta["listing_status"] = listing_status
        
        # If status is Sold or Rented, update days_on_market to current if available
        if listing_status in ["Sold", "Rented"] and meta.get("days_on_market") is not None:
            # Keep existing days_on_market, or you could calculate final days
            pass
        
        property_obj.listing_metadata = meta
        session.commit()
        session.refresh(property_obj)
        
        return JSONResponse(content={
            "message": f"Property status updated to {listing_status}",
            "property_id": property_id,
            "new_status": listing_status,
            "updated_metadata": meta
        })


@app.patch("/properties/{property_id}/agent")
async def update_property_agent(
    property_id: int,
    payload: dict = Body(...),
    user_data: dict = Depends(get_current_user_data)
):
    """Update or remove agent information for a property.
    
    To remove agent, send: {"agent": null}
    To update agent, send: {
        "agent": {
            "name": "John Doe",
            "phone": "555-0123",
            "email": "john@example.com"
        }
    }
    """
    agent_data = payload.get("agent")
    
    user_type = user_data["user_type"]
    user_id = user_data["id"]
    
    with Session(engine) as session:
        # Get property
        property_obj = session.exec(
            select(ApartmentListing).where(ApartmentListing.id == property_id)
        ).first()
        
        if not property_obj:
            raise HTTPException(
                status_code=404,
                detail="Property not found"
            )
        
        # Check access permissions
        source = session.exec(
            select(Source).where(Source.source_id == property_obj.source_id)
        ).first()
        
        if not source:
            raise HTTPException(
                status_code=404,
                detail="Source not found for property"
            )
        
        # Verify user has access to this property
        has_access = False
        if user_type == "property_manager":
            if source.property_manager_id == user_id:
                has_access = True
            else:
                # Check if it belongs to a realtor under this PM
                if source.realtor_id:
                    realtor = session.exec(
                        select(Realtor).where(Realtor.realtor_id == source.realtor_id)
                    ).first()
                    if realtor and realtor.property_manager_id == user_id:
                        has_access = True
        else:  # realtor
            if source.realtor_id == user_id:
                has_access = True
        
        if not has_access:
            raise HTTPException(
                status_code=403,
                detail="You don't have access to update this property"
            )
        
        # Update metadata
        meta = property_obj.listing_metadata or {}
        
        if agent_data is None:
            # Remove agent
            meta.pop("agent", None)
        else:
            # Validate agent data structure
            if not isinstance(agent_data, dict):
                raise HTTPException(
                    status_code=400,
                    detail="Agent must be an object with name, phone, and email fields"
                )
            
            # Update agent
            meta["agent"] = {
                "name": agent_data.get("name", ""),
                "phone": agent_data.get("phone", ""),
                "email": agent_data.get("email", "")
            }
        
        property_obj.listing_metadata = meta
        session.commit()
        session.refresh(property_obj)
        
        action = "removed" if agent_data is None else "updated"
        return JSONResponse(content={
            "message": f"Property agent {action} successfully",
            "property_id": property_id,
            "agent": meta.get("agent"),
            "updated_metadata": meta
        })


@app.patch("/properties/{property_id}")
async def update_property_details(
    property_id: int,
    payload: dict = Body(...),
    user_data: dict = Depends(get_current_user_data)
):
    """Update various property details (status, agent, or other metadata fields).
    
    Body examples:
    {
        "listing_status": "Sold",
        "agent": null,  // or agent object to update/remove
        "days_on_market": 25,
        "price": 2500,
        // ... any other metadata fields
    }
    """
    user_type = user_data["user_type"]
    user_id = user_data["id"]
    
    with Session(engine) as session:
        # Get property
        property_obj = session.exec(
            select(ApartmentListing).where(ApartmentListing.id == property_id)
        ).first()
        
        if not property_obj:
            raise HTTPException(
                status_code=404,
                detail="Property not found"
            )
        
        # Check access permissions
        source = session.exec(
            select(Source).where(Source.source_id == property_obj.source_id)
        ).first()
        
        if not source:
            raise HTTPException(
                status_code=404,
                detail="Source not found for property"
            )
        
        # Verify user has access to this property
        has_access = False
        if user_type == "property_manager":
            if source.property_manager_id == user_id:
                has_access = True
            else:
                # Check if it belongs to a realtor under this PM
                if source.realtor_id:
                    realtor = session.exec(
                        select(Realtor).where(Realtor.realtor_id == source.realtor_id)
                    ).first()
                    if realtor and realtor.property_manager_id == user_id:
                        has_access = True
        else:  # realtor
            if source.realtor_id == user_id:
                has_access = True
        
        if not has_access:
            raise HTTPException(
                status_code=403,
                detail="You don't have access to update this property"
            )
        
        # Update metadata
        meta = property_obj.listing_metadata or {}
        
        # Handle listing_status update with validation
        if "listing_status" in payload:
            new_status = payload["listing_status"]
            valid_statuses = ["Available", "For Sale", "For Rent", "Sold", "Rented"]
            if new_status not in valid_statuses:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
                )
            meta["listing_status"] = new_status
        
        # Handle agent update/removal
        if "agent" in payload:
            agent_data = payload["agent"]
            if agent_data is None:
                meta.pop("agent", None)
            else:
                if not isinstance(agent_data, dict):
                    raise HTTPException(
                        status_code=400,
                        detail="Agent must be an object with name, phone, and email fields"
                    )
                meta["agent"] = {
                    "name": agent_data.get("name", ""),
                    "phone": agent_data.get("phone", ""),
                    "email": agent_data.get("email", "")
                }
        
        # Update other metadata fields (price, days_on_market, etc.)
        updatable_fields = [
            "price", "bedrooms", "bathrooms", "square_feet", "lot_size_sqft",
            "year_built", "property_type", "days_on_market", "listing_date",
            "features", "description", "image_url", "address"
        ]
        
        for field in updatable_fields:
            if field in payload:
                meta[field] = payload[field]
        
        property_obj.listing_metadata = meta
        session.commit()
        session.refresh(property_obj)
        
        return JSONResponse(content={
            "message": "Property updated successfully",
            "property_id": property_id,
            "updated_fields": list(payload.keys()),
            "updated_metadata": meta
        })


# ---------------------- TEST USER MANAGEMENT ----------------------

@app.post("/create-test-team")
async def create_test_team():
    """Create a test team: 1 Property Manager + 2 Realtors (for development only)."""
    try:
        from utils.password_manager import PasswordManager
        password_manager = PasswordManager()
        
        result = password_manager.create_test_team()
        
        if result["success"]:
            return JSONResponse(content={
                "message": "Test team created successfully!",
                "created_users": result["created_users"],
                "total_users": result["total_users"],
                "test_credentials": result["test_credentials"]
            })
        else:
            return JSONResponse(
                content={"error": "Failed to create test team", "details": result},
                status_code=500
            )
            
    except Exception as e:
        return JSONResponse(
            content={"error": f"Failed to create test team: {str(e)}"},
            status_code=500
        )


@app.get("/test-users")
async def list_test_users():
    """List all test users with their credentials (for development only)."""
    try:
        from utils.password_manager import PasswordManager
        password_manager = PasswordManager()
        
        users = password_manager.list_all_test_users()
        
        return JSONResponse(content={
            "test_users": users,
            "count": len(users)
        })
        
    except Exception as e:
        return JSONResponse(
            content={"error": f"Failed to list test users: {str(e)}"},
            status_code=500
        )


@app.post("/reset-test-users")
async def reset_test_users():
    """Reset all test users (for development only)."""
    try:
        from utils.password_manager import PasswordManager
        password_manager = PasswordManager()
        
        password_manager.reset_test_users()
        
        return JSONResponse(content={
            "message": "All test users have been reset successfully!"
        })
        
    except Exception as e:
        return JSONResponse(
            content={"error": f"Failed to reset test users: {str(e)}"},
            status_code=500
        )


@app.get("/bookings")
async def get_bookings(user_data: dict = Depends(get_current_user_data)):
    """Get bookings based on user type and data access scope."""
    user_type = user_data["user_type"]
    user_id = user_data["id"]
    
    print(f"Getting bookings for {user_type} ID: {user_id}")

    with Session(engine) as session:
        if user_type == "property_manager":
            # Property managers can see bookings from all their realtors
            realtors = session.exec(
                select(Realtor).where(Realtor.property_manager_id == user_id)
            ).all()
            realtor_ids = [r.realtor_id for r in realtors]
            
            if not realtor_ids:
                return JSONResponse(content={"bookings": []})
            
            bookings = session.exec(
                select(Booking).where(Booking.realtor_id.in_(realtor_ids))
            ).all()
        else:
            # Realtors can only see their own bookings
            bookings = session.exec(
                select(Booking).where(Booking.realtor_id == user_id)
            ).all()

        # Transform bookings for response
        result = []
        for booking in bookings:
            result.append({
                "id": booking.id,
                "address": booking.address,
                "date": booking.date.isoformat() if booking.date else None,
                "time": booking.time.isoformat() if booking.time else None,
                "visited": booking.visited,
                "customer_feedback": booking.cust_feedback,
                "customer_id": booking.cust_id,
                "realtor_id": booking.realtor_id,
            })

        return JSONResponse(content={"bookings": result})


def get_db():
    with Session(engine) as session:
        yield session


@app.post("/buy-number")
def buy_number(
    area_code: str = "412",
    authorization: str = Header(
        ...
    ),  # Extract JWT from frontend Authorization: Bearer <token>
    db: Session = Depends(get_db),
):
    """Buy Twilio number, link with Vapi, and save to DB."""

    try:
        token = authorization.split(" ")[1]
        decoded = jwt.decode(
            token, options={"verify_signature": False}
        )  # in dev, skip sig verify
        auth_user_id = decoded.get("sub")
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid auth token")

    realtor = db.exec(
        select(Realtor).where(Realtor.auth_user_id == auth_user_id)
    ).first()
    print("Realtor id recv:", realtor.realtor_id)
    if not realtor:
        raise HTTPException(status_code=404, detail="Realtor not found")

    #  Buy Twilio number
    available = twillio_client.available_phone_numbers("US").local.list(
        area_code=area_code, limit=1
    )
    if not available:
        raise HTTPException(
            status_code=400, detail=f"No numbers available for area code {area_code}"
        )

    number_to_buy = available[0].phone_number

    purchased = twillio_client.incoming_phone_numbers.create(
        phone_number=number_to_buy,
        sms_url=f"https://api.vapi.ai/sms/twilio/{VAPI_ASSISTANT_ID2}",
        voice_url="https://api.vapi.ai/twilio/inbound_call",
    )

    #  Link with Vapi assistant
    payload = {
        "provider": "twilio",
        "number": purchased.phone_number,
        "twilioAccountSid": TWILIO_ACCOUNT_SID2,
        "twilioAuthToken": TWILIO_AUTH_TOKEN2,
        "assistantId": VAPI_ASSISTANT_ID2,
        "name": f"Realtor {realtor.realtor_id} Bot Number",
    }

    response = requests.post(
        "https://api.vapi.ai/phone-number",
        headers={
            "Authorization": f"Bearer {VAPI_API_KEY2}",
            "Content-Type": "application/json",
        },
        json=payload,
    )

    #  Save Twilio number to realtor table
    with Session(engine) as session:
        realtor = session.get(Realtor, realtor.realtor_id)  # fetch existing realtor by ID
        if realtor:
            # Save the Twilio number in the twilio_contact field
            realtor.twilio_contact = purchased.phone_number
            # Save the Twilio SID
            realtor.twilio_sid = purchased.sid

            session.add(realtor)
            session.commit()
            session.refresh(realtor)

            return {
                "twilio_contact": realtor.twilio_contact,
                "twilio_sid": realtor.twilio_sid,
                "realtor_id": realtor.realtor_id,
                "vapi_response": response.json(),
            }
        else:
            return {"error": "Realtor not found"}


@app.get("/my-number")
def get_my_number(current_user: int = Depends(get_current_realtor_id)):
    with Session(engine) as session:
        statement = select(Realtor).where(Realtor.realtor_id == current_user)
        realtor = session.exec(statement).first()
        print("Hey realtor:", realtor)

        if not realtor or not realtor.twilio_contact:
            raise HTTPException(
                status_code=404, detail="You haven't bought the number yet!"
            )

        return {"twilio_number": realtor.twilio_contact}


@app.get("/recordings")
def get_recordings(realtor_id: int = Depends(get_current_realtor_id)):
    recordings = []

    # Step 1: Look up the realtor in DB to get their Twilio number
    with Session(engine) as session:
        realtor = session.exec(select(Realtor).where(Realtor.realtor_id == realtor_id)).first()

        if not realtor:
            raise HTTPException(status_code=404, detail="Realtor not found")

        if not realtor.twilio_contact:
            raise HTTPException(
                status_code=400,
                detail="Realtor does not have a Twilio contact configured",
            )

        twilio_number = realtor.twilio_contact
        print("from supabse got twilio contact:", twilio_number)

    # Step 2: Fetch all calls from VAPI
    resp = requests.get(f"{VAPI_BASE_URL}/call", headers=headers)
    calls = resp.json()

    for call in calls:
        # Step 3: Get the phoneNumberId from the call
        phone_number_id = call.get("phoneNumberId")
        print("phone from vapi call id", phone_number_id)
        if not phone_number_id:
            continue

        # Step 4: Look up the number against the phoneNumberId
        pn_resp = requests.get(
            f"{VAPI_BASE_URL}/phone-number/{phone_number_id}", headers=headers
        )
        if pn_resp.status_code != 200:
            continue

        bot_number = pn_resp.json().get("number")
        print("bot number from vapi", bot_number)

        # Step 5: Match with realtor’s Twilio contact
        if bot_number != twilio_number:
            continue

        # Step 7: Extract recordings if available
        recording_url = call.get("artifact", {}).get("recordingUrl")

        if recording_url:
            recordings.append({"url": recording_url})

    return {"recordings": recordings}


@app.get("/chat-history")
async def get_all_chats_endpoint(realtor_id: int = Depends(get_current_realtor_id)):
    with Session(engine) as session:
        realtor = session.get(Realtor, realtor_id)
        realtor_number = realtor.twilio_contact
        realtor_number = "+14155238886"

    chats = get_all_chats(realtor_number)
    return chats


def get_all_chats(realtor_number: str):
    # Ensure WhatsApp format
    if not realtor_number.startswith("whatsapp:"):
        realtor_number = f"whatsapp:{realtor_number}"

    print(f"Fetching chats for {realtor_number}...")

    # Fetch all incoming and outgoing messages (pagination will be handled automatically by Twilio)
    incoming = twillio_client1.messages.list(to=realtor_number)
    outgoing = twillio_client1.messages.list(from_=realtor_number)
    messages = incoming + outgoing

    # Sort by date
    messages = sorted(messages, key=lambda m: m.date_sent or datetime.min)

    # Group messages by customer
    chats = {}
    for msg in messages:
        if msg.from_ == realtor_number:
            customer_number = msg.to
            sender = "realtor"
        else:
            customer_number = msg.from_
            sender = "customer"

        if customer_number not in chats:
            chats[customer_number] = []

        chats[customer_number].append(
            {
                "sender": sender,  # realtor / customer
                "message": msg.body,
                "timestamp": msg.date_sent.isoformat() if msg.date_sent else None,
            }
        )

    return {"chats": chats}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
