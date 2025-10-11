"""Main application controller that coordinates all services and UI components."""

import logging
from datetime import datetime

from PyQt6.QtCore import QObject, pyqtSignal, QTimer

from ..models.project import Project
from ..models.worktree import Worktree
from ..services.project_service import ProjectService
from ..services.worktree_service import WorktreeService
from ..services.command_service import CommandService
from ..services.validation_service import ValidationService
from ..services.config_manager import ConfigManager
from ..services.git_service import GitService
from ..services.message_service import get_message_service
from ..ui.main_window import MainWindow
from ..utils.exceptions import ServiceError, ValidationError, GitError
from ..utils.error_handler import ErrorHandler


class ApplicationController(QObject):
    """
    Main application controller that coordinates services and UI components.

    This controller acts as the central coordinator between the UI layer and
    the service layer, handling all business logic and state management.
    """

    # Signals for application-wide events
    project_added = pyqtSignal(Project)
    project_removed = pyqtSignal(str)  # project_id
    project_updated = pyqtSignal(Project)
    worktree_created = pyqtSignal(str, Worktree)  # project_id, worktree
    worktree_removed = pyqtSignal(str, str)  # project_id, worktree_path
    application_error = pyqtSignal(str, str)  # title, message

    def __init__(self):
        """Initialize the application controller."""
        super().__init__()
        self.logger = logging.getLogger(__name__)

        # Services
        self.config_manager = ConfigManager()
        self.validation_service = ValidationService()
        self.git_service = GitService()
        self.project_service = ProjectService(
            config_manager=self.config_manager,
            git_service=self.git_service,
            validation_service=self.validation_service,
        )
        self.worktree_service = WorktreeService(
            git_service=self.git_service, validation_service=self.validation_service
        )
        self.command_service = CommandService(
            validation_service=self.validation_service
        )

        # UI
        self.main_window: MainWindow | None = None

        # Configuration
        self.config = self.config_manager.config

        # Error handler
        self.error_handler = ErrorHandler()

        # State
        self._current_project: Project | None = None
        self._projects: dict[str, Project] = {}

        # Auto-refresh timer
        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self._auto_refresh)

        # Debounced refresh timer to prevent excessive refreshes
        self._debounced_refresh_timer = QTimer()
        self._debounced_refresh_timer.setSingleShot(True)
        self._debounced_refresh_timer.timeout.connect(self._perform_debounced_refresh)
        self._pending_refresh_project_id = None

        self.logger.info("Application controller initialized")

    def initialize(self) -> None:
        """Initialize all services and components."""
        try:
            self.logger.info("Initializing application controller...")

            # Initialize services in dependency order
            self.validation_service.initialize()
            self.git_service.initialize()
            self.project_service.initialize()
            self.worktree_service.initialize()
            self.command_service.initialize()

            # Create and initialize main window
            self.main_window = MainWindow(
                command_service=self.command_service,
                validation_service=self.validation_service,
                config=self.config,
            )

            # Connect UI signals to controller methods
            self._connect_ui_signals()

            # Load initial data
            self._load_initial_data()

            # Start auto-refresh if enabled
            self._setup_auto_refresh()

            self.logger.info("Application controller initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize application controller: {e}")
            raise ServiceError(f"Application initialization failed: {e}")

    def _connect_ui_signals(self) -> None:
        """Connect UI signals to controller methods."""
        if not self.main_window:
            return

        # Project management signals
        self.main_window.add_project_requested.connect(self._handle_add_project)
        self.main_window.remove_project_requested.connect(self._handle_remove_project)
        self.main_window.project_selected.connect(self._handle_project_selected)
        self.main_window.refresh_requested.connect(self._handle_refresh_all)
        self.main_window.project_health_requested.connect(
            self._handle_project_health_check
        )

        # Worktree management signals
        self.main_window.create_worktree_requested.connect(self._handle_create_worktree)
        self.main_window.remove_worktree_requested.connect(self._handle_remove_worktree)
        self.main_window.open_worktree_requested.connect(self._handle_open_worktree)
        self.main_window.refresh_worktrees_requested.connect(
            self._handle_refresh_worktrees
        )

        # Preferences management signals
        self.main_window.preferences_updated.connect(self._handle_preferences_updated)

        # Connect controller signals to UI updates
        self.project_added.connect(self._on_project_added)
        self.project_removed.connect(self._on_project_removed)
        self.project_updated.connect(self._on_project_updated)
        self.worktree_created.connect(self._on_worktree_created)
        self.worktree_removed.connect(self._on_worktree_removed)
        self.application_error.connect(self._on_application_error)

    def _load_initial_data(self) -> None:
        """Load initial application data."""
        try:
            # Load projects from configuration
            projects = self.project_service.get_projects()
            self._projects = {project.id: project for project in projects}

            # Populate UI with projects
            if self.main_window:
                self.main_window.populate_projects(list(self._projects.values()))

                # Restore last selected project if available
                last_project_id = self.config_manager.get_last_selected_project()
                if last_project_id and last_project_id in self._projects:
                    self._handle_project_selected(last_project_id)

            self.logger.info(f"Loaded {len(projects)} projects")

        except Exception as e:
            self.logger.error(f"Failed to load initial data: {e}")
            self.application_error.emit(
                "Initialization Error", f"Failed to load application data: {e}"
            )

    def _setup_auto_refresh(self) -> None:
        """Setup auto-refresh timer based on preferences."""
        try:
            config = self.config_manager.config
            if config.preferences.auto_refresh_enabled:
                interval_ms = config.preferences.auto_refresh_interval * 1000
                self._refresh_timer.start(interval_ms)
                self.logger.info(
                    f"Auto-refresh enabled with {config.preferences.auto_refresh_interval}s interval"
                )
            else:
                self._refresh_timer.stop()
                self.logger.info("Auto-refresh disabled")

        except Exception as e:
            self.logger.warning(f"Failed to setup auto-refresh: {e}")

    def _auto_refresh(self) -> None:
        """Perform automatic refresh of current project data."""
        try:
            if self._current_project:
                self._refresh_project_worktrees(self._current_project.id, silent=True)

        except Exception as e:
            self.logger.warning(f"Auto-refresh failed: {e}")

    # Project management handlers
    def _handle_add_project(self, path: str, name: str) -> None:
        """Handle add project request from UI."""
        try:
            self.logger.info(f"Adding project: {name} at {path}")

            if self.main_window:
                self.main_window.show_progress("Adding project...")

            # Add project through service
            project = self.project_service.add_project(path)

            # Update local state
            self._projects[project.id] = project

            # Update last access time
            self.project_service.update_project_access_time(project.id)

            # Emit signal for UI updates
            self.project_added.emit(project)

            if self.main_window:
                self.main_window.hide_progress()
                self.main_window.show_project_operation_success(
                    f"Project '{project.name}' added successfully"
                )

            self.logger.info(f"Successfully added project: {project.name}")

        except ValidationError as e:
            self.logger.warning(f"Project validation failed: {e}")
            if self.main_window:
                self.main_window.hide_progress()
                self.main_window.show_project_validation_error(str(e))

        except ServiceError as e:
            self.logger.error(f"Failed to add project: {e}")
            if self.main_window:
                self.main_window.hide_progress()
                self.main_window.show_project_operation_error(
                    "Add Project Failed", str(e)
                )

        except Exception as e:
            self.logger.error(f"Unexpected error removing project: {e}")
            self.application_error.emit(
                "Remove Project Error", f"Unexpected error: {e}"
            )

    def _handle_remove_project(self, project_id: str) -> None:
        """Handle remove project request from UI."""
        try:
            project = self._projects.get(project_id)
            if not project:
                self.logger.warning(f"Project not found for removal: {project_id}")
                return

            self.logger.info(f"Removing project: {project.name}")

            if self.main_window:
                self.main_window.show_progress("Removing project...")

            # Remove project through service
            success = self.project_service.remove_project(project_id)

            if success:
                self._handle_successful_project_removal(project_id, project)
            else:
                self._handle_failed_project_removal(project)

        except ServiceError as e:
            self.logger.error(f"Failed to remove project: {e}")
            if self.main_window:
                self.main_window.hide_progress()
                self.main_window.show_project_operation_error(
                    "Remove Project Failed", str(e)
                )

        except Exception as e:
            self.logger.error(f"Unexpected error removing project: {e}")
            self.application_error.emit(
                "Remove Project Error", f"Unexpected error: {e}"
            )

    def _handle_successful_project_removal(
        self, project_id: str, project: Project
    ) -> None:
        """Handle successful project removal."""
        # Update local state
        del self._projects[project_id]

        # Clear current project if it was removed
        if self._current_project and self._current_project.id == project_id:
            self._current_project = None
            if self.main_window:
                self.main_window.clear_worktrees()

        # Emit signal for UI updates
        self.project_removed.emit(project_id)

        if self.main_window:
            self.main_window.hide_progress()
            self.main_window.show_project_operation_success(
                f"Project '{project.name}' removed successfully"
            )

        self.logger.info(f"Successfully removed project: {project.name}")

    def _handle_failed_project_removal(self, project: Project) -> None:
        """Handle failed project removal."""
        if self.main_window:
            self.main_window.hide_progress()
            self.main_window.show_project_operation_error(
                "Remove Project Failed", "Failed to remove project from configuration"
            )

        self.logger.error(f"Failed to remove project: {project.name}")

    def _handle_project_selected(self, project_id: str) -> None:
        """Handle project selection from UI."""
        try:
            project = self._projects.get(project_id)
            if not project:
                self.logger.warning(f"Selected project not found: {project_id}")
                return

            self.logger.debug(f"Project selected: {project.name}")

            # Update current project
            self._current_project = project

            # Update last access time
            self.project_service.update_project_access_time(project_id)

            # Save last selected project
            self.config_manager.set_last_selected_project(project_id)

            # Load worktrees for the project
            self._load_project_worktrees(project)

        except Exception as e:
            self.logger.error(f"Error handling project selection: {e}")
            self.application_error.emit(
                "Project Selection Error", f"Failed to select project: {e}"
            )

    def _handle_refresh_all(self) -> None:
        """Handle refresh all request from UI."""
        try:
            self.logger.info("Refreshing all projects")

            if self.main_window:
                self.main_window.show_progress("Refreshing projects...")

            # Refresh all projects
            refreshed_projects = self.project_service.refresh_all_projects()

            # Update local state
            self._projects = {project.id: project for project in refreshed_projects}

            # Update UI
            if self.main_window:
                self.main_window.populate_projects(refreshed_projects)

                # Refresh current project worktrees if applicable
                if self._current_project:
                    current_project = self._projects.get(self._current_project.id)
                    if current_project:
                        self._current_project = current_project
                        self._load_project_worktrees(current_project)

                self.main_window.hide_progress()
                self.main_window.update_status("All projects refreshed")

            self.logger.info(
                f"Successfully refreshed {len(refreshed_projects)} projects"
            )

        except Exception as e:
            self.logger.error(f"Failed to refresh projects: {e}")
            if self.main_window:
                self.main_window.hide_progress()
            self.application_error.emit(
                "Refresh Error", f"Failed to refresh projects: {e}"
            )

    def _handle_project_health_check(self, project_id: str) -> None:
        """Handle project health check request from UI."""
        try:
            project = self._projects.get(project_id)
            if not project:
                return

            self.logger.debug(f"Checking health for project: {project.name}")

            # Get health status
            health_data = self.project_service.get_project_health_status(project_id)

            # Show health dialog
            if self.main_window:
                self.main_window.show_project_health(project_id, health_data)

        except ServiceError as e:
            self.logger.error(f"Failed to check project health: {e}")
            if self.main_window:
                self.main_window.show_project_operation_error(
                    "Health Check Failed", str(e)
                )

        except Exception as e:
            self.logger.error(f"Unexpected error during health check: {e}")
            self.application_error.emit("Health Check Error", f"Unexpected error: {e}")

    # Worktree management handlers
    def _handle_create_worktree(self, project_id: str, config: dict) -> None:
        """Handle create worktree request from UI."""
        try:
            project = self._projects.get(project_id)
            if not project:
                self.logger.warning(
                    f"Project not found for worktree creation: {project_id}"
                )
                return

            path = config.get("path", "")
            branch = config.get("branch", "")
            auto_create_branch = config.get("auto_create_branch", False)
            base_branch = config.get("base_branch", "main")

            self.logger.info(f"Creating worktree at {path} for branch {branch}")

            if self.main_window:
                self.main_window.show_progress("Creating worktree...")

            # Create worktree through service
            worktree = self.worktree_service.create_worktree(
                project, path, branch, auto_create_branch, base_branch
            )

            # Update project in local state
            self._projects[project_id] = project

            # Emit signal for UI updates
            self.worktree_created.emit(project_id, worktree)

            if self.main_window:
                self.main_window.hide_progress()
                self.main_window.update_status(f"Worktree created at {path}")

            # Refresh worktrees display
            self._refresh_project_worktrees(project_id)

            self.logger.info(f"Successfully created worktree at {path}")

        except ValidationError as e:
            self.logger.warning(f"Worktree validation failed: {e}")
            if self.main_window:
                self.main_window.hide_progress()
                # Show validation error through worktree panel

        except (ServiceError, GitError) as e:
            self.logger.error(f"Failed to create worktree: {e}")
            if self.main_window:
                self.main_window.hide_progress()
                # Show error through worktree panel

        except Exception as e:
            self.logger.error(f"Unexpected error creating worktree: {e}")
            self.application_error.emit(
                "Create Worktree Error", f"Unexpected error: {e}"
            )

    def _handle_remove_worktree(
        self, project_id: str, worktree_path: str, config: dict
    ) -> None:
        """Handle remove worktree request from UI."""
        try:
            project = self._projects.get(project_id)
            if not project:
                self.logger.warning(
                    f"Project not found for worktree removal: {project_id}"
                )
                return

            # Find the worktree
            worktree = self._find_worktree_in_project(project, worktree_path)
            if not worktree:
                self.logger.warning(f"Worktree not found for removal: {worktree_path}")
                return

            force = config.get("force", False)
            self.logger.info(f"Removing worktree at {worktree_path} (force={force})")

            if self.main_window:
                self.main_window.show_progress("Removing worktree...")

            # Remove worktree through service
            success = self.worktree_service.remove_worktree(worktree, force)

            if success:
                self._handle_successful_worktree_removal(
                    project, worktree, worktree_path
                )
            else:
                self._handle_failed_worktree_removal()

        except ServiceError as e:
            self.logger.error(f"Failed to remove worktree: {e}")
            if self.main_window:
                self.main_window.hide_progress()
                # Show error through worktree panel

        except Exception as e:
            self.logger.error(f"Unexpected error removing worktree: {e}")
            self.application_error.emit(
                "Remove Worktree Error", f"Unexpected error: {e}"
            )

    def _find_worktree_in_project(
        self, project: Project, worktree_path: str
    ) -> Worktree | None:
        """Find a worktree in the project by path."""
        for wt in project.worktrees:
            if wt.path == worktree_path:
                return wt
        return None

    def _handle_successful_worktree_removal(
        self, project: Project, worktree: Worktree, worktree_path: str
    ) -> None:
        """Handle successful worktree removal."""
        # Remove from project
        project.remove_worktree(worktree)

        # Emit signal for UI updates
        self.worktree_removed.emit(project.id, worktree_path)

        if self.main_window:
            self.main_window.hide_progress()
            self.main_window.update_status(f"Worktree removed from {worktree_path}")

        # Refresh worktrees display
        self._refresh_project_worktrees(project.id)

        self.logger.info(f"Successfully removed worktree at {worktree_path}")

    def _handle_failed_worktree_removal(self) -> None:
        """Handle failed worktree removal."""
        if self.main_window:
            self.main_window.hide_progress()

    def _handle_open_worktree(self, worktree_path: str, action_type: str) -> None:
        """Handle open worktree request from UI."""
        try:
            self.logger.info(f"Opening worktree {worktree_path} with {action_type}")

            # Import here to avoid circular imports
            import platform
            from pathlib import Path

            path_obj = Path(worktree_path)
            if not path_obj.exists():
                raise ServiceError(f"Worktree path does not exist: {worktree_path}")

            system = platform.system()

            if action_type == "file_manager":
                self._open_in_file_manager(worktree_path, system)
            elif action_type == "terminal":
                self._open_in_terminal(worktree_path, system)
            elif action_type == "editor":
                self._open_in_editor(worktree_path, system)
            elif action_type.startswith("custom_app:"):
                app_name = action_type.split(":", 1)[1]
                self._open_in_custom_app(worktree_path, app_name, system)
            else:
                raise ServiceError(f"Unknown action type: {action_type}")

            if self.main_window:
                self.main_window.update_status(
                    f"Opened {worktree_path} in {action_type}"
                )

        except Exception as e:
            self.logger.error(f"Failed to open worktree: {e}")
            self.application_error.emit(
                "Open Worktree Error", f"Failed to open worktree: {e}"
            )

    def _open_in_file_manager(self, worktree_path: str, system: str) -> None:
        """Open worktree in file manager."""
        import subprocess

        if system == "Darwin":  # macOS
            subprocess.run(["open", worktree_path])
        elif system == "Windows":
            subprocess.run(["explorer", worktree_path])
        else:  # Linux
            subprocess.run(["xdg-open", worktree_path])

    def _open_in_terminal(self, worktree_path: str, system: str) -> None:
        """Open worktree in terminal."""
        import subprocess

        if system == "Darwin":  # macOS
            subprocess.run(["open", "-a", "Terminal", worktree_path])
        elif system == "Windows":
            subprocess.run(
                ["cmd", "/c", "start", "cmd", "/k", f"cd /d {worktree_path}"]
            )
        else:  # Linux
            subprocess.run(["gnome-terminal", "--working-directory", worktree_path])

    def _open_in_editor(self, worktree_path: str, system: str) -> None:
        """Open worktree in editor."""
        import subprocess
        from pathlib import Path

        # Check if default editor is configured
        default_editor = self.config.preferences.default_editor.strip()
        if default_editor:
            try:
                # Handle macOS .app bundles
                if system == "Darwin" and default_editor.endswith(".app"):
                    app_name = Path(default_editor).name
                    subprocess.run(["open", "-a", app_name, worktree_path], check=True)
                    return
                else:
                    # Try the configured editor directly
                    subprocess.run([default_editor, worktree_path], check=True)
                    return
            except (subprocess.CalledProcessError, FileNotFoundError):
                # Configured editor failed, continue to fallback
                pass

        # Try common editors
        editors = ["code", "subl", "atom", "vim"]
        for editor in editors:
            try:
                subprocess.run([editor, worktree_path], check=True)
                break
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
        else:
            # Fallback to system default
            if system == "Darwin":
                subprocess.run(["open", worktree_path])
            elif system == "Windows":
                subprocess.run(["start", worktree_path], shell=True)
            else:
                subprocess.run(["xdg-open", worktree_path])

    def _open_in_custom_app(
        self, worktree_path: str, app_name: str, system: str
    ) -> None:
        """Open worktree in custom application."""
        import subprocess

        # Find the custom application in preferences
        custom_apps = self.config.preferences.custom_applications
        app_config = None
        for app in custom_apps:
            if app.name == app_name:
                app_config = app
                break

        if not app_config:
            raise ServiceError(
                f"Custom application '{app_name}' not found in preferences"
            )

        # Substitute %PATH% placeholder in command template
        command_template = app_config.command_template
        command = command_template.replace("%PATH%", worktree_path)

        # Execute the command
        try:
            if system == "Darwin":
                command = f"open -a {command}"
                self.logger.info(f">>> Running command: {command}")
                subprocess.run(command, shell=True, check=True)
            else:
                # Split command for other systems
                subprocess.run(command.split(), check=True)
        except subprocess.CalledProcessError as e:
            raise ServiceError(f"Failed to execute custom application command: {e}")

    def _handle_refresh_worktrees(self, project_id: str) -> None:
        """Handle refresh worktrees request from UI."""
        self._refresh_project_worktrees(project_id)

    def _handle_preferences_updated(self, preferences) -> None:
        """Handle preferences updated signal from UI."""
        try:
            self.logger.info("Updating user preferences")

            # Update the configuration with new preferences
            self.config.preferences = preferences

            # Save the configuration
            success = self.config_manager.save_config()

            if success:
                self.logger.info("User preferences saved successfully")

                # Update auto-refresh timer if needed
                self._setup_auto_refresh()
            else:
                self.logger.error("Failed to save user preferences")
                self.application_error.emit(
                    "Preferences Error", "Failed to save preferences to disk"
                )

        except Exception as e:
            self.logger.error(f"Exception while updating preferences: {e}")
            self.application_error.emit(
                "Preferences Error", f"Failed to update preferences: {e}"
            )

    # Helper methods
    def _load_project_worktrees(self, project: Project) -> None:
        """Load worktrees for a project with lazy loading optimization."""
        try:
            if self.main_window:
                self.main_window.show_progress("Loading worktrees...")

            # Check if worktrees are already cached and recent
            if (
                project.worktrees
                and hasattr(project, "_worktrees_last_loaded")
                and (datetime.now() - project._worktrees_last_loaded).seconds < 30
            ):
                # Use cached worktrees if loaded within last 30 seconds
                worktrees = project.worktrees
                self.logger.debug(f"Using cached worktrees for project {project.name}")
            else:
                # Get worktrees through service
                worktrees = self.worktree_service.get_worktrees(project)
                # Cache the load time
                project._worktrees_last_loaded = datetime.now()

            # Update UI
            if self.main_window:
                self.main_window.set_current_project(project)
                self.main_window.populate_worktrees(worktrees)
                self.main_window.hide_progress()

            self.logger.debug(
                f"Loaded {len(worktrees)} worktrees for project {project.name}"
            )

        except Exception as e:
            self.logger.error(
                f"Failed to load worktrees for project {project.name}: {e}"
            )
            if self.main_window:
                self.main_window.hide_progress()
                self.main_window.clear_worktrees()
            self.application_error.emit(
                "Load Worktrees Error", f"Failed to load worktrees: {e}"
            )

    def _refresh_project_worktrees(self, project_id: str, silent: bool = False) -> None:
        """Refresh worktrees for a specific project with debouncing."""
        if silent:
            # For silent refreshes (like auto-refresh), use debouncing
            self._pending_refresh_project_id = project_id
            self._debounced_refresh_timer.start(500)  # 500ms debounce
        else:
            # For explicit refreshes, execute immediately
            self._perform_refresh_project_worktrees(project_id, silent)

    def _perform_debounced_refresh(self) -> None:
        """Perform the debounced refresh operation."""
        if self._pending_refresh_project_id:
            self._perform_refresh_project_worktrees(
                self._pending_refresh_project_id, silent=True
            )
            self._pending_refresh_project_id = None

    def _perform_refresh_project_worktrees(
        self, project_id: str, silent: bool = False
    ) -> None:
        """Actually perform the worktree refresh operation."""
        try:
            project = self._projects.get(project_id)
            if not project:
                return

            if not silent and self.main_window:
                self.main_window.show_progress("Refreshing worktrees...")

            # Refresh worktrees through service
            worktrees = self.worktree_service.refresh_worktrees(project)

            # Update UI if this is the current project
            self._update_ui_after_refresh(project_id, worktrees, silent)

            if not silent:
                self.logger.debug(
                    f"Refreshed {len(worktrees)} worktrees for project {project.name}"
                )

        except Exception as e:
            self.logger.error(f"Failed to refresh worktrees: {e}")
            if not silent and self.main_window:
                self.main_window.hide_progress()

    def _update_ui_after_refresh(
        self, project_id: str, worktrees: list, silent: bool
    ) -> None:
        """Update UI after worktree refresh."""
        if self._current_project and self._current_project.id == project_id:
            if self.main_window:
                self.main_window.populate_worktrees(worktrees)
                if not silent:
                    self.main_window.hide_progress()
                    self.main_window.update_status("Worktrees refreshed")

    # UI update handlers
    def _on_project_added(self, project: Project) -> None:
        """Handle project added signal."""
        if self.main_window:
            # Refresh the entire project list to show the new project
            self.main_window.populate_projects(list(self._projects.values()))
            self.logger.debug(
                f"Project list refreshed after adding project: {project.name}"
            )

    def _on_project_removed(self, project_id: str) -> None:
        """Handle project removed signal."""
        if self.main_window:
            # Refresh the entire project list to remove the deleted project
            self.main_window.populate_projects(list(self._projects.values()))
            self.logger.debug(
                f"Project list refreshed after removing project: {project_id}"
            )

    def _on_project_updated(self, project: Project) -> None:
        """Handle project updated signal."""
        if self.main_window:
            self.main_window.refresh_project_item(project)

    def _on_worktree_created(self, project_id: str, worktree: Worktree) -> None:
        """Handle worktree created signal."""
        # Worktree panel will be refreshed by the handler
        pass

    def _on_worktree_removed(self, project_id: str, worktree_path: str) -> None:
        """Handle worktree removed signal."""
        # Worktree panel will be refreshed by the handler
        pass

    def _on_application_error(self, title: str, message: str) -> None:
        """Handle application error signal."""
        self.logger.error(f"Application error: {title} - {message}")
        get_message_service().show_error(title, message)

    # Public interface
    def show_main_window(self) -> None:
        """Show the main application window."""
        if self.main_window:
            self.main_window.show()

    def get_main_window(self) -> MainWindow | None:
        """Get the main window instance."""
        return self.main_window

    def cleanup(self) -> None:
        """Clean up resources and save state."""
        try:
            self.logger.info("Cleaning up application controller...")

            # Stop timers
            self._refresh_timer.stop()
            self._debounced_refresh_timer.stop()

            # Save configuration
            self.config_manager.save_config()

            # Clean up services
            if self.command_service:
                self.command_service.cleanup()

            # Clean up main window
            if self.main_window:
                self.main_window.cancel_running_commands()

            # Clear caches to free memory
            self._projects.clear()
            self._current_project = None

            self.logger.info("Application controller cleanup completed")

        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

    def __str__(self) -> str:
        """String representation of the application controller."""
        return f"ApplicationController(projects={len(self._projects)})"

    def __repr__(self) -> str:
        """Detailed string representation of the application controller."""
        return (
            f"ApplicationController(projects={len(self._projects)}, "
            f"current_project={self._current_project.name if self._current_project else None})"
        )
