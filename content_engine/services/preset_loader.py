"""
PresetLoader: Load presets from JSON files and compute fingerprints.

Presets are organized in subdirectories:
- presets/niches/
- presets/styles/
- presets/voices/
- presets/visuals/
- presets/realism/
"""

from pathlib import Path
from dataclasses import dataclass
import json
import hashlib
from typing import Any


@dataclass
class PresetInfo:
    """Information about a loaded preset."""
    name: str
    category: str
    path: Path
    data: dict[str, Any]


class PresetLoader:
    """
    Load and manage preset JSON files.

    Presets are JSON files in categorized subdirectories.
    Each preset defines configuration for its category (niche, style, voice, etc.).
    """

    CATEGORIES = ["niches", "styles", "voices", "visuals", "realism"]

    def __init__(self, presets_dir: Path | None = None):
        """
        Initialize PresetLoader.

        Args:
            presets_dir: Path to presets directory. If None, uses content_engine/presets/
        """
        if presets_dir is None:
            presets_dir = Path(__file__).parent.parent / "presets"

        self.presets_dir = presets_dir
        self._cache: dict[str, dict[str, PresetInfo]] = {}

    def list_presets(self, category: str) -> list[str]:
        """
        List available preset names in a category.

        Args:
            category: One of niches, styles, voices, visuals, realism

        Returns:
            List of preset names (without .json extension)
        """
        category_dir = self.presets_dir / category
        if not category_dir.exists():
            return []

        return sorted([
            p.stem for p in category_dir.glob("*.json")
            if p.is_file()
        ])

    def get_preset(self, category: str, name: str) -> PresetInfo | None:
        """
        Load a specific preset.

        Args:
            category: Preset category (niches, styles, etc.)
            name: Preset name (without .json)

        Returns:
            PresetInfo if found, None otherwise
        """
        # Check cache first
        cache_key = f"{category}/{name}"
        if category in self._cache and name in self._cache[category]:
            return self._cache[category][name]

        preset_path = self.presets_dir / category / f"{name}.json"
        if not preset_path.exists():
            return None

        try:
            with open(preset_path) as f:
                data = json.load(f)

            preset = PresetInfo(
                name=name,
                category=category,
                path=preset_path,
                data=data
            )

            # Cache it
            if category not in self._cache:
                self._cache[category] = {}
            self._cache[category][name] = preset

            return preset

        except (json.JSONDecodeError, IOError):
            return None

    def get_all_presets(self, category: str) -> list[PresetInfo]:
        """
        Load all presets in a category.

        Args:
            category: Preset category

        Returns:
            List of PresetInfo objects
        """
        presets = []
        for name in self.list_presets(category):
            preset = self.get_preset(category, name)
            if preset:
                presets.append(preset)
        return presets

    def compute_fingerprint(self, selected_presets: dict[str, str]) -> str:
        """
        Compute SHA256 hash of selected preset contents.

        Used for cache invalidation - when presets change, fingerprint changes.

        Args:
            selected_presets: Dict mapping category to preset name, e.g.:
                {
                    "niche": "motivation",
                    "style": "affirming",
                    "voice": "deep_motivational",
                    "visual": "nanobanana_cinematic",
                    "realism": "standard"
                }

        Returns:
            16-character hex hash of combined preset contents
        """
        contents = []

        # Sort for deterministic ordering
        for category, name in sorted(selected_presets.items()):
            # Handle singular vs plural category names
            category_dir = category if category.endswith("s") else f"{category}s"
            preset_path = self.presets_dir / category_dir / f"{name}.json"

            if preset_path.exists():
                try:
                    contents.append(preset_path.read_text())
                except IOError:
                    # Include name as fallback if file can't be read
                    contents.append(f"{category}:{name}")
            else:
                # Include name even if file doesn't exist (for consistent hashing)
                contents.append(f"{category}:{name}")

        combined = "||".join(contents)
        return hashlib.sha256(combined.encode()).hexdigest()[:16]

    def validate_selection(self, selected_presets: dict[str, str]) -> tuple[bool, list[str]]:
        """
        Validate that all selected presets exist.

        Args:
            selected_presets: Dict mapping category to preset name

        Returns:
            (is_valid, list_of_missing_presets)
        """
        missing = []

        for category, name in selected_presets.items():
            category_dir = category if category.endswith("s") else f"{category}s"
            preset_path = self.presets_dir / category_dir / f"{name}.json"

            if not preset_path.exists():
                missing.append(f"{category_dir}/{name}")

        return len(missing) == 0, missing

    def clear_cache(self):
        """Clear the preset cache (useful after preset files are modified)."""
        self._cache.clear()

    def get_preset_metadata(self, category: str, name: str) -> dict[str, Any]:
        """
        Get just the metadata from a preset (name, description, etc.).

        Useful for UI display without loading full preset data.

        Args:
            category: Preset category
            name: Preset name

        Returns:
            Dict with metadata fields, or empty dict if not found
        """
        preset = self.get_preset(category, name)
        if not preset:
            return {}

        return {
            "name": preset.name,
            "display_name": preset.data.get("display_name", preset.name.replace("_", " ").title()),
            "description": preset.data.get("description", ""),
            "tags": preset.data.get("tags", []),
        }

    def get_visual_preset(self, visual_mode: str) -> dict[str, Any] | None:
        """
        Load a visual preset by name.

        Convenience method for loading visual presets used by the pipeline
        for NanoBanana prompt generation.

        Args:
            visual_mode: Visual preset name (e.g., "nanobanana_cinematic", "stock_only")

        Returns:
            Preset data dict if found, None otherwise
        """
        if not visual_mode:
            return None

        preset = self.get_preset("visuals", visual_mode)
        if preset:
            return preset.data
        return None

    def get_niche_preset(self, niche: str) -> dict[str, Any] | None:
        """
        Load a niche preset by name.

        Args:
            niche: Niche preset name (e.g., "motivation", "fun_facts")

        Returns:
            Preset data dict if found, None otherwise
        """
        if not niche:
            return None

        preset = self.get_preset("niches", niche)
        if preset:
            return preset.data
        return None

    def get_style_preset(self, style: str) -> dict[str, Any] | None:
        """
        Load a style preset by name.

        Args:
            style: Style preset name (e.g., "affirming", "edgy_funny")

        Returns:
            Preset data dict if found, None otherwise
        """
        if not style:
            return None

        preset = self.get_preset("styles", style)
        if preset:
            return preset.data
        return None
