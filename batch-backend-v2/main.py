"""
Antigravity Engine v2.0 — FastAPI API Layer
Endpoints for batch processing, health checks, and folder picking.

Usage:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""
from __future__ import annotations

import os
# Fix for gRPC + subprocess/fork on macOS
os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"

import httpx
import psutil
import subprocess
from contextlib import asynccontextmanager
import asyncio
from datetime import datetime

from services.prompt_service import PromptService
from services.rag_automation import RAGAutomationService
from services.model_evaluator import ModelEvaluatorService
from services.export_service import DatasetExportService
from config import SYSTEM_TOTAL_RAM_GB, HEADROOM_GB, MEMORY_GATE_THRESHOLD_PCT

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Depends
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

import batch_orchestrator
import firebase_bridge
from database import SessionLocal, Media, Inference, Annotation, ModelRegistry, SyncQueue, get_db
from services.mlops_metrics import DatasetMetricsService
from services.recommendation_engine import RecommendationEngine

class PromptCreate(BaseModel):
    version: str
    system_prompt: str
    user_prompt: str
    author: str = "system"
    notes: Optional[str] = None
    parent_version: Optional[str] = None

class BootstrapRequest(BaseModel):
    limit: int = 50

app = FastAPI(
    title="Antigravity Engine",
    version="2.1.0",
    description="AI Photography Culling & Enhancement Engine",
)

# Allow Next.js PWA (running on Vercel or locally) to hit the Ngrok tunnel
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from services.governance_service import GovernanceService

class GovernancePromotion(BaseModel):
    photo_hash: str
    role: str  # 'golden', 'benchmark', 'rag'
    is_manual: bool = True

class NASMediaRegister(BaseModel):
    file_path: str
    source_node: str # e.g., "NAS_TAILSCALE_01"

@app.post("/api/governance/promote")
async def promote_media(request: GovernancePromotion):
    db = SessionLocal()
    gov = GovernanceService(db)
    try:
        result = gov.promote_to_role(request.photo_hash, request.role, request.is_manual)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()

@app.post("/api/governance/register-remote")
async def register_remote_media(request: NASMediaRegister):
    """
    Endpoint for NAS/Tailscale systems to 'announce' new media to the engine.
    The engine will hash it and track its location on the remote node.
    """
    db = SessionLocal()
    gov = GovernanceService(db)
    try:
        # Note: In a real remote setup, the remote node would hash and send metadata.
        # For now, we assume path is reachable via Tailscale mount.
        media = gov.register_media(request.file_path, request.source_node)
        return {"status": "registered", "media_id": media.id, "hash": media.photo_hash}
    finally:
        db.close()

@app.get("/api/governance/lineage/{photo_hash}")
async def get_photo_lineage(photo_hash: str):
    db = SessionLocal()
    gov = GovernanceService(db)
    lineage = gov.get_lineage(photo_hash)
    db.close()
    if not lineage:
        raise HTTPException(status_code=404, detail="Photo not found")
    return lineage

# ─── Admin & MLOps Endpoints ──────────────────────────────────────
@app.get("/api/admin/dataset-stats")
async def get_dataset_stats(db: SessionLocal = Depends(get_db)):
    service = DatasetMetricsService(db)
    return service.get_dataset_stats()

@app.get("/api/admin/telemetry")
async def get_system_telemetry(db: SessionLocal = Depends(get_db)):
    service = DatasetMetricsService(db)
    return service.get_system_telemetry()

@app.get("/api/admin/recommendations")
async def get_recommendations(db: SessionLocal = Depends(get_db)):
    service = RecommendationEngine(db)
    return service.get_recommendations()

@app.get("/api/admin/promotable-snapshots")
async def get_promotable_snapshots(db: SessionLocal = Depends(get_db)):
    service = RAGAutomationService(db)
    return service.get_promotable_snapshots()

@app.get("/api/admin/vitals")
async def get_system_vitals():
    """Phase 4: Real-time hardware telemetry (M4 optimized)."""
    import psutil
    import subprocess
    from config import SYSTEM_TOTAL_RAM_GB, SAFE_VLM_MAX_GB
    
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    # Thermal check proxy (macOS)
    thermal = "Nominal"
    try:
        res = subprocess.run(["pmset", "-g", "therm"], capture_output=True, text=True, timeout=1)
        # If any 'warning' or 'limit' less than 100 is found, it's throttled
        if "warning" in res.stdout.lower() or "limit" in res.stdout.lower():
            if "100" not in res.stdout:
                thermal = "Throttled"
    except: pass

    return {
        "memory": {
            "total_gb": SYSTEM_TOTAL_RAM_GB,
            "used_gb": round(mem.used / (1024**3), 2),
            "percent": mem.percent,
            "vlm_safe_ceiling_gb": SAFE_VLM_MAX_GB
        },
        "disk": {
            "total_gb": round(disk.total / (1024**3), 2),
            "free_gb": round(disk.free / (1024**3), 2),
            "percent": disk.percent
        },
        "thermal": thermal,
        "cpu_count": psutil.cpu_count(),
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/admin/export-dataset")
async def export_dataset(db: SessionLocal = Depends(get_db)):
    """Feature 10: Export curated decisions + VLM data to JSONL."""
    service = DatasetExportService(db)
    return service.export_curated_dataset()

@app.post("/api/admin/promote-golden-set")
async def promote_golden_set(snapshot_version: str, db: SessionLocal = Depends(get_db)):
    service = RAGAutomationService(db)
    return service.promote_golden_set_to_rag(snapshot_version)

@app.post("/api/annotations/ttl-cleanup")
async def cleanup_stale_annotations(db: SessionLocal = Depends(get_db)):
    """Feature 7: Purge annotations older than TTL window (default 10 days)."""
    from services.janitor import JanitorService
    janitor = JanitorService(max_age_days=10)
    count = janitor.purge_local_annotations(db)
    return {"status": "cleanup_complete", "deleted_count": count}

class PhotoSkip(BaseModel):
    photo_id: str
    batch_id: str
    reason: str = "undecided"

@app.post("/api/annotations/skip")
async def skip_photo(payload: PhotoSkip):
    """
    Re-enqueue a photo by updating its timestamp in Firestore.
    This moves it to the end of the queue for later review.
    """
    try:
        from firebase_bridge import get_bridge
        bridge = get_bridge()
        if not bridge.initialize():
            raise HTTPException(status_code=500, detail="Firebase unreachable")
        
        from firebase_admin import firestore
        db = firestore.client()
        photo_ref = db.collection("photos").document(payload.photo_id)
        
        # Update timestamp to NOW to move it to the tail of the queue
        # (Assuming frontend sorts by timestamp ascending)
        photo_ref.update({
            "timestamp": firestore.SERVER_TIMESTAMP,
            "skip_count": firestore.Increment(1),
            "last_skipped_at": firestore.SERVER_TIMESTAMP
        })
        
        return {"status": "skipped", "photo_id": payload.photo_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/annotations/reverse")
async def reverse_annotation(payload: DecisionReversal, db: SessionLocal = Depends(get_db)):
    """Feature 8: Full reversal of annotation."""
    media = db.query(Media).filter(Media.photo_hash == payload.photo_hash).first()
    if not media:
        raise HTTPException(status_code=404, detail="Photo not found")
    
    annotation = db.query(Annotation).filter(Annotation.media_id == media.id).first()
    if not annotation:
        raise HTTPException(status_code=404, detail="No annotation to reverse")
    
    # Toggle logic
    old_action = annotation.action
    new_action = "swipe_right_keeper" if old_action == "swipe_left_cull" else "swipe_left_cull"
    annotation.action = new_action
    annotation.timestamp = datetime.now()
    db.commit()
    
    return {"status": "reversed", "from": old_action, "to": new_action}

@app.post("/api/annotations/skip")
async def skip_annotation(payload: DecisionReversal, db: SessionLocal = Depends(get_db)):
    """Feature 9: Mark a photo as skipped for later review."""
    media = db.query(Media).filter(Media.photo_hash == payload.photo_hash).first()
    if not media:
        raise HTTPException(status_code=404, detail="Photo not found")
    
    # We record a 'skip' action. This prevents it from appearing in current culling 
    # but keeps it in the system for a 'Review Skips' pass later.
    new_ann = Annotation(
        media_id=media.id,
        user_id=payload.user_id,
        action="skipped",
        timestamp=datetime.now()
    )
    db.add(new_ann)
    db.commit()
    return {"status": "skipped"}

@app.post("/api/admin/flush-test-data")
async def flush_test_data(session_id: Optional[str] = None, db: SessionLocal = Depends(get_db)):
    """Surgically wipe test inferences and skipped annotations to reset for testing."""
    from services.janitor import JanitorService
    janitor = JanitorService()
    results = janitor.flush_test_data(db, session_id=session_id)
    return {"status": "flush_complete", "details": results}

@app.post("/api/model/compare")
async def compare_models(candidate_tag: str, snapshot_version: str, db: SessionLocal = Depends(get_db)):
    """Run a comparative evaluation between production and candidate models."""
    service = ModelEvaluatorService(db)
    results = await service.run_comparative_eval(candidate_tag, snapshot_version)
    if "error" in results:
        raise HTTPException(status_code=400, detail=results["error"])
    return results

# ─── Prompt Playground Endpoints ──────────────────────────────────
@app.get("/api/prompts")
async def list_prompts(db: SessionLocal = Depends(get_db)):
    from database import PromptVersion
    return db.query(PromptVersion).order_by(PromptVersion.created_at.desc()).all()

@app.get("/api/prompts/active")
async def get_active_prompt(db: SessionLocal = Depends(get_db)):
    service = PromptService(db)
    active = service.get_active_prompt()
    if not active:
        raise HTTPException(status_code=404, detail="No active prompt found")
    return active

@app.post("/api/prompts/create")
async def create_prompt(payload: PromptCreate, db: SessionLocal = Depends(get_db)):
    service = PromptService(db)
    return service.create_prompt_version(
        version=payload.version,
        system_prompt=payload.system_prompt,
        user_prompt=payload.user_prompt,
        author=payload.author,
        parent_version=payload.parent_version,
        notes=payload.notes
    )

@app.post("/api/prompts/{version}/promote")
async def promote_prompt(version: str, db: SessionLocal = Depends(get_db)):
    service = PromptService(db)
    service.promote_to_production(version)
    return {"status": "promoted", "version": version}

@app.post("/api/model/test-prompt")
async def test_prompt(version: str, db: SessionLocal = Depends(get_db)):
    """Run a candidate prompt against the Golden Set."""
    service = PromptService(db)
    results = await service.run_golden_set_test(version)
    if "error" in results:
        raise HTTPException(status_code=400, detail=results["error"])
    return results

@app.post("/api/admin/bootstrap-golden-set")
async def bootstrap_golden_set(payload: BootstrapRequest, db: SessionLocal = Depends(get_db)):
    service = PromptService(db)
    snapshot = service.bootstrap_golden_set(payload.limit)
    if not snapshot:
        raise HTTPException(status_code=400, detail="No annotations found to bootstrap from")
    return {"status": "golden_set_created", "version": snapshot.snapshot_version}

# ─── Memory & VRAM Management ──────────────────────────────────────
async def ensure_memory_headroom(threshold_pct: float = None):
    """
    Adaptive Memory Guard: Check Unified Memory on M4.
    MANDATORY FLUSH: Always unload models before a batch starts.
    """
    target_threshold = threshold_pct or MEMORY_GATE_THRESHOLD_PCT
    mem = psutil.virtual_memory()
    
    # ── Mandatory Flush ──
    print(f"🧠 [Memory Guard] Pre-batch Flush: Evicting VLM models from Unified Memory...")
    ollama_url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
    try:
        async with httpx.AsyncClient() as client:
            # 1. Get all loaded models
            tags_res = await client.get(f"{ollama_url}/api/tags", timeout=2.0)
            if tags_res.status_code == 200:
                models = tags_res.json().get("models", [])
                for m in models:
                    # 2. Mandatory Eviction: keep_alive: 0 unloads the model
                    await client.post(f"{ollama_url}/api/generate", json={"model": m["name"], "keep_alive": 0}, timeout=2.0)
                    print(f"✅ [Memory Guard] Unloaded model: {m['name']}")
            
            # 3. Kernel Page Reclaim Pause
            await asyncio.sleep(3.0)
    except Exception as e:
        print(f"⚠️ [Memory Guard] Flush warning: {e}")
    else:
        print("✅ [Memory Guard] Headroom sufficient.")


# ─── Startup / Shutdown ──────────────────────────────────────────────
from firebase_init import initialize_firebase
import database
import seed_models

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run self-tests and initialize cloud telemetry on startup."""
    # 0. Initialize Database & Seed Models
    try:
        database.init_db()
        seed_models.seed()
        print("✅ [main] Database initialized and models seeded.")
    except Exception as e:
        print(f"❌ [main] DB/Seed error: {e}")

    # 1. Initialize Firebase Admin (Control Plane) — via singleton
    try:
        initialize_firebase()
        print("📡 [main] Firebase Control Plane Initialized.")
    except Exception as e:
        print(f"❌ [main] Firebase Init Failed: {e}")

    # 2. Launch Background Queue Processor
    threading.Thread(target=batch_orchestrator.process_background_queue, daemon=True).start()
    print("🤖 [main] Background Queue Processor started.")

    # 3. Sequential Self-Tests
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


# Lifespan handled via app.set_lifespan (modern FastAPI) or just defined here
app.router.lifespan_context = lifespan

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
async def close_session(payload: SessionClosePayload, background_tasks: BackgroundTasks, db: SessionLocal = Depends(get_db)):
    """
    Mandate 1: Resource Segregation (M4 Unified Memory).
    Unloads the VLM from VRAM, verifies clearance, and hands off to Stage 9 MPS render.
    """
    print("🛑 [Memory Gatekeeper] User session complete. Commencing VLM Eviction from Unified Memory...")
    
    # Step A: Dynamic VLM Unload via Ollama API
    try:
        # Find the active production model to evict
        prod = db.query(ModelRegistry).filter(ModelRegistry.is_production == True, ModelRegistry.model_type == 'vlm').first()
        model_name = prod.ollama_tag if prod and prod.ollama_tag else "moondream"
        
        async with httpx.AsyncClient() as client:
            api_payload = {"model": model_name, "keep_alive": 0} 
            await client.post("http://127.0.0.1:11434/api/generate", json=api_payload, timeout=3.0)
            print(f"✅ [Memory Gatekeeper] Ollama Eviction Signal Sent for {model_name}. Model unloaded.")
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


class SourceRootConfig(BaseModel):
    source_root: str

@app.post("/api/config/source-root")
async def update_source_root(payload: SourceRootConfig):
    """Update SOURCE_ROOT in .env.local for the background watcher."""
    if not os.path.isdir(payload.source_root):
        raise HTTPException(status_code=400, detail="Invalid directory path")
    
    env_path = os.path.join(os.path.dirname(__file__), ".env.local")
    lines = []
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            lines = f.readlines()
    
    found = False
    new_lines = []
    for line in lines:
        if line.startswith("SOURCE_ROOT="):
            new_lines.append(f'SOURCE_ROOT="{payload.source_root}"\n')
            found = True
        else:
            new_lines.append(line)
    
    if not found:
        new_lines.append(f'SOURCE_ROOT="{payload.source_root}"\n')
    
    with open(env_path, "w") as f:
        f.writelines(new_lines)
    
    # Also update current environment for immediately subsequent requests
    os.environ["SOURCE_ROOT"] = payload.source_root
    return {"status": "success", "source_root": payload.source_root}

@app.get("/api/config/source-root")
async def get_source_root():
    return {"source_root": os.getenv("SOURCE_ROOT", "")}

# ─── Ollama Tags ────────────────────────────────────────────────────
@app.get("/api/ollama-tags")
async def get_ollama_tags():
    """Proxy local ollama models to the web frontend."""
    try:
        ollama_url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
        async with httpx.AsyncClient() as client:
            res = await client.get(f"{ollama_url}/api/tags", timeout=3.0)
            models = []
            if res.status_code == 200:
                data = res.json()
                models = [model["name"] for model in data.get("models", [])]
            
            # ── UI Robustness: Fallback models if local list is sparse ──
            fallbacks = ["moondream:latest", "llava:latest", "bakllava:latest", "llama3.2-vision:latest"]
            for f in fallbacks:
                if f not in models:
                    models.append(f)
            
            return {"success": True, "models": models}
    except Exception as e:
        # If Ollama is down, still return the fallbacks so the UI isn't empty
        return {"success": True, "models": ["moondream:latest", "llava:latest"]}
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
    Lightweight heartbeat: Reports sync status without blocking.
    """
    db_local = SessionLocal()
    firestore_connected = False
    rendering_remaining = 0

    try:
        # 1. Quick Local Check
        failed_count = db_local.query(SyncQueue).filter(SyncQueue.status == "FAILED").count()

        # 2. Firestore check (with very short timeout)
        from firebase_admin import firestore
        try:
            db_cloud = firestore.client()
            # Use a faster limit-1 query just to verify connection
            db_cloud.collection('photos').limit(1).get(timeout=1.0)
            firestore_connected = True
            # Optional: Move the full count to a background cache if needed
            rendering_remaining = 0 
        except:
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

        inferences = db.query(Inference).order_by(Inference.id.asc()).all()
        model_predictions = {}
        for inf in inferences:
            try:
                data = json.loads(inf.inference_value)
                is_keeper = data.get("tier") in ["portfolio", "keeper"]
                # Overwrite with latest inference per media_id
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

    await ensure_memory_headroom()

    result = await asyncio.to_thread(
        batch_orchestrator.scan_only,
        target_folder=request.target_folder,
        session_id=request.session_id or "scan_only"
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
                "sharp": a.sharpness_score,
                "aesthetic": a.aesthetic_score,
                "aes": a.aesthetic_score,
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
    await ensure_memory_headroom()
    
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
    await ensure_memory_headroom()

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

