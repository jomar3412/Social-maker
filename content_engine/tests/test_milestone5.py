"""Tests for Milestone 5 features: Provider abstraction and concurrency."""

import pytest
import tempfile
from pathlib import Path

from content_engine.providers.base import (
    ContentProvider,
    ProviderConfig,
    ProviderType,
    GenerationResult,
    get_provider,
)
from content_engine.providers.stub_provider import StubProvider
from content_engine.providers.cli_provider import CLIProvider
from content_engine.services.concurrency import (
    ConcurrencyManager,
    ConcurrencyConfig,
    RunLimitExceeded,
    RegenerationLimitExceeded,
    get_concurrency_manager,
    reset_concurrency_manager,
)


class TestProviderConfig:
    """Test provider configuration."""

    def test_from_config_stub(self):
        """Test creating stub provider config from dict."""
        config = ProviderConfig.from_config({"provider": "stub"})
        assert config.provider_type == ProviderType.STUB

    def test_from_config_cli(self):
        """Test creating CLI provider config from dict."""
        config = ProviderConfig.from_config({"provider": "cli", "cli_model": "gemini"})
        assert config.provider_type == ProviderType.CLI
        assert config.cli_model == "gemini"

    def test_from_config_defaults(self):
        """Test default values."""
        config = ProviderConfig.from_config({})
        assert config.provider_type == ProviderType.STUB
        assert config.timeout_seconds == 120
        assert config.max_retries == 2


class TestGetProvider:
    """Test provider factory function."""

    def test_get_stub_provider(self):
        """Test getting stub provider."""
        provider = get_provider({"provider": "stub"})
        assert isinstance(provider, StubProvider)

    def test_get_cli_provider(self):
        """Test getting CLI provider."""
        provider = get_provider({"provider": "cli"})
        assert isinstance(provider, CLIProvider)

    def test_get_provider_default(self):
        """Test default provider is stub."""
        provider = get_provider({})
        assert isinstance(provider, StubProvider)


class TestStubProvider:
    """Test stub provider functionality."""

    @pytest.fixture
    def provider(self):
        """Create stub provider."""
        config = ProviderConfig(provider_type=ProviderType.STUB, stub_delay_ms=0)
        return StubProvider(config)

    @pytest.fixture
    def temp_dir(self):
        """Create temporary output directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_generate_script_motivation(self, provider, temp_dir):
        """Test generating motivation script."""
        result = provider.generate_script(
            run_id="test-001",
            niche="motivation",
            style="affirming",
            topic=None,
            output_dir=temp_dir,
        )

        assert result.success
        assert "script" in result.output_files
        assert "script_meta" in result.output_files
        assert result.output_files["script"].exists()

        script_text = result.output_files["script"].read_text()
        assert "You did good today" in script_text

    def test_generate_script_fun_facts(self, provider, temp_dir):
        """Test generating fun facts script."""
        result = provider.generate_script(
            run_id="test-002",
            niche="fun_facts",
            style="curious",
            topic=None,
            output_dir=temp_dir,
        )

        assert result.success
        assert "honey" in result.output_files["script"].read_text().lower()

    def test_regenerate_script(self, provider, temp_dir):
        """Test regenerating script."""
        prior = {"script": "Old script", "hook": "Old hook"}
        result = provider.regenerate_script(
            run_id="test-003",
            niche="motivation",
            style="affirming",
            prior_script=prior,
            feedback="Make it more energetic",
            output_dir=temp_dir,
        )

        assert result.success
        assert result.artifacts.get("regeneration_note") is not None

    def test_generate_shot_list(self, provider, temp_dir):
        """Test generating shot list."""
        script = {
            "script": "Line one.\nLine two.\nLine three.",
            "hook": "Line one.",
        }
        result = provider.generate_shot_list(
            run_id="test-004",
            script=script,
            visual_mode="hybrid",
            output_dir=temp_dir,
        )

        assert result.success
        assert "shot_list" in result.output_files
        assert "shot_list_md" in result.output_files

    def test_generate_visual_prompts(self, provider, temp_dir):
        """Test generating visual prompts."""
        shot_list = {
            "shot_list": [
                {"scene_number": 1, "beat_type": "HOOK", "visual_description": "Test"},
            ]
        }
        result = provider.generate_visual_prompts(
            run_id="test-005",
            shot_list=shot_list,
            visual_mode="nanobanana",
            realism_mode="standard",
            output_dir=temp_dir,
        )

        assert result.success
        assert "nanobanana_prompts" in result.output_files

    def test_generate_stock_queries(self, provider, temp_dir):
        """Test generating stock queries."""
        shot_list = {
            "shot_list": [
                {"scene_number": 1, "beat_type": "HOOK", "search_tight": "test", "search_broad": "test"},
            ]
        }
        result = provider.generate_stock_queries(
            run_id="test-006",
            shot_list=shot_list,
            output_dir=temp_dir,
        )

        assert result.success
        assert "stock_queries" in result.output_files

    def test_progress_callback(self, provider, temp_dir):
        """Test progress callback is called."""
        progress_updates = []

        def on_progress(stage: str, percent: int):
            progress_updates.append((stage, percent))

        provider.set_progress_callback(on_progress)
        provider.generate_script(
            run_id="test-007",
            niche="motivation",
            style="affirming",
            topic=None,
            output_dir=temp_dir,
        )

        assert len(progress_updates) > 0
        assert progress_updates[-1][1] == 100  # Final should be 100%


class TestConcurrencyConfig:
    """Test concurrency configuration."""

    def test_from_config(self):
        """Test creating config from dict."""
        config = ConcurrencyConfig.from_config({
            "max_active_runs": 5,
            "max_regenerations_per_run": 10,
        })
        assert config.max_active_runs == 5
        assert config.max_regenerations_per_run == 10

    def test_defaults(self):
        """Test default values."""
        config = ConcurrencyConfig()
        assert config.max_active_runs == 2
        assert config.max_regenerations_per_run == 3


class TestConcurrencyManager:
    """Test concurrency manager functionality."""

    @pytest.fixture
    def manager(self):
        """Create concurrency manager."""
        config = ConcurrencyConfig(max_active_runs=2, max_regenerations_per_run=3)
        return ConcurrencyManager(config)

    def test_can_start_run(self, manager):
        """Test checking if run can start."""
        assert manager.can_start_run() is True

    def test_start_run(self, manager):
        """Test starting a run."""
        result = manager.start_run("run-001", "init")
        assert result is True
        assert manager.is_run_active("run-001")

    def test_max_runs_limit(self, manager):
        """Test max concurrent runs limit."""
        manager.start_run("run-001", "init")
        manager.start_run("run-002", "init")

        # Third run should fail
        with pytest.raises(RunLimitExceeded):
            manager.start_run("run-003", "init")

    def test_complete_run(self, manager):
        """Test completing a run frees a slot."""
        manager.start_run("run-001", "init")
        manager.start_run("run-002", "init")

        # Complete one
        manager.complete_run("run-001")

        # Now can start another
        assert manager.can_start_run()
        manager.start_run("run-003", "init")

    def test_can_regenerate(self, manager):
        """Test regeneration limit check."""
        assert manager.can_regenerate("run-001") is True

    def test_increment_regeneration(self, manager):
        """Test incrementing regeneration count."""
        count = manager.increment_regeneration("run-001")
        assert count == 1

        count = manager.increment_regeneration("run-001")
        assert count == 2

    def test_regeneration_limit(self, manager):
        """Test regeneration limit exceeded."""
        manager.increment_regeneration("run-001")
        manager.increment_regeneration("run-001")
        manager.increment_regeneration("run-001")

        # Fourth should fail
        with pytest.raises(RegenerationLimitExceeded):
            manager.increment_regeneration("run-001")

    def test_get_remaining_regenerations(self, manager):
        """Test getting remaining regenerations."""
        assert manager.get_remaining_regenerations("run-001") == 3

        manager.increment_regeneration("run-001")
        assert manager.get_remaining_regenerations("run-001") == 2

    def test_get_status(self, manager):
        """Test getting status."""
        manager.start_run("run-001", "init")
        status = manager.get_status()

        assert status["active_runs"] == 1
        assert status["max_runs"] == 2
        assert status["available_slots"] == 1
        assert "run-001" in status["active_run_ids"]

    def test_update_stage(self, manager):
        """Test updating run stage."""
        manager.start_run("run-001", "init")
        manager.update_stage("run-001", "research")

        # Stage should be updated in active runs
        active = manager.get_active_runs()
        assert len(active) == 1
        assert active[0].stage == "research"

    def test_reset_regeneration_count(self, manager):
        """Test resetting regeneration count."""
        manager.increment_regeneration("run-001")
        manager.increment_regeneration("run-001")
        assert manager.get_regeneration_count("run-001") == 2

        manager.reset_regeneration_count("run-001")
        assert manager.get_regeneration_count("run-001") == 0


class TestGlobalConcurrencyManager:
    """Test global concurrency manager singleton."""

    def setup_method(self):
        """Reset singleton before each test."""
        reset_concurrency_manager()

    def test_get_concurrency_manager_singleton(self):
        """Test singleton pattern."""
        manager1 = get_concurrency_manager()
        manager2 = get_concurrency_manager()
        assert manager1 is manager2

    def test_get_concurrency_manager_with_config(self):
        """Test initializing with config."""
        manager = get_concurrency_manager({"max_active_runs": 5})
        assert manager.config.max_active_runs == 5

    def test_reset_concurrency_manager(self):
        """Test resetting singleton."""
        manager1 = get_concurrency_manager()
        reset_concurrency_manager()
        manager2 = get_concurrency_manager()
        assert manager1 is not manager2
