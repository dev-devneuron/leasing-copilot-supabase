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
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
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

    uploaded_files = embed_and_store_rules(files, realtor_id, source.id)
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
    """Get apartments based on user type and data access scope."""
    user_type = user_data["user_type"]
    user_id = user_data["id"]
    
    print(f"Getting apartments for {user_type} ID: {user_id}")

    # Get data access scope
    access_scope = get_data_access_scope(user_type, user_id)
    source_ids = access_scope["source_ids"]

    if not source_ids:
        return JSONResponse(
            content={"message": "No sources found for this user"}, status_code=404
        )

    with Session(engine) as session:
        # Get apartments for accessible source_ids
        apartments = session.exec(
            select(ApartmentListing).where(ApartmentListing.source_id.in_(source_ids))
        ).all()

        # Transform into frontend-friendly shape
        result = []
        for apt in apartments:
            meta = apt.listing_metadata or {}
            result.append(
                {
                    "id": apt.id,
                    "address": meta.get("address"),
                    "price": meta.get("price"),
                    "bedrooms": meta.get("bedrooms"),
                    "bathrooms": meta.get("bathrooms"),
                    "description": meta.get("description"),
                }
            )

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
