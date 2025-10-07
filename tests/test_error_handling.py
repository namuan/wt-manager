"""Tests for error handling system."""

import pytest
from unittest.mock import Mock, patch
from PyQt6.QtWidgets import QWidget

from wt_manager.utils.exceptions import (
    GitWorktreeManagerError,
    ErrorSeverity,
    ErrorCategory,
    GitError,
    ValidationError,
    FileSystemError,
    CommandExecutionError,
)
from wt_manager.utils.error_handler import (
    ErrorHandler,
    get_error_handler,
    set_error_handler,
    handle_error,
    error_handler_decorator,
)


class TestGitWorktreeManagerError:
    """Test the base error class."""

    def test_basic_error_creation(self):
        """Test creating a basic error."""
        error = GitWorktreeManagerError(
            "Test error", category=ErrorCategory.SERVICE, severity=ErrorSeverity.ERROR
        )

        assert error.message == "Test error"
        assert error.category == ErrorCategory.SERVICE
        assert error.severity == ErrorSeverity.ERROR
        assert error.user_message == "Test error"
        assert error.suggested_action is None
        assert error.error_code is None

    def test_error_with_details(self):
        """Test creating error with additional details."""
        details = {"file": "test.py", "line": 42}
        error = GitWorktreeManagerError(
            "Test error",
            details=details,
            user_message="User-friendly message",
            suggested_action="Try again",
            error_code="E001",
        )

        assert error.details == details
        assert error.user_message == "User-friendly message"
        assert error.suggested_action == "Try again"
        assert error.error_code == "E001"

    def test_error_to_dict(self):
        """Test converting error to dictionary."""
        error = GitWorktreeManagerError(
            "Test error",
            category=ErrorCategory.GIT_OPERATION,
            severity=ErrorSeverity.WARNING,
            details={"command": "git status"},
            user_message="Git command failed",
            suggested_action="Check repository",
            error_code="G001",
        )

        error_dict = error.to_dict()

        assert error_dict["message"] == "Test error"
        assert error_dict["category"] == "git_operation"
        assert error_dict["severity"] == "warning"
        assert error_dict["details"] == {"command": "git status"}
        assert error_dict["user_message"] == "Git command failed"
        assert error_dict["suggested_action"] == "Check repository"
        assert error_dict["error_code"] == "G001"
        assert error_dict["type"] == "GitWorktreeManagerError"


class TestSpecificErrors:
    """Test specific error types."""

    def test_git_error(self):
        """Test GitError with command details."""
        error = GitError(
            "Git command failed",
            command="git clone repo",
            exit_code=128,
            stderr="Repository not found",
        )

        assert error.category == ErrorCategory.GIT_OPERATION
        assert error.command == "git clone repo"
        assert error.exit_code == 128
        assert error.stderr == "Repository not found"
        assert "command" in error.details
        assert "exit_code" in error.details
        assert "stderr" in error.details

    def test_validation_error(self):
        """Test ValidationError with field details."""
        error = ValidationError("Invalid input", field="email", value="invalid-email")

        assert error.category == ErrorCategory.VALIDATION
        assert error.severity == ErrorSeverity.WARNING
        assert error.field == "email"
        assert error.value == "invalid-email"
        assert "field" in error.details
        assert "value" in error.details

    def test_file_system_error(self):
        """Test FileSystemError with path details."""
        error = FileSystemError(
            "Permission denied", path="/restricted/path", operation="write"
        )

        assert error.category == ErrorCategory.FILE_SYSTEM
        assert error.path == "/restricted/path"
        assert error.operation == "write"
        assert "path" in error.details
        assert "operation" in error.details

    def test_command_execution_error(self):
        """Test CommandExecutionError with execution details."""
        error = CommandExecutionError(
            "Command failed",
            command="npm test",
            exit_code=1,
            stdout="Running tests...",
            stderr="Test failed",
        )

        assert error.category == ErrorCategory.COMMAND_EXECUTION
        assert error.command == "npm test"
        assert error.exit_code == 1
        assert error.stdout == "Running tests..."
        assert error.stderr == "Test failed"


@pytest.fixture
def error_handler(qtbot):
    """Create an error handler for testing."""
    parent = QWidget()
    qtbot.addWidget(parent)
    handler = ErrorHandler(parent)
    return handler


class TestErrorHandler:
    """Test the ErrorHandler class."""

    def test_error_handler_creation(self, error_handler):
        """Test creating an error handler."""
        assert error_handler.parent_widget is not None
        assert error_handler.logger is not None

    def test_handle_app_error(self, error_handler, qtbot):
        """Test handling a GitWorktreeManagerError."""
        error = GitWorktreeManagerError(
            "Test error", user_message="User message", suggested_action="Try again"
        )

        with patch.object(error_handler, "_show_error_dialog") as mock_dialog:
            result = error_handler.handle_error(error, show_dialog=True)

            assert result is True
            mock_dialog.assert_called_once_with(error)

    def test_handle_generic_error(self, error_handler):
        """Test handling a generic Python exception."""
        error = ValueError("Invalid value")

        with patch.object(error_handler, "_show_error_dialog") as mock_dialog:
            result = error_handler.handle_error(error, show_dialog=True)

            assert result is True
            # Should convert to ValidationError
            mock_dialog.assert_called_once()
            called_error = mock_dialog.call_args[0][0]
            assert isinstance(called_error, ValidationError)

    def test_handle_file_system_error(self, error_handler):
        """Test handling file system errors."""
        error = FileNotFoundError("File not found")

        with patch.object(error_handler, "_show_error_dialog") as mock_dialog:
            error_handler.handle_error(error, show_dialog=True)

            called_error = mock_dialog.call_args[0][0]
            assert isinstance(called_error, FileSystemError)

    def test_error_logging(self, error_handler):
        """Test that errors are properly logged."""
        error = GitWorktreeManagerError("Test error", severity=ErrorSeverity.ERROR)

        with patch.object(error_handler.logger, "error") as mock_log:
            error_handler.handle_error(error, log_error=True, show_dialog=False)

            mock_log.assert_called_once()

    def test_error_signal_emission(self, error_handler, qtbot):
        """Test that error signal is emitted."""
        error = GitWorktreeManagerError("Test error")

        with qtbot.waitSignal(error_handler.error_occurred, timeout=1000):
            error_handler.handle_error(error, show_dialog=False)

    def test_recovery_callback_registration(self, error_handler):
        """Test registering and using recovery callbacks."""
        callback = Mock(return_value=True)
        error_handler.register_recovery_callback(ValidationError, callback)

        error = ValidationError("Test validation error")

        with patch.object(error_handler, "_show_error_dialog"):
            result = error_handler.handle_error(error, attempt_recovery=True)

            assert result is True
            callback.assert_called_once_with(error)

    def test_no_dialog_on_successful_recovery(self, error_handler):
        """Test that dialog is not shown if recovery is successful."""
        callback = Mock(return_value=True)  # Successful recovery
        error_handler.register_recovery_callback(ValidationError, callback)

        error = ValidationError("Test validation error")

        with patch.object(error_handler, "_show_error_dialog") as mock_dialog:
            error_handler.handle_error(error, show_dialog=True, attempt_recovery=True)

            # Dialog should not be shown because recovery was successful
            mock_dialog.assert_not_called()


class TestGlobalErrorHandler:
    """Test global error handler functions."""

    def test_get_global_handler(self):
        """Test getting global error handler."""
        handler1 = get_error_handler()
        handler2 = get_error_handler()

        assert handler1 is handler2  # Should be same instance

    def test_set_global_handler(self):
        """Test setting global error handler."""
        custom_handler = ErrorHandler()
        set_error_handler(custom_handler)

        retrieved_handler = get_error_handler()
        assert retrieved_handler is custom_handler

    def test_global_handle_error_function(self):
        """Test global handle_error function."""
        error = GitWorktreeManagerError("Test error")

        with patch.object(get_error_handler(), "handle_error") as mock_handle:
            mock_handle.return_value = True

            result = handle_error(error, show_dialog=False)

            assert result is True
            mock_handle.assert_called_once_with(
                error, show_dialog=False, log_error=True, attempt_recovery=True
            )


class TestErrorHandlerDecorator:
    """Test the error handler decorator."""

    def test_decorator_success(self):
        """Test decorator with successful function."""

        @error_handler_decorator(show_dialog=False, log_error=False)
        def successful_function():
            return "success"

        result = successful_function()
        assert result == "success"

    def test_decorator_with_exception(self):
        """Test decorator with function that raises exception."""

        @error_handler_decorator(show_dialog=False, log_error=False, reraise=False)
        def failing_function():
            raise ValueError("Test error")

        with patch("wt_manager.utils.error_handler.handle_error") as mock_handle:
            mock_handle.return_value = True

            result = failing_function()

            assert result is None  # Should return None when error is handled
            mock_handle.assert_called_once()

    def test_decorator_with_reraise(self):
        """Test decorator with reraise=True."""

        @error_handler_decorator(show_dialog=False, log_error=False, reraise=True)
        def failing_function():
            raise ValueError("Test error")

        with patch("wt_manager.utils.error_handler.handle_error") as mock_handle:
            mock_handle.return_value = True

            with pytest.raises(ValueError):
                failing_function()


class TestErrorDialogIntegration:
    """Test error dialog integration (mocked)."""

    def test_show_error_dialog_critical(self, error_handler):
        """Test showing critical error dialog."""
        error = GitWorktreeManagerError(
            "Critical error",
            severity=ErrorSeverity.CRITICAL,
            user_message="Something went very wrong",
            suggested_action="Restart the application",
        )

        with patch("wt_manager.utils.error_handler.QMessageBox") as mock_box:
            mock_instance = Mock()
            mock_box.return_value = mock_instance

            error_handler._show_error_dialog(error)

            mock_box.assert_called_once()
            # Check that setIcon was called (the exact enum value is mocked)
            mock_instance.setIcon.assert_called_once()
            mock_instance.setWindowTitle.assert_called_with("Critical Error")
            mock_instance.setText.assert_called_with("Something went very wrong")

    def test_show_error_dialog_with_details(self, error_handler):
        """Test showing error dialog with detailed information."""
        error = GitWorktreeManagerError(
            "Error with details",
            details={"file": "test.py", "operation": "read"},
            suggested_action="Check file permissions",
            error_code="E001",
        )

        with patch("wt_manager.utils.error_handler.QMessageBox") as mock_box:
            mock_instance = Mock()
            mock_box.return_value = mock_instance

            error_handler._show_error_dialog(error)

            mock_instance.setDetailedText.assert_called_once()
            mock_instance.setInformativeText.assert_called_with("Error Code: E001")

    def test_fallback_error_dialog(self, error_handler):
        """Test fallback error dialog when main dialog fails."""
        with patch("wt_manager.utils.error_handler.QMessageBox") as mock_box:
            # Make the main dialog creation fail
            mock_box.side_effect = Exception("Dialog creation failed")

            with patch(
                "wt_manager.utils.error_handler.QMessageBox.critical"
            ) as mock_critical:
                error_handler._show_fallback_error_dialog("Test message")
                mock_critical.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])
