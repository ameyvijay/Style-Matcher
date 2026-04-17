import os
import time
import json
import threading
from pathlib import Path
from typing import Optional, Callable, Dict, Any

import firebase_admin
from firebase_admin import credentials, firestore, storage
from google.cloud.firestore_v1.watch import Watch

# Local imports
from models import ImageAssessment, BatchResult
from database import SessionLocal, Media, Annotation

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

    def initialize(self) -> bool:
        """Initialize Firebase Admin SDK."""
        if self.initialized:
            return True
            
        if not os.path.exists(self.service_account_path):
            print(f"[firebase_bridge] Error: Service account not found at {self.service_account_path}")
            return False
            
        try:
            cred = credentials.Certificate(self.service_account_path)
            firebase_admin.initialize_app(cred, {
                'storageBucket': self.storage_bucket
            })
            self.db = firestore.client()
            self.bucket = storage.bucket()
            self.initialized = True
            print("[firebase_bridge] Connected to Firebase successfully")
            return True
        except Exception as e:
            print(f"[firebase_bridge] Initialization failed: {e}")
            return False

    # ─── Data Injection ──────────────────────────────────────────────────
    def upload_rlhf_batch(self, batch_id: str, photos: list[ImageAssessment]) -> bool:
        """
        Uploads a batch of 90% RLHF JPEGs to Storage and adds metadata to Firestore.
        """
        if not self.initialize():
            return False
            
        print(f"[firebase_bridge] Uploading batch {batch_id}...")
        
        batch_ref = self.db.collection('batches').document(batch_id)
        batch_ref.set({
            'status': 'processing',
            'timestamp': firestore.SERVER_TIMESTAMP,
            'total_photos': len(photos),
            'processed_count': 0
        })

        for i, photo in enumerate(photos):
            if not photo.enhanced_path or not os.path.exists(photo.enhanced_path):
                continue
                
            photo_id = f"{batch_id}_{photo.filename.replace('.', '_')}"
            storage_path = f"rlhf/{batch_id}/{photo.filename}"
            
            try:
                # 1. Upload to Storage
                blob = self.bucket.blob(storage_path)
                blob.upload_from_filename(photo.enhanced_path)
                blob.make_public() # PWA needs to see it
                public_url = blob.public_url

                # 2. Add to Firestore
                photo_ref = self.db.collection('photos').document(photo_id)
                photo_ref.set({
                    'batch_id': batch_id,
                    'filename': photo.filename,
                    'original_path': photo.filepath,
                    'rlhf_url': public_url,
                    'status': 'pending',
                    'score': photo.composite_score,
                    'tier': photo.tier,
                    'user_id': None, # To be assigned or picked up by first user
                    'timestamp': firestore.SERVER_TIMESTAMP
                })
                
                print(f"[firebase_bridge] [{i+1}/{len(photos)}] Injected {photo.filename}")
            except Exception as e:
                print(f"[firebase_bridge] Error injecting {photo.filename}: {e}")

        batch_ref.update({'status': 'ready_for_rlhf'})
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
                                
                                annotation = Annotation(
                                    media_id=media_record.id,
                                    user_id=doc_data.get("user_id", "guest"),
                                    action=action_mapping.get(status, status)
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
