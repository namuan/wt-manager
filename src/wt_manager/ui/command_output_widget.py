"""Enhanced command output widget for Git Worktree Manager."""

import logging

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QTextCursor, QTextCharFormat, QColor
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QLabel,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QFrame,
)

from ..models.command_execution import CommandExecution, CommandStatus


class CommandExecutionWidget(QWidget):
    """Widget for displaying a single command execution with status and output."""

    def __init__(self, execution: CommandExecution, parent=None):
        super().__init__(parent)
        self.execution = execution
        self.logger = logging.getLogger(__name__)

        self._setup_ui()
        self._update_display()

    def _setup_ui(self) -> None:
        """Set up the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)

        # Header with command info and status
        header_layout = QHBoxLayout()

        # Command display
        self.command_label = QLabel()
        self.command_label.setFont(QFont("Consolas, Monaco, monospace", 9))
        self.command_label.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(self.command_label)

        header_layout.addStretch()

        # Status indicator
        self.status_label = QLabel()
        self.status_label.setMinimumWidth(100)
        header_layout.addWidget(self.status_label)

        # Duration
        self.duration_label = QLabel()
        self.duration_label.setMinimumWidth(80)
        self.duration_label.setStyleSheet("color: #666;")
        header_layout.addWidget(self.duration_label)

        layout.addLayout(header_layout)

        # Progress bar for running commands
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.setMaximumHeight(4)
        self.progress_bar.setVisible(False)  # Explicitly set to False initially
        layout.addWidget(self.progress_bar)

        # Output area
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setFont(QFont("Consolas, Monaco, monospace", 8))
        self.output_text.setMaximumHeight(200)
        self.output_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3e3e3e;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.output_text)

        # Update timer for running commands
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_display)

    def _update_display(self) -> None:
        """Update the display with current execution state."""
        # Update command display
        self.command_label.setText(f"$ {self.execution.get_command_display(60)}")

        # Update status
        status_text = self.execution.get_status_display()
        self.status_label.setText(status_text)

        # Style status based on execution state
        if self.execution.is_running():
            self.status_label.setStyleSheet("color: #2196f3; font-weight: bold;")
            self.progress_bar.setVisible(True)
            self.progress_bar.show()  # Explicitly call show() as well
            if not self.update_timer.isActive():
                self.update_timer.start(1000)  # Update every second
        elif self.execution.is_successful():
            self.status_label.setStyleSheet("color: #4caf50; font-weight: bold;")
            self.progress_bar.setVisible(False)
            self.progress_bar.hide()  # Explicitly call hide() as well
            self.update_timer.stop()
        elif self.execution.status == CommandStatus.FAILED:
            self.status_label.setStyleSheet("color: #f44336; font-weight: bold;")
            self.progress_bar.setVisible(False)
            self.progress_bar.hide()  # Explicitly call hide() as well
            self.update_timer.stop()
        elif self.execution.status == CommandStatus.CANCELLED:
            self.status_label.setStyleSheet("color: #ff9800; font-weight: bold;")
            self.progress_bar.setVisible(False)
            self.progress_bar.hide()  # Explicitly call hide() as well
            self.update_timer.stop()
        else:
            self.status_label.setStyleSheet("color: #666;")
            self.progress_bar.setVisible(False)
            self.progress_bar.hide()  # Explicitly call hide() as well

        # Update duration
        duration_text = self.execution.get_duration_display()
        self.duration_label.setText(duration_text)

        # Update output
        formatted_output = self.execution.get_formatted_output()
        if formatted_output != self.output_text.toPlainText():
            self.output_text.setPlainText(formatted_output)
            # Auto-scroll to bottom
            cursor = self.output_text.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.output_text.setTextCursor(cursor)

    def append_output(self, text: str, is_error: bool = False) -> None:
        """
        Append output text to the display.

        Args:
            text: Text to append
            is_error: Whether this is error output (for styling)
        """
        cursor = self.output_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        if is_error:
            # Style error text differently
            format = QTextCharFormat()
            format.setForeground(QColor("#f44336"))
            cursor.setCharFormat(format)

        cursor.insertText(text)

        # Reset format
        cursor.setCharFormat(QTextCharFormat())

        # Auto-scroll to bottom
        self.output_text.setTextCursor(cursor)

    def update_execution(self, execution: CommandExecution) -> None:
        """Update with new execution data."""
        self.execution = execution
        self._update_display()


class CommandOutputPanel(QWidget):
    """
    Enhanced command output panel with real-time display and status indicators.

    Features:
    - Real-time command output streaming
    - Multiple command execution tracking
    - Command status indicators and progress feedback
    - Command cancellation controls
    - Output formatting and syntax highlighting
    """

    # Signals
    cancel_command_requested = pyqtSignal(str)  # execution_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)

        # Active execution widgets
        self._execution_widgets: dict[str, CommandExecutionWidget] = {}

        self._setup_ui()
        self._setup_connections()

    def _setup_ui(self) -> None:
        """Set up the panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Header with title and controls
        header_layout = QHBoxLayout()

        self.title_label = QLabel("Command Output")
        self.title_label.setFont(QFont("", 10, QFont.Weight.Bold))
        header_layout.addWidget(self.title_label)

        header_layout.addStretch()

        # Active commands counter
        self.active_count_label = QLabel("No active commands")
        self.active_count_label.setStyleSheet("color: #666; font-size: 9px;")
        header_layout.addWidget(self.active_count_label)

        # Controls
        self.clear_all_btn = QPushButton("Clear All")
        self.clear_all_btn.setMaximumWidth(70)
        self.clear_all_btn.setToolTip("Clear all command output")
        header_layout.addWidget(self.clear_all_btn)

        self.cancel_all_btn = QPushButton("Cancel All")
        self.cancel_all_btn.setMaximumWidth(70)
        self.cancel_all_btn.setToolTip("Cancel all running commands")
        self.cancel_all_btn.setEnabled(False)
        self.cancel_all_btn.setStyleSheet(
            "QPushButton { background-color: #d32f2f; color: white; }"
        )
        header_layout.addWidget(self.cancel_all_btn)

        layout.addLayout(header_layout)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)

        # Scrollable area for command executions
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        # Container widget for executions
        self.executions_container = QWidget()
        self.executions_layout = QVBoxLayout(self.executions_container)
        self.executions_layout.setContentsMargins(0, 0, 0, 0)
        self.executions_layout.setSpacing(8)
        self.executions_layout.addStretch()  # Push executions to top

        self.scroll_area.setWidget(self.executions_container)
        layout.addWidget(self.scroll_area)

        # Status bar
        status_layout = QHBoxLayout()

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #666; font-size: 9px;")
        status_layout.addWidget(self.status_label)

        status_layout.addStretch()

        self.total_executions_label = QLabel("0 total executions")
        self.total_executions_label.setStyleSheet("color: #666; font-size: 9px;")
        status_layout.addWidget(self.total_executions_label)

        layout.addLayout(status_layout)

    def _setup_connections(self) -> None:
        """Set up signal connections."""
        self.clear_all_btn.clicked.connect(self.clear_all_output)
        self.cancel_all_btn.clicked.connect(self._cancel_all_commands)

    def add_execution(self, execution: CommandExecution) -> None:
        """
        Add a new command execution to the panel.

        Args:
            execution: CommandExecution instance to track
        """
        if execution.id in self._execution_widgets:
            # Update existing widget
            self._execution_widgets[execution.id].update_execution(execution)
            return

        # Create new execution widget
        widget = CommandExecutionWidget(execution)
        self._execution_widgets[execution.id] = widget

        # Insert at the top (before the stretch)
        self.executions_layout.insertWidget(0, widget)

        # Update counters
        self._update_counters()

        # Auto-scroll to show new execution
        self.scroll_area.ensureWidgetVisible(widget)

        self.logger.debug(f"Added execution widget: {execution.id}")

    def update_execution(self, execution: CommandExecution) -> None:
        """
        Update an existing command execution.

        Args:
            execution: Updated CommandExecution instance
        """
        widget = self._execution_widgets.get(execution.id)
        if widget:
            widget.update_execution(execution)
            self._update_counters()

    def remove_execution(self, execution_id: str) -> None:
        """
        Remove a command execution from the panel.

        Args:
            execution_id: ID of the execution to remove
        """
        widget = self._execution_widgets.pop(execution_id, None)
        if widget:
            self.executions_layout.removeWidget(widget)
            widget.deleteLater()
            self._update_counters()
            self.logger.debug(f"Removed execution widget: {execution_id}")

    def append_output(
        self, execution_id: str, text: str, is_error: bool = False
    ) -> None:
        """
        Append output to a specific execution.

        Args:
            execution_id: ID of the execution
            text: Output text to append
            is_error: Whether this is error output
        """
        widget = self._execution_widgets.get(execution_id)
        if widget:
            widget.append_output(text, is_error)

    def clear_all_output(self) -> None:
        """Clear all command output."""
        for widget in list(self._execution_widgets.values()):
            self.executions_layout.removeWidget(widget)
            widget.deleteLater()

        self._execution_widgets.clear()
        self._update_counters()
        self.status_label.setText("Output cleared")

        self.logger.info("Cleared all command output")

    def get_active_executions(self) -> list[str]:
        """
        Get list of active execution IDs.

        Returns:
            List of execution IDs that are currently running
        """
        active = []
        for execution_id, widget in self._execution_widgets.items():
            if widget.execution.is_running():
                active.append(execution_id)
        return active

    def set_status(self, status: str) -> None:
        """Set the status message."""
        self.status_label.setText(status)

    def _update_counters(self) -> None:
        """Update the execution counters."""
        total = len(self._execution_widgets)
        active = len(self.get_active_executions())

        # Update active count
        if active == 0:
            self.active_count_label.setText("No active commands")
            self.cancel_all_btn.setEnabled(False)
        elif active == 1:
            self.active_count_label.setText("1 active command")
            self.cancel_all_btn.setEnabled(True)
        else:
            self.active_count_label.setText(f"{active} active commands")
            self.cancel_all_btn.setEnabled(True)

        # Update total count
        if total == 0:
            self.total_executions_label.setText("0 total executions")
        elif total == 1:
            self.total_executions_label.setText("1 total execution")
        else:
            self.total_executions_label.setText(f"{total} total executions")

    def _cancel_all_commands(self) -> None:
        """Cancel all running commands."""
        active_executions = self.get_active_executions()
        for execution_id in active_executions:
            self.cancel_command_requested.emit(execution_id)

        if active_executions:
            self.set_status(f"Cancelling {len(active_executions)} commands...")
            self.logger.info(
                f"Requested cancellation of {len(active_executions)} commands"
            )

    def cleanup(self) -> None:
        """Clean up resources."""
        for widget in self._execution_widgets.values():
            if hasattr(widget, "update_timer"):
                widget.update_timer.stop()

        self._execution_widgets.clear()
