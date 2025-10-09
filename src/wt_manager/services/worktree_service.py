"""Worktree management service for Git Worktree Manager."""

import logging
from datetime import datetime
from pathlib import Path

from ..models.project import Project
from ..models.worktree import Worktree
from ..utils.exceptions import GitError, ServiceError, ValidationError
from .base import ValidationResult, WorktreeServiceInterface
from .git_service import GitService
from .validation_service import ValidationService

logger = logging.getLogger(__name__)


class WorktreeService(WorktreeServiceInterface):
    """
    Service for managing Git worktrees and their operations.

    This service provides high-level operations for creating, removing, listing,
    and managing Git worktrees within projects.
    """

    def __init__(
        self,
        git_service: GitService | None = None,
        validation_service: ValidationService | None = None,
    ):
        """
        Initialize the worktree service.

        Args:
            git_service: Git service instance
            validation_service: Validation service instance
        """
        super().__init__()
        self._git_service = git_service or GitService()
        self._validation_service = validation_service or ValidationService()

    def _do_initialize(self) -> None:
        """Initialize the worktree service and its dependencies."""
        try:
            # Initialize dependencies
            if not self._git_service.is_initialized():
                self._git_service.initialize()

            if not self._validation_service.is_initialized():
                self._validation_service.initialize()

            logger.info("Worktree service initialized successfully")

        except Exception as e:
            raise ServiceError(f"Failed to initialize worktree service: {e}")

    def get_worktrees(self, project: Project) -> list[Worktree]:
        """
        Get all worktrees for a project.

        Args:
            project: Project to get worktrees for

        Returns:
            List[Worktree]: List of worktrees for the project

        Raises:
            ServiceError: If worktrees cannot be retrieved
        """
        try:
            if not project or not project.path:
                raise ServiceError("Invalid project provided")

            # Get worktree list from Git
            worktree_data = self._git_service.get_worktree_list(project.path)

            # Convert to Worktree objects
            worktrees = []
            for wt_data in worktree_data:
                try:
                    worktree = self._create_worktree_from_git_data(wt_data)
                    worktrees.append(worktree)
                except Exception as e:
                    logger.warning(
                        f"Failed to create worktree from data {wt_data}: {e}"
                    )

            # Update project's worktree list
            project.worktrees = worktrees

            logger.debug(
                f"Retrieved {len(worktrees)} worktrees for project {project.name}"
            )
            return worktrees

        except GitError:
            raise
        except Exception as e:
            project_name = project.name if project else "unknown"
            raise ServiceError(
                f"Failed to get worktrees for project {project_name}: {e}"
            )

    def create_worktree(
        self,
        project: Project,
        path: str,
        branch: str,
        auto_create_branch: bool = False,
        base_branch: str = "main",
    ) -> Worktree:
        """
        Create a new worktree for a project.

        Args:
            project: Project to create worktree for
            path: Path where the worktree should be created
            branch: Branch name for the worktree
            auto_create_branch: Whether to create the branch if it doesn't exist
            base_branch: Base branch to create the new branch from

        Returns:
            Worktree: The newly created worktree

        Raises:
            ValidationError: If the creation parameters are invalid
            ServiceError: If the worktree cannot be created
        """
        try:
            # Validate creation parameters
            validation_result = self.validate_worktree_creation(project, path, branch)
            if not validation_result.is_valid:
                raise ValidationError(validation_result.message)

            # Normalize the path
            normalized_path = str(Path(path).resolve())

            # Check if worktree already exists at this path
            existing_worktree = self._find_worktree_by_path(project, normalized_path)
            if existing_worktree:
                raise ServiceError(
                    f"Worktree already exists at path: {normalized_path}"
                )

            # Fetch remote changes if needed
            try:
                self._git_service.fetch_remote(project.path)
                logger.debug(f"Fetched remote changes for project {project.name}")
            except GitError as e:
                logger.warning(f"Failed to fetch remote changes: {e}")
                # Continue with worktree creation even if fetch fails

            # Create the worktree using Git service
            result = self._git_service.create_worktree(
                project.path, normalized_path, branch, auto_create_branch, base_branch
            )
            if not result.success:
                raise ServiceError(f"Failed to create worktree: {result.error}")

            # Create Worktree object
            worktree = Worktree(
                path=normalized_path,
                branch=branch,
                commit_hash="",  # Will be updated by refresh
                is_bare=False,
                is_detached=False,
                has_uncommitted_changes=False,
                last_modified=datetime.now(),
            )

            # Refresh worktree information from Git
            worktree = self._refresh_worktree_info(worktree)

            # Add to project
            project.add_worktree(worktree)

            logger.info(f"Created worktree at {normalized_path} for branch {branch}")
            return worktree

        except (ValidationError, ServiceError, GitError):
            raise
        except Exception as e:
            raise ServiceError(f"Failed to create worktree: {e}")

    def remove_worktree(self, worktree: Worktree, force: bool = False) -> bool:
        """
        Remove a worktree.

        Args:
            worktree: Worktree to remove
            force: Whether to force removal even with uncommitted changes

        Returns:
            bool: True if the worktree was successfully removed

        Raises:
            ServiceError: If the worktree cannot be removed
        """
        try:
            if not worktree or not worktree.path:
                raise ServiceError("Invalid worktree provided")

            # Check for uncommitted changes if not forcing
            if not force:
                changes_result = self._validation_service.check_uncommitted_changes(
                    worktree.path
                )
                if changes_result.is_valid and changes_result.details.get(
                    "has_uncommitted_changes"
                ):
                    raise ServiceError(
                        f"Worktree has uncommitted changes: {worktree.path}. "
                        "Use force=True to remove anyway."
                    )

            # Check if worktree is current directory
            if worktree.is_current_directory():
                raise ServiceError(
                    f"Cannot remove worktree that is the current working directory: {worktree.path}"
                )

            # Remove the worktree using Git service
            result = self._git_service.remove_worktree(worktree.path, force)
            if not result.success:
                raise ServiceError(f"Failed to remove worktree: {result.error}")

            logger.info(f"Removed worktree at {worktree.path}")
            return True

        except ServiceError:
            raise
        except Exception as e:
            raise ServiceError(f"Failed to remove worktree: {e}")

    def validate_worktree_creation(
        self, project: Project, path: str, branch: str
    ) -> ValidationResult:
        """
        Validate parameters for worktree creation.

        Args:
            project: Project to create worktree for
            path: Path where worktree should be created
            branch: Branch name for the worktree

        Returns:
            ValidationResult: Validation result with details
        """
        try:
            # Validate path
            path_result = self._validation_service.validate_worktree_path(path)
            if not path_result.is_valid:
                return path_result

            # Validate branch name
            branch_result = self._validation_service.validate_branch_name(branch)
            if not branch_result.is_valid:
                return branch_result

            # Check if branch is already in use by another worktree
            branch_usage_result = self._validation_service.validate_branch_not_in_use(
                branch, project.path, self._git_service
            )
            if not branch_usage_result.is_valid:
                return branch_usage_result

            return ValidationResult(
                is_valid=True,
                message="Worktree creation parameters are valid",
                details={"path": path, "branch": branch},
            )

        except Exception as e:
            return ValidationResult(
                is_valid=False,
                message=f"Error validating worktree creation: {e}",
                details={"error_type": "validation_exception", "exception": str(e)},
            )

    def refresh_worktree(self, worktree: Worktree) -> Worktree:
        """
        Refresh worktree information from Git.

        Args:
            worktree: Worktree to refresh

        Returns:
            Worktree: Refreshed worktree instance

        Raises:
            ServiceError: If the worktree cannot be refreshed
        """
        try:
            return self._refresh_worktree_info(worktree)

        except Exception as e:
            raise ServiceError(f"Failed to refresh worktree: {e}")

    def refresh_worktrees(self, project: Project) -> list[Worktree]:
        """
        Refresh all worktrees for a project.

        Args:
            project: Project to refresh worktrees for

        Returns:
            List[Worktree]: List of refreshed worktrees
        """
        try:
            return self.get_worktrees(project)

        except Exception as e:
            raise ServiceError(
                f"Failed to refresh worktrees for project {project.name}: {e}"
            )

    def get_worktree_status(self, worktree: Worktree) -> dict:
        """
        Get detailed status information for a worktree.

        Args:
            worktree: Worktree to get status for

        Returns:
            Dict: Status information

        Raises:
            ServiceError: If status cannot be retrieved
        """
        try:
            status_info = {
                "path": worktree.path,
                "branch": worktree.branch,
                "commit_hash": worktree.commit_hash,
                "is_bare": worktree.is_bare,
                "is_detached": worktree.is_detached,
                "has_uncommitted_changes": worktree.has_uncommitted_changes,
                "last_modified": worktree.last_modified.isoformat()
                if worktree.last_modified
                else None,
                "exists": worktree.exists(),
                "accessible": worktree.is_accessible(),
                "is_current_directory": worktree.is_current_directory(),
                "status_display": worktree.get_status_display(),
                "branch_display": worktree.get_branch_display(),
                "age_display": worktree.get_age_display(),
            }

            # Get additional Git information if accessible
            if worktree.is_accessible():
                try:
                    # Get current branch
                    current_branch = self._git_service.get_current_branch(worktree.path)
                    status_info["current_branch"] = current_branch

                    # Check for uncommitted changes
                    has_changes = self._git_service.check_uncommitted_changes(
                        worktree.path
                    )
                    status_info["has_uncommitted_changes"] = has_changes

                except GitError as e:
                    status_info["git_error"] = str(e)

            return status_info

        except Exception as e:
            raise ServiceError(f"Failed to get worktree status: {e}")

    def find_worktree_by_path(self, project: Project, path: str) -> Worktree | None:
        """
        Find a worktree by its path within a project.

        Args:
            project: Project to search in
            path: Path to search for

        Returns:
            Optional[Worktree]: Worktree if found, None otherwise
        """
        normalized_path = str(Path(path).resolve())
        return self._find_worktree_by_path(project, normalized_path)

    def get_available_branches(self, project: Project) -> list[str]:
        """
        Get available branches for worktree creation.

        Args:
            project: Project to get branches for

        Returns:
            List[str]: List of available branch names

        Raises:
            ServiceError: If branches cannot be retrieved
        """
        try:
            branches = self._git_service.get_branch_list(project.path)
            logger.debug(
                f"Retrieved {len(branches)} branches for project {project.name}"
            )
            return branches

        except GitError:
            raise
        except Exception as e:
            raise ServiceError(f"Failed to get available branches: {e}")

    def _create_worktree_from_git_data(self, git_data: dict) -> Worktree:
        """Create a Worktree object from Git worktree list data."""
        worktree = Worktree(
            path=git_data.get("path", ""),
            branch=git_data.get("branch", "HEAD"),
            commit_hash=git_data.get("commit_hash", ""),
            is_bare=git_data.get("is_bare", False),
            is_detached=git_data.get("is_detached", False),
            has_uncommitted_changes=False,  # Will be updated by refresh
            last_modified=datetime.now(),
        )

        # Refresh additional information
        return self._refresh_worktree_info(worktree)

    def _refresh_worktree_info(self, worktree: Worktree) -> Worktree:
        """Refresh worktree information from Git."""
        try:
            if not worktree.exists():
                logger.warning(f"Worktree path does not exist: {worktree.path}")
                return worktree

            self._update_commit_hash(worktree)
            self._update_uncommitted_changes(worktree)
            self._update_last_modified(worktree)

            return worktree

        except Exception as e:
            logger.warning(f"Failed to refresh worktree info for {worktree.path}: {e}")
            return worktree

    def _update_commit_hash(self, worktree: Worktree) -> None:
        """Update commit hash if not set."""
        if worktree.commit_hash:
            return

        try:
            current_branch = self._git_service.get_current_branch(worktree.path)
            if current_branch.startswith("(") and current_branch.endswith(")"):
                # Detached HEAD, extract commit hash
                worktree.commit_hash = current_branch[1:-1]
                worktree.is_detached = True
            else:
                # Get commit hash for the branch
                result = self._git_service.execute_command(
                    ["rev-parse", "HEAD"], worktree.path
                )
                if result.success:
                    worktree.commit_hash = result.output.strip()
        except GitError:
            pass  # Keep existing values

    def _update_uncommitted_changes(self, worktree: Worktree) -> None:
        """Check for uncommitted changes."""
        try:
            worktree.has_uncommitted_changes = (
                self._git_service.check_uncommitted_changes(worktree.path)
            )
        except GitError:
            pass  # Keep existing value

    def _update_last_modified(self, worktree: Worktree) -> None:
        """Update last modified time based on filesystem."""
        try:
            path_obj = Path(worktree.path)
            if path_obj.exists():
                stat = path_obj.stat()
                worktree.last_modified = datetime.fromtimestamp(stat.st_mtime)
        except OSError:
            pass  # Keep existing value

    def _find_worktree_by_path(self, project: Project, path: str) -> Worktree | None:
        """Find a worktree by its path within a project."""
        for worktree in project.worktrees:
            if worktree.path == path:
                return worktree
        return None

    def __str__(self) -> str:
        """String representation of the worktree service."""
        return "WorktreeService()"

    def __repr__(self) -> str:
        """Detailed string representation of the worktree service."""
        return f"WorktreeService(initialized={self.is_initialized()})"
