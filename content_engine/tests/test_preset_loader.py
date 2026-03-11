"""Tests for PresetLoader service."""

import pytest
from pathlib import Path
import tempfile
import json

from content_engine.services.preset_loader import PresetLoader, PresetInfo


class TestPresetLoader:
    """Test PresetLoader functionality."""

    @pytest.fixture
    def temp_presets_dir(self):
        """Create temporary presets directory with test presets."""
        with tempfile.TemporaryDirectory() as tmpdir:
            presets_dir = Path(tmpdir)

            # Create category directories
            (presets_dir / "niches").mkdir()
            (presets_dir / "styles").mkdir()
            (presets_dir / "voices").mkdir()

            # Create test presets
            motivation_preset = {
                "name": "motivation",
                "display_name": "Test Motivation",
                "description": "Test motivation preset",
                "tags": ["test"],
            }
            (presets_dir / "niches" / "motivation.json").write_text(
                json.dumps(motivation_preset)
            )

            affirming_preset = {
                "name": "affirming",
                "display_name": "Test Affirming",
                "description": "Test affirming style",
                "energy": "low",
            }
            (presets_dir / "styles" / "affirming.json").write_text(
                json.dumps(affirming_preset)
            )

            deep_voice_preset = {
                "name": "deep_motivational",
                "display_name": "Deep Voice",
                "elevenlabs": {"voice_id": "test123"},
            }
            (presets_dir / "voices" / "deep_motivational.json").write_text(
                json.dumps(deep_voice_preset)
            )

            yield presets_dir

    @pytest.fixture
    def loader(self, temp_presets_dir):
        """Create PresetLoader with test directory."""
        return PresetLoader(temp_presets_dir)

    def test_list_presets(self, loader):
        """Test listing presets in a category."""
        niches = loader.list_presets("niches")
        assert "motivation" in niches

        styles = loader.list_presets("styles")
        assert "affirming" in styles

    def test_list_presets_empty_category(self, loader, temp_presets_dir):
        """Test listing presets in empty category."""
        (temp_presets_dir / "realism").mkdir()
        result = loader.list_presets("realism")
        assert result == []

    def test_list_presets_nonexistent_category(self, loader):
        """Test listing presets in nonexistent category."""
        result = loader.list_presets("nonexistent")
        assert result == []

    def test_get_preset(self, loader):
        """Test loading a specific preset."""
        preset = loader.get_preset("niches", "motivation")

        assert preset is not None
        assert isinstance(preset, PresetInfo)
        assert preset.name == "motivation"
        assert preset.category == "niches"
        assert preset.data["display_name"] == "Test Motivation"

    def test_get_preset_cached(self, loader):
        """Test that presets are cached."""
        preset1 = loader.get_preset("niches", "motivation")
        preset2 = loader.get_preset("niches", "motivation")

        # Should be the same object (cached)
        assert preset1 is preset2

    def test_get_preset_nonexistent(self, loader):
        """Test loading nonexistent preset."""
        preset = loader.get_preset("niches", "nonexistent")
        assert preset is None

    def test_get_all_presets(self, loader):
        """Test loading all presets in a category."""
        niches = loader.get_all_presets("niches")
        assert len(niches) == 1
        assert niches[0].name == "motivation"

    def test_compute_fingerprint(self, loader):
        """Test fingerprint computation."""
        selected = {
            "niche": "motivation",
            "style": "affirming",
            "voice": "deep_motivational",
        }
        fp = loader.compute_fingerprint(selected)

        assert isinstance(fp, str)
        assert len(fp) == 16  # SHA256 truncated to 16 chars

    def test_fingerprint_changes_with_content(self, loader, temp_presets_dir):
        """Test fingerprint changes when preset content changes."""
        selected = {"niche": "motivation"}

        # Get initial fingerprint
        fp1 = loader.compute_fingerprint(selected)

        # Modify the preset
        preset_path = temp_presets_dir / "niches" / "motivation.json"
        data = json.loads(preset_path.read_text())
        data["description"] = "Modified description"
        preset_path.write_text(json.dumps(data))

        # Clear cache to ensure fresh read
        loader.clear_cache()

        # Get new fingerprint
        fp2 = loader.compute_fingerprint(selected)

        assert fp1 != fp2

    def test_fingerprint_same_for_same_content(self, loader):
        """Test fingerprint is deterministic."""
        selected = {
            "niche": "motivation",
            "style": "affirming",
        }

        fp1 = loader.compute_fingerprint(selected)
        fp2 = loader.compute_fingerprint(selected)

        assert fp1 == fp2

    def test_fingerprint_handles_missing_presets(self, loader):
        """Test fingerprint with some missing presets."""
        selected = {
            "niche": "motivation",
            "style": "nonexistent",
        }
        fp = loader.compute_fingerprint(selected)

        assert isinstance(fp, str)
        assert len(fp) == 16

    def test_validate_selection_valid(self, loader):
        """Test validation with all valid presets."""
        selected = {
            "niche": "motivation",
            "style": "affirming",
        }
        is_valid, missing = loader.validate_selection(selected)

        assert is_valid is True
        assert missing == []

    def test_validate_selection_missing(self, loader):
        """Test validation with missing presets."""
        selected = {
            "niche": "motivation",
            "style": "nonexistent",
        }
        is_valid, missing = loader.validate_selection(selected)

        assert is_valid is False
        assert "styles/nonexistent" in missing

    def test_clear_cache(self, loader):
        """Test cache clearing."""
        # Load a preset (caches it)
        loader.get_preset("niches", "motivation")
        assert "niches" in loader._cache

        # Clear cache
        loader.clear_cache()
        assert loader._cache == {}

    def test_get_preset_metadata(self, loader):
        """Test getting preset metadata."""
        meta = loader.get_preset_metadata("niches", "motivation")

        assert meta["name"] == "motivation"
        assert meta["display_name"] == "Test Motivation"
        assert meta["description"] == "Test motivation preset"
        assert meta["tags"] == ["test"]

    def test_get_preset_metadata_nonexistent(self, loader):
        """Test metadata for nonexistent preset."""
        meta = loader.get_preset_metadata("niches", "nonexistent")
        assert meta == {}


class TestPresetInfo:
    """Test PresetInfo dataclass."""

    def test_preset_info_creation(self, tmp_path):
        """Test creating PresetInfo."""
        info = PresetInfo(
            name="test",
            category="niches",
            path=tmp_path / "test.json",
            data={"key": "value"},
        )

        assert info.name == "test"
        assert info.category == "niches"
        assert info.data["key"] == "value"
