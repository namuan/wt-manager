"""Preferences dialog for application settings."""

import logging
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QDialogButtonBox,
    QGroupBox,
    QLabel,
    QMessageBox,
    QSizePolicy,
)
from PyQt6.QtCore import pyqtSignal

from ..models.config import UserPreferences


class PreferencesDialog(QDialog):
    """Dialog for configuring application preferences."""

    preferences_changed = pyqtSignal(UserPreferences)

    def __init__(self, current_preferences: UserPreferences, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.current_preferences = current_preferences

        self._setup_ui()
        self._load_current_preferences()
        self._setup_connections()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        self.setWindowTitle("Preferences")
        self.setModal(True)
        self.setMinimumSize(500, 300)
        self.resize(600, 400)

        # Enable automatic resizing
        self.setSizeGripEnabled(True)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Worktree settings group
        worktree_group = QGroupBox("Worktree Settings")
        worktree_group.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        worktree_layout = QFormLayout(worktree_group)
        worktree_layout.setSpacing(8)
        worktree_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        # Base path setting
        base_path_layout = QHBoxLayout()
        base_path_layout.setSpacing(8)

        self.base_path_edit = QLineEdit()
        self.base_path_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.base_path_edit.setPlaceholderText(
            "Select a base directory for all worktrees..."
        )
        self.base_path_edit.setToolTip(
            "Base directory where all new worktrees will be created. "
            "This path will be automatically populated in the Create Worktree dialog."
        )

        self.browse_button = QPushButton("Browse...")
        self.browse_button.setToolTip("Browse for base directory")
        self.browse_button.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )

        base_path_layout.addWidget(
            self.base_path_edit, 1
        )  # Give text edit stretch factor of 1
        base_path_layout.addWidget(
            self.browse_button, 0
        )  # Give button stretch factor of 0

        worktree_layout.addRow("Base Path:", base_path_layout)

        # Add description label
        description_label = QLabel(
            "The base path will be used as the default location for creating new worktrees. "
            "You can still change the path when creating individual worktrees."
        )
        description_label.setWordWrap(True)
        description_label.setStyleSheet("color: #666; font-size: 11px;")
        description_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        worktree_layout.addRow("", description_label)

        layout.addWidget(worktree_group)

        # Add stretch to push buttons to bottom
        layout.addStretch(1)

        # Dialog buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        layout.addWidget(self.button_box)

    def _setup_connections(self) -> None:
        """Set up signal-slot connections."""
        self.browse_button.clicked.connect(self._browse_base_path)
        self.button_box.accepted.connect(self._accept_changes)
        self.button_box.rejected.connect(self.reject)

        # Enable/disable OK button based on validation
        self.base_path_edit.textChanged.connect(self._validate_input)

    def _load_current_preferences(self) -> None:
        """Load current preferences into the UI."""
        if self.current_preferences.worktree_base_path:
            self.base_path_edit.setText(self.current_preferences.worktree_base_path)

        self._validate_input()

    def _browse_base_path(self) -> None:
        """Open file dialog to browse for base path."""
        current_path = self.base_path_edit.text().strip()
        if current_path and Path(current_path).exists():
            start_dir = current_path
        else:
            start_dir = str(Path.home())

        selected_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Base Directory for Worktrees",
            start_dir,
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks,
        )

        if selected_dir:
            self.base_path_edit.setText(selected_dir)

    def _validate_input(self) -> None:
        """Validate the input and enable/disable OK button."""
        base_path = self.base_path_edit.text().strip()

        # OK button should be enabled if:
        # 1. Base path is empty (user wants to clear it), or
        # 2. Base path exists and is a directory
        is_valid = True
        if base_path:
            path = Path(base_path)
            is_valid = path.exists() and path.is_dir()

        ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.setEnabled(is_valid)

        # Update tooltip for validation feedback
        if base_path and not is_valid:
            self.base_path_edit.setToolTip("Path does not exist or is not a directory")
            self.base_path_edit.setStyleSheet("QLineEdit { border: 1px solid red; }")
        else:
            self.base_path_edit.setToolTip(
                "Base directory where all new worktrees will be created. "
                "This path will be automatically populated in the Create Worktree dialog."
            )
            self.base_path_edit.setStyleSheet("")

    def _accept_changes(self) -> None:
        """Accept changes and emit signal with updated preferences."""
        base_path = self.base_path_edit.text().strip()

        # Validate one more time
        if base_path:
            path = Path(base_path)
            if not path.exists():
                QMessageBox.warning(
                    self,
                    "Invalid Path",
                    f"The selected path does not exist:\n{base_path}\n\n"
                    "Please select a valid directory or leave empty to clear the setting.",
                )
                return

            if not path.is_dir():
                QMessageBox.warning(
                    self,
                    "Invalid Path",
                    f"The selected path is not a directory:\n{base_path}\n\n"
                    "Please select a valid directory.",
                )
                return

        # Create updated preferences
        updated_preferences = UserPreferences(
            theme=self.current_preferences.theme,
            auto_refresh_interval=self.current_preferences.auto_refresh_interval,
            show_hidden_files=self.current_preferences.show_hidden_files,
            confirm_destructive_actions=self.current_preferences.confirm_destructive_actions,
            worktree_base_path=base_path if base_path else None,
        )

        self.logger.info(f"Preferences updated - base path: {base_path or 'None'}")
        self.preferences_changed.emit(updated_preferences)
        self.accept()

    def get_base_path(self) -> str:
        """Get the configured base path."""
        return self.base_path_edit.text().strip()
