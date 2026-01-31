"""Command input dialog for Git Worktree Manager."""

import logging
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QStringListModel
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QPushButton,
    QDialogButtonBox,
    QGroupBox,
    QCheckBox,
    QSpinBox,
    QCompleter,
    QMessageBox,
)

from ..services.validation_service import ValidationService


class CommandInputDialog(QDialog):
    """
    Dialog for inputting and executing commands in a worktree context.

    Features:
    - Command input with validation and safety checks
    - Command history and auto-completion
    - Worktree context display
    - Execution timeout configuration
    - Real-time validation feedback
    """

    # Signals
    command_execution_requested = pyqtSignal(
        str, str, int
    )  # command, worktree_path, timeout

    def __init__(
        self,
        worktree_path: str,
        command_history: list[str] = None,
        validation_service: ValidationService = None,
        parent=None,
    ):
        """
        Initialize the command input dialog.

        Args:
            worktree_path: Path to the worktree where command will be executed
            command_history: List of previous commands for auto-completion
            validation_service: Service for command validation
            parent: Parent widget
        """
        super().__init__(parent)
        self.worktree_path = worktree_path

        # Deduplicate history while preserving order
        self.command_history = []
        if command_history:
            seen = set()
            for cmd in command_history:
                if cmd not in seen:
                    self.command_history.append(cmd)
                    seen.add(cmd)

        self.validation_service = validation_service or ValidationService()
        self.logger = logging.getLogger(__name__)

        # Validation timer for debounced validation
        self.validation_timer = QTimer()
        self.validation_timer.setSingleShot(True)
        self.validation_timer.timeout.connect(self._validate_command)

        # Default timeout (5 minutes)
        self.default_timeout = 300

        self._setup_ui()
        self._setup_connections()
        self._setup_auto_completion()
        self._populate_common_commands()

        # Focus on command input
        self.command_input.setFocus()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        self.setWindowTitle("Run Command")
        self.setModal(True)
        self.resize(700, 500)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Worktree context section
        self._create_context_section(layout)

        # Command input section
        self._create_command_section(layout)

        # Options section
        self._create_options_section(layout)

        # Validation section
        self._create_validation_section(layout)

        # Command history section
        self._create_history_section(layout)

        # Buttons
        self._create_buttons(layout)

    def _create_context_section(self, layout: QVBoxLayout) -> None:
        """Create the worktree context display section."""
        context_group = QGroupBox("Execution Context")
        context_layout = QFormLayout(context_group)

        # Worktree path
        worktree_name = Path(self.worktree_path).name
        full_path_label = QLabel(self.worktree_path)
        full_path_label.setStyleSheet("font-family: monospace; color: #666;")
        context_layout.addRow("Worktree:", QLabel(worktree_name))
        context_layout.addRow("Full Path:", full_path_label)

        # Working directory (same as worktree path)
        context_layout.addRow("Working Directory:", QLabel(worktree_name))

        layout.addWidget(context_group)

    def _create_command_section(self, layout: QVBoxLayout) -> None:
        """Create the command input section."""
        command_group = QGroupBox("Command")
        command_layout = QVBoxLayout(command_group)

        # Command input
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("$"))

        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("Enter command to execute...")
        self.command_input.setFont(QFont("Consolas, Monaco, monospace", 10))
        input_layout.addWidget(self.command_input)

        command_layout.addLayout(input_layout)

        # Common commands dropdown
        common_layout = QHBoxLayout()
        common_layout.addWidget(QLabel("Common:"))

        self.common_commands = QComboBox()
        self.common_commands.setEditable(False)
        self.common_commands.setMinimumWidth(200)
        common_layout.addWidget(self.common_commands)

        self.insert_common_btn = QPushButton("Insert")
        self.insert_common_btn.setMaximumWidth(60)
        self.insert_common_btn.setEnabled(False)
        common_layout.addWidget(self.insert_common_btn)

        common_layout.addStretch()
        command_layout.addLayout(common_layout)

        layout.addWidget(command_group)

    def _create_options_section(self, layout: QVBoxLayout) -> None:
        """Create the execution options section."""
        options_group = QGroupBox("Execution Options")
        options_layout = QFormLayout(options_group)

        # Timeout setting
        timeout_layout = QHBoxLayout()
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(10, 3600)  # 10 seconds to 1 hour
        self.timeout_spin.setValue(self.default_timeout)
        self.timeout_spin.setSuffix(" seconds")
        timeout_layout.addWidget(self.timeout_spin)

        self.no_timeout_check = QCheckBox("No timeout")
        self.no_timeout_check.setToolTip("Allow command to run indefinitely")
        timeout_layout.addWidget(self.no_timeout_check)

        timeout_layout.addStretch()
        options_layout.addRow("Timeout:", timeout_layout)

        # Execution mode
        self.background_check = QCheckBox("Run in background")
        self.background_check.setToolTip("Execute command without blocking the UI")
        self.background_check.setChecked(True)
        options_layout.addRow("Mode:", self.background_check)

        layout.addWidget(options_group)

    def _create_validation_section(self, layout: QVBoxLayout) -> None:
        """Create the command validation section."""
        self.validation_group = QGroupBox("Command Validation")
        validation_layout = QVBoxLayout(self.validation_group)

        self.validation_status = QLabel("Enter a command to validate")
        self.validation_status.setWordWrap(True)
        self.validation_status.setStyleSheet("color: #666; font-style: italic;")
        validation_layout.addWidget(self.validation_status)

        self.validation_details = QTextEdit()
        self.validation_details.setMaximumHeight(80)
        self.validation_details.setReadOnly(True)
        self.validation_details.hide()
        validation_layout.addWidget(self.validation_details)

        layout.addWidget(self.validation_group)

    def _create_history_section(self, layout: QVBoxLayout) -> None:
        """Create the command history section."""
        if not self.command_history:
            return

        history_group = QGroupBox("Recent Commands")
        history_layout = QVBoxLayout(history_group)

        self.history_list = QComboBox()
        self.history_list.setEditable(False)
        self.history_list.addItem("Select from history...")
        self.history_list.addItems(self.command_history[:10])  # Show last 10 commands
        history_layout.addWidget(self.history_list)

        layout.addWidget(history_group)

    def _create_buttons(self, layout: QVBoxLayout) -> None:
        """Create dialog buttons."""
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

        # Customize OK button
        self.execute_btn = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.execute_btn.setText("Execute Command")
        self.execute_btn.setEnabled(False)
        self.execute_btn.setStyleSheet(
            "QPushButton { background-color: #2e7d32; color: white; font-weight: bold; }"
        )

        self.button_box.accepted.connect(self._execute_command)
        self.button_box.rejected.connect(self.reject)

        layout.addWidget(self.button_box)

    def _setup_connections(self) -> None:
        """Set up signal-slot connections."""
        # Command input validation
        self.command_input.textChanged.connect(self._on_command_changed)
        self.command_input.returnPressed.connect(self._on_return_pressed)

        # Common commands
        self.common_commands.currentTextChanged.connect(self._on_common_command_changed)
        self.insert_common_btn.clicked.connect(self._insert_common_command)

        # Options
        self.no_timeout_check.toggled.connect(self._on_timeout_check_changed)

        # History
        if hasattr(self, "history_list"):
            self.history_list.currentTextChanged.connect(self._on_history_changed)

    def _setup_auto_completion(self) -> None:
        """Set up auto-completion for command input."""
        if self.command_history:
            completer = QCompleter(self.command_history)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            self.command_input.setCompleter(completer)

    def _populate_common_commands(self) -> None:
        """Populate the common commands dropdown."""
        common_commands = [
            "Select a common command...",
            "git status",
            "git log --oneline -10",
            "git branch -a",
            "git diff",
            "git diff --staged",
            "npm install",
            "npm run build",
            "npm run test",
            "npm run dev",
            "yarn install",
            "yarn build",
            "yarn test",
            "python -m pip install -r requirements.txt",
            "python -m pytest",
            "python manage.py runserver",
            "make",
            "make test",
            "make clean",
            "ls -la",
            "pwd",
            "find . -name '*.py' | head -20",
            "grep -r 'TODO' --include='*.py' .",
        ]

        self.common_commands.addItems(common_commands)

    def _on_command_changed(self, text: str) -> None:
        """Handle command input text changes."""
        # Debounce validation
        self.validation_timer.stop()
        if text.strip():
            self.validation_timer.start(300)  # 300ms delay
        else:
            self._clear_validation()
            self.execute_btn.setEnabled(False)

    def _on_return_pressed(self) -> None:
        """Handle return key press in command input."""
        if self.execute_btn.isEnabled():
            self._execute_command()

    def _on_common_command_changed(self, text: str) -> None:
        """Handle common command selection change."""
        self.insert_common_btn.setEnabled(text and text != "Select a common command...")

    def _insert_common_command(self) -> None:
        """Insert selected common command into input."""
        command = self.common_commands.currentText()
        if command and command != "Select a common command...":
            self.command_input.setText(command)
            self.command_input.setFocus()

    def _on_timeout_check_changed(self, checked: bool) -> None:
        """Handle timeout checkbox change."""
        self.timeout_spin.setEnabled(not checked)

    def _on_history_changed(self, text: str) -> None:
        """Handle history selection change."""
        if not text or text == "Select from history...":
            return

        # Auto-populate command input directly from selection.
        self.command_input.setText(text)
        self.command_input.setFocus()

    def _validate_command(self) -> None:
        """Validate the entered command."""
        command = self.command_input.text().strip()
        if not command:
            self._clear_validation()
            return

        try:
            # Validate command safety
            validation_result = self.validation_service.validate_command_safety(command)

            if validation_result.is_valid:
                self._show_validation_success()
            else:
                self._show_validation_error(validation_result.message)

        except Exception as e:
            self.logger.error(f"Error validating command: {e}")
            self._show_validation_error(f"Validation error: {e}")

    def _show_validation_success(self) -> None:
        """Show successful validation."""
        self.validation_status.setText("✓ Command is valid and safe to execute")
        self.validation_status.setStyleSheet("color: #2e7d32; font-weight: bold;")
        self.validation_details.hide()
        self.execute_btn.setEnabled(True)

    def _show_validation_error(self, message: str) -> None:
        """Show validation error."""
        self.validation_status.setText(f"✗ {message}")
        self.validation_status.setStyleSheet("color: #d32f2f; font-weight: bold;")

        # Show additional details if available
        if len(message) > 100:
            self.validation_details.setPlainText(message)
            self.validation_details.show()
        else:
            self.validation_details.hide()

        self.execute_btn.setEnabled(False)

    def _clear_validation(self) -> None:
        """Clear validation display."""
        self.validation_status.setText("Enter a command to validate")
        self.validation_status.setStyleSheet("color: #666; font-style: italic;")
        self.validation_details.hide()

    def _execute_command(self) -> None:
        """Execute the command."""
        command = self.command_input.text().strip()
        if not command:
            return

        # Get timeout value
        if self.no_timeout_check.isChecked():
            timeout = 0  # No timeout
        else:
            timeout = self.timeout_spin.value()

        # Confirm execution for potentially dangerous commands
        if self._is_potentially_dangerous_command(command):
            reply = QMessageBox.question(
                self,
                "Confirm Command Execution",
                f"Are you sure you want to execute this command?\n\n{command}\n\n"
                f"This command may modify files or system state.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        # Emit signal to execute command
        self.command_execution_requested.emit(command, self.worktree_path, timeout)
        self.accept()

    def _is_potentially_dangerous_command(self, command: str) -> bool:
        """Check if command is potentially dangerous and needs confirmation."""
        dangerous_patterns = [
            "rm ",
            "del ",
            "rmdir",
            "format",
            "fdisk",
            "git reset --hard",
            "git clean -f",
            "git push --force",
            "sudo ",
            "su ",
            "chmod 777",
            "chown ",
            "npm uninstall",
            "pip uninstall",
            "yarn remove",
            "make clean",
            "make distclean",
        ]

        command_lower = command.lower()
        return any(pattern in command_lower for pattern in dangerous_patterns)

    def get_command(self) -> str:
        """Get the entered command."""
        return self.command_input.text().strip()

    def get_timeout(self) -> int:
        """Get the timeout value (0 for no timeout)."""
        if self.no_timeout_check.isChecked():
            return 0
        return self.timeout_spin.value()

    def set_command(self, command: str) -> None:
        """Set the command input text."""
        self.command_input.setText(command)

    def add_to_history(self, command: str) -> None:
        """Add a command to the history for future auto-completion."""
        if not command:
            return

        # Remove existing occurrence if present to move it to the top
        if command in self.command_history:
            self.command_history.remove(command)

        self.command_history.insert(0, command)
        # Keep only last 50 commands
        self.command_history = self.command_history[:50]

        # Update auto-completion
        if self.command_input.completer():
            model = QStringListModel(self.command_history)
            self.command_input.completer().setModel(model)
