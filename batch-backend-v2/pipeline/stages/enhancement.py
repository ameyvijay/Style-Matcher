"""
Antigravity Engine v2.1 — Stage 3: Enhancement
RAW development, RLHF/Master image enhancement, XMP tagging, and tier routing.

Extracted from batch_orchestrator.py L207–L271 (Stages 3-6).
Contains the formerly private _enhance_file() and _build_recovery_notes().
"""
from __future__ import annotations

import os
import shutil
import time
import hashlib
from typing import Generator

from pipeline.base import ProcessingStage, yield_log
from pipeline.context import PipelineContext
from models import (
    Tier, ENHANCEMENT_PROFILE_MASTER, ENHANCEMENT_PROFILE_RLHF,
)
from database import Media

import raw_developer
import image_enhancer
import file_tagger


class EnhancementStage(ProcessingStage):
    """
    Stage 3: Enhance, tag, and route images based on tier assignment.

    For each assessed group:
    1. Assign reconciled tier to each file's quality score
    2. Hash file and upsert Media DB record
    3. Route by tier: Portfolio/Keeper → Enhanced + RLHF; Cull → RLHF only
    4. Develop RAW files, apply enhancement profiles, write XMP sidecar
    5. Track created files in ctx.session_files for rollback
    """

    @property
    def name(self) -> str:
        return "Enhancement"

    def execute(self, ctx: PipelineContext) -> Generator[str, None, None]:
        # The PipelineRunner and AssessmentStage have already populated these
        stem = ctx.current_stem
        group_results = ctx.current_group_results
        max_tier = ctx.current_max_tier
        raw_master = ctx.current_raw_master

        if not group_results:
            return

        for res in group_results:
            # 🛑 Check for Abort Request
            if ctx.session_id in ctx.abort_registry:
                return

            ctx.processed_count += 1
            filename, filepath = res["filename"], res["filepath"]
            quality, exif = res["quality"], res["exif"]
            quality.tier = max_tier

            yield yield_log(
                f"Processing image {ctx.processed_count}/{ctx.total_files}: {filename}",
                "progress",
                {
                    "tier": max_tier.value,
                    "sharpness": round(quality.sharpness, 1),
                    "aesthetic": round(quality.aesthetic, 1),
                    "aes": round(quality.aesthetic, 1),
                },
            )
            print(
                f"[{ctx.processed_count}/{ctx.total_files}] {filename} "
                f"({res['format_type']}) → {max_tier.value.upper()} ",
                end="",
                flush=True,
            )

            try:
                # ── MLOps: Hash & DB ─────────────────────────────
                file_hash = hashlib.sha256(
                    f"{filename}_{os.path.getsize(filepath)}".encode()
                ).hexdigest()
                media = (
                    ctx.db.query(Media)
                    .filter(Media.photo_hash == file_hash)
                    .first()
                )
                if not media:
                    media = Media(
                        photo_hash=file_hash,
                        file_path=filepath,
                        format=res["format_type"],
                    )
                    ctx.db.add(media)
                    ctx.db.commit()
                ctx.session_db_ids.append(media.id)

                # ── Tier Routing ─────────────────────────────────
                enhanced_path = ""
                rlhf_path = ""
                recovery_notes = _build_recovery_notes(quality, exif)

                if max_tier in [Tier.CULL, Tier.REJECTED]:
                    if max_tier == Tier.CULL:
                        ctx.result.culled += 1
                        ctx.tier_buckets["culled"] += 1
                    else:
                        # REJECTED counts as culled for stats but stays visible
                        ctx.result.culled += 1
                        ctx.tier_buckets["culled"] += 1
                        
                    if quality.recovery_potential in ("high", "medium"):
                        ctx.result.recoverable += 1
                        ctx.tier_buckets["recoverable"] += 1

                    # Even for Culls, we need a proxy for the 'Second Chance' bin
                    # Ensure stem is clean of path separators
                    clean_stem = os.path.basename(stem)
                    rlhf_path = os.path.join(
                        ctx.rlhf_input_dir, f"{clean_stem}_rlhf.jpg"
                    )
                    _enhance_file(
                        filepath, filename, res["format_type"],
                        exif.get("ISO", 0), rlhf_path,
                        ctx.workspace_dir, ctx.result,
                        ENHANCEMENT_PROFILE_RLHF,
                    )
                    ctx.session_files.append(rlhf_path)
                else:
                    if max_tier == Tier.REVIEW:
                        ctx.result.review += 1
                        ctx.tier_buckets["review"] += 1
                    else:
                        if max_tier == Tier.PORTFOLIO:
                            ctx.result.portfolio += 1
                            ctx.tier_buckets["portfolio"] += 1
                        else:
                            ctx.result.keepers += 1
                            ctx.tier_buckets["keeper"] += 1

                    # 1. RLHF Proxy (Global for all cloud-bound photos)
                    clean_stem = os.path.basename(stem)
                    rlhf_path = os.path.join(
                        ctx.rlhf_input_dir, f"{clean_stem}_rlhf.jpg"
                    )
                    _enhance_file(
                        filepath, filename, res["format_type"],
                        exif.get("ISO", 0), rlhf_path,
                        ctx.workspace_dir, ctx.result,
                        ENHANCEMENT_PROFILE_RLHF,
                    )
                    ctx.session_files.append(rlhf_path)

                    # 2. Master & High-Res Enhancement
                    is_master = (
                        (raw_master and res == raw_master)
                        or (not raw_master)
                    )
                    if is_master:
                        clean_stem = os.path.basename(stem)
                        enhanced_path = os.path.join(
                            ctx.enhanced_dir, f"{clean_stem}_master.jpg"
                        )
                        _enhance_file(
                            filepath, filename, res["format_type"],
                            exif.get("ISO", 0), enhanced_path,
                            ctx.workspace_dir, ctx.result,
                            ENHANCEMENT_PROFILE_MASTER,
                        )
                        ctx.session_files.append(enhanced_path)
                        media.enhanced_path = enhanced_path
                        ctx.db.commit()

                # ── Store per-file metadata for downstream stages ─
                res["media"] = media
                res["enhanced_path"] = enhanced_path
                res["rlhf_path"] = rlhf_path
                res["recovery_notes"] = recovery_notes
                res["max_tier"] = max_tier

            except Exception as e:
                print(f"❌ ERROR: {e}")
                yield yield_log(
                    f"⚠️ Internal error processing {filename}: {str(e)}",
                    "error",
                )


# ─── Private Helpers (extracted from batch_orchestrator) ─────────────

def _enhance_file(
    filepath, filename, format_type, iso, enhanced_path,
    workspace_dir, result, profile,
) -> str:
    """Develop (if RAW) and enhance an image file with the given profile."""
    stem = os.path.splitext(filename)[0]
    if format_type == "RAW":
        developed_path = os.path.join(workspace_dir, f"{stem}_dev.jpg")
        if raw_developer.develop(filepath, developed_path):
            if image_enhancer.enhance(developed_path, enhanced_path, iso=iso):
                result.enhanced += 1
            else:
                shutil.copy2(developed_path, enhanced_path)
                result.enhanced += 1
            if os.path.exists(developed_path):
                os.unlink(developed_path)
            return enhanced_path
    else:
        if image_enhancer.enhance(filepath, enhanced_path, iso=iso):
            result.enhanced += 1
            return enhanced_path
    return ""


def _build_recovery_notes(quality, exif) -> str:
    """Build recovery notes for borderline/culled images."""
    if not quality.recovery_potential:
        return ""
    notes = []
    if quality.exposure < 40:
        notes.append("Underexposed — lift shadows +30, exposure +0.7")
    elif quality.exposure > 85:
        notes.append("Overexposed — recover highlights")
    iso = exif.get("ISO", 0)
    if iso and iso > 3200:
        notes.append(f"High ISO ({iso}) — noise reduction required")
    return "; ".join(notes)
