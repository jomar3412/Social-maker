"""
Tests for sequential scene generation workflow.

Tests:
1. Only scene 1 is generated (ACTIVE) after script approval; scenes 2+ are PENDING
2. Locking a scene triggers generation of the next scene
3. Changing a scene's prompt marks downstream scenes as OUTDATED
4. Unlocking a locked scene works correctly
"""

import pytest
import tempfile
import os
from pathlib import Path

from content_engine.services.run_store import (
    RunStore, RunStage, ArtifactType, PromptStatus, PromptVersion
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture
def store(temp_db):
    """Create a RunStore with temporary database."""
    return RunStore(db_path=Path(temp_db))


@pytest.fixture
def run_id(store):
    """Create a test run and return its ID."""
    run_id = "test-seq-001"
    store.create_run(
        run_id=run_id,
        config={"niche": "motivation", "visual_mode": "hybrid"}
    )
    return run_id


class TestSequentialGeneration:
    """Tests for the sequential scene generation workflow."""

    def test_scene_1_active_others_pending(self, store, run_id):
        """After approval, only scene 1 should be ACTIVE; scenes 2+ should be PENDING."""
        # Simulate what _store_prompt_versions does after approval

        # Scene 1: ACTIVE with full prompt
        store.create_prompt_version(
            run_id=run_id,
            artifact_type=ArtifactType.NANOBANANA,
            item_key="scene_1",
            prompt_text="Full prompt for scene 1...",
            notes="Beat: HOOK",
            created_by="system",
            status=PromptStatus.ACTIVE,
        )

        # Scene 2: PENDING, waiting for scene 1
        store.create_prompt_version(
            run_id=run_id,
            artifact_type=ArtifactType.NANOBANANA,
            item_key="scene_2",
            prompt_text="",  # Empty placeholder
            notes="Beat: TENSION | Pending: waiting for scene_1 to be locked",
            created_by="system",
            status=PromptStatus.PENDING,
            depends_on_scene="scene_1",
        )

        # Scene 3: PENDING, waiting for scene 2
        store.create_prompt_version(
            run_id=run_id,
            artifact_type=ArtifactType.NANOBANANA,
            item_key="scene_3",
            prompt_text="",
            notes="Beat: SHIFT | Pending: waiting for scene_2 to be locked",
            created_by="system",
            status=PromptStatus.PENDING,
            depends_on_scene="scene_2",
        )

        # Verify scene 1 is ACTIVE
        scene1_prompts = store.get_prompt_history(
            run_id, ArtifactType.NANOBANANA, item_key="scene_1"
        )
        assert len(scene1_prompts) == 1
        assert scene1_prompts[0].status == PromptStatus.ACTIVE
        assert scene1_prompts[0].prompt_text != ""

        # Verify scenes 2 and 3 are PENDING
        scene2_prompts = store.get_prompt_history(
            run_id, ArtifactType.NANOBANANA, item_key="scene_2"
        )
        assert len(scene2_prompts) == 1
        assert scene2_prompts[0].status == PromptStatus.PENDING
        assert scene2_prompts[0].depends_on_scene == "scene_1"

        scene3_prompts = store.get_prompt_history(
            run_id, ArtifactType.NANOBANANA, item_key="scene_3"
        )
        assert len(scene3_prompts) == 1
        assert scene3_prompts[0].status == PromptStatus.PENDING
        assert scene3_prompts[0].depends_on_scene == "scene_2"

    def test_lock_prompt_sets_locked_status(self, store, run_id):
        """Locking a prompt should set its status to LOCKED."""
        # Create an ACTIVE prompt for scene 1
        prompt = store.create_prompt_version(
            run_id=run_id,
            artifact_type=ArtifactType.NANOBANANA,
            item_key="scene_1",
            prompt_text="Scene 1 prompt content",
            notes="Beat: HOOK",
            created_by="system",
            status=PromptStatus.ACTIVE,
        )

        # Lock the prompt
        success = store.lock_prompt(prompt.id)
        assert success

        # Verify it's locked
        updated_prompt = store.get_prompt_version(prompt.id)
        assert updated_prompt.status == PromptStatus.LOCKED
        assert updated_prompt.locked_at is not None

    def test_unlock_prompt_returns_to_active(self, store, run_id):
        """Unlocking a LOCKED prompt should return it to ACTIVE."""
        # Create and lock a prompt
        prompt = store.create_prompt_version(
            run_id=run_id,
            artifact_type=ArtifactType.NANOBANANA,
            item_key="scene_1",
            prompt_text="Scene 1 prompt content",
            notes="Beat: HOOK",
            created_by="system",
            status=PromptStatus.ACTIVE,
        )
        store.lock_prompt(prompt.id)

        # Unlock it
        success = store.unlock_prompt(prompt.id)
        assert success

        # Verify it's back to ACTIVE
        updated_prompt = store.get_prompt_version(prompt.id)
        assert updated_prompt.status == PromptStatus.ACTIVE
        assert updated_prompt.locked_at is None

    def test_mark_downstream_outdated(self, store, run_id):
        """When a scene changes, downstream scenes should be marked OUTDATED."""
        # Create prompts for 3 scenes
        store.create_prompt_version(
            run_id=run_id,
            artifact_type=ArtifactType.NANOBANANA,
            item_key="scene_1",
            prompt_text="Scene 1 prompt",
            notes="Beat: HOOK",
            created_by="system",
            status=PromptStatus.LOCKED,  # Already locked
        )

        store.create_prompt_version(
            run_id=run_id,
            artifact_type=ArtifactType.NANOBANANA,
            item_key="scene_2",
            prompt_text="Scene 2 prompt",
            notes="Beat: TENSION",
            created_by="system",
            status=PromptStatus.LOCKED,  # Already locked
            depends_on_scene="scene_1",
        )

        store.create_prompt_version(
            run_id=run_id,
            artifact_type=ArtifactType.NANOBANANA,
            item_key="scene_3",
            prompt_text="Scene 3 prompt",
            notes="Beat: SHIFT",
            created_by="system",
            status=PromptStatus.ACTIVE,
            depends_on_scene="scene_2",
        )

        # Mark downstream scenes as outdated starting from scene 1
        count = store.mark_downstream_outdated(
            run_id=run_id,
            artifact_type=ArtifactType.NANOBANANA,
            changed_scene_key="scene_1",
        )

        # Should have marked 2 downstream scenes (scene_2 and scene_3)
        assert count == 2

        # Verify scene 2 is OUTDATED
        scene2_prompts = store.get_prompt_history(run_id, ArtifactType.NANOBANANA, item_key="scene_2")
        scene2 = scene2_prompts[0] if scene2_prompts else None
        assert scene2 is not None
        assert scene2.status == PromptStatus.OUTDATED

        # Verify scene 3 is OUTDATED
        scene3_prompts = store.get_prompt_history(run_id, ArtifactType.NANOBANANA, item_key="scene_3")
        scene3 = scene3_prompts[0] if scene3_prompts else None
        assert scene3 is not None
        assert scene3.status == PromptStatus.OUTDATED

    def test_scene_generation_status(self, store, run_id):
        """Test getting the generation status for all scenes."""
        # Create prompts in various states
        p1 = store.create_prompt_version(
            run_id=run_id,
            artifact_type=ArtifactType.NANOBANANA,
            item_key="scene_1",
            prompt_text="Scene 1",
            notes="",
            created_by="system",
            status=PromptStatus.ACTIVE,
        )
        # Lock scene 1
        store.lock_prompt(p1.id)

        p2 = store.create_prompt_version(
            run_id=run_id,
            artifact_type=ArtifactType.NANOBANANA,
            item_key="scene_2",
            prompt_text="Scene 2",
            notes="",
            created_by="system",
            status=PromptStatus.ACTIVE,
            depends_on_scene="scene_1",
        )
        # Lock scene 2 as well
        store.lock_prompt(p2.id)

        store.create_prompt_version(
            run_id=run_id,
            artifact_type=ArtifactType.NANOBANANA,
            item_key="scene_3",
            prompt_text="",
            notes="",
            created_by="system",
            status=PromptStatus.PENDING,
            depends_on_scene="scene_2",
        )

        # Get scene status (returns a list of dicts)
        status_list = store.get_scene_generation_status(run_id, ArtifactType.NANOBANANA)

        # Convert to dict for easier assertions
        status = {s["item_key"]: s for s in status_list}

        assert "scene_1" in status
        assert status["scene_1"]["status"] == "locked"
        assert status["scene_1"]["can_generate"] is False  # Already has content

        assert "scene_2" in status
        assert status["scene_2"]["status"] == "locked"
        assert status["scene_2"]["can_generate"] is False  # Already has content

        assert "scene_3" in status
        assert status["scene_3"]["status"] == "pending"
        # scene_3 can generate because scene_2 is LOCKED (required for sequential)
        assert status["scene_3"]["can_generate"] is True

    def test_prompt_version_scene_number_property(self, store, run_id):
        """Test that scene_number property correctly extracts scene number."""
        prompt = store.create_prompt_version(
            run_id=run_id,
            artifact_type=ArtifactType.NANOBANANA,
            item_key="scene_5",
            prompt_text="Scene 5 content",
            notes="",
            created_by="system",
            status=PromptStatus.ACTIVE,
        )

        assert prompt.scene_number == 5

    def test_get_locked_prompt_for_scene(self, store, run_id):
        """Test retrieving locked prompt for a specific scene."""
        # Create an active and then locked prompt
        prompt = store.create_prompt_version(
            run_id=run_id,
            artifact_type=ArtifactType.NANOBANANA,
            item_key="scene_1",
            prompt_text="Scene 1 locked content",
            notes="",
            created_by="system",
            status=PromptStatus.ACTIVE,
        )
        store.lock_prompt(prompt.id)

        # Retrieve the locked prompt
        locked = store.get_locked_prompt_for_scene(run_id, ArtifactType.NANOBANANA, "scene_1")
        assert locked is not None
        assert locked.status == PromptStatus.LOCKED
        assert locked.prompt_text == "Scene 1 locked content"

    def test_clear_continuity_warning(self, store, run_id):
        """Test clearing continuity warning from a prompt."""
        prompt = store.create_prompt_version(
            run_id=run_id,
            artifact_type=ArtifactType.NANOBANANA,
            item_key="scene_2",
            prompt_text="Scene 2",
            notes="",
            created_by="system",
            status=PromptStatus.OUTDATED,
        )

        # Set a continuity warning using sqlite3 directly
        import sqlite3
        with sqlite3.connect(store.db_path) as conn:
            conn.execute(
                "UPDATE prompt_versions SET continuity_warning = ? WHERE id = ?",
                ("Previous scene changed", prompt.id)
            )

        # Clear the warning
        store.clear_continuity_warning(prompt.id)

        # Verify warning is cleared
        updated_prompt = store.get_prompt_version(prompt.id)
        assert updated_prompt.continuity_warning is None


class TestPromptVersionModel:
    """Tests for PromptVersion dataclass behavior."""

    def test_scene_number_extraction_various_formats(self):
        """Test scene number extraction from various item_key formats."""
        # Valid scene keys
        pv1 = PromptVersion(
            id=1, run_id="r1", artifact_type=ArtifactType.NANOBANANA,
            item_key="scene_1", version=1, prompt_text="", notes="",
            created_at="", created_by="", status=PromptStatus.ACTIVE
        )
        assert pv1.scene_number == 1

        pv10 = PromptVersion(
            id=2, run_id="r1", artifact_type=ArtifactType.NANOBANANA,
            item_key="scene_10", version=1, prompt_text="", notes="",
            created_at="", created_by="", status=PromptStatus.ACTIVE
        )
        assert pv10.scene_number == 10

        # Invalid formats should return None
        pv_invalid = PromptVersion(
            id=3, run_id="r1", artifact_type=ArtifactType.NANOBANANA,
            item_key="not_a_scene", version=1, prompt_text="", notes="",
            created_at="", created_by="", status=PromptStatus.ACTIVE
        )
        assert pv_invalid.scene_number is None

        pv_empty = PromptVersion(
            id=4, run_id="r1", artifact_type=ArtifactType.NANOBANANA,
            item_key=None, version=1, prompt_text="", notes="",
            created_at="", created_by="", status=PromptStatus.ACTIVE
        )
        assert pv_empty.scene_number is None


class TestStorePromptVersionsFunction:
    """Tests for the _store_prompt_versions background runner function."""

    def test_store_prompt_versions_creates_scene_1_active(self, store, run_id):
        """
        Test that _store_prompt_versions creates Scene 1 as ACTIVE and others as PENDING.

        This is the core test for the issue: after script approval, prompts should appear.
        """
        from content_engine.services.background_runner import _store_prompt_versions

        # Simulate shot list from orchestrator
        shot_list = [
            {
                "scene_number": 1,
                "beat_type": "HOOK",
                "duration": 3.0,
                "nano_prompt": "Scene 1 NanoBanana prompt with all details",
                "search_tight": "person silhouette",
                "search_broad": "dramatic lighting",
                "negative_search": ["watermark", "logo"],
            },
            {
                "scene_number": 2,
                "beat_type": "TENSION",
                "duration": 5.0,
                "nano_prompt": "Scene 2 NanoBanana prompt",
                "search_tight": "focused person",
                "search_broad": "office scene",
                "negative_search": ["cartoon"],
            },
            {
                "scene_number": 3,
                "beat_type": "RESOLUTION",
                "duration": 4.0,
                "nano_prompt": "Scene 3 NanoBanana prompt",
                "search_tight": "sunrise",
                "search_broad": "hope",
                "negative_search": [],
            },
        ]

        # Call the function
        _store_prompt_versions(run_id, shot_list, "hybrid", store)

        # Verify prompts were created
        nano_prompts = store.get_prompts_for_artifacts(run_id, ArtifactType.NANOBANANA)
        stock_prompts = store.get_prompts_for_artifacts(run_id, ArtifactType.STOCK_QUERY)

        # Should have 3 NanoBanana prompts and 3 stock queries
        assert len(nano_prompts) == 3
        assert len(stock_prompts) == 3

        # Check Scene 1 is ACTIVE with full prompt text
        scene_1_nano = next((p for p in nano_prompts if p.item_key == "scene_1"), None)
        assert scene_1_nano is not None
        assert scene_1_nano.status == PromptStatus.ACTIVE
        assert scene_1_nano.prompt_text == "Scene 1 NanoBanana prompt with all details"

        # Check Scene 2 is PENDING with empty prompt text
        scene_2_nano = next((p for p in nano_prompts if p.item_key == "scene_2"), None)
        assert scene_2_nano is not None
        assert scene_2_nano.status == PromptStatus.PENDING
        assert scene_2_nano.prompt_text == ""
        assert scene_2_nano.depends_on_scene == "scene_1"

        # Check Scene 3 is PENDING
        scene_3_nano = next((p for p in nano_prompts if p.item_key == "scene_3"), None)
        assert scene_3_nano is not None
        assert scene_3_nano.status == PromptStatus.PENDING
        assert scene_3_nano.depends_on_scene == "scene_2"

    def test_get_prompts_for_artifacts_returns_active_and_pending(self, store, run_id):
        """Test that get_prompts_for_artifacts returns ACTIVE, PENDING, and LOCKED prompts."""
        # Create prompts in various states
        store.create_prompt_version(
            run_id=run_id,
            artifact_type=ArtifactType.NANOBANANA,
            item_key="scene_1",
            prompt_text="Scene 1",
            status=PromptStatus.ACTIVE,
        )
        store.create_prompt_version(
            run_id=run_id,
            artifact_type=ArtifactType.NANOBANANA,
            item_key="scene_2",
            prompt_text="",
            status=PromptStatus.PENDING,
            depends_on_scene="scene_1",
        )
        store.create_prompt_version(
            run_id=run_id,
            artifact_type=ArtifactType.NANOBANANA,
            item_key="scene_3",
            prompt_text="",
            status=PromptStatus.PENDING,
            depends_on_scene="scene_2",
        )

        # Create a superseded version (should NOT be returned)
        p_superseded = store.create_prompt_version(
            run_id=run_id,
            artifact_type=ArtifactType.NANOBANANA,
            item_key="scene_4",
            prompt_text="Old version",
            status=PromptStatus.ACTIVE,
        )
        # Now supersede it by creating a new version
        import sqlite3
        with sqlite3.connect(store.db_path) as conn:
            conn.execute(
                "UPDATE prompt_versions SET status = ? WHERE id = ?",
                (PromptStatus.SUPERSEDED.value, p_superseded.id)
            )

        # Get prompts for artifacts
        prompts = store.get_prompts_for_artifacts(run_id, ArtifactType.NANOBANANA)

        # Should return 3 prompts (scene_1 ACTIVE, scene_2 PENDING, scene_3 PENDING)
        # Should NOT return scene_4 (SUPERSEDED)
        assert len(prompts) == 3
        assert any(p.item_key == "scene_1" and p.status == PromptStatus.ACTIVE for p in prompts)
        assert any(p.item_key == "scene_2" and p.status == PromptStatus.PENDING for p in prompts)
        assert any(p.item_key == "scene_3" and p.status == PromptStatus.PENDING for p in prompts)
        assert not any(p.status == PromptStatus.SUPERSEDED for p in prompts)

    def test_get_prompts_for_artifacts_includes_locked(self, store, run_id):
        """Test that get_prompts_for_artifacts includes LOCKED prompts."""
        p1 = store.create_prompt_version(
            run_id=run_id,
            artifact_type=ArtifactType.NANOBANANA,
            item_key="scene_1",
            prompt_text="Scene 1",
            status=PromptStatus.ACTIVE,
        )
        # Lock it
        store.lock_prompt(p1.id)

        prompts = store.get_prompts_for_artifacts(run_id, ArtifactType.NANOBANANA)

        assert len(prompts) == 1
        assert prompts[0].status == PromptStatus.LOCKED


class TestWorkflowStage:
    """Tests for the WorkflowStage enum and workflow transitions."""

    def test_workflow_stage_display_name(self):
        """Test WorkflowStage display_name property."""
        from content_engine.services.run_store import WorkflowStage

        assert WorkflowStage.SCRIPT_PENDING.display_name == "Script"
        assert WorkflowStage.VISUALS_PENDING.display_name == "Visuals"
        assert WorkflowStage.VIDEO_PENDING.display_name == "Video"
        assert WorkflowStage.READY_TO_POST.display_name == "Ready"
        assert WorkflowStage.POSTED.display_name == "Posted"
        assert WorkflowStage.REVIEW_READY.display_name == "Review"

    def test_workflow_stage_badge_classes(self):
        """Test WorkflowStage badge_classes property."""
        from content_engine.services.run_store import WorkflowStage

        assert "yellow" in WorkflowStage.SCRIPT_PENDING.badge_classes
        assert "blue" in WorkflowStage.VISUALS_PENDING.badge_classes
        assert "purple" in WorkflowStage.VIDEO_PENDING.badge_classes
        assert "green" in WorkflowStage.READY_TO_POST.badge_classes
        assert "emerald" in WorkflowStage.POSTED.badge_classes or "green" in WorkflowStage.POSTED.badge_classes

    def test_workflow_stage_is_posted(self):
        """Test WorkflowStage is_posted method."""
        from content_engine.services.run_store import WorkflowStage

        assert WorkflowStage.POSTED.is_posted() is True
        assert WorkflowStage.REVIEW_READY.is_posted() is True
        assert WorkflowStage.READY_TO_POST.is_posted() is False
        assert WorkflowStage.SCRIPT_PENDING.is_posted() is False

    def test_compute_workflow_stage_script_pending(self, store, run_id):
        """Test compute_workflow_stage returns SCRIPT_PENDING for awaiting approval runs."""
        from content_engine.services.run_store import WorkflowStage

        store.update_stage(run_id, RunStage.AWAITING_SCRIPT_APPROVAL)

        stage = store.compute_workflow_stage(run_id)
        assert stage == WorkflowStage.SCRIPT_PENDING

    def test_compute_workflow_stage_visuals_pending(self, store, run_id):
        """Test compute_workflow_stage returns VISUALS_PENDING after script approval."""
        from content_engine.services.run_store import WorkflowStage

        store.update_stage(run_id, RunStage.SCRIPT_APPROVED)

        stage = store.compute_workflow_stage(run_id)
        assert stage == WorkflowStage.VISUALS_PENDING

    def test_compute_workflow_stage_posted(self, store, run_id):
        """Test compute_workflow_stage returns POSTED after post_run."""
        from content_engine.services.run_store import WorkflowStage

        store.update_stage(run_id, RunStage.COMPLETE)
        store.post_run(run_id)

        stage = store.compute_workflow_stage(run_id)
        assert stage == WorkflowStage.POSTED

    def test_get_queue_runs(self, store):
        """Test get_queue_runs returns only non-posted runs."""
        # Create two runs
        store.create_run("queue-run-1", {"niche": "test"})
        store.create_run("queue-run-2", {"niche": "test"})

        # Post the second run
        store.post_run("queue-run-2")

        # Get queue runs
        queue_runs = store.get_queue_runs()

        # Should only return queue-run-1 (not posted)
        run_ids = [r.run_id for r in queue_runs]
        assert "queue-run-1" in run_ids
        assert "queue-run-2" not in run_ids

    def test_get_posted_runs(self, store):
        """Test get_posted_runs returns only posted runs."""
        # Create two runs
        store.create_run("posted-run-1", {"niche": "test"})
        store.create_run("posted-run-2", {"niche": "test"})

        # Post the first run
        store.post_run("posted-run-1")

        # Get posted runs
        posted_runs = store.get_posted_runs()

        # Should only return posted-run-1
        run_ids = [r.run_id for r in posted_runs]
        assert "posted-run-1" in run_ids
        assert "posted-run-2" not in run_ids

    def test_post_run(self, store, run_id):
        """Test post_run sets posted_at timestamp."""
        # Verify no posted_at initially
        record = store.get_run(run_id)
        assert record.posted_at is None

        # Post the run
        success = store.post_run(run_id)
        assert success is True

        # Verify posted_at is set
        record = store.get_run(run_id)
        assert record.posted_at is not None

    def test_post_run_nonexistent(self, store):
        """Test post_run returns False for nonexistent run."""
        success = store.post_run("nonexistent-run")
        assert success is False

    def test_workflow_progress(self, store, run_id):
        """Test RunRecord workflow_progress property."""
        from content_engine.services.run_store import WorkflowStage

        # Script pending stage
        store.update_stage(run_id, RunStage.AWAITING_SCRIPT_APPROVAL)
        record = store.get_run(run_id)

        progress = record.workflow_progress
        assert progress["script_done"] is False
        assert progress["visuals_done"] is False
        assert progress["video_done"] is False
        assert progress["posted"] is False

        # Complete and post
        store.update_stage(run_id, RunStage.COMPLETE)
        store.post_run(run_id)
        record = store.get_run(run_id)

        progress = record.workflow_progress
        assert progress["script_done"] is True
        assert progress["visuals_done"] is True
        assert progress["video_done"] is True
        assert progress["posted"] is True
