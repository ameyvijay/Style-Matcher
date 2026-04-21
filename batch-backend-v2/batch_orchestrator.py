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
    session_id: str = "default"
) -> Generator[str, None, None]:
    """
    Executes the full 8-stage pipeline and yields real-time progress events.
    Supports atomic rollback if aborted via ABORT_REGISTRY.

    This is now a thin delegate to Pipeline.run() with 6 modular stages.
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
    yield from pipeline.run(ctx)


# ─── Scan Only (Read-Only) — Gemini Refinement #3 ──────────────────
# Reuses DiscoveryStage and AssessmentStage to prevent logic drift
# in tier reconciliation between scanner and full pipeline.

def scan_only(target_folder: str) -> BatchResult:
    """Read-only scan: score all images WITHOUT modifying anything."""
    batch_start = time.time()

    # Construct a lightweight context (no rollback tracking needed)
    ctx = PipelineContext(
        target_folder=target_folder,
        session_id="scan_only",
    )

    db = SessionLocal()
    ctx.db = db

    try:
        # Stage 1: Discovery — reuse the same filesystem scan logic
        discovery = DiscoveryStage()
        # Consume the generator to execute discovery
        for _ in discovery.execute(ctx):
            pass  # Discard SSE events in scan-only mode

        if not ctx.stems:
            return BatchResult()

        # Stage 2: Assessment — reuse the same EXIF/quality/tier logic
        assessment = AssessmentStage()
        for _ in assessment.execute(ctx):
            pass  # Discard SSE events in scan-only mode

        # Build result from assessed groups (no enhancement)
        result = ctx.result or BatchResult(total_scanned=ctx.total_files)
        assessments: list[ImageAssessment] = []
        processed_count = 0

        for stem, group_results, max_tier, raw_master in ctx._assessed_groups:
            for res in group_results:
                processed_count += 1
                filename = res["filename"]
                quality = res["quality"]
                exif = res["exif"]
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
