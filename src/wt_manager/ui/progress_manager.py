"""Progress feedback and status management system."""

from PyQt6.QtWidgets import QProgressDialog, QWidget, QStatusBar
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

from ..utils.exceptions import GitWorktreeManagerError
from .error_dialogs import show_success_notification


class OperationProgress(QObject):
    """Represents progress for a single operation."""

    progress_changed = pyqtSignal(int)  # Progress percentage (0-100)
    status_changed = pyqtSignal(str)  # Status message
    completed = pyqtSignal(bool)  # True for success, False for failure
    error_occurred = pyqtSignal(GitWorktreeManagerError)

    def __init__(self, operation_id: str, description: str):
        super().__init__()
        self.operation_id = operation_id
        self.description = description
        self.progress = 0
        self.status = "Starting..."
        self.is_completed = False
        self.is_cancelled = False

    def update_progress(self, progress: int, status: str = None):
        """Update progress and optionally status."""
        self.progress = max(0, min(100, progress))
        if status:
            self.status = status

        self.progress_changed.emit(self.progress)
        if status:
            self.status_changed.emit(self.status)

    def update_status(self, status: str):
        """Update status message."""
        self.status = status
        self.status_changed.emit(status)

    def complete_success(self, message: str = None):
        """Mark operation as successfully completed."""
        if not self.is_completed:
            self.progress = 100
            self.status = message or "Completed successfully"
            self.is_completed = True
            self.progress_changed.emit(100)
            self.status_changed.emit(self.status)
            self.completed.emit(True)

    def complete_error(self, error: GitWorktreeManagerError):
        """Mark operation as failed with error."""
        if not self.is_completed:
            self.is_completed = True
            # Handle both GitWorktreeManagerError and generic exceptions
            if hasattr(error, "user_message"):
                self.status = f"Failed: {error.user_message}"
            else:
                self.status = f"Failed: {str(error)}"
            self.status_changed.emit(self.status)
            self.error_occurred.emit(error)
            self.completed.emit(False)

    def cancel(self):
        """Cancel the operation."""
        if not self.is_completed:
            self.is_cancelled = True
            self.is_completed = True
            self.status = "Cancelled"
            self.status_changed.emit(self.status)
            self.completed.emit(False)


class ProgressDialog(QProgressDialog):
    """Enhanced progress dialog with better UX."""

    def __init__(
        self,
        operation: OperationProgress,
        parent: QWidget | None = None,
        show_cancel: bool = True,
    ):
        super().__init__(parent)
        self.operation = operation

        # Configure dialog
        self.setWindowTitle("Operation in Progress")
        self.setLabelText(operation.description)
        self.setRange(0, 100)
        self.setValue(0)
        self.setModal(True)
        self.setAutoClose(False)
        self.setAutoReset(False)

        if not show_cancel:
            self.setCancelButton(None)

        # Connect signals
        operation.progress_changed.connect(self.setValue)
        operation.status_changed.connect(self.setLabelText)
        operation.completed.connect(self._on_completed)
        operation.error_occurred.connect(self._on_error)

        if show_cancel:
            self.canceled.connect(operation.cancel)

    def _on_completed(self, success: bool):
        """Handle operation completion."""
        if success:
            self.setValue(100)
            QTimer.singleShot(500, self.accept)  # Brief delay to show completion
        else:
            self.reject()

    def _on_error(self, error: GitWorktreeManagerError):
        """Handle operation error."""
        self.setLabelText(f"Error: {error.user_message}")
        QTimer.singleShot(2000, self.reject)  # Show error briefly then close


class StatusBarManager(QObject):
    """Manages status bar updates and temporary messages."""

    def __init__(self, status_bar: QStatusBar):
        super().__init__()
        self.status_bar = status_bar
        self._temp_timer = QTimer()
        self._temp_timer.timeout.connect(self._clear_temp_message)
        self._permanent_message = ""
        self._temp_message = ""

    def show_message(self, message: str, timeout: int = 0):
        """Show a message in the status bar."""
        if timeout > 0:
            self._temp_message = message
            self.status_bar.showMessage(message, timeout)
            self._temp_timer.start(timeout)
        else:
            self._permanent_message = message
            self.status_bar.showMessage(message)

    def show_temporary_message(self, message: str, duration: int = 3000):
        """Show a temporary message that auto-clears."""
        self.show_message(message, duration)

    def show_success(self, message: str, duration: int = 3000):
        """Show a success message with icon."""
        self.show_temporary_message(f"✅ {message}", duration)

    def show_warning(self, message: str, duration: int = 5000):
        """Show a warning message with icon."""
        self.show_temporary_message(f"⚠️ {message}", duration)

    def show_error(self, message: str, duration: int = 5000):
        """Show an error message with icon."""
        self.show_temporary_message(f"❌ {message}", duration)

    def show_info(self, message: str, duration: int = 3000):
        """Show an info message with icon."""
        self.show_temporary_message(f"ℹ️ {message}", duration)

    def clear_message(self):
        """Clear the status bar message."""
        self.status_bar.clearMessage()
        self._permanent_message = ""
        self._temp_message = ""

    def _clear_temp_message(self):
        """Clear temporary message and restore permanent one."""
        self._temp_timer.stop()
        if self._permanent_message:
            self.status_bar.showMessage(self._permanent_message)
        else:
            self.status_bar.clearMessage()
        self._temp_message = ""


class ProgressManager(QObject):
    """Central manager for all progress operations."""

    operation_started = pyqtSignal(str, str)  # operation_id, description
    operation_completed = pyqtSignal(str, bool)  # operation_id, success

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.parent_widget = parent
        self._operations: dict[str, OperationProgress] = {}
        self._dialogs: dict[str, ProgressDialog] = {}
        self.status_manager: StatusBarManager | None = None

    def set_status_manager(self, status_manager: StatusBarManager):
        """Set the status bar manager."""
        self.status_manager = status_manager

    def start_operation(
        self,
        operation_id: str,
        description: str,
        show_dialog: bool = True,
        show_cancel: bool = True,
    ) -> OperationProgress:
        """Start a new operation with progress tracking."""
        # Create operation
        operation = OperationProgress(operation_id, description)
        self._operations[operation_id] = operation

        # Connect completion signal
        operation.completed.connect(
            lambda success: self._on_operation_completed(operation_id, success)
        )

        # Show progress dialog if requested
        if show_dialog:
            dialog = ProgressDialog(operation, self.parent_widget, show_cancel)
            self._dialogs[operation_id] = dialog
            dialog.show()

        # Update status bar
        if self.status_manager:
            self.status_manager.show_info(f"Starting: {description}")

        # Emit signal
        self.operation_started.emit(operation_id, description)

        return operation

    def get_operation(self, operation_id: str) -> OperationProgress | None:
        """Get an existing operation by ID."""
        return self._operations.get(operation_id)

    def complete_operation(
        self,
        operation_id: str,
        success: bool = True,
        message: str = None,
        error: GitWorktreeManagerError = None,
    ):
        """Complete an operation."""
        operation = self._operations.get(operation_id)
        if not operation:
            return

        if success:
            operation.complete_success(message)
        elif error:
            operation.complete_error(error)
        else:
            operation.complete_error(
                GitWorktreeManagerError(
                    message or "Operation failed",
                    user_message=message or "The operation could not be completed.",
                )
            )

    def cancel_operation(self, operation_id: str):
        """Cancel an operation."""
        operation = self._operations.get(operation_id)
        if operation:
            operation.cancel()

    def update_operation_progress(
        self, operation_id: str, progress: int, status: str = None
    ):
        """Update progress for an operation."""
        operation = self._operations.get(operation_id)
        if operation:
            operation.update_progress(progress, status)

    def update_operation_status(self, operation_id: str, status: str):
        """Update status for an operation."""
        operation = self._operations.get(operation_id)
        if operation:
            operation.update_status(status)

    def _on_operation_completed(self, operation_id: str, success: bool):
        """Handle operation completion."""
        operation = self._operations.get(operation_id)
        if not operation:
            return

        # Update status bar
        if self.status_manager:
            if success:
                self.status_manager.show_success(f"Completed: {operation.description}")
                # Show system notification for important operations
                show_success_notification("Operation Completed", operation.description)
            else:
                self.status_manager.show_error(f"Failed: {operation.description}")

        # Clean up dialog
        dialog = self._dialogs.pop(operation_id, None)
        if dialog:
            dialog.close()

        # Keep operation for a while for history, then clean up
        QTimer.singleShot(30000, lambda: self._cleanup_operation(operation_id))

        # Emit signal
        self.operation_completed.emit(operation_id, success)

    def _cleanup_operation(self, operation_id: str):
        """Clean up completed operation."""
        self._operations.pop(operation_id, None)

    def get_active_operations(self) -> dict[str, OperationProgress]:
        """Get all active (non-completed) operations."""
        return {
            op_id: op for op_id, op in self._operations.items() if not op.is_completed
        }

    def cancel_all_operations(self):
        """Cancel all active operations."""
        for operation in self.get_active_operations().values():
            operation.cancel()


# Global progress manager instance
_global_progress_manager: ProgressManager | None = None


def get_progress_manager() -> ProgressManager:
    """Get the global progress manager instance."""
    global _global_progress_manager
    if _global_progress_manager is None:
        _global_progress_manager = ProgressManager()
    return _global_progress_manager


def set_progress_manager(manager: ProgressManager):
    """Set the global progress manager instance."""
    global _global_progress_manager
    _global_progress_manager = manager


# Convenience functions for common operations
def start_operation(
    operation_id: str,
    description: str,
    show_dialog: bool = True,
    show_cancel: bool = True,
) -> OperationProgress:
    """Start a new operation using the global manager."""
    return get_progress_manager().start_operation(
        operation_id, description, show_dialog, show_cancel
    )


def complete_operation(
    operation_id: str,
    success: bool = True,
    message: str = None,
    error: GitWorktreeManagerError = None,
):
    """Complete an operation using the global manager."""
    get_progress_manager().complete_operation(operation_id, success, message, error)


def update_operation_progress(operation_id: str, progress: int, status: str = None):
    """Update operation progress using the global manager."""
    get_progress_manager().update_operation_progress(operation_id, progress, status)


def progress_operation_decorator(
    operation_id: str = None,
    description: str = "Operation in progress",
    show_dialog: bool = True,
):
    """Decorator to automatically track function progress."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            # Generate operation ID if not provided
            op_id = operation_id or f"{func.__name__}_{id(args)}"

            # Start operation
            start_operation(op_id, description, show_dialog)

            try:
                # Execute function
                result = func(*args, **kwargs)

                # Complete successfully
                complete_operation(op_id, True, "Operation completed successfully")
                return result

            except Exception as e:
                # Handle error
                if isinstance(e, GitWorktreeManagerError):
                    complete_operation(op_id, False, error=e)
                else:
                    complete_operation(op_id, False, str(e))
                raise

        return wrapper

    return decorator
