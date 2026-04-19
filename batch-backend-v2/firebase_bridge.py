import os
import time
import json
import threading
from datetime import timedelta
from pathlib import Path
from typing import Optional, Callable, Dict, Any

import firebase_admin
from firebase_admin import firestore, storage
from firebase_init import initialize_firebase
from google.cloud.firestore_v1.watch import Watch

# Local imports
from models import ImageAssessment, BatchResult
from database import SessionLocal, Media, Annotation, Inference
from vector_store import ChromaManager

class FirebaseBridge:
    """
    Antigravity Engine v2.1 — Module 8: Firebase Bridge
    Handles cloud sync between the Mac Mini and the PWA.
    
    Responsibilities:
    1. Upload RLHF JPEGs to Firebase Storage.
    2. Sync batch/photo metadata to Firestore.
    3. Listen for user swipe decisions (real-time).
    4. Guard against drift and ensure exactly-one decision per photo.
    """
    
    def __init__(self, service_account_path: str, storage_bucket: str):
        self.db = None
        self.bucket = None
        self.initialized = False
        self.service_account_path = service_account_path
        self.storage_bucket = storage_bucket
        self.active_listeners = {}
        self._chroma = None  # Lazy-initialised ChromaManager

    def initialize(self) -> bool:
        """Initialize Firebase Admin SDK."""
        if self.initialized:
            return True
            
        try:
            initialize_firebase()
            
            self.db = firestore.client()
            # If the app was initialized elsewhere without a bucket, we MUST bind it explicitly
            try:
                # User confirmed: gs://style-matcher-9480d.firebasestorage.app
                target_bucket = self.storage_bucket.replace("gs://", "")
                self.bucket = storage.bucket(target_bucket)
                
                # Performance Note: exists() is a network call, but essential for the cloud handshake verification
                if not self.bucket.exists():
                    print(f"❌ [firebase_bridge] Critical: Bucket '{target_bucket}' exists in config but NOT found on GCP.")
                    print("👉 FIX: Go to Firebase Console > Storage > Click 'Get Started' to provision the bucket.")
                    return False
            except Exception as e:
                print(f"❌ [firebase_bridge] Storage access error: {e}")
                return False

            self.initialized = True
            print("[firebase_bridge] Connected to Firebase successfully")
            return True
        except Exception as e:
            print(f"[firebase_bridge] Initialization failed: {e}")
            return False

    # ─── Data Injection ──────────────────────────────────────────────────
    def upload_rlhf_batch(self, batch_id: str, photos: list[ImageAssessment]) -> bool:
        """
        [DEPRECATED] Use push_doppler_manifest for coordinated 70/30 cloud sync.
        Legacy support for uploading a sample batch of RLHF JPEGs.
        """
        if not self.initialize():
            return False
            
        print(f"[firebase_bridge] Uploading batch {batch_id} (Legacy)...")
        # Reuse the new push logic but for a subset
        return self.push_doppler_manifest(batch_id, [
            {
                "filename": p.filename,
                "filepath": p.filepath,
                "enhanced_path": p.enhanced_path,
                "composite_score": p.composite_score,
                "tier": p.tier
            } for p in photos
        ])

    def push_doppler_manifest(self, batch_id: str, manifest_photos: list[dict]) -> bool:
        """
        GA Transition: Mass-injects the 70/30 fatigue-optimized manifest into Firestore.
        Uses 500-op chunked loading to respect Firestore limits.
        """
        if not self.initialize():
            return False

        print(f"[firebase_bridge] Initializing Cloud Ingestion for Batch: {batch_id}")
        
        # 1. Initialize Batch Singleton
        batch_ref = self.db.collection('batches').document(batch_id)
        batch_ref.set({
            'batch_id': batch_id,
            'status': 'ingesting',
            'timestamp': firestore.SERVER_TIMESTAMP,
            'total_photos': len(manifest_photos),
            'processed_count': 0
        })

        # 2. Chunked Firestore Injection (500-op limit)
        CHUNK_SIZE = 450 # Safety margin below 500
        for i in range(0, len(manifest_photos), CHUNK_SIZE):
            chunk = manifest_photos[i:i + CHUNK_SIZE]
            firestore_batch = self.db.batch()
            
            for j, photo in enumerate(chunk):
                # Ensure we have a valid RLHF URL (Physical upload to Storage)
                rlhf_url = ""
                
                # Priority: 1. Dedicated Proxy (rlhf_path), 2. Master Render (enhanced_path)
                # We strictly avoid uploading RAW files (original_path) to Storage for the swiper.
                upload_target = photo.get("rlhf_path") or photo.get("enhanced_path")
                
                if upload_target and os.path.exists(upload_target):
                    # Only upload if it's a JPEG (safety check for browser compatibility)
                    if upload_target.lower().endswith(('.jpg', '.jpeg', '.png')):
                        storage_path = f"rlhf/{batch_id}/{photo['filename']}.jpg"
                        try:
                            # 🧪 Debug: Verify bucket before upload
                            if not self.bucket:
                                print("❌ [firebase_bridge] Storage bucket NOT initialized.")
                            else:
                                blob = self.bucket.blob(storage_path)
                                blob.upload_from_filename(upload_target)
                                
                                # Generate a Signed URL for Vercel/PWA consumption (Bypasses 'allow read: if false')
                                # Expiration: 7 days from now (timedelta avoids the Unix epoch trap)
                                rlhf_url = blob.generate_signed_url(expiration=timedelta(days=7))
                                
                                print(f"✅ [firebase_bridge] Uploaded & Signed {photo['filename']} -> {storage_path}")
                        except Exception as e:
                            print(f"⚠️ [firebase_bridge] Storage upload failed for {photo['filename']}: {str(e)}")
                    else:
                        print(f"⚠️ [firebase_bridge] Skipping non-JPEG upload target: {upload_target}")
                else:
                    if not upload_target:
                        print(f"⚠️ [firebase_bridge] No render found for {photo['filename']} (Sync only)")
                    else:
                        print(f"⚠️ [firebase_bridge] Render path missing on disk: {upload_target}")

                photo_id = f"{batch_id}_{i+j}_{photo['filename'].replace('.', '_')}"
                photo_ref = self.db.collection('photos').document(photo_id)
                firestore_batch.set(photo_ref, {
                    'batch_id': batch_id,
                    'filename': photo['filename'],
                    'original_path': photo['filepath'],
                    'rlhf_url': rlhf_url,
                    'status': 'pending',
                    'score': photo.get('composite_score', 0),
                    'tier': photo.get('tier', 'review'),
                    'timestamp': firestore.SERVER_TIMESTAMP,
                    # ── Visual RAG Schema (Phase B) ──────────────────
                    'genre': photo.get('genre', 'unclassified'),
                    'exif': photo.get('exif', {}),
                    'embedding_id': None,
                    'few_shot_ids': [],
                    'prompt_version': 'v1.0',
                    'presentation_timestamp': None,
                })

            firestore_batch.commit()
            print(f"[firebase_bridge] Comitted Chunk [{i//CHUNK_SIZE + 1}/{(len(manifest_photos)//CHUNK_SIZE)+1}]")

        # 3. Finalize & Set Current Active Singleton
        batch_ref.update({'status': 'ready_for_rlhf'})
        self.db.collection('batches').document('current_active').set({
            'batch_id': batch_id,
            'total_photos': len(manifest_photos),
            'last_sync': firestore.SERVER_TIMESTAMP
        })
        
        print(f"✅ [firebase_bridge] Total Cloud Plane Handshake Complete: {len(manifest_photos)} photos.")
        return True

    # ─── Decision Listener ───────────────────────────────────────────────
    def start_listening(self, on_decision_callback: Callable[[Dict[str, Any]], None]):
        """
        Starts a background listener for photo status changes.
        """
        if not self.initialize():
            return
            
        def on_snapshot(col_snapshot, changes, read_time):
            for change in changes:
                if change.type.name == 'MODIFIED':
                    doc_data = change.document.to_dict()
                    status = doc_data.get('status')
                    if status in ['accepted', 'rejected']:
                        print(f"[firebase_bridge] New decision for {doc_data.get('filename')}: {status}")
                        
                        # MLOps: Write to table_annotations
                        try:
                            # DB session handled per callback to avoid threading issues
                            db = SessionLocal()
                            # Query the media
                            media_record = db.query(Media).filter(Media.file_path == doc_data.get("original_path")).first()
                            
                            if media_record:
                                action_mapping = {
                                    'accepted': 'swipe_right_keeper',
                                    'rejected': 'swipe_left_cull'
                                }
                                
                                # ── Phase D: Retrieve embedding & push to ChromaDB ──
                                embedding_id = None
                                inference_row = (
                                    db.query(Inference)
                                    .filter(
                                        Inference.media_id == media_record.id,
                                        Inference.embedding_blob.isnot(None),
                                    )
                                    .order_by(Inference.created_at.desc())
                                    .first()
                                )

                                if inference_row and inference_row.embedding_blob:
                                    try:
                                        embedding_vector = json.loads(inference_row.embedding_blob)
                                        collection_name = (
                                            "accepted_preferences"
                                            if status == "accepted"
                                            else "rejected_preferences"
                                        )
                                        # Lazy-init ChromaManager (thread-safe: PersistentClient is safe for reads/writes)
                                        if self._chroma is None:
                                            self._chroma = ChromaManager()
                                        self._chroma.add_embedding(
                                            collection_name=collection_name,
                                            photo_hash=media_record.photo_hash,
                                            embedding=embedding_vector,
                                            metadata={
                                                "filename": doc_data.get("filename", ""),
                                                "action": action_mapping.get(status, status),
                                            },
                                        )
                                        embedding_id = inference_row.id
                                        print(f"[firebase_bridge] 🧠 Embedding → {collection_name} for {media_record.photo_hash}")
                                    except (json.JSONDecodeError, KeyError) as vec_err:
                                        print(f"[firebase_bridge] ⚠️ Embedding deserialization failed: {vec_err}")

                                # Pull EXIF snapshot from Firestore doc (set during push_doppler_manifest)
                                exif_snapshot_str = None
                                exif_data = doc_data.get("exif")
                                if exif_data:
                                    exif_snapshot_str = json.dumps(exif_data) if isinstance(exif_data, dict) else str(exif_data)

                                annotation = Annotation(
                                    media_id=media_record.id,
                                    user_id=doc_data.get("user_id", "guest"),
                                    action=action_mapping.get(status, status),
                                    embedding_id=embedding_id,
                                    exif_snapshot=exif_snapshot_str,
                                    swipe_duration_ms=doc_data.get("swipe_duration_ms"),
                                )
                                db.add(annotation)
                                db.commit()
                                print(f"[firebase_bridge] Saved annotation to local DB for {media_record.id}")
                            db.close()
                        except Exception as e:
                            print(f"[firebase_bridge] Failed to log annotation to DB: {e}")
                        
                        if on_decision_callback:
                            on_decision_callback(doc_data)

        # Watch the 'photos' collection for decisions
        query = self.db.collection('photos').where('status', 'in', ['accepted', 'rejected'])
        watch = query.on_snapshot(on_snapshot)
        self.active_listeners['photos'] = watch
        print("[firebase_bridge] Listener active: Waiting for swipes...")

    def stop_listening(self):
        """Cleanly close listeners."""
        for name, watch in self.active_listeners.items():
            watch.unsubscribe()
        self.active_listeners = {}

if __name__ == "__main__":
    # Self-test snippet (requires service account)
    bridge = FirebaseBridge("firebase-service-account.json", "style-matcher-9480d.firebasestorage.app")
    if bridge.initialize():
        print("Self-test: Connection OK")
    else:
        print("Self-test: Failed (Check credentials)")
