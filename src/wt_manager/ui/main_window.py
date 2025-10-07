"""Main application window."""

import logging
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QFrame,
    QSizePolicy,
    QProgressBar,
    QTextEdit,
    QGroupBox,
    QMenu,
)
from PyQt6.QtCore import Qt, QSettings, pyqtSignal
from PyQt6.QtGui import QAction, QFont

from .project_panel import ProjectPanel


class MainWindow(QMainWindow):
    """Main application window with dual-pane layout."""

    # Signals for communication with services
    project_selected = pyqtSignal(str)  # project_id
    worktree_selected = pyqtSignal(str, str)  # project_id, worktree_path
    add_project_requested = pyqtSignal(str, str)  # path, name
    remove_project_requested = pyqtSignal(str)  # project_id
    refresh_requested = pyqtSignal()
    project_health_requested = pyqtSignal(str)  # project_id
    command_execution_requested = pyqtSignal(str, str)  # worktree_path, command

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.settings = QSettings()

        # Current selections
        self._current_project_id = None
        self._current_worktree_path = None

        # UI components
        self.project_panel = None
        self.worktree_list = None
        self.command_output = None
        self.progress_bar = None

        self._setup_ui()
        self._setup_menu_bar()
        self._setup_toolbar()
        self._setup_status_bar()
        self._setup_connections()
        self._restore_state()

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

        # Create splitter for dual-pane layout
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.main_splitter)

        # Create project panel
        self.project_panel = ProjectPanel()
        self.main_splitter.addWidget(self.project_panel)

        # Create worktree panel
        self.worktree_panel = self._create_worktree_panel()
        self.main_splitter.addWidget(self.worktree_panel)

        # Create command output panel (collapsible)
        self.command_panel = self._create_command_panel()
        self.command_panel.setVisible(False)  # Initially hidden
        main_layout.addWidget(self.command_panel)

        # Set initial splitter proportions (30% projects, 70% worktrees)
        self.main_splitter.setSizes([350, 850])
        self.main_splitter.setStretchFactor(0, 0)  # Project panel fixed
        self.main_splitter.setStretchFactor(1, 1)  # Worktree panel stretches

    def _create_worktree_panel(self) -> QWidget:
        """Create the worktree management panel."""
        panel = QWidget()

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Worktrees header with actions
        header_layout = QHBoxLayout()
        header_label = QLabel("Worktrees")
        header_label.setFont(QFont("", 12, QFont.Weight.Bold))
        header_layout.addWidget(header_label)

        self.project_name_label = QLabel("No project selected")
        self.project_name_label.setStyleSheet("color: #666; font-style: italic;")
        header_layout.addWidget(self.project_name_label)

        header_layout.addStretch()

        self.new_worktree_btn = QPushButton("New Worktree")
        self.new_worktree_btn.setEnabled(False)
        self.new_worktree_btn.setToolTip("Create a new worktree")
        header_layout.addWidget(self.new_worktree_btn)

        layout.addLayout(header_layout)

        # Worktree list
        self.worktree_list = QListWidget()
        self.worktree_list.setAlternatingRowColors(True)
        self.worktree_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.worktree_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        layout.addWidget(self.worktree_list)

        # Worktree actions
        actions_layout = QHBoxLayout()

        self.open_worktree_btn = QPushButton("Open")
        self.open_worktree_btn.setEnabled(False)
        self.open_worktree_btn.setToolTip("Open worktree in file manager")
        actions_layout.addWidget(self.open_worktree_btn)

        self.run_command_btn = QPushButton("Run Command")
        self.run_command_btn.setEnabled(False)
        self.run_command_btn.setToolTip("Run command in worktree")
        actions_layout.addWidget(self.run_command_btn)

        self.remove_worktree_btn = QPushButton("Remove")
        self.remove_worktree_btn.setEnabled(False)
        self.remove_worktree_btn.setToolTip("Remove selected worktree")
        actions_layout.addWidget(self.remove_worktree_btn)

        layout.addLayout(actions_layout)

        return panel

    def _create_command_panel(self) -> QWidget:
        """Create the collapsible command output panel."""
        panel = QGroupBox("Command Output")
        panel.setCheckable(True)
        panel.setChecked(False)
        panel.setMaximumHeight(300)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Command output display
        self.command_output = QTextEdit()
        self.command_output.setReadOnly(True)
        self.command_output.setFont(QFont("Consolas, Monaco, monospace", 9))
        self.command_output.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3e3e3e;
            }
        """)
        layout.addWidget(self.command_output)

        # Command controls
        controls_layout = QHBoxLayout()

        self.clear_output_btn = QPushButton("Clear")
        self.clear_output_btn.setMaximumWidth(60)
        self.clear_output_btn.setToolTip("Clear command output")
        controls_layout.addWidget(self.clear_output_btn)

        controls_layout.addStretch()

        self.command_status_label = QLabel("Ready")
        self.command_status_label.setStyleSheet("color: #666;")
        controls_layout.addWidget(self.command_status_label)

        layout.addLayout(controls_layout)

        return panel

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

        # Worktree panel connections
        self.new_worktree_btn.clicked.connect(self._on_new_worktree_clicked)
        self.open_worktree_btn.clicked.connect(self._on_open_worktree_clicked)
        self.run_command_btn.clicked.connect(self._on_run_command_clicked)
        self.remove_worktree_btn.clicked.connect(self._on_remove_worktree_clicked)
        self.worktree_list.itemSelectionChanged.connect(
            self._on_worktree_selection_changed
        )
        self.worktree_list.customContextMenuRequested.connect(
            self._show_worktree_context_menu
        )

        # Command panel connections
        self.clear_output_btn.clicked.connect(self.command_output.clear)
        self.command_panel.toggled.connect(self._on_command_panel_toggled)

        # Menu action connections
        self.add_project_action.triggered.connect(self._on_add_project_menu)
        self.remove_project_action.triggered.connect(self._on_remove_project_menu)
        self.refresh_action.triggered.connect(self.refresh_requested.emit)
        self.new_worktree_action.triggered.connect(self._on_new_worktree_clicked)
        self.remove_worktree_action.triggered.connect(self._on_remove_worktree_clicked)
        self.open_worktree_action.triggered.connect(self._on_open_worktree_clicked)
        self.run_command_action.triggered.connect(self._on_run_command_clicked)

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

        self.new_worktree_action = QAction("&New Worktree...", self)
        self.new_worktree_action.setShortcut("Ctrl+W")
        self.new_worktree_action.setStatusTip("Create a new worktree")
        self.new_worktree_action.setEnabled(False)
        worktree_menu.addAction(self.new_worktree_action)

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

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.setStatusTip("About Git Worktree Manager")
        help_menu.addAction(about_action)

        keyboard_shortcuts_action = QAction("&Keyboard Shortcuts", self)
        keyboard_shortcuts_action.setStatusTip("Show keyboard shortcuts")
        help_menu.addAction(keyboard_shortcuts_action)

    def _setup_toolbar(self) -> None:
        """Set up the toolbar."""
        toolbar = self.addToolBar("Main")
        toolbar.setObjectName("MainToolBar")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

        # Add project action
        toolbar.addAction(self.add_project_action)

        toolbar.addSeparator()

        # Refresh action
        toolbar.addAction(self.refresh_action)

        toolbar.addSeparator()

        # Worktree actions
        toolbar.addAction(self.new_worktree_action)
        toolbar.addAction(self.run_command_action)

        # Add stretch to push status to the right
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        # Progress bar for operations
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(200)
        toolbar.addWidget(self.progress_bar)

    def _setup_status_bar(self) -> None:
        """Set up the status bar."""
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")

        # Add permanent widgets to status bar
        self.project_count_label = QLabel("No projects loaded")
        self.status_bar.addPermanentWidget(self.project_count_label)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        self.status_bar.addPermanentWidget(separator)

        # Worktree count
        self.worktree_count_label = QLabel("No worktrees")
        self.status_bar.addPermanentWidget(self.worktree_count_label)

        # Another separator
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.Shape.VLine)
        separator2.setFrameShadow(QFrame.Shadow.Sunken)
        self.status_bar.addPermanentWidget(separator2)

        # Operation status
        self.operation_status_label = QLabel("Ready")
        self.status_bar.addPermanentWidget(self.operation_status_label)

    def _toggle_command_panel(self, checked: bool) -> None:
        """Toggle the command output panel visibility."""
        self.command_panel.setChecked(checked)
        self.toggle_command_panel_action.setText(
            "Hide Command &Output" if checked else "Show Command &Output"
        )

    def _on_command_panel_toggled(self, checked: bool) -> None:
        """Handle command panel toggle."""
        self.toggle_command_panel_action.setChecked(checked)
        self.toggle_command_panel_action.setText(
            "Hide Command &Output" if checked else "Show Command &Output"
        )

    def _on_project_selected(self, project_id: str) -> None:
        """Handle project selection change."""
        self._current_project_id = project_id

        # Enable project-related actions
        self.remove_project_action.setEnabled(True)
        self.new_worktree_btn.setEnabled(True)
        self.new_worktree_action.setEnabled(True)

        # Update project name label - we'll need to get the project name
        # This will be handled by the controller layer
        self.project_name_label.setText("Project selected")

    def _on_project_deselected(self) -> None:
        """Handle project deselection."""
        self._current_project_id = None
        self.remove_project_action.setEnabled(False)
        self.new_worktree_btn.setEnabled(False)
        self.new_worktree_action.setEnabled(False)
        self.project_name_label.setText("No project selected")

    def _on_worktree_selection_changed(self) -> None:
        """Handle worktree selection change."""
        selected_items = self.worktree_list.selectedItems()
        if selected_items and self._current_project_id:
            item = selected_items[0]
            worktree_path = item.data(Qt.ItemDataRole.UserRole)
            if worktree_path:
                self._current_worktree_path = worktree_path
                self.worktree_selected.emit(self._current_project_id, worktree_path)

                # Enable worktree-related actions
                self.open_worktree_btn.setEnabled(True)
                self.run_command_btn.setEnabled(True)
                self.remove_worktree_btn.setEnabled(True)
                self.open_worktree_action.setEnabled(True)
                self.run_command_action.setEnabled(True)
                self.remove_worktree_action.setEnabled(True)
        else:
            self._current_worktree_path = None
            self.open_worktree_btn.setEnabled(False)
            self.run_command_btn.setEnabled(False)
            self.remove_worktree_btn.setEnabled(False)
            self.open_worktree_action.setEnabled(False)
            self.run_command_action.setEnabled(False)
            self.remove_worktree_action.setEnabled(False)

    def _on_add_project_menu(self) -> None:
        """Handle add project menu action."""
        # Trigger the project panel's add dialog
        self.project_panel._on_add_project()

    def _on_remove_project_menu(self) -> None:
        """Handle remove project menu action."""
        # Trigger the project panel's remove action
        self.project_panel._on_remove_project()

    def _on_new_worktree_clicked(self) -> None:
        """Handle new worktree button click."""
        # This will be implemented when we create the worktree dialog
        self.update_status("New worktree creation not yet implemented")

    def _on_open_worktree_clicked(self) -> None:
        """Handle open worktree button click."""
        # This will be implemented when we add external application integration
        self.update_status("Open worktree not yet implemented")

    def _on_run_command_clicked(self) -> None:
        """Handle run command button click."""
        # This will be implemented when we create the command dialog
        self.update_status("Run command not yet implemented")

    def _on_remove_worktree_clicked(self) -> None:
        """Handle remove worktree button click."""
        # This will be implemented when we add worktree removal
        self.update_status("Remove worktree not yet implemented")

    def _show_worktree_context_menu(self, position) -> None:
        """Show context menu for worktree list."""
        item = self.worktree_list.itemAt(position)
        if item and self._current_worktree_path:
            menu = QMenu(self)

            menu.addAction("Open in File Manager", self._on_open_worktree_clicked)
            menu.addAction(
                "Open in Terminal",
                lambda: self.update_status("Open in terminal not yet implemented"),
            )
            menu.addAction(
                "Open in Editor",
                lambda: self.update_status("Open in editor not yet implemented"),
            )
            menu.addSeparator()
            menu.addAction("Run Command...", self._on_run_command_clicked)
            menu.addSeparator()
            menu.addAction("Remove Worktree", self._on_remove_worktree_clicked)

            menu.exec(self.worktree_list.mapToGlobal(position))

    def show_command_panel(self) -> None:
        """Show the command output panel."""
        if not self.command_panel.isChecked():
            self.command_panel.setChecked(True)
            self.toggle_command_panel_action.setChecked(True)
            self.toggle_command_panel_action.setText("Hide Command &Output")

    def hide_command_panel(self) -> None:
        """Hide the command output panel."""
        if self.command_panel.isChecked():
            self.command_panel.setChecked(False)
            self.toggle_command_panel_action.setChecked(False)
            self.toggle_command_panel_action.setText("Show Command &Output")

    def update_status(self, message: str, timeout: int = 3000) -> None:
        """Update the status bar message."""
        self.status_bar.showMessage(message, timeout)

    def update_operation_status(self, status: str) -> None:
        """Update the operation status in the status bar."""
        self.operation_status_label.setText(status)

    def update_project_count(self, count: int) -> None:
        """Update the project count in the status bar."""
        if count == 0:
            self.project_count_label.setText("No projects loaded")
        elif count == 1:
            self.project_count_label.setText("1 project loaded")
        else:
            self.project_count_label.setText(f"{count} projects loaded")

    def update_worktree_count(self, count: int) -> None:
        """Update the worktree count in the status bar."""
        if count == 0:
            self.worktree_count_label.setText("No worktrees")
        elif count == 1:
            self.worktree_count_label.setText("1 worktree")
        else:
            self.worktree_count_label.setText(f"{count} worktrees")

    def show_progress(self, message: str = "") -> None:
        """Show progress bar with optional message."""
        self.progress_bar.setVisible(True)
        if message:
            self.update_operation_status(message)

    def hide_progress(self) -> None:
        """Hide progress bar."""
        self.progress_bar.setVisible(False)
        self.update_operation_status("Ready")

    def set_progress_value(self, value: int) -> None:
        """Set progress bar value (0-100)."""
        self.progress_bar.setValue(value)

    def set_progress_indeterminate(self) -> None:
        """Set progress bar to indeterminate mode."""
        self.progress_bar.setRange(0, 0)

    def populate_projects(self, projects: list) -> None:
        """Populate the project list with project data."""
        self.project_panel.populate_projects(projects)
        self.update_project_count(len(projects))

    def populate_worktrees(self, worktrees: list) -> None:
        """Populate the worktree list with worktree data."""
        self.worktree_list.clear()

        for worktree in worktrees:
            item = QListWidgetItem()

            # Set display text with branch and status
            status_display = worktree.get_status_display()
            branch_display = worktree.get_branch_display()

            item.setText(
                f"{worktree.get_directory_name()} ({branch_display}) - {status_display}"
            )

            # Store worktree path in item data
            item.setData(Qt.ItemDataRole.UserRole, worktree.path)

            # Set tooltip with worktree details
            tooltip = (
                f"Path: {worktree.path}\n"
                f"Branch: {branch_display}\n"
                f"Commit: {worktree.get_commit_short_hash()}\n"
                f"Status: {status_display}\n"
                f"Last Modified: {worktree.get_age_display()}"
            )
            item.setToolTip(tooltip)

            # Set item color based on status
            if worktree.has_uncommitted_changes:
                item.setForeground(Qt.GlobalColor.blue)
            elif worktree.is_detached:
                item.setForeground(Qt.GlobalColor.darkYellow)

            self.worktree_list.addItem(item)

        self.update_worktree_count(len(worktrees))

    def append_command_output(self, text: str) -> None:
        """Append text to the command output panel."""
        if not self.command_panel.isChecked():
            self.show_command_panel()

        self.command_output.append(text)

        # Auto-scroll to bottom
        scrollbar = self.command_output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def set_command_status(self, status: str) -> None:
        """Set the command status label."""
        self.command_status_label.setText(status)

    def clear_worktrees(self) -> None:
        """Clear the worktree list."""
        self.worktree_list.clear()
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
        self.settings.setValue("commandPanelVisible", self.command_panel.isChecked())

        # Save command panel height if visible
        if self.command_panel.isChecked():
            self.settings.setValue("commandPanelHeight", self.command_panel.height())

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

        command_panel_visible = self.settings.value(
            "commandPanelVisible", False, type=bool
        )
        if command_panel_visible:
            self.show_command_panel()

            # Restore command panel height
            panel_height = self.settings.value("commandPanelHeight", 200, type=int)
            self.command_panel.setMaximumHeight(panel_height)

        self.logger.debug("Window state restored")

    def closeEvent(self, event) -> None:
        """Handle window close event."""
        self.save_state()
        self.logger.info("Main window closing")
        event.accept()
