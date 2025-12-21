"""Project management service for Git Worktree Manager."""

import logging
import uuid
from datetime import datetime
from pathlib import Path

from ..models.project import Project, ProjectStatus
from ..utils.exceptions import ServiceError, ValidationError
from .base import ProjectServiceInterface, ValidationResult
from .config_manager import ConfigManager
from .git_service import GitService
from .validation_service import ValidationService

logger = logging.getLogger(__name__)


class ProjectService(ProjectServiceInterface):
    """
    Service for managing Git projects and their lifecycle.

    This service provides high-level operations for adding, removing, validating,
    and managing Git projects within the application.
    """

    def __init__(
        self,
        config_manager: ConfigManager | None = None,
        git_service: GitService | None = None,
        validation_service: ValidationService | None = None,
    ):
        """
        Initialize the project service.

        Args:
            config_manager: Configuration manager instance
            git_service: Git service instance
            validation_service: Validation service instance
        """
        super().__init__()
        self._config_manager = config_manager or ConfigManager()
        self._git_service = git_service or GitService()
        self._validation_service = validation_service or ValidationService()
        self._projects_cache: dict[str, Project] = {}

    def _do_initialize(self) -> None:
        """Initialize the project service and its dependencies."""
        try:
            # Initialize dependencies
            if not self._git_service.is_initialized():
                self._git_service.initialize()

            if not self._validation_service.is_initialized():
                self._validation_service.initialize()

            # Load existing projects from configuration
            self._load_projects_from_config()

            logger.info("Project service initialized successfully")

        except Exception as e:
            raise ServiceError(f"Failed to initialize project service: {e}")

    def add_project(self, path: str) -> Project:
        """
        Add a new project to the manager.

        Args:
            path: Filesystem path to the Git repository

        Returns:
            Project: The newly added project

        Raises:
            ValidationError: If the path is not a valid Git repository
            ServiceError: If the project cannot be added
        """
        try:
            # Validate the project path
            validation_result = self.validate_project(path)
            if not validation_result.is_valid:
                raise ValidationError(validation_result.message)

            # Normalize the path
            normalized_path = str(Path(path).resolve())

            # Check if project already exists
            existing_project = self._find_project_by_path(normalized_path)
            if existing_project:
                logger.info(f"Project already exists: {existing_project.name}")
                return existing_project

            # Create new project
            project = self._create_project(normalized_path)

            # Add to cache and configuration
            self._projects_cache[project.id] = project
            success = self._config_manager.add_project(project)

            if not success:
                # Remove from cache if config save failed
                del self._projects_cache[project.id]
                raise ServiceError("Failed to save project configuration")

            logger.info(f"Added new project: {project.name} at {project.path}")
            return project

        except (ValidationError, ServiceError):
            raise
        except Exception as e:
            raise ServiceError(f"Failed to add project: {e}")

    def remove_project(self, project_id: str) -> bool:
        """
        Remove a project from the manager.

        Args:
            project_id: Unique identifier of the project to remove

        Returns:
            bool: True if the project was successfully removed

        Raises:
            ServiceError: If the project cannot be removed
        """
        try:
            # Check if project exists
            if project_id not in self._projects_cache:
                logger.warning(f"Project not found for removal: {project_id}")
                return False

            project = self._projects_cache[project_id]

            # Remove from configuration
            success = self._config_manager.remove_project(project_id)
            if not success:
                raise ServiceError("Failed to remove project from configuration")

            # Remove from cache
            del self._projects_cache[project_id]

            logger.info(f"Removed project: {project.name}")
            return True

        except ServiceError:
            raise
        except Exception as e:
            raise ServiceError(f"Failed to remove project: {e}")

    def validate_project(self, path: str) -> ValidationResult:
        """
        Validate that a path contains a valid Git repository.

        Args:
            path: Path to validate

        Returns:
            ValidationResult: Validation result with details
        """
        try:
            # Use validation service to check if it's a Git repository
            return self._validation_service.validate_git_repository(path)

        except Exception as e:
            return ValidationResult(
                is_valid=False,
                message=f"Error validating project: {e}",
                details={"error_type": "validation_exception", "exception": str(e)},
            )

    def get_projects(self) -> list[Project]:
        """
        Get all managed projects.

        Returns:
            List[Project]: List of all projects
        """
        return list(self._projects_cache.values())

    def refresh_project(self, project_id: str) -> Project:
        """
        Refresh project information and status.

        Args:
            project_id: Unique identifier of the project to refresh

        Returns:
            Project: Refreshed project instance

        Raises:
            ServiceError: If the project cannot be refreshed
        """
        try:
            if project_id not in self._projects_cache:
                raise ServiceError(f"Project not found: {project_id}")

            project = self._projects_cache[project_id]

            # Update project status and information
            updated_project = self._refresh_project_status(project)

            # Update cache
            self._projects_cache[project_id] = updated_project

            # Update configuration with refreshed project
            success = self._config_manager.update_project(updated_project)
            if not success:
                logger.warning(
                    f"Failed to save refreshed project configuration: {project.name}"
                )

            logger.debug(f"Refreshed project: {updated_project.name}")
            return updated_project

        except ServiceError:
            raise
        except Exception as e:
            raise ServiceError(f"Failed to refresh project: {e}")

    def get_project_by_id(self, project_id: str) -> Project | None:
        """
        Get a project by its ID.

        Args:
            project_id: Unique identifier of the project

        Returns:
            Optional[Project]: Project if found, None otherwise
        """
        return self._projects_cache.get(project_id)

    def get_project_by_path(self, path: str) -> Project | None:
        """
        Get a project by its path.

        Args:
            path: Filesystem path to the project

        Returns:
            Optional[Project]: Project if found, None otherwise
        """
        normalized_path = str(Path(path).resolve())
        return self._find_project_by_path(normalized_path)

    def refresh_all_projects(self) -> list[Project]:
        """
        Refresh all projects and their status.

        Returns:
            List[Project]: List of all refreshed projects
        """
        refreshed_projects = []

        for project_id in list(self._projects_cache.keys()):
            try:
                refreshed_project = self.refresh_project(project_id)
                refreshed_projects.append(refreshed_project)
            except ServiceError as e:
                logger.error(f"Failed to refresh project {project_id}: {e}")
                # Keep the original project in case of refresh failure
                refreshed_projects.append(self._projects_cache[project_id])

        logger.info(f"Refreshed {len(refreshed_projects)} projects")
        return refreshed_projects

    def get_project_health_status(self, project_id: str) -> dict:
        """
        Get detailed health status for a project.

        Args:
            project_id: Unique identifier of the project

        Returns:
            Dict: Health status information

        Raises:
            ServiceError: If the project cannot be found or checked
        """
        try:
            if project_id not in self._projects_cache:
                raise ServiceError(f"Project not found: {project_id}")

            project = self._projects_cache[project_id]
            return self._check_project_health(project)

        except ServiceError:
            raise
        except Exception as e:
            raise ServiceError(f"Failed to get project health status: {e}")

    def update_project_access_time(self, project_id: str) -> bool:
        """
        Update the last accessed time for a project.

        Args:
            project_id: Unique identifier of the project

        Returns:
            bool: True if the access time was updated successfully
        """
        try:
            if project_id not in self._projects_cache:
                logger.warning(
                    f"Project not found for access time update: {project_id}"
                )
                return False

            project = self._projects_cache[project_id]
            project.last_accessed = datetime.now()

            # Update configuration
            success = self._config_manager.update_project(project)
            if success:
                logger.debug(f"Updated access time for project: {project.name}")

            return success

        except Exception as e:
            logger.error(f"Failed to update project access time: {e}")
            return False

    def _load_projects_from_config(self) -> None:
        """Load projects from configuration into cache."""
        try:
            project_configs = self._config_manager.get_all_project_configs()

            for project_config in project_configs:
                try:
                    project = Project(
                        id=project_config.id,
                        name=project_config.name,
                        path=project_config.path,
                        status=ProjectStatus.ACTIVE,  # Will be updated by refresh
                        last_accessed=project_config.last_accessed,
                    )

                    # Refresh project status
                    project = self._refresh_project_status(project)
                    self._projects_cache[project.id] = project

                except Exception as e:
                    logger.error(f"Failed to load project {project_config.name}: {e}")

            logger.info(
                f"Loaded {len(self._projects_cache)} projects from configuration"
            )

        except Exception as e:
            logger.error(f"Failed to load projects from configuration: {e}")

    def _create_project(self, path: str) -> Project:
        """Create a new project instance."""
        path_obj = Path(path)
        project_name = path_obj.name

        return Project(
            id=str(uuid.uuid4()),
            name=project_name,
            path=path,
            status=ProjectStatus.ACTIVE,
            last_accessed=datetime.now(),
        )

    def _find_project_by_path(self, path: str) -> Project | None:
        """Find a project by its normalized path."""
        for project in self._projects_cache.values():
            if project.path == path:
                return project
        return None

    def _refresh_project_status(self, project: Project) -> Project:
        """Refresh the status of a project."""
        try:
            # Check if project path still exists and is valid
            if not project.is_valid():
                if not Path(project.path).exists():
                    project.status = ProjectStatus.UNAVAILABLE
                else:
                    project.status = ProjectStatus.ERROR
            else:
                if self._git_service.check_uncommitted_changes(project.path):
                    project.status = ProjectStatus.MODIFIED
                else:
                    project.status = ProjectStatus.ACTIVE

            return project

        except Exception as e:
            logger.error(f"Error refreshing project status for {project.name}: {e}")
            project.status = ProjectStatus.ERROR
            return project

    def _check_project_health(self, project: Project) -> dict:
        """Check the health status of a project."""
        health_info = {
            "project_id": project.id,
            "project_name": project.name,
            "project_path": project.path,
            "status": project.status.value,
            "issues": [],
            "warnings": [],
            "last_checked": datetime.now().isoformat(),
        }

        try:
            # Check if path exists
            path_obj = Path(project.path)
            if not path_obj.exists():
                health_info["issues"].append("Project path does not exist")
                return health_info

            # Check if it's still a Git repository
            if not self._git_service.is_git_repository(project.path):
                health_info["issues"].append("Path is no longer a Git repository")
                return health_info

            # Check Git repository health
            try:
                # Try to get repository information
                branches = self._git_service.get_branch_list(project.path)
                health_info["branch_count"] = len(branches)

                # Check for worktrees
                worktrees = self._git_service.get_worktree_list(project.path)
                health_info["worktree_count"] = len(worktrees)

                # Check for uncommitted changes in main repository
                has_changes = self._git_service.check_uncommitted_changes(project.path)
                if has_changes:
                    health_info["warnings"].append("Repository has uncommitted changes")

            except Exception as e:
                health_info["warnings"].append(f"Git operations failed: {e}")

            # Check directory permissions
            if not path_obj.is_dir():
                health_info["issues"].append("Project path is not a directory")
            elif not path_obj.stat().st_mode & 0o400:  # Check read permission
                health_info["warnings"].append("Project directory may not be readable")

        except Exception as e:
            health_info["issues"].append(f"Health check failed: {e}")

        # Determine overall health status
        if health_info["issues"]:
            health_info["overall_status"] = "unhealthy"
        elif health_info["warnings"]:
            health_info["overall_status"] = "warning"
        else:
            health_info["overall_status"] = "healthy"

        return health_info

    def __str__(self) -> str:
        """String representation of the project service."""
        return f"ProjectService(projects={len(self._projects_cache)})"

    def __repr__(self) -> str:
        """Detailed string representation of the project service."""
        return (
            f"ProjectService(projects={len(self._projects_cache)}, "
            f"initialized={self.is_initialized()})"
        )
