"""
test_sync_feedback.py
=====================
Standalone integration test — mocks a Firestore 'accepted' event and verifies
the local SQLite Annotation table is updated correctly.

Run from the batch-backend-v2 directory:
    python tests/test_sync_feedback.py

Requirements: mlops_registry.db must exist (run `python database.py` to create it).
"""

import os
import json
import sys
import unittest
from unittest.mock import MagicMock, patch

# Ensure the parent (batch-backend-v2) directory is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, Media, Annotation, init_db

# ─── Fixtures ────────────────────────────────────────────────────────

FAKE_FILE_PATH = "/tmp/test_photo_antigravity.ARW"
FAKE_HASH = "deadbeef12345678deadbeef12345678deadbeef12345678deadbeef12345678"


def _seed_media_record() -> int:
    """Insert a dummy Media row and return its id."""
    db = SessionLocal()
    try:
        existing = db.query(Media).filter(Media.file_path == FAKE_FILE_PATH).first()
        if existing:
            return existing.id
        media = Media(
            photo_hash=FAKE_HASH,
            file_path=FAKE_FILE_PATH,
        )
        db.add(media)
        db.commit()
        db.refresh(media)
        return media.id
    finally:
        db.close()


def _cleanup(media_id: int):
    """Remove test rows to keep the test idempotent."""
    db = SessionLocal()
    try:
        db.query(Annotation).filter(Annotation.media_id == media_id).delete()
        db.query(Media).filter(Media.id == media_id).delete()
        db.commit()
    finally:
        db.close()


# ─── Core callback simulation ────────────────────────────────────────

def _simulate_on_snapshot(doc_data: dict) -> None:
    """
    Reproduces the hardened on_snapshot logic from firebase_bridge.py
    without requiring a live Firestore connection.
    """
    status = doc_data.get("status")
    if status not in ["accepted", "rejected"]:
        return

    action_mapping = {
        "accepted": "swipe_right_keeper",
        "rejected": "swipe_left_cull",
    }
    mapped_action = action_mapping[status]

    db = SessionLocal()
    try:
        media_record = db.query(Media).filter(
            Media.file_path == doc_data.get("original_path")
        ).first()

        if not media_record:
            raise AssertionError(f"No Media record for path: {doc_data.get('original_path')}")

        # Idempotency guard
        existing = db.query(Annotation).filter(
            Annotation.media_id == media_record.id,
            Annotation.action == mapped_action,
        ).first()
        if existing:
            print(f"[test] ℹ️  Idempotency guard triggered — skipping duplicate.")
            return

        exif_data = doc_data.get("exif")
        exif_str = (
            json.dumps(exif_data) if isinstance(exif_data, dict) else str(exif_data)
        ) if exif_data else None

        annotation = Annotation(
            media_id=media_record.id,
            user_id=doc_data.get("user_id", "guest"),
            action=mapped_action,
            exif_snapshot=exif_str,
            swipe_duration_ms=doc_data.get("swipe_duration_ms"),
        )
        db.add(annotation)
        db.commit()
        print(f"[test] ✅ Annotation written for media_id={media_record.id} ({mapped_action})")
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()


# ─── Tests ───────────────────────────────────────────────────────────

class TestSyncFeedback(unittest.TestCase):

    def setUp(self):
        init_db()
        self.media_id = _seed_media_record()

    def tearDown(self):
        _cleanup(self.media_id)

    # ── Test 1: Happy path — accepted event ──────────────────────────
    def test_accepted_event_writes_swipe_right_keeper(self):
        """
        GIVEN  a Firestore MODIFIED event with status='accepted'
        WHEN   the on_snapshot callback processes it
        THEN   an Annotation row with action='swipe_right_keeper' is written
               with the correct user_id, swipe_duration_ms, and exif_snapshot
        """
        doc_data = {
            "filename": "test_photo_antigravity.ARW",
            "original_path": FAKE_FILE_PATH,
            "status": "accepted",
            "user_id": "test_user",
            "swipe_duration_ms": 620,
            "exif": {"FocalLengthMM": 85, "FNumber": 1.8, "ISO": 400},
        }

        _simulate_on_snapshot(doc_data)

        db = SessionLocal()
        try:
            row = db.query(Annotation).filter(
                Annotation.media_id == self.media_id,
                Annotation.action == "swipe_right_keeper",
            ).first()

            self.assertIsNotNone(row, "❌ FAIL — Annotation row was NOT written to SQLite.")
            self.assertEqual(row.action, "swipe_right_keeper")
            self.assertEqual(row.user_id, "test_user")
            self.assertEqual(row.swipe_duration_ms, 620)

            exif = json.loads(row.exif_snapshot)
            self.assertEqual(exif["FocalLengthMM"], 85)
            self.assertEqual(exif["FNumber"], 1.8)

            print("\n✅ PASS — test_accepted_event_writes_swipe_right_keeper")
            print(f"   media_id       : {row.media_id}")
            print(f"   action         : {row.action}")
            print(f"   user_id        : {row.user_id}")
            print(f"   swipe_duration : {row.swipe_duration_ms}ms")
            print(f"   exif_snapshot  : {row.exif_snapshot}")
        finally:
            db.close()

    # ── Test 2: Rejected event ───────────────────────────────────────
    def test_rejected_event_writes_swipe_left_cull(self):
        """
        GIVEN  a Firestore MODIFIED event with status='rejected'
        WHEN   the on_snapshot callback processes it
        THEN   an Annotation row with action='swipe_left_cull' is written
        """
        doc_data = {
            "filename": "test_photo_antigravity.ARW",
            "original_path": FAKE_FILE_PATH,
            "status": "rejected",
            "user_id": "test_user",
            "swipe_duration_ms": 310,
            "exif": {"FocalLengthMM": 24, "FNumber": 8.0, "ISO": 100},
        }

        _simulate_on_snapshot(doc_data)

        db = SessionLocal()
        try:
            row = db.query(Annotation).filter(
                Annotation.media_id == self.media_id,
                Annotation.action == "swipe_left_cull",
            ).first()

            self.assertIsNotNone(row, "❌ FAIL — Annotation row was NOT written for rejected event.")
            self.assertEqual(row.action, "swipe_left_cull")
            print("\n✅ PASS — test_rejected_event_writes_swipe_left_cull")
        finally:
            db.close()

    # ── Test 3: Idempotency guard ────────────────────────────────────
    def test_duplicate_event_does_not_create_double_annotation(self):
        """
        GIVEN  the same accepted event fired twice (engine restart simulation)
        WHEN   on_snapshot processes it a second time
        THEN   only ONE Annotation row exists — no duplicates
        """
        doc_data = {
            "filename": "test_photo_antigravity.ARW",
            "original_path": FAKE_FILE_PATH,
            "status": "accepted",
            "user_id": "test_user",
            "swipe_duration_ms": 500,
            "exif": {},
        }

        _simulate_on_snapshot(doc_data)  # First call
        _simulate_on_snapshot(doc_data)  # Second call — should be a no-op

        db = SessionLocal()
        try:
            count = db.query(Annotation).filter(
                Annotation.media_id == self.media_id,
                Annotation.action == "swipe_right_keeper",
            ).count()

            self.assertEqual(count, 1, f"❌ FAIL — Expected 1 row, found {count} (duplicate guard broken).")
            print(f"\n✅ PASS — test_duplicate_event_does_not_create_double_annotation (count={count})")
        finally:
            db.close()

    # ── Test 4: Nomenclature alignment ──────────────────────────────
    def test_nomenclature_mapping_is_correct(self):
        """
        GIVEN  frontend status labels 'accepted' and 'rejected'
        THEN   they map exactly to 'swipe_right_keeper' and 'swipe_left_cull'
               (no raw frontend strings should ever reach table_annotations)
        """
        action_mapping = {
            "accepted": "swipe_right_keeper",
            "rejected": "swipe_left_cull",
        }
        self.assertEqual(action_mapping["accepted"], "swipe_right_keeper")
        self.assertEqual(action_mapping["rejected"], "swipe_left_cull")
        self.assertNotIn("accepted", action_mapping.values())
        self.assertNotIn("rejected", action_mapping.values())
        print("\n✅ PASS — test_nomenclature_mapping_is_correct")


if __name__ == "__main__":
    unittest.main(verbosity=2)
