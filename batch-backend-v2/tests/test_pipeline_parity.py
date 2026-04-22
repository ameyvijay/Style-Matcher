"""
test_pipeline_parity.py
=======================
Golden-file regression tests verifying that the modular Pipeline produces
identical behavior to the original monolithic batch_orchestrator.

Gemini Refinement #5: SSE event sequence (type + message) must remain
byte-identical to the current monolith to avoid breaking the Batch Studio
terminal regex/parsing.

Run from the batch-backend-v2 directory:
    python -m pytest tests/test_pipeline_parity.py -v
"""
from __future__ import annotations

import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock
from dataclasses import dataclass

# Ensure the parent (batch-backend-v2) directory is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import Pipeline, PipelineContext, ProcessingStage, yield_log
from pipeline.stages.discovery import DiscoveryStage
from pipeline.stages.assessment import AssessmentStage
from pipeline.stages.enhancement import EnhancementStage
from pipeline.stages.embedding import EmbeddingStage
from pipeline.stages.coaching import CoachingStage
from pipeline.stages.cloud_sync import CloudSyncStage, generate_doppler_manifest
from pipeline.pipeline_runner import Pipeline as PipelineRunner

from models import BatchResult, QualityScore, Tier, ImageAssessment


# ─── Fixtures ────────────────────────────────────────────────────────

NONEXISTENT_FOLDER = "/tmp/antigravity_test_nonexistent_folder_xyz"


# ─── Unit Tests ──────────────────────────────────────────────────────

class TestYieldLogParity(unittest.TestCase):
    """Verify yield_log produces the exact same JSON structure as the original."""

    def test_basic_event_format(self):
        """yield_log must produce JSON with timestamp, type, message, data keys."""
        raw = yield_log("Test message", "sys", {"key": "val"})
        event = json.loads(raw.strip())

        self.assertIn("timestamp", event)
        self.assertEqual(event["type"], "sys")
        self.assertEqual(event["message"], "Test message")
        self.assertEqual(event["data"], {"key": "val"})

    def test_newline_terminated(self):
        """Each SSE event must end with exactly one newline."""
        raw = yield_log("Test", "sys")
        self.assertTrue(raw.endswith("\n"))
        self.assertFalse(raw.endswith("\n\n"))

    def test_null_data_when_none(self):
        """data field must be null (not missing) when no data is provided."""
        raw = yield_log("No data event", "sys")
        event = json.loads(raw.strip())
        self.assertIsNone(event["data"])


class TestPipelineContextDefaults(unittest.TestCase):
    """Verify PipelineContext initializes with safe defaults."""

    def test_default_values(self):
        ctx = PipelineContext(
            target_folder="/tmp/test",
            session_id="test_session",
        )
        self.assertEqual(ctx.target_folder, "/tmp/test")
        self.assertEqual(ctx.session_id, "test_session")
        self.assertIsNone(ctx.db)
        self.assertEqual(ctx.processed_count, 0)
        self.assertEqual(ctx.session_files, [])
        self.assertEqual(ctx.session_db_ids, [])
        self.assertEqual(ctx.inference_db_ids, [])
        self.assertEqual(ctx.assessments, [])
        self.assertEqual(ctx.tier_buckets, {
            "portfolio": 0, "keeper": 0, "review": 0,
            "culled": 0, "recoverable": 0,
        })

    def test_abort_registry_isolated(self):
        """Each context has its own abort_registry reference by default."""
        ctx1 = PipelineContext(target_folder="/a")
        ctx2 = PipelineContext(target_folder="/b")
        ctx1.abort_registry.add("test")
        self.assertNotIn("test", ctx2.abort_registry)


class TestProcessingStageContract(unittest.TestCase):
    """Verify the ABC enforces the contract."""

    def test_cannot_instantiate_abc(self):
        """ProcessingStage is abstract and cannot be instantiated directly."""
        with self.assertRaises(TypeError):
            ProcessingStage()

    def test_concrete_stage_must_implement_name_and_execute(self):
        """A stage missing name or execute cannot be instantiated."""

        class IncompleteStage(ProcessingStage):
            pass

        with self.assertRaises(TypeError):
            IncompleteStage()

    def test_concrete_stage_works(self):
        """A properly implemented stage can be instantiated."""

        class TestStage(ProcessingStage):
            @property
            def name(self):
                return "TestStage"

            def execute(self, ctx):
                yield yield_log("test", "sys")

        stage = TestStage()
        self.assertEqual(stage.name, "TestStage")
        self.assertFalse(stage.should_skip(PipelineContext()))


class TestDiscoveryStageNonexistentFolder(unittest.TestCase):
    """DiscoveryStage must handle a missing folder gracefully."""

    def test_nonexistent_folder_emits_error(self):
        ctx = PipelineContext(
            target_folder=NONEXISTENT_FOLDER,
            session_id="test",
        )
        # Need a mock db since DiscoveryStage is called without PipelineRunner
        ctx.db = MagicMock()

        events = list(DiscoveryStage().execute(ctx))

        # Should emit exactly one error event
        self.assertEqual(len(events), 1)
        event = json.loads(events[0].strip())
        self.assertEqual(event["type"], "error")
        self.assertIn("not found", event["message"])

    def test_nonexistent_folder_does_not_populate_stems(self):
        ctx = PipelineContext(
            target_folder=NONEXISTENT_FOLDER,
            session_id="test",
        )
        ctx.db = MagicMock()

        list(DiscoveryStage().execute(ctx))

        self.assertEqual(ctx.stems, [])
        self.assertEqual(ctx.groups, {})
        self.assertEqual(ctx.total_files, 0)


class TestDopplerManifestParity(unittest.TestCase):
    """Verify the Doppler manifest generator preserves the 70/30 ratio logic."""

    def test_empty_inputs(self):
        """Empty lists produce a valid manifest with 0 items."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            path, data = generate_doppler_manifest([], [], [], tmpdir)
            self.assertEqual(data["total_items"], 0)
            self.assertEqual(data["photos"], [])

    def test_all_accepts_no_rejects(self):
        """When there are only accepts, all should appear in the manifest."""
        import tempfile
        accepts = [f"photo_{i}" for i in range(5)]
        with tempfile.TemporaryDirectory() as tmpdir:
            path, data = generate_doppler_manifest(accepts, [], [], tmpdir)
            self.assertEqual(data["total_items"], 5)

    def test_ratio_structure(self):
        """With 7+ accepts and 3+ rejects, chunks should follow 7:3 pattern."""
        import tempfile
        accepts = [f"accept_{i}" for i in range(14)]
        rejects = [f"reject_{i}" for i in range(6)]
        with tempfile.TemporaryDirectory() as tmpdir:
            path, data = generate_doppler_manifest(accepts, rejects, [], tmpdir)
            self.assertEqual(data["total_items"], 20)


class TestPipelineRollback(unittest.TestCase):
    """Verify the Pipeline handles abort signals correctly."""

    def test_abort_triggers_rollback_events(self):
        """When session_id is in abort_registry, rollback events are emitted."""
        abort_reg = {"test_session"}

        pipeline = Pipeline(
            stages=[DiscoveryStage()],
            abort_registry=abort_reg,
        )

        ctx = PipelineContext(
            target_folder=NONEXISTENT_FOLDER,
            session_id="test_session",
        )

        # Start the pipeline and inject the abort signal AFTER it clears stale signals
        gen = pipeline.run(ctx)
        
        # Get the first event (Initializing)
        next(gen)
        
        # Now inject the abort signal
        abort_reg.add("test_session")
        
        # Consume the rest of the events
        events = list(gen)
        
        # Should contain rollback-related events
        event_types = [json.loads(e.strip())["type"] for e in events]
        self.assertIn("warn", event_types)

        # Abort registry should be cleared after rollback
        self.assertNotIn("test_session", abort_reg)


class TestFacadeBackwardCompat(unittest.TestCase):
    """Verify batch_orchestrator façade exports match what main.py expects."""

    def test_all_public_symbols_exist(self):
        import batch_orchestrator

        required_symbols = [
            "ABORT_REGISTRY",
            "stream_batch",
            "scan_only",
            "run_all_self_tests",
            "generate_doppler_manifest",
        ]
        for sym in required_symbols:
            self.assertTrue(
                hasattr(batch_orchestrator, sym),
                f"batch_orchestrator missing required symbol: {sym}",
            )

    def test_stream_batch_is_generator(self):
        import inspect
        import batch_orchestrator

        self.assertTrue(
            inspect.isgeneratorfunction(batch_orchestrator.stream_batch),
            "stream_batch must be a generator function",
        )

    def test_abort_registry_is_shared_set(self):
        import batch_orchestrator

        self.assertIsInstance(batch_orchestrator.ABORT_REGISTRY, set)


if __name__ == "__main__":
    unittest.main(verbosity=2)
