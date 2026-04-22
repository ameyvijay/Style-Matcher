"""
Antigravity Engine v2.1 — Pipeline Context
Shared mutable state object passed through all pipeline stages.

Replaces the ~15 scattered local variables in the original stream_batch().
Makes the data contract between stages explicit, testable, and inspectable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Set


@dataclass
class PipelineContext:
    """
    Shared state flowing through the pipeline.

    All stages read from and write to this context. The PipelineRunner owns
    the lifecycle of ctx.db (open/close/rollback) per Gemini refinement #2.
    """

    # ── Inputs (immutable after construction) ────────────────────────
    target_folder: str = ""
    benchmark_folder: str | None = None
    session_id: str = "default"

    # ── Configuration (set by DiscoveryStage) ────────────────────────
    workspace_dir: str = ""
    enhanced_dir: str = ""
    rejected_dir: str = ""
    rlhf_input_dir: str = ""

    # ── Discovery results (set by DiscoveryStage) ────────────────────
    groups: dict[str, list[str]] = field(default_factory=dict)
    stems: list[str] = field(default_factory=list)
    total_files: int = 0

    # ── Database state (managed by PipelineRunner) ───────────────────
    db: Any = None                          # SQLAlchemy Session (SessionLocal)
    model_record: Any = None                # ModelRegistry row

    # ── Processing counters ──────────────────────────────────────────
    processed_count: int = 0
    batch_start: float = 0.0

    # ── Lazy-init ML components (shared across stages) ───────────────
    clip_embedder: Any = None               # ClipEmbedder instance
    chroma_mgr: Any = None                  # ChromaManager instance
    semantic_rag: Any = None                # SemanticRAG instance
    vision_analyst: Any = None              # VisionAnalyst instance

    # ── Rollback tracking (used by PipelineRunner on abort) ──────────
    session_files: list[str] = field(default_factory=list)
    session_db_ids: list[int] = field(default_factory=list)
    inference_db_ids: list[int] = field(default_factory=list)

    # ── Results (accumulated across stages) ──────────────────────────
    assessments: list = field(default_factory=list)       # list[ImageAssessment]
    result: Any = None                                     # BatchResult
    tier_buckets: dict = field(default_factory=lambda: {
        "portfolio": 0, "keeper": 0, "review": 0, "culled": 0, "recoverable": 0
    })

    # ── Per-group transient state ────────────────────────────────────
    # Reset by AssessmentStage at the start of each stem group iteration.
    current_stem: str = ""
    current_stem_idx: int = 0
    current_group_results: list = field(default_factory=list)
    current_max_tier: Any = None
    current_raw_master: Any = None

    # ── Reference to abort registry (injected by PipelineRunner) ─────
    abort_registry: Set[str] = field(default_factory=set)

    # ── Stage-crossing accumulator (set by AssessmentStage) ──────────
    _assessed_groups: list = field(default_factory=list)
