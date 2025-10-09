"""Worktree management panel for Git Worktree Manager."""

import logging
from pathlib import Path

from PyQt6.QtCore import Qt, QSortFilterProxyModel, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QFont, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QTextEdit,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from ..models.project import Project
from ..models.worktree import Worktree
from ..services.message_service import get_message_service


class CreateWorktreeDialog(QDialog):
    """Dialog for creating a new worktree."""

    def __init__(
        self,
        project: Project,
        available_branches: list[str],
        base_path: str = None,
        parent=None,
    ):
        super().__init__(parent)
        self.project = project
        self.available_branches = available_branches
        self.base_path = base_path

        self.setWindowTitle(f"Create Worktree - {project.get_display_name()}")
        self.setModal(True)
        self.resize(600, 400)

        # Validation timer
        self.validation_timer = QTimer()
        self.validation_timer.setSingleShot(True)
        self.validation_timer.timeout.connect(self._validate_inputs)

        self._setup_ui()
        self._setup_connections()

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Create a fixed top section that won't be affected by dynamic content
        top_section = QVBoxLayout()

        # Project info
        info_group = QGroupBox("Project Information")
        info_layout = QFormLayout(info_group)
        info_layout.addRow("Project:", QLabel(self.project.get_display_name()))
        info_layout.addRow("Repository:", QLabel(self.project.path))
        top_section.addWidget(info_group)

        # Worktree configuration
        config_group = QGroupBox("Worktree Configuration")
        config_layout = QVBoxLayout(
            config_group
        )  # Changed from QFormLayout to QVBoxLayout for better control

        # Worktree path section
        path_section = QVBoxLayout()
        path_label = QLabel("Worktree Path:")
        path_section.addWidget(path_label)

        path_layout = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Enter worktree directory path...")
        path_layout.addWidget(self.path_edit, 1)  # Give path edit stretch factor of 1

        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.setFixedWidth(100)  # Fixed width for browse button
        self.browse_btn.clicked.connect(self._browse_for_path)
        path_layout.addWidget(self.browse_btn)

        path_section.addLayout(path_layout)
        config_layout.addLayout(path_section)

        # Branch selection section
        branch_section = QVBoxLayout()
        branch_label = QLabel("Branch:")
        branch_section.addWidget(branch_label)

        # Existing branch option
        existing_branch_layout = QHBoxLayout()
        self.existing_branch_radio = QRadioButton("Use existing branch:")
        self.existing_branch_radio.setChecked(True)
        existing_branch_layout.addWidget(self.existing_branch_radio)

        self.branch_combo = QComboBox()
        self.branch_combo.setEditable(False)
        self.branch_combo.addItems(self.available_branches)
        existing_branch_layout.addWidget(self.branch_combo, 1)  # Expand to fill space
        branch_section.addLayout(existing_branch_layout)

        # New branch option
        new_branch_layout = QHBoxLayout()
        self.new_branch_radio = QRadioButton("Create new branch:")
        new_branch_layout.addWidget(self.new_branch_radio)

        self.new_branch_edit = QLineEdit()
        self.new_branch_edit.setPlaceholderText("Enter new branch name...")
        self.new_branch_edit.setEnabled(False)
        new_branch_layout.addWidget(
            self.new_branch_edit, 2
        )  # Give more space to branch name

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
        new_branch_layout.addWidget(
            self.base_branch_combo, 1
        )  # Expand base branch combo

        branch_section.addLayout(new_branch_layout)
        config_layout.addLayout(branch_section)

        # Options section
        options_section = QVBoxLayout()
        options_label = QLabel("Options:")
        options_section.addWidget(options_label)

        # Arrange options in a grid for better space utilization
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

        top_section.addWidget(config_group)

        # Add the fixed top section to the main layout
        layout.addLayout(top_section)

        # Create a dynamic section for validation messages and other dynamic content
        dynamic_section = QVBoxLayout()

        # Validation status
        self.validation_status = QLabel()
        self.validation_status.setWordWrap(True)
        self.validation_status.hide()
        dynamic_section.addWidget(self.validation_status)

        # Validation progress
        self.validation_progress = QProgressBar()
        self.validation_progress.setRange(0, 0)  # Indeterminate
        self.validation_progress.hide()
        dynamic_section.addWidget(self.validation_progress)

        # Path preview
        self.path_preview_group = QGroupBox("Path Preview")
        self.path_preview_layout = QFormLayout(self.path_preview_group)
        self.path_preview_group.hide()
        dynamic_section.addWidget(self.path_preview_group)

        # Add the dynamic section to the main layout
        layout.addLayout(dynamic_section)

        # Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        # Initially disable OK button
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

        # Initialize with base path if provided
        self._initialize_base_path()

    def _initialize_base_path(self):
        """Initialize the path field with base path if configured."""
        if self.base_path and Path(self.base_path).exists():
            # Auto-populate with base path + project name
            suggested_path = str(Path(self.base_path) / self.project.get_display_name())
            self.path_edit.setText(suggested_path)
            self.path_edit.setToolTip(
                f"Auto-populated from configured base path: {self.base_path}"
            )
        else:
            self.path_edit.setToolTip("Enter worktree directory path...")

    def _setup_connections(self):
        """Set up signal connections."""
        self.path_edit.textChanged.connect(self._on_input_changed)
        self.new_branch_edit.textChanged.connect(self._on_input_changed)

        self.existing_branch_radio.toggled.connect(self._on_branch_type_changed)
        self.new_branch_radio.toggled.connect(self._on_branch_type_changed)

    def _browse_for_path(self):
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
            # Suggest a subdirectory name based on branch
            branch_name = self._get_selected_branch()
            if branch_name:
                suggested_path = str(
                    Path(path) / f"{self.project.get_display_name()}-{branch_name}"
                )
                self.path_edit.setText(suggested_path)
            else:
                self.path_edit.setText(path)

    def _on_branch_type_changed(self):
        """Handle branch type radio button changes."""
        use_existing = self.existing_branch_radio.isChecked()

        self.branch_combo.setEnabled(use_existing)
        self.new_branch_edit.setEnabled(not use_existing)
        self.base_branch_combo.setEnabled(not use_existing)

        self._on_input_changed()

    def _on_input_changed(self):
        """Handle input changes for validation."""
        self.validation_timer.stop()
        self.validation_timer.start(500)  # 500ms delay

    def _validate_inputs(self):
        """Validate the dialog inputs."""
        path = self.path_edit.text().strip()
        branch = self._get_selected_branch()

        if not path:
            self._clear_validation()
            self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            return

        if not branch:
            self._show_validation_error("Please select or enter a branch name")
            return

        self._show_validation_progress()

        try:
            path_obj = Path(path)

            # Check if path already exists
            if path_obj.exists():
                if any(path_obj.iterdir()):  # Directory exists and is not empty
                    self._show_validation_error(
                        "Directory already exists and is not empty"
                    )
                    return

            # Check if parent directory exists and is writable
            parent = path_obj.parent
            if not parent.exists():
                self._show_validation_error("Parent directory does not exist")
                return

            if not parent.is_dir():
                self._show_validation_error("Parent path is not a directory")
                return

            # Check write permissions
            try:
                test_file = parent / ".test_write_permission"
                test_file.touch()
                test_file.unlink()
            except (PermissionError, OSError):
                self._show_validation_error("No write permission in parent directory")
                return

            # Validation passed
            self._show_validation_success(path_obj)

        except Exception as e:
            self._show_validation_error(f"Path validation error: {e}")

    def _show_validation_progress(self):
        """Show validation in progress."""
        self.validation_progress.show()
        self.validation_status.hide()
        self.path_preview_group.hide()
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

    def _show_validation_success(self, path_obj: Path):
        """Show successful validation."""
        self.validation_progress.hide()

        self.validation_status.setText("✓ Valid worktree configuration")
        self.validation_status.setStyleSheet("color: green; font-weight: bold;")
        self.validation_status.show()

        # Show path preview
        self._update_path_preview(path_obj)
        self.path_preview_group.show()

        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)

    def _show_validation_error(self, message: str):
        """Show validation error."""
        self.validation_progress.hide()
        self.path_preview_group.hide()

        self.validation_status.setText(f"✗ {message}")
        self.validation_status.setStyleSheet("color: red; font-weight: bold;")
        self.validation_status.show()

        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

    def _clear_validation(self):
        """Clear validation display."""
        self.validation_progress.hide()
        self.validation_status.hide()
        self.path_preview_group.hide()

    def _update_path_preview(self, path_obj: Path):
        """Update path preview information."""
        # Clear existing preview
        for i in reversed(range(self.path_preview_layout.count())):
            self.path_preview_layout.itemAt(i).widget().setParent(None)

        self.path_preview_layout.addRow("Full Path:", QLabel(str(path_obj.resolve())))
        self.path_preview_layout.addRow("Directory Name:", QLabel(path_obj.name))
        self.path_preview_layout.addRow(
            "Parent Directory:", QLabel(str(path_obj.parent))
        )

        branch = self._get_selected_branch()
        self.path_preview_layout.addRow("Branch:", QLabel(branch))

        if self.new_branch_radio.isChecked():
            base_branch = self.base_branch_combo.currentText()
            self.path_preview_layout.addRow("Base Branch:", QLabel(base_branch))

    def _get_selected_branch(self) -> str:
        """Get the selected or entered branch name."""
        if self.existing_branch_radio.isChecked():
            return self.branch_combo.currentText()
        else:
            return self.new_branch_edit.text().strip()

    def get_worktree_config(self) -> dict:
        """Get the worktree configuration from the dialog."""
        return {
            "path": self.path_edit.text().strip(),
            "branch": self._get_selected_branch(),
            "is_new_branch": self.new_branch_radio.isChecked(),
            "base_branch": self.base_branch_combo.currentText()
            if self.new_branch_radio.isChecked()
            else None,
            "fetch_remote": self.fetch_remote_check.isChecked(),
            "auto_create_branch": self.auto_create_branch_check.isChecked(),
        }


class RemoveWorktreeDialog(QDialog):
    """Dialog for removing a worktree with safety checks."""

    def __init__(self, worktree: Worktree, project: Project, parent=None):
        super().__init__(parent)
        self.worktree = worktree
        self.project = project

        self.setWindowTitle("Remove Worktree")
        self.setModal(True)
        self.resize(500, 400)

        self._setup_ui()

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Warning header
        warning_label = QLabel("⚠️ Remove Worktree")
        warning_label.setFont(QFont("", 14, QFont.Weight.Bold))
        warning_label.setStyleSheet("color: #d32f2f; padding: 8px;")
        layout.addWidget(warning_label)

        # Worktree information
        info_group = QGroupBox("Worktree Information")
        info_layout = QFormLayout(info_group)

        info_layout.addRow("Project:", QLabel(self.project.get_display_name()))
        info_layout.addRow("Path:", QLabel(self.worktree.path))
        info_layout.addRow("Branch:", QLabel(self.worktree.get_branch_display()))
        info_layout.addRow("Commit:", QLabel(self.worktree.commit_hash))
        info_layout.addRow("Status:", QLabel(self.worktree.get_status_display()))
        info_layout.addRow("Last Modified:", QLabel(self.worktree.get_age_display()))

        layout.addWidget(info_group)

        # Safety checks
        checks_group = QGroupBox("Safety Checks")
        checks_layout = QVBoxLayout(checks_group)

        # Check for uncommitted changes
        if self.worktree.has_uncommitted_changes:
            uncommitted_label = QLabel(
                "⚠️ This worktree has uncommitted changes that will be lost!"
            )
            uncommitted_label.setStyleSheet(
                "color: #d32f2f; font-weight: bold; padding: 4px;"
            )
            checks_layout.addWidget(uncommitted_label)

        # Check if worktree is accessible
        if not self.worktree.is_accessible():
            inaccessible_label = QLabel(
                "⚠️ Worktree directory is not accessible - removal may fail"
            )
            inaccessible_label.setStyleSheet(
                "color: #ff9800; font-weight: bold; padding: 4px;"
            )
            checks_layout.addWidget(inaccessible_label)

        # Check if it's the current directory
        if self.worktree.is_current_directory():
            current_dir_label = QLabel(
                "⚠️ This worktree is your current working directory!"
            )
            current_dir_label.setStyleSheet(
                "color: #d32f2f; font-weight: bold; padding: 4px;"
            )
            checks_layout.addWidget(current_dir_label)

        layout.addWidget(checks_group)

        # Options
        options_group = QGroupBox("Removal Options")
        options_layout = QVBoxLayout(options_group)

        self.force_check = QCheckBox("Force removal (ignore safety checks)")
        self.force_check.setToolTip(
            "Force removal even if there are uncommitted changes"
        )
        options_layout.addWidget(self.force_check)

        self.remove_directory_check = QCheckBox(
            "Remove worktree directory from filesystem"
        )
        self.remove_directory_check.setChecked(True)
        self.remove_directory_check.setToolTip(
            "Delete the worktree directory and all its contents"
        )
        options_layout.addWidget(self.remove_directory_check)

        layout.addWidget(options_group)

        # Confirmation text
        confirmation_group = QGroupBox("Confirmation")
        confirmation_layout = QVBoxLayout(confirmation_group)

        confirmation_text = QTextEdit()
        confirmation_text.setReadOnly(True)
        confirmation_text.setMaximumHeight(100)

        confirmation_message = (
            "This action will remove the worktree from Git's tracking and "
            "optionally delete the directory from your filesystem.\n\n"
            "This action cannot be undone. Make sure you have committed or "
            "backed up any important changes."
        )
        confirmation_text.setPlainText(confirmation_message)
        confirmation_layout.addWidget(confirmation_text)

        self.confirm_check = QCheckBox(
            "I understand the consequences and want to proceed"
        )
        confirmation_layout.addWidget(self.confirm_check)

        layout.addWidget(confirmation_group)

        # Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

        # Customize OK button
        ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.setText("Remove Worktree")
        ok_button.setStyleSheet(
            "QPushButton { background-color: #d32f2f; color: white; font-weight: bold; }"
        )
        ok_button.setEnabled(False)

        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        # Connect confirmation checkbox
        self.confirm_check.toggled.connect(self._on_confirmation_changed)

    def _on_confirmation_changed(self, checked: bool):
        """Handle confirmation checkbox change."""
        ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.setEnabled(checked)

    def get_removal_config(self) -> dict:
        """Get the removal configuration from the dialog."""
        return {
            "force": self.force_check.isChecked(),
            "remove_directory": self.remove_directory_check.isChecked(),
        }


class WorktreeFilterModel(QSortFilterProxyModel):
    """Filter model for worktree list with custom filtering logic."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setRecursiveFilteringEnabled(True)

        # Filter criteria
        self._branch_filter = ""
        self._status_filter = ""
        self._text_filter = ""

    def set_branch_filter(self, branch: str):
        """Set branch filter."""
        self._branch_filter = branch.lower()
        self.invalidateFilter()

    def set_status_filter(self, status: str):
        """Set status filter."""
        self._status_filter = status.lower()
        self.invalidateFilter()

    def set_text_filter(self, text: str):
        """Set text filter."""
        self._text_filter = text.lower()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:
        """Custom filter logic for worktree items."""
        worktree_data = self._get_worktree_data(source_row, source_parent)
        if not worktree_data:
            return True

        return (
            self._passes_branch_filter(worktree_data)
            and self._passes_status_filter(worktree_data)
            and self._passes_text_filter(worktree_data)
        )

    def _get_worktree_data(self, source_row: int, source_parent):
        """Get worktree data from the model."""
        model = self.sourceModel()
        if not model:
            return None

        index = model.index(source_row, 0, source_parent)
        if not index.isValid():
            return None

        item = model.itemFromIndex(index)
        if not item:
            return None

        worktree_data = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(worktree_data, Worktree):
            return None

        return worktree_data

    def _passes_branch_filter(self, worktree_data) -> bool:
        """Check if worktree passes branch filter."""
        if not self._branch_filter:
            return True
        return self._branch_filter in worktree_data.branch.lower()

    def _passes_status_filter(self, worktree_data) -> bool:
        """Check if worktree passes status filter."""
        if not self._status_filter:
            return True
        status_display = worktree_data.get_status_display().lower()
        return self._status_filter in status_display

    def _passes_text_filter(self, worktree_data) -> bool:
        """Check if worktree passes text filter."""
        if not self._text_filter:
            return True

        searchable_text = (
            f"{worktree_data.path} {worktree_data.branch} "
            f"{worktree_data.get_status_display()} {worktree_data.get_directory_name()}"
        ).lower()

        return self._text_filter in searchable_text


class WorktreePanel(QWidget):
    """Panel for displaying and managing Git worktrees."""

    # Signals
    worktree_selected = pyqtSignal(str)  # worktree_path
    create_worktree_requested = pyqtSignal(str, dict)  # project_id, config
    remove_worktree_requested = pyqtSignal(
        str, str, dict
    )  # project_id, worktree_path, config
    open_worktree_requested = pyqtSignal(str, str)  # worktree_path, action_type
    run_command_requested = pyqtSignal(str)  # worktree_path
    refresh_worktrees_requested = pyqtSignal(str)  # project_id
    get_available_branches_requested = pyqtSignal(str)  # project_id

    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.config = config

        # Current state
        self._current_project: Project | None = None
        self._current_worktree_path: str | None = None
        self._worktrees: list[Worktree] = []

        # UI components
        self.model = QStandardItemModel()
        self.filter_model = WorktreeFilterModel()

        self._setup_ui()
        self._setup_connections()
        self._setup_model()

    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Header section
        self._create_header_section(layout)

        # Filter section
        self._create_filter_section(layout)

        # Worktree list
        self._create_worktree_list(layout)

        # Action buttons
        self._create_action_buttons(layout)

        # Status section
        self._create_status_section(layout)

    def _create_header_section(self, layout: QVBoxLayout):
        """Create the header section with title and project info."""
        header_layout = QHBoxLayout()

        # Title
        self.title_label = QLabel("Worktrees")
        self.title_label.setFont(QFont("", 12, QFont.Weight.Bold))
        header_layout.addWidget(self.title_label)

        # Project name
        self.project_name_label = QLabel("No project selected")
        self.project_name_label.setStyleSheet("color: #666; font-style: italic;")
        header_layout.addWidget(self.project_name_label)

        header_layout.addStretch()

        # New worktree button
        self.new_worktree_btn = QPushButton("New Worktree")
        self.new_worktree_btn.setEnabled(False)
        self.new_worktree_btn.setToolTip("Create a new worktree")
        header_layout.addWidget(self.new_worktree_btn)

        layout.addLayout(header_layout)

    def _create_filter_section(self, layout: QVBoxLayout):
        """Create the filter section."""
        filter_group = QGroupBox("Filters")
        filter_layout = QVBoxLayout(filter_group)
        filter_layout.setSpacing(4)

        # Text search
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search worktrees...")
        self.search_edit.setClearButtonEnabled(True)
        search_layout.addWidget(self.search_edit)

        filter_layout.addLayout(search_layout)

        # Filter dropdowns
        dropdown_layout = QHBoxLayout()

        # Branch filter
        dropdown_layout.addWidget(QLabel("Branch:"))
        self.branch_filter = QComboBox()
        self.branch_filter.addItem("All Branches", "")
        self.branch_filter.setMinimumWidth(120)
        dropdown_layout.addWidget(self.branch_filter)

        # Status filter
        dropdown_layout.addWidget(QLabel("Status:"))
        self.status_filter = QComboBox()
        self.status_filter.addItem("All Status", "")
        self.status_filter.addItem("Clean", "clean")
        self.status_filter.addItem("Modified", "modified")
        self.status_filter.addItem("Detached", "detached")
        self.status_filter.addItem("Bare", "bare")
        self.status_filter.setMinimumWidth(100)
        dropdown_layout.addWidget(self.status_filter)

        dropdown_layout.addStretch()

        # Clear filters button
        self.clear_filters_btn = QPushButton("Clear")
        self.clear_filters_btn.setMaximumWidth(60)
        self.clear_filters_btn.setToolTip("Clear all filters")
        dropdown_layout.addWidget(self.clear_filters_btn)

        filter_layout.addLayout(dropdown_layout)
        layout.addWidget(filter_group)

    def _create_worktree_list(self, layout: QVBoxLayout):
        """Create the worktree list view."""
        self.worktree_view = QTreeView()
        self.worktree_view.setAlternatingRowColors(True)
        self.worktree_view.setSelectionMode(QTreeView.SelectionMode.SingleSelection)
        self.worktree_view.setSelectionBehavior(QTreeView.SelectionBehavior.SelectRows)
        self.worktree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.worktree_view.setSortingEnabled(True)
        self.worktree_view.setRootIsDecorated(False)

        # Set up headers
        self.model.setHorizontalHeaderLabels(
            ["Directory", "Branch", "Status", "Commit", "Age"]
        )

        layout.addWidget(self.worktree_view)

    def _create_action_buttons(self, layout: QVBoxLayout):
        """Create action buttons."""
        actions_layout = QHBoxLayout()

        self.open_btn = QPushButton("Open")
        self.open_btn.setEnabled(False)
        self.open_btn.setToolTip("Open worktree in file manager")
        actions_layout.addWidget(self.open_btn)

        self.terminal_btn = QPushButton("Terminal")
        self.terminal_btn.setEnabled(False)
        self.terminal_btn.setToolTip("Open terminal in worktree")
        actions_layout.addWidget(self.terminal_btn)

        self.run_command_btn = QPushButton("Run Command")
        self.run_command_btn.setEnabled(False)
        self.run_command_btn.setToolTip("Run command in worktree")
        actions_layout.addWidget(self.run_command_btn)

        actions_layout.addStretch()

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setToolTip("Refresh worktree list")
        actions_layout.addWidget(self.refresh_btn)

        self.remove_btn = QPushButton("Remove")
        self.remove_btn.setEnabled(False)
        self.remove_btn.setToolTip("Remove selected worktree")
        actions_layout.addWidget(self.remove_btn)

        layout.addLayout(actions_layout)

    def _create_status_section(self, layout: QVBoxLayout):
        """Create status section."""
        self.status_label = QLabel("No project selected")
        self.status_label.setStyleSheet(
            "color: #666; font-style: italic; padding: 4px;"
        )
        layout.addWidget(self.status_label)

    def _setup_model(self):
        """Set up the data model and view."""
        # Set up filter model
        self.filter_model.setSourceModel(self.model)
        self.worktree_view.setModel(self.filter_model)

        # Now that model is set, connect selection signals
        if self.worktree_view.selectionModel():
            self.worktree_view.selectionModel().selectionChanged.connect(
                self._on_selection_changed
            )

        # Configure column widths
        header = self.worktree_view.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Directory
        header.setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )  # Branch
        header.setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )  # Status
        header.setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )  # Commit
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Age

        # Set initial sort
        self.filter_model.sort(0, Qt.SortOrder.AscendingOrder)

    def _setup_connections(self):
        """Set up signal-slot connections."""
        # Button connections
        self.new_worktree_btn.clicked.connect(self._on_new_worktree)
        self.open_btn.clicked.connect(self._on_open_worktree)
        self.terminal_btn.clicked.connect(self._on_open_terminal)
        self.run_command_btn.clicked.connect(self._on_run_command)
        self.refresh_btn.clicked.connect(self._on_refresh)
        self.remove_btn.clicked.connect(self._on_remove_worktree)

        # Filter connections
        self.search_edit.textChanged.connect(self._on_search_changed)
        self.branch_filter.currentTextChanged.connect(self._on_branch_filter_changed)
        self.status_filter.currentTextChanged.connect(self._on_status_filter_changed)
        self.clear_filters_btn.clicked.connect(self._clear_filters)

        # View connections - will be set up after model is assigned
        self.worktree_view.doubleClicked.connect(self._on_item_double_clicked)
        self.worktree_view.customContextMenuRequested.connect(self._show_context_menu)

    def set_project(self, project: Project | None):
        """
        Set the current project and update the display.

        Args:
            project: Project to display worktrees for, or None to clear
        """
        self._current_project = project
        self._current_worktree_path = None

        if project:
            self.project_name_label.setText(project.get_display_name())
            self.new_worktree_btn.setEnabled(True)
            self.refresh_btn.setEnabled(True)
            self._update_status_label(0)  # Will be updated when worktrees are loaded
        else:
            self.project_name_label.setText("No project selected")
            self.new_worktree_btn.setEnabled(False)
            self.refresh_btn.setEnabled(False)
            self._update_status_label(0)
            self.clear_worktrees()

    def populate_worktrees(self, worktrees: list[Worktree]):
        """
        Populate the worktree list with worktree data.

        Args:
            worktrees: List of Worktree instances to display
        """
        self._worktrees = worktrees

        # Clear existing items
        self.model.clear()
        self.model.setHorizontalHeaderLabels(
            ["Directory", "Branch", "Status", "Commit", "Age"]
        )

        # Update branch filter options
        self._update_branch_filter(worktrees)

        # Add worktree items
        for worktree in worktrees:
            self._add_worktree_item(worktree)

        # Update status
        self._update_status_label(len(worktrees))

        # Resize columns to content
        self.worktree_view.resizeColumnToContents(1)  # Branch
        self.worktree_view.resizeColumnToContents(2)  # Status
        self.worktree_view.resizeColumnToContents(3)  # Commit
        self.worktree_view.resizeColumnToContents(4)  # Age

        self.logger.debug(f"Populated worktree list with {len(worktrees)} worktrees")

    def _add_worktree_item(self, worktree: Worktree):
        """Add a single worktree item to the model."""
        # Create row items
        dir_item = QStandardItem(worktree.get_directory_name())
        branch_item = QStandardItem(worktree.get_branch_display())
        status_item = QStandardItem(worktree.get_status_display())
        commit_item = QStandardItem(worktree.get_commit_short_hash())
        age_item = QStandardItem(worktree.get_age_display())

        # Store worktree data in the first item
        dir_item.setData(worktree, Qt.ItemDataRole.UserRole)

        # Set tooltips
        tooltip = self._create_worktree_tooltip(worktree)
        for item in [dir_item, branch_item, status_item, commit_item, age_item]:
            item.setToolTip(tooltip)

        # Apply styling based on status
        self._apply_worktree_styling(
            [dir_item, branch_item, status_item, commit_item, age_item], worktree
        )

        # Add row to model
        self.model.appendRow(
            [dir_item, branch_item, status_item, commit_item, age_item]
        )

    def _create_worktree_tooltip(self, worktree: Worktree) -> str:
        """Create tooltip text for worktree."""
        return (
            f"Path: {worktree.path}\n"
            f"Branch: {worktree.get_branch_display()}\n"
            f"Commit: {worktree.commit_hash}\n"
            f"Status: {worktree.get_status_display()}\n"
            f"Last Modified: {worktree.get_age_display()}\n"
            f"Accessible: {'Yes' if worktree.is_accessible() else 'No'}"
        )

    def _apply_worktree_styling(self, items: list[QStandardItem], worktree: Worktree):
        """Apply styling to worktree items based on status."""
        if worktree.has_uncommitted_changes:
            # Blue for modified worktrees
            for item in items:
                item.setForeground(Qt.GlobalColor.blue)
        elif worktree.is_detached:
            # Orange for detached worktrees
            for item in items:
                item.setForeground(Qt.GlobalColor.darkYellow)
        elif not worktree.is_accessible():
            # Gray for inaccessible worktrees
            for item in items:
                item.setForeground(Qt.GlobalColor.gray)

    def _update_branch_filter(self, worktrees: list[Worktree]):
        """Update branch filter dropdown with available branches."""
        # Get unique branches
        branches = set()
        for worktree in worktrees:
            if not worktree.is_detached:
                branches.add(worktree.branch)

        # Clear and repopulate
        current_text = self.branch_filter.currentText()
        self.branch_filter.clear()
        self.branch_filter.addItem("All Branches", "")

        for branch in sorted(branches):
            self.branch_filter.addItem(branch, branch)

        # Restore selection if possible
        index = self.branch_filter.findText(current_text)
        if index >= 0:
            self.branch_filter.setCurrentIndex(index)

    def _update_status_label(self, count: int):
        """Update the status label with worktree count."""
        if not self._current_project:
            self.status_label.setText("No project selected")
        elif count == 0:
            self.status_label.setText("No worktrees found")
        elif count == 1:
            self.status_label.setText("1 worktree")
        else:
            self.status_label.setText(f"{count} worktrees")

    def clear_worktrees(self):
        """Clear all worktrees from the list."""
        self.model.clear()
        self.model.setHorizontalHeaderLabels(
            ["Directory", "Branch", "Status", "Commit", "Age"]
        )
        self._worktrees.clear()
        self._current_worktree_path = None
        self._update_button_states()
        self._update_status_label(0)

    def get_selected_worktree(self) -> Worktree | None:
        """Get the currently selected worktree."""
        selection = self.worktree_view.selectionModel().selectedRows()
        if not selection:
            return None

        # Get the source index (not filtered)
        proxy_index = selection[0]
        source_index = self.filter_model.mapToSource(proxy_index)

        if not source_index.isValid():
            return None

        item = self.model.itemFromIndex(source_index)
        if not item:
            return None

        return item.data(Qt.ItemDataRole.UserRole)

    def select_worktree(self, worktree_path: str):
        """
        Select a worktree by path.

        Args:
            worktree_path: Path of the worktree to select
        """
        for row in range(self.model.rowCount()):
            item = self.model.item(row, 0)
            if item:
                worktree = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(worktree, Worktree) and worktree.path == worktree_path:
                    # Map to filtered model
                    source_index = self.model.indexFromItem(item)
                    proxy_index = self.filter_model.mapFromSource(source_index)
                    if proxy_index.isValid():
                        self.worktree_view.selectionModel().select(
                            proxy_index,
                            self.worktree_view.selectionModel().SelectionFlag.ClearAndSelect
                            | self.worktree_view.selectionModel().SelectionFlag.Rows,
                        )
                    break

    def _update_button_states(self):
        """Update button enabled states based on selection."""
        has_selection = self.get_selected_worktree() is not None

        self.open_btn.setEnabled(has_selection)
        self.terminal_btn.setEnabled(has_selection)
        self.run_command_btn.setEnabled(has_selection)
        self.remove_btn.setEnabled(has_selection)

    # Event handlers
    def _on_new_worktree(self):
        """Handle new worktree button click."""
        if self._current_project:
            # For now, use a default set of branches - this should be provided by the service layer
            available_branches = ["main", "master", "develop", "dev"]

            # Add branches from existing worktrees
            for worktree in self._worktrees:
                if (
                    not worktree.is_detached
                    and worktree.branch not in available_branches
                ):
                    available_branches.append(worktree.branch)

            config = self.show_create_worktree_dialog(available_branches)
            if config:
                self.create_worktree_requested.emit(self._current_project.id, config)

    def _on_open_worktree(self):
        """Handle open worktree button click."""
        worktree = self.get_selected_worktree()
        if worktree:
            self.open_worktree_requested.emit(worktree.path, "file_manager")

    def _on_open_terminal(self):
        """Handle open terminal button click."""
        worktree = self.get_selected_worktree()
        if worktree:
            self.open_worktree_requested.emit(worktree.path, "terminal")

    def _on_run_command(self):
        """Handle run command button click."""
        worktree = self.get_selected_worktree()
        if worktree:
            self.run_command_requested.emit(worktree.path)

    def _on_refresh(self):
        """Handle refresh button click."""
        if self._current_project:
            self.refresh_worktrees_requested.emit(self._current_project.id)

    def _on_remove_worktree(self):
        """Handle remove worktree button click."""
        worktree = self.get_selected_worktree()
        if worktree and self._current_project:
            config = self.show_remove_worktree_dialog(worktree)
            if config:
                self.remove_worktree_requested.emit(
                    self._current_project.id, worktree.path, config
                )

    def _on_selection_changed(self):
        """Handle selection change in worktree view."""
        worktree = self.get_selected_worktree()
        if worktree:
            self._current_worktree_path = worktree.path
            self.worktree_selected.emit(worktree.path)
        else:
            self._current_worktree_path = None

        self._update_button_states()

    def _on_item_double_clicked(self, index):
        """Handle double-click on worktree item."""
        # Double-click opens in file manager
        self._on_open_worktree()

    def _on_search_changed(self, text: str):
        """Handle search text change."""
        self.filter_model.set_text_filter(text)

    def _on_branch_filter_changed(self, text: str):
        """Handle branch filter change."""
        filter_value = self.branch_filter.currentData() or ""
        self.filter_model.set_branch_filter(filter_value)

    def _on_status_filter_changed(self, text: str):
        """Handle status filter change."""
        filter_value = self.status_filter.currentData() or ""
        self.filter_model.set_status_filter(filter_value)

    def _clear_filters(self):
        """Clear all filters."""
        self.search_edit.clear()
        self.branch_filter.setCurrentIndex(0)
        self.status_filter.setCurrentIndex(0)

    def _show_context_menu(self, position):
        """Show context menu for worktree list."""
        index = self.worktree_view.indexAt(position)
        if not index.isValid():
            return

        # Get worktree from selection
        worktree = self.get_selected_worktree()
        if not worktree:
            return

        menu = QMenu(self)

        # Open actions
        open_file_manager = QAction("Open in File Manager", self)
        open_file_manager.triggered.connect(
            lambda: self.open_worktree_requested.emit(worktree.path, "file_manager")
        )
        menu.addAction(open_file_manager)

        open_terminal = QAction("Open in Terminal", self)
        open_terminal.triggered.connect(
            lambda: self.open_worktree_requested.emit(worktree.path, "terminal")
        )
        menu.addAction(open_terminal)

        open_editor = QAction("Open in Editor", self)
        open_editor.triggered.connect(
            lambda: self.open_worktree_requested.emit(worktree.path, "editor")
        )
        menu.addAction(open_editor)

        menu.addSeparator()

        # Command action
        run_command = QAction("Run Command...", self)
        run_command.triggered.connect(
            lambda: self.run_command_requested.emit(worktree.path)
        )
        menu.addAction(run_command)

        menu.addSeparator()

        # Remove action
        remove_worktree = QAction("Remove Worktree", self)
        remove_worktree.triggered.connect(
            lambda: self._remove_worktree_from_context(worktree)
        )
        menu.addAction(remove_worktree)

        menu.exec(self.worktree_view.mapToGlobal(position))

    def _remove_worktree_from_context(self, worktree: Worktree):
        """Remove worktree from context menu."""
        if self._current_project:
            config = self.show_remove_worktree_dialog(worktree)
            if config:
                self.remove_worktree_requested.emit(
                    self._current_project.id, worktree.path, config
                )

    def refresh_worktree_item(self, worktree: Worktree):
        """
        Refresh a specific worktree item in the list.

        Args:
            worktree: Updated worktree instance
        """
        # Find the item in the model
        for row in range(self.model.rowCount()):
            item = self.model.item(row, 0)
            if item:
                existing_worktree = item.data(Qt.ItemDataRole.UserRole)
                if (
                    isinstance(existing_worktree, Worktree)
                    and existing_worktree.path == worktree.path
                ):
                    # Update the row
                    self.model.item(row, 0).setText(worktree.get_directory_name())
                    self.model.item(row, 1).setText(worktree.get_branch_display())
                    self.model.item(row, 2).setText(worktree.get_status_display())
                    self.model.item(row, 3).setText(worktree.get_commit_short_hash())
                    self.model.item(row, 4).setText(worktree.get_age_display())

                    # Update stored data
                    item.setData(worktree, Qt.ItemDataRole.UserRole)

                    # Update tooltip and styling
                    tooltip = self._create_worktree_tooltip(worktree)
                    items = [self.model.item(row, col) for col in range(5)]
                    for item in items:
                        if item:
                            item.setToolTip(tooltip)

                    self._apply_worktree_styling(items, worktree)
                    break

    def get_filter_summary(self) -> str:
        """Get a summary of current filters."""
        filters = []

        if self.search_edit.text():
            filters.append(f"Text: '{self.search_edit.text()}'")

        if self.branch_filter.currentData():
            filters.append(f"Branch: '{self.branch_filter.currentText()}'")

        if self.status_filter.currentData():
            filters.append(f"Status: '{self.status_filter.currentText()}'")

        if filters:
            return f"Filtered by: {', '.join(filters)}"
        else:
            return "No filters applied"

    def show_create_worktree_dialog(self, available_branches: list[str]) -> dict | None:
        """
        Show the create worktree dialog.

        Args:
            available_branches: List of available branch names

        Returns:
            Worktree configuration dict if accepted, None if cancelled
        """
        if not self._current_project:
            return None

        # Get base path from config if available
        base_path = None
        if self.config and hasattr(self.config, "user_preferences"):
            base_path = self.config.user_preferences.worktree_base_path

        dialog = CreateWorktreeDialog(
            self._current_project, available_branches, base_path, self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.get_worktree_config()
        return None

    def show_remove_worktree_dialog(self, worktree: Worktree) -> dict | None:
        """
        Show the remove worktree dialog.

        Args:
            worktree: Worktree to remove

        Returns:
            Removal configuration dict if accepted, None if cancelled
        """
        if not self._current_project:
            return None

        dialog = RemoveWorktreeDialog(worktree, self._current_project, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.get_removal_config()
        return None

    def show_validation_error(self, message: str):
        """Show validation error message."""
        get_message_service().show_error("Validation Error", message)

    def show_operation_error(self, title: str, message: str):
        """Show operation error message."""
        get_message_service().show_error(title, message)

    def show_operation_success(self, message: str):
        """Show operation success message."""
        get_message_service().show_success(message)
