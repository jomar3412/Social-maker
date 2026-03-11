"""
RunConfig: Configuration for a pipeline run.
"""

from dataclasses import dataclass, field
from datetime import datetime
import json
import uuid


@dataclass
class RunConfig:
    """Configuration for a content generation run."""

    # Identifiers
    run_id: str = field(default_factory=lambda: f"run-{uuid.uuid4().hex[:8]}")
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    # Presets
    niche: str = "motivation"
    style: str = "affirming"
    voice_preset: str = "deep_motivational"
    visual_mode: str = "hybrid"
    realism_mode: str = "standard"
    visual_engine: str = "nanobanana"  # nanobanana, cdream, custom

    # Budget
    budget_mode: bool = False
    max_calls: int = 10
    max_regens: int = 2

    # Features
    generate_shot_list: bool = True
    align_audio: bool = False
    align_duration: bool = False
    dry_run: bool = False

    # Script generation options
    loop_friendly_ending: bool = False  # Enable ending that flows back to hook

    # Optional overrides
    topic: str | None = None
    custom_hook: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "niche": self.niche,
            "style": self.style,
            "voice_preset": self.voice_preset,
            "visual_mode": self.visual_mode,
            "visual_engine": self.visual_engine,
            "realism_mode": self.realism_mode,
            "budget_mode": self.budget_mode,
            "max_calls": self.max_calls,
            "max_regens": self.max_regens,
            "generate_shot_list": self.generate_shot_list,
            "align_audio": self.align_audio,
            "align_duration": self.align_duration,
            "dry_run": self.dry_run,
            "loop_friendly_ending": self.loop_friendly_ending,
            "topic": self.topic,
            "custom_hook": self.custom_hook,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> "RunConfig":
        """Create from dictionary."""
        return cls(
            run_id=data.get("run_id", f"run-{uuid.uuid4().hex[:8]}"),
            timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
            niche=data.get("niche", "motivation"),
            style=data.get("style", "affirming"),
            voice_preset=data.get("voice_preset", "deep_motivational"),
            visual_mode=data.get("visual_mode", "hybrid"),
            visual_engine=data.get("visual_engine", "nanobanana"),
            realism_mode=data.get("realism_mode", "standard"),
            budget_mode=data.get("budget_mode", False),
            max_calls=data.get("max_calls", 10),
            max_regens=data.get("max_regens", 2),
            generate_shot_list=data.get("generate_shot_list", True),
            align_audio=data.get("align_audio", False),
            align_duration=data.get("align_duration", False),
            dry_run=data.get("dry_run", False),
            loop_friendly_ending=data.get("loop_friendly_ending", False),
            topic=data.get("topic"),
            custom_hook=data.get("custom_hook"),
        )

    @classmethod
    def from_cli(cls, args) -> "RunConfig":
        """Create from CLI arguments namespace."""
        return cls(
            niche=getattr(args, "niche", "motivation"),
            style=getattr(args, "style", "affirming"),
            voice_preset=getattr(args, "voice", "deep_motivational"),
            visual_mode=getattr(args, "visual", "hybrid"),
            realism_mode=getattr(args, "realism", "standard"),
            budget_mode=getattr(args, "budget_mode", False),
            max_calls=getattr(args, "max_calls", 10),
            generate_shot_list=getattr(args, "shot_list", True),
            align_audio=getattr(args, "align_audio", False),
            align_duration=getattr(args, "align_duration", False),
            dry_run=getattr(args, "dry_run", False),
            loop_friendly_ending=getattr(args, "loop_friendly", False),
            topic=getattr(args, "topic", None),
        )
