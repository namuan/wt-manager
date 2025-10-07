"""Message service for routing messages to appropriate UI components."""

import logging
from enum import Enum
from typing import Protocol

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QMessageBox, QWidget


logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Types of messages that can be displayed."""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    QUESTION = "question"


class MessageTarget(Enum):
    """Target destinations for messages."""

    STATUS_BAR = "status_bar"
    ALERT = "alert"
    NOTIFICATION = "notification"


class StatusBarInterface(Protocol):
    """Interface for status bar components."""

    def show_message(self, message: str, timeout: int = 3000) -> None:
        """Show a message in the status bar."""
        ...


class MessageService(QObject):
    """
    Centralized service for handling application messages.

    Routes messages to appropriate UI components based on message type and importance.
    """

    # Signals for different message types
    status_message = pyqtSignal(str, int)  # message, timeout
    alert_message = pyqtSignal(str, str, str)  # title, message, type
    notification_message = pyqtSignal(str, str, str)  # title, message, type

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self._parent_widget = parent
        self._status_bar: StatusBarInterface | None = None

        # Message routing rules
        self._routing_rules = {
            MessageType.INFO: MessageTarget.STATUS_BAR,
            MessageType.SUCCESS: MessageTarget.STATUS_BAR,
            MessageType.WARNING: MessageTarget.STATUS_BAR,
            MessageType.ERROR: MessageTarget.ALERT,
            MessageType.CRITICAL: MessageTarget.ALERT,
            MessageType.QUESTION: MessageTarget.ALERT,
        }

        self.logger.info("Message service initialized")

    def set_status_bar(self, status_bar: StatusBarInterface) -> None:
        """Set the status bar interface for displaying messages."""
        self._status_bar = status_bar
        self.logger.debug("Status bar interface registered")

    def show_info(self, message: str, timeout: int = 3000) -> None:
        """Show an informational message."""
        self._route_message(MessageType.INFO, "Information", message, timeout)

    def show_success(self, message: str, timeout: int = 5000) -> None:
        """Show a success message."""
        self._route_message(MessageType.SUCCESS, "Success", message, timeout)

    def show_warning(self, message: str, timeout: int = 5000) -> None:
        """Show a warning message."""
        self._route_message(MessageType.WARNING, "Warning", message, timeout)

    def show_error(self, title: str, message: str) -> None:
        """Show an error message."""
        self._route_message(MessageType.ERROR, title, message)

    def show_critical(self, title: str, message: str) -> None:
        """Show a critical error message."""
        self._route_message(MessageType.CRITICAL, title, message)

    def ask_question(
        self,
        title: str,
        message: str,
        buttons: QMessageBox.StandardButton = QMessageBox.StandardButton.Yes
        | QMessageBox.StandardButton.No,
        default_button: QMessageBox.StandardButton = QMessageBox.StandardButton.No,
    ) -> QMessageBox.StandardButton:
        """
        Ask a question and return the user's response.

        Args:
            title: Dialog title
            message: Question message
            buttons: Available buttons
            default_button: Default button selection

        Returns:
            The button that was clicked
        """
        self.logger.debug(f"Showing question dialog: {title}")

        reply = QMessageBox.question(
            self._parent_widget, title, message, buttons, default_button
        )

        self.logger.debug(f"Question dialog result: {reply}")
        return reply

    def _route_message(
        self, msg_type: MessageType, title: str, message: str, timeout: int = 3000
    ) -> None:
        """Route message to appropriate destination based on type."""
        target = self._routing_rules.get(msg_type, MessageTarget.STATUS_BAR)

        self.logger.debug(
            f"Routing {msg_type.value} message to {target.value}: {message}"
        )

        if target == MessageTarget.STATUS_BAR:
            self._show_status_message(message, timeout)
        elif target == MessageTarget.ALERT:
            self._show_alert_message(msg_type, title, message)
        elif target == MessageTarget.NOTIFICATION:
            self._show_notification_message(msg_type, title, message)

    def _show_status_message(self, message: str, timeout: int) -> None:
        """Show message in status bar."""
        if self._status_bar:
            try:
                self._status_bar.show_message(message, timeout)
                self.status_message.emit(message, timeout)
            except RuntimeError:
                # Handle case where status bar has been deleted
                self.logger.warning(f"Status bar deleted, logging message: {message}")
        else:
            # Fallback to logging if no status bar available
            self.logger.info(f"Status: {message}")

    def _show_alert_message(
        self, msg_type: MessageType, title: str, message: str
    ) -> None:
        """Show message as an alert dialog."""
        if not self._parent_widget:
            self.logger.error(f"No parent widget for alert: {title} - {message}")
            return

        try:
            if msg_type == MessageType.ERROR:
                QMessageBox.critical(self._parent_widget, title, message)
            elif msg_type == MessageType.CRITICAL:
                QMessageBox.critical(self._parent_widget, title, message)
            elif msg_type == MessageType.WARNING:
                QMessageBox.warning(self._parent_widget, title, message)
            else:
                QMessageBox.information(self._parent_widget, title, message)

            self.alert_message.emit(title, message, msg_type.value)
        except RuntimeError:
            # Handle case where parent widget has been deleted
            self.logger.warning(
                f"Parent widget deleted, logging alert: {title} - {message}"
            )

    def _show_notification_message(
        self, msg_type: MessageType, title: str, message: str
    ) -> None:
        """Show message as a system notification."""
        try:
            # This could be extended to use system notifications
            self.notification_message.emit(title, message, msg_type.value)
        except RuntimeError:
            # Handle case where object has been deleted
            pass
        self.logger.info(f"Notification: {title} - {message}")

    def override_routing(self, msg_type: MessageType, target: MessageTarget) -> None:
        """Override the default routing for a message type."""
        self._routing_rules[msg_type] = target
        self.logger.debug(f"Routing override: {msg_type.value} -> {target.value}")


# Global message service instance
_message_service: MessageService | None = None


def get_message_service() -> MessageService:
    """Get the global message service instance."""
    global _message_service
    if _message_service is None:
        _message_service = MessageService()
    return _message_service


def initialize_message_service(
    parent_widget: QWidget, status_bar: StatusBarInterface
) -> MessageService:
    """Initialize the global message service with required components."""
    global _message_service
    _message_service = MessageService(parent_widget)
    _message_service.set_status_bar(status_bar)
    return _message_service


# Convenience functions for common message types
def show_info(message: str, timeout: int = 3000) -> None:
    """Show an informational message."""
    get_message_service().show_info(message, timeout)


def show_success(message: str, timeout: int = 5000) -> None:
    """Show a success message."""
    get_message_service().show_success(message, timeout)


def show_warning(message: str, timeout: int = 5000) -> None:
    """Show a warning message."""
    get_message_service().show_warning(message, timeout)


def show_error(title: str, message: str) -> None:
    """Show an error message."""
    get_message_service().show_error(title, message)


def show_critical(title: str, message: str) -> None:
    """Show a critical error message."""
    get_message_service().show_critical(title, message)


def ask_question(
    title: str,
    message: str,
    buttons: QMessageBox.StandardButton = QMessageBox.StandardButton.Yes
    | QMessageBox.StandardButton.No,
    default_button: QMessageBox.StandardButton = QMessageBox.StandardButton.No,
) -> QMessageBox.StandardButton:
    """Ask a question and return the user's response."""
    return get_message_service().ask_question(title, message, buttons, default_button)
