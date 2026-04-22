"""
Antigravity Engine v2.1 — Pipeline Runner
The orchestrator that replaces stream_batch(). Iterates stages, handles
pre-flight checks, abort signals, atomic rollback, and durable log persistence.

Gemini Refinements Implemented:
  Phase 4 #1 — Pre-flight Memory Guard before Stage 1
  Phase 4 #2 — try/finally DB lifecycle for ctx.db (no connection leaks)
  Phase 4 #5 — SSE event sequence identical to original monolith
  Extension #1 — Early log init fallback (log file created at Pipeline instantiation)
  Extension #3 — batch_status tracking for polling metadata
"""
from __future__ import annotations

import os
import shutil
import time
from typing import Generator, Set

from pipeline.base import ProcessingStage, yield_log
from pipeline.context import PipelineContext
from database import SessionLocal, Inference, Media


# ─── Session Registry ────────────────────────────────────────────────
# Maps session_id → { "log_path": str, "status": str }
# Used by the GET /api/logs/{session_id} polling endpoint.
SESSION_REGISTRY: dict[str, dict] = {}

# Fallback log directory (Gemini Extension Refinement #1):
# Created at import time, guarantees a writable path even if
# DiscoveryStage fails before workspace_dir is initialized.
_FALLBACK_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(_FALLBACK_LOG_DIR, exist_ok=True)


# ─── Pipeline Runner ─────────────────────────────────────────────────

class Pipeline:
    """
    Executes a list of ProcessingStage objects in sequence.

    Responsibilities:
    - Pre-flight memory check (Gemini refinement #1)
    - DB session lifecycle management (Gemini refinement #2)
    - Abort signal detection + atomic rollback
    - Durable log persistence to logs.jsonl (Extension #1)
    - batch_status tracking for polling API (Extension #3)
    - Yield SSE-formatted log strings for real-time frontend telemetry
    """

    def __init__(self, stages: list[ProcessingStage], abort_registry: Set[str] | None = None):
        self.stages = stages
        self._abort_registry = abort_registry if abort_registry is not None else set()

    def run(self, ctx: PipelineContext) -> Generator[str, None, None]:
        """
        Execute all stages, yielding telemetry events.

        The SSE event sequence (type + message) MUST match the original
        batch_orchestrator.stream_batch() output to avoid breaking the
        Batch Studio terminal regex/parsing (Gemini refinement #5).
        """
        # Inject abort registry reference into context
        ctx.abort_registry = self._abort_registry
        
        # ── Gemini Fix: Clear any stale abort signals for this ID ──
        # If the user previously aborted a run with this ID, we must
        # clear it now so the NEW run can actually start.
        self._abort_registry.discard(ctx.session_id)

        # ── Extension Refinement #1: Early log path init ─────────────
        # Create log file BEFORE any stage runs, so even DiscoveryStage
        # errors are visible to the polling UI.
        log_path = os.path.join(_FALLBACK_LOG_DIR, f"{ctx.session_id}.jsonl")
        # Clear any stale log from a previous run with the same session_id
        if os.path.exists(log_path):
            os.unlink(log_path)

        # Register session immediately (Gemini Extension #3: batch_status)
        SESSION_REGISTRY[ctx.session_id] = {
            "log_path": log_path,
            "status": "running",
        }

        yield self._emit(log_path, yield_log(
            f"Initializing Antigravity Kernel (Session: {ctx.session_id})", "sys"
        ))
        print(f"\n🚀 Antigravity Engine v2.1 — Kernel Active (Session: {ctx.session_id})")

        ctx.batch_start = time.time()

        # ── Gemini Refinement #1: Pre-flight Memory Guard ────────────
        try:
            from main import ensure_memory_headroom
            import asyncio

            # Pipeline runs in a background thread. We MUST get the running 
            # uvicorn loop from the main thread context, schedule the 
            # coroutine, and BLOCK until it completes.
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    future = asyncio.run_coroutine_threadsafe(ensure_memory_headroom(), loop)
                    # Block for up to 30s to allow memory eviction to finish
                    future.result(timeout=30)
                else:
                    loop.run_until_complete(ensure_memory_headroom())
            except RuntimeError:
                # Fallback for environments where get_event_loop() fails (Python 3.12+)
                asyncio.run(ensure_memory_headroom())
        except ImportError:
            # Graceful degradation if main.py is not importable
            # (e.g., during isolated unit tests)
            print("⚠️ [Pipeline] Memory guard unavailable — skipping pre-flight check.")
        except Exception as e:
            print(f"⚠️ [Pipeline] Memory guard error (non-fatal): {e}")

        # ── Gemini Refinement #2: DB lifecycle managed here ──────────
        try:
            ctx.db = SessionLocal()

            # ── Partition Stages ─────────────────────────────────────
            # Group stages into Pre-Loop (Global), Per-Group, and Post-Loop (Global).
            global_pre = []
            per_group = []
            global_post = []
            
            mode = 0  # 0: global_pre, 1: per_group, 2: global_post
            for stage in self.stages:
                if stage.is_global:
                    if mode == 0:
                        global_pre.append(stage)
                    else:
                        mode = 2
                        global_post.append(stage)
                else:
                    mode = 1
                    per_group.append(stage)

            # 1. Execute Global Pre-flight Stages (e.g., Discovery)
            for stage in global_pre:
                if stage.should_skip(ctx): continue
                for event_str in stage.execute(ctx):
                    yield self._emit(log_path, event_str)

            # 🛑 Check for Abort after Discovery (stems populated)
            if ctx.session_id in self._abort_registry:
                yield from self._rollback_with_log(ctx, log_path)
                SESSION_REGISTRY[ctx.session_id]["status"] = "failed"
                return

            # 2. Execute Per-Group Vertical Pipeline
            # Process each image group completely (Assess -> Enhance -> Tag)
            # before moving to the next group.
            for stem_idx, stem in enumerate(ctx.stems, 1):
                # 🛑 Check for Abort Request before each group
                if ctx.session_id in self._abort_registry:
                    yield from self._rollback_with_log(ctx, log_path)
                    SESSION_REGISTRY[ctx.session_id]["status"] = "failed"
                    return

                ctx.current_stem = stem
                ctx.current_stem_idx = stem_idx
                # Transient state is reset inside each per_group stage or context

                for stage in per_group:
                    if stage.should_skip(ctx): continue
                    for event_str in stage.execute(ctx):
                        yield self._emit(log_path, event_str)

            # 3. Execute Global Post-flight Stages (e.g., CloudSync)
            for stage in global_post:
                if stage.should_skip(ctx): continue
                for event_str in stage.execute(ctx):
                    yield self._emit(log_path, event_str)

            # ── All stages completed — no abort ──────────────────────
            # Final "done" event is emitted by CloudSyncStage
            SESSION_REGISTRY[ctx.session_id]["status"] = "completed"

            # Upgrade log path to workspace if it was initialized
            if ctx.workspace_dir:
                workspace_log = os.path.join(ctx.workspace_dir, "logs.jsonl")
                try:
                    shutil.copy2(log_path, workspace_log)
                except Exception:
                    pass  # Non-fatal — fallback log is authoritative

        except Exception as e:
            yield self._emit(log_path, yield_log(
                f"CRITICAL KERNEL ERROR: {str(e)}", "error"
            ))
            SESSION_REGISTRY[ctx.session_id]["status"] = "failed"
            # Rollback DB on critical failure
            if ctx.db:
                try:
                    ctx.db.rollback()
                except Exception:
                    pass
        finally:
            # ── Gemini Refinement #2: Guaranteed DB closure ──────────
            if ctx.db:
                try:
                    ctx.db.close()
                except Exception:
                    pass
            
            # 🛑 Ensure session is removed from abort registry if it was there
            self._abort_registry.discard(ctx.session_id)

            # Clean up workspace directory
            shutil.rmtree(
                os.path.join(ctx.target_folder, ".antigravity_workspace"),
                ignore_errors=True,
            )

    def _emit(self, log_path: str, log_str: str) -> str:
        """
        Yield a log event AND persist it to the durable log file.
        Gemini Extension Refinement #1: dual-write for polling reliability.
        """
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(log_str)  # Already newline-terminated by yield_log()
        except Exception:
            pass  # Non-fatal — the generator yield is the primary path
        return log_str

    def _rollback_with_log(self, ctx: PipelineContext, log_path: str) -> Generator[str, None, None]:
        """Rollback with log persistence."""
        for event_str in self._rollback(ctx):
            yield self._emit(log_path, event_str)

    def _rollback(self, ctx: PipelineContext) -> Generator[str, None, None]:
        """
        Atomic rollback sequence. Removes created files and prunes
        pending DB records. Mirrors original batch_orchestrator L359-372.
        """
        print(f"DEBUG: Starting rollback for {ctx.session_id}")
        yield yield_log(
            "🚨 ABORT SIGNAL RECEIVED. Initiating Atomic Rollback...", "warn"
        )

        # 1. Delete created files
        yield yield_log("Rolling back partial files...", "revert")
        for f in ctx.session_files:
            if os.path.exists(f):
                os.unlink(f)
            yield yield_log(f"Deleted: {os.path.basename(f)}", "revert")

        # 2. Prune pending DB records
        yield yield_log("Pruring pending database records...", "revert")
        if ctx.db:
            ctx.db.query(Inference).filter(
                Inference.id.in_(ctx.inference_db_ids)
            ).delete(synchronize_session=False)
            ctx.db.query(Media).filter(
                Media.id.in_(ctx.session_db_ids),
                Media.enhanced_path == None,
            ).delete(synchronize_session=False)
            ctx.db.commit()

        yield yield_log(
            "Rollback Complete. Session Terminated Safely.", "warn"
        )
