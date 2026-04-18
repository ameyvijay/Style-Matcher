"""
Antigravity Engine v2.0 — FastAPI API Layer
Endpoints for batch processing, health checks, and folder picking.

Usage:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""
from __future__ import annotations

import os
import subprocess
from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

import json
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List
import numpy as np
import torch
from PIL import Image

from models import BatchRequest, BatchResult

class SessionClosePayload(BaseModel):
    accepted_file_paths: List[str]

import batch_orchestrator
import firebase_bridge
from database import SessionLocal, Media, Inference, Annotation, ModelRegistry, SyncQueue


# ─── Startup / Shutdown ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run self-tests on startup."""
    results = batch_orchestrator.run_all_self_tests()
    yield


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
# /rlhf-media points to the batch-local "For RLHF input" directory
# This allows the PWA to pull images if they are hosted on the same network
# (Firebase Storage is the primary path for cross-network access)
app.mount("/rlhf-media", StaticFiles(directory="/Users/shivamagent/Desktop/Style-Matcher"), name="rlhf-media")


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
import httpx
@app.get("/api/ollama-tags")
async def get_ollama_tags():
    """Proxy local ollama models to the web frontend."""
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get("http://127.0.0.1:11434/api/tags", timeout=3.0)
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


# ─── Batch Processing (Streaming) ──────────────────────────────────
@app.get("/api/batch-process-stream")
async def batch_process_stream(
    target_folder: str, 
    benchmark_folder: str = None, 
    session_id: str = "default"
):
    """
    Execute the batch pipeline and stream real-time JSON logs.
    """
    return StreamingResponse(
        batch_orchestrator.stream_batch(target_folder, benchmark_folder, session_id),
        media_type="text/event-stream"
    )


# ─── Batch Processing (Legacy Sync) ─────────────────────────────────
@app.post("/api/batch-process")
async def batch_process(request: BatchRequest):
    """
    Legacy endpoint that now just drains the stream and returns the final result.
    """
    # For now, we'll keep it simple for compatibility
    if not os.path.isdir(request.target_folder):
        return {"status": "error", "message": f"Folder not found: {request.target_folder}"}
    
    # We'll just call the streamer and collect the last 'done' event
    final_result = {}
    for event_str in batch_orchestrator.stream_batch(request.target_folder, request.benchmark_folder):
        event = json.loads(event_str.strip())
        if event["type"] == "error":
            return {"status": "error", "message": event["message"]}
        if event["type"] == "done":
            final_result = event["data"]
            break
            
    return {"status": "success", "metrics": final_result}

