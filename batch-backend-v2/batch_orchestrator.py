"""
Antigravity Engine v2.1 — Module 7: Batch Orchestrator
The pipeline controller that wires all modules together with real-time SSE streaming.
"""
from __future__ import annotations
import os
import shutil
import time
import hashlib
import json
from pathlib import Path
from typing import Any, Generator

from models import (
    ImageAssessment, BatchResult, QualityScore, Tier, TIER_CONFIG,
    IMAGE_EXTENSIONS, NEEDS_CONVERSION, get_format_type,
    SelfTestResult, ENHANCEMENT_PROFILE_MASTER, ENHANCEMENT_PROFILE_RLHF
)

import preview_extractor
import quality_classifier
import raw_developer
import image_enhancer
import file_tagger
import ai_coach
from database import SessionLocal, Media, Inference, ModelRegistry
from firebase_bridge import FirebaseBridge
from diversity_sampler import DiversitySampler

# ─── Abort Registry ──────────────────────────────────────────────────
ABORT_REGISTRY: set[str] = set()

def _yield_log(msg: str, type: str = "info", data: Any = None):
    return json.dumps({
        "type": type,
        "message": msg,
        "data": data,
        "timestamp": time.time()
    }) + "\n"

# ─── Streaming Batch Processing ──────────────────────────────────────
def stream_batch(
    target_folder: str,
    benchmark_folder: str | None = None,
    session_id: str = "default"
) -> Generator[str, None, None]:
    batch_start = time.time()
    rollback_files = []
    rollback_media_ids = []
    rollback_inference_ids = []
    assessments: list[ImageAssessment] = []

    db = SessionLocal()
    try:
        # 1. Setup
        enhanced_dir = os.path.join(target_folder, "Enhanced")
        rejected_dir = os.path.join(target_folder, "Rejected")
        rlhf_input_dir = os.path.join(target_folder, "For RLHF input")
        workspace_dir = os.path.join(target_folder, ".antigravity_workspace")
        for d in [enhanced_dir, rejected_dir, rlhf_input_dir, workspace_dir]:
            os.makedirs(d, exist_ok=True)

        # 2. Scan
        yield _yield_log("Scanning directory...", "sys")
        groups: dict[str, list[str]] = {}
        all_raw_files = sorted(os.listdir(target_folder))
        for f in all_raw_files:
            if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS:
                stem = Path(f).stem
                if stem not in groups: groups[stem] = []
                groups[stem].append(f)

        total_files = sum(len(files) for files in groups.values())
        stems = sorted(groups.keys())
        yield _yield_log(f"Found {total_files} images in {len(stems)} groups.", "sys")

        model_name = "laplacian_v2"
        model_record = db.query(ModelRegistry).filter(ModelRegistry.name == model_name).first()
        if not model_record:
            model_record = ModelRegistry(name=model_name, model_type="heuristics", is_production=True)
            db.add(model_record)
            db.commit()

        processed_count = 0
        result = BatchResult(total_scanned=total_files)

        # 3. Process
        for stem in stems:
            if session_id in ABORT_REGISTRY:
                yield from _execute_rollback(session_id, rollback_files, rollback_media_ids, rollback_inference_ids, db)
                return

            group_files = groups[stem]
            group_results = []
            for filename in group_files:
                filepath = os.path.join(target_folder, filename)
                try:
                    exif = preview_extractor.extract_metadata(filepath)
                    preview_bytes = preview_extractor.extract_preview(filepath)
                    if not preview_bytes: continue
                    quality = quality_classifier.classify(preview_bytes, exif=exif)
                    group_results.append({
                        "filename": filename, "filepath": filepath, "exif": exif, 
                        "quality": quality, "format": get_format_type(filepath)
                    })
                except Exception as e:
                    yield _yield_log(f"Error assessing {filename}: {e}", "error")

            if not group_results: continue
            
            # Reconciliation
            max_tier = Tier.CULL
            for res in group_results:
                if res["quality"].tier.rank > max_tier.rank:
                    max_tier = res["quality"].tier
            
            raw_master = next((res for res in group_results if res["format"] == "RAW"), None)

            # Execution
            for res in group_results:
                processed_count += 1
                quality = res["quality"]
                quality.tier = max_tier
                
                yield _yield_log(f"Processing {res['filename']} as {max_tier.value}", "progress", {
                    "count": processed_count, "total": total_files, "tier": max_tier.value,
                    "sharpness": quality.sharpness, "aesthetic": quality.aesthetic
                })

                try:
                    file_hash = hashlib.sha256(f"{res['filename']}_{os.path.getsize(res['filepath'])}".encode()).hexdigest()
                    media_record = db.query(Media).filter(Media.photo_hash == file_hash).first()
                    if not media_record:
                        media_record = Media(photo_hash=file_hash, file_path=res['filepath'], format=res['format'])
                        db.add(media_record); db.commit()
                        rollback_media_ids.append(media_record.id)

                    enhanced_path = ""
                    if max_tier != Tier.CULL:
                        is_best = (raw_master and res == raw_master) or (not raw_master)
                        if is_best:
                            rlhf_p = os.path.join(rlhf_input_dir, f"{stem}_rlhf.jpg")
                            _enhance_file(res['filepath'], res['filename'], res['format'], res['exif'].get("ISO",0), rlhf_p, workspace_dir, result, ENHANCEMENT_PROFILE_RLHF)
                            rollback_files.append(rlhf_p)
                            
                            enhanced_path = os.path.join(enhanced_dir, f"{stem}_master.jpg")
                            _enhance_file(res['filepath'], res['filename'], res['format'], res['exif'].get("ISO",0), enhanced_path, workspace_dir, result, ENHANCEMENT_PROFILE_MASTER)
                            rollback_files.append(enhanced_path)
                            media_record.enhanced_path = enhanced_path; db.commit()

                    inf = Inference(media_id=media_record.id, model_id=model_record.id, 
                                   inference_value=json.dumps({"tier": max_tier.value, "sharpness": quality.sharpness}))
                    db.add(inf); db.commit()
                    rollback_inference_ids.append(inf.id)

                    file_tagger.tag_photo(res['filepath'], max_tier, score=quality.composite, reasoning=f"SSE Stream {max_tier.value}")
                    rollback_files.append(os.path.join(target_folder, f"{stem}.xmp"))

                    # Collect for final report
                    assessments.append(ai_coach.assess_image(res['filename'], res['filepath'], res['format'], quality, res['exif'], enhanced_path))

                except Exception as e:
                    yield _yield_log(f"Failure in {res['filename']}: {e}", "error")

        # 4. Wrap up
        yield _yield_log("Compiling reports and sampler...", "sys")
        batch_time = time.time() - batch_start
        report_path = os.path.join(target_folder, "batch_report.json")
        coaching = ai_coach.compile_batch_report(assessments, batch_time)
        ai_coach.save_report_json(assessments, report_path, coaching, batch_time)
        
        # Diversity Sample for RLHF
        sampler = DiversitySampler(target_batch_size=50)
        rlhf_batch = sampler.curate_rlhf_batch(assessments)
        if rlhf_batch:
            bridge = FirebaseBridge("firebase-service-account.json", "style-matcher-9480d.firebasestorage.app")
            if bridge.initialize():
                bridge.upload_rlhf_batch(f"stream_{int(time.time())}", rlhf_batch)
                yield _yield_log(f"Uploaded {len(rlhf_batch)} samples to Firebase Cloud for global swipe.", "sys")

        shutil.rmtree(workspace_dir, ignore_errors=True)
        yield _yield_log("Batch Complete.", "done", {
            "total": result.total_scanned, "keepers": result.keepers, "portfolio": result.portfolio, 
            "culled": result.culled, "processing_time": round(batch_time, 1)
        })

    finally:
        db.close()

def _execute_rollback(session_id, files, media_ids, inf_ids, db):
    yield _yield_log("🚨 ABORT REQUESTED. Rolling back...", "warn")
    ABORT_REGISTRY.discard(session_id)
    for f in files:
        if os.path.exists(f): os.remove(f); yield _yield_log(f"Deleted {os.path.basename(f)}", "revert")
    for i in inf_ids: db.query(Inference).filter(Inference.id == i).delete(); yield _yield_log(f"Purged inf {i}", "revert")
    for m in media_ids: db.query(Media).filter(Media.id == m).delete(); yield _yield_log(f"Purged media {m}", "revert")
    db.commit()
    yield _yield_log("✅ Terminated.", "sys")

def _enhance_file(filepath, filename, format_type, iso, eth_path, workspace, result, profile):
    stem = Path(filename).stem
    if format_type == "RAW":
        dev_p = os.path.join(workspace, f"{stem}_dev.jpg")
        if raw_developer.develop(filepath, dev_p):
            image_enhancer.enhance(dev_p, eth_path, iso=iso)
            result.enhanced += 1
            if os.path.exists(dev_p): os.unlink(dev_p)
    else:
        image_enhancer.enhance(filepath, eth_path, iso=iso)
        result.enhanced += 1
    return eth_path

def run_all_self_tests() -> dict[str, SelfTestResult]:
    modules = {
        "preview_extractor": preview_extractor.self_test,
        "quality_classifier": quality_classifier.self_test,
        "raw_developer": raw_developer.self_test,
        "image_enhancer": image_enhancer.self_test,
        "file_tagger": file_tagger.self_test,
        "ai_coach": ai_coach.self_test,
    }
    results = {}
    for name, test_fn in modules.items():
        try: results[name] = test_fn()
        except Exception as e: results[name] = SelfTestResult(module=name, passed=False, message=str(e))
    return results

def scan_only(target_folder: str) -> BatchResult:
    # Legacy sync wrapper for health checks if needed
    return BatchResult()
