"""
Antigravity Engine v2.1 — Module E.1: Preference Engine (Few-Shot RAG)
Retrieval-Augmented Generation using the ChromaDB accepted_preferences vector store.

Key Design:
- Cosine similarity query against accepted_preferences collection
- Returns exemplar shots + aggregate similarity score for the 70/30 composite
- KL Divergence guard: flags style-collapse when similarity is suspiciously high
"""
from __future__ import annotations

from vector_store import ChromaManager


# Cosine distance in ChromaDB's "cosine" space is (1 - cosine_similarity).
# We invert and scale so the returned score mirrors the 0-100 quality range.
_COSINE_DIST_TO_SIM = lambda d: max(0.0, 1.0 - d)  # noqa: E731

# Style-collapse threshold (cosine similarity): embeddings this close suggest
# the model has collapsed to a single mode — flag divergence warning.
_KL_DIVERGENCE_THRESHOLD = 0.95


class SemanticRAG:
    """
    Few-Shot RAG engine that retrieves visually similar accepted preferences
    from ChromaDB and converts them into a similarity score for the scoring
    pipeline's 70/30 composite formula.
    """

    def __init__(self, chroma_mgr: ChromaManager):
        """
        Args:
            chroma_mgr: An initialised ChromaManager instance.  The engine
                        reads *only* from accepted_preferences; it never writes.
        """
        self._chroma = chroma_mgr

    def get_few_shot_context(
        self,
        current_embedding: list[float],
        n_exemplars: int = 3,
    ) -> dict:
        """
        Query the accepted_preferences collection for the top-n visually
        similar embeddings and synthesise a semantic context payload.

        Args:
            current_embedding: 512-dim CLIP embedding of the photo being scored.
            n_exemplars:       Number of nearest neighbours to retrieve.

        Returns:
            A dict with the following keys:
                "exemplars"          – list[dict] each containing:
                                           "exif_snapshot" (str | None)
                                           "photo_hash"    (str)
                "similarity_score"   – float, 0.0-100.0 (average cosine similarity,
                                       scaled to match the quality_classifier range)
                "divergence_warning" – bool, True when similarity is suspiciously
                                       high (potential KL Divergence / style collapse)
        """
        # Defensive: if the collection is empty, Chroma raises.  Return neutral
        # context so the pipeline degrades gracefully without crashing.
        try:
            results = self._chroma.query_similar(
                collection_name="accepted_preferences",
                embedding=current_embedding,
                n_results=n_exemplars,
            )
        except Exception as exc:
            print(f"[preference_engine] RAG query failed (empty collection?): {exc}")
            return {
                "exemplars": [],
                "similarity_score": 50.0,   # Neutral — no prior preferences yet
                "divergence_warning": False,
            }

        # Unpack ChromaDB result structure
        ids_list      = results.get("ids",       [[]])[0]
        distances     = results.get("distances", [[]])[0]
        metadatas     = results.get("metadatas", [[]])[0]

        if not ids_list:
            return {
                "exemplars": [],
                "similarity_score": 50.0,
                "divergence_warning": False,
            }

        # Build exemplar list
        exemplars: list[dict] = []
        cosine_similarities: list[float] = []

        for photo_hash, distance, meta in zip(ids_list, distances, metadatas):
            cos_sim = _COSINE_DIST_TO_SIM(distance)
            cosine_similarities.append(cos_sim)
            exemplars.append({
                "photo_hash":    photo_hash,
                "exif_snapshot": meta.get("exif_snapshot") if meta else None,
            })

        # Average cosine similarity (0.0–1.0), then scale to 0-100 for parity
        # with the other quality signals (sharpness, aesthetic, exposure).
        avg_cos_sim = sum(cosine_similarities) / len(cosine_similarities)
        similarity_score = round(avg_cos_sim * 100.0, 2)

        # KL Divergence guard: a perfect match cluster signals style collapse —
        # the user may have accepted a near-duplicate burst.  Warn the caller.
        divergence_warning = avg_cos_sim > _KL_DIVERGENCE_THRESHOLD

        if divergence_warning:
            print(
                f"[preference_engine] ⚠️  Divergence Warning: avg cosine similarity "
                f"{avg_cos_sim:.4f} exceeds threshold {_KL_DIVERGENCE_THRESHOLD}. "
                "Possible style collapse — consider diversifying accepted samples."
            )

        return {
            "exemplars":          exemplars,
            "similarity_score":   similarity_score,
            "divergence_warning": divergence_warning,
        }
