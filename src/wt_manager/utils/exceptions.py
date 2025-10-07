"""Custom exceptions for the application."""


class GitWorktreeManagerError(Exception):
    """Base exception for Git Worktree Manager."""

    pass


class GitError(GitWorktreeManagerError):
    """Exception for Git-related errors."""

    pass


class ValidationError(GitWorktreeManagerError):
    """Exception for validation errors."""

    pass


class ConfigurationError(GitWorktreeManagerError):
    """Exception for configuration-related errors."""

    pass


class FileSystemError(GitWorktreeManagerError):
    """Exception for file system-related errors."""

    pass


class CommandExecutionError(GitWorktreeManagerError):
    """Exception for command execution errors."""

    pass


class ServiceError(GitWorktreeManagerError):
    """Exception for service layer errors."""

    pass


class PathError(GitWorktreeManagerError):
    """Exception for path-related errors."""

    pass
