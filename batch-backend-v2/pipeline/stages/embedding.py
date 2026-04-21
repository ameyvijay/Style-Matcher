"""
Antigravity Engine v2.1 — Stage 4: Embedding
CLIP embedding persistence, prompt context build, and Inference DB commit.

Extracted from batch_orchestrator.py L272–L332 (Phase C/E/F).
"""
from __future__ import annotations

import os
import json
import time
from typing import Generator

from pipeline.base import ProcessingStage, yield_log
from pipeline.context import PipelineContext
from database import Inference
from clip_embedder import ClipEmbedder
from vector_store import ChromaManager
from preference_engine import SemanticRAG
from prompt_registry import PromptRegistry, build_prompt_context, LATEST_VERSION


class EmbeddingStage(ProcessingStage):
    """
    Stage 4: Persist CLIP embeddings and create Inference DB records.

    For each file in each assessed group:
    1. Re-use or generate CLIP embedding vector
    2. Build prompt context from RAG payload (Phase F)
    3. Construct and commit Inference record with prompt version + semantic desc
    4. Track inference IDs in ctx.inference_db_ids for rollback
    """

    @property
    def name(self) -> str:
        return "Embedding"

    def execute(self, ctx: PipelineContext) -> Generator[str, None, None]:
        for stem, group_results, max_tier, raw_master in ctx._assessed_groups:
            if ctx.session_id in ctx.abort_registry:
                return

            for res in group_results:
                filename = res["filename"]
                filepath = res["filepath"]
                quality = res["quality"]
                exif = res["exif"]
                media = res.get("media")
                rlhf_path = res.get("rlhf_path", "")

                if media is None:
                    # Enhancement stage may have skipped this file on error
                    continue

                # ── Phase C: CLIP Embedding Persistence ──────────────
                embedding_json = None
                try:
                    if ctx.clip_embedder is None:
                        ctx.clip_embedder = ClipEmbedder()
                        ctx.chroma_mgr = ChromaManager()
                        ctx.semantic_rag = SemanticRAG(ctx.chroma_mgr)

                    embedding_vec = res.get("pre_embedding")
                    if embedding_vec is None:
                        embed_source = (
                            rlhf_path
                            if rlhf_path and os.path.isfile(rlhf_path)
                            else filepath
                        )
                        embedding_vec = ctx.clip_embedder.generate_embedding(
                            embed_source
                        )
                    embedding_json = json.dumps(embedding_vec)
                except Exception as emb_err:
                    yield yield_log(
                        f"⚠️ CLIP embedding skipped for {filename}: {emb_err}",
                        "warn",
                    )

                # ── Phase F: Prompt Context & Traceability ───────────
                _rag_ctx = res.get("rag_context")
                _prompt_version = LATEST_VERSION
                _semantic_desc = ""
                try:
                    from models import detect_genre as _dg

                    _genre = _dg(exif)
                    _p_ctx = build_prompt_context(_rag_ctx, genre=_genre)
                    _prompt_version = LATEST_VERSION
                    if _rag_ctx and _rag_ctx.get("exemplars"):
                        _semantic_desc = (
                            f"RAG-enriched assessment (v{_prompt_version}): "
                            f"similarity={_rag_ctx.get('similarity_score', 0):.1f}, "
                            f"exemplars={len(_rag_ctx['exemplars'])}"
                        )
                except Exception as _pf_err:
                    yield yield_log(
                        f"⚠️ Prompt context build skipped for {filename}: {_pf_err}",
                        "warn",
                    )

                # Enrich the QualityScore with prompt metadata
                quality.semantic_description = (
                    _semantic_desc or quality.semantic_description
                )

                # ── Database Inference record ────────────────────────
                inf = Inference(
                    media_id=media.id,
                    model_id=ctx.model_record.id,
                    inference_value=json.dumps({
                        "tier": max_tier.value,
                        "sharp": quality.sharpness,
                        "aes": quality.aesthetic,
                        "prompt_version": _prompt_version,
                        "semantic_description": _semantic_desc,
                    }),
                    embedding_blob=embedding_json,
                    confidence=1.0,
                    processing_time_ms=(time.time() - res["start"]) * 1000,
                )
                ctx.db.add(inf)
                ctx.db.commit()
                ctx.inference_db_ids.append(inf.id)

                # Store prompt metadata for downstream CoachingStage
                res["_prompt_version"] = _prompt_version
                res["_semantic_desc"] = _semantic_desc
