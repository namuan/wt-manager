"""Status indicator widgets for showing operation feedback."""

from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QScrollArea,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor

from .progress_manager import OperationProgress, ProgressManager


class StatusIndicator(QWidget):
    """A small status indicator widget that can show different states."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedSize(20, 20)
        self._status = "idle"
        self._animation = QPropertyAnimation(self, b"windowOpacity")
        self._setup_animation()

    def _setup_animation(self):
        """Set up pulsing animation for active states."""
        self._animation.setDuration(1000)
        self._animation.setStartValue(0.3)
        self._animation.setEndValue(1.0)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._animation.setLoopCount(-1)  # Infinite loop

    def set_status(self, status: str):
        """Set the status and update appearance."""
        self._status = status
        self.update()

        # Start/stop animation based on status
        if status in ["working", "loading"]:
            self._animation.start()
        else:
            self._animation.stop()
            self.setWindowOpacity(1.0)

    def paintEvent(self, event):
        """Paint the status indicator."""
        from PyQt6.QtGui import QPainter, QBrush

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Choose color based on status
        if self._status == "success":
            color = QColor(34, 197, 94)  # Green
        elif self._status == "error":
            color = QColor(239, 68, 68)  # Red
        elif self._status == "warning":
            color = QColor(245, 158, 11)  # Yellow
        elif self._status == "working":
            color = QColor(59, 130, 246)  # Blue
        else:  # idle
            color = QColor(156, 163, 175)  # Gray

        # Draw circle
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, 16, 16)


class OperationStatusWidget(QWidget):
    """Widget showing status of a single operation."""

    cancel_requested = pyqtSignal(str)  # operation_id

    def __init__(self, operation: OperationProgress, parent: QWidget | None = None):
        super().__init__(parent)
        self.operation = operation
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Set up the widget UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)

        # Status indicator
        self.status_indicator = StatusIndicator()
        layout.addWidget(self.status_indicator)

        # Description label
        self.description_label = QLabel(self.operation.description)
        self.description_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.description_label, 1)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(self.operation.progress)
        self.progress_bar.setFixedHeight(15)
        layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel(self.operation.status)
        self.status_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.status_label)

        # Cancel button (if operation is not completed)
        if not self.operation.is_completed:
            self.cancel_button = QPushButton("✕")
            self.cancel_button.setFixedSize(20, 20)
            self.cancel_button.setStyleSheet("""
                QPushButton {
                    border: none;
                    background-color: #f3f4f6;
                    border-radius: 10px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #ef4444;
                    color: white;
                }
            """)
            self.cancel_button.clicked.connect(
                lambda: self.cancel_requested.emit(self.operation.operation_id)
            )
            layout.addWidget(self.cancel_button)

        # Set initial status
        self._update_status_indicator()

    def _connect_signals(self):
        """Connect operation signals."""
        self.operation.progress_changed.connect(self.progress_bar.setValue)
        self.operation.status_changed.connect(self.status_label.setText)
        self.operation.completed.connect(self._on_completed)

    def _update_status_indicator(self):
        """Update the status indicator based on operation state."""
        if self.operation.is_completed:
            if self.operation.is_cancelled:
                self.status_indicator.set_status("warning")
            else:
                # Determine success/failure from progress or status
                if self.operation.progress == 100:
                    self.status_indicator.set_status("success")
                else:
                    self.status_indicator.set_status("error")
        else:
            self.status_indicator.set_status("working")

    def _on_completed(self, success: bool):
        """Handle operation completion."""
        if success:
            self.status_indicator.set_status("success")
        else:
            self.status_indicator.set_status("error")

        # Hide cancel button
        if hasattr(self, "cancel_button"):
            self.cancel_button.hide()

        # Auto-remove after delay
        QTimer.singleShot(5000, self._fade_out)

    def _fade_out(self):
        """Fade out the widget."""
        self.setEnabled(False)
        self.setStyleSheet("background-color: #f9fafb; opacity: 0.5;")
        QTimer.singleShot(2000, lambda: self.setVisible(False))


class OperationStatusPanel(QWidget):
    """Panel showing all active operations."""

    def __init__(
        self, progress_manager: ProgressManager, parent: QWidget | None = None
    ):
        super().__init__(parent)
        self.progress_manager = progress_manager
        self._operation_widgets: dict = {}
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Set up the panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header
        header_layout = QHBoxLayout()

        title_label = QLabel("Operations")
        title_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #374151;")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        # Clear completed button
        self.clear_button = QPushButton("Clear Completed")
        self.clear_button.setStyleSheet("""
            QPushButton {
                border: 1px solid #d1d5db;
                background-color: #f9fafb;
                padding: 2px 8px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #f3f4f6;
            }
        """)
        self.clear_button.clicked.connect(self._clear_completed)
        header_layout.addWidget(self.clear_button)

        layout.addLayout(header_layout)

        # Scroll area for operations
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.operations_widget = QWidget()
        self.operations_layout = QVBoxLayout(self.operations_widget)
        self.operations_layout.setContentsMargins(0, 0, 0, 0)
        self.operations_layout.addStretch()

        scroll_area.setWidget(self.operations_widget)
        layout.addWidget(scroll_area)

        # Initially hidden
        self.setVisible(False)

    def _connect_signals(self):
        """Connect progress manager signals."""
        self.progress_manager.operation_started.connect(self._on_operation_started)
        self.progress_manager.operation_completed.connect(self._on_operation_completed)

    def _on_operation_started(self, operation_id: str, description: str):
        """Handle new operation started."""
        operation = self.progress_manager.get_operation(operation_id)
        if operation:
            widget = OperationStatusWidget(operation)
            widget.cancel_requested.connect(self.progress_manager.cancel_operation)

            # Insert before stretch
            self.operations_layout.insertWidget(
                self.operations_layout.count() - 1, widget
            )
            self._operation_widgets[operation_id] = widget

            # Show panel if hidden
            self.setVisible(True)

    def _on_operation_completed(self, operation_id: str, success: bool):
        """Handle operation completion."""
        # Widget will handle its own completion display
        pass

    def _clear_completed(self):
        """Clear all completed operation widgets."""
        to_remove = []
        for op_id, widget in self._operation_widgets.items():
            if widget.operation.is_completed:
                widget.setVisible(False)
                self.operations_layout.removeWidget(widget)
                widget.deleteLater()
                to_remove.append(op_id)

        for op_id in to_remove:
            del self._operation_widgets[op_id]

        # Hide panel if no operations
        if not self._operation_widgets:
            self.setVisible(False)
