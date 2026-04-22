"""
Antigravity Engine v2.1 — Stage 5: Coaching
AI Photography Coach assessment and XMP tagging per file.

Extracted from batch_orchestrator.py L334–L355 (AI Coach block).
"""
from __future__ import annotations

import os
import time
from typing import Generator

from pipeline.base import ProcessingStage, yield_log
from pipeline.context import PipelineContext
from models import Tier

import ai_coach
import file_tagger


class CoachingStage(ProcessingStage):
    """
    Stage 5: Generate AI coaching assessments for each processed file.

    For each file in each assessed group:
    1. Write XMP sidecar metadata via file_tagger
    2. Generate per-file AI coaching assessment via ai_coach
    3. Attach recovery metadata and prompt version traceability
    4. Accumulate assessments in ctx.assessments
    """

    @property
    def name(self) -> str:
        return "Coaching"

    def execute(self, ctx: PipelineContext) -> Generator[str, None, None]:
        group_results = ctx.current_group_results
        max_tier = ctx.current_max_tier
        if not group_results:
            return

        for res in group_results:
            # 🛑 Check for Abort Request
            if ctx.session_id in ctx.abort_registry:
                return

            filename = res["filename"]
            filepath = res["filepath"]
            quality = res["quality"]
            exif = res["exif"]
            enhanced_path = res.get("enhanced_path", "")
            rlhf_path = res.get("rlhf_path", "")
            recovery_notes = res.get("recovery_notes", "")
            _prompt_version = res.get("_prompt_version", "v1.0")
            media = res.get("media")

            if media is None:
                continue

            try:
                # ── XMP Tagging ──────────────────────────────────
                xmp_path = os.path.join(
                    ctx.target_folder, f"{os.path.splitext(filename)[0]}.xmp"
                )
                file_tagger.tag_photo(
                    filepath,
                    max_tier,
                    score=quality.composite,
                    sharpness=quality.sharpness,
                    aesthetic=quality.aesthetic,
                    exposure=quality.exposure,
                    reasoning=f"SSE Session: {ctx.session_id}",
                    recovery_potential=quality.recovery_potential,
                    recovery_notes=recovery_notes,
                )
                ctx.session_files.append(xmp_path)

                # ── AI Coach Assessment ──────────────────────────
                denoise = exif.get("ISO", 0) > 1600 and rlhf_path != ""
                if denoise:
                    ctx.result.denoised += 1

                assessment = ai_coach.assess_image(
                    filename,
                    filepath,
                    res["format_type"],
                    quality,
                    exif,
                    enhanced_path,
                    rlhf_path,
                    denoise,
                    (time.time() - res["start"]),
                )
                assessment.recovery_potential = quality.recovery_potential
                assessment.recovery_notes = recovery_notes
                assessment.prompt_version = _prompt_version
                ctx.assessments.append(assessment)
                print(f"[{quality.composite:.0f}%] ✅")

            except Exception as e:
                print(f"❌ ERROR: {e}")
                yield yield_log(
                    f"⚠️ Internal error processing {filename}: {str(e)}",
                    "error",
                )
