"""Tests for WorktreeService."""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from wt_manager.models.project import Project, ProjectStatus
from wt_manager.models.worktree import Worktree
from wt_manager.services.worktree_service import WorktreeService
from wt_manager.utils.exceptions import ServiceError, ValidationError


class TestWorktreeService:
    """Test cases for WorktreeService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_git_service = Mock()
        self.mock_validation_service = Mock()

        # Mock initialization
        self.mock_git_service.is_initialized.return_value = True
        self.mock_validation_service.is_initialized.return_value = True

        self.service = WorktreeService(
            git_service=self.mock_git_service,
            validation_service=self.mock_validation_service,
        )

    def test_initialization(self):
        """Test service initialization."""
        assert not self.service.is_initialized()
        self.service.initialize()
        assert self.service.is_initialized()

    def test_get_worktrees_success(self):
        """Test successful worktree retrieval."""
        # Setup
        project = Project(
            id="test-id",
            name="test-project",
            path="/test/project",
            status=ProjectStatus.ACTIVE,
            last_accessed=datetime.now(),
        )

        # Mock Git service response
        git_worktree_data = [
            {
                "path": "/test/project",
                "branch": "main",
                "commit_hash": "abc123",
                "is_bare": False,
                "is_detached": False,
            },
            {
                "path": "/test/worktree1",
                "branch": "feature",
                "commit_hash": "def456",
                "is_bare": False,
                "is_detached": False,
            },
        ]
        self.mock_git_service.get_worktree_list.return_value = git_worktree_data
        self.mock_git_service.check_uncommitted_changes.return_value = False

        self.service.initialize()

        # Get worktrees
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.stat") as mock_stat,
        ):
            mock_stat.return_value.st_mtime = datetime.now().timestamp()
            worktrees = self.service.get_worktrees(project)

        # Verify
        assert len(worktrees) == 2
        assert all(isinstance(wt, Worktree) for wt in worktrees)
        assert worktrees[0].path == "/test/project"
        assert worktrees[0].branch == "main"
        assert worktrees[1].path == "/test/worktree1"
        assert worktrees[1].branch == "feature"
        assert project.worktrees == worktrees

    def test_get_worktrees_invalid_project(self):
        """Test worktree retrieval with invalid project."""
        self.service.initialize()

        with pytest.raises(ServiceError, match="Invalid project provided"):
            self.service.get_worktrees(None)

    def test_create_worktree_success(self):
        """Test successful worktree creation."""
        # Setup
        project = Project(
            id="test-id",
            name="test-project",
            path="/test/project",
            status=ProjectStatus.ACTIVE,
            last_accessed=datetime.now(),
        )

        worktree_path = "/test/new-worktree"
        branch_name = "feature-branch"

        # Mock validation and Git operations
        self.mock_validation_service.validate_worktree_path.return_value = Mock(
            is_valid=True, message="Valid path"
        )
        self.mock_validation_service.validate_branch_name.return_value = Mock(
            is_valid=True, message="Valid branch"
        )
        self.mock_git_service.fetch_remote.return_value = Mock(success=True)
        self.mock_git_service.create_worktree.return_value = Mock(
            success=True, output="Worktree created"
        )
        self.mock_git_service.check_uncommitted_changes.return_value = False

        self.service.initialize()

        # Create worktree
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.stat") as mock_stat,
        ):
            mock_stat.return_value.st_mtime = datetime.now().timestamp()
            worktree = self.service.create_worktree(project, worktree_path, branch_name)

        # Verify
        assert isinstance(worktree, Worktree)
        assert worktree.path == str(Path(worktree_path).resolve())
        assert worktree.branch == branch_name
        assert worktree in project.worktrees

        self.mock_validation_service.validate_worktree_path.assert_called_once_with(
            worktree_path
        )
        self.mock_validation_service.validate_branch_name.assert_called_once_with(
            branch_name
        )
        self.mock_git_service.create_worktree.assert_called_once()

    def test_create_worktree_validation_failure(self):
        """Test worktree creation with validation failure."""
        # Setup
        project = Project(
            id="test-id",
            name="test-project",
            path="/test/project",
            status=ProjectStatus.ACTIVE,
            last_accessed=datetime.now(),
        )

        # Mock validation failure
        self.mock_validation_service.validate_worktree_path.return_value = Mock(
            is_valid=False, message="Invalid path"
        )
        self.mock_validation_service.validate_branch_name.return_value = Mock(
            is_valid=True, message="Valid branch"
        )

        self.service.initialize()

        # Attempt to create worktree
        with pytest.raises(ValidationError, match="Invalid path"):
            self.service.create_worktree(project, "/invalid/path", "branch")

    def test_create_worktree_git_failure(self):
        """Test worktree creation with Git operation failure."""
        # Setup
        project = Project(
            id="test-id",
            name="test-project",
            path="/test/project",
            status=ProjectStatus.ACTIVE,
            last_accessed=datetime.now(),
        )

        # Mock validation success but Git failure
        self.mock_validation_service.validate_worktree_path.return_value = Mock(
            is_valid=True, message="Valid path"
        )
        self.mock_validation_service.validate_branch_name.return_value = Mock(
            is_valid=True, message="Valid branch"
        )
        self.mock_git_service.fetch_remote.return_value = Mock(success=True)
        self.mock_git_service.create_worktree.return_value = Mock(
            success=False, error="Branch does not exist"
        )

        self.service.initialize()

        # Attempt to create worktree
        with pytest.raises(ServiceError, match="Failed to create worktree"):
            self.service.create_worktree(project, "/test/path", "nonexistent-branch")

    def test_remove_worktree_success(self):
        """Test successful worktree removal."""
        # Setup
        worktree = Worktree(
            path="/test/worktree",
            branch="feature",
            commit_hash="abc123",
        )

        # Mock validation and Git operations
        self.mock_validation_service.check_uncommitted_changes.return_value = Mock(
            is_valid=True, details={"has_uncommitted_changes": False}
        )
        self.mock_git_service.remove_worktree.return_value = Mock(
            success=True, output="Worktree removed"
        )

        self.service.initialize()

        # Remove worktree
        with patch.object(worktree, "is_current_directory", return_value=False):
            result = self.service.remove_worktree(worktree)

        # Verify
        assert result is True
        self.mock_git_service.remove_worktree.assert_called_once_with(
            "/test/worktree", False
        )

    def test_remove_worktree_with_uncommitted_changes(self):
        """Test worktree removal with uncommitted changes."""
        # Setup
        worktree = Worktree(
            path="/test/worktree",
            branch="feature",
            commit_hash="abc123",
        )

        # Mock uncommitted changes
        self.mock_validation_service.check_uncommitted_changes.return_value = Mock(
            is_valid=True, details={"has_uncommitted_changes": True}
        )

        self.service.initialize()

        # Attempt to remove worktree without force
        with patch.object(worktree, "is_current_directory", return_value=False):
            with pytest.raises(ServiceError, match="has uncommitted changes"):
                self.service.remove_worktree(worktree, force=False)

    def test_remove_worktree_current_directory(self):
        """Test worktree removal when it's the current directory."""
        # Setup
        worktree = Worktree(
            path="/test/worktree",
            branch="feature",
            commit_hash="abc123",
        )

        # Mock no uncommitted changes
        self.mock_validation_service.check_uncommitted_changes.return_value = Mock(
            is_valid=True, details={"has_uncommitted_changes": False}
        )

        self.service.initialize()

        # Attempt to remove current directory worktree
        with patch.object(worktree, "is_current_directory", return_value=True):
            with pytest.raises(ServiceError, match="current working directory"):
                self.service.remove_worktree(worktree)

    def test_validate_worktree_creation(self):
        """Test worktree creation validation."""
        # Setup project
        project = Project(
            id="test-id",
            name="test-project",
            path="/test/project",
            status=ProjectStatus.ACTIVE,
            last_accessed=datetime.now(),
        )

        # Setup mocks
        self.mock_validation_service.validate_worktree_path.return_value = Mock(
            is_valid=True, message="Valid path"
        )
        self.mock_validation_service.validate_branch_name.return_value = Mock(
            is_valid=True, message="Valid branch"
        )
        self.mock_validation_service.validate_branch_not_in_use.return_value = Mock(
            is_valid=True, message="Branch available"
        )

        # Test validation
        result = self.service.validate_worktree_creation(
            project, "/test/path", "branch-name"
        )

        # Verify
        assert result.is_valid
        self.mock_validation_service.validate_worktree_path.assert_called_once_with(
            "/test/path"
        )
        self.mock_validation_service.validate_branch_name.assert_called_once_with(
            "branch-name"
        )
        self.mock_validation_service.validate_branch_not_in_use.assert_called_once_with(
            "branch-name", "/test/project", self.mock_git_service
        )

    def test_refresh_worktree(self):
        """Test worktree refresh."""
        # Setup
        worktree = Worktree(
            path="/test/worktree",
            branch="feature",
            commit_hash="",  # Empty, should be updated
        )

        # Mock Git operations
        self.mock_git_service.get_current_branch.return_value = "feature"
        self.mock_git_service.execute_command.return_value = Mock(
            success=True, output="def456"
        )
        self.mock_git_service.check_uncommitted_changes.return_value = True

        self.service.initialize()

        # Refresh worktree
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.stat") as mock_stat,
        ):
            mock_stat.return_value.st_mtime = datetime.now().timestamp()
            refreshed_worktree = self.service.refresh_worktree(worktree)

        # Verify
        assert refreshed_worktree.commit_hash == "def456"
        assert refreshed_worktree.has_uncommitted_changes is True

    def test_get_available_branches(self):
        """Test getting available branches."""
        # Setup
        project = Project(
            id="test-id",
            name="test-project",
            path="/test/project",
            status=ProjectStatus.ACTIVE,
            last_accessed=datetime.now(),
        )

        expected_branches = ["main", "develop", "feature/new"]
        self.mock_git_service.get_branch_list.return_value = expected_branches

        self.service.initialize()

        # Get branches
        branches = self.service.get_available_branches(project)

        # Verify
        assert branches == expected_branches
        self.mock_git_service.get_branch_list.assert_called_once_with(project.path)

    def test_find_worktree_by_path(self):
        """Test finding worktree by path."""
        # Setup
        worktree1 = Worktree(path="/test/worktree1", branch="main", commit_hash="abc")
        worktree2 = Worktree(
            path="/test/worktree2", branch="feature", commit_hash="def"
        )

        project = Project(
            id="test-id",
            name="test-project",
            path="/test/project",
            status=ProjectStatus.ACTIVE,
            last_accessed=datetime.now(),
            worktrees=[worktree1, worktree2],
        )

        self.service.initialize()

        # Find worktree
        found = self.service.find_worktree_by_path(project, "/test/worktree1")
        assert found == worktree1

        not_found = self.service.find_worktree_by_path(project, "/test/nonexistent")
        assert not_found is None

    def test_get_worktree_status(self):
        """Test getting worktree status."""
        # Setup
        worktree = Worktree(
            path="/test/worktree",
            branch="feature",
            commit_hash="abc123",
            has_uncommitted_changes=True,
        )

        # Mock Git operations
        self.mock_git_service.get_current_branch.return_value = "feature"
        self.mock_git_service.check_uncommitted_changes.return_value = True

        self.service.initialize()

        # Get status
        with (
            patch.object(worktree, "exists", return_value=True),
            patch.object(worktree, "is_accessible", return_value=True),
            patch.object(worktree, "is_current_directory", return_value=False),
        ):
            status = self.service.get_worktree_status(worktree)

        # Verify
        assert status["path"] == "/test/worktree"
        assert status["branch"] == "feature"
        assert status["commit_hash"] == "abc123"
        assert status["has_uncommitted_changes"] is True
        assert status["exists"] is True
        assert status["accessible"] is True
        assert status["current_branch"] == "feature"


class TestWorktreeServiceIntegration:
    """Integration tests for WorktreeService."""

    def test_real_worktree_operations(self):
        """Test worktree operations with real Git repository."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = self._setup_test_repository(temp_dir)
            project = self._create_test_project(repo_path)
            service = WorktreeService()
            service.initialize()

            self._test_basic_worktree_operations(service, project, repo_path)
            self._test_worktree_creation_and_removal(service, project, temp_dir)

    def _setup_test_repository(self, temp_dir: str) -> Path:
        """Set up a test Git repository."""
        repo_path = Path(temp_dir) / "test_repo"
        repo_path.mkdir()

        # Initialize Git repo
        import subprocess

        subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test"], cwd=repo_path, check=True
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo_path,
            check=True,
        )

        # Create a test file and commit
        test_file = repo_path / "README.md"
        test_file.write_text("# Test Repository")
        subprocess.run(["git", "add", "README.md"], cwd=repo_path, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"], cwd=repo_path, check=True
        )

        return repo_path

    def _create_test_project(self, repo_path: Path) -> Project:
        """Create a test project."""
        return Project(
            id="test-id",
            name="test-project",
            path=str(repo_path),
            status=ProjectStatus.ACTIVE,
            last_accessed=datetime.now(),
        )

    def _test_basic_worktree_operations(
        self, service: WorktreeService, project: Project, repo_path: Path
    ) -> None:
        """Test basic worktree operations."""
        # Test getting worktrees (should have main worktree)
        worktrees = service.get_worktrees(project)
        assert len(worktrees) >= 1
        main_worktree = worktrees[0]
        # Use resolve() to handle symlinks in temp directories
        assert Path(main_worktree.path).resolve() == Path(repo_path).resolve()

        # Test getting available branches
        branches = service.get_available_branches(project)
        assert "main" in branches or "master" in branches

    def _test_worktree_creation_and_removal(
        self, service: WorktreeService, project: Project, temp_dir: str
    ) -> None:
        """Test worktree creation and removal."""
        import subprocess

        # Create a new branch for the worktree
        subprocess.run(
            ["git", "checkout", "-b", "feature"], cwd=project.path, check=True
        )
        subprocess.run(
            ["git", "checkout", "main"], cwd=project.path, check=True
        )  # Go back to main

        # Test worktree validation
        worktree_path = str(Path(temp_dir) / "new_worktree")
        validation_result = service.validate_worktree_creation(
            project, worktree_path, "feature"
        )
        assert validation_result.is_valid

        # Test creating a new worktree
        new_worktree = service.create_worktree(project, worktree_path, "feature")
        assert Path(new_worktree.path).resolve() == Path(worktree_path).resolve()
        assert new_worktree.branch == "feature"
        assert Path(worktree_path).exists()

        # Test getting worktree status
        status = service.get_worktree_status(new_worktree)
        assert status["exists"] is True
        assert status["accessible"] is True

        # Test removing worktree
        result = service.remove_worktree(new_worktree, force=True)
        assert result is True
        assert not Path(worktree_path).exists()
