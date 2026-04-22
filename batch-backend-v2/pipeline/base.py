"""
Antigravity Engine v2.1 — Pipeline Base
Abstract base class for all pipeline stages + shared SSE telemetry helper.
"""
from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from typing import Any, Generator

# Forward reference — PipelineContext is imported at type-check time only
# to avoid circular imports.
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pipeline.context import PipelineContext


# ─── SSE Telemetry Helper ────────────────────────────────────────────
# Extracted from the original batch_orchestrator._yield_log().
# Signature MUST remain identical to preserve SSE event parity with the
# Batch Studio frontend terminal regex/parsing (Gemini refinement #5).

def yield_log(message: str, type: str = "sys", data: Any = None) -> str:
    """Format a single SSE log event as a JSON string + newline."""
    return json.dumps({
        "timestamp": time.time(),
        "type": type,
        "message": message,
        "data": data
    }) + "\n"


# ─── Stage Abstract Base Class ───────────────────────────────────────

class ProcessingStage(ABC):
    """
    Contract for all pipeline stages.

    Each stage receives a shared PipelineContext and yields SSE log strings
    via the yield_log() helper for real-time frontend telemetry.

    Lifecycle:
        1. Pipeline checks should_skip(ctx) — skip if True
        2. Pipeline calls execute(ctx) — stage mutates ctx in-place
        3. Stage yields yield_log() strings consumed by StreamingResponse
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable stage name for telemetry logging."""
        ...

    @property
    def is_global(self) -> bool:
        """
        Scoping flag:
        - True: Stage runs once for the entire batch (e.g., Discovery).
        - False: Stage runs repeatedly for each image group (e.g., Assessment).
        """
        return False

    @abstractmethod
    def execute(self, ctx: "PipelineContext") -> Generator[str, None, None]:
        """
        Run the stage logic.

        Must yield yield_log()-formatted strings for real-time SSE streaming.
        Mutates ctx in-place to pass data to subsequent stages.
        """
        ...

    def should_skip(self, ctx: "PipelineContext") -> bool:
        """Override to conditionally skip this stage (default: never skip)."""
        return False
