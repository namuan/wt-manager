"""Tests for progress feedback and status management."""

import pytest
from unittest.mock import Mock, patch
from PyQt6.QtWidgets import QWidget, QStatusBar

from wt_manager.ui.progress_manager import (
    OperationProgress,
    StatusBarManager,
    ProgressManager,
    get_progress_manager,
    set_progress_manager,
    start_operation,
    complete_operation,
    update_operation_progress,
)
from wt_manager.ui.status_widgets import (
    StatusIndicator,
    OperationStatusWidget,
    OperationStatusPanel,
)
from wt_manager.utils.exceptions import GitWorktreeManagerError


class TestOperationProgress:
    """Test the OperationProgress class."""

    def test_operation_creation(self):
        """Test creating an operation progress tracker."""
        operation = OperationProgress("test_op", "Test operation")

        assert operation.operation_id == "test_op"
        assert operation.description == "Test operation"
        assert operation.progress == 0
        assert operation.status == "Starting..."
        assert not operation.is_completed
        assert not operation.is_cancelled

    def test_update_progress(self, qtbot):
        """Test updating operation progress."""
        operation = OperationProgress("test_op", "Test operation")

        with qtbot.waitSignal(operation.progress_changed, timeout=1000):
            operation.update_progress(50, "Half way done")

        assert operation.progress == 50
        assert operation.status == "Half way done"

    def test_update_progress_bounds(self, qtbot):
        """Test progress bounds checking."""
        operation = OperationProgress("test_op", "Test operation")

        # Test upper bound
        operation.update_progress(150)
        assert operation.progress == 100

        # Test lower bound
        operation.update_progress(-10)
        assert operation.progress == 0

    def test_update_status_only(self, qtbot):
        """Test updating only status message."""
        operation = OperationProgress("test_op", "Test operation")

        with qtbot.waitSignal(operation.status_changed, timeout=1000):
            operation.update_status("Processing files...")

        assert operation.status == "Processing files..."

    def test_complete_success(self, qtbot):
        """Test successful completion."""
        operation = OperationProgress("test_op", "Test operation")

        with qtbot.waitSignal(operation.completed, timeout=1000) as blocker:
            operation.complete_success("All done!")

        assert operation.is_completed
        assert operation.progress == 100
        assert operation.status == "All done!"
        assert blocker.args == [True]  # Success signal

    def test_complete_error(self, qtbot):
        """Test error completion."""
        operation = OperationProgress("test_op", "Test operation")
        error = GitWorktreeManagerError("Something went wrong")

        with qtbot.waitSignal(operation.completed, timeout=1000) as blocker:
            operation.complete_error(error)

        assert operation.is_completed
        assert "Failed:" in operation.status
        assert blocker.args == [False]  # Failure signal

    def test_cancel_operation(self, qtbot):
        """Test cancelling an operation."""
        operation = OperationProgress("test_op", "Test operation")

        with qtbot.waitSignal(operation.completed, timeout=1000) as blocker:
            operation.cancel()

        assert operation.is_cancelled
        assert operation.is_completed
        assert operation.status == "Cancelled"
        assert blocker.args == [False]  # Cancelled counts as failure


@pytest.fixture
def status_bar(qtbot):
    """Create a status bar for testing."""
    widget = QWidget()
    qtbot.addWidget(widget)
    status_bar = QStatusBar(widget)
    # Keep widget alive to prevent status bar deletion
    status_bar._test_parent = widget
    return status_bar


class TestStatusBarManager:
    """Test the StatusBarManager class."""

    def test_status_manager_creation(self, status_bar):
        """Test creating a status bar manager."""
        manager = StatusBarManager(status_bar)
        assert manager.status_bar is status_bar

    def test_show_permanent_message(self, status_bar):
        """Test showing a permanent message."""
        manager = StatusBarManager(status_bar)
        manager.show_message("Permanent message")

        assert status_bar.currentMessage() == "Permanent message"
        assert manager._permanent_message == "Permanent message"

    def test_show_temporary_message(self, status_bar, qtbot):
        """Test showing a temporary message."""
        manager = StatusBarManager(status_bar)

        # Show temporary message
        manager.show_temporary_message("Temporary message", 100)  # Short timeout

        assert status_bar.currentMessage() == "Temporary message"

        # Wait for timeout
        qtbot.wait(200)

        # Message should be cleared
        assert status_bar.currentMessage() == ""

    def test_show_success_message(self, status_bar):
        """Test showing success message with icon."""
        manager = StatusBarManager(status_bar)
        manager.show_success("Operation completed")

        assert "✅" in status_bar.currentMessage()
        assert "Operation completed" in status_bar.currentMessage()

    def test_show_error_message(self, status_bar):
        """Test showing error message with icon."""
        manager = StatusBarManager(status_bar)
        manager.show_error("Operation failed")

        assert "❌" in status_bar.currentMessage()
        assert "Operation failed" in status_bar.currentMessage()

    def test_clear_message(self, status_bar):
        """Test clearing status bar message."""
        manager = StatusBarManager(status_bar)
        manager.show_message("Test message")
        manager.clear_message()

        assert status_bar.currentMessage() == ""
        assert manager._permanent_message == ""


@pytest.fixture
def progress_manager(qtbot):
    """Create a progress manager for testing."""
    parent = QWidget()
    qtbot.addWidget(parent)
    manager = ProgressManager(parent)
    return manager


class TestProgressManager:
    """Test the ProgressManager class."""

    def test_progress_manager_creation(self, progress_manager):
        """Test creating a progress manager."""
        assert progress_manager.parent_widget is not None
        assert len(progress_manager._operations) == 0

    def test_start_operation(self, progress_manager, qtbot):
        """Test starting a new operation."""
        with qtbot.waitSignal(progress_manager.operation_started, timeout=1000):
            operation = progress_manager.start_operation(
                "test_op", "Test operation", show_dialog=False
            )

        assert operation.operation_id == "test_op"
        assert operation.description == "Test operation"
        assert "test_op" in progress_manager._operations

    def test_get_operation(self, progress_manager):
        """Test getting an existing operation."""
        operation = progress_manager.start_operation(
            "test_op", "Test operation", show_dialog=False
        )

        retrieved = progress_manager.get_operation("test_op")
        assert retrieved is operation

        # Test non-existent operation
        assert progress_manager.get_operation("nonexistent") is None

    def test_complete_operation_success(self, progress_manager, qtbot):
        """Test completing an operation successfully."""
        operation = progress_manager.start_operation(
            "test_op", "Test operation", show_dialog=False
        )

        with qtbot.waitSignal(progress_manager.operation_completed, timeout=1000):
            progress_manager.complete_operation("test_op", True, "Success!")

        assert operation.is_completed
        assert operation.progress == 100

    def test_complete_operation_error(self, progress_manager, qtbot):
        """Test completing an operation with error."""
        operation = progress_manager.start_operation(
            "test_op", "Test operation", show_dialog=False
        )

        error = GitWorktreeManagerError("Test error")

        with qtbot.waitSignal(progress_manager.operation_completed, timeout=1000):
            progress_manager.complete_operation("test_op", False, error=error)

        assert operation.is_completed
        assert not operation.progress == 100

    def test_update_operation_progress(self, progress_manager):
        """Test updating operation progress."""
        operation = progress_manager.start_operation(
            "test_op", "Test operation", show_dialog=False
        )

        progress_manager.update_operation_progress("test_op", 75, "Almost done")

        assert operation.progress == 75
        assert operation.status == "Almost done"

    def test_cancel_operation(self, progress_manager):
        """Test cancelling an operation."""
        operation = progress_manager.start_operation(
            "test_op", "Test operation", show_dialog=False
        )

        progress_manager.cancel_operation("test_op")

        assert operation.is_cancelled
        assert operation.is_completed

    def test_get_active_operations(self, progress_manager):
        """Test getting active operations."""
        # Start multiple operations
        progress_manager.start_operation("op1", "Operation 1", show_dialog=False)
        progress_manager.start_operation("op2", "Operation 2", show_dialog=False)
        progress_manager.start_operation("op3", "Operation 3", show_dialog=False)

        # Complete one operation
        progress_manager.complete_operation("op2", True)

        active = progress_manager.get_active_operations()

        assert len(active) == 2
        assert "op1" in active
        assert "op3" in active
        assert "op2" not in active

    def test_cancel_all_operations(self, progress_manager):
        """Test cancelling all operations."""
        # Start multiple operations
        progress_manager.start_operation("op1", "Operation 1", show_dialog=False)
        progress_manager.start_operation("op2", "Operation 2", show_dialog=False)

        progress_manager.cancel_all_operations()

        active = progress_manager.get_active_operations()
        assert len(active) == 0


class TestGlobalProgressManager:
    """Test global progress manager functions."""

    def test_get_global_manager(self):
        """Test getting global progress manager."""
        manager1 = get_progress_manager()
        manager2 = get_progress_manager()

        assert manager1 is manager2  # Should be same instance

    def test_set_global_manager(self):
        """Test setting global progress manager."""
        custom_manager = ProgressManager()
        set_progress_manager(custom_manager)

        retrieved_manager = get_progress_manager()
        assert retrieved_manager is custom_manager

    def test_global_start_operation(self):
        """Test global start_operation function."""
        with patch.object(get_progress_manager(), "start_operation") as mock_start:
            mock_operation = Mock()
            mock_start.return_value = mock_operation

            result = start_operation("test_op", "Test operation")

            assert result is mock_operation
            mock_start.assert_called_once_with("test_op", "Test operation", True, True)

    def test_global_complete_operation(self):
        """Test global complete_operation function."""
        with patch.object(
            get_progress_manager(), "complete_operation"
        ) as mock_complete:
            complete_operation("test_op", True, "Success")

            mock_complete.assert_called_once_with("test_op", True, "Success", None)

    def test_global_update_progress(self):
        """Test global update_operation_progress function."""
        with patch.object(
            get_progress_manager(), "update_operation_progress"
        ) as mock_update:
            update_operation_progress("test_op", 50, "Half done")

            mock_update.assert_called_once_with("test_op", 50, "Half done")


class TestStatusIndicator:
    """Test the StatusIndicator widget."""

    def test_status_indicator_creation(self, qtbot):
        """Test creating a status indicator."""
        indicator = StatusIndicator()
        qtbot.addWidget(indicator)

        assert indicator._status == "idle"
        assert indicator.size().width() == 20
        assert indicator.size().height() == 20

    def test_set_status(self, qtbot):
        """Test setting different statuses."""
        indicator = StatusIndicator()
        qtbot.addWidget(indicator)

        # Test different statuses
        statuses = ["success", "error", "warning", "working", "idle"]

        for status in statuses:
            indicator.set_status(status)
            assert indicator._status == status

    def test_animation_for_working_status(self, qtbot):
        """Test that animation starts for working status."""
        indicator = StatusIndicator()
        qtbot.addWidget(indicator)

        # Set to working status
        indicator.set_status("working")

        # Animation should be running
        assert indicator._animation.state() != indicator._animation.State.Stopped

        # Set to idle status
        indicator.set_status("idle")

        # Animation should be stopped
        assert indicator._animation.state() == indicator._animation.State.Stopped


class TestOperationStatusWidget:
    """Test the OperationStatusWidget."""

    def test_status_widget_creation(self, qtbot):
        """Test creating an operation status widget."""
        operation = OperationProgress("test_op", "Test operation")
        widget = OperationStatusWidget(operation)
        qtbot.addWidget(widget)

        assert widget.operation is operation
        assert widget.description_label.text() == "Test operation"
        assert widget.progress_bar.value() == 0

    def test_progress_updates(self, qtbot):
        """Test that widget updates with operation progress."""
        operation = OperationProgress("test_op", "Test operation")
        widget = OperationStatusWidget(operation)
        qtbot.addWidget(widget)

        # Update progress
        operation.update_progress(75, "Almost done")

        assert widget.progress_bar.value() == 75
        assert widget.status_label.text() == "Almost done"

    def test_completion_handling(self, qtbot):
        """Test widget behavior on operation completion."""
        operation = OperationProgress("test_op", "Test operation")
        widget = OperationStatusWidget(operation)
        qtbot.addWidget(widget)

        # Complete operation
        operation.complete_success("Done!")

        # Status indicator should show success
        assert widget.status_indicator._status == "success"

    def test_cancel_button_signal(self, qtbot):
        """Test cancel button emits correct signal."""
        operation = OperationProgress("test_op", "Test operation")
        widget = OperationStatusWidget(operation)
        qtbot.addWidget(widget)

        # Should have cancel button for non-completed operation
        assert hasattr(widget, "cancel_button")

        with qtbot.waitSignal(widget.cancel_requested, timeout=1000) as blocker:
            widget.cancel_button.click()

        assert blocker.args == ["test_op"]


class TestOperationStatusPanel:
    """Test the OperationStatusPanel."""

    def test_panel_creation(self, qtbot, progress_manager):
        """Test creating an operation status panel."""
        panel = OperationStatusPanel(progress_manager)
        qtbot.addWidget(panel)

        assert panel.progress_manager is progress_manager
        assert not panel.isVisible()  # Initially hidden

    def test_operation_widget_creation(self, qtbot, progress_manager):
        """Test that widgets are created for new operations."""
        panel = OperationStatusPanel(progress_manager)
        qtbot.addWidget(panel)

        # Start an operation
        progress_manager.start_operation("test_op", "Test operation", show_dialog=False)

        # Panel should become visible
        assert panel.isVisible()

        # Should have operation widget
        assert "test_op" in panel._operation_widgets

    def test_clear_completed_operations(self, qtbot, progress_manager):
        """Test clearing completed operations."""
        panel = OperationStatusPanel(progress_manager)
        qtbot.addWidget(panel)

        # Start and complete an operation
        progress_manager.start_operation("test_op", "Test operation", show_dialog=False)
        progress_manager.complete_operation("test_op", True)

        # Clear completed
        panel._clear_completed()

        # Widget should be removed
        assert "test_op" not in panel._operation_widgets


if __name__ == "__main__":
    pytest.main([__file__])
