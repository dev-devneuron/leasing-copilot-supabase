"""
Database Models and Configuration

This module contains:
- Database connection setup
- SQLModel table definitions for all entities
- Embedding utilities for vector search
- Data access scope functions for multi-tenant isolation
"""

from typing import Optional, List, Dict, Any, Union
from datetime import date, time, datetime
from uuid import UUID
import os
import json
import csv
import io
import requests
import jwt
import google.generativeai as genai
from dotenv import load_dotenv

# SQLModel and SQLAlchemy imports
from sqlmodel import (
    SQLModel,
    Field,
    create_engine,
    Session,
    Relationship,
    select,
    Column,
    PrimaryKeyConstraint,
)
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import sessionmaker
from pgvector.sqlalchemy import Vector

# Langchain imports for embeddings and document processing
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import CharacterTextSplitter

# Supabase imports
from supabase import create_client, Client

# FastAPI imports
from fastapi import UploadFile, File, Form, HTTPException, APIRouter

# Local imports
from .secondary_db import insert_listing_records
from config import (
    BUCKET_NAME,
    SUPABASE_URL,
    SUPABASE_KEY,
    DATABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY,
)

load_dotenv()

# ============================================================================
# DATABASE CONNECTION CONFIGURATION
# ============================================================================

if DATABASE_URL:
    # Create database engine with connection pooling and better error handling
    engine = create_engine(
        DATABASE_URL, 
        pool_pre_ping=True,  # Verify connections before using
        pool_size=5,  # Number of connections to maintain
        max_overflow=10,  # Additional connections beyond pool_size
        pool_recycle=3600,  # Recycle connections after 1 hour
        echo=False  # Set to True for SQL query logging
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
else:
    engine = None
    SessionLocal = None

# ============================================================================
# DATABASE MODELS
# ============================================================================

class PropertyManager(SQLModel, table=True):
    """
    Property Manager entity.
    
    Represents a property management company or individual property manager.
    Can manage multiple realtors and own multiple property listings.
    """
    property_manager_id: Optional[int] = Field(default=None, primary_key=True)
    auth_user_id: UUID = Field(index=True)  # Links to Supabase Auth user
    name: str
    email: str
    contact: str
    company_name: Optional[str] = None
    twilio_contact: str  # Phone number for SMS/WhatsApp (legacy or purchased)
    twilio_sid: Optional[str] = None  # Twilio SID (legacy)
    credentials: Optional[str] = Field(default=None)  # Google Calendar credentials (JSON string)
    
    # Phone number assignment (new system)
    purchased_phone_number_id: Optional[int] = Field(
        default=None, 
        foreign_key="purchasedphonenumber.purchased_phone_number_id"
    )

    # Call forwarding state
    carrier: Optional[str] = None  # User's mobile carrier (e.g., "AT&T", "Verizon", "T-Mobile", "Mint", "Metro", "Google Fi", "Xfinity Mobile")
    business_forwarding_enabled: bool = Field(default=False)
    after_hours_enabled: bool = Field(default=False)
    last_after_hours_update: Optional[datetime] = None
    business_forwarding_confirmed_at: Optional[datetime] = None
    after_hours_last_enabled_at: Optional[datetime] = None
    after_hours_last_disabled_at: Optional[datetime] = None
    forwarding_failure_reason: Optional[str] = None
    last_forwarding_update: Optional[datetime] = None
    
    # Timestamps
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    # Relationships
    managed_realtors: List["Realtor"] = Relationship(back_populates="property_manager")
    sources: List["Source"] = Relationship(back_populates="property_manager")
    phone_number_requests: List["PhoneNumberRequest"] = Relationship(back_populates="property_manager")
    purchased_phone_numbers: List["PurchasedPhoneNumber"] = Relationship(
        back_populates="property_manager",
        sa_relationship_kwargs={"foreign_keys": "[PurchasedPhoneNumber.property_manager_id]"}
    )
    purchased_phone_number: Optional["PurchasedPhoneNumber"] = Relationship(
        back_populates="assigned_property_manager",
        sa_relationship_kwargs={"foreign_keys": "[PropertyManager.purchased_phone_number_id]"}
    )
    tenants: List["Tenant"] = Relationship()
    maintenance_requests: List["MaintenanceRequest"] = Relationship()


class Realtor(SQLModel, table=True):
    """
    Realtor entity that always belongs to a Property Manager.
    
    Realtors can own property listings (assigned from their PM) and have bookings.
    """
    realtor_id: Optional[int] = Field(default=None, primary_key=True)
    auth_user_id: UUID = Field(index=True)  # Links to Supabase Auth user
    name: str
    email: str
    contact: str
    twilio_contact: str  # Phone number for SMS/WhatsApp (legacy or purchased)
    twilio_sid: Optional[str] = None  # Twilio SID (legacy)
    credentials: Optional[str] = Field(default=None)  # Google Calendar credentials (JSON string)
    
    # Property Manager relationship (required)
    property_manager_id: int = Field(
        foreign_key="propertymanager.property_manager_id",
        nullable=False,
    )
    
    # Phone number assignment (new system)
    purchased_phone_number_id: Optional[int] = Field(
        default=None, 
        foreign_key="purchasedphonenumber.purchased_phone_number_id"
    )

    # Call forwarding state
    carrier: Optional[str] = None  # User's mobile carrier (e.g., "AT&T", "Verizon", "T-Mobile", "Mint", "Metro", "Google Fi", "Xfinity Mobile")
    business_forwarding_enabled: bool = Field(default=False)
    after_hours_enabled: bool = Field(default=False)
    last_after_hours_update: Optional[datetime] = None
    business_forwarding_confirmed_at: Optional[datetime] = None
    after_hours_last_enabled_at: Optional[datetime] = None
    after_hours_last_disabled_at: Optional[datetime] = None
    forwarding_failure_reason: Optional[str] = None
    last_forwarding_update: Optional[datetime] = None
    
    # Timestamps
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    # Relationships
    property_manager: Optional["PropertyManager"] = Relationship(back_populates="managed_realtors")
    sources: List["Source"] = Relationship(back_populates="realtor")
    bookings: List["Booking"] = Relationship(back_populates="realtor")
    purchased_phone_number: Optional["PurchasedPhoneNumber"] = Relationship(back_populates="assigned_realtor")
    assigned_maintenance_requests: List["MaintenanceRequest"] = Relationship(back_populates="assigned_realtor")
    tenants: List["Tenant"] = Relationship()  # Tenants this realtor helped rent properties to


class Customer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True, alias="cust_id")
    name: Optional[str] = None
    email: Optional[str] = None
    contact: str
    if_tenant: Optional[str] = None

    bookings_as_customer: List["Booking"] = Relationship(
        back_populates="customer",
        sa_relationship_kwargs={"foreign_keys": "[Booking.cust_id]"},
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
    realtor_id: Optional[int] = Field(default=None, foreign_key="realtor.realtor_id")

    customer: Optional[Customer] = Relationship(
        back_populates="bookings_as_customer",
        sa_relationship_kwargs={"foreign_keys": "[Booking.cust_id]"},
    )
    realtor: Optional[Realtor] = Relationship(back_populates="bookings")


class RuleChunk(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)  # Auto-increment primary key
    source_id: int = Field(foreign_key="source.source_id")

    content: str
    embedding: List[float] = Field(sa_column=Column(Vector(768)))

    source: Optional["Source"] = Relationship(back_populates="rule_chunks")


class ApartmentListing(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    source_id: int = Field(foreign_key="source.source_id")

    text: str
    listing_metadata: Dict[str, Any] = Field(sa_column=Column(JSON))
    embedding: List[float] = Field(sa_column=Column(Vector(768)))

    source: Optional["Source"] = Relationship(back_populates="listings")
    tenants: List["Tenant"] = Relationship()
    maintenance_requests: List["MaintenanceRequest"] = Relationship()


class Source(SQLModel, table=True):
    """
    Source entity for grouping listings and rules.
    
    A Source represents a collection of listings and rules that belong to either:
    - A Property Manager (property_manager_id set)
    - A Realtor (realtor_id set)
    
    This allows for data organization and access control. When listings are uploaded,
    they are associated with a Source, which determines who can access them.
    """
    source_id: Optional[int] = Field(default=None, primary_key=True)
    
    # Ownership: Source belongs to either PM or Realtor (at least one must be set)
    property_manager_id: int = Field(
        foreign_key="propertymanager.property_manager_id",
        nullable=False,
    )
    realtor_id: Optional[int] = Field(
        default=None, 
        foreign_key="realtor.realtor_id"
    )
    
    # Database constraint: At least one owner must be set
    __table_args__ = (
        PrimaryKeyConstraint('source_id'),
    )

    property_manager: Optional["PropertyManager"] = Relationship(back_populates="sources")
    realtor: Optional[Realtor] = Relationship(back_populates="sources")
    rule_chunks: List["RuleChunk"] = Relationship(back_populates="source")
    listings: List["ApartmentListing"] = Relationship(back_populates="source")


class DemoRequest(SQLModel, table=True):
    """Stores demo booking requests from potential customers."""
    demo_request_id: Optional[int] = Field(default=None, primary_key=True)
    
    # Contact information
    name: str
    email: str
    phone: str
    company_name: Optional[str] = None
    
    # Demo preferences
    preferred_date: Optional[date] = None
    preferred_time: Optional[str] = None  # e.g., "10:00 AM", "2:00 PM"
    timezone: Optional[str] = None  # e.g., "America/New_York"
    notes: Optional[str] = None  # Additional information from requester
    
    # Status tracking
    status: str = Field(default="pending")  # pending, scheduled, completed, cancelled, converted
    scheduled_at: Optional[datetime] = None  # When demo is actually scheduled
    completed_at: Optional[datetime] = None  # When demo was completed
    
    # Conversion tracking
    converted_to_pm_id: Optional[int] = Field(default=None, foreign_key="propertymanager.property_manager_id")
    converted_at: Optional[datetime] = None
    
    # Timestamps
    requested_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    
    # Relationship (if converted to PM)
    converted_property_manager: Optional["PropertyManager"] = Relationship()


class PhoneNumberRequest(SQLModel, table=True):
    """Stores PM requests for phone numbers."""
    request_id: Optional[int] = Field(default=None, primary_key=True)
    property_manager_id: int = Field(foreign_key="propertymanager.property_manager_id", index=True)
    
    # Request details
    country_code: Optional[str] = None  # Country code (e.g., "+1", "1", "+44")
    area_code: Optional[str] = None  # Preferred area code (3-digit, e.g., "412")
    status: str = Field(default="pending")  # pending, approved, fulfilled, cancelled
    notes: Optional[str] = None  # Any additional notes from PM
    
    # Timestamps
    requested_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    fulfilled_at: Optional[datetime] = None
    
    # Relationship
    property_manager: Optional["PropertyManager"] = Relationship(back_populates="phone_number_requests")


class PurchasedPhoneNumber(SQLModel, table=True):
    """Stores phone numbers purchased by tech team for PMs."""
    purchased_phone_number_id: Optional[int] = Field(default=None, primary_key=True)
    property_manager_id: int = Field(foreign_key="propertymanager.property_manager_id", index=True)
    
    # Phone number details
    phone_number: str = Field(unique=True, index=True)  # E.164 format: +14125551234
    twilio_sid: str = Field(unique=True, index=True)  # Twilio SID
    vapi_phone_number_id: Optional[str] = None  # VAPI phone number ID
    
    # Assignment status
    status: str = Field(default="available")  # available, assigned, inactive
    assigned_to_type: Optional[str] = None  # "property_manager" or "realtor"
    assigned_to_id: Optional[int] = None  # ID of PM or Realtor
    
    # Timestamps
    purchased_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    assigned_at: Optional[datetime] = None
    
    # Notes
    notes: Optional[str] = None  # Internal notes from tech team
    
    # Relationships
    property_manager: Optional["PropertyManager"] = Relationship(
        back_populates="purchased_phone_numbers",
        sa_relationship_kwargs={"foreign_keys": "[PurchasedPhoneNumber.property_manager_id]"}
    )
    assigned_property_manager: Optional["PropertyManager"] = Relationship(
        back_populates="purchased_phone_number",
        sa_relationship_kwargs={"foreign_keys": "[PropertyManager.purchased_phone_number_id]"}
    )
    assigned_realtor: Optional["Realtor"] = Relationship(
        back_populates="purchased_phone_number",
        sa_relationship_kwargs={"foreign_keys": "[Realtor.purchased_phone_number_id]"}
    )


class CallForwardingEvent(SQLModel, table=True):
    """Audit log for call forwarding state changes."""
    event_id: Optional[int] = Field(default=None, primary_key=True)
    target_user_type: str = Field(index=True)  # property_manager or realtor
    target_user_id: int = Field(index=True)
    action: str  # e.g., business_enable, after_hours_on, after_hours_off, state_update
    initiated_by_user_type: str
    initiated_by_user_id: int
    event_metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSONB)  # Allows storing dial codes, frontend context, etc.
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CallRecord(SQLModel, table=True):
    """Stores call records from VAPI including transcripts and recordings."""
    id: Optional[UUID] = Field(default=None, primary_key=True)
    call_id: str = Field(
        index=True,
        unique=True,
        sa_column_kwargs={"unique": True}  # Ensure call_id is unique to prevent duplicates
    )  # VAPI call ID (unique)
    realtor_number: str = Field(index=True)  # Twilio DID that received the call
    recording_url: Optional[str] = None  # MP3 file URL from VAPI
    transcript: Optional[str] = None  # Final transcript text
    live_transcript_chunks: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(JSON)  # Store real-time transcript chunks as array
    )
    call_duration: Optional[int] = None  # Duration in seconds
    call_status: Optional[str] = None  # e.g., "ended", "failed", "no-answer"
    caller_number: Optional[str] = Field(default=None, index=True)  # Phone number of the caller (indexed for search)
    call_metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSONB)  # Store additional VAPI event data
    )
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Tenant(SQLModel, table=True):
    """
    Tenant entity representing a person renting a property.
    
    Tenants are associated with properties (ApartmentListing) and can submit
    maintenance requests via phone, text, or email through the AI bot.
    
    When a tenant is created, the property's listing_status is automatically
    updated to "Rented" to mark it as unavailable.
    """
    tenant_id: Optional[int] = Field(default=None, primary_key=True)
    
    # Tenant identification
    name: str = Field(index=True)  # Tenant's full name
    phone_number: Optional[str] = Field(default=None, index=True)  # Phone number (E.164 format: +14125551234)
    email: Optional[str] = Field(default=None, index=True)  # Email address
    
    # Property relationship
    property_id: int = Field(
        foreign_key="apartmentlisting.id",
        index=True
    )  # The property/apartment this tenant rents
    
    # Property Manager relationship (for data isolation)
    property_manager_id: int = Field(
        foreign_key="propertymanager.property_manager_id",
        index=True
    )  # The PM who manages this tenant's property
    
    # Realtor relationship (optional - tracks which realtor helped rent the property)
    realtor_id: Optional[int] = Field(
        default=None,
        foreign_key="realtor.realtor_id",
        index=True
    )  # The realtor who helped rent this property (if applicable)
    
    # Lease information
    lease_start_date: Optional[date] = None  # When the lease started
    lease_end_date: Optional[date] = None  # When the lease ends (property becomes available again)
    is_active: bool = Field(default=True, index=True)  # Whether this tenant is currently active (not moved out)
    
    # Optional metadata
    unit_number: Optional[str] = None  # Unit/apartment number (e.g., "Apt 3B", "Unit 5")
    notes: Optional[str] = None  # Additional notes about the tenant
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    property: Optional["ApartmentListing"] = Relationship()
    property_manager: Optional["PropertyManager"] = Relationship()
    realtor: Optional["Realtor"] = Relationship()
    maintenance_requests: List["MaintenanceRequest"] = Relationship(back_populates="tenant")


class MaintenanceRequest(SQLModel, table=True):
    """
    Maintenance request submitted by a tenant.
    
    Created when a tenant calls/texts the AI bot to report a maintenance issue.
    Property Managers can view and manage these requests in their dashboard.
    """
    maintenance_request_id: Optional[int] = Field(default=None, primary_key=True)
    
    # Tenant relationship
    tenant_id: int = Field(
        foreign_key="tenant.tenant_id",
        index=True
    )
    
    # Property relationship
    property_id: int = Field(
        foreign_key="apartmentlisting.id",
        index=True
    )
    
    # Property Manager relationship (for data isolation)
    property_manager_id: int = Field(
        foreign_key="propertymanager.property_manager_id",
        index=True
    )
    
    # Request details
    issue_description: str  # Description of the maintenance issue
    priority: str = Field(default="normal")  # "low", "normal", "high", "urgent"
    status: str = Field(default="pending", index=True)  # "pending", "in_progress", "completed", "cancelled"
    
    # Optional details
    category: Optional[str] = None  # e.g., "plumbing", "electrical", "appliance", "heating", "other"
    location: Optional[str] = None  # Specific location in the property (e.g., "Kitchen", "Bathroom", "Bedroom 2")
    
    # Contact information (snapshot at time of request)
    tenant_name: str  # Tenant name at time of request
    tenant_phone: Optional[str] = None  # Tenant phone at time of request
    tenant_email: Optional[str] = None  # Tenant email at time of request
    
    # Request metadata
    submitted_via: str = Field(default="phone")  # "phone", "text", "email"
    vapi_call_id: Optional[str] = None  # VAPI call ID if submitted via phone/text
    call_transcript: Optional[str] = None  # Transcript of the call if available
    
    # PM/Realtor response
    assigned_to_realtor_id: Optional[int] = Field(
        default=None,
        foreign_key="realtor.realtor_id"
    )  # Optional: assign to specific realtor
    pm_notes: Optional[str] = None  # Internal notes from PM
    resolution_notes: Optional[str] = None  # Notes about how the issue was resolved
    
    # Timestamps
    submitted_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None  # When the request was marked as completed
    
    # Relationships
    tenant: Optional["Tenant"] = Relationship(back_populates="maintenance_requests")
    property: Optional["ApartmentListing"] = Relationship()
    property_manager: Optional["PropertyManager"] = Relationship()
    assigned_realtor: Optional["Realtor"] = Relationship()

# ---------------------- EMBEDDING SETUP ----------------------
class GeminiEmbedder:
    """
    Embedder that uses Vertex AI (preferred) or Gemini API (fallback).
    Provides robust embeddings for RAG and similarity search.
    """
    def __init__(self, model_name="models/embedding-001"):
        from .vertex_ai_client import get_vertex_ai_client
        from config import USE_VERTEX_AI
        
        self.vertex_client = None
        self.model_name = model_name
        self.use_vertex_ai = USE_VERTEX_AI
        
        if self.use_vertex_ai:
            try:
                self.vertex_client = get_vertex_ai_client()
                if self.vertex_client.is_available():
                    print("✅ Using Vertex AI for embeddings")
                else:
                    print("⚠️  Vertex AI not available, falling back to Gemini API")
                    self.use_vertex_ai = False
            except Exception as e:
                print(f"⚠️  Vertex AI initialization failed: {e}, using Gemini API")
                self.use_vertex_ai = False
        
        if not self.use_vertex_ai:
            # Fallback to Gemini API
            embd_key = os.getenv("GEMINI_API_KEY")
            if embd_key:
                genai.configure(api_key=embd_key)
                print("✅ Using Gemini API for embeddings")
            else:
                print("⚠️  No embedding API key found")

    def embed_text(self, text: str) -> list:
        """Generate embedding for a single text."""
        if self.use_vertex_ai and self.vertex_client:
            try:
                return self.vertex_client.embed_text(text, task_type="retrieval_document")
            except Exception as e:
                print(f"Vertex AI embedding error: {e}, falling back to Gemini API")
                return self._gemini_embed(text)
        else:
            return self._gemini_embed(text)
    
    def _gemini_embed(self, text: str) -> list:
        """Fallback to Gemini API embedding."""
        try:
            res = genai.embed_content(
                model=self.model_name, content=text, task_type="retrieval_document"
            )
            return res["embedding"]
        except Exception as e:
            print(f"Gemini API embedding error: {e}")
            raise

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple documents."""
        if self.use_vertex_ai and self.vertex_client:
            try:
                return self.vertex_client.embed_documents(texts, task_type="retrieval_document")
            except Exception as e:
                print(f"Vertex AI batch embedding error: {e}, falling back to individual calls")
                return [self.embed_text(t) for t in texts]
        else:
            return [self.embed_text(t) for t in texts]


# embedder = HuggingFaceEmbeddings(model_name="BAAI/bge-base-en")
embedder = GeminiEmbedder()


def embed_text(text: str) -> List[float]:
    return embedder.embed_text(text)


# embedder.embed_query(text) if using huggingface embedder
def embed_documents(texts: List[str]) -> List[List[float]]:
    return embedder.embed_documents(texts)


# ---------------------- INITIALIZATION ----------------------


def init_db():
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    SQLModel.metadata.create_all(engine)


# ---------------------CRUD OPERATIONS----------------------------

supabase = create_client(
    os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY")
)
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
if SUPABASE_SERVICE_KEY and SUPABASE_SERVICE_KEY != "dummy":
    try:
        decoded = jwt.decode(SUPABASE_SERVICE_KEY, options={"verify_signature": False})
    except:
        decoded = None
else:
    decoded = None


def listing_to_text(listing: dict) -> str:
    """
    Convert listing dictionary to text format for embedding.
    Handles normalized listing data from the AI parser.
    """
    try:
        # Build text representation with available fields
        parts = []
        
        address = listing.get('address', 'N/A')
        if address and address != 'N/A':
            parts.append(f"Address: {address}")
        
        price = listing.get('price')
        if price is not None:
            parts.append(f"Price: {price}")
        
        bedrooms = listing.get('bedrooms')
        if bedrooms is not None:
            parts.append(f"Bedrooms: {bedrooms}")
        
        bathrooms = listing.get('bathrooms')
        if bathrooms is not None:
            parts.append(f"Bathrooms: {bathrooms}")
        
        # Add property type if available
        property_type = listing.get('property_type')
        if property_type:
            parts.append(f"Property Type: {property_type}")
        
        # Add square feet if available
        square_feet = listing.get('square_feet')
        if square_feet:
            parts.append(f"Square Feet: {square_feet}")
        
        # Add features if available
        features = listing.get('features', [])
        if features and isinstance(features, list) and len(features) > 0:
            features_str = ', '.join(str(f) for f in features)
            parts.append(f"Features: {features_str}")
        
        # Add description if available
        description = listing.get('description', '')
        if description:
            parts.append(f"Description: {description}")
        
        # Join all parts
        text = ". ".join(parts)
        if not text:
            text = "Property listing information"
        
        return text
        
    except Exception as e:
        print("listing_to_text error:", e)
        return "Invalid listing format."


def create_property_manager(
    auth_user_id: str,
    name: str,
    email: str,
    contact: str,
    company_name: str = None,
):
    """Create a new Property Manager."""
    with Session(engine) as session:
        # Check for duplicate property manager
        existing_pm = session.exec(
            select(PropertyManager).where(
                (PropertyManager.email == email) | (PropertyManager.contact == contact)
            )
        ).first()

        if existing_pm:
            raise HTTPException(
                status_code=400,
                detail="Property Manager with this email or contact already exists",
            )

        # Create new Property Manager
        property_manager = PropertyManager(
            auth_user_id=auth_user_id,
            name=name,
            email=email,
            contact=contact,
            company_name=company_name,
            twilio_contact="TBD",
        )
        session.add(property_manager)
        session.commit()
        session.refresh(property_manager)
        print("Property Manager created")

        # Ensure Source for Property Manager
        source = create_source(property_manager_id=property_manager.property_manager_id)
        print("Source created for Property Manager")

        auth_link = f"https://leasing-copilot-supabase.onrender.com/authorize?property_manager_id={property_manager.property_manager_id}"

        return {
            "message": "Property Manager created successfully",
            "property_manager": {
                "id": property_manager.property_manager_id,
                "name": property_manager.name,
                "email": property_manager.email,
                "contact": property_manager.contact,
                "company_name": property_manager.company_name,
            },
            "auth_link": auth_link,
        }


def create_realtor(
    auth_user_id: str,
    name: str,
    email: str,
    contact: str,
    property_manager_id: int,
):
    """Create a new Realtor that must belong to a Property Manager."""
    with Session(engine) as session:
        # Check for duplicate realtor
        existing_realtor = session.exec(
            select(Realtor).where(
                (Realtor.email == email) | (Realtor.contact == contact)
            )
        ).first()

        if existing_realtor:
            raise HTTPException(
                status_code=400,
                detail="Realtor with this email or contact already exists",
            )

        if not property_manager_id:
            raise HTTPException(
                status_code=400,
                detail="property_manager_id is required when creating a realtor",
            )
        
        # Validate property manager
        property_manager = session.exec(
            select(PropertyManager).where(PropertyManager.property_manager_id == property_manager_id)
        ).first()
        if not property_manager:
            raise HTTPException(
                status_code=404,
                detail="Property Manager not found",
            )

        # Create new Realtor
        realtor = Realtor(
            auth_user_id=auth_user_id,
            name=name,
            email=email,
            contact=contact,
            twilio_contact="TBD",
            property_manager_id=property_manager_id,
        )
        session.add(realtor)
        session.commit()
        session.refresh(realtor)
        print("Realtor created")

        # Create Source for Realtor (scoped to their PM)
        source = create_source(
            property_manager_id=property_manager_id,
            realtor_id=realtor.realtor_id,
        )
        print("Source created for Realtor")

        auth_link = f"https://leasing-copilot-supabase.onrender.com/authorize?realtor_id={realtor.realtor_id}"

        return {
            "message": "Realtor created successfully",
            "realtor": {
                "id": realtor.realtor_id,
                "name": realtor.name,
                "email": realtor.email,
                "contact": realtor.contact,
                "property_manager_id": realtor.property_manager_id,
            },
            "auth_link": auth_link,
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
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to read/parse file {file.filename}: {str(e)}",
                )

            file_path = f"realtors/{realtor_id}/{file.filename}"
            # Upload to Supabase storage
            try:
                response = supabase.storage.from_(BUCKET_NAME).upload(
                    file_path,
                    content_bytes,
                    file_options={"content-type": file.content_type},
                )
                if isinstance(response, dict) and "error" in response:
                    raise Exception(response["error"]["message"])
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to upload {file.filename} to Supabase storage: {str(e)}",
                )
            file_url = (
                f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{file_path}"
            )
            uploaded_files.append(file_url)

            # Split into chunks
            try:
                document = Document(
                    page_content=file_content, metadata={"source": file.filename}
                )

                chunk_docs = splitter.split_documents([document])
                chunks = [doc.page_content for doc in chunk_docs]
                all_chunks.extend(chunks)
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to split {file.filename} into chunks: {str(e)}",
                )

        # Insert into DB
        try:
            insert_rule_chunks(source_id=source_id, chunks=all_chunks)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to insert rule chunks into DB: {str(e)}",
            )

        return uploaded_files

    except HTTPException:
        # re-raise explicit HTTP errors
        raise
    except Exception as e:
        # catch anything unexpected
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error in embed_and_store_rules: {str(e)}",
        )


def embed_and_store_listings(
    listing_file, listing_api_url: str = None, realtor_id: int = None
):
    """
    Upload and store listings using AI-powered parser.
    Supports JSON, CSV, and TXT files with intelligent data normalization.
    """
    from .listing_parser import parse_listing_file
    
    listings = []

    if listing_file:
        content = listing_file.file.read()
        print(f"Reading file: {listing_file.filename}")
        
        # Use AI-powered parser to handle various formats
        try:
            listings = parse_listing_file(content, listing_file.filename, use_ai=True)
            print(f"Parsed {len(listings)} listings from {listing_file.filename}")
        except Exception as e:
            print(f"Parser error: {e}")
            raise HTTPException(
                status_code=400, 
                detail=f"Failed to parse file {listing_file.filename}: {str(e)}"
            )

        # Upload listing file to Supabase storage
        listing_path = f"realtors/{realtor_id}/listings/{listing_file.filename}"
        try:
            response = supabase.storage.from_(BUCKET_NAME).upload(
                listing_path,
                content,
                file_options={"content-type": listing_file.content_type},
            )
            print("File uploaded to Supabase storage")
            if isinstance(response, dict) and "error" in response:
                print(f"Supabase upload warning: {response['error']}")
        except Exception as e:
            print(f"Warning: Could not upload to Supabase: {e}")

    elif listing_api_url:
        try:
            response = requests.get(listing_api_url, timeout=30)
            if response.status_code != 200:
                raise HTTPException(
                    status_code=400, detail="Failed to fetch data from API URL"
                )
            listing_data = response.json()
            
            # Parse API response using parser
            from .listing_parser import get_parser
            parser = get_parser(use_ai=True)
            if isinstance(listing_data, list):
                listings = [parser._normalize_listing(item) for item in listing_data]
            elif isinstance(listing_data, dict):
                listings = [parser._normalize_listing(listing_data)]
            else:
                raise ValueError("Invalid API response format")
        except Exception as e:
            raise HTTPException(
                status_code=400, 
                detail=f"Failed to parse API response: {str(e)}"
            )

    if not listings:
        raise HTTPException(
            status_code=400, 
            detail="No valid listings found in the provided data"
        )

    # Generate text representations and embeddings
    formatted_texts = [listing_to_text(l) for l in listings]
    embeddings = embed_documents(formatted_texts)
    print(f"Generated embeddings for {len(listings)} listings")

    listing_records = [
        {
            "text": formatted_texts[i],
            "metadata": listings[i],
            "embedding": embeddings[i],
        }
        for i in range(len(listings))
    ]
    
    print("Inserting listing records into database")
    insert_listing_records(realtor_id, listing_records)
    print(f"Successfully stored {len(listings)} listings")

    return True


def create_source(property_manager_id: int, realtor_id: Optional[int] = None) -> Source:
    """
    Create (or return existing) source rows.
    
    - If realtor_id is None, returns the Property Manager's main source
    - If realtor_id is provided, returns the realtor's dedicated source (and validates ownership)
    """
    with Session(engine) as session:
        property_manager = session.get(PropertyManager, property_manager_id)
        if not property_manager:
            raise HTTPException(status_code=404, detail="Property Manager not found")
        
        if realtor_id is not None:
            realtor = session.get(Realtor, realtor_id)
            if not realtor:
                raise HTTPException(status_code=404, detail="Realtor not found")
            if realtor.property_manager_id != property_manager_id:
                raise HTTPException(
                    status_code=403,
                    detail="Realtor does not belong to the specified Property Manager",
                )
            
            existing = session.exec(
                select(Source).where(
                    Source.property_manager_id == property_manager_id,
                    Source.realtor_id == realtor_id,
                )
            ).first()
        else:
            existing = session.exec(
                select(Source).where(
                    Source.property_manager_id == property_manager_id,
                    Source.realtor_id == None,  # noqa: E711
                )
            ).first()
        
        if existing:
            return existing
        
        source = Source(
            property_manager_id=property_manager_id,
            realtor_id=realtor_id,
        )
        session.add(source)
        session.commit()
        session.refresh(source)
        print("Created new Source.")
        return source


def enforce_realtor_hierarchy() -> None:
    """
    Ensure database rows follow the new hierarchy rules:
    - Every realtor must belong to a property manager
    - Every source linked to a realtor must also reference that property manager
    """
    if not engine:
        return
    
    with engine.begin() as connection:
        # Drop legacy constraint that prevented PM + realtor ownership
        connection.execute(
            text(
                """
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1
                        FROM pg_constraint
                        WHERE conname = 'check_source_owner'
                          AND conrelid = 'source'::regclass
                    ) THEN
                        ALTER TABLE source DROP CONSTRAINT check_source_owner;
                    END IF;
                END$$;
                """
            )
        )
        
        # Backfill property_manager_id on sources linked to realtors (if missing or mismatched)
        connection.execute(
            text(
                """
                UPDATE source AS s
                SET property_manager_id = r.property_manager_id
                FROM realtor AS r
                WHERE s.realtor_id = r.realtor_id
                  AND (s.property_manager_id IS DISTINCT FROM r.property_manager_id)
                """
            )
        )
        
        # Check for sources with NULL property_manager_id that can't be fixed
        problematic_sources = connection.execute(
            text(
                """
                SELECT source_id, realtor_id, property_manager_id
                FROM source
                WHERE property_manager_id IS NULL
                """
            )
        ).fetchall()
        
        if problematic_sources:
            source_ids = [row[0] for row in problematic_sources]
            raise RuntimeError(
                f"Found {len(problematic_sources)} source(s) with NULL property_manager_id. "
                f"These must be fixed before the backend can start. "
                f"Source IDs: {source_ids}. "
                f"Please update these sources in Supabase to assign them to a property manager."
            )
        
        # Ensure new constraint exists (property_manager_id always required)
        # Only add if all sources have property_manager_id (checked above)
        connection.execute(
            text(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_constraint
                        WHERE conname = 'check_source_requires_pm'
                          AND conrelid = 'source'::regclass
                    ) THEN
                        ALTER TABLE source
                        ADD CONSTRAINT check_source_requires_pm CHECK (property_manager_id IS NOT NULL);
                    END IF;
                END$$;
                """
            )
        )
    
    with engine.connect() as connection:
        orphan_rows = connection.execute(
            text(
                "SELECT realtor_id FROM realtor WHERE property_manager_id IS NULL"
            )
        ).fetchall()
    
    if orphan_rows:
        orphan_ids = [row[0] for row in orphan_rows]
        raise RuntimeError(
            "Standalone realtors detected. Every realtor must be assigned to a property "
            f"manager before the backend can start. Offending realtor_ids: {orphan_ids}"
        )


enforce_realtor_hierarchy()


# ---------------------------- Bounded Usage------------------------


def get_chat_session(user_number: str) -> str | None:
    with Session(engine) as session:
        customer = session.exec(
            select(Customer).where(Customer.contact == user_number)
        ).first()
        if not customer:
            return None

        chat_stmt = (
            select(ChatSession)
            .where(ChatSession.cust_id == customer.id, ChatSession.date == date.today())
            .order_by(ChatSession.date.desc())
        )

        chat_session = session.exec(chat_stmt).first()
        return chat_session.chat_id if chat_session else None


def save_chat_session(from_number: str, chat_id: str) -> None:
    with Session(engine) as session:
        # Get or create customer
        customer = session.exec(
            select(Customer).where(Customer.contact == from_number)
        ).first()
        if not customer:
            customer = Customer(
                name="Unknown",
                email="unknown@example.com",
                contact=from_number,
                if_tenant="Unknown",
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
            chat_id=chat_id, cust_id=customer.id, date=date.today(), count=1
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
                ChatSession.cust_id == customer.id, ChatSession.date == on_date
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
            RuleChunk(content=chunk, embedding=embedding, source_id=source_id)
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
            session.add(
                ApartmentListing(
                    source_id=source_id,
                    text=text,
                    listing_metadata=listing,
                    embedding=emb,
                )
            )
        session.commit()


def embed_and_store_listings_for_source(
    listing_file, listing_api_url: str = None, source_id: int = None
):
    """
    Upload listings directly to a Source (for Property Managers or direct assignment).
    Uses AI-powered parser to handle various file formats and data inconsistencies.
    """
    from .listing_parser import parse_listing_file, get_parser
    
    listings = []

    if listing_file:
        content = listing_file.file.read()
        print(f"Reading file: {listing_file.filename}")
        
        # Use AI-powered parser to handle various formats
        try:
            listings = parse_listing_file(content, listing_file.filename, use_ai=True)
            print(f"Parsed {len(listings)} listings from {listing_file.filename}")
        except Exception as e:
            print(f"Parser error: {e}")
            raise HTTPException(
                status_code=400, 
                detail=f"Failed to parse file {listing_file.filename}: {str(e)}"
            )

    elif listing_api_url:
        try:
            response = requests.get(listing_api_url, timeout=30)
            if response.status_code != 200:
                raise HTTPException(
                    status_code=400, detail="Failed to fetch data from API URL"
                )
            listing_data = response.json()
            
            # Parse API response using parser
            parser = get_parser(use_ai=True)
            if isinstance(listing_data, list):
                listings = [parser._normalize_listing(item) for item in listing_data]
            elif isinstance(listing_data, dict):
                listings = [parser._normalize_listing(listing_data)]
            else:
                raise ValueError("Invalid API response format")
            print(f"Parsed {len(listings)} listings from API")
        except Exception as e:
            raise HTTPException(
                status_code=400, 
                detail=f"Failed to parse API response: {str(e)}"
            )

    if not listings:
        raise HTTPException(
            status_code=400, 
            detail="No valid listings found in the provided data"
        )

    # Store listings in database
    insert_apartments(listings, listing_to_text, source_id)
    print(f"Successfully inserted {len(listings)} listings into source {source_id}")
    
    return {
        "message": f"Successfully inserted {len(listings)} listings", 
        "count": len(listings),
        "source_id": source_id
    }


# ---------------------- INGEST DATA ----------------------


def ingest_apartment_data(
    data: Union[str, List[Dict[str, Any]]], from_file: bool = False
):
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

    sql = text(
        f"""
        SELECT content 
        FROM rulechunk
        WHERE source_id = :source_id
        ORDER BY embedding <=> '{qvec_str}'::vector
        LIMIT :k
    """
    )
    with SessionLocal() as session:
        rows = session.execute(sql, {"source_id": source_id, "k": k}).all()
        return [r[0] for r in rows]


def search_apartments(query: str, source_ids: Optional[List[int]] = None, k: int = 5) -> List[Dict]:
    """
    Search apartments using vector similarity.
    
    Args:
        query: Search query text
        source_ids: Optional list of source_ids to filter by (for data isolation)
                   - If None: searches all listings (use with caution)
                   - If empty list []: returns empty (user has no data)
                   - If list with IDs: filters by those source_ids
        k: Number of results to return
    
    Returns:
        List of listing metadata dictionaries
    """
    # If source_ids is an empty list, user has no data - return empty results
    if source_ids is not None and len(source_ids) == 0:
        print("⚠️  User has no data (empty source_ids) - returning empty results")
        return []
    
    qvec = embed_text(query)
    qvec_str = "[" + ",".join(f"{x:.6f}" for x in qvec) + "]"
    
    # Build SQL with optional source_id filtering
    if source_ids and len(source_ids) > 0:
        sql = text(
            f"""
            SELECT listing_metadata FROM apartmentlisting
            WHERE source_id = ANY(:source_ids)
            ORDER BY embedding <=> '{qvec_str}'::vector
            LIMIT :k
        """
        )
        params = {"source_ids": source_ids, "k": k}
    else:
        # source_ids is None - user not identified, return empty (fail secure)
        print("⚠️  No source_ids provided - returning empty results for security")
        return []
    
    with SessionLocal() as session:
        rows = session.execute(sql, params).all()
        return [r[0] for r in rows]


# ---------------------- OPTIONAL: Fetch from URL ----------------------


# needed later
def fetch_apartments_from_url():
    response = requests.get("https://zillow.com/mls/listings")
    if response.ok:
        listings = response.json()
        ingest_apartment_data(listings, from_file=False)
    else:
        print("API call failed:", response.status_code)


def create_booking_entry(
    address: str, booking_date: date, booking_time: time, contact: str
) -> Booking:
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
            realtor_id=realtor.realtor_id,
        )

        session.add(new_booking)
        session.commit()
        session.refresh(new_booking)
        return new_booking


# ------------------ CRUD---------------------------


def create_tenant_entry(
    name: str,
    property_id: int,
    property_manager_id: int,
    phone_number: Optional[str] = None,
    email: Optional[str] = None,
    realtor_id: Optional[int] = None,
    unit_number: Optional[str] = None,
    lease_start_date: Optional[date] = None,
    lease_end_date: Optional[date] = None,
    notes: Optional[str] = None
) -> Tenant:
    """
    Create a new tenant entry and automatically mark the property as "Rented".
    
    Args:
        name: Tenant's full name
        property_id: ID of the property being rented
        property_manager_id: ID of the Property Manager
        phone_number: Tenant's phone number (E.164 format)
        email: Tenant's email address
        realtor_id: Optional ID of the realtor who helped rent the property
        unit_number: Unit/apartment number
        lease_start_date: When the lease started
        lease_end_date: When the lease ends
        notes: Additional notes
    
    Returns:
        Created Tenant object
    
    Raises:
        HTTPException: If property not found, PM not found, or property already rented
    """
    from sqlalchemy.orm.attributes import flag_modified
    
    with Session(engine) as session:
        # Verify property exists
        property_listing = session.get(ApartmentListing, property_id)
        if not property_listing:
            raise HTTPException(status_code=404, detail="Property not found")
        
        # Verify Property Manager exists
        pm = session.get(PropertyManager, property_manager_id)
        if not pm:
            raise HTTPException(status_code=404, detail="Property Manager not found")
        
        # Verify property belongs to this PM (via Source)
        source = session.get(Source, property_listing.source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Source not found for property")
        
        if source.property_manager_id != property_manager_id:
            # Check if it's assigned to a realtor under this PM
            if source.realtor_id:
                realtor = session.get(Realtor, source.realtor_id)
                if not realtor or realtor.property_manager_id != property_manager_id:
                    raise HTTPException(
                        status_code=403,
                        detail="Property does not belong to this Property Manager"
                    )
            else:
                raise HTTPException(
                    status_code=403,
                    detail="Property does not belong to this Property Manager"
                )
        
        # Verify realtor belongs to PM if provided
        if realtor_id:
            realtor = session.get(Realtor, realtor_id)
            if not realtor or realtor.property_manager_id != property_manager_id:
                raise HTTPException(
                    status_code=400,
                    detail="Realtor does not belong to this Property Manager"
                )
        
        # Check if property already has an active tenant
        existing_tenant = session.exec(
            select(Tenant).where(
                Tenant.property_id == property_id,
                Tenant.is_active == True
            )
        ).first()
        
        if existing_tenant:
            raise HTTPException(
                status_code=400,
                detail=f"Property already has an active tenant: {existing_tenant.name}"
            )
        
        # Normalize phone number if provided
        if phone_number:
            from .user_lookup import normalize_phone_number
            phone_number = normalize_phone_number(phone_number)
        
        # Create tenant
        tenant = Tenant(
            name=name,
            phone_number=phone_number,
            email=email,
            property_id=property_id,
            property_manager_id=property_manager_id,
            realtor_id=realtor_id,
            unit_number=unit_number,
            lease_start_date=lease_start_date,
            lease_end_date=lease_end_date,
            notes=notes,
            is_active=True
        )
        
        session.add(tenant)
        
        # Update property status to "Rented"
        meta = dict(property_listing.listing_metadata) if property_listing.listing_metadata else {}
        meta["listing_status"] = "Rented"
        property_listing.listing_metadata = meta
        flag_modified(property_listing, "listing_metadata")
        
        session.commit()
        session.refresh(tenant)
        
        print(f"✅ Created tenant {tenant.name} for property {property_id} and marked property as Rented")
        
        return tenant


def create_customer_entry(
    name: str, email: str, contact: str, if_tenant: Optional[str] = None
) -> Customer:
    with Session(engine) as session:
        print("contact Received:", contact)
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
                name=name, email=email, contact=contact, if_tenant=if_tenant
            )
            session.add(new_customer)
            session.commit()
            session.refresh(new_customer)
            return new_customer


# ---------------------- HIERARCHICAL AUTHENTICATION ----------------------

def authenticate_property_manager(email: str, password: str) -> Dict[str, Any]:
    """Authenticate a Property Manager and return their data."""
    try:
        # Authenticate with Supabase
        auth_result = supabase.auth.sign_in_with_password(
            {"email": email, "password": password}
        )

        if not auth_result.user:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        uid = auth_result.user.id
        refresh_token = auth_result.session.refresh_token

        # Get property manager from DB
        with Session(engine) as session:
            property_manager = session.exec(
                select(PropertyManager).where(PropertyManager.auth_user_id == uid)
            ).first()

            if not property_manager:
                raise HTTPException(status_code=404, detail="Property Manager not found")

            # Get managed realtors
            managed_realtors = session.exec(
                select(Realtor).where(Realtor.property_manager_id == property_manager.property_manager_id)
            ).all()

            auth_link = f"https://leasing-copilot-mvp.onrender.com/authorize?property_manager_id={property_manager.property_manager_id}"

            return {
                "message": "Property Manager login successful",
                "auth_link": auth_link,
                "access_token": auth_result.session.access_token,
                "refresh_token": refresh_token,
                "property_manager_id": property_manager.property_manager_id,
                "user_type": "property_manager",
                "user": {
                    "uid": uid,
                    "property_manager_id": property_manager.property_manager_id,
                    "name": property_manager.name,
                    "email": property_manager.email,
                    "company_name": property_manager.company_name,
                    "managed_realtors_count": len(managed_realtors),
                },
            }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Property Manager authentication error: {e}")
        raise HTTPException(status_code=400, detail=f"Authentication failed: {e}")


def authenticate_realtor(email: str, password: str) -> Dict[str, Any]:
    """Authenticate a Realtor and return their data."""
    try:
        # Authenticate with Supabase
        auth_result = supabase.auth.sign_in_with_password(
            {"email": email, "password": password}
        )

        if not auth_result.user:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        uid = auth_result.user.id
        refresh_token = auth_result.session.refresh_token

        # Get realtor from DB with error handling
        if not engine:
            raise HTTPException(status_code=500, detail="Database connection not available")
        
        try:
            with Session(engine) as session:
                realtor = session.exec(
                    select(Realtor).where(Realtor.auth_user_id == uid)
                ).first()

                if not realtor:
                    raise HTTPException(status_code=404, detail="Realtor not found")

                # Get property manager info if realtor is managed
                property_manager_info = None
                if realtor.property_manager_id:
                    property_manager = session.exec(
                        select(PropertyManager).where(PropertyManager.property_manager_id == realtor.property_manager_id)
                    ).first()
                    if property_manager:
                        property_manager_info = {
                            "id": property_manager.property_manager_id,
                            "name": property_manager.name,
                            "company_name": property_manager.company_name,
                        }

                auth_link = f"https://leasing-copilot-mvp.onrender.com/authorize?realtor_id={realtor.realtor_id}"

                return {
                    "message": "Realtor login successful",
                    "auth_link": auth_link,
                    "access_token": auth_result.session.access_token,
                    "refresh_token": refresh_token,
                    "realtor_id": realtor.realtor_id,
                    "user_type": "realtor",
                    "user": {
                        "uid": uid,
                        "realtor_id": realtor.realtor_id,
                        "name": realtor.name,
                        "email": realtor.email,
                        "property_manager": property_manager_info,
                    },
                }
        except HTTPException:
            raise  # Re-raise HTTP exceptions as-is
        except Exception as db_error:
            print(f"Database error during realtor lookup: {db_error}")
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=503, 
                detail=f"Database connection error. Please try again. Error: {str(db_error)}"
            )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Realtor authentication error: {e}")
        raise HTTPException(status_code=400, detail=f"Authentication failed: {e}")


def get_user_data_by_auth_id(auth_user_id: str) -> Dict[str, Any]:
    """Get user data by Supabase auth user ID (for middleware)."""
    with Session(engine) as session:
        # Try Property Manager first
        property_manager = session.exec(
            select(PropertyManager).where(PropertyManager.auth_user_id == auth_user_id)
        ).first()
        
        if property_manager:
            return {
                "user_type": "property_manager",
                "id": property_manager.property_manager_id,
                "name": property_manager.name,
                "email": property_manager.email,
                "company_name": property_manager.company_name,
            }
        
        # Try Realtor
        realtor = session.exec(
            select(Realtor).where(Realtor.auth_user_id == auth_user_id)
        ).first()
        
        if realtor:
            return {
                "user_type": "realtor",
                "id": realtor.realtor_id,
                "name": realtor.name,
                "email": realtor.email,
                "property_manager_id": realtor.property_manager_id,
            }
        
        raise HTTPException(status_code=404, detail="User not found")


def get_managed_realtors(property_manager_id: int) -> List[Dict[str, Any]]:
    """Get all realtors managed by a property manager."""
    with Session(engine) as session:
        realtors = session.exec(
            select(Realtor).where(Realtor.property_manager_id == property_manager_id)
        ).all()
        
        return [
            {
                "id": realtor.realtor_id,
                "name": realtor.name,
                "email": realtor.email,
                "contact": realtor.contact,
                "created_at": realtor.created_at,
            }
            for realtor in realtors
        ]


def get_data_access_scope(user_type: str, user_id: int) -> Dict[str, Any]:
    """Determine what data a user can access based on their role."""
    with Session(engine) as session:
        if user_type == "property_manager":
            source_ids = session.exec(
                select(Source.source_id).where(Source.property_manager_id == user_id)
            ).all()
            
            return {
                "user_type": "property_manager",
                "user_id": user_id,
                "source_ids": source_ids,
                "can_access_managed_realtors": True,
            }
        
        elif user_type == "realtor":
            # Realtors can only access their own data
            realtor = session.exec(
                select(Realtor).where(Realtor.realtor_id == user_id)
            ).first()
            
            if not realtor:
                raise HTTPException(status_code=404, detail="Realtor not found")
            
            source_ids = session.exec(
                select(Source.source_id).where(Source.realtor_id == user_id)
            ).all()
            
            return {
                "user_type": "realtor",
                "user_id": user_id,
                "source_ids": source_ids,
                "property_manager_id": realtor.property_manager_id,
                "can_access_managed_realtors": False,
            }
        
        else:
            raise HTTPException(status_code=400, detail="Invalid user type")
