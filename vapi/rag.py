"""
RAG (Retrieval Augmented Generation) Engine

This module provides the RAG engine for semantic search over:
- Property listing data (apartments)
- Rules and policy documents

Uses vector embeddings and pgvector for efficient similarity search.
"""

import json
from typing import Optional, List
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import CharacterTextSplitter

from DB.db import (
    search_rules,
    search_apartments,
)


class RAGEngine:
    """
    RAG Engine for semantic search over property listings and rules.
    
    Provides methods to query relevant listings and rule chunks based on
    natural language questions using vector similarity search.
    """
    def __init__(self):
        pass

    # --------- INDEXING ---------
    # def build_rules_index(self):
    #     """Reads Rules.txt, splits into chunks, and stores them in pgvector DB."""
    #     loader = TextLoader(self.rules_path)
    #     documents = loader.load()

    #     splitter = CharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    #     chunks = [doc.page_content for doc in splitter.split_documents(documents)]

    #     insert_rule_chunks(chunks)
    #     print(f"Inserted {len(chunks)} rule chunks into pgvector.")

    # def build_apartment_index(self):
    #     """Reads data.json and stores apartment embeddings in pgvector DB."""
    #     with open(self.apartments_json, "r", encoding="utf-8") as f:
    #         listings = json.load(f)

    #     insert_apartments(listings, self.listing_to_text)
    #     print(f"Inserted {len(listings)} apartment listings into pgvector.")

    def query(self, question: str, source_id: int, k: int = 3) -> str:
        """Finds top-k relevant rule chunks for a question, filtered by source_id."""
        results = search_rules(question, source_id=source_id, k=k)
        return "Here are the most relevant parts:\n\n" + "\n".join(results)

    def search_apartments(self, query: str, source_ids: Optional[List[int]] = None, k: int = 5):
        """Finds top-k apartment listings matching the query, optionally filtered by source_ids."""
        return search_apartments(query, source_ids=source_ids, k=k)

    # --------- HELPERS ---------
    @staticmethod
    def listing_to_text(listing: dict) -> str:
        """Converts apartment listing JSON into text for embeddings."""
        return (
            f"{listing['bedrooms']} bed, {listing['bathrooms']} bath "
            f"{listing['property_type']} in {listing['address']}, "
            f"listed at ${listing['price']} with {listing['square_feet']} sqft. "
            f"Features include: {', '.join(listing.get('features', []))}."
        )
