import os
from typing import List, Dict, Any
from sqlmodel import SQLModel, Field, Session, create_engine
from sqlalchemy import Column, String, JSON, text
from pgvector.sqlalchemy import Vector

# Config for engine1 (test DB)
DATABASE_URL = (
    "postgresql+psycopg2://postgres.cadkbesvlgkpwyjccobk:Superman%40_%2511223344"
    "@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres"
)
engine1 = create_engine(DATABASE_URL, pool_pre_ping=True)

EMBED_DIM = 768

def insert_listing_records(realtor_id: int, listings: List[Dict[str, Any]]):
    """
    Inserts a list of listings into a dynamically created table named realtor_{realtor_id}_listings.
    Each listing should contain keys: 'text', 'metadata', 'embedding'.
    """
    table_name = f"realtor_{realtor_id}_listings"

    class DynamicListing(SQLModel, table=True):
        __tablename__ = table_name
        __table_args__ = {"extend_existing": True}

        id: int = Field(default=None, primary_key=True)
        text: str = Field(sa_column=Column(String))
        listing_metadata: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))
        embedding: List[float] = Field(sa_column=Column(Vector(EMBED_DIM)))

    # Ensure pgvector extension exists
    with engine1.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    # Create the dynamic table
    SQLModel.metadata.create_all(engine1, tables=[DynamicListing.__table__])

    with Session(engine1) as session:
        for listing in listings:
            try:
                record = DynamicListing(
                    text=listing["text"],
                    listing_metadata=listing["metadata"],
                    embedding=listing["embedding"]
                )
                session.add(record)
            except Exception as e:
                print(f"[Insert Error] Failed to add listing: {e}")
        session.commit()
        print("✅ Listing records inserted successfully.")
