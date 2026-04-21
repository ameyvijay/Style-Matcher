"""
Antigravity Engine v2.1 — Pipeline Package
Modular pipeline pattern replacing the monolithic batch_orchestrator internals.
"""
from pipeline.pipeline_runner import Pipeline
from pipeline.context import PipelineContext
from pipeline.base import ProcessingStage, yield_log

__all__ = ["Pipeline", "PipelineContext", "ProcessingStage", "yield_log"]
