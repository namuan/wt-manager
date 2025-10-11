"""Combined dialog for project health and worktree creation."""

from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..models.project import Project, ProjectStatus
from ..services.message_service import get_message_service


class ProjectActionDialog(QDialog):
    """Combined dialog for viewing project health and creating worktrees."""

    # Signals
    create_worktree_requested = pyqtSignal(str, dict)  # project_id, config

    def __init__(
        self,
        project: Project,
        health_data: dict,
        available_branches: list[str],
        base_path: str = None,
        parent=None,
    ):
        super().__init__(parent)
        self.project = project
        self.health_data = health_data
        self.available_branches = available_branches
        self.base_path = base_path

        self.setWindowTitle(f"Project Actions - {project.get_display_name()}")
        self.setModal(True)
        self.resize(800, 500)

        # Validation timer for worktree creation
        self.validation_timer = QTimer()
        self.validation_timer.setSingleShot(True)
        self.validation_timer.timeout.connect(self._validate_worktree_inputs)

        self._setup_ui()
        self._setup_connections()

    def _setup_ui(self):
        """Set up the dialog UI with combined view."""
        from PyQt6.QtWidgets import QScrollArea

        layout = QVBoxLayout(self)

        # Create scroll area for the content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Create container widget for scroll area
        container = QWidget()
        scroll_area.setWidget(container)

        # Main content layout
        content_layout = QVBoxLayout(container)
        content_layout.setSpacing(10)

        # Health section
        self._create_health_section(content_layout)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        content_layout.addWidget(separator)

        # Worktree creation section
        self._create_worktree_section(content_layout)

        layout.addWidget(scroll_area)

        # Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _create_health_section(self, layout: QVBoxLayout):
        """Create the project health section."""
        # Combined project info and health
        info_group = QGroupBox(self.project.path)
        info_layout = QVBoxLayout(info_group)

        # Project info in single row
        info_row = QHBoxLayout()

        name_label = QLabel(f"Name: {self.project.get_display_name()}")
        info_row.addWidget(name_label)

        status_label = QLabel("Status:")
        info_row.addWidget(status_label)
        info_row.addWidget(self._create_status_label(self.project.status))

        health_label = QLabel("Health:")
        info_row.addWidget(health_label)
        overall_status = self.health_data.get("overall_status", "unknown")
        info_row.addWidget(self._create_health_status_label(overall_status))

        info_row.addStretch()
        info_layout.addLayout(info_row)

        # Compact stats
        stats_text = f"Branches: {self.health_data.get('branch_count', 'N/A')} | Worktrees: {self.health_data.get('worktree_count', 'N/A')}"
        stats_label = QLabel(stats_text)
        stats_label.setStyleSheet("color: #666;")
        info_layout.addWidget(stats_label)

        layout.addWidget(info_group)
        info_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        # Issues and warnings inline
        issues_warnings = []
        if self.health_data.get("issues"):
            issues_warnings.extend(
                [f"• Issue: {issue}" for issue in self.health_data["issues"]]
            )
        if self.health_data.get("warnings"):
            issues_warnings.extend(
                [f"• Warning: {warning}" for warning in self.health_data["warnings"]]
            )

        if issues_warnings:
            issues_group = QGroupBox("Issues & Warnings")
            issues_layout = QVBoxLayout(issues_group)
            for item in issues_warnings:
                item_label = QLabel(item)
                item_label.setWordWrap(True)
                if "Issue:" in item:
                    item_label.setStyleSheet("color: red;")
                else:
                    item_label.setStyleSheet("color: orange;")
                issues_layout.addWidget(item_label)
            layout.addWidget(issues_group)

    def _create_worktree_section(self, layout: QVBoxLayout):
        """Create the worktree creation section."""
        # Worktree configuration
        config_group = QGroupBox("Create New Worktree")
        config_layout = QVBoxLayout(config_group)

        # Worktree path section in single row
        path_layout = QHBoxLayout()
        path_label = QLabel("Worktree Path:")
        path_layout.addWidget(path_label)

        self.worktree_path_edit = QLineEdit()
        self.worktree_path_edit.setPlaceholderText("Enter worktree directory path...")
        path_layout.addWidget(self.worktree_path_edit, 1)

        self.worktree_browse_btn = QPushButton("Browse...")
        self.worktree_browse_btn.setFixedWidth(100)
        self.worktree_browse_btn.clicked.connect(self._browse_worktree_path)
        path_layout.addWidget(self.worktree_browse_btn)

        config_layout.addLayout(path_layout)

        # Branch selection section
        branch_section = QVBoxLayout()

        # Existing branch option
        existing_branch_layout = QHBoxLayout()
        self.existing_branch_radio = QRadioButton("Use existing branch:")
        self.existing_branch_radio.setChecked(True)
        existing_branch_layout.addWidget(self.existing_branch_radio)

        self.branch_combo = QComboBox()
        self.branch_combo.setEditable(False)
        self.branch_combo.addItems(self.available_branches)
        existing_branch_layout.addWidget(self.branch_combo, 1)
        branch_section.addLayout(existing_branch_layout)

        # New branch option
        new_branch_layout = QHBoxLayout()
        self.new_branch_radio = QRadioButton("Create new branch:")
        new_branch_layout.addWidget(self.new_branch_radio)

        self.new_branch_edit = QLineEdit()
        self.new_branch_edit.setPlaceholderText("Enter new branch name...")
        self.new_branch_edit.setEnabled(False)
        new_branch_layout.addWidget(self.new_branch_edit, 2)

        from_label = QLabel("from")
        from_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        new_branch_layout.addWidget(from_label)

        self.base_branch_combo = QComboBox()
        self.base_branch_combo.addItem("main")
        self.base_branch_combo.addItem("master")
        self.base_branch_combo.addItems(
            [b for b in self.available_branches if b not in ["main", "master"]]
        )
        self.base_branch_combo.setEnabled(False)
        new_branch_layout.addWidget(self.base_branch_combo, 1)

        branch_section.addLayout(new_branch_layout)
        config_layout.addLayout(branch_section)

        # Options section
        options_section = QVBoxLayout()

        options_grid = QGridLayout()

        self.fetch_remote_check = QCheckBox("Fetch remote changes before creating")
        self.fetch_remote_check.setChecked(True)
        options_grid.addWidget(self.fetch_remote_check, 0, 0)

        self.auto_create_branch_check = QCheckBox(
            "Auto-create branch if it doesn't exist"
        )
        self.auto_create_branch_check.setChecked(True)
        self.auto_create_branch_check.setToolTip(
            "Automatically create the branch if it doesn't exist in the repository"
        )
        options_grid.addWidget(self.auto_create_branch_check, 0, 1)

        options_section.addLayout(options_grid)
        config_layout.addLayout(options_section)

        layout.addWidget(config_group)
        config_group.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        # Validation status (inline)
        self.worktree_validation_status = QLabel()
        self.worktree_validation_status.setWordWrap(True)
        self.worktree_validation_status.hide()
        config_layout.addWidget(self.worktree_validation_status)

        # Compact path preview
        self.worktree_path_preview_label = QLabel()
        self.worktree_path_preview_label.hide()
        config_layout.addWidget(self.worktree_path_preview_label)

        # Create worktree button
        self.create_worktree_btn = QPushButton("Create Worktree")
        self.create_worktree_btn.setEnabled(False)
        self.create_worktree_btn.clicked.connect(self._create_worktree)
        layout.addWidget(self.create_worktree_btn)

        # Initialize worktree path
        self._initialize_worktree_path()

    def _setup_connections(self):
        """Set up signal connections."""
        # Worktree tab connections
        self.worktree_path_edit.textChanged.connect(self._on_worktree_input_changed)
        self.new_branch_edit.textChanged.connect(self._on_worktree_input_changed)

        self.existing_branch_radio.toggled.connect(self._on_branch_type_changed)

        # Connect branch selection changes to update path
        self.branch_combo.currentTextChanged.connect(self._on_branch_selection_changed)
        self.base_branch_combo.currentTextChanged.connect(
            self._on_branch_selection_changed
        )
        self.new_branch_edit.textChanged.connect(self._on_branch_selection_changed)

    def _create_styled_label(self, text: str, status_map: dict) -> QLabel:
        """Create a styled label based on status mapping."""
        label = QLabel(text)
        color = status_map.get(text.lower(), "gray")
        label.setStyleSheet(f"color: {color}; font-weight: bold;")
        return label

    def _create_status_label(self, status: ProjectStatus) -> QLabel:
        """Create a styled status label."""
        status_map = {
            "active": "green",
            "error": "red",
            "unavailable": "orange",
        }
        return self._create_styled_label(status.value.title(), status_map)

    def _create_health_status_label(self, status: str) -> QLabel:
        """Create a styled health status label."""
        status_map = {
            "healthy": "green",
            "warning": "orange",
            "unhealthy": "red",
        }
        return self._create_styled_label(status.title(), status_map)

    def _initialize_worktree_path(self):
        """Initialize the worktree path field with default configuration."""
        # Generate path based on current branch selection (defaults to main)
        suggested_path = self._generate_worktree_path()
        self.worktree_path_edit.setText(suggested_path)

        if self.base_path and Path(self.base_path).exists():
            self.worktree_path_edit.setToolTip(
                f"Auto-populated from configured base path: {self.base_path}"
            )
        else:
            self.worktree_path_edit.setToolTip("Auto-populated with default path")

    def _browse_worktree_path(self):
        """Browse for worktree path."""
        # Use base path as default if configured, otherwise use project parent
        if self.base_path and Path(self.base_path).exists():
            default_path = self.base_path
        else:
            default_path = str(Path(self.project.path).parent)

        path = QFileDialog.getExistingDirectory(
            self,
            "Select Worktree Directory",
            default_path,
            QFileDialog.Option.ShowDirsOnly,
        )
        if path:
            # Generate the full path using the selected directory as base
            suggested_path = self._generate_worktree_path(base_path=path)
            self.worktree_path_edit.setText(suggested_path)

    def _on_branch_selection_changed(self):
        """Handle branch selection changes to update worktree path."""
        # Only update path if it hasn't been manually modified by the user
        current_path = self.worktree_path_edit.text().strip()
        generated_path = self._generate_worktree_path()

        # Check if current path looks like it was auto-generated
        # (contains project name and appears to follow our naming pattern)
        project_name = self.project.get_display_name()
        if project_name in current_path and "-" in current_path:
            # Update to new generated path
            self.worktree_path_edit.setText(generated_path)

    def _on_branch_type_changed(self):
        """Handle branch type radio button changes."""
        use_existing = self.existing_branch_radio.isChecked()

        self.branch_combo.setEnabled(use_existing)
        self.new_branch_edit.setEnabled(not use_existing)
        self.base_branch_combo.setEnabled(not use_existing)

        # Update path when branch type changes
        self._on_branch_selection_changed()
        self._on_worktree_input_changed()

    def _on_worktree_input_changed(self):
        """Handle input changes for validation."""
        self.validation_timer.stop()
        self.validation_timer.start(500)  # 500ms delay

    def _validate_worktree_inputs(self):
        """Validate the worktree dialog inputs."""
        path = self.worktree_path_edit.text().strip()
        branch = self._get_selected_branch()

        if not path:
            self._clear_worktree_validation()
            self.create_worktree_btn.setEnabled(False)
            return

        if not branch:
            self._show_worktree_validation_error("Please select or enter a branch name")
            return

        self._show_worktree_validation_progress()

        try:
            path_obj = Path(path)

            # Check if path already exists
            if path_obj.exists():
                if any(path_obj.iterdir()):  # Directory exists and is not empty
                    self._show_worktree_validation_error(
                        "Directory already exists and is not empty"
                    )
                    return

            # Check if parent directory exists and is writable
            parent = path_obj.parent
            if not parent.exists():
                self._show_worktree_validation_error("Parent directory does not exist")
                return

            if not parent.is_dir():
                self._show_worktree_validation_error("Parent path is not a directory")
                return

            # Check write permissions
            try:
                test_file = parent / ".test_write_permission"
                test_file.touch()
                test_file.unlink()
            except (PermissionError, OSError):
                self._show_worktree_validation_error(
                    "No write permission in parent directory"
                )
                return

            # Validation passed
            self._show_worktree_validation_success(path_obj)

        except Exception as e:
            self._show_worktree_validation_error(f"Path validation error: {e}")

    def _show_worktree_validation_progress(self):
        """Show validation in progress."""
        self.worktree_validation_status.setText("Validating...")
        self.worktree_validation_status.setStyleSheet("color: blue;")
        self.worktree_validation_status.show()
        self.worktree_path_preview_label.hide()
        self.create_worktree_btn.setEnabled(False)

    def _show_worktree_validation_success(self, path_obj: Path):
        """Show successful validation."""
        self.worktree_validation_status.setText("✓ Valid worktree configuration")
        self.worktree_validation_status.setStyleSheet(
            "color: green; font-weight: bold;"
        )
        self.worktree_validation_status.show()

        # Show path preview
        self._update_worktree_path_preview(path_obj)
        self.worktree_path_preview_label.show()

        self.create_worktree_btn.setEnabled(True)

    def _show_worktree_validation_error(self, message: str):
        """Show validation error."""
        self.worktree_path_preview_label.hide()

        self.worktree_validation_status.setText(f"✗ {message}")
        self.worktree_validation_status.setStyleSheet("color: red; font-weight: bold;")
        self.worktree_validation_status.show()

        self.create_worktree_btn.setEnabled(False)

    def _clear_worktree_validation(self):
        """Clear validation display."""
        self.worktree_validation_status.hide()
        self.worktree_path_preview_label.hide()

    def _update_worktree_path_preview(self, path_obj: Path):
        """Update path preview information."""
        branch = self._get_selected_branch()
        preview_text = f"Path: {path_obj.resolve()} | Branch: {branch}"
        if self.new_branch_radio.isChecked():
            base_branch = self.base_branch_combo.currentText()
            preview_text += f" (from {base_branch})"
        self.worktree_path_preview_label.setText(preview_text)
        self.worktree_path_preview_label.setStyleSheet(
            "color: #666; font-style: italic;"
        )

    def _generate_worktree_path(self, base_path: str = None) -> str:
        """Generate worktree path based on project name and selected branch."""
        # Determine the base directory
        if base_path:
            base_dir = Path(base_path)
        elif self.base_path and Path(self.base_path).exists():
            base_dir = Path(self.base_path)
        else:
            base_dir = Path(self.project.path).parent

        # Get the selected branch and sanitize it
        branch_name = self._get_selected_branch()
        if not branch_name:
            # Default to main if no branch is selected
            branch_name = "main"

        sanitized_branch = self._sanitize_branch_name(branch_name)
        project_name = self.project.get_display_name()

        # Generate the final path: base_path/project-name-branch
        worktree_dir_name = f"{project_name}-{sanitized_branch}"
        return str(base_dir / worktree_dir_name)

    def _sanitize_branch_name(self, branch_name: str) -> str:
        """Sanitize branch name for use in file paths."""
        if not branch_name:
            return ""
        # Replace forward slashes and other problematic characters with hyphens
        sanitized = branch_name.replace("/", "-").replace("\\", "-").replace(":", "-")
        # Remove any double hyphens that might have been created
        while "--" in sanitized:
            sanitized = sanitized.replace("--", "-")
        # Remove leading/trailing hyphens
        return sanitized.strip("-")

    def _get_selected_branch(self) -> str:
        """Get the selected or entered branch name."""
        if self.existing_branch_radio.isChecked():
            return self.branch_combo.currentText()
        else:
            return self.new_branch_edit.text().strip()

    def _create_worktree(self):
        """Create the worktree with current configuration."""
        config = {
            "path": self.worktree_path_edit.text().strip(),
            "branch": self._get_selected_branch(),
            "is_new_branch": self.new_branch_radio.isChecked(),
            "base_branch": self.base_branch_combo.currentText()
            if self.new_branch_radio.isChecked()
            else None,
            "fetch_remote": self.fetch_remote_check.isChecked(),
            "auto_create_branch": self.auto_create_branch_check.isChecked(),
        }

        # Emit signal to create worktree
        self.create_worktree_requested.emit(self.project.id, config)

        # Show success message
        get_message_service().show_success(
            f"Worktree creation requested for '{self.project.get_display_name()}'"
        )

        # Close dialog
        self.accept()
