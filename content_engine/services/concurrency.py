"""
Concurrency management for pipeline runs.

Provides thread-safe tracking of active runs and enforces limits.
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum


class ConcurrencyError(Exception):
    """Raised when concurrency limits are exceeded."""
    pass


class RunLimitExceeded(ConcurrencyError):
    """Raised when max concurrent runs limit is exceeded."""
    pass


class RegenerationLimitExceeded(ConcurrencyError):
    """Raised when max regenerations per run is exceeded."""
    pass


@dataclass
class ActiveRun:
    """Tracks an active run."""
    run_id: str
    started_at: datetime
    stage: str
    regeneration_count: int = 0


@dataclass
class ConcurrencyConfig:
    """Configuration for concurrency limits."""
    max_active_runs: int = 2
    max_regenerations_per_run: int = 3

    @classmethod
    def from_config(cls, config: dict) -> "ConcurrencyConfig":
        """Create from config.yaml settings."""
        return cls(
            max_active_runs=config.get("max_active_runs", 2),
            max_regenerations_per_run=config.get("max_regenerations_per_run", 3),
        )


class ConcurrencyManager:
    """
    Thread-safe manager for concurrent pipeline runs.

    Enforces limits:
    - Max concurrent active runs (default: 2)
    - Max regenerations per run (default: 3)

    Usage:
        manager = ConcurrencyManager()

        # Try to start a run
        if manager.can_start_run():
            manager.start_run("run-001")
            try:
                # ... do work ...
            finally:
                manager.complete_run("run-001")

        # Track regenerations
        if manager.can_regenerate("run-001"):
            manager.increment_regeneration("run-001")
            # ... regenerate ...
    """

    def __init__(self, config: Optional[ConcurrencyConfig] = None):
        self.config = config or ConcurrencyConfig()
        self._lock = threading.RLock()
        self._active_runs: dict[str, ActiveRun] = {}
        self._regeneration_counts: dict[str, int] = {}

    def can_start_run(self) -> bool:
        """Check if a new run can be started."""
        with self._lock:
            return len(self._active_runs) < self.config.max_active_runs

    def start_run(self, run_id: str, stage: str = "init") -> bool:
        """
        Register a new active run.

        Args:
            run_id: Unique run identifier
            stage: Initial stage name

        Returns:
            True if started, False if limit exceeded

        Raises:
            RunLimitExceeded: If max concurrent runs exceeded
        """
        with self._lock:
            if len(self._active_runs) >= self.config.max_active_runs:
                raise RunLimitExceeded(
                    f"Max concurrent runs ({self.config.max_active_runs}) exceeded. "
                    f"Active runs: {list(self._active_runs.keys())}"
                )

            self._active_runs[run_id] = ActiveRun(
                run_id=run_id,
                started_at=datetime.now(),
                stage=stage,
                regeneration_count=self._regeneration_counts.get(run_id, 0),
            )
            return True

    def update_stage(self, run_id: str, stage: str):
        """Update the stage of an active run."""
        with self._lock:
            if run_id in self._active_runs:
                self._active_runs[run_id].stage = stage

    def complete_run(self, run_id: str):
        """Mark a run as complete (remove from active)."""
        with self._lock:
            self._active_runs.pop(run_id, None)

    def fail_run(self, run_id: str):
        """Mark a run as failed (remove from active)."""
        with self._lock:
            self._active_runs.pop(run_id, None)

    def can_regenerate(self, run_id: str) -> bool:
        """Check if a run can be regenerated."""
        with self._lock:
            count = self._regeneration_counts.get(run_id, 0)
            return count < self.config.max_regenerations_per_run

    def increment_regeneration(self, run_id: str) -> int:
        """
        Increment regeneration count for a run.

        Returns:
            New regeneration count

        Raises:
            RegenerationLimitExceeded: If max regenerations exceeded
        """
        with self._lock:
            count = self._regeneration_counts.get(run_id, 0)
            if count >= self.config.max_regenerations_per_run:
                raise RegenerationLimitExceeded(
                    f"Max regenerations ({self.config.max_regenerations_per_run}) "
                    f"exceeded for run {run_id}"
                )

            new_count = count + 1
            self._regeneration_counts[run_id] = new_count

            # Update active run if present
            if run_id in self._active_runs:
                self._active_runs[run_id].regeneration_count = new_count

            return new_count

    def get_regeneration_count(self, run_id: str) -> int:
        """Get current regeneration count for a run."""
        with self._lock:
            return self._regeneration_counts.get(run_id, 0)

    def get_remaining_regenerations(self, run_id: str) -> int:
        """Get remaining regenerations for a run."""
        with self._lock:
            count = self._regeneration_counts.get(run_id, 0)
            return max(0, self.config.max_regenerations_per_run - count)

    def get_active_runs(self) -> list[ActiveRun]:
        """Get list of currently active runs."""
        with self._lock:
            return list(self._active_runs.values())

    def get_active_run_ids(self) -> list[str]:
        """Get IDs of currently active runs."""
        with self._lock:
            return list(self._active_runs.keys())

    def get_active_count(self) -> int:
        """Get count of active runs."""
        with self._lock:
            return len(self._active_runs)

    def get_available_slots(self) -> int:
        """Get number of available run slots."""
        with self._lock:
            return max(0, self.config.max_active_runs - len(self._active_runs))

    def is_run_active(self, run_id: str) -> bool:
        """Check if a specific run is currently active."""
        with self._lock:
            return run_id in self._active_runs

    def reset_regeneration_count(self, run_id: str):
        """Reset regeneration count for a run (e.g., after approval)."""
        with self._lock:
            self._regeneration_counts.pop(run_id, None)
            if run_id in self._active_runs:
                self._active_runs[run_id].regeneration_count = 0

    def cleanup_stale_runs(self, max_age_seconds: int = 3600):
        """
        Remove runs that have been active too long (likely stuck).

        Args:
            max_age_seconds: Max age in seconds before considering stale
        """
        with self._lock:
            now = datetime.now()
            stale = []
            for run_id, run in self._active_runs.items():
                age = (now - run.started_at).total_seconds()
                if age > max_age_seconds:
                    stale.append(run_id)

            for run_id in stale:
                self._active_runs.pop(run_id, None)

            return stale

    def get_status(self) -> dict:
        """Get current concurrency status."""
        with self._lock:
            return {
                "active_runs": len(self._active_runs),
                "max_runs": self.config.max_active_runs,
                "available_slots": self.get_available_slots(),
                "active_run_ids": list(self._active_runs.keys()),
                "regeneration_counts": dict(self._regeneration_counts),
            }


# Global singleton instance
_manager: Optional[ConcurrencyManager] = None
_manager_lock = threading.Lock()


def get_concurrency_manager(config: Optional[dict] = None) -> ConcurrencyManager:
    """
    Get the global concurrency manager singleton.

    Args:
        config: Optional config dict to initialize with (only used on first call)

    Returns:
        ConcurrencyManager singleton instance
    """
    global _manager

    if _manager is None:
        with _manager_lock:
            if _manager is None:
                if config:
                    cc = ConcurrencyConfig.from_config(config)
                else:
                    cc = ConcurrencyConfig()
                _manager = ConcurrencyManager(cc)

    return _manager


def reset_concurrency_manager():
    """Reset the global manager (for testing)."""
    global _manager
    with _manager_lock:
        _manager = None
