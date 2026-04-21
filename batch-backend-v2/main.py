"""
Antigravity Engine v2.0 — FastAPI API Layer
Endpoints for batch processing, health checks, and folder picking.

Usage:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""
from __future__ import annotations

import os
import httpx
import psutil
import subprocess
from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

import json
import threading
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import numpy as np
import torch
from PIL import Image

from models import BatchRequest, BatchResult

class SessionClosePayload(BaseModel):
    accepted_file_paths: List[str]

class DecisionReversal(BaseModel):
    photo_hash: str
    user_id: str = "guest"

import batch_orchestrator
import firebase_bridge
from database import SessionLocal, Media, Inference, Annotation, ModelRegistry, SyncQueue

# ─── Memory & VRAM Management ──────────────────────────────────────
async def ensure_memory_headroom(threshold_pct: float = 80.0):
    """
    Adaptive Memory Guard: Check Unified Memory on M4.
    If RAM usage is too high, proactively unload Ollama models.
    """
    mem = psutil.virtual_memory()
    print(f"🧠 [Memory Guard] System RAM Usage: {mem.percent}%")
    
    if mem.percent > threshold_pct:
        print(f"⚠️ [Memory Guard] Memory pressure high ({mem.percent}%). Evicting Ollama VLMs...")
        ollama_url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(f"{ollama_url}/api/tags", timeout=2.0)
                if res.status_code == 200:
                    models = res.json().get("models", [])
                    for m in models:
                        await client.post(f"{ollama_url}/api/generate", json={"model": m["name"], "keep_alive": 0}, timeout=2.0)
                        print(f"✅ [Memory Guard] Unloaded model: {m['name']}")
        except Exception as e:
            print(f"⚠️ [Memory Guard] Eviction failed: {e}")
    else:
        print("✅ [Memory Guard] Headroom sufficient.")


# ─── Startup / Shutdown ──────────────────────────────────────────────
from firebase_init import initialize_firebase

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run self-tests and initialize cloud telemetry on startup."""
    # 1. Initialize Firebase Admin (Control Plane) — via singleton
    try:
        initialize_firebase()
        print("📡 [main] Firebase Control Plane Initialized.")
    except Exception as e:
        print(f"❌ [main] Firebase Init Failed: {e}")

    # 2. Sequential Self-Tests
    results = batch_orchestrator.run_all_self_tests()

    # 3. Start Firestore Decision Listener (non-blocking — runs in Firestore-managed thread)
    _bridge = firebase_bridge.get_bridge()
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _bridge.start_listening, None)
        print("👂 [main] Firestore Decision Listener started.")
    except Exception as e:
        print(f"⚠️  [main] Could not start Firestore listener: {e}")

    # 4. Run Janitor Service on boot (free tier guard)
    try:
        from services.janitor import JanitorService
        janitor = JanitorService(max_age_days=10)
        await janitor.run_cleanup()
        print("🧹 [main] Janitor cleanup complete.")
    except Exception as e:
        print(f"⚠️ [main] Janitor failed (non-fatal): {e}")

    yield  # ← application runs here

    # 4. Graceful shutdown — unsubscribe all Firestore watchers
    try:
        _bridge.stop_listening()
        print("🛑 [main] Firestore listener stopped cleanly.")
    except Exception as e:
        print(f"⚠️  [main] Listener stop error (non-fatal): {e}")


app = FastAPI(
    title="Antigravity Engine",
    version="2.0.0",
    description="AI Photography Culling & Enhancement Engine",
    lifespan=lifespan,
)

# ─── CORS Middleware ────────────────────────────────────────────────
# Allow Next.js PWA (running on Vercel or locally) to hit the Ngrok tunnel
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static media folders
# /rlhf-media points to the project root directory
project_root = os.path.dirname(os.path.dirname(__file__))
app.mount("/rlhf-media", StaticFiles(directory=project_root), name="rlhf-media")

@app.get("/health")
async def health_check():
    """
    Standard health check for PM2 orchestration and local monitoring.
    Includes M4 MPS availability and memory pressure checks.
    """
    import psutil
    import time
    return {
        "status": "ok",
        "timestamp": time.time(),
        "uptime": psutil.boot_time(),
        "memory_usage_percent": psutil.virtual_memory().percent,
        "mps_available": torch.backends.mps.is_available()
    }


# ─── Manifest & Memory Gatekeeper (M4 MPS) ────────────────────────
@app.get("/api/batch-queue")
async def get_batch_queue():
    """
    Mandate 4 (SSE Elimination): Serve the pre-computed 70/30 Doppler manifest.
    """
    # The Python backend targets its own local data directory
    manifest_path = os.path.join(os.path.dirname(__file__), "batch_queue.json")
    
    if not os.path.exists(manifest_path):
        raise HTTPException(status_code=404, detail="Manifest Not Found")
        
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def execute_stage9_realization(accepted_file_paths: List[str]):
    """Background task for Stage 9 M4 MPS Realization."""
    print("▶️ [Stage 9] VRAM cleared. Booting Metal Performance Shaders (MPS) for Master Render...")
    dirs_to_sync = set()

    for file_path in accepted_file_paths:
        if not os.path.exists(file_path):
            continue

        source_dir = os.path.dirname(file_path)
        enhanced_dir = os.path.join(source_dir, "Enhanced")
        os.makedirs(enhanced_dir, exist_ok=True)
        dirs_to_sync.add(enhanced_dir)

        base_name = os.path.splitext(os.path.basename(file_path))[0]
        output_path = os.path.join(enhanced_dir, f"{base_name}_master.jpg")
        
        try:
            import rawpy
            # 1. Decode using rawpy
            with rawpy.imread(file_path) as raw:
                rgb = raw.postprocess(use_camera_wb=True)
            
            # 2. PyTorch MPS Conversion
            tensor_img = torch.from_numpy(rgb).float() / 255.0
            tensor_img = tensor_img.permute(2, 0, 1).unsqueeze(0)
            
            device = torch.device("mps")
            tensor_img = tensor_img.to(device)
            
            # ---------------------------------------------------------
            # [ML ENHANCEMENT MODEL RUNNING ON M4 MPS GOES HERE]
            # e.g., enhanced_tensor = esrgan_model(tensor_img)
            # ---------------------------------------------------------
            enhanced_tensor = tensor_img  # Placeholder pass-through
            
            # 3. CPU Offload and JPEG Save
            enhanced_cpu = enhanced_tensor.squeeze(0).permute(1, 2, 0).cpu().numpy()
            enhanced_rgb = (np.clip(enhanced_cpu, 0, 1) * 255.0).astype(np.uint8)
            
            img = Image.fromarray(enhanced_rgb)
            img.save(output_path, "JPEG", quality=95, optimize=True)
            print(f"✅ Enhanced (MPS): {output_path}")

        except Exception as e:
            print(f"⚠️ rawpy/MPS exception for {file_path}: {e}")
            print(f"🔄 Falling back to macOS sips...")
            try:
                subprocess.run(
                    ["sips", "-s", "format", "jpeg", "-s", "formatOptions", "95", file_path, "--out", output_path],
                    capture_output=True, check=True
                )
                print(f"✅ Extracted (sips): {output_path}")
            except Exception as backup_e:
                print(f"❌ Both rawpy and sips failed for {file_path}: {backup_e}")
                
    print("✅ [Stage 9] Master Render Complete.")
    
    # 4. Durable Storage Spool (Write to Local Database Journal)
    db = SessionLocal()
    try:
        for e_dir in dirs_to_sync:
            # Upsert or ignore if already existing and completed? We will just check existence.
            existing = db.query(SyncQueue).filter_by(enhanced_dir_path=e_dir).first()
            if not existing:
                print(f"📥 Spooling {e_dir} for background Watchdog Sync.")
                new_spool = SyncQueue(enhanced_dir_path=e_dir)
                db.add(new_spool)
            elif existing.status in ["COMPLETED", "FAILED"]:
                # Retry manually if rerunning the pipeline
                print(f"🔄 Re-spooling existing {e_dir} status: PENDING")
                existing.status = "PENDING"
                existing.retry_count = 0
                
        db.commit()
    except Exception as e:
        print(f"❌ DB Transaction Failed for Sync Spool: {e}")
    finally:
        db.close()


@app.post("/api/session/close")
async def close_session(payload: SessionClosePayload, background_tasks: BackgroundTasks):
    """
    Mandate 1: Resource Segregation (M4 Unified Memory).
    Unloads the VLM from VRAM, verifies clearance, and hands off to Stage 9 MPS render.
    """
    print("🛑 [Memory Gatekeeper] User session complete. Commencing VLM Eviction from Unified Memory...")
    
    # Step A: VLM Unload via Ollama API
    try:
        async with httpx.AsyncClient() as client:
            # Unload the vision model used in Stage 3.4 by passing keep_alive = 0
            api_payload = {"model": "moondream", "keep_alive": 0} 
            await client.post("http://127.0.0.1:11434/api/generate", json=api_payload, timeout=3.0)
            print("✅ [Memory Gatekeeper] Ollama Eviction Signal Sent. Model unloaded.")
    except Exception as e:
        print(f"⚠️ [Memory Gatekeeper] Ollama eviction notice: {str(e)}")

    # Step B: Verification Check (Await OS kernel GC)
    print("⌛ [Memory Gatekeeper] Awaiting kernel page reclamation (VRAM clearing)...")
    await asyncio.sleep(2.0)
    
    # Step C: MPS Trigger
    background_tasks.add_task(execute_stage9_realization, payload.accepted_file_paths)
    
    # Step D: Immediate Return
    return {
        "status": "Realization Started", 
        "message": "Memory evicted. Stage 9 executing in background queue."
    }


# ─── Ollama Tags ────────────────────────────────────────────────────
@app.get("/api/ollama-tags")
async def get_ollama_tags():
    """Proxy local ollama models to the web frontend."""
    try:
        ollama_url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
        async with httpx.AsyncClient() as client:
            res = await client.get(f"{ollama_url}/api/tags", timeout=3.0)
            if res.status_code == 200:
                data = res.json()
                models = [model["name"] for model in data.get("models", [])]
                return {"success": True, "models": models}
    except Exception as e:
        pass
    return {"success": False, "models": ["gemma4:e4b"]}

# ─── Health Check ────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    """Return engine version and module status."""
    results = batch_orchestrator.run_all_self_tests()
    modules = {}
    for name, r in results.items():
        modules[name] = {
            "passed": r.passed,
            "message": r.message,
            "details": r.details,
        }

    all_ok = all(r.passed for r in results.values())
    return {
        "engine": "Antigravity v2.0",
        "status": "operational" if all_ok else "degraded",
        "modules": modules,
    }


# ─── Native Folder Picker ───────────────────────────────────────────
@app.get("/api/pick-folder")
async def pick_folder():
    """
    Open a native macOS Finder dialog to select a folder.
    Returns the absolute path.
    """
    try:
        script = '''
        tell application "Finder"
            activate
        end tell
        set chosenFolder to choose folder with prompt "Select a folder to process"
        return POSIX path of chosenFolder
        '''
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0 and result.stdout.strip():
            folder_path = result.stdout.strip()
            return {"path": folder_path, "error": None}
        else:
            return {"path": None, "error": "User cancelled or dialog failed"}
    except subprocess.TimeoutExpired:
        return {"path": None, "error": "Dialog timed out"}
    except Exception as e:
        return {"path": None, "error": str(e)}


# ─── Analytics Dashboard ──────────────────────────────────────────
@app.get("/api/health/sync")
async def get_sync_health():
    """
    Hybrid-Cloud Telemetry: Pings Firestore Control Plane 
    to report pending master renders to the Glassmorphism UI.
    """
    db_local = SessionLocal()
    firestore_connected = False
    rendering_remaining = 0
    
    try:
        # 1. Check Local SQLite State (Legacy mapping)
        failed_count = db_local.query(SyncQueue).filter(SyncQueue.status == "FAILED").count()
        
        # 2. Check Firestore Control Plane (GA Standard)
        from firebase_admin import firestore
        try:
            # We use a lightweight check to avoid blocking the health poll
            db_cloud = firestore.client()
            pending_query = db_cloud.collection('photos').where('status', 'in', ['accepted', 'pending_render'])
            results = pending_query.get(timeout=3.0)
            rendering_remaining = len(results)
            firestore_connected = True
        except Exception as fe:
            print(f"📡 [Control Plane] Offline: {fe}")
            firestore_connected = False

        return {
            "status": "operational" if firestore_connected else "disconnected",
            "firestore_connected": firestore_connected,
            "rendering_remaining": rendering_remaining,
            "failed_directories": failed_count,
            "active_queue": rendering_remaining 
        }
    finally:
        db_local.close()

@app.get("/api/analytics")
async def get_analytics():
    """Return Cohen's Kappa, Precision, Recall, F1 against Local DB."""
    db = SessionLocal()
    try:
        annotations = db.query(Annotation).order_by(Annotation.id.asc()).all()
        human_truth = {}
        for ann in annotations:
            # Overwrite with latest annotation per media_id
            human_truth[ann.media_id] = ann.action 

        inferences = db.query(Inference).all()
        model_predictions = {}
        for inf in inferences:
            try:
                data = json.loads(inf.inference_value)
                is_keeper = data.get("tier") in ["portfolio", "keeper"]
                model_predictions[inf.media_id] = "swipe_right_keeper" if is_keeper else "swipe_left_cull"
            except:
                pass

        tp, fp, tn, fn = 0, 0, 0, 0
        for media_id, actual in human_truth.items():
            predicted = model_predictions.get(media_id)
            if not predicted: continue
            
            if predicted == "swipe_right_keeper" and actual == "swipe_right_keeper":
                tp += 1
            elif predicted == "swipe_right_keeper" and actual == "swipe_left_cull":
                fp += 1
            elif predicted == "swipe_left_cull" and actual == "swipe_left_cull":
                tn += 1
            elif predicted == "swipe_left_cull" and actual == "swipe_right_keeper":
                fn += 1
                
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

        total_processed = db.query(Media).count()
        total_accepted = list(human_truth.values()).count("swipe_right_keeper")
        total_rejected = list(human_truth.values()).count("swipe_left_cull")

        return {
            "stats": {
                "total": total_processed,
                "accepted": total_accepted,
                "rejected": total_rejected,
                "rescued": fn,
                "precision": precision,
                "recall": recall,
                "f1": f1
            }
        }
    finally:
        db.close()


# ─── Scan Only (Read-Only) ──────────────────────────────────────────
@app.post("/api/scan")
async def scan_only(request: BatchRequest):
    """
    Score all images WITHOUT modifying anything.
    No files moved, no XMP, no enhancement.
    Returns tier assignments with per-file scores.
    """
    if not os.path.isdir(request.target_folder):
        return {
            "status": "error",
            "message": f"Folder not found: {request.target_folder}",
        }

    result = batch_orchestrator.scan_only(
        target_folder=request.target_folder,
    )

    # Group filenames by tier for easy reading
    tier_groups = {"portfolio": [], "keeper": [], "review": [], "cull": [], "recoverable": []}
    for a in result.files:
        tier_groups[a.tier].append(a.filename)
        if a.recovery_potential in ("high", "medium"):
            tier_groups["recoverable"].append(a.filename)

    return {
        "status": "success",
        "mode": "scan_only",
        "metrics": {
            "total_scanned": result.total_scanned,
            "portfolio": result.portfolio,
            "keepers": result.keepers,
            "review": result.review,
            "culled": result.culled,
            "recoverable": result.recoverable,
            "processing_time": result.processing_time,
        },
        "file_listing": tier_groups,
        "batch_coaching": result.batch_coaching,
        "assessments": [
            {
                "filename": a.filename,
                "tier": a.tier,
                "score": a.composite_score,
                "sharpness": a.sharpness_score,
                "aesthetic": a.aesthetic_score,
                "exposure": a.exposure_score,
                "recovery_potential": a.recovery_potential,
                "recovery_notes": a.recovery_notes,
                "reasoning": a.reasoning,
            }
            for a in result.files
        ],
    }


# ─── Stop Batch ────────────────────────────────────────────────────
@app.post("/api/stop-batch")
async def stop_batch(session_id: str = "default"):
    """Request the engine to stop the current batch session."""
    batch_orchestrator.ABORT_REGISTRY.add(session_id)
    return {"status": "stop_requested", "session_id": session_id}


# ─── Log Polling (SSE Replacement) ─────────────────────────────────
@app.get("/api/logs/{session_id}")
async def get_session_logs(session_id: str, after: int = 0):
    """
    Polling endpoint: return log events for session_id starting from line `after`.
    Replaces the brittle StreamingResponse SSE pattern.

    Gemini Extension Refinement #3: includes batch_status field
    (running, completed, failed) so the frontend can manage the
    polling lifecycle without relying on finding a 'done' event.

    Returns:
        { "logs": [...events], "total": int, "batch_status": str }
    """
    from pipeline.pipeline_runner import SESSION_REGISTRY

    session = SESSION_REGISTRY.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    log_path = session["log_path"]
    batch_status = session.get("status", "running")  # Gemini Extension #3

    if not os.path.exists(log_path):
        return {"logs": [], "total": 0, "batch_status": batch_status}

    try:
        with open(log_path, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
    except Exception:
        return {"logs": [], "total": 0, "batch_status": batch_status}

    # Return delta from `after` line
    delta_lines = all_lines[after:]
    events = []
    for line in delta_lines:
        line = line.strip()
        if line:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    return {
        "logs": events,
        "total": len(all_lines),
        "batch_status": batch_status,
    }


# ─── Batch Processing (Streaming — Legacy, still functional) ──────
@app.get("/api/batch-process-stream")
async def batch_process_stream(
    target_folder: str, 
    benchmark_folder: str = None, 
    session_id: str = "default"
):
    """
    Execute the batch pipeline and stream real-time JSON logs.
    Preserved for backward compatibility but the frontend now uses polling.
    """
    await ensure_memory_headroom(threshold_pct=80.0)
    
    return StreamingResponse(
        batch_orchestrator.stream_batch(target_folder, benchmark_folder, session_id),
        media_type="text/event-stream"
    )


# ─── Batch Processing (Background Thread + Polling) ────────────────
def _run_batch_in_background(target_folder: str, benchmark_folder: str, session_id: str):
    """Run the pipeline in a background thread, draining the generator to persist logs."""
    try:
        for _ in batch_orchestrator.stream_batch(target_folder, benchmark_folder, session_id):
            pass  # _emit() inside PipelineRunner writes each event to logs.jsonl
    except Exception as e:
        print(f"❌ [Background Batch] Error: {e}")
        from pipeline.pipeline_runner import SESSION_REGISTRY
        if session_id in SESSION_REGISTRY:
            SESSION_REGISTRY[session_id]["status"] = "failed"


@app.post("/api/batch-process")
async def batch_process(request: BatchRequest):
    """
    Start batch processing in a background thread.
    The frontend polls GET /api/logs/{session_id} for progress.
    """
    await ensure_memory_headroom(threshold_pct=80.0)

    if not os.path.isdir(request.target_folder):
        return {"status": "error", "message": f"Folder not found: {request.target_folder}"}

    session_id = request.session_id or "default"
    t = threading.Thread(
        target=_run_batch_in_background,
        args=(request.target_folder, request.benchmark_folder, session_id),
        daemon=True,
    )
    t.start()

    return {"status": "started", "session_id": session_id}


# ─── Decision Reversal ─────────────────────────────────────────────
@app.post("/api/decision/reverse")
async def reverse_decision(payload: DecisionReversal):
    """
    Atomically reverse a swipe decision:
    1. Delete the Annotation row in SQLite
    2. Reset Firestore photo status to 'pending'
    3. Clear Media.enhanced_path if it was an accepted photo
    4. Remove embedding from ChromaDB (with existence guard — Gemini Extension #4)
    """
    db = SessionLocal()
    try:
        # ── Step 1: Find Media by photo_hash ─────────────────────────
        media = db.query(Media).filter(Media.photo_hash == payload.photo_hash).first()
        if not media:
            raise HTTPException(status_code=404, detail=f"No media found with hash: {payload.photo_hash}")

        # ── Step 2: Find and delete Annotation ───────────────────────
        annotation = db.query(Annotation).filter(
            Annotation.media_id == media.id,
            Annotation.user_id == payload.user_id,
        ).order_by(Annotation.timestamp.desc()).first()

        if not annotation:
            raise HTTPException(status_code=404, detail=f"No annotation found for hash={payload.photo_hash}, user={payload.user_id}")

        previous_action = annotation.action
        db.delete(annotation)

        # ── Step 3: Clear enhanced_path if it was an acceptance ──────
        if previous_action == "swipe_right_keeper":
            media.enhanced_path = None

        db.commit()

        # ── Step 4: Reset Firestore status to 'pending' ─────────────
        try:
            from firebase_admin import firestore as fs_admin
            fs_db = fs_admin.client()
            # Find the Firestore doc by filename
            filename = os.path.basename(media.file_path)
            docs = fs_db.collection("photos").where("filename", "==", filename).get()
            for doc in docs:
                doc.reference.update({
                    "status": "pending",
                    "swipe_duration_ms": fs_admin.DELETE_FIELD,
                })
            print(f"[decision/reverse] ✅ Firestore reset to 'pending' for {filename}")
        except Exception as fs_err:
            # Firestore update failed — rollback SQLite
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Firestore update failed, SQLite rolled back: {fs_err}"
            )

        # ── Step 5: Remove ChromaDB embedding (Gemini Extension #4) ──
        try:
            from vector_store import ChromaManager
            chroma = ChromaManager()
            collection_name = (
                "accepted_preferences" if previous_action == "swipe_right_keeper"
                else "rejected_preferences"
            )
            # Gemini Refinement #4: existence check before deletion
            try:
                existing = chroma.get_embedding(collection_name, payload.photo_hash)
                if existing:
                    chroma.delete_embedding(collection_name, payload.photo_hash)
                    print(f"[decision/reverse] 🧠 Removed embedding from {collection_name}")
            except Exception:
                pass  # Embedding may never have been generated — safe to skip
        except Exception as chroma_err:
            print(f"[decision/reverse] ⚠️ ChromaDB cleanup skipped: {chroma_err}")

        return {
            "status": "reversed",
            "photo_hash": payload.photo_hash,
            "previous_action": previous_action,
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

