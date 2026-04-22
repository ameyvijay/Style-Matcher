"""
Antigravity Engine v2.1 — Janitor Service
Periodically purges stale Firestore documents to stay within
the free tier quota limits.

Key Design:
- Runs once on engine boot via the FastAPI lifespan handler
- Deletes 'photos' and 'batches' docs older than max_age_days
- Safety: NEVER deletes documents where status == 'pending_render'
- Gemini Extension Refinement #2: Chunked deletions (max 500 per batch)
  to respect Firestore WriteBatch API limits

Usage:
    from services.janitor import JanitorService
    janitor = JanitorService(max_age_days=10)
    await janitor.run_cleanup()
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

# ─── Constants ───────────────────────────────────────────────────────
_FIRESTORE_BATCH_LIMIT = 500  # Firestore max operations per WriteBatch
_PROTECTED_STATUSES = frozenset({"pending_render"})


class JanitorService:
    """
    Free-tier Firestore document janitor.

    Scans 'photos' and 'batches' collections for documents older than
    max_age_days and deletes them in safe, chunked batches.
    """

    def __init__(self, max_age_days: int = 10):
        self.max_age_days = max_age_days

    async def run_cleanup(self) -> dict:
        """
        Delete stale Firestore documents.

        Returns:
            Summary dict: { "photos_deleted": int, "batches_deleted": int, "skipped_protected": int }
        """
        from firebase_admin import firestore

        db = firestore.client()
        cutoff = time.time() - (self.max_age_days * 86400)
        cutoff_dt = datetime.now(timezone.utc) - timedelta(days=self.max_age_days)

        summary = {
            "photos_deleted": 0,
            "batches_deleted": 0,
            "skipped_protected": 0,
        }

        # ── Clean 'photos' collection ────────────────────────────────
        print(f"🧹 [Janitor] Scanning 'photos' for documents older than {self.max_age_days} days...")
        photos_ref = db.collection("photos")
        photos_deleted, skipped = await self._purge_collection(
            db, photos_ref, cutoff, cutoff_dt, protect_statuses=True
        )
        summary["photos_deleted"] = photos_deleted
        summary["skipped_protected"] = skipped

        # ── Clean 'batches' collection ───────────────────────────────
        print(f"🧹 [Janitor] Scanning 'batches' for documents older than {self.max_age_days} days...")
        batches_ref = db.collection("batches")
        batches_deleted, _ = await self._purge_collection(
            db, batches_ref, cutoff, cutoff_dt, protect_statuses=False
        )
        summary["batches_deleted"] = batches_deleted

        total = summary["photos_deleted"] + summary["batches_deleted"]
        if total > 0:
            print(
                f"🧹 [Janitor] Purged {total} stale documents "
                f"(photos: {summary['photos_deleted']}, batches: {summary['batches_deleted']}). "
                f"Protected (pending_render): {summary['skipped_protected']}."
            )
        else:
            print("🧹 [Janitor] No stale documents found. Firestore is clean.")

        return summary

    async def _purge_collection(
        self,
        db,
        collection_ref,
        cutoff_epoch: float,
        cutoff_dt: datetime,
        protect_statuses: bool,
    ) -> tuple[int, int]:
        """
        Scan and delete stale documents from a single collection.

        Uses chunked WriteBatch API to respect the 500-operation limit
        (Gemini Extension Refinement #2).

        Returns:
            (deleted_count, skipped_protected_count)
        """
        deleted = 0
        skipped = 0

        try:
            # Fetch all docs — we'll filter in-memory since the timestamp
            # field can be either epoch float or Firestore Timestamp
            all_docs = collection_ref.get()

            # Collect refs eligible for deletion
            to_delete = []
            for doc in all_docs:
                doc_data = doc.to_dict()
                if not self._should_purge(doc_data, cutoff_epoch, cutoff_dt):
                    continue

                # Safety: never delete pending_render
                if protect_statuses and doc_data.get("status") in _PROTECTED_STATUSES:
                    skipped += 1
                    continue

                to_delete.append(doc.reference)

            # ── Chunked deletion (Gemini Refinement #2) ──────────────
            for i in range(0, len(to_delete), _FIRESTORE_BATCH_LIMIT):
                chunk = to_delete[i : i + _FIRESTORE_BATCH_LIMIT]
                batch = db.batch()
                for ref in chunk:
                    batch.delete(ref)
                batch.commit()
                deleted += len(chunk)
                print(f"🧹 [Janitor] Deleted chunk of {len(chunk)} documents.")

        except Exception as e:
            print(f"⚠️ [Janitor] Collection purge error: {e}")

        return deleted, skipped

    def _should_purge(
        self,
        doc_data: dict,
        cutoff_epoch: float,
        cutoff_dt: datetime,
    ) -> bool:
        """
        Check if a document is eligible for deletion based on its timestamp.
        Handles both epoch floats and Firestore Timestamp objects.
        """
        ts = doc_data.get("timestamp") or doc_data.get("generated_at")
        if ts is None:
            return False  # No timestamp — can't determine age, skip

        # Firestore Timestamp object
        if hasattr(ts, "seconds"):
            return ts.seconds < cutoff_epoch

        # Python datetime
        if isinstance(ts, datetime):
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            return ts < cutoff_dt

        # Epoch float/int
        if isinstance(ts, (int, float)):
            return ts < cutoff_epoch

        return False  # Unknown format — don't delete

    def purge_local_annotations(self, db_session) -> int:
        """
        Feature 7/8: Purge local database annotations older than TTL.
        """
        from database import Annotation
        from sqlalchemy import delete
        
        cutoff_dt = datetime.now() - timedelta(days=self.max_age_days)
        print(f"🧹 [Janitor] Purging local annotations older than {cutoff_dt}")
        
        stmt = delete(Annotation).where(Annotation.timestamp < cutoff_dt)
        result = db_session.execute(stmt)
        db_session.commit()
        
        return result.rowcount

    def flush_test_data(self, db_session, session_id: str = None) -> dict:
        """
        Surgically delete test inferences and annotations.
        If session_id is provided, only flushes that session.
        """
        from database import Inference, Annotation
        import json
        from sqlalchemy import delete

        # 1. Delete Inferences marked as test
        # Note: We filter by parsing the JSON in SQLite
        inferences = db_session.query(Inference).all()
        inf_deleted = 0
        for inf in inferences:
            try:
                val = json.loads(inf.inference_value)
                if val.get("is_test") is True:
                    if session_id and val.get("eval_session") != session_id:
                        continue
                    db_session.delete(inf)
                    inf_deleted += 1
            except:
                continue
        
        # 2. Delete annotations marked as 'skipped' or from test sessions
        # (Annotations don't have is_test yet, we usually trigger them manually)
        ann_stmt = delete(Annotation).where(Annotation.action == 'skipped')
        ann_res = db_session.execute(ann_stmt)
        
        db_session.commit()
        return {
            "inferences_flushed": inf_deleted,
            "skips_cleared": ann_res.rowcount
        }
