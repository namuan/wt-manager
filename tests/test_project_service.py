"""Tests for ProjectService."""

import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from wt_manager.models.project import Project, ProjectStatus
from wt_manager.services.project_service import ProjectService
from wt_manager.utils.exceptions import ServiceError, ValidationError


class TestProjectService:
    """Test cases for ProjectService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_config_manager = Mock()
        self.mock_git_service = Mock()
        self.mock_validation_service = Mock()

        # Mock initialization
        self.mock_git_service.is_initialized.return_value = True
        self.mock_validation_service.is_initialized.return_value = True

        self.service = ProjectService(
            config_manager=self.mock_config_manager,
            git_service=self.mock_git_service,
            validation_service=self.mock_validation_service,
        )

    def test_initialization(self):
        """Test service initialization."""
        assert not self.service.is_initialized()

        # Mock config loading
        self.mock_config_manager.get_all_project_configs.return_value = []

        self.service.initialize()
        assert self.service.is_initialized()

    def test_add_project_success(self):
        """Test successful project addition."""
        # Setup mocks
        test_path = "/test/repo"
        self.mock_validation_service.validate_git_repository.return_value = Mock(
            is_valid=True, message="Valid repository"
        )
        self.mock_config_manager.add_project.return_value = True

        # Mock config loading for initialization
        self.mock_config_manager.get_all_project_configs.return_value = []
        self.service.initialize()

        # Mock path validation in Project model
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.is_dir", return_value=True),
        ):
            # Add project
            project = self.service.add_project(test_path)

        # Verify
        assert isinstance(project, Project)
        assert project.path == str(Path(test_path).resolve())
        assert project.status == ProjectStatus.ACTIVE
        self.mock_validation_service.validate_git_repository.assert_called_once_with(
            test_path
        )
        self.mock_config_manager.add_project.assert_called_once()

    def test_add_project_validation_failure(self):
        """Test project addition with validation failure."""
        # Setup mocks
        test_path = "/invalid/repo"
        self.mock_validation_service.validate_git_repository.return_value = Mock(
            is_valid=False, message="Not a Git repository"
        )

        # Mock config loading for initialization
        self.mock_config_manager.get_all_project_configs.return_value = []
        self.service.initialize()

        # Attempt to add project
        with pytest.raises(ValidationError, match="Not a Git repository"):
            self.service.add_project(test_path)

    def test_add_project_config_save_failure(self):
        """Test project addition with config save failure."""
        # Setup mocks
        test_path = "/test/repo"
        self.mock_validation_service.validate_git_repository.return_value = Mock(
            is_valid=True, message="Valid repository"
        )
        self.mock_config_manager.add_project.return_value = False

        # Mock config loading for initialization
        self.mock_config_manager.get_all_project_configs.return_value = []
        self.service.initialize()

        # Attempt to add project
        with pytest.raises(ServiceError, match="Failed to save project configuration"):
            self.service.add_project(test_path)

    def test_remove_project_success(self):
        """Test successful project removal."""
        # Setup - add a project first
        test_path = "/test/repo"
        project_id = str(uuid.uuid4())

        self.mock_validation_service.validate_git_repository.return_value = Mock(
            is_valid=True, message="Valid repository"
        )
        self.mock_config_manager.add_project.return_value = True
        self.mock_config_manager.remove_project.return_value = True

        # Mock config loading for initialization
        self.mock_config_manager.get_all_project_configs.return_value = []
        self.service.initialize()

        # Add project to cache manually for testing
        project = Project(
            id=project_id,
            name="test",
            path=test_path,
            status=ProjectStatus.ACTIVE,
            last_accessed=datetime.now(),
        )
        self.service._projects_cache[project_id] = project

        # Remove project
        result = self.service.remove_project(project_id)

        # Verify
        assert result is True
        assert project_id not in self.service._projects_cache
        self.mock_config_manager.remove_project.assert_called_once_with(project_id)

    def test_remove_project_not_found(self):
        """Test removing non-existent project."""
        # Mock config loading for initialization
        self.mock_config_manager.get_all_project_configs.return_value = []
        self.service.initialize()

        result = self.service.remove_project("nonexistent-id")
        assert result is False

    def test_get_projects(self):
        """Test getting all projects."""
        # Mock config loading for initialization
        self.mock_config_manager.get_all_project_configs.return_value = []
        self.service.initialize()

        # Add some projects to cache
        project1 = Project(
            id="1",
            name="proj1",
            path="/path1",
            status=ProjectStatus.ACTIVE,
            last_accessed=datetime.now(),
        )
        project2 = Project(
            id="2",
            name="proj2",
            path="/path2",
            status=ProjectStatus.ACTIVE,
            last_accessed=datetime.now(),
        )

        self.service._projects_cache["1"] = project1
        self.service._projects_cache["2"] = project2

        projects = self.service.get_projects()
        assert len(projects) == 2
        assert project1 in projects
        assert project2 in projects

    def test_refresh_project(self):
        """Test refreshing project information."""
        # Setup
        project_id = "test-id"
        project = Project(
            id=project_id,
            name="test",
            path="/test/path",
            status=ProjectStatus.ACTIVE,
            last_accessed=datetime.now(),
        )

        # Mock config loading for initialization
        self.mock_config_manager.get_all_project_configs.return_value = []
        self.service.initialize()

        self.service._projects_cache[project_id] = project
        self.mock_config_manager.update_project.return_value = True

        # Refresh project
        refreshed_project = self.service.refresh_project(project_id)

        # Verify
        assert refreshed_project.id == project_id
        self.mock_config_manager.update_project.assert_called_once()

    def test_refresh_project_not_found(self):
        """Test refreshing non-existent project."""
        # Mock config loading for initialization
        self.mock_config_manager.get_all_project_configs.return_value = []
        self.service.initialize()

        with pytest.raises(ServiceError, match="Project not found"):
            self.service.refresh_project("nonexistent-id")

    def test_validate_project(self):
        """Test project validation."""
        test_path = "/test/repo"
        expected_result = Mock(is_valid=True, message="Valid")
        self.mock_validation_service.validate_git_repository.return_value = (
            expected_result
        )

        result = self.service.validate_project(test_path)

        assert result == expected_result
        self.mock_validation_service.validate_git_repository.assert_called_once_with(
            test_path
        )

    def test_get_project_by_id(self):
        """Test getting project by ID."""
        # Mock config loading for initialization
        self.mock_config_manager.get_all_project_configs.return_value = []
        self.service.initialize()

        project = Project(
            id="test-id",
            name="test",
            path="/test",
            status=ProjectStatus.ACTIVE,
            last_accessed=datetime.now(),
        )
        self.service._projects_cache["test-id"] = project

        result = self.service.get_project_by_id("test-id")
        assert result == project

        result = self.service.get_project_by_id("nonexistent")
        assert result is None

    def test_get_project_by_path(self):
        """Test getting project by path."""
        # Mock config loading for initialization
        self.mock_config_manager.get_all_project_configs.return_value = []
        self.service.initialize()

        test_path = "/test/path"
        project = Project(
            id="test-id",
            name="test",
            path=test_path,
            status=ProjectStatus.ACTIVE,
            last_accessed=datetime.now(),
        )
        self.service._projects_cache["test-id"] = project

        result = self.service.get_project_by_path(test_path)
        assert result == project

        result = self.service.get_project_by_path("/nonexistent")
        assert result is None

    def test_update_project_access_time(self):
        """Test updating project access time."""
        # Mock config loading for initialization
        self.mock_config_manager.get_all_project_configs.return_value = []
        self.service.initialize()

        project_id = "test-id"
        project = Project(
            id=project_id,
            name="test",
            path="/test",
            status=ProjectStatus.ACTIVE,
            last_accessed=datetime.now(),
        )
        self.service._projects_cache[project_id] = project
        self.mock_config_manager.update_project.return_value = True

        old_access_time = project.last_accessed
        result = self.service.update_project_access_time(project_id)

        assert result is True
        assert project.last_accessed > old_access_time
        self.mock_config_manager.update_project.assert_called_once()

    def test_get_project_health_status(self):
        """Test getting project health status."""
        # Mock config loading for initialization
        self.mock_config_manager.get_all_project_configs.return_value = []
        self.service.initialize()

        project_id = "test-id"
        project = Project(
            id=project_id,
            name="test",
            path="/test",
            status=ProjectStatus.ACTIVE,
            last_accessed=datetime.now(),
        )
        self.service._projects_cache[project_id] = project

        # Mock Git service methods
        self.mock_git_service.is_git_repository.return_value = True
        self.mock_git_service.get_branch_list.return_value = ["main", "develop"]
        self.mock_git_service.get_worktree_list.return_value = []
        self.mock_git_service.check_uncommitted_changes.return_value = False

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.is_dir", return_value=True),
            patch("pathlib.Path.stat") as mock_stat,
        ):
            mock_stat.return_value.st_mode = 0o755  # Readable directory

            health_status = self.service.get_project_health_status(project_id)

        assert health_status["project_id"] == project_id
        assert health_status["overall_status"] == "healthy"
        assert health_status["branch_count"] == 2
        assert health_status["worktree_count"] == 0
        assert len(health_status["issues"]) == 0


class TestProjectServiceIntegration:
    """Integration tests for ProjectService."""

    def test_real_project_operations(self):
        """Test project operations with real temporary directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a real Git repository
            repo_path = Path(temp_dir) / "test_repo"
            repo_path.mkdir()

            # Initialize Git repo
            import subprocess

            subprocess.run(
                ["git", "init"], cwd=repo_path, check=True, capture_output=True
            )
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

            # Create isolated config file for testing
            config_file = Path(temp_dir) / "test_config.json"

            # Test with real services but isolated configuration
            from wt_manager.services.config_manager import ConfigManager

            config_manager = ConfigManager(config_file=config_file)
            service = ProjectService(config_manager=config_manager)
            service.initialize()

            # Test validation
            validation_result = service.validate_project(str(repo_path))
            assert validation_result.is_valid

            # Test adding project
            project = service.add_project(str(repo_path))
            assert project.name == "test_repo"
            assert project.status == ProjectStatus.ACTIVE

            # Test getting projects
            projects = service.get_projects()
            assert len(projects) == 1
            assert projects[0] == project

            # Test health check
            health_status = service.get_project_health_status(project.id)
            assert health_status["overall_status"] == "healthy"

            # Test removing project
            result = service.remove_project(project.id)
            assert result is True
            assert len(service.get_projects()) == 0
