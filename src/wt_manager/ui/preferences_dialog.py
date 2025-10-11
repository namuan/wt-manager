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
    QListWidget,
    QListWidgetItem,
)
from PyQt6.QtCore import Qt, pyqtSignal

from ..models.config import UserPreferences, CustomApplication


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

        # Custom applications group
        apps_group = QGroupBox("Custom Applications")
        apps_group.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        apps_layout = QVBoxLayout(apps_group)

        # Applications list
        self.apps_list = QListWidget()
        self.apps_list.setMaximumHeight(150)
        self.apps_list.setToolTip("Custom applications for opening worktrees")
        apps_layout.addWidget(self.apps_list)

        # Buttons for managing applications
        apps_buttons_layout = QHBoxLayout()

        self.add_app_btn = QPushButton("Add")
        self.add_app_btn.setToolTip("Add a new custom application")
        apps_buttons_layout.addWidget(self.add_app_btn)

        self.edit_app_btn = QPushButton("Edit")
        self.edit_app_btn.setToolTip("Edit selected application")
        self.edit_app_btn.setEnabled(False)
        apps_buttons_layout.addWidget(self.edit_app_btn)

        self.remove_app_btn = QPushButton("Remove")
        self.remove_app_btn.setToolTip("Remove selected application")
        self.remove_app_btn.setEnabled(False)
        apps_buttons_layout.addWidget(self.remove_app_btn)

        apps_buttons_layout.addStretch()
        apps_layout.addLayout(apps_buttons_layout)

        # Description
        apps_description = QLabel(
            "Custom applications allow you to open worktrees with your preferred editors or tools. "
            "Use %PATH% as a placeholder for the worktree directory path."
        )
        apps_description.setWordWrap(True)
        apps_description.setStyleSheet("color: #666; font-size: 11px;")
        apps_layout.addWidget(apps_description)

        layout.addWidget(apps_group)

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

        # Custom applications connections
        self.add_app_btn.clicked.connect(self._add_application)
        self.edit_app_btn.clicked.connect(self._edit_application)
        self.remove_app_btn.clicked.connect(self._remove_application)
        self.apps_list.itemSelectionChanged.connect(self._on_app_selection_changed)

    def _load_current_preferences(self) -> None:
        """Load current preferences into the UI."""
        if self.current_preferences.worktree_base_path:
            self.base_path_edit.setText(self.current_preferences.worktree_base_path)

        # Load custom applications
        self.apps_list.clear()
        for app in self.current_preferences.custom_applications:
            item = QListWidgetItem(f"{app.name}: {app.command_template}")
            item.setData(Qt.ItemDataRole.UserRole, app)
            self.apps_list.addItem(item)

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

        # Collect custom applications from the list
        custom_applications = []
        for i in range(self.apps_list.count()):
            item = self.apps_list.item(i)
            app = item.data(Qt.ItemDataRole.UserRole)
            if app:
                custom_applications.append(app)

        # Create updated preferences
        updated_preferences = UserPreferences(
            theme=self.current_preferences.theme,
            auto_refresh_interval=self.current_preferences.auto_refresh_interval,
            show_hidden_files=self.current_preferences.show_hidden_files,
            confirm_destructive_actions=self.current_preferences.confirm_destructive_actions,
            worktree_base_path=base_path if base_path else None,
            custom_applications=custom_applications,
        )

        self.logger.info(f"Preferences updated - base path: {base_path or 'None'}")
        self.preferences_changed.emit(updated_preferences)
        self.accept()

    def get_base_path(self) -> str:
        """Get the configured base path."""
        return self.base_path_edit.text().strip()

    def _on_app_selection_changed(self) -> None:
        """Handle application selection changes."""
        has_selection = len(self.apps_list.selectedItems()) > 0
        self.edit_app_btn.setEnabled(has_selection)
        self.remove_app_btn.setEnabled(has_selection)

    def _add_application(self) -> None:
        """Add a new custom application."""
        app = self._show_application_dialog()
        if app:
            # Check for duplicate names
            for i in range(self.apps_list.count()):
                existing_item = self.apps_list.item(i)
                existing_app = existing_item.data(Qt.ItemDataRole.UserRole)
                if existing_app and existing_app.name == app.name:
                    QMessageBox.warning(
                        self,
                        "Duplicate Name",
                        f"An application with the name '{app.name}' already exists.\n\n"
                        "Please choose a different name.",
                    )
                    return

            item = QListWidgetItem(f"{app.name}: {app.command_template}")
            item.setData(Qt.ItemDataRole.UserRole, app)
            self.apps_list.addItem(item)

    def _edit_application(self) -> None:
        """Edit the selected custom application."""
        current_item = self.apps_list.currentItem()
        if not current_item:
            return

        current_app = current_item.data(Qt.ItemDataRole.UserRole)
        if not current_app:
            return

        app = self._show_application_dialog(current_app)
        if app:
            # Check for duplicate names (excluding current app)
            for i in range(self.apps_list.count()):
                item = self.apps_list.item(i)
                if item != current_item:
                    existing_app = item.data(Qt.ItemDataRole.UserRole)
                    if existing_app and existing_app.name == app.name:
                        QMessageBox.warning(
                            self,
                            "Duplicate Name",
                            f"An application with the name '{app.name}' already exists.\n\n"
                            "Please choose a different name.",
                        )
                        return

            current_item.setText(f"{app.name}: {app.command_template}")
            current_item.setData(Qt.ItemDataRole.UserRole, app)

    def _remove_application(self) -> None:
        """Remove the selected custom application."""
        current_item = self.apps_list.currentItem()
        if not current_item:
            return

        app = current_item.data(Qt.ItemDataRole.UserRole)
        if not app:
            return

        reply = QMessageBox.question(
            self,
            "Remove Application",
            f"Are you sure you want to remove the application '{app.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            row = self.apps_list.row(current_item)
            self.apps_list.takeItem(row)

    def _show_application_dialog(
        self, existing_app: CustomApplication = None
    ) -> CustomApplication | None:
        """Show dialog for adding/editing an application."""
        dialog = self._create_application_dialog(existing_app)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return self._extract_application_from_dialog(dialog)
        return None

    def _create_application_dialog(
        self, existing_app: CustomApplication = None
    ) -> QDialog:
        """Create the application dialog with all UI elements."""
        dialog = QDialog(self)
        dialog.setWindowTitle(
            "Add Application" if existing_app is None else "Edit Application"
        )
        dialog.setModal(True)
        dialog.resize(500, 200)

        layout = QVBoxLayout(dialog)
        self._setup_application_dialog_ui(layout, dialog, existing_app)
        self._setup_application_dialog_connections(dialog)

        return dialog

    def _setup_application_dialog_ui(
        self,
        layout: QVBoxLayout,
        dialog: QDialog,
        existing_app: CustomApplication = None,
    ):
        """Set up the UI elements for the application dialog."""
        # Application selection
        app_layout = QVBoxLayout()
        app_label = QLabel("Select Application:")
        app_layout.addWidget(app_label)

        app_path_layout = QHBoxLayout()
        app_path_edit = QLineEdit()
        app_path_edit.setPlaceholderText("Browse for application executable...")
        self._populate_app_path_edit(app_path_edit, existing_app)

        app_path_layout.addWidget(app_path_edit)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(lambda: self._browse_application(app_path_edit))
        app_path_layout.addWidget(browse_btn)

        app_layout.addLayout(app_path_layout)
        layout.addLayout(app_layout)

        # Name input (auto-populated from application name)
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Name:"))
        name_edit = QLineEdit()
        if existing_app:
            name_edit.setText(existing_app.name)
        name_layout.addWidget(name_edit)
        layout.addLayout(name_layout)

        # Command template preview
        cmd_layout = QVBoxLayout()
        cmd_label = QLabel("Command Preview:")
        cmd_layout.addWidget(cmd_label)

        cmd_preview = QLineEdit()
        cmd_preview.setReadOnly(True)
        cmd_preview.setStyleSheet("background-color: #f5f5f5; color: #666;")
        cmd_layout.addWidget(cmd_preview)
        layout.addLayout(cmd_layout)

        # Help text
        help_label = QLabel(
            "The command will automatically include %PATH% as the worktree directory."
        )
        help_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(help_label)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(button_box)

        # Store references for connections
        dialog.app_path_edit = app_path_edit
        dialog.name_edit = name_edit
        dialog.cmd_preview = cmd_preview
        dialog.button_box = button_box

    def _populate_app_path_edit(
        self, app_path_edit: QLineEdit, existing_app: CustomApplication = None
    ):
        """Populate the app path edit field from existing app."""
        if not existing_app:
            return

        cmd = existing_app.command_template
        if cmd.startswith('"') and '"' in cmd[1:]:
            # Handle quoted paths like "C:\Program Files\app.exe" "%PATH%"
            end_quote = cmd.find('"', 1)
            if end_quote > 0:
                app_path_edit.setText(cmd[1:end_quote])
        elif " " in cmd:
            # Handle unquoted paths like /usr/bin/code %PATH%
            app_path_edit.setText(cmd.split(" ")[0])
        else:
            # Single command without spaces
            app_path_edit.setText(cmd.replace(" %PATH%", "").replace("%PATH%", ""))

    def _setup_application_dialog_connections(self, dialog: QDialog):
        """Set up connections for the application dialog."""
        app_path_edit = dialog.app_path_edit
        name_edit = dialog.name_edit
        cmd_preview = dialog.cmd_preview
        button_box = dialog.button_box

        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)

        # Update preview and validation
        def update_preview():
            self._update_command_preview(
                app_path_edit, name_edit, cmd_preview, button_box
            )

        def validate():
            self._validate_application_dialog(name_edit, app_path_edit, button_box)

        app_path_edit.textChanged.connect(update_preview)
        name_edit.textChanged.connect(validate)

        # Initial update
        update_preview()

    def _update_command_preview(
        self,
        app_path_edit: QLineEdit,
        name_edit: QLineEdit,
        cmd_preview: QLineEdit,
        button_box: QDialogButtonBox,
    ):
        """Update the command preview and handle auto-population."""
        app_path = app_path_edit.text().strip()
        if app_path:
            # Auto-populate name if empty
            if not name_edit.text().strip():
                import os

                name_edit.setText(os.path.splitext(os.path.basename(app_path))[0])

            # Generate command template
            cmd_template = self._generate_command_template(app_path)
            cmd_preview.setText(cmd_template)
        else:
            cmd_preview.clear()

        self._validate_application_dialog(name_edit, app_path_edit, button_box)

    def _generate_command_template(self, app_path: str) -> str:
        """Generate the command template for the application path."""
        if " " in app_path or not app_path.startswith("/"):
            # Quote paths with spaces or relative paths
            return f'"{app_path}" "%PATH%"'
        else:
            return f'{app_path} "%PATH%"'

    def _validate_application_dialog(
        self,
        name_edit: QLineEdit,
        app_path_edit: QLineEdit,
        button_box: QDialogButtonBox,
    ):
        """Validate the application dialog inputs."""
        app_path = app_path_edit.text().strip()
        name = name_edit.text().strip()
        ok_btn = button_box.button(QDialogButtonBox.StandardButton.Ok)
        ok_btn.setEnabled(bool(app_path and name))

    def _extract_application_from_dialog(
        self, dialog: QDialog
    ) -> CustomApplication | None:
        """Extract the application data from the dialog."""
        app_path = dialog.app_path_edit.text().strip()
        name = dialog.name_edit.text().strip()
        cmd_template = dialog.cmd_preview.text()

        if app_path and name and cmd_template:
            return CustomApplication(name=name, command_template=cmd_template)
        return None

    def _browse_application(self, path_edit: QLineEdit) -> None:
        """Browse for an application executable."""
        current_path = path_edit.text().strip()

        # Set default directory based on platform
        import platform

        system = platform.system()

        if system == "Darwin":  # macOS
            default_dir = "/Applications"
        elif system == "Windows":
            default_dir = "C:\\Program Files"
        else:  # Linux
            default_dir = "/usr/bin"

        if current_path:
            from pathlib import Path

            path_obj = Path(current_path)
            if path_obj.exists() and path_obj.parent.exists():
                default_dir = str(path_obj.parent)

        # Open file dialog
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Application",
            default_dir,
            "All Files (*)",  # Allow selection of any executable file
        )

        if file_path:
            path_edit.setText(file_path)
