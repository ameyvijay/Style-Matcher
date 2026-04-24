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

    async def run_cleanup(self, db_session=None) -> dict:
        """
        Delete stale Firestore documents and sync local database.
        """
        from firebase_admin import firestore
        from database import Media, Annotation
        from sqlalchemy import not_, delete

        db = firestore.client()
        cutoff = time.time() - (self.max_age_days * 86400)
        cutoff_dt = datetime.now(timezone.utc) - timedelta(days=self.max_age_days)

        summary = {
            "photos_deleted": 0,
            "batches_deleted": 0,
            "skipped_protected": 0,
            "local_media_cleaned": 0
        }

        # ── 1. Clean 'photos' collection ─────────────────────────────
        print(f"🧹 [Janitor] Scanning 'photos' for documents older than {self.max_age_days} days...")
        photos_ref = db.collection("photos")
        photos_deleted, skipped = await self._purge_collection(
            db, photos_ref, cutoff, cutoff_dt, protect_statuses=True
        )
        summary["photos_deleted"] = photos_deleted
        summary["skipped_protected"] = skipped

        # ── 2. Clean 'batches' collection ────────────────────────────
        print(f"🧹 [Janitor] Scanning 'batches' for documents older than {self.max_age_days} days...")
        batches_ref = db.collection("batches")
        batches_deleted, _ = await self._purge_collection(
            db, batches_ref, cutoff, cutoff_dt, protect_statuses=False
        )
        summary["batches_deleted"] = batches_deleted

        # ── 3. Sync Local Database ───────────────────────────────────
        # If Firestore docs are gone, unreviewed local media should be too.
        if db_session:
            print(f"🧹 [Janitor] Syncing local DB: Removing unreviewed media older than {self.max_age_days} days...")
            # We use added_at for the cutoff check
            local_cutoff = datetime.now() - timedelta(days=self.max_age_days)
            media_stmt = delete(Media).where(
                not_(Media.annotations.any()),
                Media.added_at < local_cutoff
            )
            res = db_session.execute(media_stmt)
            summary["local_media_cleaned"] = res.rowcount
            db_session.commit()

        total = summary["photos_deleted"] + summary["batches_deleted"] + summary["local_media_cleaned"]
        if total > 0:
            print(
                f"🧹 [Janitor] Purged {total} stale items "
                f"(cloud: {summary['photos_deleted'] + summary['batches_deleted']}, "
                f"local: {summary['local_media_cleaned']})."
            )
        else:
            print("🧹 [Janitor] No stale items found. System is clean.")

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
            # Use server-side filtering instead of fetching all docs into memory
            docs = []
            try:
                docs.extend(collection_ref.where("timestamp", "<", cutoff_dt).get())
            except Exception: pass
            try:
                docs.extend(collection_ref.where("timestamp", "<", cutoff_epoch).get())
            except Exception: pass
            try:
                docs.extend(collection_ref.where("generated_at", "<", cutoff_dt).get())
            except Exception: pass
            try:
                docs.extend(collection_ref.where("generated_at", "<", cutoff_epoch).get())
            except Exception: pass
            
            to_delete = []
            seen = set()
            for doc in docs:
                if doc.id in seen:
                    continue
                seen.add(doc.id)
                doc_data = doc.to_dict()

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

    async def flush_test_data(self, db_session, session_id: str = None) -> dict:
        """
        Surgically delete test data to reset the engine state.
        Now includes unannotated media to fix dashboard discrepancies.
        """
        from database import Inference, Annotation, Media
        import json
        from sqlalchemy import delete

        # 1. Delete Inferences
        inf_deleted = 0
        if not session_id:
            # Delete ALL inferences to completely reset
            res = db_session.query(Inference).delete()
            inf_deleted = res
        else:
            inferences = db_session.query(Inference).all()
            for inf in inferences:
                try:
                    # inferences might be JSON or plain string
                    val = json.loads(inf.inference_value) if (inf.inference_value and inf.inference_value.startswith('{')) else {}
                    if val.get("is_test") is True or val.get("eval_session") == session_id:
                        db_session.delete(inf)
                        inf_deleted += 1
                except:
                    continue
        
        # 2. Delete ALL annotations (reset swipes)
        ann_stmt = delete(Annotation)
        ann_res = db_session.execute(ann_stmt)
        
        # 3. Delete ALL Media records (complete purge)
        media_stmt = delete(Media)
        media_res = db_session.execute(media_stmt)

        # 4. Clear Firestore (Best effort)
        firestore_deleted = 0
        try:
            from firebase_admin import firestore as fs_admin
            fs_db = fs_admin.client()
            
            # Delete all docs in 'photos' and 'batches'
            for coll_name in ["photos", "batches"]:
                docs = fs_db.collection(coll_name).list_documents()
                for doc in docs:
                    doc.delete()
                    firestore_deleted += 1
            print(f"🔥 [Janitor] Firestore collections purged: {firestore_deleted} docs.")
        except Exception as e:
            print(f"⚠️ [Janitor] Firestore purge skipped: {e}")

        db_session.commit()
        return {
            "inferences_flushed": inf_deleted,
            "skips_cleared": ann_res.rowcount,
            "unreviewed_media_cleared": media_res.rowcount,
            "firestore_docs_purged": firestore_deleted
        }
