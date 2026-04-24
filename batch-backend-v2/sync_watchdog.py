#!/usr/bin/env python3
"""
Antigravity Engine - Hybrid-Cloud Sync Watchdog
Mac Mini GPU Worker & Firestore Listener

Execution: Run via start_engine.sh
"""

import os
import sys
import time
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Dict, Any

import firebase_admin
from firebase_admin import firestore
from google.cloud.firestore_v1.watch import Watch
from firebase_init import initialize_firebase

# Local Imports
import raw_developer

class MirrorManager:
    """
    Handles hierarchical file mirroring and atomic Stage 9 rendering.
    Ensures LOCAL_MASTER_ROOT replicates exactly the subfolder structure of SOURCE_ROOT.
    """
    def __init__(self, source_root: str, local_master_root: str):
        self.source_root = Path(source_root).resolve()
        self.local_master_root = Path(local_master_root).resolve()

    def _get_mirrored_destination(self, source_filepath: str) -> Path:
        source_path = os.path.abspath(source_filepath)
        root_path = os.path.abspath(self.source_root)

        # Guard against arbitrary paths outside the SOURCE_ROOT
        try:
            if os.path.commonpath([root_path, source_path]) != root_path:
                raise ValueError(f"Source path {source_path} breaches allowed source root constraint {root_path}.")
        except ValueError as e:
             raise ValueError(f"Constraint Violation: {e}")

        rel_path = os.path.relpath(source_path, root_path)
        target_dir = os.path.join(self.local_master_root, os.path.dirname(rel_path))
        os.makedirs(target_dir, exist_ok=True)

        return Path(os.path.join(target_dir, f"{Path(source_path).stem}_master.jpg"))
    def render_atomic(self, source_filepath: str) -> str:
        """
        Executes Stage 9 Render with Atomic Handshake.
        Renders to .tmp then os.replace to target.
        """
        final_dest = self._get_mirrored_destination(source_filepath)
        tmp_dest = final_dest.with_suffix(".tmp")
        
        print(f"▶️ [Stage 9] Rendering: {source_filepath} -> {tmp_dest}")
        
        # --- Stage 9 M4 MPS / rawpy execution ---
        success = raw_developer.develop(source_filepath, str(tmp_dest))
        
        if not success or not tmp_dest.exists():
            raise RuntimeError(f"Stage 9 Render failed for {source_filepath}")
            
        # Final Handshake (Atomic Rename)
        os.replace(tmp_dest, final_dest)
        print(f"✅ [Stage 9] Atomic Land: {final_dest}")
        return str(final_dest)

class FirebaseWorker:
    """
    Real-time Firestore listener (The Pull Mechanism).
    Monitors status == 'accepted' and triggers local GPU fulfillment.
    """
    def __init__(self, service_account: str, source_root: str, local_master_root: str):
        initialize_firebase()
            
        self.db = firestore.client()
        self.mirror_manager = MirrorManager(source_root, local_master_root)
        self.watch = None

    def start_listener(self):
        print("📡 Instantiating Global Pull Listener (Firestore)...")
        query = self.db.collection('photos').where('status', '==', 'accepted')
        self.watch = query.on_snapshot(self._on_snapshot)
        print("🟢 Antigravity Control Plane: Connected.")

    def _on_snapshot(self, col_snapshot, changes, read_time):
        for change in changes:
            if change.type.name in ['ADDED', 'MODIFIED']:
                doc = change.document
                data = doc.to_dict()
                
                # Path Drift vulnerability check
                source_path = data.get("original_path") or data.get("source_filepath")
                if not source_path or not os.path.exists(source_path):
                    print(f"⚠️ [Vulnerability] Path Drift detected: {source_path}")
                    doc.reference.update({"status": "error_path_missing"})
                    continue
                
                # Hand-off to Stage 9 Atomic Render
                print(f"🔥 [Decision] Control Plane triggered render for: {os.path.basename(source_path)}")
                self._execute_remote_render(doc.reference, source_path)

    def _execute_remote_render(self, doc_ref, source_path: str):
        try:
            # Stage 9 execution via Mirror Manager
            final_path = self.mirror_manager.render_atomic(source_path)
            doc_ref.update({
                "status": "completed", 
                "local_master": final_path,
                "completed_at": firestore.SERVER_TIMESTAMP
            })
        except Exception as e:
            print(f"❌ [Error] Render Task Failed: {e}")
            doc_ref.update({"status": "error_render_failed", "error": str(e)})

def check_disk_space(min_gb=10) -> bool:
    """Mandate: Ensure worker has enough thermal/storage overhead."""
    total, used, free = shutil.disk_usage("/")
    free_gb = free // (2**30)
    print(f"💾 Storage Health: {free_gb}GB free")
    return free_gb >= min_gb

if __name__ == "__main__":
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  🚀 Antigravity Hybrid-Cloud Worker v3.0")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # 1. Environment Loading (Mocking for standalone if not run via shell)
    source_root = os.getenv("SOURCE_ROOT", "/Users/amey/Pictures/RAW_Library")
    local_master_root = os.getenv("LOCAL_MASTER_ROOT", "/Users/amey/Pictures/Antigravity_Masters")
    service_account = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "./firebase-service-account.json")
    
    # 2. Disk Guard
    if not check_disk_space(int(os.getenv("MIN_DISK_GB", 10))):
        print("❌ CRITICAL: Insufficient disk space (Min 10GB required).")
        sys.exit(1)

    # 3. Boot Worker
    try:
        worker = FirebaseWorker(service_account, source_root, local_master_root)
        worker.start_listener()
        
        # Keep main thread alive
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n👋 Worker shutting down gracefully...")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Worker Crash: {e}")
        sys.exit(1)
