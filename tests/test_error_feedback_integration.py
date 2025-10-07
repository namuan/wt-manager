"""Integration tests for error handling and feedback systems."""

import pytest
from unittest.mock import patch
from PyQt6.QtWidgets import QStatusBar, QMainWindow

from wt_manager.utils.exceptions import GitError, ValidationError, FileSystemError
from wt_manager.utils.error_handler import ErrorHandler
from wt_manager.ui.progress_manager import ProgressManager
from wt_manager.ui.status_widgets import OperationStatusPanel
from wt_manager.ui.error_dialogs import (
    ErrorDetailsDialog,
    ProgressErrorDialog,
    NotificationManager,
)


@pytest.fixture
def main_window(qtbot):
    """Create a main window for integration testing."""
    window = QMainWindow()
    window.status_bar = QStatusBar()
    window.setStatusBar(window.status_bar)
    qtbot.addWidget(window)
    return window


@pytest.fixture
def integrated_system(qtbot, main_window):
    """Set up integrated error handling and progress system."""
    # Create error handler
    error_handler = ErrorHandler(main_window)

    # Create progress manager
    progress_manager = ProgressManager(main_window)

    # Create status panel
    status_panel = OperationStatusPanel(progress_manager, main_window)
    qtbot.addWidget(status_panel)

    # Create notification manager
    notification_manager = NotificationManager(main_window)

    return {
        "error_handler": error_handler,
        "progress_manager": progress_manager,
        "status_panel": status_panel,
        "notification_manager": notification_manager,
        "main_window": main_window,
    }


class TestErrorHandlingIntegration:
    """Test integration between error handling and UI components."""

    def test_error_with_progress_operation(self, qtbot, integrated_system):
        """Test error handling during a progress operation."""
        progress_manager = integrated_system["progress_manager"]
        error_handler = integrated_system["error_handler"]

        # Start an operation
        operation = progress_manager.start_operation(
            "test_op", "Test operation", show_dialog=False
        )

        # Simulate an error during operation
        error = GitError(
            "Git command failed",
            command="git clone repo",
            exit_code=128,
            user_message="Failed to clone repository",
            suggested_action="Check repository URL and permissions",
        )

        with patch.object(error_handler, "_show_error_dialog") as mock_dialog:
            # Handle error and complete operation
            error_handler.handle_error(error, show_dialog=True)
            operation.complete_error(error)

            # Error dialog should be shown
            mock_dialog.assert_called_once_with(error)

            # Operation should be marked as failed
            assert operation.is_completed
            assert not operation.progress == 100

    def test_progress_error_dialog_integration(self, qtbot, integrated_system):
        """Test ProgressErrorDialog with error handling."""
        # Create progress error dialog
        dialog = ProgressErrorDialog(
            "Processing...",
            parent=integrated_system["main_window"],
            show_error_dialogs=False,  # Disable dialogs for testing
        )
        qtbot.addWidget(dialog)

        # Add an error
        error = ValidationError(
            "Invalid input",
            field="path",
            value="/invalid/path",
            user_message="The specified path is invalid",
        )

        dialog.add_error(error)

        # Dialog should handle the error
        assert len(dialog._errors) == 1
        assert dialog._errors[0] is error

    def test_notification_system_integration(self, qtbot, integrated_system):
        """Test notification system with progress operations."""
        progress_manager = integrated_system["progress_manager"]
        notification_manager = integrated_system["notification_manager"]

        # Mock system tray notifications
        with patch.object(notification_manager, "_tray_icon") as mock_tray:
            mock_tray.supportsMessages.return_value = True

            # Start and complete operation successfully
            operation = progress_manager.start_operation(
                "test_op", "Test operation", show_dialog=False
            )

            # Complete successfully - should trigger notification
            with patch("wt_manager.ui.error_dialogs.show_success_notification"):
                operation.complete_success("Operation completed")

                # Wait for completion handling
                qtbot.wait(100)

    def test_status_bar_error_integration(self, qtbot, integrated_system):
        """Test status bar integration with error handling."""
        error_handler = integrated_system["error_handler"]
        main_window = integrated_system["main_window"]

        # Create status bar manager
        from wt_manager.ui.progress_manager import StatusBarManager

        status_manager = StatusBarManager(main_window.status_bar)

        # Simulate error with status bar update
        error = FileNotFoundError("File not found")

        with patch.object(error_handler, "_show_error_dialog"):
            error_handler.handle_error(error, show_dialog=True)

            # Manually update status bar (in real app this would be connected)
            status_manager.show_error("File operation failed")

            # Status bar should show error message
            assert "❌" in main_window.status_bar.currentMessage()
            assert "File operation failed" in main_window.status_bar.currentMessage()

    def test_multiple_errors_during_operation(self, qtbot, integrated_system):
        """Test handling multiple errors during a single operation."""
        progress_manager = integrated_system["progress_manager"]
        error_handler = integrated_system["error_handler"]

        # Start operation
        operation = progress_manager.start_operation(
            "test_op", "Complex operation", show_dialog=False
        )

        # Simulate multiple errors
        errors = [
            ValidationError("Invalid path", field="path"),
            GitError("Git command failed", command="git status"),
            FileSystemError("Config file not found", path="/config/file.json"),
        ]

        handled_errors = []

        def capture_error(error):
            handled_errors.append(error)

        # Connect to error signal
        error_handler.error_occurred.connect(capture_error)

        # Handle multiple errors
        for error in errors:
            error_handler.handle_error(error, show_dialog=False)

        # All errors should be handled
        assert len(handled_errors) == 3

        # Complete operation with final error
        operation.complete_error(errors[-1])
        assert operation.is_completed

    def test_error_recovery_with_progress_update(self, qtbot, integrated_system):
        """Test error recovery that allows operation to continue."""
        progress_manager = integrated_system["progress_manager"]
        error_handler = integrated_system["error_handler"]

        # Register recovery callback
        def recovery_callback(error):
            # Simulate successful recovery
            return True

        error_handler.register_recovery_callback(ValidationError, recovery_callback)

        # Start operation
        operation = progress_manager.start_operation(
            "test_op", "Operation with recovery", show_dialog=False
        )

        # Simulate recoverable error
        error = ValidationError("Recoverable error", field="input")

        with patch.object(error_handler, "_show_error_dialog") as mock_dialog:
            result = error_handler.handle_error(error, attempt_recovery=True)

            # Error should be handled successfully
            assert result is True

            # Dialog should not be shown (recovery was successful)
            mock_dialog.assert_not_called()

            # Operation can continue
            operation.update_progress(100, "Completed after recovery")
            operation.complete_success()

            assert operation.is_completed
            assert operation.progress == 100


class TestErrorDialogIntegration:
    """Test error dialog integration with the application."""

    def test_error_details_dialog_display(self, qtbot, integrated_system):
        """Test displaying detailed error dialog."""
        error = GitError(
            "Git operation failed",
            command="git worktree add /path/to/worktree branch",
            exit_code=128,
            stderr="fatal: '/path/to/worktree' already exists",
            user_message="Cannot create worktree at the specified location",
            suggested_action="Choose a different path or remove the existing directory",
            error_code="GIT001",
        )

        dialog = ErrorDetailsDialog(error, integrated_system["main_window"])
        qtbot.addWidget(dialog)

        # Dialog should display error information
        # Check that the dialog was created successfully
        assert dialog.error.user_message == error.user_message
        assert dialog.error.suggested_action == error.suggested_action

        # Details should include technical information
        details_text = dialog.details_text.toPlainText()
        assert "GitError" in details_text
        assert "git_operation" in details_text
        assert "GIT001" in details_text
        assert error.command in details_text

    def test_progress_error_dialog_multiple_errors(self, qtbot, integrated_system):
        """Test progress dialog with multiple errors."""
        dialog = ProgressErrorDialog(
            "Processing multiple files...",
            parent=integrated_system["main_window"],
            show_error_dialogs=False,  # Disable dialogs for testing
        )
        qtbot.addWidget(dialog)

        # Add multiple errors
        errors = [
            ValidationError("Invalid file format", field="file1"),
            FileSystemError("File not found: file2.txt", path="file2.txt"),
            GitError("Git add failed", command="git add file3.txt"),
        ]

        for error in errors:
            dialog.add_error(error)

        assert len(dialog._errors) == 3

        # Dialog should handle multiple errors appropriately
        # (Implementation would show summary dialog)

    def test_notification_fallback_behavior(self, qtbot, integrated_system):
        """Test notification fallback when system tray is unavailable."""
        notification_manager = integrated_system["notification_manager"]

        # Mock system tray as unavailable
        with patch.object(notification_manager, "_tray_icon", None):
            # Should fallback to console output or other method
            with patch("builtins.print") as mock_print:
                notification_manager.show_success("Test", "Success message")

                # Should use fallback method
                mock_print.assert_called_once()
                assert "Success message" in str(mock_print.call_args)


class TestSystemIntegration:
    """Test full system integration scenarios."""

    def test_complete_operation_workflow_with_errors(self, qtbot, integrated_system):
        """Test complete workflow from operation start to completion with errors."""
        progress_manager = integrated_system["progress_manager"]
        error_handler = integrated_system["error_handler"]
        status_panel = integrated_system["status_panel"]

        # Start operation
        operation = progress_manager.start_operation(
            "git_clone", "Cloning repository", show_dialog=False
        )

        # Wait for the signal to be processed
        qtbot.wait(100)

        # Wait for the signal to be processed
        qtbot.wait(100)

        # Panel should show the operation (visibility may not work in test environment)
        assert "git_clone" in status_panel._operation_widgets

        # Simulate progress updates
        operation.update_progress(25, "Connecting to remote...")
        operation.update_progress(50, "Downloading objects...")

        # Simulate an error
        error = GitError(
            "Network error",
            command="git clone https://github.com/user/repo.git",
            exit_code=128,
            stderr="fatal: unable to access 'https://github.com/user/repo.git/': Could not resolve host",
            user_message="Failed to connect to the repository",
            suggested_action="Check your internet connection and repository URL",
        )

        # Handle error and complete operation
        with patch.object(error_handler, "_show_error_dialog") as mock_dialog:
            error_handler.handle_error(error)
            operation.complete_error(error)

            # Error dialog should be shown
            mock_dialog.assert_called_once()

            # Operation should be completed with error
            assert operation.is_completed
            assert not operation.progress == 100

            # Status panel should reflect the error state
            widget = status_panel._operation_widgets["git_clone"]
            assert widget.status_indicator._status == "error"

    def test_concurrent_operations_with_mixed_outcomes(self, qtbot, integrated_system):
        """Test multiple concurrent operations with different outcomes."""
        progress_manager = integrated_system["progress_manager"]

        # Start multiple operations
        op1 = progress_manager.start_operation("op1", "Operation 1", show_dialog=False)
        op2 = progress_manager.start_operation("op2", "Operation 2", show_dialog=False)
        op3 = progress_manager.start_operation("op3", "Operation 3", show_dialog=False)

        # Complete with different outcomes
        op1.complete_success("Success!")

        error = ValidationError("Invalid input", field="test")
        op2.complete_error(error)

        op3.cancel()

        # Check final states
        assert op1.is_completed and op1.progress == 100
        assert op2.is_completed and op2.progress != 100
        assert op3.is_cancelled and op3.is_completed

        # All should be inactive now
        active_ops = progress_manager.get_active_operations()
        assert len(active_ops) == 0


if __name__ == "__main__":
    pytest.main([__file__])
