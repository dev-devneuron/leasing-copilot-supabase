# import os
# from typing import List, Dict, Any
# from sqlmodel import SQLModel, Field, Session, create_engine
# from sqlalchemy import Column, String, JSON, text, inspect
# from pgvector.sqlalchemy import Vector
# from dotenv import load_dotenv
# from config import EMBED_DIM
# from sqlalchemy.orm import declarative_base


# load_dotenv()

# # Config for engine1 (test DB)
# DATABASE_URL = os.getenv("DATABASE_2_URL")
# engine1 = create_engine(DATABASE_URL, pool_pre_ping=True)

# # Base metadata registry
# DynamicBase = declarative_base()


# def insert_listing_records(realtor_id: int, listings: List[Dict[str, Any]]):
#     table_name = f"realtor_{realtor_id}_listings"
#     print(f"[INFO] Target table: {table_name}")

#     inspector = inspect(engine1)

#     # Define dynamic table class only if not exists
#     if table_name not in DynamicBase.metadata.tables:
#         class DynamicListing(SQLModel, table=True):
#             __tablename__ = table_name
#             __table_args__ = {"extend_existing": True}

#             id: int = Field(default=None, primary_key=True)
#             text: str = Field(sa_column=Column(String))
#             listing_metadata: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))
#             embedding: List[float] = Field(sa_column=Column(Vector(EMBED_DIM)))

#     # Ensure pgvector extension exists
#     with engine1.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
#         conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

#     # Check if table already exists in DB
#     if not inspector.has_table(table_name):
#         print(f"[INFO] Creating table {table_name}")
#         SQLModel.metadata.create_all(engine1, tables=[DynamicBase.metadata.tables[table_name]])
#     else:
#         print(f"[INFO] Table {table_name} already exists, skipping creation.")
#     from sync import sync_apartment_listings
#     # Insert listings
#     with Session(engine1) as session:
#         for listing in listings:
#             try:
#                 record = DynamicBase.metadata.tables[table_name].insert().values(
#                     text=listing["text"],
#                     listing_metadata=listing["metadata"],
#                     embedding=listing["embedding"],
#                 )
#                 session.exec(record)
#             except Exception as e:
#                 print(f"[Insert Error] Failed to add listing: {e}")
#         session.commit()
#         sync_apartment_listings()
#         print(f"[SUCCESS] Listings inserted into {table_name}")
import os
from typing import List, Dict, Any
from sqlmodel import SQLModel, Field, Session, create_engine
from sqlalchemy import Column, String, JSON, text, inspect
from pgvector.sqlalchemy import Vector
from dotenv import load_dotenv
from config import EMBED_DIM

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_2_URL")
engine1 = create_engine(DATABASE_URL, pool_pre_ping=True)


def insert_listing_records(realtor_id: int, listings: List[Dict[str, Any]]):
    table_name = f"realtor_{realtor_id}_listings"
    print(f"[INFO] Target table: {table_name}")

    inspector = inspect(engine1)

    # Define dynamic model class dynamically
    if table_name not in SQLModel.metadata.tables:

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

    # Create table if it doesn’t exist
    if not inspector.has_table(table_name):
        print(f"[INFO] Creating table {table_name}")
        SQLModel.metadata.create_all(
            engine1, tables=[SQLModel.metadata.tables[table_name]]
        )
    else:
        print(f"[INFO] Table {table_name} already exists, skipping creation.")

    from sync import sync_apartment_listings

    # Insert rows
    with Session(engine1) as session:
        for listing in listings:
            try:
                record = (
                    SQLModel.metadata.tables[table_name]
                    .insert()
                    .values(
                        text=listing["text"],
                        listing_metadata=listing["metadata"],
                        embedding=listing["embedding"],
                    )
                )
                session.exec(record)
            except Exception as e:
                print(f"[Insert Error] Failed to add listing: {e}")
        session.commit()

        sync_apartment_listings()

        print(f"[SUCCESS] Listings inserted into {table_name}")
