"""Tests for Git service implementations."""

import unittest
from unittest.mock import Mock, patch

from wt_manager.services.git_service import GitService
from wt_manager.services.async_git_service import AsyncGitService
from wt_manager.utils.exceptions import ValidationError


class TestGitService(unittest.TestCase):
    """Test cases for GitService."""

    def setUp(self):
        """Set up test fixtures."""
        self.git_service = GitService(timeout=5)

    def test_initialization(self):
        """Test service initialization."""
        self.assertFalse(self.git_service.is_initialized())
        self.assertEqual(self.git_service.timeout, 5)
        self.assertEqual(self.git_service._git_executable, "git")

    @patch("subprocess.run")
    def test_git_command_execution_success(self, mock_run):
        """Test successful Git command execution."""
        # Mock successful command
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "git version 2.39.0"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = self.git_service._run_git_command(["--version"], cwd=".")

        self.assertTrue(result.success)
        self.assertEqual(result.output, "git version 2.39.0")
        self.assertEqual(result.error, "")
        self.assertEqual(result.exit_code, 0)

    @patch("subprocess.run")
    def test_git_command_execution_failure(self, mock_run):
        """Test failed Git command execution."""
        # Mock failed command
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "fatal: not a git repository"
        mock_run.return_value = mock_result

        result = self.git_service._run_git_command(["status"], cwd=".")

        self.assertFalse(result.success)
        self.assertEqual(result.output, "")
        self.assertEqual(result.error, "fatal: not a git repository")
        self.assertEqual(result.exit_code, 1)

    def test_parse_worktree_list_empty(self):
        """Test parsing empty worktree list."""
        output = ""
        result = self.git_service._parse_worktree_list(output)
        self.assertEqual(result, [])

    def test_parse_worktree_list_single_worktree(self):
        """Test parsing single worktree."""
        output = """worktree /path/to/repo
HEAD abcd1234
branch refs/heads/main
"""
        result = self.git_service._parse_worktree_list(output)

        self.assertEqual(len(result), 1)
        worktree = result[0]
        self.assertEqual(worktree["path"], "/path/to/repo")
        self.assertEqual(worktree["commit_hash"], "abcd1234")
        self.assertEqual(worktree["branch"], "main")
        self.assertFalse(worktree["is_detached"])
        self.assertFalse(worktree["is_bare"])

    def test_parse_worktree_list_detached_head(self):
        """Test parsing worktree with detached HEAD."""
        output = """worktree /path/to/worktree
HEAD abcd1234
detached
"""
        result = self.git_service._parse_worktree_list(output)

        self.assertEqual(len(result), 1)
        worktree = result[0]
        self.assertEqual(worktree["path"], "/path/to/worktree")
        self.assertEqual(worktree["commit_hash"], "abcd1234")
        self.assertEqual(worktree["branch"], "HEAD")
        self.assertTrue(worktree["is_detached"])
        self.assertFalse(worktree["is_bare"])

    def test_parse_worktree_list_bare_repository(self):
        """Test parsing bare repository."""
        output = """worktree /path/to/bare
HEAD abcd1234
bare
"""
        result = self.git_service._parse_worktree_list(output)

        self.assertEqual(len(result), 1)
        worktree = result[0]
        self.assertEqual(worktree["path"], "/path/to/bare")
        self.assertEqual(worktree["commit_hash"], "abcd1234")
        self.assertTrue(worktree["is_bare"])

    def test_parse_worktree_list_multiple_worktrees(self):
        """Test parsing multiple worktrees."""
        output = """worktree /path/to/main
HEAD abcd1234
branch refs/heads/main

worktree /path/to/feature
HEAD efgh5678
branch refs/heads/feature-branch

worktree /path/to/detached
HEAD ijkl9012
detached
"""
        result = self.git_service._parse_worktree_list(output)

        self.assertEqual(len(result), 3)

        # Check main worktree
        main_wt = result[0]
        self.assertEqual(main_wt["path"], "/path/to/main")
        self.assertEqual(main_wt["branch"], "main")
        self.assertFalse(main_wt["is_detached"])

        # Check feature worktree
        feature_wt = result[1]
        self.assertEqual(feature_wt["path"], "/path/to/feature")
        self.assertEqual(feature_wt["branch"], "feature-branch")
        self.assertFalse(feature_wt["is_detached"])

        # Check detached worktree
        detached_wt = result[2]
        self.assertEqual(detached_wt["path"], "/path/to/detached")
        self.assertEqual(detached_wt["branch"], "HEAD")
        self.assertTrue(detached_wt["is_detached"])

    @patch("subprocess.run")
    def test_is_git_repository_true(self, mock_run):
        """Test checking if path is a Git repository (positive case)."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ".git"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = self.git_service.is_git_repository("/path/to/repo")
        self.assertTrue(result)

    @patch("subprocess.run")
    def test_is_git_repository_false(self, mock_run):
        """Test checking if path is a Git repository (negative case)."""
        mock_result = Mock()
        mock_result.returncode = 128
        mock_result.stdout = ""
        mock_result.stderr = "fatal: not a git repository"
        mock_run.return_value = mock_result

        result = self.git_service.is_git_repository("/path/to/not-repo")
        self.assertFalse(result)

    def test_create_worktree_validation_error(self):
        """Test worktree creation with invalid inputs."""
        with self.assertRaises(ValidationError):
            self.git_service.create_worktree("", "path", "branch")

        with self.assertRaises(ValidationError):
            self.git_service.create_worktree("repo", "", "branch")

        with self.assertRaises(ValidationError):
            self.git_service.create_worktree("repo", "path", "")

    def test_remove_worktree_validation_error(self):
        """Test worktree removal with invalid inputs."""
        with self.assertRaises(ValidationError):
            self.git_service.remove_worktree("")


class TestAsyncGitService(unittest.TestCase):
    """Test cases for AsyncGitService."""

    def setUp(self):
        """Set up test fixtures."""
        self.git_service = Mock(spec=GitService)
        self.async_git_service = AsyncGitService(self.git_service)

    def test_initialization(self):
        """Test async service initialization."""
        self.assertEqual(self.async_git_service.git_service, self.git_service)
        self.assertEqual(len(self.async_git_service._active_operations), 0)
        self.assertEqual(self.async_git_service._operation_counter, 0)

    def test_generate_operation_id(self):
        """Test operation ID generation."""
        id1 = self.async_git_service._generate_operation_id()
        id2 = self.async_git_service._generate_operation_id()

        self.assertNotEqual(id1, id2)
        self.assertTrue(id1.startswith("git_op_1_"))
        self.assertTrue(id2.startswith("git_op_2_"))

    def test_get_active_operations_empty(self):
        """Test getting active operations when none are running."""
        operations = self.async_git_service.get_active_operations()
        self.assertEqual(operations, [])

    def test_is_operation_active_false(self):
        """Test checking if operation is active when it's not."""
        result = self.async_git_service.is_operation_active("nonexistent")
        self.assertFalse(result)

    def test_cancel_nonexistent_operation(self):
        """Test cancelling a non-existent operation."""
        result = self.async_git_service.cancel_operation("nonexistent")
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
