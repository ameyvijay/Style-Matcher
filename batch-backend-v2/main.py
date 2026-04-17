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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import json
from fastapi.staticfiles import StaticFiles
from models import BatchRequest, BatchResult
import batch_orchestrator
import firebase_bridge
from database import SessionLocal, Media, Inference, Annotation, ModelRegistry


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


# ─── Batch Processing ───────────────────────────────────────────────
@app.post("/api/batch-process")
async def batch_process(request: BatchRequest):
    """
    Run the full batch processing pipeline on a folder.
    Returns structured results with per-file assessments and coaching.
    """
    if not os.path.isdir(request.target_folder):
        return {
            "status": "error",
            "message": f"Folder not found: {request.target_folder}",
        }

    result = batch_orchestrator.run_batch(
        target_folder=request.target_folder,
        benchmark_folder=request.benchmark_folder,
    )

    return {
        "status": "success",
        "metrics": {
            "total_scanned": result.total_scanned,
            "portfolio": result.portfolio,
            "keepers": result.keepers,
            "review": result.review,
            "culled": result.culled,
            "recoverable": result.recoverable,
            "duplicates": result.duplicates,
            "denoised": result.denoised,
            "enhanced": result.enhanced,
            "processing_time": result.processing_time,
        },
        "batch_coaching": result.batch_coaching,
        "assessments": [
            {
                "filename": a.filename,
                "tier": a.tier,
                "score": a.composite_score,
                "sharpness": a.sharpness_score,
                "aesthetic": a.aesthetic_score,
                "exposure": a.exposure_score,
                "reasoning": a.reasoning,
                "flaws": a.technical_flaws,
                "recovery_potential": a.recovery_potential,
                "recovery_notes": a.recovery_notes,
                "enhanced_path": a.enhanced_path,
            }
            for a in result.files
        ],
    }
