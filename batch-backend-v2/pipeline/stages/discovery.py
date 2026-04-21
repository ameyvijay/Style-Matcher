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
        ctx.rlhf_input_dir = os.path.join(ctx.target_folder, "For RLHF input")
        ctx.workspace_dir = os.path.join(
            ctx.target_folder, ".antigravity_workspace"
        )

        for d in [ctx.workspace_dir]:
            os.makedirs(d, exist_ok=True)

        # ── Scan for images ──────────────────────────────────────────
        yield yield_log("Scanning filesystem for RAW/JPEG groups...", "sys")

        groups: dict[str, list[str]] = {}
        all_files = sorted(os.listdir(ctx.target_folder))
        for f in all_files:
            fpath = os.path.join(ctx.target_folder, f)
            if os.path.isfile(fpath) and os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS:
                stem = Path(f).stem
                if stem not in groups:
                    groups[stem] = []
                groups[stem].append(f)

        ctx.groups = groups
        ctx.total_files = sum(len(files) for files in groups.values())
        ctx.stems = sorted(groups.keys())

        print(f"📁 Source: {ctx.target_folder}")
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
