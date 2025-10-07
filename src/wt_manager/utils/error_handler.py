"""Centralized error handling system."""

import logging
import traceback
from collections.abc import Callable
from PyQt6.QtWidgets import QMessageBox, QWidget, QApplication
from PyQt6.QtCore import QObject, pyqtSignal

from .exceptions import (
    GitWorktreeManagerError,
    ErrorSeverity,
    GitError,
    ValidationError,
    ConfigurationError,
    FileSystemError,
    NetworkError,
)


class ErrorHandler(QObject):
    """Centralized error handler for the application."""

    # Signal emitted when an error occurs
    error_occurred = pyqtSignal(GitWorktreeManagerError)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.parent_widget = parent
        self.logger = logging.getLogger(__name__)

        # Error recovery callbacks
        self._recovery_callbacks: dict[type, Callable] = {}

    def register_recovery_callback(self, error_type: type, callback: Callable):
        """Register a recovery callback for a specific error type."""
        self._recovery_callbacks[error_type] = callback

    def handle_error(
        self,
        error: Exception,
        show_dialog: bool = True,
        log_error: bool = True,
        attempt_recovery: bool = True,
    ) -> bool:
        """
        Handle an error with comprehensive logging and user feedback.

        Args:
            error: The exception to handle
            show_dialog: Whether to show error dialog to user
            log_error: Whether to log the error
            attempt_recovery: Whether to attempt automatic recovery

        Returns:
            True if error was handled successfully, False otherwise
        """
        try:
            # Convert to GitWorktreeManagerError if needed
            if not isinstance(error, GitWorktreeManagerError):
                error = self._convert_to_app_error(error)

            # Log the error
            if log_error:
                self._log_error(error)

            # Emit signal for other components
            self.error_occurred.emit(error)

            # Attempt recovery if enabled
            recovery_successful = False
            if attempt_recovery:
                recovery_successful = self._attempt_recovery(error)

            # Show user dialog if requested and recovery wasn't successful
            if show_dialog and not recovery_successful:
                self._show_error_dialog(error)

            return True

        except Exception as handler_error:
            # Fallback error handling
            self.logger.critical(f"Error in error handler: {handler_error}")
            self._show_fallback_error_dialog(str(error))
            return False

    def _convert_to_app_error(self, error: Exception) -> GitWorktreeManagerError:
        """Convert a generic exception to a GitWorktreeManagerError."""
        error_message = str(error)

        # Try to categorize the error based on its type and message
        if isinstance(error, (OSError, IOError, FileNotFoundError, PermissionError)):
            return FileSystemError(
                error_message,
                user_message="A file system error occurred. Please check file permissions and disk space.",
                suggested_action="Verify that the file path exists and you have the necessary permissions.",
            )
        elif isinstance(error, ValueError):
            return ValidationError(
                error_message,
                user_message="Invalid input provided.",
                suggested_action="Please check your input and try again.",
            )
        elif "git" in error_message.lower():
            return GitError(
                error_message,
                user_message="A Git operation failed.",
                suggested_action="Please check that Git is installed and the repository is valid.",
            )
        else:
            return GitWorktreeManagerError(
                error_message,
                severity=ErrorSeverity.ERROR,
                user_message="An unexpected error occurred.",
                suggested_action="Please try again or contact support if the problem persists.",
            )

    def _log_error(self, error: GitWorktreeManagerError):
        """Log the error with appropriate level and details."""
        error_dict = error.to_dict()

        # Choose log level based on severity
        if error.severity == ErrorSeverity.CRITICAL:
            log_func = self.logger.critical
        elif error.severity == ErrorSeverity.ERROR:
            log_func = self.logger.error
        elif error.severity == ErrorSeverity.WARNING:
            log_func = self.logger.warning
        else:
            log_func = self.logger.info

        # Log with full details
        log_func(
            f"Error in {error.category.value}: {error.message}",
            extra={"error_details": error_dict, "traceback": traceback.format_exc()},
        )

    def _attempt_recovery(self, error: GitWorktreeManagerError) -> bool:
        """Attempt automatic recovery for the error."""
        error_type = type(error)

        # Check for registered recovery callback
        if error_type in self._recovery_callbacks:
            try:
                return self._recovery_callbacks[error_type](error)
            except Exception as recovery_error:
                self.logger.warning(f"Recovery callback failed: {recovery_error}")

        # Built-in recovery strategies
        if isinstance(error, ConfigurationError):
            return self._recover_configuration_error(error)
        elif isinstance(error, NetworkError):
            return self._recover_network_error(error)

        return False

    def _recover_configuration_error(self, error: ConfigurationError) -> bool:
        """Attempt to recover from configuration errors."""
        # For now, just log that recovery was attempted
        self.logger.info("Attempting configuration error recovery")
        return False

    def _recover_network_error(self, error: NetworkError) -> bool:
        """Attempt to recover from network errors."""
        # For now, just log that recovery was attempted
        self.logger.info("Attempting network error recovery")
        return False

    def _show_error_dialog(self, error: GitWorktreeManagerError):
        """Show user-friendly error dialog."""
        try:
            parent = self._get_parent_widget()
            msg_box = self._create_message_box(parent, error)
            self._configure_message_box_content(msg_box, error)
            msg_box.exec()
        except Exception as dialog_error:
            self.logger.error(f"Failed to show error dialog: {dialog_error}")
            self._show_fallback_error_dialog(error.user_message)

    def _get_parent_widget(self):
        """Get the parent widget for the dialog."""
        parent = self.parent_widget
        if not parent and QApplication.instance():
            parent = QApplication.instance().activeWindow()
        return parent

    def _create_message_box(
        self, parent, error: GitWorktreeManagerError
    ) -> QMessageBox:
        """Create and configure the basic message box."""
        msg_box = QMessageBox(parent)
        self._set_message_box_icon_and_title(msg_box, error.severity)
        return msg_box

    def _set_message_box_icon_and_title(
        self, msg_box: QMessageBox, severity: ErrorSeverity
    ):
        """Set the appropriate icon and title based on error severity."""
        severity_config = {
            ErrorSeverity.CRITICAL: (QMessageBox.Icon.Critical, "Critical Error"),
            ErrorSeverity.ERROR: (QMessageBox.Icon.Critical, "Error"),
            ErrorSeverity.WARNING: (QMessageBox.Icon.Warning, "Warning"),
        }

        icon, title = severity_config.get(
            severity, (QMessageBox.Icon.Information, "Information")
        )
        msg_box.setIcon(icon)
        msg_box.setWindowTitle(title)

    def _configure_message_box_content(
        self, msg_box: QMessageBox, error: GitWorktreeManagerError
    ):
        """Configure the message box content including details and error code."""
        msg_box.setText(error.user_message)

        details = self._build_error_details(error)
        if details:
            msg_box.setDetailedText("\n".join(details))

        if error.error_code:
            msg_box.setInformativeText(f"Error Code: {error.error_code}")

    def _build_error_details(self, error: GitWorktreeManagerError) -> list[str]:
        """Build the list of error details for display."""
        details = []

        if error.suggested_action:
            details.append(f"Suggested action: {error.suggested_action}")

        if error.details:
            for key, value in error.details.items():
                if value is not None:
                    details.append(f"{key.replace('_', ' ').title()}: {value}")

        return details

    def _show_fallback_error_dialog(self, message: str):
        """Show a simple fallback error dialog."""
        try:
            parent = self.parent_widget
            if not parent and QApplication.instance():
                parent = QApplication.instance().activeWindow()

            QMessageBox.critical(parent, "Error", f"An error occurred: {message}")
        except Exception:
            # Last resort - print to console
            print(f"CRITICAL ERROR: {message}")


# Global error handler instance
_global_error_handler: ErrorHandler | None = None


def get_error_handler() -> ErrorHandler:
    """Get the global error handler instance."""
    global _global_error_handler
    if _global_error_handler is None:
        _global_error_handler = ErrorHandler()
    return _global_error_handler


def set_error_handler(handler: ErrorHandler):
    """Set the global error handler instance."""
    global _global_error_handler
    _global_error_handler = handler


def handle_error(
    error: Exception,
    show_dialog: bool = True,
    log_error: bool = True,
    attempt_recovery: bool = True,
) -> bool:
    """Convenience function to handle errors using the global handler."""
    return get_error_handler().handle_error(
        error,
        show_dialog=show_dialog,
        log_error=log_error,
        attempt_recovery=attempt_recovery,
    )


def error_handler_decorator(
    show_dialog: bool = True,
    log_error: bool = True,
    attempt_recovery: bool = True,
    reraise: bool = False,
):
    """Decorator to automatically handle errors in functions."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                handled = handle_error(
                    e,
                    show_dialog=show_dialog,
                    log_error=log_error,
                    attempt_recovery=attempt_recovery,
                )
                if reraise or not handled:
                    raise
                return None

        return wrapper

    return decorator
