"""Base interfaces and abstract classes for services."""

from abc import ABC, abstractmethod
from typing import Any


class ValidationResult:
    """Result of a validation operation."""

    def __init__(
        self, is_valid: bool, message: str = "", details: dict[str, Any] | None = None
    ):
        self.is_valid = is_valid
        self.message = message
        self.details = details or {}


class CommandResult:
    """Result of a command execution."""

    def __init__(
        self, success: bool, output: str = "", error: str = "", exit_code: int = 0
    ):
        self.success = success
        self.output = output
        self.error = error
        self.exit_code = exit_code


class ServiceError(Exception):
    """Base exception for service layer errors."""

    pass


class BaseService(ABC):
    """Base class for all services."""

    def __init__(self):
        self._initialized = False

    def initialize(self) -> None:
        """Initialize the service."""
        if not self._initialized:
            self._do_initialize()
            self._initialized = True

    @abstractmethod
    def _do_initialize(self) -> None:
        """Perform service-specific initialization."""
        pass

    def is_initialized(self) -> bool:
        """Check if the service is initialized."""
        return self._initialized


class ProjectServiceInterface(BaseService):
    """Interface for project management operations."""

    @abstractmethod
    def add_project(self, path: str) -> Any:
        """Add a new project."""
        pass

    @abstractmethod
    def remove_project(self, project_id: str) -> bool:
        """Remove a project."""
        pass

    @abstractmethod
    def validate_project(self, path: str) -> ValidationResult:
        """Validate a project path."""
        pass

    @abstractmethod
    def get_projects(self) -> list[Any]:
        """Get all projects."""
        pass

    @abstractmethod
    def refresh_project(self, project_id: str) -> Any:
        """Refresh project information."""
        pass


class WorktreeServiceInterface(BaseService):
    """Interface for worktree management operations."""

    @abstractmethod
    def get_worktrees(self, project: Any) -> list[Any]:
        """Get worktrees for a project."""
        pass

    @abstractmethod
    def create_worktree(self, project: Any, path: str, branch: str) -> Any:
        """Create a new worktree."""
        pass

    @abstractmethod
    def remove_worktree(self, worktree: Any, force: bool = False) -> bool:
        """Remove a worktree."""
        pass

    @abstractmethod
    def validate_worktree_creation(self, path: str, branch: str) -> ValidationResult:
        """Validate worktree creation parameters."""
        pass


class GitServiceInterface(BaseService):
    """Interface for Git operations."""

    @abstractmethod
    def execute_command(self, command: list[str], cwd: str) -> CommandResult:
        """Execute a Git command."""
        pass

    @abstractmethod
    def get_worktree_list(self, repo_path: str) -> list[dict]:
        """Get list of worktrees."""
        pass

    @abstractmethod
    def create_worktree(
        self, repo_path: str, worktree_path: str, branch: str
    ) -> CommandResult:
        """Create a worktree."""
        pass

    @abstractmethod
    def remove_worktree(self, worktree_path: str, force: bool = False) -> CommandResult:
        """Remove a worktree."""
        pass

    @abstractmethod
    def fetch_remote(self, repo_path: str) -> CommandResult:
        """Fetch from remote."""
        pass

    @abstractmethod
    def get_branch_list(self, repo_path: str) -> list[str]:
        """Get list of branches."""
        pass


class CommandServiceInterface(BaseService):
    """Interface for command execution operations."""

    @abstractmethod
    def execute_command(self, command: str, worktree_path: str) -> Any:
        """Execute a command in a worktree."""
        pass

    @abstractmethod
    def get_command_history(self, worktree_path: str) -> list[Any]:
        """Get command history for a worktree."""
        pass

    @abstractmethod
    def cancel_command(self, execution_id: str) -> bool:
        """Cancel a running command."""
        pass

    @abstractmethod
    def validate_command(self, command: str) -> ValidationResult:
        """Validate a command for safety."""
        pass


class ValidationServiceInterface(BaseService):
    """Interface for validation operations."""

    @abstractmethod
    def validate_git_repository(self, path: str) -> ValidationResult:
        """Validate if path is a Git repository."""
        pass

    @abstractmethod
    def validate_worktree_path(self, path: str) -> ValidationResult:
        """Validate worktree path."""
        pass

    @abstractmethod
    def validate_branch_name(self, branch: str) -> ValidationResult:
        """Validate branch name."""
        pass

    @abstractmethod
    def check_uncommitted_changes(self, worktree_path: str) -> ValidationResult:
        """Check for uncommitted changes."""
        pass

    @abstractmethod
    def validate_command_safety(self, command: str) -> ValidationResult:
        """Validate command safety."""
        pass
