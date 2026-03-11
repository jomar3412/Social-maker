"""
RunStore: SQLite persistence for run state machine.

Stores run_id, stage, approvals, config, output_path, timestamps.
Also handles feedback, notes, and preset tuning memos.
Enables pipeline resumability after restart.
"""

import sqlite3
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from datetime import datetime
import json
from typing import Any


def generate_display_title(hook: str, max_words: int = 8) -> str:
    """
    Generate a display title from the hook.

    Takes first 6-10 words, title-cased.
    """
    if not hook:
        return "Untitled"

    # Clean up the hook
    words = hook.strip().split()

    # Take first N words
    title_words = words[:max_words]
    title = " ".join(title_words)

    # Add ellipsis if truncated
    if len(words) > max_words:
        title += "..."

    # Title case, but preserve some words
    return title.title()


class RunStage(Enum):
    """Pipeline stage states."""
    # Initial states
    STARTING = "starting"           # Run created, waiting for background job
    QUEUED = "queued"               # In background queue

    # Active processing (use current_stage_name for detail)
    RUNNING = "running"             # Background job is processing

    # Script generation stages
    INIT = "init"
    DRIVE_CHECK = "drive_check"
    RESEARCH = "research"
    DRAFT = "draft"
    HOOK_REVIEW = "hook_review"
    RELEVANCE = "relevance"
    FINALIZE = "finalize"

    # Approval gates
    AWAITING_SCRIPT_APPROVAL = "awaiting_script_approval"
    SCRIPT_APPROVED = "script_approved"

    # Post-approval stages (artifact generation)
    GENERATING_SHOT_LIST = "generating_shot_list"
    GENERATING_VISUALS = "generating_visuals"
    GENERATING_STOCK_QUERIES = "generating_stock_queries"

    # Voiceover stages (future)
    AWAITING_VOICEOVER_APPROVAL = "awaiting_voiceover_approval"
    VOICEOVER_APPROVED = "voiceover_approved"
    GENERATING_VOICEOVER = "generating_voiceover"

    # Video clip stages
    GENERATING_VIDEO_CLIPS = "generating_video_clips"
    AWAITING_VIDEO_CLIPS = "awaiting_video_clips"
    VIDEO_CLIPS_READY = "video_clips_ready"
    VIDEO_ASSEMBLY = "video_assembly"

    # Terminal states
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"

    def is_terminal(self) -> bool:
        """Check if this is a terminal state (no more auto-processing)."""
        return self in [
            RunStage.AWAITING_SCRIPT_APPROVAL,
            RunStage.COMPLETE,
            RunStage.FAILED,
            RunStage.CANCELLED,
        ]

    def is_running(self) -> bool:
        """Check if run is actively processing."""
        return self in [
            RunStage.STARTING,
            RunStage.QUEUED,
            RunStage.RUNNING,
            RunStage.GENERATING_SHOT_LIST,
            RunStage.GENERATING_VISUALS,
            RunStage.GENERATING_STOCK_QUERIES,
        ]


class WorkflowStage(Enum):
    """
    High-level workflow stages for UI navigation.

    These represent the user-facing workflow state, computed from
    the underlying RunStage + prompt statuses + feedback.
    """
    SCRIPT_PENDING = "script_pending"      # Script generated but not approved
    VISUALS_PENDING = "visuals_pending"    # Script approved, scenes not all locked
    VIDEO_PENDING = "video_pending"        # All scenes locked, video not finalized
    READY_TO_POST = "ready_to_post"        # Visuals complete, ready for posting
    POSTED = "posted"                      # User marked as posted
    REVIEW_READY = "review_ready"          # Posted and has performance data

    @property
    def display_name(self) -> str:
        """Human-readable display name."""
        names = {
            "script_pending": "Script",
            "visuals_pending": "Visuals",
            "video_pending": "Video",
            "ready_to_post": "Ready",
            "posted": "Posted",
            "review_ready": "Review",
        }
        return names.get(self.value, self.value)

    @property
    def badge_classes(self) -> str:
        """Tailwind classes for workflow stage badge."""
        classes = {
            "script_pending": "bg-yellow-500/20 text-yellow-300 border border-yellow-500/30",
            "visuals_pending": "bg-blue-500/20 text-blue-300 border border-blue-500/30",
            "video_pending": "bg-purple-500/20 text-purple-300 border border-purple-500/30",
            "ready_to_post": "bg-green-500/20 text-green-300 border border-green-500/30",
            "posted": "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30",
            "review_ready": "bg-pink-500/20 text-pink-300 border border-pink-500/30",
        }
        return classes.get(self.value, "bg-gray-500/20 text-gray-300 border border-gray-500/30")

    def is_in_queue(self) -> bool:
        """Check if this stage should appear in the Queue view."""
        return self not in [WorkflowStage.POSTED, WorkflowStage.REVIEW_READY]

    def is_posted(self) -> bool:
        """Check if this stage represents a posted run."""
        return self in [WorkflowStage.POSTED, WorkflowStage.REVIEW_READY]


# Workflow stage info for progress indicators
WORKFLOW_STAGE_INFO = {
    "script_pending": {"step": 1, "icon": "document", "progress": 25},
    "visuals_pending": {"step": 2, "icon": "eye", "progress": 50},
    "video_pending": {"step": 3, "icon": "film", "progress": 75},
    "ready_to_post": {"step": 4, "icon": "check", "progress": 90},
    "posted": {"step": 5, "icon": "globe", "progress": 100},
    "review_ready": {"step": 5, "icon": "star", "progress": 100},
}


# Stage display names and progress percentages
# Script generation: 0-100%, then reset for post-approval
STAGE_INFO = {
    # Initial script generation
    "starting": {"name": "Starting", "progress": 0},
    "queued": {"name": "Queued", "progress": 5},
    "running": {"name": "Running", "progress": 10},
    "drive_check": {"name": "Checking Drive", "progress": 15},
    "research": {"name": "Research", "progress": 30},
    "draft": {"name": "Drafting Script", "progress": 50},
    "hook_review": {"name": "Refining Hook", "progress": 65},
    "relevance": {"name": "Checking Relevance", "progress": 80},
    "finalize": {"name": "Finalizing", "progress": 95},
    "awaiting_script_approval": {"name": "Script Ready", "progress": 100},
    # Post-approval artifact generation
    "script_approved": {"name": "Script Approved", "progress": 10},
    "generating_shot_list": {"name": "Generating Shot List", "progress": 40},
    "generating_visuals": {"name": "Creating Visual Prompts", "progress": 70},
    "generating_stock_queries": {"name": "Building Stock Queries", "progress": 90},
    # Video clip stages
    "awaiting_video_clips": {"name": "Waiting for Video Clips", "progress": 95},
    "generating_video_clips": {"name": "Generating Video Clips", "progress": 96},
    "video_clips_ready": {"name": "Video Clips Ready", "progress": 97},
    "video_assembly": {"name": "Assembling Video", "progress": 98},
    # Terminal
    "complete": {"name": "Complete", "progress": 100},
    "failed": {"name": "Failed", "progress": 0},
    "cancelled": {"name": "Cancelled", "progress": 0},
}


@dataclass
class RunRecord:
    """Run record with display info and notes."""
    run_id: str
    stage: RunStage
    approvals_pending: list[str]  # ["script", "voiceover"]
    config_json: str
    output_path: str | None
    created_at: str
    updated_at: str
    error_message: str | None = None
    display_title: str | None = None
    short_title: str | None = None
    notes: str | None = None
    current_stage_name: str | None = None  # Human-readable current stage
    progress_percent: int = 0              # 0-100
    posted_at: str | None = None           # When run was marked as posted

    # Computed fields (set by RunStore methods, not stored)
    _workflow_stage: WorkflowStage | None = field(default=None, repr=False)
    _has_continuity_warnings: bool = field(default=False, repr=False)
    _locked_scene_count: int = field(default=0, repr=False)
    _total_scene_count: int = field(default=0, repr=False)

    @property
    def config(self) -> dict:
        """Parse config_json to dict."""
        return json.loads(self.config_json) if self.config_json else {}

    @property
    def stage_display_name(self) -> str:
        """Get human-readable stage name."""
        if self.current_stage_name:
            return self.current_stage_name
        info = STAGE_INFO.get(self.stage.value, {})
        return info.get("name", self.stage.value)

    @property
    def computed_progress(self) -> int:
        """Get progress percentage."""
        if self.progress_percent > 0:
            return self.progress_percent
        info = STAGE_INFO.get(self.stage.value, {})
        return info.get("progress", 0)

    @property
    def title(self) -> str:
        """Get display title or fallback to run_id."""
        return self.display_title or self.run_id

    def is_pending_approval(self) -> bool:
        """Check if run is waiting for user approval."""
        return self.stage in [
            RunStage.AWAITING_SCRIPT_APPROVAL,
            RunStage.AWAITING_VOICEOVER_APPROVAL,
        ]

    @property
    def workflow_stage(self) -> WorkflowStage:
        """Get the computed workflow stage."""
        return self._workflow_stage or WorkflowStage.SCRIPT_PENDING

    @property
    def has_continuity_warnings(self) -> bool:
        """Check if any scenes have continuity warnings."""
        return self._has_continuity_warnings

    @property
    def locked_scene_count(self) -> int:
        """Number of locked scenes."""
        return self._locked_scene_count

    @property
    def total_scene_count(self) -> int:
        """Total number of scenes."""
        return self._total_scene_count

    @property
    def workflow_progress(self) -> dict:
        """Get workflow progress indicators for UI."""
        stage = self.workflow_stage
        return {
            "script_done": stage != WorkflowStage.SCRIPT_PENDING,
            "visuals_done": stage not in [WorkflowStage.SCRIPT_PENDING, WorkflowStage.VISUALS_PENDING],
            "video_done": stage not in [WorkflowStage.SCRIPT_PENDING, WorkflowStage.VISUALS_PENDING, WorkflowStage.VIDEO_PENDING],
            "posted": stage.is_posted(),
        }

    @property
    def is_in_queue(self) -> bool:
        """Check if run should appear in Queue view."""
        return self.workflow_stage.is_in_queue()

    @property
    def is_posted(self) -> bool:
        """Check if run has been posted."""
        return self.workflow_stage.is_posted()


@dataclass
class FeedbackRecord:
    """Post-publish feedback for a run."""
    run_id: str
    script_quality: int | None = None  # 1-5
    hook_strength: int | None = None   # 1-5
    visual_match: int | None = None    # 1-5
    tags: list[str] = field(default_factory=list)
    publish_status: str | None = None  # draft, published, archived
    platform: str | None = None        # youtube, tiktok, instagram
    posted_url: str | None = None      # URL to the published video
    post_date: str | None = None       # Date posted (ISO format)
    views: int | None = None
    avg_watch_time: float | None = None  # seconds
    retention_pct: float | None = None   # 0-100
    likes: int | None = None
    shares: int | None = None
    comments: int | None = None
    feedback_notes: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "run_id": self.run_id,
            "script_quality": self.script_quality,
            "hook_strength": self.hook_strength,
            "visual_match": self.visual_match,
            "tags": self.tags,
            "publish_status": self.publish_status,
            "platform": self.platform,
            "posted_url": self.posted_url,
            "post_date": self.post_date,
            "views": self.views,
            "avg_watch_time": self.avg_watch_time,
            "retention_pct": self.retention_pct,
            "likes": self.likes,
            "shares": self.shares,
            "comments": self.comments,
            "feedback_notes": self.feedback_notes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FeedbackRecord":
        """Create from dictionary."""
        return cls(
            run_id=data.get("run_id", ""),
            script_quality=data.get("script_quality"),
            hook_strength=data.get("hook_strength"),
            visual_match=data.get("visual_match"),
            tags=data.get("tags", []),
            publish_status=data.get("publish_status"),
            platform=data.get("platform"),
            posted_url=data.get("posted_url"),
            post_date=data.get("post_date"),
            views=data.get("views"),
            avg_watch_time=data.get("avg_watch_time"),
            retention_pct=data.get("retention_pct"),
            likes=data.get("likes"),
            shares=data.get("shares"),
            comments=data.get("comments"),
            feedback_notes=data.get("feedback_notes"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


@dataclass
class PresetTuningMemo:
    """Tuning memo for a preset based on feedback patterns."""
    preset_type: str  # "niche", "style"
    preset_name: str
    memo_text: str
    avg_script_quality: float | None = None
    avg_hook_strength: float | None = None
    avg_visual_match: float | None = None
    common_tags: list[str] = field(default_factory=list)
    total_runs: int = 0
    updated_at: str | None = None


class ArtifactType(Enum):
    """Types of artifacts that can be versioned."""
    NANOBANANA = "nanobanana"
    STOCK_QUERY = "stock_query"
    SHOT_LIST = "shot_list"


class PromptStatus(Enum):
    """Status of a prompt version."""
    PENDING = "pending"      # Not yet generated (waiting for previous scene)
    ACTIVE = "active"        # Current working version
    LOCKED = "locked"        # User confirmed, frozen for continuity
    OUTDATED = "outdated"    # Upstream scene changed, needs regeneration
    SUPERSEDED = "superseded"  # Replaced by newer version


@dataclass
class PromptVersion:
    """Versioned prompt for regeneration tracking."""
    id: int
    run_id: str
    artifact_type: ArtifactType
    item_key: str  # Identifier per prompt item (e.g., "scene_1", "hook")
    version: int
    prompt_text: str
    notes: str | None = None
    image_path: str | None = None  # Path to generated image if any
    created_at: str | None = None
    created_by: str = "system"  # "system" or "user"
    status: PromptStatus = PromptStatus.ACTIVE
    # Continuity tracking fields
    locked_at: str | None = None  # Timestamp when locked
    depends_on_scene: str | None = None  # Previous scene item_key this was generated from
    depends_on_version_id: int | None = None  # The version ID of the previous scene at generation time
    continuity_warning: str | None = None  # Warning message if upstream changed

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization and template rendering."""
        return {
            "id": self.id,
            "run_id": self.run_id,
            "artifact_type": self.artifact_type.value if hasattr(self.artifact_type, 'value') else str(self.artifact_type),
            "item_key": self.item_key,
            "version": self.version,
            "prompt_text": self.prompt_text,
            "notes": self.notes,
            "image_path": self.image_path,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "status": self.status.value if hasattr(self.status, 'value') else str(self.status),
            "locked_at": self.locked_at,
            "depends_on_scene": self.depends_on_scene,
            "depends_on_version_id": self.depends_on_version_id,
            "continuity_warning": self.continuity_warning,
        }

    @property
    def scene_number(self) -> int | None:
        """Extract scene number from item_key (e.g., 'scene_1' -> 1)."""
        if self.item_key and self.item_key.startswith("scene_"):
            try:
                return int(self.item_key.split("_")[1])
            except (IndexError, ValueError):
                pass
        return None


class EntityType(Enum):
    """Types of entities for continuity tracking."""
    CHARACTER = "character"
    PROP = "prop"
    LOCATION = "location"
    STYLE = "style"


@dataclass
class Entity:
    """
    Continuity entity for consistent visual elements across scenes.

    Entities can be characters, props, locations, or styles that need
    to maintain visual consistency throughout a video.
    """
    id: int
    run_id: str
    name: str
    entity_type: EntityType
    description: str  # Visual description for prompts
    reference_image_path: str | None = None
    created_from_scene_key: str | None = None  # Which scene/prompt created this
    created_at: str | None = None
    updated_at: str | None = None
    is_active: bool = True

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "run_id": self.run_id,
            "name": self.name,
            "entity_type": self.entity_type.value,
            "description": self.description,
            "reference_image_path": self.reference_image_path,
            "created_from_scene_key": self.created_from_scene_key,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "is_active": self.is_active,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Entity":
        """Create from dictionary."""
        return cls(
            id=data.get("id", 0),
            run_id=data.get("run_id", ""),
            name=data.get("name", ""),
            entity_type=EntityType(data.get("entity_type", "character")),
            description=data.get("description", ""),
            reference_image_path=data.get("reference_image_path"),
            created_from_scene_key=data.get("created_from_scene_key"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            is_active=data.get("is_active", True),
        )

    def to_prompt_context(self) -> str:
        """Format entity as prompt context block."""
        context = f"[{self.entity_type.value.upper()}: {self.name}]\n"
        context += f"{self.description}"
        return context


@dataclass
class EntityLink:
    """Links an entity to a specific scene/prompt for usage tracking."""
    id: int
    entity_id: int
    run_id: str
    scene_key: str  # e.g., "scene_1_HOOK"
    created_at: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "entity_id": self.entity_id,
            "run_id": self.run_id,
            "scene_key": self.scene_key,
            "created_at": self.created_at,
        }

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "run_id": self.run_id,
            "artifact_type": self.artifact_type.value,
            "item_key": self.item_key,
            "version": self.version,
            "prompt_text": self.prompt_text,
            "notes": self.notes,
            "image_path": self.image_path,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PromptVersion":
        """Create from dictionary."""
        return cls(
            id=data.get("id", 0),
            run_id=data.get("run_id", ""),
            artifact_type=ArtifactType(data.get("artifact_type", "nanobanana")),
            item_key=data.get("item_key", ""),
            version=data.get("version", 1),
            prompt_text=data.get("prompt_text", ""),
            notes=data.get("notes"),
            image_path=data.get("image_path"),
            created_at=data.get("created_at"),
            created_by=data.get("created_by", "system"),
            status=PromptStatus(data.get("status", "active")),
        )


class RunStore:
    """
    SQLite-based run state persistence.

    Minimal schema for tracking pipeline runs.
    """

    def __init__(self, db_path: Path | None = None):
        """
        Initialize RunStore.

        Args:
            db_path: Path to SQLite database. Defaults to content_engine/data/runs.db
        """
        if db_path is None:
            db_path = Path(__file__).parent.parent / "data" / "runs.db"

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Create tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            # Main runs table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    stage TEXT NOT NULL,
                    approvals_pending TEXT NOT NULL DEFAULT '[]',
                    config_json TEXT NOT NULL,
                    output_path TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    error_message TEXT,
                    display_title TEXT,
                    short_title TEXT,
                    notes TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_runs_stage ON runs(stage)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_runs_updated ON runs(updated_at DESC)
            """)

            # Feedback table for post-publish reviews
            conn.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    run_id TEXT PRIMARY KEY,
                    script_quality INTEGER,
                    hook_strength INTEGER,
                    visual_match INTEGER,
                    tags TEXT DEFAULT '[]',
                    publish_status TEXT,
                    platform TEXT,
                    posted_url TEXT,
                    post_date TEXT,
                    views INTEGER,
                    avg_watch_time REAL,
                    retention_pct REAL,
                    likes INTEGER,
                    shares INTEGER,
                    comments INTEGER,
                    feedback_notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                )
            """)

            # Migrate feedback table if needed (add new columns)
            self._migrate_feedback_table(conn)

            # Preset tuning memos
            conn.execute("""
                CREATE TABLE IF NOT EXISTS preset_tuning (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    preset_type TEXT NOT NULL,
                    preset_name TEXT NOT NULL,
                    memo_text TEXT,
                    avg_script_quality REAL,
                    avg_hook_strength REAL,
                    avg_visual_match REAL,
                    common_tags TEXT DEFAULT '[]',
                    total_runs INTEGER DEFAULT 0,
                    updated_at TEXT NOT NULL,
                    UNIQUE(preset_type, preset_name)
                )
            """)

            # Prompt versions for regeneration tracking
            conn.execute("""
                CREATE TABLE IF NOT EXISTS prompt_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    artifact_type TEXT NOT NULL,
                    item_key TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    prompt_text TEXT NOT NULL,
                    notes TEXT,
                    image_path TEXT,
                    created_at TEXT NOT NULL,
                    created_by TEXT NOT NULL DEFAULT 'system',
                    status TEXT NOT NULL DEFAULT 'active',
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_prompt_versions_run ON prompt_versions(run_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_prompt_versions_key ON prompt_versions(run_id, artifact_type, item_key)
            """)

            # Entities table for continuity tracking
            conn.execute("""
                CREATE TABLE IF NOT EXISTS entities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    reference_image_path TEXT,
                    created_from_scene_key TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_entities_run ON entities(run_id)
            """)

            # Entity links table - tracks which scenes use which entities
            conn.execute("""
                CREATE TABLE IF NOT EXISTS entity_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_id INTEGER NOT NULL,
                    run_id TEXT NOT NULL,
                    scene_key TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (entity_id) REFERENCES entities(id),
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_entity_links_entity ON entity_links(entity_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_entity_links_run ON entity_links(run_id, scene_key)
            """)

            # Migrate existing tables if needed (add new columns)
            self._migrate_runs_table(conn)
            self._migrate_prompt_versions_table(conn)

    def _migrate_runs_table(self, conn):
        """Add new columns to existing runs table if needed."""
        cursor = conn.execute("PRAGMA table_info(runs)")
        columns = {row[1] for row in cursor.fetchall()}

        if "display_title" not in columns:
            conn.execute("ALTER TABLE runs ADD COLUMN display_title TEXT")
        if "short_title" not in columns:
            conn.execute("ALTER TABLE runs ADD COLUMN short_title TEXT")
        if "notes" not in columns:
            conn.execute("ALTER TABLE runs ADD COLUMN notes TEXT")
        if "current_stage_name" not in columns:
            conn.execute("ALTER TABLE runs ADD COLUMN current_stage_name TEXT")
        if "progress_percent" not in columns:
            conn.execute("ALTER TABLE runs ADD COLUMN progress_percent INTEGER DEFAULT 0")
        if "posted_at" not in columns:
            conn.execute("ALTER TABLE runs ADD COLUMN posted_at TEXT")

    def _migrate_prompt_versions_table(self, conn):
        """Add new columns to existing prompt_versions table for sequential/continuity tracking."""
        cursor = conn.execute("PRAGMA table_info(prompt_versions)")
        columns = {row[1] for row in cursor.fetchall()}

        if "locked_at" not in columns:
            conn.execute("ALTER TABLE prompt_versions ADD COLUMN locked_at TEXT")
        if "depends_on_scene" not in columns:
            conn.execute("ALTER TABLE prompt_versions ADD COLUMN depends_on_scene TEXT")
        if "depends_on_version_id" not in columns:
            conn.execute("ALTER TABLE prompt_versions ADD COLUMN depends_on_version_id INTEGER")
        if "continuity_warning" not in columns:
            conn.execute("ALTER TABLE prompt_versions ADD COLUMN continuity_warning TEXT")

    def _migrate_feedback_table(self, conn):
        """Add new columns to existing feedback table if needed."""
        cursor = conn.execute("PRAGMA table_info(feedback)")
        columns = {row[1] for row in cursor.fetchall()}

        if "posted_url" not in columns:
            conn.execute("ALTER TABLE feedback ADD COLUMN posted_url TEXT")
        if "post_date" not in columns:
            conn.execute("ALTER TABLE feedback ADD COLUMN post_date TEXT")

    def _now(self) -> str:
        """Get current timestamp."""
        return datetime.utcnow().isoformat()

    def _row_to_record(self, row: tuple) -> RunRecord:
        """Convert database row to RunRecord."""
        return RunRecord(
            run_id=row[0],
            stage=RunStage(row[1]),
            approvals_pending=json.loads(row[2]),
            config_json=row[3],
            output_path=row[4],
            created_at=row[5],
            updated_at=row[6],
            error_message=row[7] if len(row) > 7 else None,
            display_title=row[8] if len(row) > 8 else None,
            short_title=row[9] if len(row) > 9 else None,
            notes=row[10] if len(row) > 10 else None,
            current_stage_name=row[11] if len(row) > 11 else None,
            progress_percent=row[12] if len(row) > 12 else 0,
            posted_at=row[13] if len(row) > 13 else None,
        )

    def _row_to_feedback(self, row: tuple) -> FeedbackRecord:
        """Convert database row to FeedbackRecord."""
        # Actual DB schema (columns added via ALTER TABLE at end):
        # 0: run_id, 1: script_quality, 2: hook_strength, 3: visual_match, 4: tags,
        # 5: publish_status, 6: platform, 7: views, 8: avg_watch_time, 9: retention_pct,
        # 10: likes, 11: shares, 12: comments, 13: feedback_notes, 14: created_at,
        # 15: updated_at, 16: posted_url, 17: post_date

        def safe_json_loads(val):
            """Safely parse JSON, handling None and invalid types."""
            if val is None:
                return []
            if isinstance(val, str):
                try:
                    return json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    return []
            return []

        return FeedbackRecord(
            run_id=row[0] if len(row) > 0 else None,
            script_quality=row[1] if len(row) > 1 else None,
            hook_strength=row[2] if len(row) > 2 else None,
            visual_match=row[3] if len(row) > 3 else None,
            tags=safe_json_loads(row[4] if len(row) > 4 else None),
            publish_status=row[5] if len(row) > 5 else None,
            platform=row[6] if len(row) > 6 else None,
            views=row[7] if len(row) > 7 else None,
            avg_watch_time=row[8] if len(row) > 8 else None,
            retention_pct=row[9] if len(row) > 9 else None,
            likes=row[10] if len(row) > 10 else None,
            shares=row[11] if len(row) > 11 else None,
            comments=row[12] if len(row) > 12 else None,
            feedback_notes=row[13] if len(row) > 13 else None,
            created_at=row[14] if len(row) > 14 else None,
            updated_at=row[15] if len(row) > 15 else None,
            posted_url=row[16] if len(row) > 16 else None,
            post_date=row[17] if len(row) > 17 else None,
        )

    def create_run(self, run_id: str, config: dict) -> RunRecord:
        """
        Create a new run record.

        Args:
            run_id: Unique run identifier
            config: Run configuration dict

        Returns:
            Created RunRecord
        """
        now = self._now()
        record = RunRecord(
            run_id=run_id,
            stage=RunStage.INIT,
            approvals_pending=[],
            config_json=json.dumps(config),
            output_path=None,
            created_at=now,
            updated_at=now,
        )

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO runs (run_id, stage, approvals_pending, config_json,
                                  output_path, created_at, updated_at, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.run_id,
                    record.stage.value,
                    json.dumps(record.approvals_pending),
                    record.config_json,
                    record.output_path,
                    record.created_at,
                    record.updated_at,
                    record.error_message,
                ),
            )

        return record

    def get_run(self, run_id: str, enrich: bool = True) -> RunRecord | None:
        """
        Get a run by ID.

        Args:
            run_id: Run identifier
            enrich: If True, compute and set workflow stage fields

        Returns:
            RunRecord if found, None otherwise
        """
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()

            if row:
                record = self._row_to_record(row)
                if enrich:
                    return self.enrich_with_workflow_stage(record)
                return record
        return None

    def update_stage(
        self,
        run_id: str,
        stage: RunStage,
        output_path: str | None = None,
        approvals_pending: list[str] | None = None,
        error_message: str | None = None,
        current_stage_name: str | None = None,
        progress_percent: int | None = None,
    ) -> bool:
        """
        Update run stage and optional fields.

        Args:
            run_id: Run identifier
            stage: New stage
            output_path: Optional output path to set
            approvals_pending: Optional approvals list to set
            error_message: Optional error message
            current_stage_name: Human-readable stage name
            progress_percent: Progress percentage (0-100)

        Returns:
            True if updated, False if run not found
        """
        fields = ["stage = ?", "updated_at = ?"]
        values: list[Any] = [stage.value, self._now()]

        if output_path is not None:
            fields.append("output_path = ?")
            values.append(output_path)

        if approvals_pending is not None:
            fields.append("approvals_pending = ?")
            values.append(json.dumps(approvals_pending))

        if error_message is not None:
            fields.append("error_message = ?")
            values.append(error_message)

        if current_stage_name is not None:
            fields.append("current_stage_name = ?")
            values.append(current_stage_name)

        if progress_percent is not None:
            fields.append("progress_percent = ?")
            values.append(progress_percent)

        values.append(run_id)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                f"UPDATE runs SET {', '.join(fields)} WHERE run_id = ?",
                values,
            )
            return cursor.rowcount > 0

    def update_progress(
        self,
        run_id: str,
        stage_name: str,
        progress_percent: int,
    ) -> bool:
        """
        Update just the progress info for a running job.

        Args:
            run_id: Run identifier
            stage_name: Human-readable stage name
            progress_percent: Progress percentage (0-100)

        Returns:
            True if updated
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                UPDATE runs
                SET current_stage_name = ?, progress_percent = ?, updated_at = ?
                WHERE run_id = ?
                """,
                (stage_name, progress_percent, self._now(), run_id),
            )
            return cursor.rowcount > 0

    def get_pending_runs(self) -> list[RunRecord]:
        """Get runs awaiting approval."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT * FROM runs
                WHERE stage IN (?, ?)
                ORDER BY updated_at DESC
                """,
                (
                    RunStage.AWAITING_SCRIPT_APPROVAL.value,
                    RunStage.AWAITING_VOICEOVER_APPROVAL.value,
                ),
            ).fetchall()

            return [self._row_to_record(row) for row in rows]

    def get_recent_runs(self, limit: int = 10) -> list[RunRecord]:
        """Get recent runs."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM runs ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()

            return [self._row_to_record(row) for row in rows]

    # ========================================
    # WORKFLOW STAGE METHODS
    # ========================================

    def compute_workflow_stage(self, run_id: str) -> WorkflowStage:
        """
        Compute the current workflow stage for a run.

        Decision tree:
        1. If posted_at is set -> POSTED or REVIEW_READY
        2. If stage < complete and not awaiting_script_approval -> based on RunStage
        3. If awaiting_script_approval -> SCRIPT_PENDING
        4. If complete but not all scenes locked -> VISUALS_PENDING
        5. If all scenes locked but video not ready -> VIDEO_PENDING
        6. If video ready -> READY_TO_POST

        Args:
            run_id: Run identifier

        Returns:
            Computed WorkflowStage
        """
        # Use enrich=False to avoid recursion
        record = self.get_run(run_id, enrich=False)
        if not record:
            return WorkflowStage.SCRIPT_PENDING

        # Check if posted
        if record.posted_at:
            # Check if has performance data for REVIEW_READY
            feedback = self.get_feedback(run_id)
            if feedback and (feedback.views or feedback.script_quality or feedback.hook_strength):
                return WorkflowStage.REVIEW_READY
            return WorkflowStage.POSTED

        # Map RunStage to WorkflowStage
        if record.stage in [
            RunStage.INIT, RunStage.STARTING, RunStage.QUEUED, RunStage.RUNNING,
            RunStage.DRIVE_CHECK, RunStage.RESEARCH, RunStage.DRAFT,
            RunStage.HOOK_REVIEW, RunStage.RELEVANCE, RunStage.FINALIZE,
            RunStage.AWAITING_SCRIPT_APPROVAL,
        ]:
            return WorkflowStage.SCRIPT_PENDING

        if record.stage == RunStage.FAILED:
            return WorkflowStage.SCRIPT_PENDING  # Failed runs stay in script stage

        if record.stage in [
            RunStage.SCRIPT_APPROVED, RunStage.GENERATING_SHOT_LIST,
            RunStage.GENERATING_VISUALS, RunStage.GENERATING_STOCK_QUERIES,
        ]:
            return WorkflowStage.VISUALS_PENDING

        # For COMPLETE runs, check scene lock status
        if record.stage == RunStage.COMPLETE:
            scene_stats = self._get_scene_stats(run_id)
            total_scenes = scene_stats["total"]
            locked_scenes = scene_stats["locked"]
            has_warnings = scene_stats["has_warnings"]

            if total_scenes == 0:
                # No prompts yet
                return WorkflowStage.VISUALS_PENDING

            if locked_scenes < total_scenes or has_warnings:
                return WorkflowStage.VISUALS_PENDING

            # All scenes locked, no warnings -> video stage
            # For now, we consider this READY_TO_POST since we don't have video finalization yet
            return WorkflowStage.READY_TO_POST

        return WorkflowStage.SCRIPT_PENDING

    def _get_scene_stats(self, run_id: str) -> dict:
        """Get scene statistics for workflow stage computation."""
        with sqlite3.connect(self.db_path) as conn:
            # Count total ACTIVE/PENDING/LOCKED NanoBanana prompts
            rows = conn.execute(
                """
                SELECT status, COUNT(*), SUM(CASE WHEN continuity_warning IS NOT NULL THEN 1 ELSE 0 END)
                FROM prompt_versions
                WHERE run_id = ? AND artifact_type = ?
                AND status IN (?, ?, ?)
                GROUP BY status
                """,
                (run_id, ArtifactType.NANOBANANA.value,
                 PromptStatus.ACTIVE.value, PromptStatus.PENDING.value, PromptStatus.LOCKED.value),
            ).fetchall()

            total = 0
            locked = 0
            warnings = 0

            for status, count, warning_count in rows:
                total += count
                if status == PromptStatus.LOCKED.value:
                    locked += count
                warnings += warning_count or 0

            return {
                "total": total,
                "locked": locked,
                "has_warnings": warnings > 0,
            }

    def enrich_with_workflow_stage(self, record: RunRecord) -> RunRecord:
        """
        Enrich a RunRecord with computed workflow stage and related fields.

        This populates the _workflow_stage, _has_continuity_warnings,
        _locked_scene_count, and _total_scene_count fields.

        Args:
            record: RunRecord to enrich

        Returns:
            Enriched RunRecord (same object, modified in place)
        """
        record._workflow_stage = self.compute_workflow_stage(record.run_id)
        scene_stats = self._get_scene_stats(record.run_id)
        record._has_continuity_warnings = scene_stats["has_warnings"]
        record._locked_scene_count = scene_stats["locked"]
        record._total_scene_count = scene_stats["total"]
        return record

    def get_queue_runs(self, limit: int = 50) -> list[RunRecord]:
        """
        Get runs for the Queue view (not posted).

        Returns runs where workflow_stage is not POSTED or REVIEW_READY.

        Args:
            limit: Maximum number of runs to return

        Returns:
            List of enriched RunRecord objects
        """
        with sqlite3.connect(self.db_path) as conn:
            # Get runs that are not posted
            rows = conn.execute(
                """
                SELECT * FROM runs
                WHERE posted_at IS NULL
                AND stage NOT IN (?, ?)
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (RunStage.FAILED.value, RunStage.CANCELLED.value, limit),
            ).fetchall()

            runs = [self._row_to_record(row) for row in rows]
            return [self.enrich_with_workflow_stage(r) for r in runs]

    def get_posted_runs(self, limit: int = 50) -> list[RunRecord]:
        """
        Get runs for the Reviews view (posted only).

        Args:
            limit: Maximum number of runs to return

        Returns:
            List of enriched RunRecord objects
        """
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT * FROM runs
                WHERE posted_at IS NOT NULL
                ORDER BY posted_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

            runs = [self._row_to_record(row) for row in rows]
            return [self.enrich_with_workflow_stage(r) for r in runs]

    def get_library_runs(
        self,
        limit: int = 50,
        stage_filter: str | None = None,
        has_warnings: bool | None = None,
        sort_by: str = "updated_at",
    ) -> list[RunRecord]:
        """
        Get runs for the Library view with filters.

        Args:
            limit: Maximum number of runs
            stage_filter: Filter by workflow stage (script_pending, visuals_pending, etc.)
            has_warnings: Filter by presence of continuity warnings
            sort_by: Sort field (created_at, updated_at)

        Returns:
            List of enriched RunRecord objects
        """
        with sqlite3.connect(self.db_path) as conn:
            query = "SELECT * FROM runs WHERE 1=1"
            params = []

            # Stage filter (basic - workflow stage computed post-fetch)
            if stage_filter == "posted":
                query += " AND posted_at IS NOT NULL"
            elif stage_filter == "script_pending":
                query += " AND stage = ?"
                params.append(RunStage.AWAITING_SCRIPT_APPROVAL.value)
            elif stage_filter:
                query += " AND posted_at IS NULL"

            # Sort
            if sort_by == "created_at":
                query += " ORDER BY created_at DESC"
            else:
                query += " ORDER BY updated_at DESC"

            query += " LIMIT ?"
            params.append(limit)

            rows = conn.execute(query, params).fetchall()
            runs = [self._row_to_record(row) for row in rows]

            # Enrich and filter by workflow stage if needed
            enriched = [self.enrich_with_workflow_stage(r) for r in runs]

            # Filter by stage if specified and not already handled
            if stage_filter and stage_filter not in ["posted", "script_pending"]:
                try:
                    target_stage = WorkflowStage(stage_filter)
                    enriched = [r for r in enriched if r.workflow_stage == target_stage]
                except ValueError:
                    pass

            # Filter by warnings if specified
            if has_warnings is not None:
                enriched = [r for r in enriched if r.has_continuity_warnings == has_warnings]

            return enriched

    def post_run(self, run_id: str) -> bool:
        """
        Mark a run as posted.

        Sets the posted_at timestamp, transitioning the run to POSTED workflow stage.

        Args:
            run_id: Run identifier

        Returns:
            True if updated successfully
        """
        now = self._now()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                UPDATE runs
                SET posted_at = ?, updated_at = ?
                WHERE run_id = ? AND posted_at IS NULL
                """,
                (now, now, run_id),
            )
            return cursor.rowcount > 0

    def unpost_run(self, run_id: str) -> bool:
        """
        Unmark a run as posted (move back to queue).

        Clears the posted_at timestamp.

        Args:
            run_id: Run identifier

        Returns:
            True if updated successfully
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                UPDATE runs
                SET posted_at = NULL, updated_at = ?
                WHERE run_id = ? AND posted_at IS NOT NULL
                """,
                (self._now(), run_id),
            )
            return cursor.rowcount > 0

    def delete_run(self, run_id: str) -> bool:
        """Delete a run record."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM runs WHERE run_id = ?", (run_id,)
            )
            return cursor.rowcount > 0

    def update_title(
        self,
        run_id: str,
        display_title: str,
        short_title: str | None = None,
    ) -> bool:
        """
        Update run display title.

        Args:
            run_id: Run identifier
            display_title: Full display title
            short_title: Optional shortened title

        Returns:
            True if updated
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                UPDATE runs
                SET display_title = ?, short_title = ?, updated_at = ?
                WHERE run_id = ?
                """,
                (display_title, short_title, self._now(), run_id),
            )
            return cursor.rowcount > 0

    def update_notes(self, run_id: str, notes: str) -> bool:
        """
        Update run notes.

        Also writes notes.md to the run's output folder if it exists.

        Args:
            run_id: Run identifier
            notes: Notes text

        Returns:
            True if updated
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "UPDATE runs SET notes = ?, updated_at = ? WHERE run_id = ?",
                (notes, self._now(), run_id),
            )
            updated = cursor.rowcount > 0

        # Also write to output folder
        if updated:
            record = self.get_run(run_id)
            if record and record.output_path:
                output_path = Path(record.output_path)
                if output_path.exists():
                    notes_file = output_path / "notes.md"
                    notes_file.write_text(f"# Notes for {record.title}\n\n{notes}\n")

        return updated

    # === Feedback Methods ===

    def save_feedback(self, feedback: FeedbackRecord) -> bool:
        """
        Save or update feedback for a run.

        Also writes feedback.json to the run's output folder.

        Args:
            feedback: FeedbackRecord to save

        Returns:
            True if saved
        """
        now = self._now()
        with sqlite3.connect(self.db_path) as conn:
            # Check if exists
            exists = conn.execute(
                "SELECT 1 FROM feedback WHERE run_id = ?",
                (feedback.run_id,),
            ).fetchone()

            if exists:
                conn.execute(
                    """
                    UPDATE feedback SET
                        script_quality = ?, hook_strength = ?, visual_match = ?,
                        tags = ?, publish_status = ?, platform = ?,
                        posted_url = ?, post_date = ?,
                        views = ?, avg_watch_time = ?, retention_pct = ?,
                        likes = ?, shares = ?, comments = ?,
                        feedback_notes = ?, updated_at = ?
                    WHERE run_id = ?
                    """,
                    (
                        feedback.script_quality,
                        feedback.hook_strength,
                        feedback.visual_match,
                        json.dumps(feedback.tags),
                        feedback.publish_status,
                        feedback.platform,
                        feedback.posted_url,
                        feedback.post_date,
                        feedback.views,
                        feedback.avg_watch_time,
                        feedback.retention_pct,
                        feedback.likes,
                        feedback.shares,
                        feedback.comments,
                        feedback.feedback_notes,
                        now,
                        feedback.run_id,
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO feedback (
                        run_id, script_quality, hook_strength, visual_match,
                        tags, publish_status, platform,
                        posted_url, post_date,
                        views, avg_watch_time, retention_pct,
                        likes, shares, comments,
                        feedback_notes, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        feedback.run_id,
                        feedback.script_quality,
                        feedback.hook_strength,
                        feedback.visual_match,
                        json.dumps(feedback.tags),
                        feedback.publish_status,
                        feedback.platform,
                        feedback.posted_url,
                        feedback.post_date,
                        feedback.views,
                        feedback.avg_watch_time,
                        feedback.retention_pct,
                        feedback.likes,
                        feedback.shares,
                        feedback.comments,
                        feedback.feedback_notes,
                        now,
                        now,
                    ),
                )

        # Write to output folder
        record = self.get_run(feedback.run_id)
        if record and record.output_path:
            output_path = Path(record.output_path)
            if output_path.exists():
                feedback_file = output_path / "feedback.json"
                feedback_file.write_text(json.dumps(feedback.to_dict(), indent=2))

        return True

    def get_feedback(self, run_id: str) -> FeedbackRecord | None:
        """Get feedback for a run."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM feedback WHERE run_id = ?",
                (run_id,),
            ).fetchone()

            if row:
                return self._row_to_feedback(row)
        return None

    def get_runs_with_feedback(
        self,
        niche: str | None = None,
        style: str | None = None,
        limit: int = 100,
    ) -> list[tuple[RunRecord, FeedbackRecord]]:
        """Get runs that have feedback, optionally filtered by niche/style."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT r.*, f.*
                FROM runs r
                INNER JOIN feedback f ON r.run_id = f.run_id
                ORDER BY f.updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

            results = []
            for row in rows:
                # First 14 columns are runs (0-13), rest are feedback (14-31 for 18 cols)
                # _row_to_feedback handles variable column count
                run = self._row_to_record(row[:14])
                feedback = self._row_to_feedback(row[14:])

                # Filter by niche/style if specified
                config = run.config
                if niche and config.get("niche") != niche:
                    continue
                if style and config.get("style") != style:
                    continue

                results.append((run, feedback))

            return results

    # === Preset Stats and Tuning ===

    def get_preset_stats(
        self,
        preset_type: str,
        preset_name: str,
    ) -> dict:
        """
        Get aggregated stats for a preset.

        Args:
            preset_type: "niche" or "style"
            preset_name: Preset name

        Returns:
            Dict with avg ratings, common tags, total runs
        """
        # Get all runs with this preset that have feedback
        with sqlite3.connect(self.db_path) as conn:
            # Get runs with this preset
            rows = conn.execute(
                """
                SELECT r.config_json, f.script_quality, f.hook_strength,
                       f.visual_match, f.tags
                FROM runs r
                INNER JOIN feedback f ON r.run_id = f.run_id
                WHERE f.script_quality IS NOT NULL
                """,
            ).fetchall()

            matching_runs = []
            for row in rows:
                config = json.loads(row[0])
                if config.get(preset_type) == preset_name:
                    matching_runs.append({
                        "script_quality": row[1],
                        "hook_strength": row[2],
                        "visual_match": row[3],
                        "tags": json.loads(row[4]) if row[4] else [],
                    })

            if not matching_runs:
                return {
                    "total_runs": 0,
                    "avg_script_quality": None,
                    "avg_hook_strength": None,
                    "avg_visual_match": None,
                    "common_tags": [],
                }

            # Calculate averages
            qualities = [r["script_quality"] for r in matching_runs if r["script_quality"]]
            hooks = [r["hook_strength"] for r in matching_runs if r["hook_strength"]]
            visuals = [r["visual_match"] for r in matching_runs if r["visual_match"]]

            # Count tags
            tag_counts: dict[str, int] = {}
            for r in matching_runs:
                for tag in r["tags"]:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1

            # Sort tags by frequency
            common_tags = sorted(tag_counts.keys(), key=lambda t: tag_counts[t], reverse=True)[:10]

            return {
                "total_runs": len(matching_runs),
                "avg_script_quality": sum(qualities) / len(qualities) if qualities else None,
                "avg_hook_strength": sum(hooks) / len(hooks) if hooks else None,
                "avg_visual_match": sum(visuals) / len(visuals) if visuals else None,
                "common_tags": common_tags,
            }

    def get_tuning_memo(
        self,
        preset_type: str,
        preset_name: str,
    ) -> PresetTuningMemo | None:
        """Get tuning memo for a preset."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT preset_type, preset_name, memo_text,
                       avg_script_quality, avg_hook_strength, avg_visual_match,
                       common_tags, total_runs, updated_at
                FROM preset_tuning
                WHERE preset_type = ? AND preset_name = ?
                """,
                (preset_type, preset_name),
            ).fetchone()

            if row:
                return PresetTuningMemo(
                    preset_type=row[0],
                    preset_name=row[1],
                    memo_text=row[2],
                    avg_script_quality=row[3],
                    avg_hook_strength=row[4],
                    avg_visual_match=row[5],
                    common_tags=json.loads(row[6]) if row[6] else [],
                    total_runs=row[7],
                    updated_at=row[8],
                )
        return None

    def update_tuning_memo(
        self,
        preset_type: str,
        preset_name: str,
        memo_text: str | None = None,
        auto_update_stats: bool = True,
    ) -> PresetTuningMemo:
        """
        Update tuning memo for a preset.

        Args:
            preset_type: "niche" or "style"
            preset_name: Preset name
            memo_text: Optional custom memo text
            auto_update_stats: If True, recalculate stats from feedback

        Returns:
            Updated PresetTuningMemo
        """
        now = self._now()

        # Get stats if auto-updating
        stats = self.get_preset_stats(preset_type, preset_name) if auto_update_stats else {}

        with sqlite3.connect(self.db_path) as conn:
            # Check if exists
            exists = conn.execute(
                "SELECT memo_text FROM preset_tuning WHERE preset_type = ? AND preset_name = ?",
                (preset_type, preset_name),
            ).fetchone()

            if exists:
                # Keep existing memo if not provided
                if memo_text is None:
                    memo_text = exists[0]

                conn.execute(
                    """
                    UPDATE preset_tuning SET
                        memo_text = ?,
                        avg_script_quality = ?,
                        avg_hook_strength = ?,
                        avg_visual_match = ?,
                        common_tags = ?,
                        total_runs = ?,
                        updated_at = ?
                    WHERE preset_type = ? AND preset_name = ?
                    """,
                    (
                        memo_text,
                        stats.get("avg_script_quality"),
                        stats.get("avg_hook_strength"),
                        stats.get("avg_visual_match"),
                        json.dumps(stats.get("common_tags", [])),
                        stats.get("total_runs", 0),
                        now,
                        preset_type,
                        preset_name,
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO preset_tuning (
                        preset_type, preset_name, memo_text,
                        avg_script_quality, avg_hook_strength, avg_visual_match,
                        common_tags, total_runs, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        preset_type,
                        preset_name,
                        memo_text or "",
                        stats.get("avg_script_quality"),
                        stats.get("avg_hook_strength"),
                        stats.get("avg_visual_match"),
                        json.dumps(stats.get("common_tags", [])),
                        stats.get("total_runs", 0),
                        now,
                    ),
                )

        return self.get_tuning_memo(preset_type, preset_name)

    # === Review Import Drafts ===

    def _init_import_drafts_table(self):
        """Create import drafts table if not exists."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS review_import_drafts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT,
                    platform TEXT NOT NULL,
                    post_url TEXT,
                    image_path TEXT NOT NULL,
                    extracted_json TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    confirmed_at TEXT,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_drafts_status ON review_import_drafts(status)
            """)

    def create_import_draft(
        self,
        platform: str,
        image_path: str,
        extracted_json: dict,
        run_id: str | None = None,
        post_url: str | None = None,
    ) -> int:
        """
        Create a new review import draft.

        Args:
            platform: Platform name (tiktok, instagram, youtube)
            image_path: Path to uploaded screenshot
            extracted_json: Extracted metrics as dict
            run_id: Optional run ID to link to
            post_url: Optional post URL

        Returns:
            Draft ID
        """
        self._init_import_drafts_table()
        now = self._now()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO review_import_drafts (
                    run_id, platform, post_url, image_path,
                    extracted_json, status, created_at
                ) VALUES (?, ?, ?, ?, ?, 'pending', ?)
                """,
                (
                    run_id,
                    platform,
                    post_url,
                    image_path,
                    json.dumps(extracted_json),
                    now,
                ),
            )
            return cursor.lastrowid

    def get_import_draft(self, draft_id: int) -> dict | None:
        """Get an import draft by ID."""
        self._init_import_drafts_table()

        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM review_import_drafts WHERE id = ?",
                (draft_id,),
            ).fetchone()

            if not row:
                return None

            return {
                "id": row[0],
                "run_id": row[1],
                "platform": row[2],
                "post_url": row[3],
                "image_path": row[4],
                "extracted_json": json.loads(row[5]) if row[5] else {},
                "status": row[6],
                "created_at": row[7],
                "confirmed_at": row[8],
            }

    def get_pending_drafts(self, limit: int = 20) -> list[dict]:
        """Get pending import drafts."""
        self._init_import_drafts_table()

        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT * FROM review_import_drafts
                WHERE status = 'pending'
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

            return [
                {
                    "id": row[0],
                    "run_id": row[1],
                    "platform": row[2],
                    "post_url": row[3],
                    "image_path": row[4],
                    "extracted_json": json.loads(row[5]) if row[5] else {},
                    "status": row[6],
                    "created_at": row[7],
                    "confirmed_at": row[8],
                }
                for row in rows
            ]

    def confirm_import_draft(
        self,
        draft_id: int,
        run_id: str,
        confirmed_values: dict,
    ) -> bool:
        """
        Confirm an import draft and save as feedback.

        Args:
            draft_id: Draft ID
            run_id: Run ID to link feedback to
            confirmed_values: User-confirmed metric values

        Returns:
            True if successful
        """
        self._init_import_drafts_table()
        now = self._now()

        # Get draft
        draft = self.get_import_draft(draft_id)
        if not draft or draft["status"] != "pending":
            return False

        # Create feedback record
        feedback = FeedbackRecord(
            run_id=run_id,
            platform=draft["platform"],
            posted_url=draft.get("post_url") or confirmed_values.get("posted_url"),
            post_date=confirmed_values.get("post_date"),
            views=confirmed_values.get("views"),
            avg_watch_time=confirmed_values.get("avg_watch_time_seconds"),
            retention_pct=confirmed_values.get("retention_percent"),
            likes=confirmed_values.get("likes"),
            comments=confirmed_values.get("comments"),
            shares=confirmed_values.get("shares"),
            publish_status="published",
            feedback_notes=confirmed_values.get("feedback_notes"),
        )

        # Save feedback
        self.save_feedback(feedback)

        # Mark draft as confirmed
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE review_import_drafts
                SET status = 'confirmed', run_id = ?, confirmed_at = ?
                WHERE id = ?
                """,
                (run_id, now, draft_id),
            )

        return True

    def delete_import_draft(self, draft_id: int) -> bool:
        """Delete an import draft."""
        self._init_import_drafts_table()

        with sqlite3.connect(self.db_path) as conn:
            result = conn.execute(
                "DELETE FROM review_import_drafts WHERE id = ?",
                (draft_id,),
            )
            return result.rowcount > 0

    # === Prompt Version Methods ===

    def _row_to_prompt_version(self, row: tuple) -> PromptVersion:
        """Convert database row to PromptVersion."""
        return PromptVersion(
            id=row[0],
            run_id=row[1],
            artifact_type=ArtifactType(row[2]),
            item_key=row[3],
            version=row[4],
            prompt_text=row[5],
            notes=row[6],
            image_path=row[7],
            created_at=row[8],
            created_by=row[9],
            status=PromptStatus(row[10]),
            locked_at=row[11] if len(row) > 11 else None,
            depends_on_scene=row[12] if len(row) > 12 else None,
            depends_on_version_id=row[13] if len(row) > 13 else None,
            continuity_warning=row[14] if len(row) > 14 else None,
        )

    def create_prompt_version(
        self,
        run_id: str,
        artifact_type: ArtifactType,
        item_key: str,
        prompt_text: str,
        notes: str | None = None,
        image_path: str | None = None,
        created_by: str = "system",
        status: PromptStatus = PromptStatus.ACTIVE,
        depends_on_scene: str | None = None,
        depends_on_version_id: int | None = None,
    ) -> PromptVersion:
        """
        Create a new prompt version.

        Automatically increments version number and supersedes previous versions.

        Args:
            run_id: Run identifier
            artifact_type: Type of artifact (nanobanana, stock_query, shot_list)
            item_key: Item key within the artifact (e.g., "scene_1")
            prompt_text: The prompt text
            notes: Optional notes about this version
            image_path: Optional path to generated image
            created_by: Who created this version ("system" or "user")
            status: Initial status (ACTIVE, PENDING, etc.)
            depends_on_scene: Previous scene this depends on for continuity
            depends_on_version_id: Version ID of the depended scene

        Returns:
            Created PromptVersion
        """
        now = self._now()

        with sqlite3.connect(self.db_path) as conn:
            # Get current max version for this item
            row = conn.execute(
                """
                SELECT MAX(version) FROM prompt_versions
                WHERE run_id = ? AND artifact_type = ? AND item_key = ?
                """,
                (run_id, artifact_type.value, item_key),
            ).fetchone()

            current_version = row[0] if row[0] else 0
            new_version = current_version + 1

            # Supersede previous active versions (not locked ones)
            conn.execute(
                """
                UPDATE prompt_versions
                SET status = ?
                WHERE run_id = ? AND artifact_type = ? AND item_key = ? AND status = ?
                """,
                (
                    PromptStatus.SUPERSEDED.value,
                    run_id,
                    artifact_type.value,
                    item_key,
                    PromptStatus.ACTIVE.value,
                ),
            )

            # Insert new version
            cursor = conn.execute(
                """
                INSERT INTO prompt_versions (
                    run_id, artifact_type, item_key, version, prompt_text,
                    notes, image_path, created_at, created_by, status,
                    depends_on_scene, depends_on_version_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    artifact_type.value,
                    item_key,
                    new_version,
                    prompt_text,
                    notes,
                    image_path,
                    now,
                    created_by,
                    status.value,
                    depends_on_scene,
                    depends_on_version_id,
                ),
            )

            return PromptVersion(
                id=cursor.lastrowid,
                run_id=run_id,
                artifact_type=artifact_type,
                item_key=item_key,
                version=new_version,
                prompt_text=prompt_text,
                notes=notes,
                image_path=image_path,
                created_at=now,
                created_by=created_by,
                status=status,
                depends_on_scene=depends_on_scene,
                depends_on_version_id=depends_on_version_id,
            )

    def get_prompt_version(self, version_id: int) -> PromptVersion | None:
        """Get a prompt version by ID."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM prompt_versions WHERE id = ?",
                (version_id,),
            ).fetchone()

            if row:
                return self._row_to_prompt_version(row)
        return None

    def get_active_prompt(
        self,
        run_id: str,
        artifact_type: ArtifactType,
        item_key: str,
    ) -> PromptVersion | None:
        """Get the currently active prompt version for an item."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT * FROM prompt_versions
                WHERE run_id = ? AND artifact_type = ? AND item_key = ? AND status = ?
                ORDER BY version DESC
                LIMIT 1
                """,
                (run_id, artifact_type.value, item_key, PromptStatus.ACTIVE.value),
            ).fetchone()

            if row:
                return self._row_to_prompt_version(row)
        return None

    def get_prompt_history(
        self,
        run_id: str,
        artifact_type: ArtifactType | None = None,
        item_key: str | None = None,
    ) -> list[PromptVersion]:
        """
        Get prompt version history for a run.

        Args:
            run_id: Run identifier
            artifact_type: Optional filter by artifact type
            item_key: Optional filter by item key

        Returns:
            List of PromptVersion records ordered by version descending
        """
        with sqlite3.connect(self.db_path) as conn:
            query = "SELECT * FROM prompt_versions WHERE run_id = ?"
            params: list[Any] = [run_id]

            if artifact_type:
                query += " AND artifact_type = ?"
                params.append(artifact_type.value)

            if item_key:
                query += " AND item_key = ?"
                params.append(item_key)

            query += " ORDER BY artifact_type, item_key, version DESC"

            rows = conn.execute(query, params).fetchall()
            return [self._row_to_prompt_version(row) for row in rows]

    def get_all_active_prompts(
        self,
        run_id: str,
        artifact_type: ArtifactType | None = None,
    ) -> list[PromptVersion]:
        """
        Get all currently active prompts for a run.

        Args:
            run_id: Run identifier
            artifact_type: Optional filter by artifact type

        Returns:
            List of active PromptVersion records
        """
        with sqlite3.connect(self.db_path) as conn:
            query = """
                SELECT * FROM prompt_versions
                WHERE run_id = ? AND status = ?
            """
            params: list[Any] = [run_id, PromptStatus.ACTIVE.value]

            if artifact_type:
                query += " AND artifact_type = ?"
                params.append(artifact_type.value)

            query += " ORDER BY artifact_type, item_key, version DESC"

            rows = conn.execute(query, params).fetchall()
            return [self._row_to_prompt_version(row) for row in rows]

    def get_prompts_for_artifacts(
        self,
        run_id: str,
        artifact_type: ArtifactType | None = None,
    ) -> list[PromptVersion]:
        """
        Get prompts for the artifacts page - includes ACTIVE and PENDING.

        For sequential scene generation:
        - Scene 1: ACTIVE (fully generated)
        - Scenes 2+: PENDING (waiting for previous scene to be locked)

        Args:
            run_id: Run identifier
            artifact_type: Optional filter by artifact type

        Returns:
            List of PromptVersion records (ACTIVE, PENDING, or LOCKED status)
        """
        with sqlite3.connect(self.db_path) as conn:
            query = """
                SELECT * FROM prompt_versions
                WHERE run_id = ? AND status IN (?, ?, ?)
            """
            params: list[Any] = [
                run_id,
                PromptStatus.ACTIVE.value,
                PromptStatus.PENDING.value,
                PromptStatus.LOCKED.value,
            ]

            if artifact_type:
                query += " AND artifact_type = ?"
                params.append(artifact_type.value)

            query += " ORDER BY artifact_type, item_key, version DESC"

            rows = conn.execute(query, params).fetchall()
            return [self._row_to_prompt_version(row) for row in rows]

    def update_prompt_image(
        self,
        version_id: int,
        image_path: str,
    ) -> bool:
        """
        Update the image path for a prompt version.

        Args:
            version_id: Prompt version ID
            image_path: Path to the generated image

        Returns:
            True if updated
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "UPDATE prompt_versions SET image_path = ? WHERE id = ?",
                (image_path, version_id),
            )
            return cursor.rowcount > 0

    def update_prompt_notes(
        self,
        version_id: int,
        notes: str,
    ) -> bool:
        """
        Update the notes for a prompt version.

        Args:
            version_id: Prompt version ID
            notes: Notes text

        Returns:
            True if updated
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "UPDATE prompt_versions SET notes = ? WHERE id = ?",
                (notes, version_id),
            )
            return cursor.rowcount > 0

    def get_prompt_stats(self, run_id: str) -> dict:
        """
        Get prompt statistics for a run.

        Returns:
            Dict with counts by artifact type and total versions
        """
        with sqlite3.connect(self.db_path) as conn:
            # Total prompts
            total_row = conn.execute(
                "SELECT COUNT(*) FROM prompt_versions WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            total = total_row[0] if total_row else 0

            # Active prompts
            active_row = conn.execute(
                "SELECT COUNT(*) FROM prompt_versions WHERE run_id = ? AND status = ?",
                (run_id, PromptStatus.ACTIVE.value),
            ).fetchone()
            active = active_row[0] if active_row else 0

            # By artifact type
            type_rows = conn.execute(
                """
                SELECT artifact_type, COUNT(*), SUM(CASE WHEN status = ? THEN 1 ELSE 0 END)
                FROM prompt_versions
                WHERE run_id = ?
                GROUP BY artifact_type
                """,
                (PromptStatus.ACTIVE.value, run_id),
            ).fetchall()

            by_type = {}
            for row in type_rows:
                by_type[row[0]] = {
                    "total": row[1],
                    "active": row[2],
                }

            return {
                "total_versions": total,
                "active_prompts": active,
                "by_type": by_type,
            }

    def get_prompt_by_version(
        self,
        run_id: str,
        artifact_type: ArtifactType,
        item_key: str,
        version: int,
    ) -> PromptVersion | None:
        """
        Get a specific version of a prompt.

        Args:
            run_id: Run identifier
            artifact_type: Type of artifact
            item_key: Item key
            version: Version number to get

        Returns:
            PromptVersion if found, None otherwise
        """
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT * FROM prompt_versions
                WHERE run_id = ? AND artifact_type = ? AND item_key = ? AND version = ?
                """,
                (run_id, artifact_type.value, item_key, version),
            ).fetchone()

            if row:
                return self._row_to_prompt_version(row)
        return None

    def get_prompt_version_info(
        self,
        run_id: str,
        artifact_type: ArtifactType,
        item_key: str,
    ) -> dict:
        """
        Get version info for a prompt item.

        Args:
            run_id: Run identifier
            artifact_type: Type of artifact
            item_key: Item key

        Returns:
            Dict with min_version, max_version, total_versions, active_version
        """
        with sqlite3.connect(self.db_path) as conn:
            # Get version range
            row = conn.execute(
                """
                SELECT MIN(version), MAX(version), COUNT(*)
                FROM prompt_versions
                WHERE run_id = ? AND artifact_type = ? AND item_key = ?
                """,
                (run_id, artifact_type.value, item_key),
            ).fetchone()

            min_ver = row[0] if row and row[0] else 1
            max_ver = row[1] if row and row[1] else 1
            total = row[2] if row else 0

            # Get active version
            active_row = conn.execute(
                """
                SELECT version FROM prompt_versions
                WHERE run_id = ? AND artifact_type = ? AND item_key = ? AND status = ?
                ORDER BY version DESC LIMIT 1
                """,
                (run_id, artifact_type.value, item_key, PromptStatus.ACTIVE.value),
            ).fetchone()

            active_ver = active_row[0] if active_row else max_ver

            return {
                "min_version": min_ver,
                "max_version": max_ver,
                "total_versions": total,
                "active_version": active_ver,
            }

    def activate_prompt_version(self, version_id: int) -> bool:
        """
        Make a specific prompt version active.

        Marks the specified version as ACTIVE and all other versions
        for that item as SUPERSEDED.

        Args:
            version_id: ID of the version to activate

        Returns:
            True if activated successfully
        """
        # First get the prompt to find its run_id, artifact_type, item_key
        prompt = self.get_prompt_version(version_id)
        if not prompt:
            return False

        with sqlite3.connect(self.db_path) as conn:
            # Supersede all versions for this item
            conn.execute(
                """
                UPDATE prompt_versions
                SET status = ?
                WHERE run_id = ? AND artifact_type = ? AND item_key = ?
                """,
                (
                    PromptStatus.SUPERSEDED.value,
                    prompt.run_id,
                    prompt.artifact_type.value,
                    prompt.item_key,
                ),
            )

            # Activate the specified version
            cursor = conn.execute(
                """
                UPDATE prompt_versions
                SET status = ?
                WHERE id = ?
                """,
                (PromptStatus.ACTIVE.value, version_id),
            )

            return cursor.rowcount > 0

    def get_all_versions_for_item(
        self,
        run_id: str,
        artifact_type: ArtifactType,
        item_key: str,
    ) -> list[PromptVersion]:
        """
        Get all versions of a specific prompt item.

        Args:
            run_id: Run identifier
            artifact_type: Type of artifact
            item_key: Item key

        Returns:
            List of all PromptVersion records for this item, ordered by version desc
        """
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT * FROM prompt_versions
                WHERE run_id = ? AND artifact_type = ? AND item_key = ?
                ORDER BY version DESC
                """,
                (run_id, artifact_type.value, item_key),
            ).fetchall()

            return [self._row_to_prompt_version(row) for row in rows]

    # === Sequential Generation & Continuity Methods ===

    def lock_prompt(self, version_id: int) -> bool:
        """
        Lock a prompt version, preventing further changes.

        Args:
            version_id: ID of the version to lock

        Returns:
            True if locked successfully
        """
        prompt = self.get_prompt_version(version_id)
        if not prompt:
            return False

        # Can only lock ACTIVE prompts
        if prompt.status != PromptStatus.ACTIVE:
            return False

        now = self._now()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                UPDATE prompt_versions
                SET status = ?, locked_at = ?
                WHERE id = ?
                """,
                (PromptStatus.LOCKED.value, now, version_id),
            )
            return cursor.rowcount > 0

    def unlock_prompt(self, version_id: int) -> bool:
        """
        Unlock a locked prompt, returning it to ACTIVE status.

        Args:
            version_id: ID of the version to unlock

        Returns:
            True if unlocked successfully
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                UPDATE prompt_versions
                SET status = ?, locked_at = NULL
                WHERE id = ? AND status = ?
                """,
                (PromptStatus.ACTIVE.value, version_id, PromptStatus.LOCKED.value),
            )
            return cursor.rowcount > 0

    def create_pending_prompt(
        self,
        run_id: str,
        artifact_type: ArtifactType,
        item_key: str,
        depends_on_scene: str | None = None,
    ) -> PromptVersion:
        """
        Create a pending (placeholder) prompt that hasn't been generated yet.

        Args:
            run_id: Run identifier
            artifact_type: Type of artifact
            item_key: Item key (e.g., "scene_2")
            depends_on_scene: Previous scene this depends on

        Returns:
            Created PromptVersion with PENDING status
        """
        return self.create_prompt_version(
            run_id=run_id,
            artifact_type=artifact_type,
            item_key=item_key,
            prompt_text="",  # Empty until generated
            status=PromptStatus.PENDING,
            depends_on_scene=depends_on_scene,
            created_by="system",
        )

    def mark_downstream_outdated(
        self,
        run_id: str,
        artifact_type: ArtifactType,
        changed_scene_key: str,
    ) -> int:
        """
        Mark all scenes after a changed scene as OUTDATED.

        When scene K changes, scenes K+1, K+2, etc. need to be regenerated
        to maintain continuity.

        Args:
            run_id: Run identifier
            artifact_type: Type of artifact
            changed_scene_key: The scene that changed (e.g., "scene_2")

        Returns:
            Number of prompts marked as outdated
        """
        # Extract scene number
        if not changed_scene_key.startswith("scene_"):
            return 0

        try:
            changed_scene_num = int(changed_scene_key.split("_")[1])
        except (IndexError, ValueError):
            return 0

        with sqlite3.connect(self.db_path) as conn:
            # Find all downstream scenes that are ACTIVE or LOCKED
            rows = conn.execute(
                """
                SELECT id, item_key FROM prompt_versions
                WHERE run_id = ? AND artifact_type = ?
                AND status IN (?, ?, ?)
                """,
                (
                    run_id,
                    artifact_type.value,
                    PromptStatus.ACTIVE.value,
                    PromptStatus.LOCKED.value,
                    PromptStatus.OUTDATED.value,
                ),
            ).fetchall()

            outdated_count = 0
            warning_msg = f"⚠ Continuity warning: Scene {changed_scene_num} was changed. Regenerate to match."

            for row_id, item_key in rows:
                if item_key.startswith("scene_"):
                    try:
                        scene_num = int(item_key.split("_")[1])
                        if scene_num > changed_scene_num:
                            conn.execute(
                                """
                                UPDATE prompt_versions
                                SET status = ?, continuity_warning = ?
                                WHERE id = ?
                                """,
                                (PromptStatus.OUTDATED.value, warning_msg, row_id),
                            )
                            outdated_count += 1
                    except (IndexError, ValueError):
                        pass

            return outdated_count

    def clear_continuity_warning(self, version_id: int) -> bool:
        """Clear the continuity warning for a prompt."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                UPDATE prompt_versions
                SET continuity_warning = NULL
                WHERE id = ?
                """,
                (version_id,),
            )
            return cursor.rowcount > 0

    def get_scene_generation_status(
        self,
        run_id: str,
        artifact_type: ArtifactType,
    ) -> list[dict]:
        """
        Get the generation status for all scenes in a run.

        Returns a list of scene info dicts with:
        - item_key: Scene key
        - status: Current status (PENDING, ACTIVE, LOCKED, OUTDATED)
        - prompt_id: ID of active/locked prompt (or None)
        - can_generate: Whether this scene can be generated
        - can_lock: Whether this scene can be locked
        - continuity_warning: Any warning message

        Args:
            run_id: Run identifier
            artifact_type: Type of artifact

        Returns:
            List of scene status dicts, ordered by scene number
        """
        with sqlite3.connect(self.db_path) as conn:
            # Get all prompts for this run/type
            rows = conn.execute(
                """
                SELECT id, item_key, status, continuity_warning, version
                FROM prompt_versions
                WHERE run_id = ? AND artifact_type = ?
                AND status NOT IN (?)
                ORDER BY item_key, version DESC
                """,
                (run_id, artifact_type.value, PromptStatus.SUPERSEDED.value),
            ).fetchall()

        # Group by item_key, keeping track of active/current prompt
        scenes = {}
        for row in rows:
            item_key = row[1]
            if item_key not in scenes:
                scenes[item_key] = {
                    "item_key": item_key,
                    "prompt_id": row[0],
                    "status": row[2],
                    "continuity_warning": row[3],
                    "version": row[4],
                }

        # Convert to sorted list by scene number
        result = []
        for item_key in sorted(scenes.keys(), key=lambda k: int(k.split("_")[1]) if k.startswith("scene_") else 0):
            scene = scenes[item_key]
            status = scene["status"]

            # Determine can_generate and can_lock
            scene_num = int(item_key.split("_")[1]) if item_key.startswith("scene_") else 0
            prev_scene_key = f"scene_{scene_num - 1}" if scene_num > 1 else None

            # Can generate if PENDING or OUTDATED
            can_generate = status in (PromptStatus.PENDING.value, PromptStatus.OUTDATED.value)

            # Can lock if ACTIVE
            can_lock = status == PromptStatus.ACTIVE.value

            # Check if previous scene is locked (required before generating this scene)
            prev_locked = True
            if prev_scene_key and prev_scene_key in scenes:
                prev_locked = scenes[prev_scene_key]["status"] == PromptStatus.LOCKED.value

            result.append({
                "item_key": item_key,
                "scene_number": scene_num,
                "prompt_id": scene["prompt_id"],
                "status": status,
                "continuity_warning": scene["continuity_warning"],
                "version": scene["version"],
                "can_generate": can_generate and prev_locked,
                "can_lock": can_lock,
                "prev_scene_locked": prev_locked,
            })

        return result

    def get_locked_prompt_for_scene(
        self,
        run_id: str,
        artifact_type: ArtifactType,
        item_key: str,
    ) -> PromptVersion | None:
        """
        Get the locked prompt for a specific scene.

        Args:
            run_id: Run identifier
            artifact_type: Type of artifact
            item_key: Scene key

        Returns:
            Locked PromptVersion or None
        """
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT * FROM prompt_versions
                WHERE run_id = ? AND artifact_type = ? AND item_key = ? AND status = ?
                ORDER BY version DESC
                LIMIT 1
                """,
                (run_id, artifact_type.value, item_key, PromptStatus.LOCKED.value),
            ).fetchone()

            if row:
                return self._row_to_prompt_version(row)
        return None

    def get_active_or_locked_prompt(
        self,
        run_id: str,
        artifact_type: ArtifactType,
        item_key: str,
    ) -> PromptVersion | None:
        """
        Get the active or locked prompt for a scene (locked takes precedence).

        Args:
            run_id: Run identifier
            artifact_type: Type of artifact
            item_key: Scene key

        Returns:
            PromptVersion (locked preferred, then active) or None
        """
        # First try to get locked
        locked = self.get_locked_prompt_for_scene(run_id, artifact_type, item_key)
        if locked:
            return locked

        # Then try active
        return self.get_active_prompt(run_id, artifact_type, item_key)

    # === Entity Methods ===

    def _row_to_entity(self, row: tuple) -> Entity:
        """Convert database row to Entity."""
        return Entity(
            id=row[0],
            run_id=row[1],
            name=row[2],
            entity_type=EntityType(row[3]),
            description=row[4],
            reference_image_path=row[5],
            created_from_scene_key=row[6],
            created_at=row[7],
            updated_at=row[8],
            is_active=bool(row[9]) if len(row) > 9 else True,
        )

    def _row_to_entity_link(self, row: tuple) -> EntityLink:
        """Convert database row to EntityLink."""
        return EntityLink(
            id=row[0],
            entity_id=row[1],
            run_id=row[2],
            scene_key=row[3],
            created_at=row[4],
        )

    def create_entity(
        self,
        run_id: str,
        name: str,
        entity_type: EntityType,
        description: str,
        reference_image_path: str | None = None,
        created_from_scene_key: str | None = None,
    ) -> Entity:
        """
        Create a new entity for continuity tracking.

        Args:
            run_id: Run identifier
            name: Entity name (e.g., "Young Woman", "Red Umbrella")
            entity_type: Type of entity (character, prop, location, style)
            description: Visual description for prompt injection
            reference_image_path: Optional path to reference image
            created_from_scene_key: Optional scene key that created this entity

        Returns:
            Created Entity
        """
        now = self._now()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO entities (
                    run_id, name, entity_type, description,
                    reference_image_path, created_from_scene_key,
                    created_at, updated_at, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    run_id,
                    name,
                    entity_type.value,
                    description,
                    reference_image_path,
                    created_from_scene_key,
                    now,
                    now,
                ),
            )

            return Entity(
                id=cursor.lastrowid,
                run_id=run_id,
                name=name,
                entity_type=entity_type,
                description=description,
                reference_image_path=reference_image_path,
                created_from_scene_key=created_from_scene_key,
                created_at=now,
                updated_at=now,
                is_active=True,
            )

    def get_entity(self, entity_id: int) -> Entity | None:
        """Get an entity by ID."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM entities WHERE id = ?",
                (entity_id,),
            ).fetchone()

            if row:
                return self._row_to_entity(row)
        return None

    def get_entities_for_run(
        self,
        run_id: str,
        entity_type: EntityType | None = None,
        active_only: bool = True,
    ) -> list[Entity]:
        """
        Get all entities for a run.

        Args:
            run_id: Run identifier
            entity_type: Optional filter by type
            active_only: If True, only return active entities

        Returns:
            List of Entity records
        """
        with sqlite3.connect(self.db_path) as conn:
            query = "SELECT * FROM entities WHERE run_id = ?"
            params: list[Any] = [run_id]

            if entity_type:
                query += " AND entity_type = ?"
                params.append(entity_type.value)

            if active_only:
                query += " AND is_active = 1"

            query += " ORDER BY created_at DESC"

            rows = conn.execute(query, params).fetchall()
            return [self._row_to_entity(row) for row in rows]

    def update_entity(
        self,
        entity_id: int,
        name: str | None = None,
        description: str | None = None,
        reference_image_path: str | None = None,
        is_active: bool | None = None,
    ) -> bool:
        """
        Update an entity.

        Args:
            entity_id: Entity ID
            name: New name (optional)
            description: New description (optional)
            reference_image_path: New image path (optional)
            is_active: New active status (optional)

        Returns:
            True if updated
        """
        fields = ["updated_at = ?"]
        values: list[Any] = [self._now()]

        if name is not None:
            fields.append("name = ?")
            values.append(name)

        if description is not None:
            fields.append("description = ?")
            values.append(description)

        if reference_image_path is not None:
            fields.append("reference_image_path = ?")
            values.append(reference_image_path)

        if is_active is not None:
            fields.append("is_active = ?")
            values.append(1 if is_active else 0)

        values.append(entity_id)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                f"UPDATE entities SET {', '.join(fields)} WHERE id = ?",
                values,
            )
            return cursor.rowcount > 0

    def delete_entity(self, entity_id: int) -> bool:
        """Soft delete an entity (sets is_active = 0)."""
        return self.update_entity(entity_id, is_active=False)

    def hard_delete_entity(self, entity_id: int) -> bool:
        """Permanently delete an entity and its links."""
        with sqlite3.connect(self.db_path) as conn:
            # Delete links first
            conn.execute(
                "DELETE FROM entity_links WHERE entity_id = ?",
                (entity_id,),
            )
            # Delete entity
            cursor = conn.execute(
                "DELETE FROM entities WHERE id = ?",
                (entity_id,),
            )
            return cursor.rowcount > 0

    def link_entity_to_scene(
        self,
        entity_id: int,
        run_id: str,
        scene_key: str,
    ) -> EntityLink:
        """
        Link an entity to a scene.

        Args:
            entity_id: Entity ID
            run_id: Run identifier
            scene_key: Scene key (e.g., "scene_1_HOOK")

        Returns:
            Created EntityLink
        """
        now = self._now()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO entity_links (entity_id, run_id, scene_key, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (entity_id, run_id, scene_key, now),
            )

            return EntityLink(
                id=cursor.lastrowid,
                entity_id=entity_id,
                run_id=run_id,
                scene_key=scene_key,
                created_at=now,
            )

    def get_entities_for_scene(
        self,
        run_id: str,
        scene_key: str,
    ) -> list[Entity]:
        """Get all entities linked to a specific scene."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT e.* FROM entities e
                INNER JOIN entity_links el ON e.id = el.entity_id
                WHERE el.run_id = ? AND el.scene_key = ? AND e.is_active = 1
                ORDER BY e.entity_type, e.name
                """,
                (run_id, scene_key),
            ).fetchall()

            return [self._row_to_entity(row) for row in rows]

    def get_scenes_for_entity(self, entity_id: int) -> list[str]:
        """Get all scene keys linked to an entity."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT scene_key FROM entity_links
                WHERE entity_id = ?
                ORDER BY scene_key
                """,
                (entity_id,),
            ).fetchall()

            return [row[0] for row in rows]

    def unlink_entity_from_scene(
        self,
        entity_id: int,
        run_id: str,
        scene_key: str,
    ) -> bool:
        """Remove entity link from a scene."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                DELETE FROM entity_links
                WHERE entity_id = ? AND run_id = ? AND scene_key = ?
                """,
                (entity_id, run_id, scene_key),
            )
            return cursor.rowcount > 0

    def get_entity_context_for_scene(
        self,
        run_id: str,
        scene_key: str,
    ) -> str:
        """
        Get formatted entity context block for prompt injection.

        Returns a formatted string with all entities linked to this scene,
        suitable for injection into AI prompts.
        """
        entities = self.get_entities_for_scene(run_id, scene_key)

        if not entities:
            return ""

        context_parts = ["[CONTINUITY ELEMENTS]"]

        for entity in entities:
            context_parts.append(entity.to_prompt_context())

        context_parts.append("[END CONTINUITY]")

        return "\n".join(context_parts)

    def export_entities_for_run(self, run_id: str, output_path: Path) -> bool:
        """
        Export entities to JSON and Markdown files in output folder.

        Args:
            run_id: Run identifier
            output_path: Output directory path

        Returns:
            True if exported successfully
        """
        entities = self.get_entities_for_run(run_id, active_only=True)

        if not entities:
            return False

        try:
            output_dir = Path(output_path)
            output_dir.mkdir(parents=True, exist_ok=True)

            # Export JSON
            json_path = output_dir / "entities.json"
            with open(json_path, "w") as f:
                import json
                data = {
                    "run_id": run_id,
                    "entities": [e.to_dict() for e in entities],
                    "links": [],
                }
                # Add links for each entity
                for entity in entities:
                    scenes = self.get_scenes_for_entity(entity.id)
                    data["links"].extend([
                        {"entity_id": entity.id, "entity_name": entity.name, "scene_key": s}
                        for s in scenes
                    ])
                json.dump(data, f, indent=2)

            # Export Markdown
            md_path = output_dir / "entities.md"
            with open(md_path, "w") as f:
                f.write("# Continuity Entities\n\n")
                f.write(f"Run: `{run_id}`\n\n")

                for etype in EntityType:
                    type_entities = [e for e in entities if e.entity_type == etype]
                    if type_entities:
                        f.write(f"## {etype.value.title()}s\n\n")
                        for entity in type_entities:
                            f.write(f"### {entity.name}\n\n")
                            f.write(f"{entity.description}\n\n")
                            scenes = self.get_scenes_for_entity(entity.id)
                            if scenes:
                                f.write(f"**Used in:** {', '.join(scenes)}\n\n")
                            if entity.reference_image_path:
                                f.write(f"**Reference:** `{entity.reference_image_path}`\n\n")

            return True
        except Exception:
            return False
