"""
Story Registry - Organization and Series Tracking

Manages the master index of all stories, tracks series/episodes,
stores character references for reuse, and links related stories.

Usage:
    from generators.story_registry import StoryRegistry

    registry = StoryRegistry()

    # Create new story
    story_id = registry.create_story(
        title="The Coffee Stain",
        genre="thriller",
        story_data={...}
    )

    # Add to series
    registry.add_to_series(story_id, "The Stranger Chronicles")

    # Get story for continuation
    story = registry.get_story(story_id)

    # List all stories
    stories = registry.list_stories()
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from enum import Enum


# Registry file location
REGISTRY_FILE = Path(__file__).parent.parent / "story_registry.json"
OUTPUT_DIR = Path(__file__).parent.parent / "output" / "short_stories"


class StoryStatus(Enum):
    DRAFT = "draft"
    GENERATED = "generated"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class RelationType(Enum):
    SEQUEL = "sequel"
    PREQUEL = "prequel"
    SPINOFF = "spinoff"
    ALTERNATE = "alternate"


@dataclass
class Character:
    """Character information for visual consistency."""
    name: str
    description: str
    age: Optional[str] = None
    gender: Optional[str] = None
    hair: Optional[str] = None
    clothing: Optional[str] = None
    distinctive_features: Optional[str] = None
    midjourney_ref_url: Optional[str] = None
    scenes_appeared: List[int] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Character":
        return cls(**data)

    def to_prompt(self) -> str:
        """Generate a prompt description for this character."""
        parts = []
        if self.age:
            parts.append(self.age)
        if self.gender:
            parts.append(self.gender)
        if self.hair:
            parts.append(f"with {self.hair} hair")
        if self.clothing:
            parts.append(f"wearing {self.clothing}")
        if self.distinctive_features:
            parts.append(self.distinctive_features)
        return ", ".join(parts) if parts else self.description


@dataclass
class StoryEntry:
    """A single story entry in the registry."""
    story_id: str
    title: str
    genre: str
    status: StoryStatus = StoryStatus.DRAFT
    series_id: Optional[str] = None
    episode_number: Optional[int] = None
    characters: Dict[str, Character] = field(default_factory=dict)
    midjourney_refs: Dict[str, str] = field(default_factory=dict)
    related_stories: List[Dict[str, str]] = field(default_factory=list)
    expandable: bool = True
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    output_path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["status"] = self.status.value
        data["characters"] = {k: v.to_dict() if isinstance(v, Character) else v
                             for k, v in self.characters.items()}
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "StoryEntry":
        data = data.copy()
        data["status"] = StoryStatus(data.get("status", "draft"))
        characters = data.get("characters", {})
        data["characters"] = {k: Character.from_dict(v) if isinstance(v, dict) else v
                             for k, v in characters.items()}
        return cls(**data)

    def add_character(self, character: Character):
        """Add a character to the story."""
        self.characters[character.name] = character
        self.updated_at = datetime.now().isoformat()

    def add_related_story(self, story_id: str, relation_type: RelationType):
        """Add a related story."""
        self.related_stories.append({
            "story_id": story_id,
            "relation": relation_type.value
        })
        self.updated_at = datetime.now().isoformat()


@dataclass
class Series:
    """A series of related stories."""
    series_id: str
    name: str
    description: Optional[str] = None
    episodes: List[str] = field(default_factory=list)  # List of story IDs
    shared_characters: Dict[str, Character] = field(default_factory=dict)
    world_rules: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["shared_characters"] = {k: v.to_dict() if isinstance(v, Character) else v
                                    for k, v in self.shared_characters.items()}
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Series":
        data = data.copy()
        chars = data.get("shared_characters", {})
        data["shared_characters"] = {k: Character.from_dict(v) if isinstance(v, dict) else v
                                    for k, v in chars.items()}
        return cls(**data)

    def add_episode(self, story_id: str):
        """Add a story as an episode."""
        if story_id not in self.episodes:
            self.episodes.append(story_id)

    def get_next_episode_number(self) -> int:
        """Get the next episode number."""
        return len(self.episodes) + 1


class StoryRegistry:
    """
    Master registry for all stories.

    Manages story IDs, series, character references, and relationships.
    """

    def __init__(self, registry_file: Path = None):
        self.registry_file = registry_file or REGISTRY_FILE
        self.stories: Dict[str, StoryEntry] = {}
        self.series: Dict[str, Series] = {}
        self._load()

    def _load(self):
        """Load registry from JSON file."""
        if self.registry_file.exists():
            try:
                with open(self.registry_file) as f:
                    data = json.load(f)

                # Load stories
                for story_id, story_data in data.get("stories", {}).items():
                    self.stories[story_id] = StoryEntry.from_dict(story_data)

                # Load series
                for series_id, series_data in data.get("series", {}).items():
                    self.series[series_id] = Series.from_dict(series_data)

            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Could not load registry: {e}")
                self.stories = {}
                self.series = {}

    def save(self):
        """Save registry to JSON file."""
        data = {
            "stories": {k: v.to_dict() for k, v in self.stories.items()},
            "series": {k: v.to_dict() for k, v in self.series.items()},
            "metadata": {
                "last_updated": datetime.now().isoformat(),
                "total_stories": len(self.stories),
                "total_series": len(self.series)
            }
        }

        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.registry_file, "w") as f:
            json.dump(data, f, indent=2)

    def _generate_story_id(self) -> str:
        """Generate a new unique story ID."""
        # Find highest existing ID number
        existing_nums = []
        for story_id in self.stories.keys():
            match = re.match(r"STORY-(\d+)", story_id)
            if match:
                existing_nums.append(int(match.group(1)))

        next_num = max(existing_nums, default=0) + 1
        return f"STORY-{next_num:03d}"

    def _generate_series_id(self, name: str) -> str:
        """Generate a series ID from the name."""
        # Convert to lowercase, replace spaces with hyphens
        series_id = name.lower().replace(" ", "-")
        # Remove non-alphanumeric characters except hyphens
        series_id = re.sub(r"[^a-z0-9-]", "", series_id)
        return series_id

    def create_story(
        self,
        title: str,
        genre: str,
        series_name: Optional[str] = None,
        characters: Optional[Dict[str, Character]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Create a new story entry.

        Returns:
            The new story ID (e.g., "STORY-001")
        """
        story_id = self._generate_story_id()

        # Handle series
        series_id = None
        episode_number = None
        if series_name:
            series_id = self._generate_series_id(series_name)
            if series_id not in self.series:
                # Create new series
                self.series[series_id] = Series(
                    series_id=series_id,
                    name=series_name
                )
            series = self.series[series_id]
            episode_number = series.get_next_episode_number()
            series.add_episode(story_id)

        # Create story entry
        entry = StoryEntry(
            story_id=story_id,
            title=title,
            genre=genre,
            series_id=series_id,
            episode_number=episode_number,
            characters=characters or {},
            metadata=metadata or {}
        )

        self.stories[story_id] = entry
        self.save()

        return story_id

    def get_story(self, story_id: str) -> Optional[StoryEntry]:
        """Get a story by ID."""
        return self.stories.get(story_id)

    def update_story(
        self,
        story_id: str,
        status: Optional[StoryStatus] = None,
        characters: Optional[Dict[str, Character]] = None,
        midjourney_refs: Optional[Dict[str, str]] = None,
        output_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Update an existing story."""
        if story_id not in self.stories:
            raise ValueError(f"Story not found: {story_id}")

        story = self.stories[story_id]

        if status is not None:
            story.status = status
        if characters is not None:
            story.characters.update(characters)
        if midjourney_refs is not None:
            story.midjourney_refs.update(midjourney_refs)
        if output_path is not None:
            story.output_path = output_path
        if metadata is not None:
            story.metadata.update(metadata)

        story.updated_at = datetime.now().isoformat()
        self.save()

    def add_to_series(self, story_id: str, series_name: str):
        """Add an existing story to a series."""
        if story_id not in self.stories:
            raise ValueError(f"Story not found: {story_id}")

        series_id = self._generate_series_id(series_name)

        if series_id not in self.series:
            self.series[series_id] = Series(
                series_id=series_id,
                name=series_name
            )

        series = self.series[series_id]
        story = self.stories[story_id]

        if story_id not in series.episodes:
            series.add_episode(story_id)
            story.series_id = series_id
            story.episode_number = len(series.episodes)
            story.updated_at = datetime.now().isoformat()

        self.save()

    def link_stories(
        self,
        story_id: str,
        related_story_id: str,
        relation: RelationType
    ):
        """Link two stories as related."""
        if story_id not in self.stories:
            raise ValueError(f"Story not found: {story_id}")
        if related_story_id not in self.stories:
            raise ValueError(f"Related story not found: {related_story_id}")

        self.stories[story_id].add_related_story(related_story_id, relation)
        self.save()

    def get_series(self, series_id: str) -> Optional[Series]:
        """Get a series by ID."""
        return self.series.get(series_id)

    def get_series_by_name(self, name: str) -> Optional[Series]:
        """Get a series by name."""
        series_id = self._generate_series_id(name)
        return self.series.get(series_id)

    def list_stories(
        self,
        genre: Optional[str] = None,
        series_id: Optional[str] = None,
        status: Optional[StoryStatus] = None,
        expandable_only: bool = False,
    ) -> List[StoryEntry]:
        """List stories with optional filters."""
        stories = list(self.stories.values())

        if genre:
            stories = [s for s in stories if s.genre == genre]
        if series_id:
            stories = [s for s in stories if s.series_id == series_id]
        if status:
            stories = [s for s in stories if s.status == status]
        if expandable_only:
            stories = [s for s in stories if s.expandable]

        return sorted(stories, key=lambda s: s.created_at, reverse=True)

    def list_series(self) -> List[Series]:
        """List all series."""
        return sorted(
            self.series.values(),
            key=lambda s: s.created_at,
            reverse=True
        )

    def get_story_for_continuation(self, story_id: str) -> Dict[str, Any]:
        """
        Get all data needed to continue a story.

        Returns story entry plus character references and series context.
        """
        story = self.get_story(story_id)
        if not story:
            raise ValueError(f"Story not found: {story_id}")

        result = {
            "story": story.to_dict(),
            "characters": {k: v.to_dict() if isinstance(v, Character) else v
                          for k, v in story.characters.items()},
            "midjourney_refs": story.midjourney_refs,
        }

        # Add series context if part of a series
        if story.series_id:
            series = self.get_series(story.series_id)
            if series:
                result["series"] = {
                    "name": series.name,
                    "episode_number": story.episode_number,
                    "total_episodes": len(series.episodes),
                    "shared_characters": {k: v.to_dict() if isinstance(v, Character) else v
                                         for k, v in series.shared_characters.items()},
                    "world_rules": series.world_rules,
                }

        # Add related stories context
        if story.related_stories:
            result["related"] = []
            for rel in story.related_stories:
                related = self.get_story(rel["story_id"])
                if related:
                    result["related"].append({
                        "story_id": rel["story_id"],
                        "title": related.title,
                        "relation": rel["relation"],
                    })

        return result

    def get_output_path(self, story_id: str) -> Path:
        """Get the output directory path for a story."""
        story = self.get_story(story_id)
        if not story:
            raise ValueError(f"Story not found: {story_id}")

        if story.series_id:
            # Series story: output/short_stories/series/[series-id]/STORY-XXX-Title/
            series = self.get_series(story.series_id)
            title_slug = re.sub(r"[^a-zA-Z0-9-]", "", story.title.replace(" ", "-"))
            return OUTPUT_DIR / "series" / story.series_id / f"{story_id}-{title_slug}"
        else:
            # Standalone story: output/short_stories/standalone/STORY-XXX-Title/
            title_slug = re.sub(r"[^a-zA-Z0-9-]", "", story.title.replace(" ", "-"))
            return OUTPUT_DIR / "standalone" / f"{story_id}-{title_slug}"

    def get_character_refs_for_story(self, story_id: str) -> Dict[str, str]:
        """
        Get all character reference URLs for a story.

        Combines story-specific refs with series shared refs.
        """
        story = self.get_story(story_id)
        if not story:
            return {}

        refs = dict(story.midjourney_refs)

        # Add series shared character refs
        if story.series_id:
            series = self.get_series(story.series_id)
            if series:
                for name, char in series.shared_characters.items():
                    if isinstance(char, Character) and char.midjourney_ref_url:
                        if name not in refs:
                            refs[name] = char.midjourney_ref_url

        return refs


def format_story_list(stories: List[StoryEntry]) -> str:
    """Format a list of stories for display."""
    if not stories:
        return "No stories found."

    lines = []
    for story in stories:
        status_icon = {
            StoryStatus.DRAFT: "[Draft]",
            StoryStatus.GENERATED: "[Generated]",
            StoryStatus.PUBLISHED: "[Published]",
            StoryStatus.ARCHIVED: "[Archived]",
        }.get(story.status, "[?]")

        series_info = ""
        if story.series_id:
            series_info = f" (Series: {story.series_id}, Ep {story.episode_number})"

        lines.append(f"{story.story_id}: {story.title} [{story.genre}] {status_icon}{series_info}")

    return "\n".join(lines)


def format_series_list(series_list: List[Series]) -> str:
    """Format a list of series for display."""
    if not series_list:
        return "No series found."

    lines = []
    for series in series_list:
        lines.append(f"{series.series_id}: {series.name} ({len(series.episodes)} episodes)")

    return "\n".join(lines)


# CLI for testing
if __name__ == "__main__":
    import sys

    registry = StoryRegistry()

    if len(sys.argv) < 2:
        print("Story Registry")
        print("=" * 50)
        print(f"Total stories: {len(registry.stories)}")
        print(f"Total series: {len(registry.series)}")
        print("\nCommands:")
        print("  python story_registry.py list")
        print("  python story_registry.py series")
        print("  python story_registry.py info STORY-001")
        print("  python story_registry.py create 'Title' thriller")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "list":
        stories = registry.list_stories()
        print("All Stories:")
        print("-" * 50)
        print(format_story_list(stories))

    elif cmd == "series":
        series_list = registry.list_series()
        print("All Series:")
        print("-" * 50)
        print(format_series_list(series_list))

    elif cmd == "info":
        if len(sys.argv) < 3:
            print("Usage: python story_registry.py info STORY-ID")
            sys.exit(1)
        story_id = sys.argv[2]
        data = registry.get_story_for_continuation(story_id)
        print(json.dumps(data, indent=2))

    elif cmd == "create":
        if len(sys.argv) < 4:
            print("Usage: python story_registry.py create 'Title' genre [series_name]")
            sys.exit(1)
        title = sys.argv[2]
        genre = sys.argv[3]
        series_name = sys.argv[4] if len(sys.argv) > 4 else None

        story_id = registry.create_story(title, genre, series_name)
        print(f"Created: {story_id}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
