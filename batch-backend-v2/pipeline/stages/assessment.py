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
import concurrent.futures
from typing import Generator

from pipeline.base import ProcessingStage, yield_log
from pipeline.context import PipelineContext
from models import Tier, get_format_type, QualityScore

import preview_extractor
import quality_classifier
from clip_embedder import ClipEmbedder
from vector_store import ChromaManager
from preference_engine import SemanticRAG
from vision_analyst import VisionAnalyst


class AssessmentStage(ProcessingStage):
    """
    Stage 2: Assess quality and reconcile tiers for each image group.

    For each stem group:
    1. Extract EXIF + preview bytes
    2. Generate CLIP embedding + RAG similarity (Phase E)
    3. Classify quality via quality_classifier (Threaded with Timeout)
    4. Reconcile group tier (max tier across RAW+JPEG pair)

    Results are stored per-group in ctx._assessed_groups for downstream
    stages to consume in the same iteration order.
    """

    @property
    def name(self) -> str:
        return "Assessment"

    def execute(self, ctx: PipelineContext) -> Generator[str, None, None]:
        # ─── MoE Pre-flight: Fetch Production Prompt Trust ───────────
        from database import PromptVersion
        golden_success_rate = None
        try:
            # Re-use ctx.db if available to prevent connection leaks
            prod_prompt = ctx.db.query(PromptVersion).filter(PromptVersion.is_production == True).first()
            if prod_prompt:
                golden_success_rate = prod_prompt.golden_success_rate
        except Exception as e:
            print(f"⚠️ [AssessmentStage] Failed to fetch production prompt trust: {e}")

        # ─── RAG Pre-flight: Initialize singleton components ──────────
        try:
            if ctx.clip_embedder is None:
                ctx.clip_embedder = ClipEmbedder()
                ctx.chroma_mgr = ChromaManager()
                ctx.semantic_rag = SemanticRAG(ctx.chroma_mgr)
            if ctx.vision_analyst is None:
                ctx.vision_analyst = VisionAnalyst()
        except Exception as e:
            print(f"⚠️ [AssessmentStage] ML component init error: {e}")

        # --- Per-Group Assessment ---
        # The PipelineRunner has already set ctx.current_stem and current_stem_idx
        stem = ctx.current_stem
        stem_idx = ctx.current_stem_idx
        
        if not stem:
            return

        group_files = ctx.groups.get(stem, [])
        group_results = []

        # ── Per-file assessment within the group ─────────────────
        for filename in group_files:
            # 🛑 Check for Abort Request
            if ctx.session_id in ctx.abort_registry:
                return

            filepath = os.path.join(ctx.target_folder, filename)
            yield yield_log(f"Processing {filename}...", "progress")
            
            try:
                # ── Refinement: Fresh executor per file for true recovery ──
                # Ensures that a hung VLM thread doesn't block the next file.
                executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                try:
                    future = executor.submit(
                        self._process_single_file,
                        filepath,
                        filename,
                        ctx,
                        golden_success_rate
                    )
                    # 45s hard ceiling for one file (Exif + CLIP + VLM)
                    res_data = future.result(timeout=45)
                finally:
                    # wait=False is critical: it prevents the main thread from 
                    # hanging if the worker thread is truly stuck.
                    executor.shutdown(wait=False)
                
                if res_data:
                    group_results.append(res_data)
                    quality = res_data["quality"]
                    yield yield_log(
                        f"✅ Signals captured for {filename}.", 
                        "progress",
                        {
                            "sharpness": round(quality.sharpness, 1),
                            "aesthetic": round(quality.aesthetic, 1),
                            "aes": round(quality.aesthetic, 1),
                        }
                    )

            except concurrent.futures.TimeoutError:
                yield yield_log(f"⚠️ Timeout processing {filename}. Skipping.", "warn")
            except Exception as e:
                yield yield_log(f"❌ Error assessing {filename}: {str(e)}", "error")

        if not group_results:
            return

        # ── Tier Reconciliation ──────────────────────────────────
        max_tier = Tier.CULL
        for res in group_results:
            if res["quality"].tier.rank > max_tier.rank:
                max_tier = res["quality"].tier

        raw_master = next(
            (res for res in group_results if res["format_type"] == "RAW"),
            None,
        )

        # Store in transient state for downstream per-group stages
        ctx.current_group_results = group_results
        ctx.current_max_tier = max_tier
        ctx.current_raw_master = raw_master

        # Also append to the global cross-stage accumulator for CloudSync/Results
        ctx._assessed_groups.append(
            (stem, group_results, max_tier, raw_master)
        )

        # ── Gemini Fix: Periodic Garbage Collection ──────────────────
        # Heavy RAW processing with rawpy/PIL can cause memory fragmentation.
        if stem_idx % 5 == 0:
            import gc
            gc.collect()

    def _process_single_file(self, filepath, filename, ctx, golden_success_rate):
        """Heavy lifting for one file, runs in executor thread."""
        exif = preview_extractor.extract_metadata(filepath)
        preview_bytes = preview_extractor.extract_preview(filepath)
        if not preview_bytes:
            return None

        # RAG Embedding
        rag_similarity = None
        pre_embedding = None
        rag_ctx = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as _tmp:
                _tmp.write(preview_bytes)
                _tmp_path = _tmp.name
            
            try:
                pre_embedding = ctx.clip_embedder.generate_embedding(_tmp_path)
                rag_ctx = ctx.semantic_rag.get_few_shot_context(pre_embedding)
                rag_similarity = rag_ctx["similarity_score"]
            finally:
                if os.path.exists(_tmp_path):
                    os.unlink(_tmp_path)
        except:
            pass

        # MoE Quality Score (VLM + Heuristics)
        quality = quality_classifier.classify_with_analyst(
            preview_bytes,
            analyst=ctx.vision_analyst,
            exif=exif,
            rag_similarity_score=rag_similarity,
            golden_success_rate=golden_success_rate,
        )

        return {
            "filename": filename,
            "filepath": filepath,
            "exif": exif,
            "quality": quality,
            "start": time.time(),
            "format_type": get_format_type(filepath),
            "pre_embedding": pre_embedding,
            "rag_context": rag_ctx,
        }
