"""
StorageManager: Global storage policy management for content_engine.

Handles:
- Configurable max storage limit (GB)
- Auto-deletion of oldest COMPLETED runs when storage exceeds limit
- Protection of in-progress and unpublished runs
- Selective deletion (keep metadata/logs, remove heavy assets)
- Toggle options for rejected images and intermediate videos
"""

import os
import shutil
import json
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum

from content_engine.services.run_store import RunStore, RunStage, WorkflowStage


class DeletionPolicy(Enum):
    """What to delete when cleaning up a run."""
    FULL = "full"          # Delete entire run directory
    ASSETS_ONLY = "assets_only"  # Keep metadata/logs, delete heavy assets


@dataclass
class StorageConfig:
    """Storage policy configuration."""
    # Max storage in GB (0 = unlimited)
    max_storage_gb: float = 50.0

    # When to trigger cleanup (percentage of max)
    cleanup_threshold_pct: float = 90.0

    # Target storage after cleanup (percentage of max)
    cleanup_target_pct: float = 70.0

    # What to delete
    deletion_policy: DeletionPolicy = DeletionPolicy.ASSETS_ONLY

    # Toggle options
    delete_rejected_images: bool = True
    delete_intermediate_videos: bool = True

    # File patterns for heavy assets
    heavy_asset_patterns: list[str] = field(default_factory=lambda: [
        "*.mp4", "*.mov", "*.avi", "*.webm",  # Videos
        "*.mp3", "*.wav", "*.m4a",            # Audio
        "*.png", "*.jpg", "*.jpeg", "*.webp", # Images
    ])

    # Patterns to always keep
    keep_patterns: list[str] = field(default_factory=lambda: [
        "*.json", "*.yaml", "*.yml",  # Config/metadata
        "*.txt", "*.md", "*.log",     # Logs and text
        "*.ass", "*.srt",             # Subtitles
    ])

    # Rejected image patterns (for toggle)
    rejected_image_patterns: list[str] = field(default_factory=lambda: [
        "*_rejected_*", "*_v[0-9]*",  # Versioned/rejected images
    ])

    # Intermediate video patterns (for toggle)
    intermediate_video_patterns: list[str] = field(default_factory=lambda: [
        "*_temp_*", "*_intermediate_*", "*_draft_*",
    ])

    @classmethod
    def from_dict(cls, data: dict) -> "StorageConfig":
        """Create from dictionary."""
        policy_str = data.get("deletion_policy", "assets_only")
        deletion_policy = DeletionPolicy(policy_str) if policy_str else DeletionPolicy.ASSETS_ONLY

        return cls(
            max_storage_gb=data.get("max_storage_gb", 50.0),
            cleanup_threshold_pct=data.get("cleanup_threshold_pct", 90.0),
            cleanup_target_pct=data.get("cleanup_target_pct", 70.0),
            deletion_policy=deletion_policy,
            delete_rejected_images=data.get("delete_rejected_images", True),
            delete_intermediate_videos=data.get("delete_intermediate_videos", True),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "max_storage_gb": self.max_storage_gb,
            "cleanup_threshold_pct": self.cleanup_threshold_pct,
            "cleanup_target_pct": self.cleanup_target_pct,
            "deletion_policy": self.deletion_policy.value,
            "delete_rejected_images": self.delete_rejected_images,
            "delete_intermediate_videos": self.delete_intermediate_videos,
        }


@dataclass
class StorageStats:
    """Current storage statistics."""
    total_bytes: int = 0
    used_bytes: int = 0
    free_bytes: int = 0
    run_count: int = 0
    deletable_run_count: int = 0
    protected_run_count: int = 0

    @property
    def used_gb(self) -> float:
        return self.used_bytes / (1024 ** 3)

    @property
    def total_gb(self) -> float:
        return self.total_bytes / (1024 ** 3)

    @property
    def free_gb(self) -> float:
        return self.free_bytes / (1024 ** 3)

    @property
    def used_pct(self) -> float:
        if self.total_bytes == 0:
            return 0.0
        return (self.used_bytes / self.total_bytes) * 100

    def to_dict(self) -> dict:
        return {
            "total_bytes": self.total_bytes,
            "used_bytes": self.used_bytes,
            "free_bytes": self.free_bytes,
            "used_gb": round(self.used_gb, 2),
            "total_gb": round(self.total_gb, 2),
            "free_gb": round(self.free_gb, 2),
            "used_pct": round(self.used_pct, 1),
            "run_count": self.run_count,
            "deletable_run_count": self.deletable_run_count,
            "protected_run_count": self.protected_run_count,
        }


@dataclass
class CleanupResult:
    """Result of a cleanup operation."""
    success: bool
    runs_deleted: int = 0
    bytes_freed: int = 0
    errors: list[str] = field(default_factory=list)
    deleted_run_ids: list[str] = field(default_factory=list)

    @property
    def gb_freed(self) -> float:
        return self.bytes_freed / (1024 ** 3)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "runs_deleted": self.runs_deleted,
            "bytes_freed": self.bytes_freed,
            "gb_freed": round(self.gb_freed, 2),
            "errors": self.errors,
            "deleted_run_ids": self.deleted_run_ids,
        }


class StorageManager:
    """
    Manages storage for content_engine output.

    Automatically cleans up old completed runs when storage exceeds limits.
    Protects in-progress and unpublished runs from deletion.
    """

    # Default storage root
    DEFAULT_STORAGE_ROOT = Path("/home/markhuerta/gdrive_mount/content_engine")

    # Config file name
    CONFIG_FILE = "storage_config.json"

    def __init__(
        self,
        storage_root: Optional[Path] = None,
        config: Optional[StorageConfig] = None,
        run_store: Optional[RunStore] = None,
    ):
        """
        Initialize storage manager.

        Args:
            storage_root: Root directory for content storage
            config: Storage configuration (loads from file if not provided)
            run_store: RunStore instance for checking run status
        """
        self.storage_root = storage_root or self.DEFAULT_STORAGE_ROOT
        self.run_store = run_store or RunStore()

        # Load or use provided config
        if config:
            self.config = config
        else:
            self.config = self._load_config()

    def _load_config(self) -> StorageConfig:
        """Load config from file or return defaults."""
        config_path = self.storage_root / self.CONFIG_FILE
        if config_path.exists():
            try:
                with open(config_path) as f:
                    data = json.load(f)
                return StorageConfig.from_dict(data)
            except Exception:
                pass
        return StorageConfig()

    def save_config(self) -> bool:
        """Save current config to file."""
        try:
            self.storage_root.mkdir(parents=True, exist_ok=True)
            config_path = self.storage_root / self.CONFIG_FILE
            with open(config_path, 'w') as f:
                json.dump(self.config.to_dict(), f, indent=2)
            return True
        except Exception:
            return False

    def update_config(self, **kwargs) -> StorageConfig:
        """Update config with provided values."""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                if key == "deletion_policy" and isinstance(value, str):
                    value = DeletionPolicy(value)
                setattr(self.config, key, value)
        self.save_config()
        return self.config

    def get_storage_stats(self) -> StorageStats:
        """Get current storage statistics."""
        stats = StorageStats()

        if not self.storage_root.exists():
            return stats

        # Get disk usage for storage root
        try:
            usage = shutil.disk_usage(self.storage_root)
            stats.total_bytes = usage.total
            stats.free_bytes = usage.free
        except Exception:
            pass

        # Calculate used space by content_engine
        stats.used_bytes = self._get_directory_size(self.storage_root)

        # Count runs
        deletable, protected = self._categorize_runs()
        stats.deletable_run_count = len(deletable)
        stats.protected_run_count = len(protected)
        stats.run_count = stats.deletable_run_count + stats.protected_run_count

        return stats

    def _get_directory_size(self, path: Path) -> int:
        """Calculate total size of a directory in bytes."""
        total = 0
        try:
            for entry in path.rglob("*"):
                if entry.is_file():
                    try:
                        total += entry.stat().st_size
                    except (OSError, PermissionError):
                        pass
        except Exception:
            pass
        return total

    def _get_run_size(self, run_path: Path) -> int:
        """Get size of a run directory."""
        return self._get_directory_size(run_path)

    def _categorize_runs(self) -> tuple[list[dict], list[dict]]:
        """
        Categorize runs into deletable and protected.

        Returns:
            (deletable_runs, protected_runs) - each is list of {run_id, path, size, date}
        """
        deletable = []
        protected = []

        if not self.storage_root.exists():
            return deletable, protected

        # Scan all run directories
        for niche_dir in self.storage_root.iterdir():
            if not niche_dir.is_dir() or niche_dir.name.startswith('.'):
                continue

            for style_dir in niche_dir.iterdir():
                if not style_dir.is_dir():
                    continue

                for date_dir in style_dir.iterdir():
                    if not date_dir.is_dir():
                        continue

                    for run_dir in date_dir.iterdir():
                        if not run_dir.is_dir() or not run_dir.name.startswith("run-"):
                            continue

                        run_id = run_dir.name
                        run_info = {
                            "run_id": run_id,
                            "path": run_dir,
                            "size": self._get_run_size(run_dir),
                            "mtime": run_dir.stat().st_mtime,
                        }

                        if self._is_deletable(run_id):
                            deletable.append(run_info)
                        else:
                            protected.append(run_info)

        # Sort deletable by mtime (oldest first)
        deletable.sort(key=lambda x: x["mtime"])

        return deletable, protected

    def _is_deletable(self, run_id: str) -> bool:
        """
        Check if a run can be deleted.

        A run is deletable if:
        1. It is COMPLETE (not in-progress)
        2. It has been POSTED (published)
        """
        try:
            record = self.run_store.get_run(run_id)
            if not record:
                # No record = orphan directory, can delete
                return True

            # Check if in-progress
            if record.stage.is_running():
                return False

            # Check if unpublished
            if not record.is_posted:
                return False

            # Must be complete AND posted
            return record.stage == RunStage.COMPLETE and record.posted_at is not None

        except Exception:
            # If we can't check, assume protected
            return False

    def needs_cleanup(self) -> bool:
        """Check if storage cleanup is needed."""
        if self.config.max_storage_gb <= 0:
            return False

        stats = self.get_storage_stats()
        max_bytes = self.config.max_storage_gb * (1024 ** 3)
        threshold_bytes = max_bytes * (self.config.cleanup_threshold_pct / 100)

        return stats.used_bytes >= threshold_bytes

    def run_cleanup(self, force: bool = False) -> CleanupResult:
        """
        Run storage cleanup.

        Args:
            force: If True, run even if not above threshold

        Returns:
            CleanupResult with details of what was deleted
        """
        result = CleanupResult(success=True)

        if not force and not self.needs_cleanup():
            return result

        # Calculate target
        max_bytes = self.config.max_storage_gb * (1024 ** 3)
        target_bytes = max_bytes * (self.config.cleanup_target_pct / 100)

        stats = self.get_storage_stats()
        bytes_to_free = stats.used_bytes - target_bytes

        if bytes_to_free <= 0:
            return result

        # Get deletable runs (sorted oldest first)
        deletable, _ = self._categorize_runs()

        if not deletable:
            result.errors.append("No deletable runs found")
            return result

        # Delete oldest runs until we reach target
        bytes_freed = 0
        for run_info in deletable:
            if bytes_freed >= bytes_to_free:
                break

            try:
                freed = self._delete_run(run_info["path"], run_info["run_id"])
                bytes_freed += freed
                result.bytes_freed += freed
                result.runs_deleted += 1
                result.deleted_run_ids.append(run_info["run_id"])
            except Exception as e:
                result.errors.append(f"Failed to delete {run_info['run_id']}: {e}")

        return result

    def _delete_run(self, run_path: Path, run_id: str) -> int:
        """
        Delete a run according to the deletion policy.

        Returns bytes freed.
        """
        if not run_path.exists():
            return 0

        bytes_freed = 0

        if self.config.deletion_policy == DeletionPolicy.FULL:
            # Delete entire directory
            bytes_freed = self._get_run_size(run_path)
            shutil.rmtree(run_path)
        else:
            # Delete only heavy assets, keep metadata/logs
            bytes_freed = self._delete_heavy_assets(run_path)

        return bytes_freed

    def _delete_heavy_assets(self, run_path: Path) -> int:
        """Delete heavy assets from a run directory, keeping metadata."""
        bytes_freed = 0

        for pattern in self.config.heavy_asset_patterns:
            for file in run_path.rglob(pattern):
                # Check if it matches a keep pattern
                should_keep = False
                for keep_pattern in self.config.keep_patterns:
                    if file.match(keep_pattern):
                        should_keep = True
                        break

                if not should_keep:
                    try:
                        size = file.stat().st_size
                        file.unlink()
                        bytes_freed += size
                    except Exception:
                        pass

        return bytes_freed

    def cleanup_rejected_images(self) -> int:
        """Delete rejected image iterations across all runs."""
        if not self.config.delete_rejected_images:
            return 0

        bytes_freed = 0
        for pattern in self.config.rejected_image_patterns:
            for file in self.storage_root.rglob(pattern):
                if file.suffix.lower() in ['.png', '.jpg', '.jpeg', '.webp']:
                    try:
                        size = file.stat().st_size
                        file.unlink()
                        bytes_freed += size
                    except Exception:
                        pass
        return bytes_freed

    def cleanup_intermediate_videos(self, run_path: Optional[Path] = None) -> int:
        """Delete intermediate video files (after publish)."""
        if not self.config.delete_intermediate_videos:
            return 0

        search_path = run_path or self.storage_root
        bytes_freed = 0

        for pattern in self.config.intermediate_video_patterns:
            for file in search_path.rglob(pattern):
                if file.suffix.lower() in ['.mp4', '.mov', '.avi', '.webm']:
                    try:
                        size = file.stat().st_size
                        file.unlink()
                        bytes_freed += size
                    except Exception:
                        pass
        return bytes_freed

    def get_run_storage_info(self, run_id: str) -> Optional[dict]:
        """Get storage info for a specific run."""
        deletable, protected = self._categorize_runs()

        for run_info in deletable + protected:
            if run_info["run_id"] == run_id:
                return {
                    "run_id": run_id,
                    "path": str(run_info["path"]),
                    "size_bytes": run_info["size"],
                    "size_mb": round(run_info["size"] / (1024 ** 2), 2),
                    "deletable": run_info in deletable,
                    "mtime": datetime.fromtimestamp(run_info["mtime"]).isoformat(),
                }
        return None


# Singleton instance
_storage_manager: Optional[StorageManager] = None


def get_storage_manager(
    storage_root: Optional[Path] = None,
    config: Optional[StorageConfig] = None,
) -> StorageManager:
    """Get or create the storage manager singleton."""
    global _storage_manager

    if _storage_manager is None or storage_root is not None or config is not None:
        _storage_manager = StorageManager(storage_root=storage_root, config=config)

    return _storage_manager
