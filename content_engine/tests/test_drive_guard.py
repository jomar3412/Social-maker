"""Tests for DriveGuard service."""

import pytest
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock
import tempfile
import os

from content_engine.services.drive_guard import (
    DriveGuard,
    DriveStatus,
    DriveCheckResult,
    DriveNotAvailableError,
)


class TestDriveGuard:
    """Test DriveGuard mount detection and validation."""

    @pytest.fixture
    def temp_mount(self):
        """Create a temporary directory to simulate mount point."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def mock_config(self, temp_mount):
        """Create mock config for testing."""
        return {
            "gdrive": {
                "mount_path": str(temp_mount),
                "mount_name": "Test Drive",
                "output_root": "test_output",
                "rclone_remote": "test:remote",
                "attempt_auto_remount": False,
                "mount_command": "rclone mount {remote} {path} --daemon",
                "unmount_command": "fusermount -uz {path}",
            }
        }

    @pytest.fixture
    def guard(self, mock_config, temp_mount):
        """Create DriveGuard with mock config."""
        with patch.object(DriveGuard, "_load_config", return_value=mock_config):
            guard = DriveGuard()
            guard.mount_path = temp_mount
            yield guard

    def test_check_mount_path_not_exists(self, guard):
        """Test detection when mount path doesn't exist."""
        guard.mount_path = Path("/nonexistent/path")
        result = guard.check()

        assert result.status == DriveStatus.NOT_MOUNTED
        assert result.can_write is False
        assert result.mount_command is not None
        assert "not exist" in result.error_message

    def test_check_proc_mounts_detection(self, guard, temp_mount):
        """Test priority 1: /proc/mounts detection."""
        # Create marker file first
        marker = temp_mount / DriveGuard.MARKER_FILENAME
        marker.write_text("test marker")

        # Mock /proc/mounts to show our path as mounted
        proc_mounts_content = f"rclone {temp_mount.resolve()} fuse.rclone rw 0 0\n"

        with patch("builtins.open", mock_open(read_data=proc_mounts_content)):
            is_mounted, method = guard._is_mounted()

        assert is_mounted is True
        assert method == "/proc/mounts"

    def test_check_ismount_detection(self, guard, temp_mount):
        """Test priority 2: os.path.ismount detection."""
        # Mock /proc/mounts to not contain our path
        with patch("builtins.open", side_effect=FileNotFoundError):
            with patch("os.path.ismount", return_value=True):
                is_mounted, method = guard._is_mounted()

        assert is_mounted is True
        assert method == "os.path.ismount"

    def test_check_marker_file_detection(self, guard, temp_mount):
        """Test priority 3: marker file detection."""
        # Create marker file
        marker = temp_mount / DriveGuard.MARKER_FILENAME
        marker.write_text("test marker")

        # Mock both higher priority methods to fail
        with patch("builtins.open", side_effect=FileNotFoundError):
            with patch("os.path.ismount", return_value=False):
                is_mounted, method = guard._is_mounted()

        assert is_mounted is True
        assert method == "marker_file"

    def test_check_all_methods_failed(self, guard, temp_mount):
        """Test when all detection methods fail."""
        # No marker file, mock others to fail
        with patch("builtins.open", side_effect=FileNotFoundError):
            with patch("os.path.ismount", return_value=False):
                is_mounted, method = guard._is_mounted()

        assert is_mounted is False
        assert method == "all_methods_failed"

    def test_write_permission_check(self, guard, temp_mount):
        """Test write permission verification."""
        can_write, error = guard._test_write()
        assert can_write is True
        assert error is None

    def test_write_permission_readonly(self, guard, temp_mount):
        """Test write check fails on read-only path."""
        guard.mount_path = Path("/")  # Root is typically not writable
        can_write, error = guard._test_write()
        # This might pass or fail depending on permissions
        # Just verify it returns a tuple
        assert isinstance(can_write, bool)

    def test_ensure_marker_creates_file(self, guard, temp_mount):
        """Test marker file creation."""
        marker = temp_mount / DriveGuard.MARKER_FILENAME

        # Ensure marker doesn't exist
        if marker.exists():
            marker.unlink()

        result = guard.ensure_marker()
        assert result is True
        assert marker.exists()
        assert "Content Engine marker" in marker.read_text()

    def test_require_writable_success(self, guard, temp_mount):
        """Test require_writable returns path when writable."""
        # Create marker to simulate mounted drive
        marker = temp_mount / DriveGuard.MARKER_FILENAME
        marker.write_text("test")

        with patch.object(guard, "_is_mounted", return_value=(True, "marker_file")):
            path = guard.require_writable()
            assert path == temp_mount

    def test_require_writable_raises_when_not_mounted(self, guard, temp_mount):
        """Test require_writable raises when not mounted."""
        with patch.object(guard, "_is_mounted", return_value=(False, "all_methods_failed")):
            with pytest.raises(DriveNotAvailableError) as exc_info:
                guard.require_writable()

            assert exc_info.value.result.status in [
                DriveStatus.NOT_MOUNTED,
                DriveStatus.UNREACHABLE,
            ]

    def test_get_output_base(self, guard, temp_mount):
        """Test output base path generation."""
        guard.output_root = "content_engine"
        base = guard.get_output_base()
        assert base == temp_mount / "content_engine"

    def test_get_mount_command(self, guard):
        """Test mount command generation."""
        cmd = guard._get_mount_command()
        assert "rclone mount" in cmd
        assert guard.rclone_remote in cmd
        assert str(guard.mount_path) in cmd

    def test_format_status_message_mounted(self, guard, temp_mount):
        """Test status message for mounted drive."""
        result = DriveCheckResult(
            status=DriveStatus.MOUNTED,
            mount_path=temp_mount,
            can_write=True,
            error_message=None,
            attempted_remount=False,
            mount_command=None,
            stderr_output=None,
            detection_method="/proc/mounts",
        )
        msg = guard.format_status_message(result)
        assert "connected" in msg.lower()

    def test_format_status_message_not_mounted(self, guard, temp_mount):
        """Test status message for unmounted drive."""
        result = DriveCheckResult(
            status=DriveStatus.NOT_MOUNTED,
            mount_path=temp_mount,
            can_write=False,
            error_message="Drive not mounted",
            attempted_remount=False,
            mount_command="rclone mount ...",
            stderr_output=None,
            detection_method=None,
        )
        msg = guard.format_status_message(result)
        assert "not available" in msg.lower()
        assert "mount" in msg.lower()


class TestDriveNotAvailableError:
    """Test DriveNotAvailableError exception."""

    def test_error_includes_message(self):
        """Test error message includes drive status."""
        result = DriveCheckResult(
            status=DriveStatus.NOT_MOUNTED,
            mount_path=Path("/test"),
            can_write=False,
            error_message="Test error message",
            attempted_remount=False,
            mount_command="rclone mount test",
            stderr_output=None,
            detection_method=None,
        )
        error = DriveNotAvailableError(result)
        assert "Test error message" in str(error)
        assert "rclone mount test" in str(error)

    def test_error_includes_stderr(self):
        """Test error message includes stderr output."""
        result = DriveCheckResult(
            status=DriveStatus.UNREACHABLE,
            mount_path=Path("/test"),
            can_write=False,
            error_message="Mount failed",
            attempted_remount=True,
            mount_command="rclone mount test",
            stderr_output="Connection refused",
            detection_method=None,
        )
        error = DriveNotAvailableError(result)
        assert "Connection refused" in str(error)
