"""Main application window."""

import logging
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QSplitter, QLabel
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QAction


class MainWindow(QMainWindow):
    """Main application window with dual-pane layout."""

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.settings = QSettings()

        self._setup_ui()
        self._setup_menu_bar()
        self._setup_toolbar()
        self._setup_status_bar()
        self._restore_state()

        self.logger.info("Main window initialized")

    def _setup_ui(self) -> None:
        """Set up the main UI layout."""
        self.setWindowTitle("Git Worktree Manager")
        self.setMinimumSize(800, 600)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Create main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # Create splitter for dual-pane layout
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.main_splitter)

        # Create project panel placeholder
        self.project_panel = QWidget()
        self.project_panel.setMinimumWidth(250)
        project_layout = QVBoxLayout(self.project_panel)
        project_layout.addWidget(QLabel("Projects Panel"))
        self.main_splitter.addWidget(self.project_panel)

        # Create worktree panel placeholder
        self.worktree_panel = QWidget()
        self.worktree_panel.setMinimumWidth(400)
        worktree_layout = QVBoxLayout(self.worktree_panel)
        worktree_layout.addWidget(QLabel("Worktrees Panel"))
        self.main_splitter.addWidget(self.worktree_panel)

        # Create command output panel placeholder (collapsible)
        self.command_panel = QWidget()
        self.command_panel.setMaximumHeight(200)
        self.command_panel.setVisible(False)  # Initially hidden
        command_layout = QVBoxLayout(self.command_panel)
        command_layout.addWidget(QLabel("Command Output Panel"))
        main_layout.addWidget(self.command_panel)

        # Set initial splitter proportions
        self.main_splitter.setSizes([300, 500])

    def _setup_menu_bar(self) -> None:
        """Set up the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        add_project_action = QAction("&Add Project...", self)
        add_project_action.setShortcut("Ctrl+N")
        add_project_action.setStatusTip("Add a new Git project")
        file_menu.addAction(add_project_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.setStatusTip("Exit the application")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        self.toggle_command_panel_action = QAction("Show Command &Output", self)
        self.toggle_command_panel_action.setCheckable(True)
        self.toggle_command_panel_action.setStatusTip("Toggle command output panel")
        self.toggle_command_panel_action.triggered.connect(self._toggle_command_panel)
        view_menu.addAction(self.toggle_command_panel_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.setStatusTip("About Git Worktree Manager")
        help_menu.addAction(about_action)

    def _setup_toolbar(self) -> None:
        """Set up the toolbar."""
        toolbar = self.addToolBar("Main")
        toolbar.setObjectName("MainToolBar")
        toolbar.setMovable(False)

        # Add project action
        add_project_action = QAction("Add Project", self)
        add_project_action.setStatusTip("Add a new Git project")
        toolbar.addAction(add_project_action)

        toolbar.addSeparator()

        # Refresh action
        refresh_action = QAction("Refresh", self)
        refresh_action.setStatusTip("Refresh current view")
        toolbar.addAction(refresh_action)

    def _setup_status_bar(self) -> None:
        """Set up the status bar."""
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")

        # Add permanent widgets to status bar
        self.status_label = QLabel("No projects loaded")
        self.status_bar.addPermanentWidget(self.status_label)

    def _toggle_command_panel(self, checked: bool) -> None:
        """Toggle the command output panel visibility."""
        self.command_panel.setVisible(checked)
        self.toggle_command_panel_action.setText(
            "Hide Command &Output" if checked else "Show Command &Output"
        )

    def show_command_panel(self) -> None:
        """Show the command output panel."""
        if not self.command_panel.isVisible():
            self.command_panel.setVisible(True)
            self.toggle_command_panel_action.setChecked(True)
            self.toggle_command_panel_action.setText("Hide Command &Output")

    def hide_command_panel(self) -> None:
        """Hide the command output panel."""
        if self.command_panel.isVisible():
            self.command_panel.setVisible(False)
            self.toggle_command_panel_action.setChecked(False)
            self.toggle_command_panel_action.setText("Show Command &Output")

    def update_status(self, message: str) -> None:
        """Update the status bar message."""
        self.status_bar.showMessage(message, 3000)  # Show for 3 seconds

    def update_project_count(self, count: int) -> None:
        """Update the project count in the status bar."""
        if count == 0:
            self.status_label.setText("No projects loaded")
        elif count == 1:
            self.status_label.setText("1 project loaded")
        else:
            self.status_label.setText(f"{count} projects loaded")

    def save_state(self) -> None:
        """Save window state and geometry."""
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        self.settings.setValue("splitterSizes", self.main_splitter.sizes())
        self.settings.setValue("commandPanelVisible", self.command_panel.isVisible())

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

        self.logger.debug("Window state restored")

    def closeEvent(self, event) -> None:
        """Handle window close event."""
        self.save_state()
        self.logger.info("Main window closing")
        event.accept()
