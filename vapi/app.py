from fastapi import FastAPI, HTTPException, Form, Request,File,UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Union
from datetime import datetime
import json,os
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
)

from sqlalchemy import update
from fastapi.middleware.cors import CORSMiddleware



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
    print("Checking and initializing pgvector indexes and Relational DB tables")
    #vector db is being initialized in  
    init_vector_db()
    try:
        rules = rag.query("test", k=1)
        if "Here are the most relevant parts:" in rules and len(rules.splitlines()) <= 1:
            rag.build_rules_index()

        apartments = rag.search_apartments("test", k=1)
        if not apartments:
            rag.build_apartment_index()
    except Exception as e:
        print(f"Error initializing indexes: {e}")

    yield  # This is where FastAPI app runs

    print("Shutting down fastapi app...")

# origins = [
#     "https://react-app-form.onrender.com"
# ]
app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
            if not question:
                raise HTTPException(status_code=400, detail="Missing query text")

            response = rag.query(question)
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
SCOPES = ["https://www.googleapis.com/auth/calendar"]
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
    print(f"Sending message to Vapi with previousChatId={prev_chat_id}")

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
        return PlainTextResponse("Error with Vapi", status_code=500)
    
    response_json = response.json()
    output = response_json.get("output", [])

    if not output or not isinstance(output, list):
        print("Vapi returned empty or invalid output:", output)
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


from fastapi import  UploadFile, File, Form, HTTPException
from supabase import create_client, Client

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
    contact: str = Form(...),
    files: List[UploadFile] = File(...),
    listing_file: Optional[UploadFile] = File(None),
    listing_api_url: Optional[str] = Form(None)
):
    try:
        result= create_realtor_with_files(
            name=name,
            email=email,
            contact=contact,
            files=files,
            listing_file=listing_file,
            listing_api_url=listing_api_url
        )
        print(result)
        

        return JSONResponse(content=result, status_code=200)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
