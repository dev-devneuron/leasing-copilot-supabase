# sync.py
import json
import hashlib
from typing import Dict, Any, List
from sqlmodel import Session, SQLModel, Field, select
from sqlalchemy import Column, String, JSON
from pgvector.sqlalchemy import Vector

from db import engine, ApartmentListing, Source
from secondary_db import engine1

EMBED_DIM = 768


def listing_hash(text: str, metadata: dict) -> str:
    serialized = text + json.dumps(metadata, sort_keys=True)
    return hashlib.md5(serialized.encode('utf-8')).hexdigest()


def create_dynamic_listing_class(table_name: str):
    class DynamicListing(SQLModel, table=True):
        __tablename__ = table_name
        __table_args__ = {"extend_existing": True}

        id: int = Field(default=None, primary_key=True)
        text: str = Field(sa_column=Column(String))
        listing_metadata: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))
        embedding: List[float] = Field(sa_column=Column(Vector(EMBED_DIM)))

    return DynamicListing


def sync_apartment_listings() -> Dict[str, Any]:
    summary = []

    with Session(engine) as main_session:
        sources = main_session.exec(select(Source)).all()

    print(f"Starting sync for {len(sources)} realtor(s)...")

    for source in sources:
        realtor_id = source.realtor_id
        source_id = source.id
        table_name = f"realtor_{realtor_id}_listings"
        DynamicListing = create_dynamic_listing_class(table_name)

        print(f"\nSyncing Realtor {realtor_id} from table: {table_name}")

        try:
            with Session(engine1) as sec_session:
                secondary_listings = sec_session.exec(select(DynamicListing)).all()
        except Exception as e:
            msg = f"Error reading secondary DB table {table_name}: {str(e)}"
            print(msg)
            summary.append({"realtor_id": realtor_id, "status": "error", "error": msg})
            continue

        with Session(engine) as main_session:
            main_listings = main_session.exec(
                select(ApartmentListing).where(ApartmentListing.source_id == source_id)
            ).all()

        sec_map = {
            listing_hash(l.text, l.listing_metadata): l for l in secondary_listings
        }
        main_map = {
            listing_hash(l.text, l.listing_metadata): l for l in main_listings
        }

        new_hashes = set(sec_map) - set(main_map)
        removed_hashes = set(main_map) - set(sec_map)

        # Log sync actions
        if new_hashes or removed_hashes:
            print(f"Changes detected for Realtor {realtor_id}:")
            print(f"   + {len(new_hashes)} new listing(s)")
            print(f"   - {len(removed_hashes)} removed listing(s)")
        else:
            print(f"No changes for Realtor {realtor_id}")

        # Insert and Delete listings
        with Session(engine) as main_session:
            for h in new_hashes:
                l = sec_map[h]
                main_session.add(ApartmentListing(
                    source_id=source_id,
                    text=l.text,
                    listing_metadata=l.listing_metadata,
                    embedding=l.embedding
                ))

            for h in removed_hashes:
                main_session.delete(main_map[h])

            main_session.commit()

        summary.append({
            "realtor_id": realtor_id,
            "status": "success",
            "added": len(new_hashes),
            "removed": len(removed_hashes)
        })

    print("\nSync finished for all sources.")
    return {"sync_summary": summary}
