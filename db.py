from typing import Optional, List, Dict, Union, Any
from datetime import date, time
from sqlmodel import SQLModel, Field, create_engine, Session,JSON, Relationship, select, Column,PrimaryKeyConstraint
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import sessionmaker
from langchain_huggingface import HuggingFaceEmbeddings
import requests, os, json
import google.generativeai as genai
from langchain_core.documents import Document
from sqlmodel import SQLModel, Field, Relationship
from pgvector.sqlalchemy import Vector
from typing import Optional, List, Dict, Any
from secondary_db import insert_listing_records
from sqlmodel import Session, select
from datetime import date
from supabase import create_client, Client
from fastapi import UploadFile, File, Form, HTTPException, APIRouter
from dotenv import load_dotenv
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import CharacterTextSplitter
from config import BUCKET_NAME,SUPABASE_URL,SUPABASE_KEY,DATABASE_URL,SUPABASE_SERVICE_ROLE_KEY
from uuid import UUID
import jwt
import json, csv, io, requests
from langchain.schema import Document
from langchain.text_splitter import CharacterTextSplitter

load_dotenv()

# ---------------------- DATABASE CONFIG ----------------------


engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# ---------------------- MODELS ----------------------

class Realtor(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True, alias="realtor_id")
    auth_user_id: UUID = Field(index=True)
    name: str
    email: str
    contact: str
    twilio_contact: str
    twilio_sid: Optional[str] = None
    credentials: Optional[str] = Field(default=None)  # Store as serialized JSON string

    sources: List["Source"] = Relationship(back_populates="realtor")
    bookings: List["Booking"] = Relationship(back_populates="realtor")


class Customer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True, alias="cust_id")
    name: Optional[str] = None
    email: Optional[str] = None
    contact: str
    if_tenant: Optional[str] = None

    bookings_as_customer: List["Booking"] = Relationship(
        back_populates="customer", sa_relationship_kwargs={"foreign_keys": "[Booking.cust_id]"}
    )
    chat_sessions: List["ChatSession"] = Relationship(back_populates="customer")


class ChatSession(SQLModel, table=True):
    chat_id: str = Field(primary_key=True)
    cust_id: int = Field(foreign_key="customer.id")
    date: date
    count: int

    customer: Optional["Customer"] = Relationship(back_populates="chat_sessions")

class Booking(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    address: str
    date: date
    time: time
    visited: Optional[bool] = False
    cust_feedback: Optional[str] = None

    cust_id: Optional[int] = Field(default=None, foreign_key="customer.id")
    realtor_id: Optional[int] = Field(default=None, foreign_key="realtor.id")

    customer: Optional[Customer] = Relationship(back_populates="bookings_as_customer", sa_relationship_kwargs={"foreign_keys": "[Booking.cust_id]"})
    realtor: Optional[Realtor] = Relationship(back_populates="bookings")

class RuleChunk(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)  # Auto-increment primary key
    source_id: int = Field(foreign_key="source.id")

    content: str
    embedding: List[float] = Field(sa_column=Column(Vector(768)))

    source: Optional["Source"] = Relationship(back_populates="rule_chunks")

class ApartmentListing(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True) 
    source_id: int = Field(foreign_key="source.id")

    text: str
    listing_metadata: Dict[str, Any] = Field(sa_column=Column(JSON))
    embedding: List[float] = Field(sa_column=Column(Vector(768)))

    source: Optional["Source"] = Relationship(back_populates="listings")

class Source(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True, alias="source_id")
    realtor_id: int = Field(foreign_key="realtor.id")

    realtor: Optional[Realtor] = Relationship(back_populates="sources")
    rule_chunks: List["RuleChunk"] = Relationship(back_populates="source")
    listings: List["ApartmentListing"] = Relationship(back_populates="source")


# ---------------------- EMBEDDING SETUP ----------------------
class GeminiEmbedder:
    def __init__(self, model_name="models/embedding-001"):
        embd_key = os.getenv("GOOGLE_API_KEY")
        genai.configure(api_key=embd_key)
        self.model_name = model_name

    def embed_text(self, text: str) -> list:
        res = genai.embed_content(model=self.model_name, content=text, task_type="retrieval_document")
        return res["embedding"]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(t) for t in texts]
    

#embedder = HuggingFaceEmbeddings(model_name="BAAI/bge-base-en")
embedder = GeminiEmbedder()  



def embed_text(text: str) -> List[float]:
    return embedder.embed_text(text)
#embedder.embed_query(text) if using huggingface embedder
def embed_documents(texts: List[str]) -> List[List[float]]:
    return embedder.embed_documents(texts)


# ---------------------- INITIALIZATION ----------------------

def init_db():
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    SQLModel.metadata.create_all(engine)


#------------------------Embedding Init---------------------------
def init_vector_db():
    init_db()  # Ensure tables and vector extension are initialized

    
#---------------------CRUD OPERATIONS----------------------------

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
decoded = jwt.decode(SUPABASE_SERVICE_KEY, options={"verify_signature": False})
print("ROLEEEEE:",decoded.get("role"))



def listing_to_text(listing: dict) -> str:
    try:
        return (
            f"Address: {listing.get('address', 'N/A')}. "
            f"Price: {listing.get('price', 'N/A')}. "
            f"Bedrooms: {listing.get('bedrooms', 'N/A')}. "
            f"Bathrooms: {listing.get('bathrooms', 'N/A')}. "
            f"Description: {listing.get('description', '')}"
        )
    except Exception as e:
        print("listing_to_text error:", e)
        return "Invalid listing format."

def create_realtor(
    auth_user_id: str,
    name: str,
    email: str,
    contact: str,
):
    with Session(engine) as session:
        # Check for duplicate realtor
        existing_realtor = session.exec(
            select(Realtor).where((Realtor.email == email) | (Realtor.contact == contact))
        ).first()

        if existing_realtor:
            raise HTTPException(status_code=400, detail="Realtor with this email or contact already exists")

        # Create new Realtor with Supabase auth UUID
        realtor = Realtor(
            auth_user_id=auth_user_id,  # new field
            name=name,
            email=email,
            contact=contact,
            twilio_contact="TBD"
        )
        session.add(realtor)
        session.commit()
        session.refresh(realtor)
        print("realtor created")

        # 3. Create Source and assign to Realtor
        source = Source(realtor_id=realtor.id)
        session.add(source)
        session.commit()
        session.refresh(source)
        print("source created")
        
        auth_link = f"https://leasing-copilot-supabase.onrender.com/authorize?realtor_id={realtor.id}"
        
        return {
            "message": "Realtor created, rules uploaded, listings processed (not stored)",
            "realtor": {
                "id": realtor.id,
                "name": realtor.name,
                "email": realtor.email,
                "contact": realtor.contact
            },
            "auth_link": auth_link
        }




def embed_and_store_rules(files: list[UploadFile], realtor_id: int, source_id: int):
    uploaded_files = []
    splitter = CharacterTextSplitter(separator="\n", chunk_size=500, chunk_overlap=50)
    all_chunks = []

    try:
        for file in files:
            try:
                # Read file content
                content_bytes = file.file.read()
                if not content_bytes:
                    raise ValueError(f"File {file.filename} is empty or unreadable")

                file_content = content_bytes.decode("utf-8")
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to read/parse file {file.filename}: {str(e)}")

            file_path = f"realtors/{realtor_id}/{file.filename}"
            # Upload to Supabase storage
            try:
                response = supabase.storage.from_(BUCKET_NAME).upload(
                    file_path,
                    content_bytes,
                    file_options={"content-type": file.content_type}
                )
                if isinstance(response, dict) and "error" in response:
                    raise Exception(response["error"]["message"])
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to upload {file.filename} to Supabase storage: {str(e)}")
            file_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{file_path}"
            uploaded_files.append(file_url)

            # Split into chunks
            try:
                document = Document(page_content=file_content, metadata={"source": file.filename})
                chunk_docs = splitter.split_documents([document])
                chunks = [doc.page_content for doc in chunk_docs]
                all_chunks.extend(chunks)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to split {file.filename} into chunks: {str(e)}")

        # Insert into DB
        try:
            insert_rule_chunks(source_id=source_id,chunks=all_chunks)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to insert rule chunks into DB: {str(e)}")

        return uploaded_files

    except HTTPException:
        # re-raise explicit HTTP errors
        raise
    except Exception as e:
        # catch anything unexpected
        raise HTTPException(status_code=500, detail=f"Unexpected error in embed_and_store_rules: {str(e)}")



def embed_and_store_listings(listing_file, listing_api_url: str = None, realtor_id: int = None):
    listing_text = ""

    if listing_file:
        content = listing_file.file.read()
        print("reading done")
        if listing_file.filename.endswith(".json"):
            parsed = json.loads(content)
            listing_text = json.dumps(parsed, indent=2)
            print("it was json")
        elif listing_file.filename.endswith(".csv"):
            decoded = content.decode("utf-8")
            reader = csv.DictReader(io.StringIO(decoded))
            rows = [row for row in reader]
            listing_text = json.dumps(rows, indent=2)
        else:
            raise HTTPException(status_code=400, detail="Unsupported listing file format")

        # Upload listing file
        listing_path = f"realtors/{realtor_id}/listings/{listing_file.filename}"
        response = supabase.storage.from_(BUCKET_NAME).upload(
            listing_path,
            content,
            file_options={"content-type": listing_file.content_type}
        )
        print("file uploaded to supabase")
        if isinstance(response, dict) and "error" in response:
            raise HTTPException(status_code=500, detail=response["error"]["message"])

    elif listing_api_url:
        response = requests.get(listing_api_url)
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch data from API URL")
        listing_data = response.json()
        listing_text = json.dumps(listing_data, indent=2)

    if listing_text:
        listings = json.loads(listing_text)
        if isinstance(listings, dict):
            listings = [listings]

        formatted_texts = [listing_to_text(l) for l in listings]
        embeddings = embed_documents(formatted_texts)
        print("embedding done")

        listing_records = [
            {"text": formatted_texts[i], "metadata": listings[i], "embedding": embeddings[i]}
            for i in range(len(listings))
        ]
        print("calling insert function")
        insert_listing_records(realtor_id, listing_records)

    return True


def create_source(realtor_id: int) -> Source:
    with Session(engine) as session:
        source = Source(realtor_id=realtor_id)
        session.add(source)
        session.commit()
        session.refresh(source)
        print("Created new Source.")
        return source


#---------------------------- Bounded Usage------------------------

def get_chat_session(user_number: str) -> str | None:
    with Session(engine) as session:
        customer = session.exec(select(Customer).where(Customer.contact == user_number)).first()
        if not customer: 
            return None

        chat_stmt = select(ChatSession).where(
        ChatSession.cust_id == customer.id,
        ChatSession.date == date.today()
    ).order_by(ChatSession.date.desc())

        chat_session = session.exec(chat_stmt).first()
        return chat_session.chat_id if chat_session else None

def save_chat_session(from_number: str, chat_id: str) -> None:
    with Session(engine) as session:
        # Get or create customer
        customer = session.exec(select(Customer).where(Customer.contact == from_number)).first()
        if not customer:
            customer = Customer(
                name="Unknown",
                email="unknown@example.com",
                contact=from_number,
                if_tenant="Unknown"
            )
            session.add(customer)
            session.commit()
            session.refresh(customer)

        # Check if chat session exists for the customer (regardless of date)
        existing_chat = session.exec(
            select(ChatSession).where(ChatSession.cust_id == customer.id)
        ).first()

        if existing_chat:
            if existing_chat.date != date.today():
                # Update date and reset count
                existing_chat.date = date.today()
                existing_chat.count = 0

            # Always update chat_id to the latest
            existing_chat.chat_id = chat_id

            session.add(existing_chat)
            session.commit()
            print(f"Updated chat_id for {from_number} to {chat_id}")
            return

        # No session at all — create new one
        new_session = ChatSession(
            chat_id=chat_id,
            cust_id=customer.id,
            date=date.today(),
            count=1
        )
        session.add(new_session)
        session.commit()
        print(f"New chat session created for {from_number}")

def get_message_count(contact_number: str, on_date: date) -> int:
    with Session(engine) as session:
        customer = session.exec(
            select(Customer).where(Customer.contact == contact_number)
        ).first()

        if not customer:
            return 0  # No customer exists, so message count is zero

        session_record = session.exec(
            select(ChatSession).where(
                ChatSession.cust_id == customer.id,
                ChatSession.date == on_date
            )
        ).first()

        return session_record.count if session_record else 0

def increment_message_count(contact_number: str, on_date: date) -> None:
    with Session(engine) as session:
        customer = session.exec(
            select(Customer).where(Customer.contact == contact_number)
        ).first()

        if not customer:
            return  # Customer doesn't exist

        session_record = session.exec(
            select(ChatSession).where(ChatSession.cust_id == customer.id)
        ).first()

        if not session_record:
            return  # No existing session, and we don't create a new one

        if session_record.date != on_date:
            session_record.date = on_date
            session_record.count = 1  # Reset for new day
        else:
            session_record.count += 1  # Increment for same day

        session.commit()

# ---------------------- EMBEDDING HELPERS ----------------------




def insert_rule_chunks(source_id: int, chunks: List[str]):
    try:
        embeddings = embedder.embed_documents(chunks)
        records = [
            RuleChunk(
                content=chunk,
                embedding=embedding,
                source_id=source_id
            )
            for chunk, embedding in zip(chunks, embeddings)
        ]

        print("records created, storing in database")

        with Session(engine) as session:
            session.add_all(records)
            session.commit()

        print("inserted")

        return {"message": f"Inserted {len(records)} rule chunks successfully."}

    except Exception as e:
        print("Error inserting rule chunks:", str(e))
        raise HTTPException(status_code=500, detail=str(e))


def insert_apartments(listings: List[dict], listing_to_text, source_id: int):
    texts = [listing_to_text(l) for l in listings]
    embeddings = embedder.embed_documents(texts)
    with SessionLocal() as session:
        for listing, text, emb in zip(listings, texts, embeddings):
            session.add(ApartmentListing(
                source_id=source_id,
                text=text,
                listing_metadata=listing,
                embedding=emb
            ))
        session.commit()


# ---------------------- INGEST DATA ----------------------

def ingest_apartment_data(data: Union[str, List[Dict[str, Any]]], from_file: bool = False):
    if from_file:
        with open(data, "r") as f:
            listings_raw = json.load(f)
    else:
        listings_raw = data

    if not isinstance(listings_raw, list):
        raise ValueError("Expected a list of listings (dicts).")

    documents = []
    for listing in listings_raw:
        try:
            serialized = json.dumps(listing, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Skipping a listing due to serialization error: {e}")
            continue
        documents.append(Document(page_content=serialized, metadata={"source": "MLS"}))

    if documents:
        embed_documents([doc.page_content for doc in documents])
        print(f"Successfully ingested {len(documents)} documents.")
    else:
        print("No documents to ingest.")

# ---------------------- SEARCH ----------------------

def search_rules(query: str, source_id: int, k: int = 3) -> List[str]:
    qvec = embed_text(query)
    qvec_str = "[" + ",".join(f"{x:.6f}" for x in qvec) + "]"

    sql = text(f"""
        SELECT content 
        FROM rulechunk
        WHERE source_id = :source_id
        ORDER BY embedding <=> '{qvec_str}'::vector
        LIMIT :k
    """)
    with SessionLocal() as session:
        rows = session.execute(sql, {"source_id": source_id, "k": k}).all()
        return [r[0] for r in rows]


def search_apartments(query: str, k: int = 5) -> List[Dict]:
    qvec = embed_text(query)
    qvec_str = "[" + ",".join(f"{x:.6f}" for x in qvec) + "]"
    sql = text(f"""
        SELECT listing_metadata FROM apartmentlisting
        ORDER BY embedding <=> '{qvec_str}'::vector
        LIMIT :k
    """)
    with SessionLocal() as session:
        rows = session.execute(sql, {"k": k}).all()
        return [r[0] for r in rows]

# ---------------------- OPTIONAL: Fetch from URL ----------------------

def fetch_apartments_from_url():
    response = requests.get("https://zillow.com/mls/listings")
    if response.ok:
        listings = response.json()
        ingest_apartment_data(listings, from_file=False)
    else:
        print("API call failed:", response.status_code)

def create_booking_entry(address: str, booking_date: date, booking_time: time, contact: str) -> Booking:
    with Session(engine) as session:
        # Step 1: Get the customer by contact number
        customer = session.exec(
            select(Customer).where(Customer.contact == contact)
        ).first()
        if not customer:
            raise ValueError(f"No customer found with contact: {contact}")

        # Step 2: Get the first available realtor
        realtor = session.exec(select(Realtor)).first()
        if not realtor:
            raise ValueError("No realtor found in the system.")

        # Step 3: Create a booking entry
        new_booking = Booking(
            address=address,
            date=booking_date,
            time=booking_time,
            visited=False,
            cust_feedback=None,
            cust_id=customer.id,
            realtor_id=realtor.id
        )

        session.add(new_booking)
        session.commit()
        session.refresh(new_booking)
        return new_booking

#------------------ CRUD---------------------------

def create_customer_entry(name: str, email: str, contact: str, if_tenant: Optional[str] = None) -> Customer:
    with Session(engine) as session:
        print("contact Received:",contact)
        existing_customer = session.exec(
            select(Customer).where(Customer.contact == contact)
        ).first()

        if existing_customer:
            existing_customer.name = name
            existing_customer.email = email
            session.commit()
            session.refresh(existing_customer)
            return existing_customer
        else:
            new_customer = Customer(
                name=name,
                email=email,
                contact=contact,
                if_tenant=if_tenant
            )
            session.add(new_customer)
            session.commit()
            session.refresh(new_customer)
            return new_customer
