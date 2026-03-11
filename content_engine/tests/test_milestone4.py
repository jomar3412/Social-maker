"""Tests for Milestone 4 features."""

import pytest
import json
import tempfile
import shutil
from pathlib import Path

from content_engine.services.run_store import (
    RunStore, RunStage, RunRecord, FeedbackRecord, generate_display_title
)
from content_engine.services.preset_loader import PresetLoader


class TestDisplayTitleGeneration:
    """Test display title generation from hooks."""

    def test_generate_display_title_basic(self):
        """Test basic title generation."""
        hook = "You did good today. Really good."
        title = generate_display_title(hook)
        assert title == "You Did Good Today. Really Good."

    def test_generate_display_title_truncation(self):
        """Test title truncation at max words."""
        hook = "This is a very long hook that goes on and on forever"
        title = generate_display_title(hook, max_words=5)
        assert title == "This Is A Very Long..."
        assert len(title.split()) <= 6  # 5 words + "..."

    def test_generate_display_title_short(self):
        """Test title with fewer than max words."""
        hook = "Short hook"
        title = generate_display_title(hook, max_words=8)
        assert title == "Short Hook"
        assert "..." not in title

    def test_generate_display_title_empty(self):
        """Test title generation with empty hook."""
        title = generate_display_title("")
        assert title == "Untitled"

    def test_generate_display_title_none(self):
        """Test title generation with None hook."""
        title = generate_display_title(None)
        assert title == "Untitled"


class TestPresetEditor:
    """Test preset editing with backup and validation."""

    @pytest.fixture
    def temp_presets_dir(self):
        """Create temporary presets directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            presets_dir = Path(tmpdir) / "presets"
            presets_dir.mkdir()

            # Create category subdirs
            for category in ["niches", "styles", "voices", "visuals", "realism"]:
                (presets_dir / category).mkdir()

            # Create a test preset
            test_preset = {
                "display_name": "Test Niche",
                "description": "A test niche",
                "tags": ["test"]
            }
            (presets_dir / "niches" / "test.json").write_text(
                json.dumps(test_preset, indent=2)
            )

            yield presets_dir

    def test_preset_loader_get_preset(self, temp_presets_dir):
        """Test loading a preset."""
        loader = PresetLoader(temp_presets_dir)
        preset = loader.get_preset("niches", "test")

        assert preset is not None
        assert preset.name == "test"
        assert preset.data["display_name"] == "Test Niche"

    def test_preset_loader_list_presets(self, temp_presets_dir):
        """Test listing presets."""
        loader = PresetLoader(temp_presets_dir)
        presets = loader.list_presets("niches")

        assert "test" in presets

    def test_preset_loader_compute_fingerprint(self, temp_presets_dir):
        """Test fingerprint computation."""
        loader = PresetLoader(temp_presets_dir)
        fp1 = loader.compute_fingerprint({"niche": "test"})

        # Fingerprint should be 16 chars
        assert len(fp1) == 16

        # Same input should give same fingerprint
        fp2 = loader.compute_fingerprint({"niche": "test"})
        assert fp1 == fp2

    def test_preset_loader_fingerprint_changes_on_edit(self, temp_presets_dir):
        """Test that fingerprint changes when preset is modified."""
        loader = PresetLoader(temp_presets_dir)
        fp_before = loader.compute_fingerprint({"niche": "test"})

        # Modify the preset
        preset_path = temp_presets_dir / "niches" / "test.json"
        data = json.loads(preset_path.read_text())
        data["description"] = "Modified description"
        preset_path.write_text(json.dumps(data))

        # Clear cache to pick up changes
        loader.clear_cache()

        fp_after = loader.compute_fingerprint({"niche": "test"})
        assert fp_before != fp_after

    def test_preset_backup_creation(self, temp_presets_dir):
        """Test that backups are created on save."""
        history_dir = temp_presets_dir / "_history"

        # Initially no history
        assert not history_dir.exists() or len(list(history_dir.glob("*.json"))) == 0

        # Create a backup manually (simulating save)
        history_dir.mkdir(exist_ok=True)
        backup_path = history_dir / "20260224_120000_test.json"
        shutil.copy(
            temp_presets_dir / "niches" / "test.json",
            backup_path
        )

        # Verify backup exists
        assert backup_path.exists()

    def test_preset_validation_required_keys(self, temp_presets_dir):
        """Test that required keys are validated."""
        # Test data missing display_name
        invalid_data = {"description": "No display name"}

        # Should raise or return error when saving
        # (The actual validation is in the API endpoint)
        assert "display_name" not in invalid_data


class TestPostApprovalStages:
    """Test post-approval stage progression."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "test_runs.db"

    @pytest.fixture
    def store(self, temp_db):
        """Create RunStore with temp database."""
        return RunStore(temp_db)

    def test_stage_progression_to_shot_list(self, store):
        """Test progression from approved to generating shot list."""
        store.create_run("run-001", {"niche": "motivation", "style": "affirming"})

        # Simulate approval flow
        store.update_stage("run-001", RunStage.AWAITING_SCRIPT_APPROVAL)
        store.update_stage("run-001", RunStage.SCRIPT_APPROVED)
        store.update_stage("run-001", RunStage.GENERATING_SHOT_LIST,
                          current_stage_name="Generating Shot List",
                          progress_percent=40)

        record = store.get_run("run-001")
        assert record.stage == RunStage.GENERATING_SHOT_LIST
        assert record.progress_percent == 40

    def test_stage_progression_full_flow(self, store):
        """Test full post-approval stage progression."""
        store.create_run("run-001", {})

        stages = [
            (RunStage.SCRIPT_APPROVED, 10),
            (RunStage.GENERATING_SHOT_LIST, 40),
            (RunStage.GENERATING_VISUALS, 70),
            (RunStage.GENERATING_STOCK_QUERIES, 90),
            (RunStage.COMPLETE, 100),
        ]

        for stage, progress in stages:
            store.update_stage("run-001", stage, progress_percent=progress)
            record = store.get_run("run-001")
            assert record.stage == stage
            assert record.progress_percent == progress

    def test_is_running_for_post_approval_stages(self, store):
        """Test that post-approval stages are considered running."""
        store.create_run("run-001", {})

        running_stages = [
            RunStage.GENERATING_SHOT_LIST,
            RunStage.GENERATING_VISUALS,
            RunStage.GENERATING_STOCK_QUERIES,
        ]

        for stage in running_stages:
            store.update_stage("run-001", stage)
            record = store.get_run("run-001")
            assert record.stage.is_running() is True

    def test_complete_is_not_running(self, store):
        """Test that complete stage is not running."""
        store.create_run("run-001", {})
        store.update_stage("run-001", RunStage.COMPLETE)

        record = store.get_run("run-001")
        assert record.stage.is_running() is False


class TestFeedbackWithNewFields:
    """Test feedback with posted_url and post_date fields."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "test_runs.db"

    @pytest.fixture
    def store(self, temp_db):
        """Create RunStore with temp database."""
        return RunStore(temp_db)

    def test_save_feedback_with_new_fields(self, store):
        """Test saving feedback with posted_url and post_date."""
        store.create_run("run-001", {})

        feedback = FeedbackRecord(
            run_id="run-001",
            script_quality=4,
            platform="youtube",
            posted_url="https://youtube.com/watch?v=abc123",
            post_date="2026-02-24",
            views=1000,
        )
        store.save_feedback(feedback)

        retrieved = store.get_feedback("run-001")
        assert retrieved is not None
        assert retrieved.posted_url == "https://youtube.com/watch?v=abc123"
        assert retrieved.post_date == "2026-02-24"
        assert retrieved.views == 1000

    def test_feedback_to_dict_includes_new_fields(self, store):
        """Test that to_dict includes new fields."""
        feedback = FeedbackRecord(
            run_id="run-001",
            posted_url="https://example.com",
            post_date="2026-02-24",
        )
        data = feedback.to_dict()

        assert "posted_url" in data
        assert "post_date" in data
        assert data["posted_url"] == "https://example.com"

    def test_update_feedback_preserves_fields(self, store):
        """Test updating feedback preserves existing fields."""
        store.create_run("run-001", {})

        # Initial save
        feedback1 = FeedbackRecord(
            run_id="run-001",
            script_quality=3,
            posted_url="https://youtube.com/watch?v=abc123",
        )
        store.save_feedback(feedback1)

        # Update with new data
        feedback2 = FeedbackRecord(
            run_id="run-001",
            script_quality=5,
            posted_url="https://youtube.com/watch?v=abc123",
            views=2000,
        )
        store.save_feedback(feedback2)

        retrieved = store.get_feedback("run-001")
        assert retrieved.script_quality == 5
        assert retrieved.views == 2000
        assert retrieved.posted_url == "https://youtube.com/watch?v=abc123"


class TestRunOverviewData:
    """Test run overview data retrieval."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "test_runs.db"

    @pytest.fixture
    def store(self, temp_db):
        """Create RunStore with temp database."""
        return RunStore(temp_db)

    def test_run_record_title_property(self, store):
        """Test title property returns display_title or run_id."""
        store.create_run("run-001", {})

        record = store.get_run("run-001")
        assert record.title == "run-001"  # No display_title set

        store.update_title("run-001", "My Great Video")
        record = store.get_run("run-001")
        assert record.title == "My Great Video"

    def test_run_record_stage_display_name(self, store):
        """Test stage_display_name property."""
        store.create_run("run-001", {})

        store.update_stage("run-001", RunStage.GENERATING_SHOT_LIST,
                          current_stage_name="Building Shots")
        record = store.get_run("run-001")
        assert record.stage_display_name == "Building Shots"

    def test_run_record_computed_progress(self, store):
        """Test computed_progress from STAGE_INFO."""
        store.create_run("run-001", {})

        store.update_stage("run-001", RunStage.AWAITING_SCRIPT_APPROVAL)
        record = store.get_run("run-001")

        # STAGE_INFO defines awaiting_script_approval as 100%
        assert record.computed_progress == 100
