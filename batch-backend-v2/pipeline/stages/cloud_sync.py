"""
Antigravity Engine v2.1 — Stage 6: Cloud Sync
Doppler manifest generation, Firebase push, and final telemetry emission.

Extracted from batch_orchestrator.py L358–L452 (Stage 7: Compilation).
Also contains the generate_doppler_manifest() function (L462–L517).
"""
from __future__ import annotations

import os
import json
import time
import random
from typing import Generator

from pipeline.base import ProcessingStage, yield_log
from pipeline.context import PipelineContext
from models import Tier
from firebase_bridge import FirebaseBridge

import ai_coach


class CloudSyncStage(ProcessingStage):
    """
    Stage 6: Compile results, generate Doppler manifest, and push to cloud.

    Responsibilities:
    1. Compile AI Coaching batch report
    2. Generate fatigue-optimized 70/30 Doppler manifest
    3. Initialize FirebaseBridge and push manifest to Firestore
    4. Emit the final "done" SSE event with batch metrics
    """

    @property
    def name(self) -> str:
        return "Cloud Sync"

    @property
    def is_global(self) -> bool:
        return True

    def execute(self, ctx: PipelineContext) -> Generator[str, None, None]:
        # ── Abort guard (final check) ────────────────────────────────
        if ctx.session_id in ctx.abort_registry:
            return

        batch_time = time.time() - ctx.batch_start
        ctx.result.processing_time = round(batch_time, 1)
        ctx.result.files = ctx.assessments

        # ── Compile batch report ─────────────────────────────────────
        yield yield_log("Compiling AI Coaching Batch Report...", "sys")
        coaching = ai_coach.compile_batch_report(ctx.assessments, batch_time)
        ctx.result.batch_coaching = coaching

        # ── Mandate 4: Doppler Manifest ──────────────────────────────
        yield yield_log(
            "Generating fatigue-optimized Doppler manifest...", "sys"
        )

        portfolio = [
            a for a in ctx.assessments if a.tier == Tier.PORTFOLIO.value
        ]
        amber = [
            a
            for a in ctx.assessments
            if a.tier in [Tier.KEEPER.value, Tier.REVIEW.value]
        ]
        cull = [a for a in ctx.assessments if a.tier == Tier.CULL.value]

        manifest_dir = os.path.dirname(os.path.dirname(__file__))
        manifest_path, manifest_data = generate_doppler_manifest(
            portfolio, amber, cull, manifest_dir
        )
        yield yield_log(
            "Local Doppler manifest live at /api/batch-queue", "sys"
        )

        # ── Cloud Plane Handshake ────────────────────────────────────
        yield yield_log("⚓ Initiating Cloud Plane Handshake...", "sys")

        backend_dir = os.path.dirname(os.path.dirname(__file__))
        service_account = os.path.join(
            backend_dir, "firebase-service-account.json"
        )
        bridge = FirebaseBridge(
            service_account, "style-matcher-9480d.firebasestorage.app"
        )

        if bridge.initialize():
            batch_id = f"batch_{ctx.session_id}_{int(time.time())}"

            # Serialize ImageAssessment → dict for Firestore
            manifest_photos = []
            for p in manifest_data["photos"]:
                coaching_dict = {}
                if hasattr(p, "coaching") and p.coaching:
                    coaching_obj = p.coaching
                    coaching_dict = {
                        "exposure_triangle": getattr(
                            coaching_obj, "exposure_triangle", ""
                        ),
                        "composition": getattr(coaching_obj, "composition", ""),
                        "artistic": getattr(coaching_obj, "artistic", ""),
                        "improvement_priority": getattr(
                            coaching_obj, "improvement_priority", ""
                        ),
                    }
                manifest_photos.append({
                    # ── Identity ────────────────────────────────────
                    "filename": p.filename,
                    "filepath": p.filepath,
                    "enhanced_path": p.enhanced_path,
                    "rlhf_path": p.rlhf_path,
                    # ── AI Scores ───────────────────────────────────
                    "composite_score": p.composite_score,
                    "sharpness_score": p.sharpness_score,
                    "aesthetic_score": p.aesthetic_score,
                    "exposure_score": p.exposure_score,
                    # ── Classification ──────────────────────────────
                    "tier": p.tier,
                    "genre": getattr(p, "genre", "general") or "general",
                    # ── AI Coach ────────────────────────────────────
                    "reasoning": getattr(p, "reasoning", ""),
                    "coaching": coaching_dict,
                    "prompt_version": (
                        getattr(p, "prompt_version", "v1.0") or "v1.0"
                    ),
                    # ── EXIF ────────────────────────────────────────
                    "exif": p.exif if isinstance(p.exif, dict) else {},
                })

            yield yield_log(
                f"Syncing {len(manifest_photos)} photos to cloud plane...",
                "sys",
            )
            if bridge.push_doppler_manifest(batch_id, manifest_photos):
                yield yield_log(
                    f"✅ Cloud Manifest Sync Complete. Batch ID: {batch_id}",
                    "sys",
                )
            else:
                yield yield_log(
                    "⚠️ Cloud Sync Failed. UI may remain blind.", "error"
                )
        else:
            yield yield_log(
                f"⚠️ Firebase Bridge failed (Creds check: {service_account})",
                "error",
            )

        # ── Final "done" event ───────────────────────────────────────
        yield yield_log(
            f"Batch Complete. ({len(ctx.assessments)} photos assessed)",
            "done",
            {
                "total_scanned": ctx.result.total_scanned,
                "portfolio": ctx.result.portfolio,
                "keepers": ctx.result.keepers,
                "review": ctx.result.review,
                "culled": ctx.result.culled,
                "recoverable": ctx.result.recoverable,
                "enhanced": ctx.result.enhanced,
                "denoised": ctx.result.denoised,
                "processing_time": ctx.result.processing_time,
            },
        )


# ─── Doppler Manifest Generator ─────────────────────────────────────
# Extracted from batch_orchestrator.py L462-L517.
# Preserved as a module-level function for backward-compat re-export.

def generate_doppler_manifest(
    portfolio_list: list,
    amber_list: list,
    cull_list: list,
    output_dir: str,
) -> tuple[str, dict]:
    """
    Mandate 4: Psychological Load Balancer (The 70/30 Dopamine Loop)
    Interleaves known winners (Portfolio) with likely losers (Amber/Cull)
    in a strict 70/30 (7 accepts to 3 rejects) ratio, with stochastic
    jitter to avoid UI fatigue.
    """
    accepts = list(portfolio_list)
    rejects = list(amber_list) + list(cull_list)

    # Pre-shuffle to avoid clustering identical consecutive traits
    random.shuffle(accepts)
    random.shuffle(rejects)

    interleaved_queue = []

    while accepts or rejects:
        chunk_accepts = min(len(accepts), 7)
        chunk_rejects = min(len(rejects), 3)

        chunk = []
        for _ in range(chunk_accepts):
            chunk.append(accepts.pop(0))
        for _ in range(chunk_rejects):
            chunk.append(rejects.pop(0))

        # Jitter: Stochastic shuffle within the 10-item micro-batch
        random.shuffle(chunk)
        interleaved_queue.extend(chunk)

    # Edge Case: Fallback if mathematical parity is broken
    if accepts:
        print(
            f"⚠️ Doppler Warning: 70/30 ratio broken. "
            f"Appended {len(accepts)} remaining accepts."
        )
        interleaved_queue.extend(accepts)
    if rejects:
        print(
            f"⚠️ Doppler Warning: 70/30 ratio broken. "
            f"Appended {len(rejects)} remaining rejects."
        )
        interleaved_queue.extend(rejects)

    manifest_path = os.path.join(output_dir, "batch_queue.json")
    temp_path = f"{manifest_path}.tmp"

    manifest_data = {
        "generated_at": time.time(),
        "total_items": len(interleaved_queue),
        "photos": interleaved_queue,
    }

    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)
        os.replace(temp_path, manifest_path)
    except Exception as e:
        print(f"❌ Failed to atomically write Doppler manifest: {e}")
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    return manifest_path, manifest_data
