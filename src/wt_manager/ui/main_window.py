"""Main application window."""

import logging
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QSplitter,
    QLabel,
    QGroupBox,
    QDialog,
)
from PyQt6.QtCore import Qt, QSettings, pyqtSignal
from PyQt6.QtGui import QAction

from .project_panel import ProjectPanel
from .worktree_panel import WorktreePanel
from .command_dialog import CommandInputDialog
from .command_output_widget import CommandOutputPanel
from .preferences_dialog import PreferencesDialog
from ..services.message_service import initialize_message_service
from ..services.worktree_service import WorktreeService


class MainWindow(QMainWindow):
    """Main application window with dual-pane layout."""

    # Signals for communication with services
    project_selected = pyqtSignal(str)  # project_id
    worktree_selected = pyqtSignal(str)  # worktree_path
    add_project_requested = pyqtSignal(str, str)  # path, name
    remove_project_requested = pyqtSignal(str)  # project_id
    refresh_requested = pyqtSignal()
    project_health_requested = pyqtSignal(str)  # project_id
    create_worktree_requested = pyqtSignal(str, dict)  # project_id, config
    remove_worktree_requested = pyqtSignal(
        str, str, dict
    )  # project_id, worktree_path, config
    open_worktree_requested = pyqtSignal(str, str)  # worktree_path, action_type
    run_command_requested = pyqtSignal(str)  # worktree_path
    refresh_worktrees_requested = pyqtSignal(str)  # project_id
    preferences_updated = pyqtSignal(object)  # UserPreferences

    def __init__(
        self,
        command_service=None,
        validation_service=None,
        worktree_service=None,
        config=None,
    ):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.settings = QSettings()
        self.config = config

        # Services
        self.command_service = command_service
        self.validation_service = validation_service
        self.worktree_service = worktree_service or WorktreeService()

        # Current selections
        self._current_project_id = None
        self._current_worktree_path = None

        # UI components
        self.project_panel = None
        self.worktree_list = None
        self.command_output = None
        self.progress_bar = None

        # Active command executions
        self._active_executions = {}

        self._setup_ui()
        self._setup_menu_bar()
        self._setup_toolbar()
        # self._setup_status_bar()
        self._setup_connections()
        self._restore_state()

        # Set up command service callbacks if available
        if self.command_service:
            self._setup_command_service_callbacks()

        # Initialize message service with status bar interface
        self.message_service = initialize_message_service(self, self)

        self.logger.info("Main window initialized")

    def _setup_ui(self) -> None:
        """Set up the main UI layout."""
        self.setWindowTitle("Git Worktree Manager")
        self.setMinimumSize(1000, 700)
        self.resize(1200, 800)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Create main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # Create vertical splitter for main content and command panel
        self.vertical_splitter = QSplitter(Qt.Orientation.Vertical)
        self.vertical_splitter.setAccessibleName("Vertical content splitter")
        main_layout.addWidget(self.vertical_splitter)

        # Create splitter for dual-pane layout
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setAccessibleName("Main content splitter")
        self.vertical_splitter.addWidget(self.main_splitter)

        # Create project panel
        self.project_panel = ProjectPanel()
        self.project_panel.setAccessibleName("Projects panel")
        self.project_panel.setToolTip(
            "Manage Git projects - Add, remove, and select projects to work with"
        )
        self.main_splitter.addWidget(self.project_panel)

        # Create worktree panel
        self.worktree_panel = WorktreePanel(self.config, self.worktree_service)
        self.worktree_panel.setAccessibleName("Worktrees panel")
        self.worktree_panel.setToolTip(
            "Manage worktrees for the selected project - Create, remove, and open worktrees"
        )
        self.main_splitter.addWidget(self.worktree_panel)

        # Create command output panel (collapsible)
        self.command_panel_group = QGroupBox("Command Output")
        self.command_panel_group.setCheckable(True)
        self.command_panel_group.setChecked(False)  # Ensure it starts unchecked
        self.command_panel_group.setMinimumHeight(100)
        self.command_panel_group.setAccessibleName("Command output panel")
        self.command_panel_group.setToolTip(
            "View real-time output from commands executed in worktrees"
        )

        command_panel_layout = QVBoxLayout(self.command_panel_group)
        command_panel_layout.setContentsMargins(6, 6, 6, 6)

        self.command_panel = CommandOutputPanel()
        command_panel_layout.addWidget(self.command_panel)

        self.vertical_splitter.addWidget(self.command_panel_group)

        # Set initial splitter proportions (30% projects, 70% worktrees)
        self.main_splitter.setSizes([350, 850])
        self.main_splitter.setStretchFactor(0, 0)  # Project panel fixed
        self.main_splitter.setStretchFactor(1, 1)  # Worktree panel stretches

        # Set vertical splitter proportions (main content stretches, command panel minimum)
        self.vertical_splitter.setSizes([700, 200])
        self.vertical_splitter.setStretchFactor(0, 1)  # Main splitter stretches
        self.vertical_splitter.setStretchFactor(1, 0)  # Command panel fixed

        # Set up focus policy for better keyboard navigation
        self.project_panel.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.worktree_panel.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.command_panel.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _setup_connections(self) -> None:
        """Set up signal-slot connections."""
        # Project panel connections
        self.project_panel.project_selected.connect(self._on_project_selected)
        self.project_panel.project_selected.connect(self.project_selected.emit)
        self.project_panel.add_project_requested.connect(
            self.add_project_requested.emit
        )
        self.project_panel.remove_project_requested.connect(
            self.remove_project_requested.emit
        )
        self.project_panel.refresh_projects_requested.connect(
            self.refresh_requested.emit
        )
        self.project_panel.project_health_requested.connect(
            self.project_health_requested.emit
        )
        self.project_panel.create_worktree_requested.connect(
            self.create_worktree_requested.emit
        )
        self.project_panel.get_available_branches_requested.connect(
            self.worktree_panel.get_available_branches_requested.emit
        )

        # Connect worktree panel branches received back to project panel
        self.worktree_panel.available_branches_received.connect(
            self.project_panel.on_available_branches_received
        )

        # Worktree panel connections
        self.worktree_panel.worktree_selected.connect(self._on_worktree_selected)
        self.worktree_panel.create_worktree_requested.connect(
            self._on_create_worktree_requested
        )
        self.worktree_panel.remove_worktree_requested.connect(
            self._on_remove_worktree_requested
        )
        self.worktree_panel.open_worktree_requested.connect(
            self._on_open_worktree_requested
        )
        self.worktree_panel.run_command_requested.connect(
            self._on_run_command_requested
        )
        self.worktree_panel.refresh_worktrees_requested.connect(
            self._on_refresh_worktrees_requested
        )

        # Preferences connections
        self.preferences_updated.connect(self.worktree_panel.update_preferences)

        # Command panel connections
        self.command_panel.cancel_command_requested.connect(self._cancel_single_command)
        self.command_panel_group.toggled.connect(self._on_command_panel_toggled)

        # Menu action connections
        self.add_project_action.triggered.connect(self._on_add_project_menu)
        self.remove_project_action.triggered.connect(self._on_remove_project_menu)
        self.refresh_action.triggered.connect(self.refresh_requested.emit)

        self.remove_worktree_action.triggered.connect(self._on_remove_worktree_menu)
        self.open_worktree_action.triggered.connect(self._on_open_worktree_menu)
        self.run_command_action.triggered.connect(self._on_run_command_menu)

    def _setup_menu_bar(self) -> None:
        """Set up the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        self.add_project_action = QAction("&Add Project...", self)
        self.add_project_action.setShortcut("Ctrl+N")
        self.add_project_action.setStatusTip("Add a new Git project")
        file_menu.addAction(self.add_project_action)

        self.remove_project_action = QAction("&Remove Project", self)
        self.remove_project_action.setShortcut("Ctrl+D")
        self.remove_project_action.setStatusTip("Remove selected project")
        self.remove_project_action.setEnabled(False)
        file_menu.addAction(self.remove_project_action)

        file_menu.addSeparator()

        self.refresh_action = QAction("&Refresh All", self)
        self.refresh_action.setShortcut("F5")
        self.refresh_action.setStatusTip("Refresh all projects and worktrees")
        file_menu.addAction(self.refresh_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.setStatusTip("Exit the application")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Worktree menu
        worktree_menu = menubar.addMenu("&Worktree")

        self.remove_worktree_action = QAction("&Remove Worktree", self)
        self.remove_worktree_action.setShortcut("Ctrl+R")
        self.remove_worktree_action.setStatusTip("Remove selected worktree")
        self.remove_worktree_action.setEnabled(False)
        worktree_menu.addAction(self.remove_worktree_action)

        worktree_menu.addSeparator()

        self.open_worktree_action = QAction("&Open in File Manager", self)
        self.open_worktree_action.setShortcut("Ctrl+O")
        self.open_worktree_action.setStatusTip("Open worktree in file manager")
        self.open_worktree_action.setEnabled(False)
        worktree_menu.addAction(self.open_worktree_action)

        self.run_command_action = QAction("Run &Command...", self)
        self.run_command_action.setShortcut("Ctrl+T")
        self.run_command_action.setStatusTip("Run command in selected worktree")
        self.run_command_action.setEnabled(False)
        worktree_menu.addAction(self.run_command_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        self.toggle_command_panel_action = QAction("Show Command &Output", self)
        self.toggle_command_panel_action.setCheckable(True)
        self.toggle_command_panel_action.setStatusTip("Toggle command output panel")
        self.toggle_command_panel_action.triggered.connect(self._toggle_command_panel)
        view_menu.addAction(self.toggle_command_panel_action)

        view_menu.addSeparator()

        self.expand_all_action = QAction("&Expand All", self)
        self.expand_all_action.setStatusTip("Expand all project sections")
        view_menu.addAction(self.expand_all_action)

        self.collapse_all_action = QAction("&Collapse All", self)
        self.collapse_all_action.setStatusTip("Collapse all project sections")
        view_menu.addAction(self.collapse_all_action)

        # Edit menu
        edit_menu = menubar.addMenu("&Edit")

        self.preferences_action = QAction("&Preferences...", self)
        self.preferences_action.setShortcut("Ctrl+,")
        self.preferences_action.setStatusTip("Configure application preferences")
        self.preferences_action.triggered.connect(self._show_preferences_dialog)
        edit_menu.addAction(self.preferences_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.setStatusTip("About Git Worktree Manager")
        about_action.triggered.connect(self._show_about_dialog)
        help_menu.addAction(about_action)

        keyboard_shortcuts_action = QAction("&Keyboard Shortcuts", self)
        keyboard_shortcuts_action.setShortcut("F1")
        keyboard_shortcuts_action.setStatusTip("Show keyboard shortcuts")
        keyboard_shortcuts_action.triggered.connect(self._show_keyboard_shortcuts)
        help_menu.addAction(keyboard_shortcuts_action)

    def _setup_toolbar(self) -> None:
        """Set up the toolbar."""
        # Toolbar removed as it's no longer needed
        pass

    def _setup_status_bar(self) -> None:
        """Set up the status bar."""
        # Status bar removed
        pass

    def _toggle_command_panel(self, checked: bool) -> None:
        """Toggle the command output panel visibility."""
        self.command_panel_group.setChecked(checked)
        self.toggle_command_panel_action.setText(
            "Hide Command &Output" if checked else "Show Command &Output"
        )

    def _on_command_panel_toggled(self, checked: bool) -> None:
        """Handle command panel toggle."""
        self.toggle_command_panel_action.setChecked(checked)
        self.toggle_command_panel_action.setText(
            "Hide Command &Output" if checked else "Show Command &Output"
        )
        self.command_panel_group.setVisible(checked)

    def _on_project_selected(self, project_id: str) -> None:
        """Handle project selection change."""
        self._current_project_id = project_id

        # Enable project-related actions
        self.remove_project_action.setEnabled(True)

    def _on_project_deselected(self) -> None:
        """Handle project deselection."""
        self._current_project_id = None
        self.remove_project_action.setEnabled(False)

    def _on_worktree_selected(self, worktree_path: str) -> None:
        """Handle worktree selection change."""
        self._current_worktree_path = worktree_path
        self.worktree_selected.emit(worktree_path)

        # Enable worktree-related actions
        self.open_worktree_action.setEnabled(True)
        self.run_command_action.setEnabled(True)
        self.remove_worktree_action.setEnabled(True)

    def _on_add_project_menu(self) -> None:
        """Handle add project menu action."""
        # Trigger the project panel's add dialog
        self.project_panel._on_add_project()

    def _on_remove_project_menu(self) -> None:
        """Handle remove project menu action."""
        # Trigger the project panel's remove action
        self.project_panel._on_remove_project()

    def _on_create_worktree_requested(self, project_id: str, config: dict) -> None:
        """Handle create worktree request from worktree panel."""
        self.create_worktree_requested.emit(project_id, config)

    def _on_remove_worktree_requested(
        self, project_id: str, worktree_path: str, config: dict
    ) -> None:
        """Handle remove worktree request from worktree panel."""
        self.remove_worktree_requested.emit(project_id, worktree_path, config)

    def _on_open_worktree_requested(self, worktree_path: str, action_type: str) -> None:
        """Handle open worktree request from worktree panel."""
        self.open_worktree_requested.emit(worktree_path, action_type)

    def _on_run_command_requested(self, worktree_path: str) -> None:
        """Handle run command request from worktree panel."""
        self._show_command_dialog(worktree_path)

    def _on_refresh_worktrees_requested(self, project_id: str) -> None:
        """Handle refresh worktrees request from worktree panel."""
        self.refresh_worktrees_requested.emit(project_id)

    # Menu action handlers
    def _on_new_worktree_menu(self) -> None:
        """Handle new worktree menu action."""
        # This method is kept for compatibility but should not be called
        # since the menu item was removed
        pass

    def _on_remove_worktree_menu(self) -> None:
        """Handle remove worktree menu action."""
        # Delegate to worktree panel to show dialog
        self.worktree_panel._on_remove_worktree()

    def _on_open_worktree_menu(self) -> None:
        """Handle open worktree menu action."""
        if self._current_worktree_path:
            self.open_worktree_requested.emit(
                self._current_worktree_path, "file_manager"
            )

    def _on_run_command_menu(self) -> None:
        """Handle run command menu action."""
        if self._current_worktree_path:
            self._show_command_dialog(self._current_worktree_path)

    def show_command_panel(self) -> None:
        """Show the command output panel."""
        if not self.command_panel_group.isChecked():
            self.command_panel_group.setChecked(True)
            self.command_panel_group.setVisible(True)
            self.toggle_command_panel_action.setChecked(True)
            self.toggle_command_panel_action.setText("Hide Command &Output")

    def hide_command_panel(self) -> None:
        """Hide the command output panel."""
        if self.command_panel_group.isChecked():
            self.command_panel_group.setChecked(False)
            self.command_panel_group.setVisible(False)
            self.toggle_command_panel_action.setChecked(False)
            self.toggle_command_panel_action.setText("Show Command &Output")

    def update_status(self, message: str, timeout: int = 3000) -> None:
        """Update the status bar message."""
        # Status bar removed
        self.logger.info(f"Status update: {message}")

    def show_message(self, message: str, timeout: int = 3000) -> None:
        """
        StatusBarInterface implementation.
        Show a message in the status bar.
        """
        self.update_status(message, timeout)

    def update_operation_status(self, status: str) -> None:
        """Update the operation status in the status bar."""
        # Status bar removed
        pass

    def update_project_count(self, count: int) -> None:
        """Update the project count in the status bar."""
        # Status bar removed
        pass

    def update_worktree_count(self, count: int) -> None:
        """Update the worktree count in the status bar."""
        # Status bar removed
        pass

    def show_progress(self, message: str = "") -> None:
        """Show progress indication with optional message."""
        if message:
            self.update_operation_status(message)

    def hide_progress(self) -> None:
        """Hide progress indication."""
        self.update_operation_status("Ready")

    def set_progress_value(self, value: int) -> None:
        """Set progress value (0-100) - no-op since progress bar removed."""
        pass

    def set_progress_indeterminate(self) -> None:
        """Set progress to indeterminate mode - no-op since progress bar removed."""
        pass

    def populate_projects(self, projects: list) -> None:
        """Populate the project list with project data."""
        self.project_panel.populate_projects(projects)
        self.update_project_count(len(projects))

    def set_current_project(self, project) -> None:
        """Set the current project in the worktree panel."""
        self.worktree_panel.set_project(project)

    def populate_worktrees(self, worktrees: list) -> None:
        """Populate the worktree list with worktree data."""
        self.worktree_panel.populate_worktrees(worktrees)
        self.update_worktree_count(len(worktrees))

    def clear_worktrees(self) -> None:
        """Clear the worktree list."""
        self.worktree_panel.clear_worktrees()
        self.update_worktree_count(0)

    def clear_projects(self) -> None:
        """Clear the project list."""
        self.project_panel.clear_projects()
        self.update_project_count(0)

    def refresh_project_item(self, project) -> None:
        """Refresh a specific project item."""
        self.project_panel.refresh_project_item(project)

    def show_project_validation_error(self, message: str) -> None:
        """Show project validation error."""
        self.project_panel.show_validation_error(message)

    def show_project_operation_error(self, title: str, message: str) -> None:
        """Show project operation error."""
        self.project_panel.show_operation_error(title, message)

    def show_project_operation_success(self, message: str) -> None:
        """Show project operation success."""
        self.project_panel.show_operation_success(message)

    def show_project_health(self, project_id: str, health_data: dict) -> None:
        """Show project health status dialog."""
        self.project_panel.show_project_health(project_id, health_data)

    def _get_status_icon(self, status: str) -> str:
        """Get status icon for project status."""
        icons = {"active": "●", "inactive": "○", "error": "✗", "unavailable": "⚠"}
        return icons.get(status, "○")

    def save_state(self) -> None:
        """Save window state and geometry."""
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        self.settings.setValue("splitterSizes", self.main_splitter.sizes())
        self.settings.setValue("verticalSplitterSizes", self.vertical_splitter.sizes())
        self.settings.setValue(
            "commandPanelVisible", self.command_panel_group.isChecked()
        )

        self.logger.debug("Window state saved")

    def _restore_state(self) -> None:
        """Restore window state and geometry."""
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

        window_state = self.settings.value("windowState")
        if window_state:
            self.restoreState(window_state)

        splitter_sizes = self.settings.value("splitterSizes")
        if splitter_sizes:
            # Convert to list of integers
            sizes = [int(size) for size in splitter_sizes]
            self.main_splitter.setSizes(sizes)

        vertical_splitter_sizes = self.settings.value("verticalSplitterSizes")
        if vertical_splitter_sizes:
            # Convert to list of integers
            sizes = [int(size) for size in vertical_splitter_sizes]
            self.vertical_splitter.setSizes(sizes)
        else:
            # Backward compatibility: if no vertical sizes, use default
            self.vertical_splitter.setSizes([700, 200])

        command_panel_visible = self.settings.value(
            "commandPanelVisible", False, type=bool
        )
        if command_panel_visible:
            self.show_command_panel()
        else:
            self.command_panel_group.setVisible(False)

        self.logger.debug("Window state restored")

    def _setup_command_service_callbacks(self) -> None:
        """Set up command service callbacks for UI updates."""
        if not self.command_service:
            return

        self.command_service.on_command_started = self._on_command_started
        self.command_service.on_command_finished = self._on_command_finished
        self.command_service.on_command_output = self._on_command_output
        self.command_service.on_command_error = self._on_command_error

    def _show_command_dialog(self, worktree_path: str) -> None:
        """Show the command input dialog for the specified worktree."""
        try:
            # Get command history for this worktree
            command_history = []
            if self.command_service:
                history = self.command_service.get_command_history(
                    worktree_path, limit=20
                )
                command_history = [exec.command for exec in history]

            # Create and show dialog
            dialog = CommandInputDialog(
                worktree_path=worktree_path,
                command_history=command_history,
                validation_service=self.validation_service,
                parent=self,
            )

            # Connect dialog signals
            dialog.command_execution_requested.connect(self._execute_command)

            # Show dialog
            dialog.exec()

        except Exception as e:
            self.logger.error(f"Error showing command dialog: {e}")
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.critical(self, "Error", f"Failed to show command dialog:\n{e}")

    def _execute_command(self, command: str, worktree_path: str, timeout: int) -> None:
        """Execute a command in the specified worktree."""
        if not self.command_service:
            self.logger.error("No command service available")
            return

        try:
            # Show command panel
            self.show_command_panel()

            # Execute command
            execution = self.command_service.execute_command(
                command=command,
                worktree_path=worktree_path,
                timeout_seconds=timeout if timeout > 0 else None,
            )

            # Track execution
            self._active_executions[execution.id] = execution

            # Add execution to command panel
            self.command_panel.add_execution(execution)

            # Update status
            self.command_panel.set_status(f"Running: {execution.get_command_display()}")
            self.update_operation_status("Executing command...")

            self.logger.info(f"Started command execution: {command} in {worktree_path}")

        except Exception as e:
            self.logger.error(f"Error executing command: {e}")
            self.command_panel.set_status(f"Error: {e}")
            self.update_operation_status("Ready")

    def _on_command_started(self, execution_id: str) -> None:
        """Handle command execution started."""
        execution = self._active_executions.get(execution_id)
        if execution:
            self.command_panel.update_execution(execution)
            self.command_panel.set_status(f"Running: {execution.get_command_display()}")

    def _on_command_finished(self, execution_id: str) -> None:
        """Handle command execution finished."""
        execution = self._active_executions.pop(execution_id, None)
        if execution:
            self.command_panel.update_execution(execution)

            if execution.is_successful():
                self.command_panel.set_status("Completed successfully")
            else:
                status = execution.get_status_display()
                self.command_panel.set_status(f"Failed: {status}")

            self.update_operation_status("Ready")

    def _on_command_output(self, execution_id: str, output: str) -> None:
        """Handle command output received."""
        # Remove trailing newline to avoid double spacing
        output = output.rstrip("\n\r")
        if output:
            self.command_panel.append_output(execution_id, output, is_error=False)

    def _on_command_error(self, execution_id: str, error: str) -> None:
        """Handle command error output received."""
        # Remove trailing newline to avoid double spacing
        error = error.rstrip("\n\r")
        if error:
            self.command_panel.append_output(execution_id, error, is_error=True)

    def cancel_running_commands(self) -> None:
        """Cancel all running commands."""
        if not self.command_service:
            return

        active_executions = list(self._active_executions.keys())
        for execution_id in active_executions:
            self.command_service.cancel_command(execution_id)

        if active_executions:
            self.command_panel.set_status("Cancelling commands...")
            self.update_operation_status("Cancelling...")

    def _cancel_single_command(self, execution_id: str) -> None:
        """Cancel a single command execution."""
        if not self.command_service:
            return

        if self.command_service.cancel_command(execution_id):
            self.command_panel.set_status("Cancelling command...")
            self.logger.info(f"Cancelled command execution: {execution_id}")

    def _show_about_dialog(self) -> None:
        """Show the about dialog."""
        from PyQt6.QtWidgets import QMessageBox

        about_text = """
        <h2>Git Worktree Manager</h2>
        <p><b>Version:</b> 0.1.0</p>
        <p><b>Description:</b> A modern PyQt6-based GUI application for managing Git worktrees across multiple projects.</p>
        <p><b>Features:</b></p>
        <ul>
        <li>Multi-project management</li>
        <li>Worktree operations (create, remove, manage)</li>
        <li>Command execution with real-time output</li>
        <li>Smart branch management</li>
        <li>Safety features and validation</li>
        </ul>
        <p><b>Built with:</b> Python, PyQt6, Git</p>
        """

        QMessageBox.about(self, "About Git Worktree Manager", about_text)

    def _show_preferences_dialog(self) -> None:
        """Show the preferences dialog."""
        # Get current preferences from config
        current_prefs = self.config.preferences

        dialog = PreferencesDialog(current_prefs, self)
        dialog.preferences_changed.connect(self.preferences_updated.emit)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.logger.info("Preferences dialog accepted")
        else:
            self.logger.info("Preferences dialog cancelled")

    def _show_keyboard_shortcuts(self) -> None:
        """Show the keyboard shortcuts dialog."""
        from PyQt6.QtWidgets import (
            QDialog,
            QVBoxLayout,
            QDialogButtonBox,
            QScrollArea,
        )

        dialog = QDialog(self)
        dialog.setWindowTitle("Keyboard Shortcuts")
        dialog.setMinimumSize(500, 400)

        layout = QVBoxLayout(dialog)

        # Create scroll area for shortcuts
        scroll_area = QScrollArea()
        scroll_widget = QLabel()
        scroll_widget.setWordWrap(True)

        shortcuts_text = """
        <h3>File Operations</h3>
        <table>
        <tr><td><b>Ctrl+N</b></td><td>Add new project</td></tr>
        <tr><td><b>Ctrl+D</b></td><td>Remove selected project</td></tr>
        <tr><td><b>F5</b></td><td>Refresh all projects</td></tr>
        <tr><td><b>Ctrl+Q</b></td><td>Exit application</td></tr>
        </table>

        <h3>Worktree Operations</h3>
        <table>
        <tr><td><b>Ctrl+R</b></td><td>Remove selected worktree</td></tr>
        <tr><td><b>Ctrl+O</b></td><td>Open worktree in file manager</td></tr>
        <tr><td><b>Ctrl+T</b></td><td>Run command in selected worktree</td></tr>
        </table>

        <h3>View Operations</h3>
        <table>
        <tr><td><b>Ctrl+Shift+O</b></td><td>Toggle command output panel</td></tr>
        <tr><td><b>Escape</b></td><td>Cancel running command</td></tr>
        </table>

        <h3>Navigation</h3>
        <table>
        <tr><td><b>Tab</b></td><td>Navigate between panels</td></tr>
        <tr><td><b>Up/Down</b></td><td>Navigate within lists</td></tr>
        <tr><td><b>Enter</b></td><td>Activate selected item</td></tr>
        </table>

        <h3>Help</h3>
        <table>
        <tr><td><b>F1</b></td><td>Show this help dialog</td></tr>
        </table>
        """

        scroll_widget.setText(shortcuts_text)
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)

        # Add OK button
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(dialog.accept)
        layout.addWidget(button_box)

        dialog.exec()

    def keyPressEvent(self, event) -> None:
        """Handle key press events for additional shortcuts."""
        from PyQt6.QtCore import Qt

        key = event.key()
        modifiers = event.modifiers()

        # Escape key cancels running commands
        if key == Qt.Key.Key_Escape:
            if self._active_executions:
                self.cancel_running_commands()
                event.accept()
                return

        # Ctrl+Shift+O toggles command panel
        if (
            modifiers
            == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
            and key == Qt.Key.Key_O
        ):
            self._toggle_command_panel(not self.command_panel_group.isChecked())
            event.accept()
            return

        # Pass to parent for default handling
        super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        """Handle window close event."""
        # Cancel any running commands
        if self._active_executions:
            self.cancel_running_commands()

        # Clean up command panel
        self.command_panel.cleanup()

        self.save_state()
        self.logger.info("Main window closing")
        event.accept()
