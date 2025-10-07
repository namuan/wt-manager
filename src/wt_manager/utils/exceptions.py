"""Custom exceptions for the application."""

from typing import Any
from enum import Enum


class ErrorSeverity(Enum):
    """Error severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for better classification."""

    GIT_OPERATION = "git_operation"
    FILE_SYSTEM = "file_system"
    VALIDATION = "validation"
    CONFIGURATION = "configuration"
    COMMAND_EXECUTION = "command_execution"
    SERVICE = "service"
    UI = "ui"
    NETWORK = "network"


class GitWorktreeManagerError(Exception):
    """Base exception for Git Worktree Manager."""

    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.SERVICE,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        details: dict[str, Any] | None = None,
        user_message: str | None = None,
        suggested_action: str | None = None,
        error_code: str | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.category = category
        self.severity = severity
        self.details = details or {}
        self.user_message = user_message or message
        self.suggested_action = suggested_action
        self.error_code = error_code

    def to_dict(self) -> dict[str, Any]:
        """Convert error to dictionary for logging."""
        return {
            "message": self.message,
            "category": self.category.value,
            "severity": self.severity.value,
            "details": self.details,
            "user_message": self.user_message,
            "suggested_action": self.suggested_action,
            "error_code": self.error_code,
            "type": self.__class__.__name__,
        }


class GitError(GitWorktreeManagerError):
    """Exception for Git-related errors."""

    def __init__(
        self,
        message: str,
        command: str | None = None,
        exit_code: int | None = None,
        stderr: str | None = None,
        **kwargs,
    ):
        super().__init__(message, category=ErrorCategory.GIT_OPERATION, **kwargs)
        self.command = command
        self.exit_code = exit_code
        self.stderr = stderr
        if command:
            self.details.update(
                {"command": command, "exit_code": exit_code, "stderr": stderr}
            )


class ValidationError(GitWorktreeManagerError):
    """Exception for validation errors."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: Any | None = None,
        **kwargs,
    ):
        super().__init__(
            message,
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.WARNING,
            **kwargs,
        )
        self.field = field
        self.value = value
        if field:
            self.details.update(
                {"field": field, "value": str(value) if value is not None else None}
            )


class ConfigurationError(GitWorktreeManagerError):
    """Exception for configuration-related errors."""

    def __init__(self, message: str, config_file: str | None = None, **kwargs):
        super().__init__(message, category=ErrorCategory.CONFIGURATION, **kwargs)
        self.config_file = config_file
        if config_file:
            self.details.update({"config_file": config_file})


class FileSystemError(GitWorktreeManagerError):
    """Exception for file system-related errors."""

    def __init__(
        self,
        message: str,
        path: str | None = None,
        operation: str | None = None,
        **kwargs,
    ):
        super().__init__(message, category=ErrorCategory.FILE_SYSTEM, **kwargs)
        self.path = path
        self.operation = operation
        if path:
            self.details.update({"path": path, "operation": operation})


class CommandExecutionError(GitWorktreeManagerError):
    """Exception for command execution errors."""

    def __init__(
        self,
        message: str,
        command: str | None = None,
        exit_code: int | None = None,
        stdout: str | None = None,
        stderr: str | None = None,
        **kwargs,
    ):
        super().__init__(message, category=ErrorCategory.COMMAND_EXECUTION, **kwargs)
        self.command = command
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        if command:
            self.details.update(
                {
                    "command": command,
                    "exit_code": exit_code,
                    "stdout": stdout,
                    "stderr": stderr,
                }
            )


class ServiceError(GitWorktreeManagerError):
    """Exception for service layer errors."""

    def __init__(
        self,
        message: str,
        service: str | None = None,
        operation: str | None = None,
        **kwargs,
    ):
        super().__init__(message, category=ErrorCategory.SERVICE, **kwargs)
        self.service = service
        self.operation = operation
        if service:
            self.details.update({"service": service, "operation": operation})


class PathError(GitWorktreeManagerError):
    """Exception for path-related errors."""

    def __init__(self, message: str, path: str | None = None, **kwargs):
        super().__init__(message, category=ErrorCategory.FILE_SYSTEM, **kwargs)
        self.path = path
        if path:
            self.details.update({"path": path})


class NetworkError(GitWorktreeManagerError):
    """Exception for network-related errors."""

    def __init__(self, message: str, url: str | None = None, **kwargs):
        super().__init__(message, category=ErrorCategory.NETWORK, **kwargs)
        self.url = url
        if url:
            self.details.update({"url": url})


class UIError(GitWorktreeManagerError):
    """Exception for UI-related errors."""

    def __init__(self, message: str, component: str | None = None, **kwargs):
        super().__init__(message, category=ErrorCategory.UI, **kwargs)
        self.component = component
        if component:
            self.details.update({"component": component})
