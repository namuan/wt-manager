"""Tests for PathManager utility class."""

import stat
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from wt_manager.utils.exceptions import PathError
from wt_manager.utils.path_manager import PathManager


class TestPathManager:
    """Test cases for PathManager class."""

    def test_get_config_dir_macos(self):
        """Test config directory resolution on macOS."""
        with patch("sys.platform", "darwin"):
            config_dir = PathManager.get_config_dir()
            expected = (
                Path.home() / "Library" / "Application Support" / "GitWorktreeManager"
            )
            assert config_dir == expected

    def test_get_config_dir_windows(self):
        """Test config directory resolution on Windows."""
        with patch("sys.platform", "win32"):
            config_dir = PathManager.get_config_dir()
            expected = Path.home() / "AppData" / "Roaming" / "GitWorktreeManager"
            assert config_dir == expected

    def test_get_config_dir_linux(self):
        """Test config directory resolution on Linux."""
        with patch("sys.platform", "linux"):
            config_dir = PathManager.get_config_dir()
            expected = Path.home() / ".config" / "GitWorktreeManager"
            assert config_dir == expected

    def test_get_log_dir_macos(self):
        """Test log directory resolution on macOS."""
        with patch("sys.platform", "darwin"):
            log_dir = PathManager.get_log_dir()
            expected = Path.home() / "Library" / "Logs" / "GitWorktreeManager"
            assert log_dir == expected

    def test_get_log_dir_windows(self):
        """Test log directory resolution on Windows."""
        with patch("sys.platform", "win32"):
            log_dir = PathManager.get_log_dir()
            expected = Path.home() / "AppData" / "Local" / "GitWorktreeManager" / "Logs"
            assert log_dir == expected

    def test_get_log_dir_linux(self):
        """Test log directory resolution on Linux."""
        with patch("sys.platform", "linux"):
            log_dir = PathManager.get_log_dir()
            expected = (
                Path.home()
                / ".local"
                / "share"
                / "git-worktree-manager"
                / "logs"
                / "GitWorktreeManager"
            )
            assert log_dir == expected

    def test_get_cache_dir_macos(self):
        """Test cache directory resolution on macOS."""
        with patch("sys.platform", "darwin"):
            cache_dir = PathManager.get_cache_dir()
            expected = Path.home() / "Library" / "Caches" / "GitWorktreeManager"
            assert cache_dir == expected

    def test_get_cache_dir_windows(self):
        """Test cache directory resolution on Windows."""
        with patch("sys.platform", "win32"):
            cache_dir = PathManager.get_cache_dir()
            expected = (
                Path.home() / "AppData" / "Local" / "GitWorktreeManager" / "Cache"
            )
            assert cache_dir == expected

    def test_get_cache_dir_linux(self):
        """Test cache directory resolution on Linux."""
        with patch("sys.platform", "linux"):
            cache_dir = PathManager.get_cache_dir()
            expected = Path.home() / ".cache" / "GitWorktreeManager"
            assert cache_dir == expected

    def test_sanitize_path_basic(self):
        """Test basic path sanitization."""
        result = PathManager.sanitize_path("normal/path")
        assert result == "normal/path"

    def test_sanitize_path_traversal_attack(self):
        """Test path sanitization removes traversal attempts."""
        result = PathManager.sanitize_path("../../../etc/passwd")
        assert result == "etc/passwd"

    def test_sanitize_path_mixed_separators(self):
        """Test path sanitization normalizes separators."""
        result = PathManager.sanitize_path("path\\with\\backslashes")
        assert result == "path/with/backslashes"

    def test_sanitize_path_whitespace(self):
        """Test path sanitization removes leading/trailing whitespace."""
        result = PathManager.sanitize_path("  /path/with/spaces/  ")
        assert result == "path/with/spaces"

    def test_sanitize_path_empty_string(self):
        """Test path sanitization handles empty string."""
        with pytest.raises(PathError, match="Path must be a non-empty string"):
            PathManager.sanitize_path("")

    def test_sanitize_path_none(self):
        """Test path sanitization handles None."""
        with pytest.raises(PathError, match="Path must be a non-empty string"):
            PathManager.sanitize_path(None)

    def test_sanitize_path_null_bytes(self):
        """Test path sanitization rejects null bytes."""
        with pytest.raises(PathError, match="Path contains null bytes"):
            PathManager.sanitize_path("path\x00with\x00nulls")

    def test_sanitize_path_becomes_empty(self):
        """Test path sanitization handles paths that become empty."""
        with pytest.raises(PathError, match="Path becomes empty after sanitization"):
            PathManager.sanitize_path("../../..")

    def test_is_safe_path_within_base(self):
        """Test is_safe_path returns True for paths within base."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)
            safe_path = base_path / "subdir" / "file.txt"
            assert PathManager.is_safe_path(safe_path, base_path) is True

    def test_is_safe_path_outside_base(self):
        """Test is_safe_path returns False for paths outside base."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir) / "subdir"
            unsafe_path = Path(temp_dir) / "other" / "file.txt"
            assert PathManager.is_safe_path(unsafe_path, base_path) is False

    def test_is_safe_path_same_as_base(self):
        """Test is_safe_path returns True for path same as base."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)
            assert PathManager.is_safe_path(base_path, base_path) is True

    def test_validate_directory_permissions_valid(self):
        """Test validate_directory_permissions with valid directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            # Should not raise an exception
            PathManager.validate_directory_permissions(directory)

    def test_validate_directory_permissions_nonexistent(self):
        """Test validate_directory_permissions with nonexistent directory."""
        nonexistent = Path("/nonexistent/directory")
        with pytest.raises(PathError, match="Directory does not exist"):
            PathManager.validate_directory_permissions(nonexistent)

    def test_validate_directory_permissions_not_directory(self):
        """Test validate_directory_permissions with file instead of directory."""
        with tempfile.NamedTemporaryFile() as temp_file:
            file_path = Path(temp_file.name)
            with pytest.raises(PathError, match="Path is not a directory"):
                PathManager.validate_directory_permissions(file_path)

    def test_validate_path_writable_existing_writable(self):
        """Test validate_path_writable with existing writable path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir)
            assert PathManager.validate_path_writable(path) is True

    def test_validate_path_writable_nonexistent_writable_parent(self):
        """Test validate_path_writable with nonexistent path but writable parent."""
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "nonexistent"
            assert PathManager.validate_path_writable(path) is True

    def test_create_directory_safe_success(self):
        """Test create_directory_safe creates directory successfully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            new_dir = Path(temp_dir) / "new_directory"
            PathManager.create_directory_safe(new_dir)
            assert new_dir.exists()
            assert new_dir.is_dir()

    def test_create_directory_safe_with_mode(self):
        """Test create_directory_safe with specific mode."""
        if sys.platform == "win32":
            pytest.skip("File mode not supported on Windows")

        with tempfile.TemporaryDirectory() as temp_dir:
            new_dir = Path(temp_dir) / "new_directory"
            mode = stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP  # 750
            PathManager.create_directory_safe(new_dir, mode)
            assert new_dir.exists()
            assert new_dir.is_dir()
            # Check permissions (may vary due to umask)
            actual_mode = new_dir.stat().st_mode & 0o777
            assert actual_mode == mode

    def test_get_safe_filename_normal(self):
        """Test get_safe_filename with normal filename."""
        result = PathManager.get_safe_filename("normal_file.txt")
        assert result == "normal_file.txt"

    def test_get_safe_filename_invalid_chars(self):
        """Test get_safe_filename removes invalid characters."""
        result = PathManager.get_safe_filename('file<>:"/\\|?*.txt')
        # Count the actual invalid characters: < > : " / \ | ? * = 9 characters
        assert result == "file_________.txt"

    def test_get_safe_filename_empty(self):
        """Test get_safe_filename handles empty string."""
        result = PathManager.get_safe_filename("")
        assert result == "unnamed"

    def test_get_safe_filename_whitespace_and_dots(self):
        """Test get_safe_filename handles whitespace and dots."""
        result = PathManager.get_safe_filename("  file.txt  ...")
        assert result == "file.txt"

    def test_get_safe_filename_too_long(self):
        """Test get_safe_filename truncates long filenames."""
        long_name = "a" * 300
        result = PathManager.get_safe_filename(long_name)
        assert len(result) == 255
        assert result == "a" * 255

    def test_resolve_path_safely_absolute(self):
        """Test resolve_path_safely with absolute path."""
        # Use a path that we know exists and won't be deleted
        home_dir = str(Path.home())
        path = PathManager.resolve_path_safely(home_dir)
        # Path should be absolute and exist
        assert path.is_absolute()
        assert path.exists()
        # Should resolve to the same directory
        assert path == Path(home_dir).resolve()

    def test_resolve_path_safely_relative_with_base(self):
        """Test resolve_path_safely with relative path and base."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)
            relative_path = "subdir/file.txt"
            result = PathManager.resolve_path_safely(relative_path, base_path)
            expected = (base_path / relative_path).resolve()
            assert result == expected

    def test_resolve_path_safely_unsafe_path(self):
        """Test resolve_path_safely rejects unsafe paths."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir) / "subdir"
            base_path.mkdir()
            unsafe_path = "../../../etc/passwd"
            with pytest.raises(PathError, match="resolves outside of base path"):
                PathManager.resolve_path_safely(unsafe_path, base_path)

    def test_get_config_file(self):
        """Test get_config_file returns correct path."""
        filename = "test_config.json"
        result = PathManager.get_config_file(filename)
        expected = PathManager.get_config_dir() / filename
        assert result == expected

    def test_get_log_file(self):
        """Test get_log_file returns correct path."""
        filename = "test.log"
        result = PathManager.get_log_file(filename)
        expected = PathManager.get_log_dir() / filename
        assert result == expected

    def test_get_cache_file(self):
        """Test get_cache_file returns correct path."""
        filename = "test_cache.dat"
        result = PathManager.get_cache_file(filename)
        expected = PathManager.get_cache_dir() / filename
        assert result == expected

    def test_ensure_directories_success(self):
        """Test ensure_directories creates all required directories."""
        with (
            patch.object(PathManager, "get_config_dir") as mock_config,
            patch.object(PathManager, "get_log_dir") as mock_log,
            patch.object(PathManager, "get_cache_dir") as mock_cache,
        ):
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                mock_config.return_value = temp_path / "config"
                mock_log.return_value = temp_path / "logs"
                mock_cache.return_value = temp_path / "cache"

                PathManager.ensure_directories()

                assert (temp_path / "config").exists()
                assert (temp_path / "logs").exists()
                assert (temp_path / "cache").exists()

    def test_ensure_directories_permission_error(self):
        """Test ensure_directories handles permission errors."""
        with patch.object(PathManager, "get_config_dir") as mock_config:
            # Use a path that should cause permission error
            mock_config.return_value = Path("/root/restricted")

            with pytest.raises(PathError, match="Failed to create directory"):
                PathManager.ensure_directories()
