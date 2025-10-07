"""Project management panel for Git Worktree Manager."""

import logging
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QFont
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..models.project import Project, ProjectStatus


class ProjectHealthDialog(QDialog):
    """Dialog for displaying project health status."""

    def __init__(self, project: Project, health_data: dict, parent=None):
        super().__init__(parent)
        self.project = project
        self.health_data = health_data

        self.setWindowTitle(f"Project Health - {project.get_display_name()}")
        self.setModal(True)
        self.resize(600, 500)

        self._setup_ui()

    def _setup_ui(self):
        """Set up the health dialog UI."""
        layout = QVBoxLayout(self)

        # Project info header
        header_group = QGroupBox("Project Information")
        header_layout = QFormLayout(header_group)

        header_layout.addRow("Name:", QLabel(self.project.get_display_name()))
        header_layout.addRow("Path:", QLabel(self.project.path))
        header_layout.addRow("Status:", self._create_status_label(self.project.status))
        header_layout.addRow(
            "Last Accessed:",
            QLabel(self.project.last_accessed.strftime("%Y-%m-%d %H:%M:%S")),
        )

        layout.addWidget(header_group)

        # Health status
        health_group = QGroupBox("Health Status")
        health_layout = QVBoxLayout(health_group)

        # Overall status
        overall_status = self.health_data.get("overall_status", "unknown")
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("Overall Status:"))
        status_layout.addWidget(self._create_health_status_label(overall_status))
        status_layout.addStretch()
        health_layout.addLayout(status_layout)

        # Statistics
        stats_layout = QFormLayout()
        stats_layout.addRow(
            "Branch Count:", QLabel(str(self.health_data.get("branch_count", "N/A")))
        )
        stats_layout.addRow(
            "Worktree Count:",
            QLabel(str(self.health_data.get("worktree_count", "N/A"))),
        )
        health_layout.addLayout(stats_layout)

        layout.addWidget(health_group)

        # Issues section
        if self.health_data.get("issues"):
            issues_group = QGroupBox("Issues")
            issues_layout = QVBoxLayout(issues_group)

            for issue in self.health_data["issues"]:
                issue_label = QLabel(f"• {issue}")
                issue_label.setStyleSheet("color: red; font-weight: bold;")
                issue_label.setWordWrap(True)
                issues_layout.addWidget(issue_label)

            layout.addWidget(issues_group)

        # Warnings section
        if self.health_data.get("warnings"):
            warnings_group = QGroupBox("Warnings")
            warnings_layout = QVBoxLayout(warnings_group)

            for warning in self.health_data["warnings"]:
                warning_label = QLabel(f"• {warning}")
                warning_label.setStyleSheet("color: orange; font-weight: bold;")
                warning_label.setWordWrap(True)
                warnings_layout.addWidget(warning_label)

            layout.addWidget(warnings_group)

        # Last checked
        last_checked = self.health_data.get("last_checked", "Unknown")
        footer_label = QLabel(f"Last checked: {last_checked}")
        footer_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(footer_label)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _create_status_label(self, status: ProjectStatus) -> QLabel:
        """Create a styled status label."""
        label = QLabel(status.value.title())

        if status == ProjectStatus.ACTIVE:
            label.setStyleSheet("color: green; font-weight: bold;")
        elif status == ProjectStatus.ERROR:
            label.setStyleSheet("color: red; font-weight: bold;")
        elif status == ProjectStatus.UNAVAILABLE:
            label.setStyleSheet("color: orange; font-weight: bold;")
        else:
            label.setStyleSheet("color: gray; font-weight: bold;")

        return label

    def _create_health_status_label(self, status: str) -> QLabel:
        """Create a styled health status label."""
        label = QLabel(status.title())

        if status == "healthy":
            label.setStyleSheet("color: green; font-weight: bold;")
        elif status == "warning":
            label.setStyleSheet("color: orange; font-weight: bold;")
        elif status == "unhealthy":
            label.setStyleSheet("color: red; font-weight: bold;")
        else:
            label.setStyleSheet("color: gray; font-weight: bold;")

        return label


class AddProjectDialog(QDialog):
    """Dialog for adding a new project."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Project")
        self.setModal(True)
        self.resize(550, 300)

        # Validation timer to debounce validation
        self.validation_timer = QTimer()
        self.validation_timer.setSingleShot(True)
        self.validation_timer.timeout.connect(self._validate_path)

        # Project path
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Select or enter Git repository path...")

        # Browse button
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self._browse_for_path)

        # Project name (optional)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Optional: Custom project name")

        # Validation status
        self.validation_status = QLabel()
        self.validation_status.setWordWrap(True)
        self.validation_status.hide()

        # Validation progress
        self.validation_progress = QProgressBar()
        self.validation_progress.setRange(0, 0)  # Indeterminate
        self.validation_progress.hide()

        # Path info display
        self.path_info_group = QGroupBox("Path Information")
        self.path_info_layout = QFormLayout(self.path_info_group)
        self.path_info_group.hide()

        # Layout
        layout = QVBoxLayout(self)

        # Form layout for inputs
        form_layout = QFormLayout()

        # Path row with browse button
        path_layout = QHBoxLayout()
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(self.browse_btn)
        form_layout.addRow("Repository Path:", path_layout)

        form_layout.addRow("Project Name:", self.name_edit)
        layout.addLayout(form_layout)

        # Validation progress
        layout.addWidget(self.validation_progress)

        # Validation status
        layout.addWidget(self.validation_status)

        # Path information
        layout.addWidget(self.path_info_group)

        # Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        # Connect path change to validation
        self.path_edit.textChanged.connect(self._on_path_changed)

        # Initially disable OK button
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

    def _browse_for_path(self):
        """Open file dialog to browse for project path."""
        path = QFileDialog.getExistingDirectory(
            self, "Select Git Repository", "", QFileDialog.Option.ShowDirsOnly
        )
        if path:
            self.path_edit.setText(path)

    def _on_path_changed(self):
        """Handle path text change for validation."""
        # Stop any existing validation timer
        self.validation_timer.stop()

        path = self.path_edit.text().strip()
        if path:
            # Start validation timer (debounced)
            self.validation_timer.start(500)  # 500ms delay
            self._show_validation_progress()
        else:
            self._clear_validation()
            self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

    def _validate_path(self):
        """Validate the entered path."""
        path = self.path_edit.text().strip()
        if not path:
            self._clear_validation()
            return

        try:
            path_obj = Path(path)

            # Check if path exists
            if not path_obj.exists():
                self._show_validation_error("Path does not exist")
                return

            # Check if it's a directory
            if not path_obj.is_dir():
                self._show_validation_error("Path is not a directory")
                return

            # Check if it's a Git repository
            git_dir = path_obj / ".git"
            if not git_dir.exists():
                self._show_validation_error(
                    "Path is not a Git repository (no .git directory found)"
                )
                return

            # Check if directory is readable
            try:
                list(path_obj.iterdir())
            except PermissionError:
                self._show_validation_error("Permission denied: Cannot read directory")
                return

            # Path is valid
            self._show_validation_success(path_obj)

        except Exception as e:
            self._show_validation_error(f"Error validating path: {e}")

    def _show_validation_progress(self):
        """Show validation in progress."""
        self.validation_progress.show()
        self.validation_status.hide()
        self.path_info_group.hide()
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

    def _show_validation_success(self, path_obj: Path):
        """Show successful validation."""
        self.validation_progress.hide()

        # Show success message
        self.validation_status.setText("✓ Valid Git repository")
        self.validation_status.setStyleSheet("color: green; font-weight: bold;")
        self.validation_status.show()

        # Show path information
        self._update_path_info(path_obj)
        self.path_info_group.show()

        # Auto-fill project name if empty
        if not self.name_edit.text().strip():
            self.name_edit.setText(path_obj.name)

        # Enable OK button
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)

    def _show_validation_error(self, message: str):
        """Show validation error."""
        self.validation_progress.hide()
        self.path_info_group.hide()

        self.validation_status.setText(f"✗ {message}")
        self.validation_status.setStyleSheet("color: red; font-weight: bold;")
        self.validation_status.show()

        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

    def _clear_validation(self):
        """Clear validation display."""
        self.validation_progress.hide()
        self.validation_status.hide()
        self.path_info_group.hide()

    def _update_path_info(self, path_obj: Path):
        """Update path information display."""
        # Clear existing info
        for i in reversed(range(self.path_info_layout.count())):
            self.path_info_layout.itemAt(i).widget().setParent(None)

        # Add path information
        self.path_info_layout.addRow("Full Path:", QLabel(str(path_obj.resolve())))
        self.path_info_layout.addRow("Directory Name:", QLabel(path_obj.name))

        # Try to get Git information
        try:
            # Check if it has remotes
            git_config = path_obj / ".git" / "config"
            if git_config.exists():
                with open(git_config) as f:
                    config_content = f.read()
                    if '[remote "origin"]' in config_content:
                        self.path_info_layout.addRow("Has Remote:", QLabel("✓ Yes"))
                    else:
                        self.path_info_layout.addRow("Has Remote:", QLabel("✗ No"))

            # Check for existing worktrees
            worktrees_dir = path_obj / ".git" / "worktrees"
            if worktrees_dir.exists():
                worktree_count = len(list(worktrees_dir.iterdir()))
                self.path_info_layout.addRow(
                    "Existing Worktrees:", QLabel(str(worktree_count))
                )
            else:
                self.path_info_layout.addRow("Existing Worktrees:", QLabel("0"))

        except Exception as e:
            self.path_info_layout.addRow("Git Info:", QLabel(f"Error reading: {e}"))

    def get_project_data(self) -> dict:
        """Get the project data from the dialog."""
        return {
            "path": self.path_edit.text().strip(),
            "name": self.name_edit.text().strip() or None,
        }

    def show_external_validation_error(self, message: str):
        """Show external validation error message."""
        self._show_validation_error(message)


class ProjectPanel(QWidget):
    """Panel for displaying and managing Git projects."""

    # Signals
    project_selected = pyqtSignal(str)  # project_id
    add_project_requested = pyqtSignal(str, str)  # path, name
    remove_project_requested = pyqtSignal(str)  # project_id
    refresh_projects_requested = pyqtSignal()
    project_health_requested = pyqtSignal(str)  # project_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)

        # Current selection
        self._current_project_id: str | None = None
        self._projects: dict[str, Project] = {}

        self._setup_ui()
        self._setup_connections()

    def _setup_ui(self):
        """Set up the user interface."""
        self.setMinimumWidth(300)
        self.setMaximumWidth(400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Header with title and add button
        header_layout = QHBoxLayout()

        self.title_label = QLabel("Projects")
        self.title_label.setFont(QFont("", 12, QFont.Weight.Bold))
        header_layout.addWidget(self.title_label)

        header_layout.addStretch()

        self.add_btn = QPushButton("Add")
        self.add_btn.setMaximumWidth(60)
        self.add_btn.setToolTip("Add a new Git project")
        header_layout.addWidget(self.add_btn)

        layout.addLayout(header_layout)

        # Project list
        self.project_list = QListWidget()
        self.project_list.setAlternatingRowColors(True)
        self.project_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.project_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        layout.addWidget(self.project_list)

        # Action buttons
        actions_layout = QHBoxLayout()

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setToolTip("Refresh all projects")
        actions_layout.addWidget(self.refresh_btn)

        self.remove_btn = QPushButton("Remove")
        self.remove_btn.setEnabled(False)
        self.remove_btn.setToolTip("Remove selected project")
        actions_layout.addWidget(self.remove_btn)

        layout.addLayout(actions_layout)

        # Status label
        self.status_label = QLabel("No projects loaded")
        self.status_label.setStyleSheet(
            "color: #666; font-style: italic; padding: 4px;"
        )
        layout.addWidget(self.status_label)

    def _setup_connections(self):
        """Set up signal-slot connections."""
        self.add_btn.clicked.connect(self._on_add_project)
        self.refresh_btn.clicked.connect(self.refresh_projects_requested.emit)
        self.remove_btn.clicked.connect(self._on_remove_project)

        self.project_list.itemSelectionChanged.connect(self._on_selection_changed)
        self.project_list.customContextMenuRequested.connect(self._show_context_menu)
        self.project_list.itemDoubleClicked.connect(self._on_item_double_clicked)

    def _on_add_project(self):
        """Handle add project button click."""
        dialog = AddProjectDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_project_data()
            self.add_project_requested.emit(data["path"], data["name"] or "")

    def _on_remove_project(self):
        """Handle remove project button click."""
        if not self._current_project_id:
            return

        project = self._projects.get(self._current_project_id)
        if not project:
            return

        # Show confirmation dialog
        reply = QMessageBox.question(
            self,
            "Remove Project",
            f"Are you sure you want to remove the project '{project.get_display_name()}'?\n\n"
            f"Path: {project.path}\n\n"
            "This will only remove the project from the manager, "
            "not delete any files from your system.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.remove_project_requested.emit(self._current_project_id)

    def _on_selection_changed(self):
        """Handle project selection change."""
        selected_items = self.project_list.selectedItems()
        if selected_items:
            item = selected_items[0]
            project_id = item.data(Qt.ItemDataRole.UserRole)
            if project_id:
                self._current_project_id = project_id
                self.remove_btn.setEnabled(True)
                self.project_selected.emit(project_id)
        else:
            self._current_project_id = None
            self.remove_btn.setEnabled(False)

    def _on_item_double_clicked(self, item: QListWidgetItem):
        """Handle double-click on project item."""
        project_id = item.data(Qt.ItemDataRole.UserRole)
        if project_id:
            # Double-click triggers project health check
            self.project_health_requested.emit(project_id)

    def _show_context_menu(self, position):
        """Show context menu for project list."""
        item = self.project_list.itemAt(position)
        if not item:
            return

        project_id = item.data(Qt.ItemDataRole.UserRole)
        if not project_id:
            return

        project = self._projects.get(project_id)
        if not project:
            return

        menu = QMenu(self)

        # Refresh project action
        refresh_action = QAction("Refresh Project", self)
        refresh_action.triggered.connect(lambda: self.refresh_projects_requested.emit())
        menu.addAction(refresh_action)

        # Check health action
        health_action = QAction("Check Health", self)
        health_action.triggered.connect(
            lambda: self.project_health_requested.emit(project_id)
        )
        menu.addAction(health_action)

        menu.addSeparator()

        # Open in file manager action
        open_action = QAction("Open in File Manager", self)
        open_action.triggered.connect(lambda: self._open_in_file_manager(project.path))
        menu.addAction(open_action)

        menu.addSeparator()

        # Remove project action
        remove_action = QAction("Remove Project", self)
        remove_action.triggered.connect(self._on_remove_project)
        menu.addAction(remove_action)

        menu.exec(self.project_list.mapToGlobal(position))

    def _open_in_file_manager(self, path: str):
        """Open project path in system file manager."""
        import subprocess
        import sys

        try:
            if sys.platform == "win32":
                subprocess.run(["explorer", path], check=True)
            elif sys.platform == "darwin":
                subprocess.run(["open", path], check=True)
            else:  # Linux and other Unix-like systems
                subprocess.run(["xdg-open", path], check=True)
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to open file manager: {e}")
            QMessageBox.warning(
                self,
                "Error",
                f"Failed to open file manager:\n{e}",
            )

    def populate_projects(self, projects: list[Project]):
        """
        Populate the project list with project data.

        Args:
            projects: List of Project instances to display
        """
        # Store projects for reference
        self._projects = {project.id: project for project in projects}

        # Clear and repopulate list
        self.project_list.clear()

        for project in projects:
            item = QListWidgetItem()

            # Set display text with status indicator
            status_icon = self._get_status_icon(project.status)
            display_name = project.get_display_name()
            item.setText(f"{status_icon} {display_name}")

            # Store project ID in item data
            item.setData(Qt.ItemDataRole.UserRole, project.id)

            # Set tooltip with project details
            tooltip = self._create_project_tooltip(project)
            item.setToolTip(tooltip)

            # Set item appearance based on status
            self._apply_status_styling(item, project.status)

            self.project_list.addItem(item)

        # Update status label
        self._update_status_label(len(projects))

        self.logger.debug(f"Populated project list with {len(projects)} projects")

    def _get_status_icon(self, status: ProjectStatus) -> str:
        """Get status icon for project status."""
        icons = {
            ProjectStatus.ACTIVE: "●",
            ProjectStatus.INACTIVE: "○",
            ProjectStatus.ERROR: "✗",
            ProjectStatus.UNAVAILABLE: "⚠",
        }
        return icons.get(status, "○")

    def _create_project_tooltip(self, project: Project) -> str:
        """Create tooltip text for project."""
        return (
            f"Name: {project.get_display_name()}\n"
            f"Path: {project.path}\n"
            f"Status: {project.status.value}\n"
            f"Worktrees: {len(project.worktrees)}\n"
            f"Last Accessed: {project.last_accessed.strftime('%Y-%m-%d %H:%M:%S')}"
        )

    def _apply_status_styling(self, item: QListWidgetItem, status: ProjectStatus):
        """Apply styling to list item based on project status."""
        if status == ProjectStatus.ERROR:
            item.setForeground(Qt.GlobalColor.red)
        elif status == ProjectStatus.UNAVAILABLE:
            item.setForeground(Qt.GlobalColor.gray)
        elif status == ProjectStatus.INACTIVE:
            item.setForeground(Qt.GlobalColor.darkGray)
        # ACTIVE projects use default color

    def _update_status_label(self, count: int):
        """Update the status label with project count."""
        if count == 0:
            self.status_label.setText("No projects loaded")
        elif count == 1:
            self.status_label.setText("1 project loaded")
        else:
            self.status_label.setText(f"{count} projects loaded")

    def clear_projects(self):
        """Clear all projects from the list."""
        self.project_list.clear()
        self._projects.clear()
        self._current_project_id = None
        self.remove_btn.setEnabled(False)
        self._update_status_label(0)

    def get_selected_project_id(self) -> str | None:
        """Get the currently selected project ID."""
        return self._current_project_id

    def select_project(self, project_id: str):
        """
        Select a project by ID.

        Args:
            project_id: ID of the project to select
        """
        for i in range(self.project_list.count()):
            item = self.project_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == project_id:
                self.project_list.setCurrentItem(item)
                break

    def refresh_project_item(self, project: Project):
        """
        Refresh a specific project item in the list.

        Args:
            project: Updated project instance
        """
        # Update stored project
        self._projects[project.id] = project

        # Find and update the list item
        for i in range(self.project_list.count()):
            item = self.project_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == project.id:
                # Update display text
                status_icon = self._get_status_icon(project.status)
                display_name = project.get_display_name()
                item.setText(f"{status_icon} {display_name}")

                # Update tooltip
                tooltip = self._create_project_tooltip(project)
                item.setToolTip(tooltip)

                # Update styling
                self._apply_status_styling(item, project.status)
                break

    def show_validation_error(self, message: str):
        """
        Show validation error message.

        Args:
            message: Error message to display
        """
        QMessageBox.warning(self, "Validation Error", message)

    def show_operation_error(self, title: str, message: str):
        """
        Show operation error message.

        Args:
            title: Error dialog title
            message: Error message to display
        """
        QMessageBox.critical(self, title, message)

    def show_operation_success(self, message: str):
        """
        Show operation success message.

        Args:
            message: Success message to display
        """
        # For now, just log the success. Could be enhanced with status bar integration
        self.logger.info(message)

    def show_project_health(self, project_id: str, health_data: dict):
        """
        Show project health status dialog.

        Args:
            project_id: ID of the project
            health_data: Health status data
        """
        project = self._projects.get(project_id)
        if not project:
            self.logger.error(f"Project not found for health display: {project_id}")
            return

        dialog = ProjectHealthDialog(project, health_data, self)
        dialog.exec()

    def update_project_status_indicators(self):
        """Update status indicators for all projects in the list."""
        for i in range(self.project_list.count()):
            item = self.project_list.item(i)
            project_id = item.data(Qt.ItemDataRole.UserRole)
            if project_id and project_id in self._projects:
                project = self._projects[project_id]

                # Update display text with current status
                status_icon = self._get_status_icon(project.status)
                display_name = project.get_display_name()
                item.setText(f"{status_icon} {display_name}")

                # Update styling
                self._apply_status_styling(item, project.status)

                # Update tooltip
                tooltip = self._create_project_tooltip(project)
                item.setToolTip(tooltip)
