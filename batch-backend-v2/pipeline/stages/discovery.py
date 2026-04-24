"""
Antigravity Engine v2.1 — Stage 1: Discovery
Filesystem scan, directory creation, and model registry initialization.

Extracted from batch_orchestrator.py L78–L131 (Stage 0: Initialization).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

from pipeline.base import ProcessingStage, yield_log
from pipeline.context import PipelineContext
from models import IMAGE_EXTENSIONS, BatchResult
from database import ModelRegistry


class DiscoveryStage(ProcessingStage):
    """
    Stage 1: Discover images and prepare the processing environment.

    Responsibilities:
    - Validate target folder exists
    - Create output directory structure (.antigravity_workspace)
    - Scan filesystem for image groups (stem → file list)
    - Initialize ModelRegistry record for the current model
    - Populate ctx.groups, ctx.stems, ctx.total_files, ctx.result
    """

    @property
    def name(self) -> str:
        return "Discovery"

    @property
    def is_global(self) -> bool:
        return True

    def execute(self, ctx: PipelineContext) -> Generator[str, None, None]:
        # ── Validate target folder ───────────────────────────────────
        if not os.path.isdir(ctx.target_folder):
            print(f"❌ Error: folder not found: {ctx.target_folder}")
            yield yield_log(
                f"Error: folder not found: {ctx.target_folder}", "error"
            )
            return

        # ── Create output directories ────────────────────────────────
        ctx.enhanced_dir = os.path.join(ctx.target_folder, "Enhanced")
        ctx.rejected_dir = os.path.join(ctx.target_folder, "Rejected")
        ctx.rlhf_input_dir = os.path.join(ctx.target_folder, "HiTL")
        ctx.workspace_dir = os.path.join(
            ctx.target_folder, ".antigravity_workspace"
        )

        for d in [ctx.enhanced_dir, ctx.rlhf_input_dir, ctx.workspace_dir]:
            os.makedirs(d, exist_ok=True)

        # ── Scan for images (Recursive) ──────────────────────────────
        yield yield_log("Scanning filesystem for RAW/JPEG groups...", "sys")

        groups: dict[str, list[str]] = {}
        
        # We walk recursively but ignore hidden dirs and our own output folders
        exclude_dirs = {'.antigravity_workspace', 'Enhanced', 'HiTL', 'RLHF', 'logs', 'vector_store'}
        
        for root, dirs, files in os.walk(ctx.target_folder):
            # Prune hidden dirs and known output directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in exclude_dirs]
            
            for f in sorted(files):
                # 🛑 Check for Abort Request
                if ctx.session_id in ctx.abort_registry:
                    return

                if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS:
                    fpath = os.path.join(root, f)
                    rel_fpath = os.path.relpath(fpath, ctx.target_folder)
                    # We use relative path from target_folder as the 'identifier'
                    # but group by stem for RAW+JPEG pairing
                    stem = Path(f).stem
                    if stem not in groups:
                        groups[stem] = []
                    
                    # Store the relative path in the group
                    groups[stem].append(rel_fpath)

        ctx.groups = groups
        ctx.total_files = sum(len(files) for files in groups.values())
        
        # ── Idempotency Check (Resume Logic) ────────────────────────
        from models import ImageAssessment, Tier, get_format_type, QualityScore
        from database import Inference, Media
        import json

        stems_to_process = []
        completed_count = 0

        for stem in sorted(groups.keys()):
            if ctx.force_reprocess:
                stems_to_process.append(stem)
                continue

            # Check if all files in this group have a production inference
            # We look for at least one Inference record linked to one of the group files
            is_completed = False
            try:
                # Find one media in the group
                sample_file = groups[stem][0]
                abs_sample_path = os.path.join(ctx.target_folder, sample_file)
                
                media = ctx.db.query(Media).filter(Media.file_path == abs_sample_path).first()
                if media:
                    inference = ctx.db.query(Inference).filter(Inference.media_id == media.id).first()
                    if inference:
                        is_completed = True
                        
                        # Reconstruct ImageAssessment from DB for CloudSyncStage
                        inf_val = {}
                        if inference.inference_value:
                            try:
                                if inference.inference_value.startswith('{'):
                                    inf_val = json.loads(inference.inference_value)
                                else:
                                    # Handle legacy or simple string inferences
                                    inf_val = {"tier": inference.inference_value}
                            except:
                                inf_val = {"tier": "review"}
                        
                        # Reconstruct EXIF safely
                        exif_data = {}
                        try:
                            # Try to extract EXIF if saved in inf_val or if we want to re-read it
                            exif_data = inf_val.get("exif", {})
                        except:
                            pass

                        assessment = ImageAssessment(
                            filename=os.path.basename(media.file_path),
                            filepath=media.file_path,
                            format=media.format or get_format_type(media.file_path),
                            tier=inf_val.get("tier", "review"),
                            composite_score=inf_val.get("composite_score", 0.0),
                            sharpness_score=inf_val.get("sharpness", 0.0),
                            aesthetic_score=inf_val.get("aesthetic", 0.0),
                            exposure_score=inf_val.get("exposure", 0.0),
                            reasoning=inf_val.get("semantic_description", ""),
                            enhanced_path=media.enhanced_path,
                            rlhf_path=media.proxy_path,
                            exif=exif_data, 
                            prompt_version=inference.prompt_version or "v1.0"
                        )
                        
                        # We append directly to _assessed_groups so AssessmentStage skips it,
                        # but CloudSyncStage sees it.
                        try:
                            tier_obj = Tier[assessment.tier.upper()] if assessment.tier else Tier.REVIEW
                        except:
                            tier_obj = Tier.REVIEW

                        ctx._assessed_groups.append((stem, [], tier_obj, None))
                        ctx.assessments.append(assessment)
                        completed_count += 1

                        # Update summary results for correct "done" report
                        if assessment.tier == Tier.PORTFOLIO.value:
                            ctx.result.portfolio += 1
                        elif assessment.tier == Tier.KEEPER.value:
                            ctx.result.keepers += 1
                        elif assessment.tier == Tier.REVIEW.value:
                            ctx.result.review += 1
                        elif assessment.tier in [Tier.CULL.value, Tier.REJECTED.value]:
                            ctx.result.culled += 1
                        
                        # Re-calculate recoverable for summary
                        if assessment.tier in [Tier.CULL.value, Tier.REJECTED.value]:
                            # Approximation for resume logic
                            if assessment.composite_score > 30:
                                ctx.result.recoverable += 1
            except Exception as e:
                print(f"⚠️ [Discovery] Resume check failed for {stem}: {e}")

            if not is_completed:
                stems_to_process.append(stem)

        ctx.stems = stems_to_process
        ctx.completed_stems = [s for s in groups.keys() if s not in stems_to_process]

        print(f"📁 Source: {ctx.target_folder}")
        if completed_count > 0:
            print(f"♻️  Resuming: {completed_count} groups already processed. {len(ctx.stems)} groups remaining.")
            yield yield_log(f"Resuming: {completed_count} groups already processed. {len(ctx.stems)} groups remaining.", "sys")
        else:
            print(f"🔍 Found {len(ctx.stems)} groups ({ctx.total_files} files) to process.")
            yield yield_log(
                f"Found {len(ctx.stems)} groups ({ctx.total_files} files) to process.",
                "sys",
            )

        # ── Initialize BatchResult ───────────────────────────────────
        ctx.result = BatchResult(total_scanned=ctx.total_files)

        # ── Prep Model Registry ──────────────────────────────────────
        model_record = (
            ctx.db.query(ModelRegistry)
            .filter(ModelRegistry.name == "laplacian_v2")
            .first()
        )
        if not model_record:
            model_record = ModelRegistry(
                name="laplacian_v2", model_type="heuristics", is_production=True
            )
            ctx.db.add(model_record)
            ctx.db.commit()

        ctx.model_record = model_record
        print("=" * 60)
