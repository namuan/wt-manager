"""Error dialog components for user-friendly error display."""

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QScrollArea,
    QWidget,
    QFrame,
    QApplication,
    QProgressDialog,
    QSystemTrayIcon,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal

from ..utils.exceptions import GitWorktreeManagerError, ErrorSeverity


class ErrorDetailsDialog(QDialog):
    """Detailed error dialog with expandable information."""

    def __init__(self, error: GitWorktreeManagerError, parent: QWidget | None = None):
        super().__init__(parent)
        self.error = error
        self.setWindowTitle("Error Details")
        self.setModal(True)
        self.resize(500, 300)

        self._setup_ui()
        self._populate_content()

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Header with icon and main message
        header_layout = QHBoxLayout()

        # Error icon
        icon_label = QLabel()
        icon_label.setFixedSize(48, 48)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if self.error.severity == ErrorSeverity.CRITICAL:
            icon_label.setText("🚨")
        elif self.error.severity == ErrorSeverity.ERROR:
            icon_label.setText("❌")
        elif self.error.severity == ErrorSeverity.WARNING:
            icon_label.setText("⚠️")
        else:
            icon_label.setText("ℹ️")

        icon_label.setStyleSheet("font-size: 32px;")
        header_layout.addWidget(icon_label)

        # Main message
        message_label = QLabel(self.error.user_message)
        message_label.setWordWrap(True)
        message_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        header_layout.addWidget(message_label, 1)

        layout.addLayout(header_layout)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)

        # Suggested action
        if self.error.suggested_action:
            action_label = QLabel(
                f"<b>Suggested Action:</b> {self.error.suggested_action}"
            )
            action_label.setWordWrap(True)
            action_label.setStyleSheet("color: #0066cc; margin: 10px 0;")
            layout.addWidget(action_label)

        # Details section
        details_label = QLabel("<b>Technical Details:</b>")
        layout.addWidget(details_label)

        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(150)
        layout.addWidget(self.details_text)

        # Buttons
        button_layout = QHBoxLayout()

        copy_button = QPushButton("Copy Details")
        copy_button.clicked.connect(self._copy_details)
        button_layout.addWidget(copy_button)

        button_layout.addStretch()

        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        ok_button.setDefault(True)
        button_layout.addWidget(ok_button)

        layout.addLayout(button_layout)

    def _populate_content(self):
        """Populate the dialog with error details."""
        details = []

        # Error type and category
        details.append(f"Error Type: {self.error.__class__.__name__}")
        details.append(f"Category: {self.error.category.value}")
        details.append(f"Severity: {self.error.severity.value}")

        if self.error.error_code:
            details.append(f"Error Code: {self.error.error_code}")

        details.append(f"Message: {self.error.message}")

        # Additional details
        if self.error.details:
            details.append("\nAdditional Information:")
            for key, value in self.error.details.items():
                if value is not None:
                    details.append(f"  {key.replace('_', ' ').title()}: {value}")

        self.details_text.setPlainText("\n".join(details))

    def _copy_details(self):
        """Copy error details to clipboard."""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.details_text.toPlainText())

        # Show brief confirmation
        self.sender().setText("Copied!")
        QTimer.singleShot(1000, lambda: self.sender().setText("Copy Details"))


class ProgressErrorDialog(QProgressDialog):
    """Progress dialog that can display errors during long operations."""

    error_occurred = pyqtSignal(GitWorktreeManagerError)

    def __init__(
        self,
        label_text: str,
        cancel_button_text: str = "Cancel",
        minimum: int = 0,
        maximum: int = 0,
        parent: QWidget | None = None,
        show_error_dialogs: bool = True,
    ):
        super().__init__(label_text, cancel_button_text, minimum, maximum, parent)
        self.setModal(True)
        self.setAutoClose(False)
        self.setAutoReset(False)

        # Error handling
        self._errors: list[GitWorktreeManagerError] = []
        self._show_error_dialogs = show_error_dialogs
        self.error_occurred.connect(self._handle_error)

    def add_error(self, error: GitWorktreeManagerError):
        """Add an error to be displayed."""
        # Convert generic exceptions to GitWorktreeManagerError if needed
        if not isinstance(error, GitWorktreeManagerError):
            from ..utils.error_handler import ErrorHandler

            handler = ErrorHandler()
            error = handler._convert_to_app_error(error)

        self._errors.append(error)
        self.error_occurred.emit(error)

    def _handle_error(self, error: GitWorktreeManagerError):
        """Handle error during progress."""
        if error.severity in [ErrorSeverity.ERROR, ErrorSeverity.CRITICAL]:
            self.cancel()
            self._show_error_summary()

    def _show_error_summary(self):
        """Show summary of errors that occurred."""
        if not self._errors or not self._show_error_dialogs:
            return

        if len(self._errors) == 1:
            # Show single error dialog
            dialog = ErrorDetailsDialog(self._errors[0], self.parent())
            dialog.exec()
        else:
            # Show multiple errors summary
            self._show_multiple_errors_dialog()

    def _show_multiple_errors_dialog(self):
        """Show dialog for multiple errors."""
        if not self._show_error_dialogs:
            return

        dialog = QDialog(self.parent())
        dialog.setWindowTitle("Multiple Errors Occurred")
        dialog.setModal(True)
        dialog.resize(600, 400)

        layout = QVBoxLayout(dialog)

        # Header
        header_label = QLabel(
            f"{len(self._errors)} errors occurred during the operation:"
        )
        header_label.setStyleSheet(
            "font-weight: bold; font-size: 14px; margin-bottom: 10px;"
        )
        layout.addWidget(header_label)

        # Error list
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        for i, error in enumerate(self._errors, 1):
            error_frame = QFrame()
            error_frame.setFrameShape(QFrame.Shape.Box)
            error_frame.setStyleSheet(
                "margin: 5px; padding: 10px; background-color: #f5f5f5;"
            )

            error_layout = QVBoxLayout(error_frame)

            # Error header
            error_header = QLabel(f"Error {i}: {error.__class__.__name__}")
            error_header.setStyleSheet("font-weight: bold;")
            error_layout.addWidget(error_header)

            # Error message
            error_message = QLabel(error.user_message)
            error_message.setWordWrap(True)
            error_layout.addWidget(error_message)

            scroll_layout.addWidget(error_frame)

        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)

        # Buttons
        button_layout = QHBoxLayout()

        details_button = QPushButton("Show First Error Details")
        details_button.clicked.connect(
            lambda: ErrorDetailsDialog(self._errors[0], dialog).exec()
        )
        button_layout.addWidget(details_button)

        button_layout.addStretch()

        ok_button = QPushButton("OK")
        ok_button.clicked.connect(dialog.accept)
        ok_button.setDefault(True)
        button_layout.addWidget(ok_button)

        layout.addLayout(button_layout)

        dialog.exec()


class NotificationManager:
    """Manages success notifications and non-critical feedback."""

    def __init__(self, parent: QWidget | None = None):
        self.parent = parent
        self._tray_icon = None
        self._setup_tray_icon()

    def _setup_tray_icon(self):
        """Set up system tray icon for notifications."""
        if QSystemTrayIcon.isSystemTrayAvailable():
            self._tray_icon = QSystemTrayIcon(self.parent)
            # Set a default icon (you might want to use your app icon)
            from PyQt6.QtWidgets import QApplication

            if QApplication.instance():
                style = QApplication.instance().style()
                icon = style.standardIcon(style.StandardPixmap.SP_ComputerIcon)
                self._tray_icon.setIcon(icon)

    def show_success(self, title: str, message: str, duration: int = 3000):
        """Show success notification."""
        if self._tray_icon and self._tray_icon.supportsMessages():
            self._tray_icon.showMessage(
                title, message, QSystemTrayIcon.MessageIcon.Information, duration
            )
        else:
            # Fallback to status bar or simple message
            self._show_temporary_message(f"✅ {title}: {message}")

    def show_warning(self, title: str, message: str, duration: int = 5000):
        """Show warning notification."""
        if self._tray_icon and self._tray_icon.supportsMessages():
            self._tray_icon.showMessage(
                title, message, QSystemTrayIcon.MessageIcon.Warning, duration
            )
        else:
            self._show_temporary_message(f"⚠️ {title}: {message}")

    def show_info(self, title: str, message: str, duration: int = 3000):
        """Show info notification."""
        if self._tray_icon and self._tray_icon.supportsMessages():
            self._tray_icon.showMessage(
                title, message, QSystemTrayIcon.MessageIcon.Information, duration
            )
        else:
            self._show_temporary_message(f"ℹ️ {title}: {message}")

    def _show_temporary_message(self, message: str):
        """Show temporary message as fallback."""
        # This could be implemented to show in status bar or as a temporary widget
        print(f"Notification: {message}")  # Fallback to console


# Global notification manager
_notification_manager: NotificationManager | None = None


def get_notification_manager() -> NotificationManager:
    """Get the global notification manager."""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager()
    return _notification_manager


def show_success_notification(title: str, message: str, duration: int = 3000):
    """Show success notification using global manager."""
    get_notification_manager().show_success(title, message, duration)


def show_warning_notification(title: str, message: str, duration: int = 5000):
    """Show warning notification using global manager."""
    get_notification_manager().show_warning(title, message, duration)


def show_info_notification(title: str, message: str, duration: int = 3000):
    """Show info notification using global manager."""
    get_notification_manager().show_info(title, message, duration)
