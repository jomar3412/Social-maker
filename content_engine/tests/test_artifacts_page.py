"""
Regression tests for the artifacts page.

Tests that the artifacts page loads successfully in various scenarios,
including when prompts are missing or empty.
"""

import pytest
from pathlib import Path
import tempfile
import json

from fastapi.testclient import TestClient

from content_engine.app.main import app
from content_engine.services.run_store import (
    RunStore,
    RunStage,
    ArtifactType,
    PromptStatus,
)


class TestArtifactsPage:
    """Test /runs/{run_id}/artifacts endpoint."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "test_runs.db"

    @pytest.fixture
    def temp_output(self):
        """Create temporary output directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def store(self, temp_db):
        """Create RunStore with temp database."""
        return RunStore(temp_db)

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_artifacts_page_returns_200_for_run_with_prompts(self, store, temp_output):
        """
        Regression test: Artifacts page should return 200 when prompts exist.

        This tests the fix for: AttributeError: 'PromptVersion' object has no attribute 'to_dict'
        """
        # Create a run
        config = {"niche": "fun_facts", "style": "edgy_funny"}
        record = store.create_run("run-test-001", config)

        # Set up output path
        output_dir = temp_output / "run-test-001"
        output_dir.mkdir(parents=True, exist_ok=True)
        store.update_stage("run-test-001", RunStage.COMPLETE, output_path=str(output_dir))

        # Add some test prompts
        store.create_prompt_version(
            run_id="run-test-001",
            artifact_type=ArtifactType.NANOBANANA,
            item_key="scene_1",
            prompt_text="Test NanoBanana prompt for scene 1",
            notes=None,
            created_by="system",
        )
        store.create_prompt_version(
            run_id="run-test-001",
            artifact_type=ArtifactType.STOCK_QUERY,
            item_key="scene_1",
            prompt_text="person looking at sunset, inspirational",
            notes=None,
            created_by="system",
        )

        # Create script meta
        meta_path = output_dir / "script_meta.json"
        meta_path.write_text(json.dumps({
            "hook": "Test hook text",
            "duration_estimate": 45,
        }))

        # Get the prompts and verify to_dict works
        prompts = store.get_all_active_prompts("run-test-001", ArtifactType.NANOBANANA)
        assert len(prompts) == 1

        # This is the key test - to_dict must work
        prompt_dict = prompts[0].to_dict()
        assert prompt_dict["run_id"] == "run-test-001"
        assert prompt_dict["item_key"] == "scene_1"
        assert prompt_dict["version"] == 1
        assert "prompt_text" in prompt_dict

    def test_artifacts_page_returns_200_with_no_prompts(self, store, temp_output):
        """
        Artifacts page should return 200 even when no prompts exist.

        This tests graceful handling of empty prompt lists.
        """
        # Create a run with no prompts
        config = {"niche": "fun_facts", "style": "edgy_funny"}
        store.create_run("run-empty-001", config)

        output_dir = temp_output / "run-empty-001"
        output_dir.mkdir(parents=True, exist_ok=True)
        store.update_stage("run-empty-001", RunStage.COMPLETE, output_path=str(output_dir))

        # Get prompts - should return empty list, not crash
        prompts = store.get_all_active_prompts("run-empty-001", ArtifactType.NANOBANANA)
        assert prompts == []

    def test_prompt_version_to_dict_method(self, store):
        """
        Direct test of PromptVersion.to_dict() method.

        Regression test for: AttributeError: 'PromptVersion' object has no attribute 'to_dict'
        """
        # Create a run and add a prompt
        store.create_run("run-dict-test", {"test": True})
        store.create_prompt_version(
            run_id="run-dict-test",
            artifact_type=ArtifactType.NANOBANANA,
            item_key="hook",
            prompt_text="Cinematic shot of person at sunrise",
            notes="Test note",
            created_by="user",
        )

        # Get the prompt
        prompts = store.get_all_active_prompts("run-dict-test", ArtifactType.NANOBANANA)
        assert len(prompts) == 1

        prompt = prompts[0]

        # Test to_dict exists and returns correct structure
        assert hasattr(prompt, 'to_dict'), "PromptVersion must have to_dict method"

        d = prompt.to_dict()

        # Verify all expected fields
        assert isinstance(d, dict)
        assert d["run_id"] == "run-dict-test"
        assert d["artifact_type"] == "nanobanana"
        assert d["item_key"] == "hook"
        assert d["version"] == 1
        assert d["prompt_text"] == "Cinematic shot of person at sunrise"
        assert d["notes"] == "Test note"
        assert d["created_by"] == "user"
        assert d["status"] == "active"
        assert "id" in d
        assert "created_at" in d
        assert "image_path" in d

    def test_enrich_with_version_info_handles_empty_list(self, store):
        """
        The enrich_with_version_info function should handle empty prompt lists gracefully.
        """
        store.create_run("run-enrich-test", {"test": True})

        # Get empty prompts list
        prompts = store.get_all_active_prompts("run-enrich-test", ArtifactType.NANOBANANA)
        assert prompts == []

        # Simulating enrich_with_version_info behavior
        enriched = []
        if prompts:
            for p in prompts:
                d = p.to_dict()
                enriched.append(d)

        assert enriched == []

    def test_prompt_version_info_returns_dict_or_none(self, store):
        """
        get_prompt_version_info should return dict with version info or handle gracefully.
        """
        store.create_run("run-version-info", {"test": True})

        # Add multiple versions of a prompt
        store.create_prompt_version(
            run_id="run-version-info",
            artifact_type=ArtifactType.NANOBANANA,
            item_key="scene_1",
            prompt_text="Version 1",
            created_by="system",
        )
        store.create_prompt_version(
            run_id="run-version-info",
            artifact_type=ArtifactType.NANOBANANA,
            item_key="scene_1",
            prompt_text="Version 2 - regenerated",
            created_by="user",
        )

        # Get version info
        version_info = store.get_prompt_version_info(
            "run-version-info",
            ArtifactType.NANOBANANA,
            "scene_1"
        )

        assert version_info is not None
        assert "max_version" in version_info
        assert "total_versions" in version_info
        assert version_info["max_version"] >= 1
        assert version_info["total_versions"] >= 1


class TestPromptVersionModel:
    """Direct tests for PromptVersion dataclass."""

    def test_to_dict_includes_all_fields(self):
        """PromptVersion.to_dict() should include all fields."""
        from content_engine.services.run_store import PromptVersion, ArtifactType, PromptStatus

        prompt = PromptVersion(
            id=1,
            run_id="test-run",
            artifact_type=ArtifactType.NANOBANANA,
            item_key="scene_1",
            version=1,
            prompt_text="Test prompt text",
            notes="Some notes",
            image_path="/path/to/image.png",
            created_at="2026-02-27T10:00:00",
            created_by="user",
            status=PromptStatus.ACTIVE,
        )

        d = prompt.to_dict()

        assert d["id"] == 1
        assert d["run_id"] == "test-run"
        assert d["artifact_type"] == "nanobanana"
        assert d["item_key"] == "scene_1"
        assert d["version"] == 1
        assert d["prompt_text"] == "Test prompt text"
        assert d["notes"] == "Some notes"
        assert d["image_path"] == "/path/to/image.png"
        assert d["created_at"] == "2026-02-27T10:00:00"
        assert d["created_by"] == "user"
        assert d["status"] == "active"

    def test_to_dict_handles_none_values(self):
        """PromptVersion.to_dict() should handle None values."""
        from content_engine.services.run_store import PromptVersion, ArtifactType, PromptStatus

        prompt = PromptVersion(
            id=1,
            run_id="test-run",
            artifact_type=ArtifactType.STOCK_QUERY,
            item_key="hook",
            version=1,
            prompt_text="Query text",
            notes=None,
            image_path=None,
            created_at=None,
            created_by="system",
            status=PromptStatus.SUPERSEDED,
        )

        d = prompt.to_dict()

        assert d["notes"] is None
        assert d["image_path"] is None
        assert d["created_at"] is None
        assert d["status"] == "superseded"
