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
load_dotenv()

# ---------------------- DATABASE CONFIG ----------------------
DATABASE_URL = (
    "postgresql+psycopg2://postgres.cmpywleowxnvucymvwgv:Superman%40_%2511223344"
    "@aws-0-us-west-1.pooler.supabase.com:5432/postgres?sslmode=require"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# ---------------------- MODELS ----------------------

class Realtor(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True, alias="realtor_id")
    name: str
    email: str
    contact: str
    twilio_contact: str
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
        genai.configure(api_key="AIzaSyA_kWzpMyEwBv2hxLOVE8f9CUpXYoW6z7U")
        self.model_name = model_name

    def embed_text(self, text: str) -> list:
        res = genai.embed_content(model=self.model_name, content=text, task_type="retrieval_document")
        return res["embedding"]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(t) for t in texts]
    
EMBED_DIM = 768
#embedder = HuggingFaceEmbeddings(model_name="BAAI/bge-base-en")
embedder = GeminiEmbedder()  



def embed_text(text: str) -> List[float]:
    return embedder.embed_text(text)
#embedder.embed_query(text)
def embed_documents(texts: List[str]) -> List[List[float]]:
    return embedder.embed_documents(texts)


# ---------------------- INITIALIZATION ----------------------

def init_db():
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    SQLModel.metadata.create_all(engine)


#------------------------Embedding Init---------------------------
def init_vector_db(rules_path="Rules.txt", apartments_path="data.json", listing_to_text=None):
    init_db()  # Ensure tables and vector extension are initialized

    # with SessionLocal() as session:
        # Ensure a Realtor exists
        # realtor = session.query(Realtor).first()
        # if not realtor:
        #     realtor = Realtor(name="Default Realtor", email="default@example.com", contact="0000000000", twilio_contact="default_twilio")
        #     session.add(realtor)
        #     session.commit()
        #     session.refresh(realtor)

        # # Ensure a Source exists for that Realtor
        # source = session.query(Source).filter_by(realtor_id=realtor.id).first()
        # if not source:
        #     source = Source(name="Default Source", realtor_id=realtor.id)
        #     session.add(source)
        #     session.commit()
        #     session.refresh(source)

        # default_source_id = source.id

    # Default text formatter for listings
    # if listing_to_text is None:
    #     def listing_to_text(d):
    #         return (
    #             f"{d.get('bedrooms', '?')} bed, {d.get('bathrooms', '?')} bath "
    #             f"{d.get('property_type', '')} in {d.get('address', '')}, "
    #             f"listed at ${d.get('price', '?')} with {d.get('square_feet', '?')} sqft. "
    #             f"Features: {', '.join(d.get('features', []))}"
    #         )

    #Dont need this now as rule chunks are created when realtors are created
    # with SessionLocal() as session:
    #     # Insert Rule Chunks if missing
    #     if not session.query(RuleChunk).first() and os.path.exists(rules_path):
            

    #         loader = TextLoader(rules_path)
    #         docs = loader.load()
    #         splitter = CharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    #         chunks = [c.page_content for c in splitter.split_documents(docs)]

    #         print(f"Inserting {len(chunks)} rule chunks...")
    #         insert_rule_chunks(chunks, source_id=default_source_id)

        # Insert Apartment Listings if missing
        # if not session.query(ApartmentListing).first() and os.path.exists(apartments_path):
        #     with open(apartments_path, "r", encoding="utf-8") as f:
        #         listings = json.load(f)

        #     print(f"Inserting {len(listings)} apartment listings...")
        #     insert_apartments(listings, listing_to_text, source_id=default_source_id)



#---------------------CRUD OPERATIONS----------------------------



SUPABASE_URL = "https://cmpywleowxnvucymvwgv.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
BUCKET_NAME = "realtor-files"
from typing import Optional
import json, csv, io, requests
from langchain.schema import Document
from langchain.text_splitter import CharacterTextSplitter



def listing_to_text(listing: dict) -> str:
    """
    Convert a listing dictionary into a readable text format.
    """
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

def create_realtor_with_files(
    name: str,
    email: str,
    contact: str,
    files: List[UploadFile],
    listing_file: Optional[UploadFile] = None,
    listing_api_url: Optional[str] = None
):
    with Session(engine) as session:
        # 1. Check for duplicate realtor
        existing_realtor = session.exec(
            select(Realtor).where((Realtor.email == email) | (Realtor.contact == contact))
        ).first()

        if existing_realtor:
            raise HTTPException(status_code=400, detail="Realtor with this email or contact already exists")

        # 2. Create new Realtor
        realtor = Realtor(
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

        uploaded_files = []
        splitter = CharacterTextSplitter(separator="\n", chunk_size=500, chunk_overlap=50)
        all_chunks = []

        # 4. Process each document file (rules/guidelines)
        for file in files:
            content_bytes = file.file.read()
            file_content = content_bytes.decode("utf-8")
            file_path = f"realtors/{realtor.id}/{file.filename}"

            # Upload to Supabase
            response = supabase.storage.from_(BUCKET_NAME).upload(
                file_path,
                content_bytes,
                file_options={"content-type": file.content_type}
            )

            if isinstance(response, dict) and "error" in response:
                raise HTTPException(status_code=500, detail=response["error"]["message"])

            file_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{file_path}"
            uploaded_files.append(file_url)
            print("files uploaded:",uploaded_files)

            # Split and collect chunks
            document = Document(page_content=file_content, metadata={"source": file.filename})
            chunk_docs = splitter.split_documents([document])
            chunks = [doc.page_content for doc in chunk_docs]
            all_chunks.extend(chunks)


        # 5. Insert rule chunks into DB
        insert_rule_chunks(all_chunks, source_id=source.id)
        print("rules chunk inserted")

        # 6. Handle listing data: file OR API URL
        listing_chunks = []
        listing_text = ""

        if listing_file:
            content = listing_file.file.read()
            if listing_file.filename.endswith(".json"):
                print("received json")
                parsed = json.loads(content)
                listing_text = json.dumps(parsed, indent=2)
            elif listing_file.filename.endswith(".csv"):
                print("received csv")
                decoded = content.decode("utf-8")
                reader = csv.DictReader(io.StringIO(decoded))
                rows = [row for row in reader]
                listing_text = json.dumps(rows, indent=2)
            else:
                raise HTTPException(status_code=400, detail="Unsupported listing file format")

            # Upload the listing file to Supabase
            listing_path = f"realtors/{realtor.id}/listings/{listing_file.filename}"
            response = supabase.storage.from_(BUCKET_NAME).upload(
                listing_path,
                content,
                file_options={"content-type": listing_file.content_type}
            )
            print("uploaded lisitng file")

        elif listing_api_url:
            response = requests.get(listing_api_url)
            if response.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to fetch data from API URL")
            listing_data = response.json()
            listing_text = json.dumps(listing_data, indent=2)
            print("fetched data")

        if listing_text:
            try:
                listings = json.loads(listing_text)
                if isinstance(listings, dict):  # ensure it's a list
                    listings = [listings]
        
                formatted_texts = [listing_to_text(l) for l in listings]
                embeddings = embed_documents(formatted_texts)

                listing_records = [
                    {"text": formatted_texts[i], "metadata": listings[i], "embedding": embeddings[i]}
                    for i in range(len(listings))
                ]

                insert_listing_records(realtor.id, listing_records)

                print("Listings processed successfully.")
            except Exception as e:
                print("add_listings error:", e)
                raise HTTPException(status_code=500, detail=f"Failed to process listing: {e}")


        # 8. Return response
        auth_link = f"https://2aab9bffd32f.ngrok-free.app/authorize?realtor_id={realtor.id}"

        return {
            "message": "Realtor created, rules uploaded, listings processed (not stored)",
            "realtor": {
                "id": realtor.id,
                "name": realtor.name,
                "email": realtor.email,
                "contact": realtor.contact
            },
            "uploaded_files": uploaded_files,
            "listing_file_provided": bool(listing_file),
            "listing_api_url": listing_api_url,
            "auth_link": auth_link
        }



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


def insert_rule_chunks(chunks: List[str], source_id: int):
    embeddings = embedder.embed_documents(chunks)
    with SessionLocal() as session:
        for chunk, emb in zip(chunks, embeddings):
            session.add(RuleChunk(content=chunk, embedding=emb, source_id=source_id))
        session.commit()

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

def search_rules(query: str, k: int = 3) -> List[str]:
    qvec = embed_text(query)
    qvec_str = "[" + ",".join(f"{x:.6f}" for x in qvec) + "]"
    sql = text(f"""
        SELECT content FROM rulechunk
        ORDER BY embedding <=> '{qvec_str}'::vector
        LIMIT :k
    """)
    with SessionLocal() as session:
        rows = session.execute(sql, {"k": k}).all()
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




#----------------testing-----------------------------
# from sqlmodel import Session, select
# from typing import List
# import numpy as np
# from sqlalchemy import text
# from secondary_db import ApartmentListingStore
# COSINE_SIM_THRESHOLD = 0.1  # Lower is more similar (0 = identical)


# def sync_apartments(source_id: int):
#     with Session(engine1) as test_session, Session(engine) as main_session:
        
#         test_listings: List[ApartmentListingStore] = test_session.exec(
#             select(ApartmentListingStore)
#         ).all()

#         inserted_count = 0

#         for test_listing in test_listings:
#             # Format embedding as a Postgres vector literal
#             embedding_str = "[" + ",".join(map(str, test_listing.embedding)) + "]"

#             # Prepare raw SQL with parameters and cosine search
#             result = main_session.exec(
#                 text("""
#                     SELECT id, embedding <-> :embedding AS cosine_distance
#                     FROM apartmentlisting
#                     ORDER BY embedding <-> :embedding
#                     LIMIT 1
#                 """).params(embedding=embedding_str)
#             ).first()

#             # If similar listing exists (below threshold), skip insertion
#             if result and result.cosine_distance < COSINE_SIM_THRESHOLD:
#                 print(result.cosine_distance)
#                 print("Skipped due to similarity.")
#                 continue

#             # Insert new unique listing
#             new_listing = ApartmentListing(
#                 source_id=source_id,
#                 text=test_listing.text,
#                 listing_metadata=test_listing.listing_metadata,
#                 embedding=test_listing.embedding,
#             )
#             main_session.add(new_listing)
#             inserted_count += 1

#         main_session.commit()
#         print(f"Sync complete: {inserted_count} new listings added from test DB.")
