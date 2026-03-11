"""Tests for OutputWriter service."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import json

from content_engine.services.output_writer import OutputWriter, OutputPaths
from content_engine.services.drive_guard import DriveGuard, DriveStatus, DriveCheckResult


class TestOutputWriter:
    """Test OutputWriter functionality."""

    @pytest.fixture
    def temp_mount(self):
        """Create temporary mount directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mount = Path(tmpdir)
            # Create output root
            (mount / "content_engine").mkdir()
            yield mount

    @pytest.fixture
    def mock_guard(self, temp_mount):
        """Create mock DriveGuard."""
        guard = MagicMock(spec=DriveGuard)
        guard.mount_path = temp_mount
        guard.output_root = "content_engine"
        guard.get_output_base.return_value = temp_mount / "content_engine"
        guard.require_writable.return_value = temp_mount
        return guard

    @pytest.fixture
    def writer(self, mock_guard):
        """Create OutputWriter with mock guard."""
        return OutputWriter(mock_guard)

    def test_create_run_directory(self, writer, temp_mount):
        """Test creating run output directory."""
        paths = writer.create_run_directory(
            run_id="run-001",
            niche="motivation",
            style="affirming",
            date="2026-02-23",
        )

        assert isinstance(paths, OutputPaths)
        assert paths.base_dir.exists()
        assert "motivation" in str(paths.base_dir)
        assert "affirming" in str(paths.base_dir)
        assert "2026-02-23" in str(paths.base_dir)
        assert "run-001" in str(paths.base_dir)

    def test_create_run_directory_default_date(self, writer):
        """Test run directory uses today's date by default."""
        paths = writer.create_run_directory(
            run_id="run-002",
            niche="fun_facts",
            style="energetic",
        )

        assert paths.base_dir.exists()
        # Date should be in the path
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        assert today in str(paths.base_dir)

    def test_write_config(self, writer, temp_mount):
        """Test writing config.json."""
        paths = writer.create_run_directory("run-001", "test", "test")
        config = {"niche": "motivation", "style": "affirming"}

        result_path = writer.write_config(paths, config)

        assert result_path.exists()
        data = json.loads(result_path.read_text())
        assert data["niche"] == "motivation"

    def test_write_script(self, writer):
        """Test writing script.txt."""
        paths = writer.create_run_directory("run-001", "test", "test")
        script = "You did good today. Really good."

        result_path = writer.write_script(paths, script)

        assert result_path.exists()
        assert result_path.read_text() == script

    def test_write_script_meta(self, writer):
        """Test writing script_meta.json."""
        paths = writer.create_run_directory("run-001", "test", "test")
        meta = {
            "hook": "You did good today.",
            "keywords": ["motivation", "self-worth"],
        }

        result_path = writer.write_script_meta(paths, meta)

        assert result_path.exists()
        data = json.loads(result_path.read_text())
        assert data["hook"] == "You did good today."

    def test_write_shot_list(self, writer):
        """Test writing shot_list.json."""
        paths = writer.create_run_directory("run-001", "test", "test")
        shot_list = [
            {"scene": 1, "beat": "HOOK"},
            {"scene": 2, "beat": "TENSION"},
        ]

        result_path = writer.write_shot_list(paths, shot_list)

        assert result_path.exists()
        data = json.loads(result_path.read_text())
        assert len(data) == 2

    def test_write_nanobanana_prompts(self, writer):
        """Test writing nanobanana_prompts.txt."""
        paths = writer.create_run_directory("run-001", "test", "test")
        prompts = "Scene 1: Cinematic sunrise over mountains\nScene 2: Person walking alone"

        result_path = writer.write_nanobanana_prompts(paths, prompts)

        assert result_path.exists()
        assert "Scene 1" in result_path.read_text()

    def test_write_run_log(self, writer):
        """Test writing run_log.txt."""
        paths = writer.create_run_directory("run-001", "test", "test")

        # Add some log events
        writer.log_event("test_event", {"key": "value"})
        writer.log_event("another_event")

        result_path = writer.write_run_log(paths)

        assert result_path.exists()
        content = result_path.read_text()
        assert "test_event" in content

    def test_clear_log(self, writer):
        """Test clearing log entries."""
        writer.log_event("event1")
        writer.log_event("event2")
        assert len(writer._log_entries) == 2

        writer.clear_log()
        assert len(writer._log_entries) == 0

    def test_get_output_summary(self, writer):
        """Test getting output summary."""
        paths = writer.create_run_directory("run-001", "test", "test")
        writer.write_config(paths, {"test": True})
        writer.write_script(paths, "Test script")

        summary = writer.get_output_summary(paths)

        assert summary["total_files"] >= 2
        assert "files" in summary

    def test_open_output_folder_linux(self, writer):
        """Test open folder command on Linux."""
        paths = writer.create_run_directory("run-001", "test", "test")

        with patch("platform.system", return_value="Linux"):
            cmd = writer.open_output_folder(paths)
            assert "xdg-open" in cmd

    def test_open_output_folder_macos(self, writer):
        """Test open folder command on macOS."""
        paths = writer.create_run_directory("run-001", "test", "test")

        with patch("platform.system", return_value="Darwin"):
            cmd = writer.open_output_folder(paths)
            assert "open" in cmd


class TestOutputPaths:
    """Test OutputPaths dataclass."""

    def test_all_files_list(self, tmp_path):
        """Test all_files returns all path fields."""
        paths = OutputPaths(
            base_dir=tmp_path,
            config=tmp_path / "config.json",
            script=tmp_path / "script.txt",
            script_meta=tmp_path / "script_meta.json",
            shot_list_json=tmp_path / "shot_list.json",
            shot_list_md=tmp_path / "shot_list.md",
            nanobanana_prompts=tmp_path / "nanobanana_prompts.txt",
            stock_queries=tmp_path / "stock_queries.txt",
            timeline=tmp_path / "timeline.json",
            timeline_aligned=tmp_path / "timeline_aligned.json",
            voiceover=tmp_path / "voiceover.mp3",
            word_timing=tmp_path / "word_timing.json",
            run_log=tmp_path / "run_log.txt",
            coherence_report=tmp_path / "coherence_report.json",
        )

        all_files = paths.all_files()
        assert len(all_files) == 13  # All file paths except base_dir

    def test_existing_files(self, tmp_path):
        """Test existing_files only returns files that exist."""
        paths = OutputPaths(
            base_dir=tmp_path,
            config=tmp_path / "config.json",
            script=tmp_path / "script.txt",
            script_meta=tmp_path / "script_meta.json",
            shot_list_json=tmp_path / "shot_list.json",
            shot_list_md=tmp_path / "shot_list.md",
            nanobanana_prompts=tmp_path / "nanobanana_prompts.txt",
            stock_queries=tmp_path / "stock_queries.txt",
            timeline=tmp_path / "timeline.json",
            timeline_aligned=tmp_path / "timeline_aligned.json",
            voiceover=tmp_path / "voiceover.mp3",
            word_timing=tmp_path / "word_timing.json",
            run_log=tmp_path / "run_log.txt",
            coherence_report=tmp_path / "coherence_report.json",
        )

        # Create only some files
        paths.config.write_text("{}")
        paths.script.write_text("test")

        existing = paths.existing_files()
        assert len(existing) == 2


class TestFindRunOutput:
    """Test finding existing run outputs."""

    def test_find_run_output(self, tmp_path):
        """Test finding an existing run."""
        # Create mock guard
        guard = MagicMock(spec=DriveGuard)
        guard.get_output_base.return_value = tmp_path

        # Create run directory structure
        run_dir = tmp_path / "motivation" / "affirming" / "2026-02-23" / "run-001"
        run_dir.mkdir(parents=True)
        (run_dir / "config.json").write_text("{}")

        paths = OutputWriter.find_run_output(guard, "run-001")

        assert paths is not None
        assert paths.base_dir == run_dir

    def test_find_run_output_not_found(self, tmp_path):
        """Test finding nonexistent run."""
        guard = MagicMock(spec=DriveGuard)
        guard.get_output_base.return_value = tmp_path

        paths = OutputWriter.find_run_output(guard, "nonexistent")
        assert paths is None
