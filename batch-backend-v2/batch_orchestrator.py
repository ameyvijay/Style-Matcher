"""
Antigravity Engine v2.1 — Module 7: Batch Orchestrator (Façade)
Thin wrapper over the pipeline package for backward compatibility.

Key Design:
- stream_batch() delegates to Pipeline.run() with 6 modular stages
- scan_only() reuses DiscoveryStage + AssessmentStage (Gemini refinement #3)
- All public symbols (ABORT_REGISTRY, stream_batch, scan_only,
  run_all_self_tests, generate_doppler_manifest) remain importable
  from this module — main.py requires ZERO changes.
"""
from __future__ import annotations

import time
from typing import Any, Generator, Set

# Import models & constants (preserved for any external consumers)
from models import (
    ImageAssessment, BatchResult,
    QualityScore, Tier, TIER_CONFIG,
    IMAGE_EXTENSIONS, get_format_type,
    SelfTestResult, ENHANCEMENT_PROFILE_MASTER, ENHANCEMENT_PROFILE_RLHF
)

# Pipeline imports
from pipeline import Pipeline, PipelineContext
from pipeline.stages.discovery import DiscoveryStage
from pipeline.stages.assessment import AssessmentStage
from pipeline.stages.enhancement import EnhancementStage
from pipeline.stages.embedding import EmbeddingStage
from pipeline.stages.coaching import CoachingStage
from pipeline.stages.cloud_sync import CloudSyncStage, generate_doppler_manifest

# Module imports for scan_only and self_tests
import preview_extractor
import quality_classifier
import raw_developer
import image_enhancer
import file_tagger
import ai_coach
from database import SessionLocal, Media, Inference, ModelRegistry

# ─── Global State ──────────────────────────────────────────────────
# Thread-safe registry for active sessions that should be aborted
ABORT_REGISTRY: Set[str] = set()


# ─── Main Batch Processing (Streaming Generator) ───────────────────

def stream_batch(
    target_folder: str,
    benchmark_folder: str | None = None,
    session_id: str = "default",
    priority: str = "foreground",
    force_reprocess: bool = False
) -> Generator[str, None, None]:
    """
    Executes the full 8-stage pipeline and yields real-time progress events.
    priority: 'foreground' (full speed) or 'background' (throttled).
    """
    pipeline = Pipeline(
        stages=[
            DiscoveryStage(),
            AssessmentStage(),
            EnhancementStage(),
            EmbeddingStage(),
            CoachingStage(),
            CloudSyncStage(),
        ],
        abort_registry=ABORT_REGISTRY,
    )
    ctx = PipelineContext(
        target_folder=target_folder,
        benchmark_folder=benchmark_folder,
        session_id=session_id,
    )
    ctx.priority = priority # Inject priority into context for stages to consume
    ctx.force_reprocess = force_reprocess
    yield from pipeline.run(ctx)

def process_background_queue():
    """
    Background worker that drains 'batch_queue.json' silently.
    Called by main.py lifespan.
    """
    import os
    import json
    queue_file = os.path.join(os.path.dirname(__file__), "batch_queue.json")

    # 🔄 [Resilience] Reset stuck 'processing' tasks to 'pending' on startup
    if os.path.exists(queue_file):
        try:
            with open(queue_file, "r") as f:
                queue = json.load(f)

            needs_save = False
            for item in queue:
                if item.get('status') == 'processing':
                    print(f"🔄 [Background] Resetting stale task: {item.get('folder')}")
                    item['status'] = 'pending'
                    needs_save = True

            if needs_save:
                with open(queue_file, "w") as f:
                    json.dump(queue, f, indent=4)
        except Exception as e:
            print(f"⚠️ [Background] Startup queue reset failed: {e}")

    while True:
        if not os.path.exists(queue_file):
            time.sleep(10)
            continue
            
        try:
            with open(queue_file, "r") as f:
                queue = json.load(f)
        except:
            time.sleep(10)
            continue
            
        pending = [item for item in queue if item['status'] == 'pending']
        if not pending:
            time.sleep(10)
            continue
            
        # Process the oldest item
        task = pending[0]
        task['status'] = 'processing'
        with open(queue_file, "w") as f:
            json.dump(queue, f, indent=4)
            
        print(f"🤖 [Background] Starting silent batch: {task['folder']}")
        
        # Drain the generator silently
        try:
            for _ in stream_batch(
                target_folder=task['folder'],
                session_id=f"silent_{int(time.time())}",
                priority="background"
            ):
                pass
            task['status'] = 'completed'

            # 🔔 Notify via Firebase
            try:
                from firebase_bridge import get_bridge
                bridge = get_bridge()
                bridge.send_push_notification(
                    title="Batch Complete",
                    body=f"Background processing for '{os.path.basename(task['folder'])}' is finished.",
                    data={"type": "batch_done", "folder": task['folder']}
                )
            except:
                pass
        except Exception as e:
            print(f"❌ [Background] Failed: {e}")
            task['status'] = 'failed'
            task['error'] = str(e)
            
        with open(queue_file, "w") as f:
            json.dump(queue, f, indent=4)
        
        time.sleep(5) # Cooldown between batches


# ─── Scan Only (Read-Only) — Gemini Refinement #3 ──────────────────
# Reuses DiscoveryStage and AssessmentStage to prevent logic drift
# in tier reconciliation between scanner and full pipeline.

def scan_only(target_folder: str, session_id: str = "scan_only") -> BatchResult:
    """Read-only scan: score all images WITHOUT modifying anything."""
    from pipeline.pipeline_runner import SESSION_REGISTRY
    
    # Register session for Telemetry visibility
    SESSION_REGISTRY[session_id] = {"status": "running", "log_path": None}
    
    batch_start = time.time()
    try:
        # Construct a lightweight context
        ctx = PipelineContext(
            target_folder=target_folder,
            session_id=session_id,
        )
        # Link to global abort registry
        ctx.abort_registry = ABORT_REGISTRY

        db = SessionLocal()
        ctx.db = db
        assessments = []

        # Stage 1: Discovery — reuse the same filesystem scan logic
        from pipeline.stages.discovery import DiscoveryStage
        discovery = DiscoveryStage()
        # Consume the generator to execute discovery
        for _ in discovery.execute(ctx):
            pass  # Discard SSE events in scan-only mode

        if not ctx.stems:
            return BatchResult()

        # Stage 2: Assessment — reuse the same EXIF/quality/tier logic
        from pipeline.stages.assessment import AssessmentStage
        assessment_stage = AssessmentStage()
        for stem_idx, stem in enumerate(ctx.stems, 1):
            ctx.current_stem = stem
            ctx.current_stem_idx = stem_idx
            # Consume generator (discard SSE events)
            for _ in assessment_stage.execute(ctx):
                pass

        # Build result from assessed groups
        result = ctx.result or BatchResult(total_scanned=ctx.total_files)
        
        # The AssessmentStage already populated ctx._assessed_groups with MoE-calculated QualityScores
        for stem, group_results, max_tier, raw_master in ctx._assessed_groups:
            for res in group_results:
                filename = res["filename"]
                quality = res["quality"] # Already MoE-scored in AssessmentStage
                exif = res["exif"]
                
                # Ensure the quality tier reflects the reconciled group tier
                quality.tier = max_tier

                if max_tier == Tier.PORTFOLIO:
                    result.portfolio += 1
                elif max_tier == Tier.KEEPER:
                    result.keepers += 1
                elif max_tier == Tier.REVIEW:
                    result.review += 1
                else:
                    result.culled += 1

                if quality.recovery_potential in ("high", "medium"):
                    result.recoverable += 1

                assessment = ai_coach.assess_image(
                    filename,
                    res["filepath"],
                    res["format_type"],
                    quality,
                    exif,
                    "",      # enhanced_path
                    "",      # rlhf_path
                    False,   # denoising_applied
                    (time.time() - res["start"]),
                )
                assessment.recovery_potential = quality.recovery_potential
                from pipeline.stages.enhancement import _build_recovery_notes
                assessment.recovery_notes = _build_recovery_notes(quality, exif)
                assessments.append(assessment)

        batch_time = time.time() - batch_start
        result.processing_time = round(batch_time, 1)
        result.files = assessments
        result.batch_coaching = ai_coach.compile_batch_report(
            assessments, batch_time
        )
        return result

    finally:
        db.close()
        # Mark as completed in registry for telemetry visibility
        SESSION_REGISTRY[session_id]["status"] = "completed"


# ─── Self-Tests ────────────────────────────────────────────────────

def run_all_self_tests() -> dict[str, SelfTestResult]:
    """Full 6-module diagnostic suite."""
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
        try:
            results[name] = test_fn()
        except Exception as e:
            results[name] = SelfTestResult(
                module=name, passed=False, message=str(e)
            )
    return results
