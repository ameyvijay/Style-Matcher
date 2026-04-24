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
        cull = [
            a for a in ctx.assessments 
            if a.tier in [Tier.CULL.value, Tier.REJECTED.value]
        ]

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
            # Use manifest_data['photos'] which might be dicts now if generate_doppler_manifest was updated
            for p in manifest_data["photos"]:
                # Ensure we handle both objects and dicts for flexibility
                get_attr = lambda obj, key, default="": getattr(obj, key, default) if not isinstance(obj, dict) else obj.get(key, default)
                
                coaching_dict = {}
                p_coaching = get_attr(p, "coaching", None)
                if p_coaching:
                    coaching_dict = {
                        "exposure_triangle": get_attr(p_coaching, "exposure_triangle", ""),
                        "composition": get_attr(p_coaching, "composition", ""),
                        "artistic": get_attr(p_coaching, "artistic", ""),
                        "improvement_priority": get_attr(p_coaching, "improvement_priority", ""),
                    }

                manifest_photos.append({
                    # ── Identity ────────────────────────────────────
                    "filename": get_attr(p, "filename"),
                    "filepath": get_attr(p, "filepath"),
                    "enhanced_path": get_attr(p, "enhanced_path"),
                    "rlhf_path": get_attr(p, "rlhf_path"),
                    # ── AI Scores ───────────────────────────────────
                    "composite_score": get_attr(p, "composite_score", 0.0),
                    "sharpness_score": get_attr(p, "sharpness_score", 0.0),
                    "aesthetic_score": get_attr(p, "aesthetic_score", 0.0),
                    "exposure_score": get_attr(p, "exposure_score", 0.0),
                    # ── Classification ──────────────────────────────
                    "tier": get_attr(p, "tier"),
                    "genre": get_attr(p, "genre", "general") or "general",
                    # ── AI Coach ────────────────────────────────────
                    "reasoning": get_attr(p, "reasoning", ""),
                    "coaching": coaching_dict,
                    "prompt_version": get_attr(p, "prompt_version", "v1.0") or "v1.0",
                    # ── EXIF ────────────────────────────────────────
                    "exif": get_attr(p, "exif", {}),
                })

            yield yield_log(
                f"Syncing {len(manifest_photos)} photos to cloud plane...",
                "sys",
            )
            
            # Use a list to accumulate progress events from the callback
            sync_events = []
            def sync_callback(current, total, filename):
                if current % 10 == 0 or current == total:
                    sync_events.append(yield_log(
                        f"Cloud Handshake: {current}/{total} ({filename})", 
                        "progress"
                    ))

            if bridge.push_doppler_manifest(batch_id, manifest_photos, on_progress=sync_callback):
                # Drain accumulated events
                for event in sync_events:
                    yield event

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
        "photos": [p.to_dict() if hasattr(p, 'to_dict') else p for p in interleaved_queue],
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
