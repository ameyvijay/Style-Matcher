"""
Antigravity Engine v2.1 — Stage 2: Assessment
EXIF extraction, CLIP embedding, RAG similarity, quality classification,
and group tier reconciliation.

Extracted from batch_orchestrator.py L134–L196 (Stages 1-2).

This stage iterates over all stem groups and populates per-group results
into ctx for downstream stages. The Enhancement, Embedding, and Coaching
stages then iterate the same groups using the pre-computed results.
"""
from __future__ import annotations

import os
import time
import tempfile
from typing import Generator

from pipeline.base import ProcessingStage, yield_log
from pipeline.context import PipelineContext
from models import Tier, get_format_type

import preview_extractor
import quality_classifier
from clip_embedder import ClipEmbedder
from vector_store import ChromaManager
from preference_engine import SemanticRAG


class AssessmentStage(ProcessingStage):
    """
    Stage 2: Assess quality and reconcile tiers for each image group.

    For each stem group:
    1. Extract EXIF + preview bytes
    2. Generate CLIP embedding + RAG similarity (Phase E)
    3. Classify quality via quality_classifier
    4. Reconcile group tier (max tier across RAW+JPEG pair)

    Results are stored per-group in ctx._assessed_groups for downstream
    stages to consume in the same iteration order.
    """

    @property
    def name(self) -> str:
        return "Assessment"

    def execute(self, ctx: PipelineContext) -> Generator[str, None, None]:
        # ─── MoE Pre-flight: Fetch Production Prompt Trust ───────────
        from database import SessionLocal, PromptVersion
        golden_success_rate = None
        try:
            with SessionLocal() as db:
                prod_prompt = db.query(PromptVersion).filter(PromptVersion.is_production == True).first()
                if prod_prompt:
                    golden_success_rate = prod_prompt.golden_success_rate
        except Exception as e:
            print(f"⚠️ [AssessmentStage] Failed to fetch production prompt trust: {e}")

        # Accumulator for all groups' assessment data.
        # Each entry: (stem, group_results, max_tier, raw_master)
        ctx._assessed_groups = []

        for stem_idx, stem in enumerate(ctx.stems, 1):
            # 🛑 Check for Abort Request
            if ctx.session_id in ctx.abort_registry:
                return

            group_files = ctx.groups[stem]
            group_results = []

            # ── Per-file assessment within the group ─────────────────
            for filename in group_files:
                filepath = os.path.join(ctx.target_folder, filename)
                try:
                    exif = preview_extractor.extract_metadata(filepath)
                    preview_bytes = preview_extractor.extract_preview(filepath)
                    if not preview_bytes:
                        continue

                    # ── Phase E: Pre-classification RAG embedding ────
                    rag_similarity: float | None = None
                    pre_embedding: list[float] | None = None
                    rag_ctx = None
                    try:
                        if ctx.clip_embedder is None:
                            ctx.clip_embedder = ClipEmbedder()
                            ctx.chroma_mgr = ChromaManager()
                            ctx.semantic_rag = SemanticRAG(ctx.chroma_mgr)

                        # Embed from preview bytes via temp file
                        _tmp = tempfile.mktemp(suffix=".jpg")
                        try:
                            with open(_tmp, "wb") as _fh:
                                _fh.write(preview_bytes)
                            pre_embedding = ctx.clip_embedder.generate_embedding(_tmp)
                        finally:
                            if os.path.exists(_tmp):
                                os.unlink(_tmp)

                        rag_ctx = ctx.semantic_rag.get_few_shot_context(pre_embedding)
                        rag_similarity = rag_ctx["similarity_score"]

                    except Exception as _rag_err:
                        yield yield_log(
                            f"⚠️ RAG pre-embedding skipped for {filename}: {_rag_err}",
                            "warn",
                        )

                    # ── Quality classification ───────────────────────
                    quality = quality_classifier.classify_with_analyst(
                        preview_bytes,
                        analyst=None,
                        exif=exif,
                        rag_similarity_score=rag_similarity,
                        golden_success_rate=golden_success_rate,
                    )

                    group_results.append({
                        "filename": filename,
                        "filepath": filepath,
                        "exif": exif,
                        "quality": quality,
                        "start": time.time(),
                        "format_type": get_format_type(filepath),
                        "pre_embedding": pre_embedding,
                        "rag_context": rag_ctx if rag_similarity is not None else None,
                    })

                except Exception as e:
                    yield yield_log(
                        f"❌ Error assessing {filename}: {str(e)}", "error"
                    )

            if not group_results:
                continue

            # ── Tier Reconciliation ──────────────────────────────────
            max_tier = Tier.CULL
            for res in group_results:
                if res["quality"].tier.rank > max_tier.rank:
                    max_tier = res["quality"].tier

            raw_master = next(
                (res for res in group_results if res["format_type"] == "RAW"),
                None,
            )

            ctx._assessed_groups.append(
                (stem, group_results, max_tier, raw_master)
            )
