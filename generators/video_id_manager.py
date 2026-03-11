"""
Video ID and Version Control System

NAMING CONVENTION:
1. FOLDER FORMAT: [3 digit]-[Niche]-[Topic]
   Example: 001-FunFacts-Butterfly_Taste

2. VIDEO FORMAT: [3 digit]-[Niche]-[Topic]_V[number].mp4
   Example: 001-FunFacts-Butterfly_Taste_V1.mp4

3. CLIPS FOLDER: [Topic]_V[number]_Clips/
   Contains all VEO-generated scene clips + VEO_PROMPTS.md

4. VERSION CONTROL: V1, V2, V3, etc.
   - New visuals on same script = new version
   - Maintain change log per version
   - Continue numbering across versions

5. NICHE OPTIONS: FunFacts, Motivation, Health
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any

from config.settings import OUTPUT_DIR


# Registry file for all videos
REGISTRY_FILE = OUTPUT_DIR / "video_registry.json"

# Niche mapping
NICHE_MAP = {
    "fact": "FunFacts",
    "motivation": "Motivation",
    "health": "Health",
}


def _load_registry() -> Dict:
    """Load the video registry."""
    if REGISTRY_FILE.exists():
        with open(REGISTRY_FILE) as f:
            return json.load(f)
    return {"videos": {}, "next_number": 1}


def _save_registry(registry: Dict) -> None:
    """Save the video registry."""
    REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY_FILE, "w") as f:
        json.dump(registry, f, indent=2)


def _extract_topic_slug(script_text: str, hook_text: str = "") -> str:
    """
    Extract a topic slug from the script content.

    Returns Title_Case slug like Butterfly_Taste, Venus_Day, Chess_Moves
    """
    # Combine hook and script, prioritize hook
    text = (hook_text + " " + script_text).lower()

    # Remove common words
    stop_words = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'must', 'to', 'of', 'in', 'for', 'on',
        'with', 'at', 'by', 'from', 'up', 'about', 'into', 'through', 'over',
        'and', 'but', 'or', 'so', 'yet', 'this', 'that', 'these', 'those',
        'it', 'its', 'you', 'your', 'we', 'our', 'they', 'their', 'them',
        'what', 'which', 'who', 'whom', 'when', 'where', 'why', 'how',
        'all', 'each', 'every', 'both', 'few', 'more', 'most', 'other',
        'some', 'such', 'no', 'not', 'only', 'own', 'same', 'than', 'too',
        'very', 'just', 'can', 'now', 'one', 'two', 'three', 'like', 'even',
        'actually', 'really', 'completely', 'ever', 'never', 'always',
        'wait', 'well', 'food', 'feet', 'taste',
    }

    # Extract significant words (nouns/verbs likely)
    words = re.findall(r'\b[a-z]{4,}\b', text)
    significant = [w for w in words if w not in stop_words]

    # Take first 2 significant words, Title_Case
    if len(significant) >= 2:
        slug = f"{significant[0].title()}_{significant[1].title()}"
    elif significant:
        slug = significant[0].title()
    else:
        slug = "Content"

    return slug


def generate_video_id(script_text: str, hook_text: str = "",
                      content_type: str = "fact") -> str:
    """
    Generate a unique Video ID.

    Format: [3 digit]-[Niche]-[Topic]
    Example: 001-FunFacts-Butterfly_Taste

    Args:
        script_text: The full script text
        hook_text: The hook text (optional, used for topic extraction)
        content_type: "fact", "motivation", or "health"

    Returns:
        Unique Video ID string
    """
    niche = NICHE_MAP.get(content_type, "FunFacts")
    topic_slug = _extract_topic_slug(script_text, hook_text)

    # Get next sequence number (global, not daily)
    registry = _load_registry()
    seq_num = registry.get("next_number", 1)

    video_id = f"{seq_num:03d}-{niche}-{topic_slug}"

    # Increment for next video
    registry["next_number"] = seq_num + 1
    _save_registry(registry)

    return video_id


def get_output_folder(video_id: str) -> Path:
    """Get the output folder path for a Video ID."""
    return OUTPUT_DIR / video_id


def get_video_filename(video_id: str, version: int) -> str:
    """
    Get the video filename for a Video ID and version.

    Format: [Video-ID]_V[number].mp4
    Example: 001-FunFacts-Butterfly_Taste_V1.mp4
    """
    return f"{video_id}_V{version}.mp4"


def get_clips_folder(video_id: str, version: int) -> Path:
    """
    Get the clips folder path for VEO-generated scene clips.

    Format: [output_folder]/[Topic]_V[number]_Clips/
    Example: .../001-FunFacts-Butterfly_Taste/Butterfly_Taste_V1_Clips/
    """
    # Extract topic from video_id (last part after niche)
    parts = video_id.split("-")
    if len(parts) >= 3:
        topic = parts[-1]  # e.g., "Butterfly_Taste"
    else:
        topic = "Clips"

    clips_folder_name = f"{topic}_V{version}_Clips"
    return get_output_folder(video_id) / clips_folder_name


def get_clip_filename(scene_number: int) -> str:
    """
    Get filename for a single scene clip.

    Format: scene_[2 digit].mp4
    """
    return f"scene_{scene_number:02d}.mp4"


class VideoVersion:
    """Represents a single version of a video."""

    def __init__(self, version_number: int, video_id: str):
        self.version_number = version_number
        self.video_id = video_id
        self.created_at = datetime.now().isoformat()
        self.changes: List[str] = []
        self.feedback: Dict[str, List[str]] = {
            "liked": [],
            "disliked": [],
        }
        self.scene_count = 0
        self.duration = 0.0
        self.video_path: Optional[str] = None
        self.clips_folder: Optional[str] = None
        # Removed VEO

    def add_change(self, description: str) -> None:
        """Record a change made in this version."""
        self.changes.append(description)

    def add_feedback(self, liked: Optional[List[str]] = None,
                     disliked: Optional[List[str]] = None) -> None:
        """Record feedback for this version."""
        if liked:
            self.feedback["liked"].extend(liked)
        if disliked:
            self.feedback["disliked"].extend(disliked)

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON storage."""
        return {
            "version": self.version_number,
            "video_id": self.video_id,
            "created_at": self.created_at,
            "changes": self.changes,
            "feedback": self.feedback,
            "scene_count": self.scene_count,
            "duration": self.duration,
            "video_path": self.video_path,
            "clips_folder": self.clips_folder,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "VideoVersion":
        """Create from dictionary."""
        version = cls(data["version"], data["video_id"])
        version.created_at = data.get("created_at", "")
        version.changes = data.get("changes", [])
        version.feedback = data.get("feedback", {"liked": [], "disliked": []})
        version.scene_count = data.get("scene_count", 0)
        version.duration = data.get("duration", 0.0)
        version.video_path = data.get("video_path")
        version.clips_folder = data.get("clips_folder")
        return version


class VideoRecord:
    """Complete record for a video including all versions."""

    def __init__(self, video_id: str):
        self.video_id = video_id
        self.created_at = datetime.now().isoformat()
        self.script: Dict[str, Any] = {}
        self.versions: List[VideoVersion] = []
        self.approved_version: Optional[int] = None
        self.is_template = False

    @property
    def current_version(self) -> int:
        """Get the current (latest) version number."""
        return len(self.versions)

    @property
    def next_version(self) -> int:
        """Get the next version number."""
        return len(self.versions) + 1

    def create_version(self) -> VideoVersion:
        """Create a new version."""
        version = VideoVersion(self.next_version, self.video_id)
        self.versions.append(version)
        return version

    def get_version(self, version_num: int) -> Optional[VideoVersion]:
        """Get a specific version."""
        if 1 <= version_num <= len(self.versions):
            return self.versions[version_num - 1]
        return None

    def set_script(self, fact: str, hook: str, caption: str,
                   voiceover_text: str, scenes: List[Dict]) -> None:
        """Store the script data."""
        self.script = {
            "fact": fact,
            "hook": hook,
            "caption": caption,
            "voiceover_text": voiceover_text,
            "scenes": scenes,
        }

    def approve_version(self, version_num: int) -> None:
        """Mark a version as approved (use as template)."""
        if 1 <= version_num <= len(self.versions):
            self.approved_version = version_num
            self.is_template = True

    def get_improvement_suggestions(self) -> List[str]:
        """
        Analyze feedback from all versions to suggest improvements.
        """
        suggestions = []

        # Collect all dislikes that haven't been addressed
        all_dislikes = set()
        addressed = set()

        for version in self.versions:
            for dislike in version.feedback.get("disliked", []):
                all_dislikes.add(dislike.lower())
            for change in version.changes:
                addressed.add(change.lower())

        # Find unaddressed issues
        for dislike in all_dislikes:
            if not any(dislike in change for change in addressed):
                suggestions.append(f"Consider addressing: {dislike}")

        # Collect patterns from likes to maintain
        all_likes = []
        for version in self.versions:
            all_likes.extend(version.feedback.get("liked", []))

        if all_likes:
            suggestions.append(f"Maintain these positives: {', '.join(set(all_likes)[:3])}")

        return suggestions

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON storage."""
        return {
            "video_id": self.video_id,
            "created_at": self.created_at,
            "script": self.script,
            "versions": [v.to_dict() for v in self.versions],
            "approved_version": self.approved_version,
            "is_template": self.is_template,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "VideoRecord":
        """Create from dictionary."""
        record = cls(data["video_id"])
        record.created_at = data.get("created_at", "")
        record.script = data.get("script", {})
        record.versions = [VideoVersion.from_dict(v) for v in data.get("versions", [])]
        record.approved_version = data.get("approved_version")
        record.is_template = data.get("is_template", False)
        return record

    def save(self) -> None:
        """Save this record to the registry."""
        registry = _load_registry()
        registry["videos"][self.video_id] = self.to_dict()
        _save_registry(registry)

    @classmethod
    def load(cls, video_id: str) -> Optional["VideoRecord"]:
        """Load a record from the registry."""
        registry = _load_registry()
        if video_id in registry["videos"]:
            return cls.from_dict(registry["videos"][video_id])
        return None

    @classmethod
    def exists(cls, video_id: str) -> bool:
        """Check if a video ID exists in the registry."""
        registry = _load_registry()
        return video_id in registry["videos"]


def get_template_videos() -> List[VideoRecord]:
    """Get all videos marked as templates."""
    registry = _load_registry()
    templates = []
    for video_data in registry["videos"].values():
        if video_data.get("is_template"):
            templates.append(VideoRecord.from_dict(video_data))
    return templates


def lookup_by_topic(topic_keywords: List[str]) -> List[VideoRecord]:
    """Find videos by topic keywords."""
    registry = _load_registry()
    matches = []

    for video_data in registry["videos"].values():
        video_id = video_data["video_id"]
        # Check if any keyword matches the video ID
        for keyword in topic_keywords:
            if keyword.upper() in video_id.upper():
                matches.append(VideoRecord.from_dict(video_data))
                break

    return matches


def generate_change_log(record: VideoRecord) -> str:
    """Generate a formatted change log for all versions."""
    lines = [
        f"# Change Log: {record.video_id}",
        f"Created: {record.created_at}",
        "",
    ]

    for version in record.versions:
        lines.append(f"## Version {version.version_number}")
        lines.append(f"Created: {version.created_at}")

        if version.changes:
            lines.append("### Changes:")
            for change in version.changes:
                lines.append(f"  - {change}")

        if version.feedback["liked"]:
            lines.append("### Liked:")
            for like in version.feedback["liked"]:
                lines.append(f"  + {like}")

        if version.feedback["disliked"]:
            lines.append("### Disliked:")
            for dislike in version.feedback["disliked"]:
                lines.append(f"  - {dislike}")

        lines.append("")

    if record.approved_version:
        lines.append(f"**Approved Version:** V{record.approved_version}")

    return "\n".join(lines)


