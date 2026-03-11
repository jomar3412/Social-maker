"""Tests for RunStore service."""

import pytest
from pathlib import Path
import tempfile

from content_engine.services.run_store import RunStore, RunStage, RunRecord


class TestRunStore:
    """Test RunStore persistence."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "test_runs.db"

    @pytest.fixture
    def store(self, temp_db):
        """Create RunStore with temp database."""
        return RunStore(temp_db)

    def test_create_run(self, store):
        """Test creating a run record."""
        config = {"niche": "motivation", "style": "affirming"}
        record = store.create_run("run-001", config)

        assert record.run_id == "run-001"
        assert record.stage == RunStage.INIT
        assert record.config["niche"] == "motivation"
        assert record.approvals_pending == []
        assert record.output_path is None

    def test_get_run(self, store):
        """Test retrieving a run record."""
        store.create_run("run-001", {"test": True})
        record = store.get_run("run-001")

        assert record is not None
        assert record.run_id == "run-001"

    def test_get_run_not_found(self, store):
        """Test retrieving nonexistent run."""
        record = store.get_run("nonexistent")
        assert record is None

    def test_update_stage(self, store):
        """Test updating run stage."""
        store.create_run("run-001", {})

        success = store.update_stage("run-001", RunStage.RESEARCH)
        assert success is True

        record = store.get_run("run-001")
        assert record.stage == RunStage.RESEARCH

    def test_update_stage_with_output_path(self, store):
        """Test updating stage with output path."""
        store.create_run("run-001", {})

        store.update_stage(
            "run-001",
            RunStage.COMPLETE,
            output_path="/path/to/output",
        )

        record = store.get_run("run-001")
        assert record.output_path == "/path/to/output"

    def test_update_stage_with_error(self, store):
        """Test updating stage with error message."""
        store.create_run("run-001", {})

        store.update_stage(
            "run-001",
            RunStage.FAILED,
            error_message="Test error",
        )

        record = store.get_run("run-001")
        assert record.stage == RunStage.FAILED
        assert record.error_message == "Test error"

    def test_update_stage_with_approvals(self, store):
        """Test updating stage with approvals pending."""
        store.create_run("run-001", {})

        store.update_stage(
            "run-001",
            RunStage.AWAITING_SCRIPT_APPROVAL,
            approvals_pending=["script"],
        )

        record = store.get_run("run-001")
        assert record.approvals_pending == ["script"]

    def test_get_pending_runs(self, store):
        """Test getting runs awaiting approval."""
        store.create_run("run-001", {})
        store.create_run("run-002", {})
        store.create_run("run-003", {})

        store.update_stage("run-001", RunStage.COMPLETE)
        store.update_stage("run-002", RunStage.AWAITING_SCRIPT_APPROVAL)
        store.update_stage("run-003", RunStage.AWAITING_VOICEOVER_APPROVAL)

        pending = store.get_pending_runs()
        assert len(pending) == 2
        run_ids = [r.run_id for r in pending]
        assert "run-002" in run_ids
        assert "run-003" in run_ids

    def test_get_recent_runs(self, store):
        """Test getting recent runs."""
        for i in range(5):
            store.create_run(f"run-{i:03d}", {"index": i})

        recent = store.get_recent_runs(limit=3)
        assert len(recent) == 3

    def test_delete_run(self, store):
        """Test deleting a run."""
        store.create_run("run-001", {})
        assert store.get_run("run-001") is not None

        success = store.delete_run("run-001")
        assert success is True
        assert store.get_run("run-001") is None

    def test_delete_run_not_found(self, store):
        """Test deleting nonexistent run."""
        success = store.delete_run("nonexistent")
        assert success is False

    def test_is_pending_approval(self, store):
        """Test is_pending_approval method."""
        store.create_run("run-001", {})

        store.update_stage("run-001", RunStage.AWAITING_SCRIPT_APPROVAL)
        record = store.get_run("run-001")
        assert record.is_pending_approval() is True

        store.update_stage("run-001", RunStage.COMPLETE)
        record = store.get_run("run-001")
        assert record.is_pending_approval() is False


class TestRunRecord:
    """Test RunRecord dataclass."""

    def test_config_property(self):
        """Test config property parses JSON."""
        record = RunRecord(
            run_id="test",
            stage=RunStage.INIT,
            approvals_pending=[],
            config_json='{"key": "value"}',
            output_path=None,
            created_at="2026-01-01",
            updated_at="2026-01-01",
        )

        assert record.config["key"] == "value"

    def test_config_property_empty(self):
        """Test config property with empty JSON."""
        record = RunRecord(
            run_id="test",
            stage=RunStage.INIT,
            approvals_pending=[],
            config_json="",
            output_path=None,
            created_at="2026-01-01",
            updated_at="2026-01-01",
        )

        assert record.config == {}
