"""
Antigravity Engine v2.1 — Module C.2: Vector Store (ChromaDB)
Local persistent vector database for Visual RAG preference retrieval.

Key Design:
- PersistentClient backed by SQLite at ./vector_store/chroma.sqlite3
- Two collections: accepted_preferences / rejected_preferences
- Cosine-similarity queries for RLHF-driven prompt optimisation
"""
from __future__ import annotations

import os
import chromadb


# Resolve storage path relative to this file so it works regardless of CWD
_CHROMA_DIR = os.path.join(os.path.dirname(__file__), "vector_store")


class ChromaManager:
    """
    Manages two ChromaDB collections for accepted and rejected preference
    embeddings, enabling cosine-similarity retrieval for the Visual RAG loop.
    """

    COLLECTION_NAMES = ("accepted_preferences", "rejected_preferences", "golden_exemplars")

    def __init__(self, persist_dir: str = _CHROMA_DIR):
        os.makedirs(persist_dir, exist_ok=True)
        self.client = chromadb.PersistentClient(path=persist_dir)

        # Pre-create all collections (get_or_create is idempotent)
        self.collections = {}
        for name in self.COLLECTION_NAMES:
            self.collections[name] = self.client.get_or_create_collection(
                name=name,
                metadata={
                    "hnsw:space": "cosine",
                    "hnsw:construction_ef": 200,
                    "hnsw:search_ef": 50,
                    "hnsw:M": 16
                },
            )
        print(f"✅ ChromaManager: Persistent store ready at {persist_dir}")

    def add_embedding(
        self,
        collection_name: str,
        doc_id: str,
        embedding: list[float],
        metadata: dict,
    ) -> None:
        """
        Upsert a single embedding into the specified collection.
        Using version-scoped composite IDs: {photo_hash}__{prompt_version}
        """
        collection = self.collections[collection_name]
        collection.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            metadatas=[metadata],
        )

    def get_embedding(self, collection_name: str, doc_id: str) -> dict | None:
        """Retrieve a specific embedding by ID."""
        collection = self.collections[collection_name]
        res = collection.get(ids=[doc_id], include=["embeddings", "metadatas"])
        if res and res["ids"]:
            return {
                "id": res["ids"][0],
                "embedding": res["embeddings"][0],
                "metadata": res["metadatas"][0]
            }
        return None

    def delete_embedding(self, collection_name: str, doc_id: str) -> None:
        """Delete a specific embedding by ID."""
        collection = self.collections[collection_name]
        collection.delete(ids=[doc_id])

    def query_similar(
        self,
        collection_name: str,
        embedding: list[float],
        n_results: int = 5,
    ) -> dict:
        """
        Retrieve the ``n_results`` nearest neighbours from the specified
        collection using cosine similarity.

        Args:
            collection_name: One of ``COLLECTION_NAMES``.
            embedding:       Query vector (512-dim float list).
            n_results:       Number of neighbours to return.

        Returns:
            ChromaDB query result dict with keys ``ids``, ``distances``,
            ``metadatas``, etc.
        """
        collection = self.collections[collection_name]
        return collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
        )
