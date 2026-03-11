"""
DriveGuard: Google Drive mount detection and validation.

Ensures G Drive is mounted and writable BEFORE any expensive operations.
Uses priority-based detection: /proc/mounts > os.path.ismount > marker file.
"""

from pathlib import Path
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import subprocess
import os
import yaml


class DriveStatus(Enum):
    """Status of the Google Drive mount."""
    MOUNTED = "mounted"
    NOT_MOUNTED = "not_mounted"
    READ_ONLY = "read_only"
    UNREACHABLE = "unreachable"


@dataclass
class DriveCheckResult:
    """Result of a drive availability check."""
    status: DriveStatus
    mount_path: Path | None
    can_write: bool
    error_message: str | None
    attempted_remount: bool
    mount_command: str | None  # Exact command for UI/CLI display
    stderr_output: str | None  # Error details for debugging
    detection_method: str | None  # How mount was detected


class DriveNotAvailableError(Exception):
    """Raised when G Drive is not available."""

    def __init__(self, result: DriveCheckResult):
        self.result = result
        msg = f"G Drive not available: {result.error_message}"
        if result.mount_command:
            msg += f"\n\nRun: {result.mount_command}"
        if result.stderr_output:
            msg += f"\n\nDetails:\n{result.stderr_output}"
        super().__init__(msg)


class DriveGuard:
    """
    Detects and validates Google Drive mount.

    Priority-based detection:
    1. /proc/mounts (most reliable on Linux)
    2. os.path.ismount (cross-platform)
    3. Marker file check (.content_engine_marker)
    """

    MARKER_FILENAME = ".content_engine_marker"

    def __init__(self, config_path: Path | None = None):
        """
        Initialize DriveGuard.

        Args:
            config_path: Path to config.yaml. If None, looks in parent directory.
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config.yaml"

        self.config = self._load_config(config_path)
        gdrive_config = self.config.get("gdrive", {})

        self.mount_name = gdrive_config.get("mount_name", "G Drive")
        self.mount_path = Path(
            os.path.expanduser(gdrive_config.get("mount_path", "~/gdrive_mount"))
        )
        self.output_root = gdrive_config.get("output_root", "content_engine")
        self.rclone_remote = gdrive_config.get("rclone_remote", "gdrive:Social_Maker")
        self.attempt_auto_remount = gdrive_config.get("attempt_auto_remount", True)
        self.mount_command_template = gdrive_config.get(
            "mount_command",
            "rclone mount {remote} {path} --daemon --vfs-cache-mode writes"
        )
        self.unmount_command_template = gdrive_config.get(
            "unmount_command",
            "fusermount -uz {path}"
        )

    def _load_config(self, config_path: Path) -> dict:
        """Load configuration from YAML file."""
        if not config_path.exists():
            return {}
        with open(config_path) as f:
            return yaml.safe_load(f) or {}

    def _get_mount_command(self) -> str:
        """Return the exact mount command for display."""
        return self.mount_command_template.format(
            remote=self.rclone_remote,
            path=str(self.mount_path)
        )

    def check(self) -> DriveCheckResult:
        """
        Check if G Drive is available and writable.

        Returns:
            DriveCheckResult with status and details.
        """
        mount_cmd = self._get_mount_command()

        # Step 1: Check if mount point directory exists
        if not self.mount_path.exists():
            return DriveCheckResult(
                status=DriveStatus.NOT_MOUNTED,
                mount_path=None,
                can_write=False,
                error_message=f"Mount path {self.mount_path} does not exist",
                attempted_remount=False,
                mount_command=mount_cmd,
                stderr_output=None,
                detection_method=None
            )

        # Step 2: Check if mounted using priority-based detection
        is_mounted, detection_method = self._is_mounted()
        if not is_mounted:
            if self.attempt_auto_remount:
                return self._try_remount()
            return DriveCheckResult(
                status=DriveStatus.NOT_MOUNTED,
                mount_path=self.mount_path,
                can_write=False,
                error_message=f"Directory exists but drive not mounted (checked: {detection_method})",
                attempted_remount=False,
                mount_command=mount_cmd,
                stderr_output=None,
                detection_method=detection_method
            )

        # Step 3: Check write permissions
        can_write, write_error = self._test_write()
        if not can_write:
            return DriveCheckResult(
                status=DriveStatus.READ_ONLY,
                mount_path=self.mount_path,
                can_write=False,
                error_message=f"Drive mounted but not writable: {write_error}",
                attempted_remount=False,
                mount_command=None,
                stderr_output=write_error,
                detection_method=detection_method
            )

        # Step 4: Ensure marker file exists
        self.ensure_marker()

        return DriveCheckResult(
            status=DriveStatus.MOUNTED,
            mount_path=self.mount_path,
            can_write=True,
            error_message=None,
            attempted_remount=False,
            mount_command=None,
            stderr_output=None,
            detection_method=detection_method
        )

    def _is_mounted(self) -> tuple[bool, str]:
        """
        Check if path is a mount point.

        Returns:
            (is_mounted, detection_method_used)

        Priority:
        1. /proc/mounts (most reliable on Linux)
        2. os.path.ismount (cross-platform)
        3. Marker file check (fallback)
        """
        path_str = str(self.mount_path.resolve())

        # Priority 1: /proc/mounts (Linux-specific, most reliable)
        try:
            with open("/proc/mounts") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2 and parts[1] == path_str:
                        return True, "/proc/mounts"
        except (FileNotFoundError, PermissionError):
            pass

        # Priority 2: os.path.ismount (cross-platform)
        try:
            if os.path.ismount(path_str):
                return True, "os.path.ismount"
        except Exception:
            pass

        # Priority 3: Marker file check (more reliable than directory content)
        marker_file = self.mount_path / self.MARKER_FILENAME
        try:
            if marker_file.exists():
                return True, "marker_file"
        except Exception:
            pass

        return False, "all_methods_failed"

    def _test_write(self) -> tuple[bool, str | None]:
        """
        Test write by creating and deleting a temp file.

        Returns:
            (can_write, error_message)
        """
        test_file = self.mount_path / ".write_test"
        try:
            test_file.write_text("test")
            test_file.unlink()
            return True, None
        except Exception as e:
            return False, str(e)

    def ensure_marker(self) -> bool:
        """
        Create marker file if missing.

        Call after successful mount verification.

        Returns:
            True if marker exists or was created successfully.
        """
        marker_file = self.mount_path / self.MARKER_FILENAME
        try:
            if not marker_file.exists():
                marker_file.write_text(
                    f"Content Engine marker\nCreated: {datetime.now().isoformat()}\n"
                )
            return True
        except Exception:
            return False

    def _try_remount(self) -> DriveCheckResult:
        """Attempt to remount using configured commands."""
        mount_cmd = self._get_mount_command()
        unmount_cmd = self.unmount_command_template.format(path=str(self.mount_path))
        stderr_output = []

        try:
            # Kill any existing mount
            result = subprocess.run(
                unmount_cmd.split(),
                capture_output=True,
                timeout=5,
                text=True
            )
            if result.stderr:
                stderr_output.append(f"unmount: {result.stderr.strip()}")

            # Remount using configured command
            result = subprocess.run(
                mount_cmd.split(),
                capture_output=True,
                timeout=15,
                text=True
            )
            if result.stderr:
                stderr_output.append(f"mount: {result.stderr.strip()}")
            if result.returncode != 0:
                stderr_output.append(f"mount exit code: {result.returncode}")

            # Wait and verify
            import time
            time.sleep(2)

            is_mounted, detection = self._is_mounted()
            can_write, write_err = self._test_write()

            if is_mounted and can_write:
                self.ensure_marker()
                return DriveCheckResult(
                    status=DriveStatus.MOUNTED,
                    mount_path=self.mount_path,
                    can_write=True,
                    error_message=None,
                    attempted_remount=True,
                    mount_command=None,
                    stderr_output=None,
                    detection_method=detection
                )

            stderr_output.append(
                f"Post-mount check failed: mounted={is_mounted}, writable={can_write}"
            )
            if write_err:
                stderr_output.append(f"Write error: {write_err}")

        except subprocess.TimeoutExpired:
            stderr_output.append("Command timed out")
        except Exception as e:
            stderr_output.append(str(e))

        return DriveCheckResult(
            status=DriveStatus.UNREACHABLE,
            mount_path=self.mount_path,
            can_write=False,
            error_message="Automatic remount failed. Run this command manually:",
            attempted_remount=True,
            mount_command=mount_cmd,
            stderr_output="\n".join(stderr_output) if stderr_output else None,
            detection_method=None
        )

    def require_writable(self) -> Path:
        """
        Assert drive is writable or raise exception.

        Call before any expensive operations.

        Returns:
            Mount path if writable.

        Raises:
            DriveNotAvailableError if not writable.
        """
        result = self.check()
        if not result.can_write:
            raise DriveNotAvailableError(result)
        return result.mount_path

    def get_output_base(self) -> Path:
        """
        Get the base output directory path.

        Returns:
            Path to {mount}/{output_root}/
        """
        return self.mount_path / self.output_root

    def format_status_message(self, result: DriveCheckResult) -> str:
        """Format a human-readable status message."""
        if result.status == DriveStatus.MOUNTED:
            return f"G Drive connected at {result.mount_path}"

        msg = f"G Drive not available: {result.error_message}"
        if result.mount_command:
            msg += f"\n\nTo mount manually:\n  {result.mount_command}"
        return msg
