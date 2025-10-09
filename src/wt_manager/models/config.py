"""Configuration data models for Git Worktree Manager."""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from ..utils.path_manager import PathManager
from .command_execution import CommandExecution, CommandHistory
from .project import Project


logger = logging.getLogger(__name__)


@dataclass
class UserPreferences:
    """
    User preferences and application settings.

    Attributes:
        theme: UI theme preference (light, dark, auto)
        auto_refresh_interval: Interval in seconds for auto-refreshing worktree status
        show_hidden_files: Whether to show hidden files in file operations
        default_editor: Default code editor command
        default_terminal: Default terminal command
        confirm_destructive_actions: Whether to show confirmation dialogs for destructive actions
        max_command_history: Maximum number of commands to keep in history
        command_timeout: Default timeout for command execution in seconds
        git_fetch_on_create: Whether to fetch remote changes when creating worktrees
        window_geometry: Window geometry settings
        panel_sizes: Panel size preferences
    """

    theme: str = "auto"
    auto_refresh_enabled: bool = True
    auto_refresh_interval: int = 30
    show_hidden_files: bool = False
    default_editor: str = ""
    default_terminal: str = ""
    confirm_destructive_actions: bool = True
    max_command_history: int = 100
    command_timeout: int = 300  # 5 minutes
    git_fetch_on_create: bool = True
    worktree_base_path: str = ""  # Base path for all worktrees
    window_geometry: dict[str, int] = field(default_factory=dict)
    panel_sizes: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize preferences to dictionary.

        Returns:
            Dict[str, Any]: Serialized preferences data
        """
        return {
            "theme": self.theme,
            "auto_refresh_interval": self.auto_refresh_interval,
            "show_hidden_files": self.show_hidden_files,
            "default_editor": self.default_editor,
            "default_terminal": self.default_terminal,
            "confirm_destructive_actions": self.confirm_destructive_actions,
            "max_command_history": self.max_command_history,
            "command_timeout": self.command_timeout,
            "git_fetch_on_create": self.git_fetch_on_create,
            "worktree_base_path": self.worktree_base_path,
            "window_geometry": self.window_geometry,
            "panel_sizes": self.panel_sizes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserPreferences":
        """
        Deserialize preferences from dictionary.

        Args:
            data: Dictionary containing preferences data

        Returns:
            UserPreferences: Deserialized preferences instance
        """
        return cls(
            theme=data.get("theme", "auto"),
            auto_refresh_interval=data.get("auto_refresh_interval", 30),
            show_hidden_files=data.get("show_hidden_files", False),
            default_editor=data.get("default_editor", ""),
            default_terminal=data.get("default_terminal", ""),
            confirm_destructive_actions=data.get("confirm_destructive_actions", True),
            max_command_history=data.get("max_command_history", 100),
            command_timeout=data.get("command_timeout", 300),
            git_fetch_on_create=data.get("git_fetch_on_create", True),
            worktree_base_path=data.get("worktree_base_path", ""),
            window_geometry=data.get("window_geometry", {}),
            panel_sizes=data.get("panel_sizes", {}),
        )


@dataclass
class ProjectConfig:
    """
    Configuration for a single project.

    Attributes:
        id: Unique project identifier
        name: Display name of the project
        path: Filesystem path to the Git repository
        last_accessed: Timestamp of last access
        is_favorite: Whether this project is marked as favorite
        custom_commands: Custom commands defined for this project
        notes: User notes about the project
    """

    id: str
    name: str
    path: str
    last_accessed: datetime
    is_favorite: bool = False
    custom_commands: dict[str, str] = field(default_factory=dict)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize project config to dictionary.

        Returns:
            Dict[str, Any]: Serialized project config data
        """
        return {
            "id": self.id,
            "name": self.name,
            "path": self.path,
            "last_accessed": self.last_accessed.isoformat(),
            "is_favorite": self.is_favorite,
            "custom_commands": self.custom_commands,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectConfig":
        """
        Deserialize project config from dictionary.

        Args:
            data: Dictionary containing project config data

        Returns:
            ProjectConfig: Deserialized project config instance
        """
        return cls(
            id=data["id"],
            name=data["name"],
            path=data["path"],
            last_accessed=datetime.fromisoformat(data["last_accessed"]),
            is_favorite=data.get("is_favorite", False),
            custom_commands=data.get("custom_commands", {}),
            notes=data.get("notes", ""),
        )

    @classmethod
    def from_project(cls, project: Project) -> "ProjectConfig":
        """
        Create project config from a Project instance.

        Args:
            project: Project instance to convert

        Returns:
            ProjectConfig: Project configuration
        """
        return cls(
            id=project.id,
            name=project.name,
            path=project.path,
            last_accessed=project.last_accessed,
        )


@dataclass
class AppConfig:
    """
    Main application configuration containing all settings and data.

    Attributes:
        version: Configuration version for migration purposes
        projects: List of project configurations
        preferences: User preferences and settings
        command_history: Command execution history by worktree path
        last_selected_project: ID of the last selected project
        created_at: Timestamp when configuration was first created
        updated_at: Timestamp when configuration was last updated
    """

    version: str = "1.0.0"
    projects: list[ProjectConfig] = field(default_factory=list)
    preferences: UserPreferences = field(default_factory=UserPreferences)
    command_history: dict[str, CommandHistory] = field(default_factory=dict)
    last_selected_project: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Post-initialization setup."""
        # Ensure directories exist
        PathManager.ensure_directories()

    def add_project(self, project_config: ProjectConfig) -> None:
        """
        Add a project configuration.

        Args:
            project_config: ProjectConfig instance to add
        """
        # Remove existing project with same ID if it exists
        self.remove_project(project_config.id)

        # Add the new project config
        self.projects.append(project_config)
        self.updated_at = datetime.now()

        logger.info(f"Added project config: {project_config.name}")

    def remove_project(self, project_id: str) -> bool:
        """
        Remove a project configuration.

        Args:
            project_id: ID of the project to remove

        Returns:
            bool: True if project was found and removed, False otherwise
        """
        for i, project in enumerate(self.projects):
            if project.id == project_id:
                removed_project = self.projects.pop(i)
                self.updated_at = datetime.now()

                # Clear last selected project if it was the removed one
                if self.last_selected_project == project_id:
                    self.last_selected_project = None

                # Remove command history for this project's worktrees
                self._cleanup_project_command_history(removed_project.path)

                logger.info(f"Removed project config: {removed_project.name}")
                return True

        return False

    def get_project(self, project_id: str) -> ProjectConfig | None:
        """
        Get a project configuration by ID.

        Args:
            project_id: ID of the project to find

        Returns:
            Optional[ProjectConfig]: Project config if found, None otherwise
        """
        for project in self.projects:
            if project.id == project_id:
                return project
        return None

    def update_project(self, project_config: ProjectConfig) -> bool:
        """
        Update an existing project configuration.

        Args:
            project_config: Updated project configuration

        Returns:
            bool: True if project was found and updated, False otherwise
        """
        for i, project in enumerate(self.projects):
            if project.id == project_config.id:
                self.projects[i] = project_config
                self.updated_at = datetime.now()
                logger.info(f"Updated project config: {project_config.name}")
                return True

        return False

    def get_recent_projects(self, limit: int = 5) -> list[ProjectConfig]:
        """
        Get recently accessed projects.

        Args:
            limit: Maximum number of projects to return

        Returns:
            List[ProjectConfig]: Recently accessed projects
        """
        sorted_projects = sorted(
            self.projects, key=lambda p: p.last_accessed, reverse=True
        )
        return sorted_projects[:limit]

    def get_favorite_projects(self) -> list[ProjectConfig]:
        """
        Get favorite projects.

        Returns:
            List[ProjectConfig]: Favorite projects
        """
        return [project for project in self.projects if project.is_favorite]

    def add_command_execution(self, execution: "CommandExecution") -> None:
        """
        Add a command execution to the history.

        Args:
            execution: CommandExecution instance to add
        """
        worktree_path = execution.worktree_path

        if worktree_path not in self.command_history:
            self.command_history[worktree_path] = CommandHistory(
                worktree_path=worktree_path,
                max_history_size=self.preferences.max_command_history,
            )

        self.command_history[worktree_path].add_execution(execution)
        self.updated_at = datetime.now()

    def get_command_history(self, worktree_path: str) -> CommandHistory | None:
        """
        Get command history for a specific worktree.

        Args:
            worktree_path: Path to the worktree

        Returns:
            Optional[CommandHistory]: Command history if exists, None otherwise
        """
        return self.command_history.get(worktree_path)

    def clear_command_history(self, worktree_path: str | None = None) -> None:
        """
        Clear command history for a specific worktree or all history.

        Args:
            worktree_path: Path to the worktree (None to clear all history)
        """
        if worktree_path:
            if worktree_path in self.command_history:
                del self.command_history[worktree_path]
                logger.info(f"Cleared command history for worktree: {worktree_path}")
        else:
            self.command_history.clear()
            logger.info("Cleared all command history")

        self.updated_at = datetime.now()

    def _cleanup_project_command_history(self, project_path: str) -> None:
        """
        Clean up command history for worktrees belonging to a removed project.

        Args:
            project_path: Path to the removed project
        """
        project_path_obj = Path(project_path)
        worktrees_to_remove = []

        for worktree_path in self.command_history.keys():
            worktree_path_obj = Path(worktree_path)
            try:
                # Check if worktree is under the project path
                worktree_path_obj.relative_to(project_path_obj)
                worktrees_to_remove.append(worktree_path)
            except ValueError:
                # Worktree is not under this project path
                continue

        for worktree_path in worktrees_to_remove:
            del self.command_history[worktree_path]

    def save(self, config_file: Path | None = None) -> bool:
        """
        Save configuration to file.

        Args:
            config_file: Optional path to config file (uses default if None)

        Returns:
            bool: True if save was successful, False otherwise
        """
        if config_file is None:
            config_file = PathManager.get_config_file("app_config.json")

        try:
            # Update timestamp
            self.updated_at = datetime.now()

            # Ensure parent directory exists
            config_file.parent.mkdir(parents=True, exist_ok=True)

            # Save configuration
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

            logger.info(f"Configuration saved to: {config_file}")
            return True

        except (OSError, json.JSONEncodeError) as e:
            logger.error(f"Failed to save configuration to {config_file}: {e}")
            return False

    @classmethod
    def load(cls, config_file: Path | None = None) -> "AppConfig":
        """
        Load configuration from file.

        Args:
            config_file: Optional path to config file (uses default if None)

        Returns:
            AppConfig: Loaded configuration or default if loading fails
        """
        if config_file is None:
            config_file = PathManager.get_config_file("app_config.json")

        try:
            if not config_file.exists():
                logger.info(
                    f"Configuration file not found: {config_file}, creating default"
                )
                config = cls()
                config.save(config_file)
                return config

            with open(config_file, encoding="utf-8") as f:
                data = json.load(f)

            config = cls.from_dict(data)
            logger.info(f"Configuration loaded from: {config_file}")
            return config

        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load configuration from {config_file}: {e}")
            logger.info("Creating default configuration")
            return cls()

    def backup(self, backup_file: Path | None = None) -> bool:
        """
        Create a backup of the current configuration.

        Args:
            backup_file: Optional path to backup file

        Returns:
            bool: True if backup was successful, False otherwise
        """
        if backup_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = PathManager.get_config_file(
                f"app_config_backup_{timestamp}.json"
            )

        return self.save(backup_file)

    def restore_from_backup(self, backup_file: Path) -> bool:
        """
        Restore configuration from a backup file.

        Args:
            backup_file: Path to the backup file

        Returns:
            bool: True if restore was successful, False otherwise
        """
        try:
            if not backup_file.exists():
                logger.error(f"Backup file not found: {backup_file}")
                return False

            with open(backup_file, encoding="utf-8") as f:
                data = json.load(f)

            restored_config = self.from_dict(data)

            # Update current instance with restored data
            self.version = restored_config.version
            self.projects = restored_config.projects
            self.preferences = restored_config.preferences
            self.command_history = restored_config.command_history
            self.last_selected_project = restored_config.last_selected_project
            self.created_at = restored_config.created_at
            self.updated_at = datetime.now()

            logger.info(f"Configuration restored from backup: {backup_file}")
            return True

        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"Failed to restore configuration from {backup_file}: {e}")
            return False

    def migrate_if_needed(self) -> bool:
        """
        Migrate configuration to current version if needed.

        Returns:
            bool: True if migration was performed or not needed, False if migration failed
        """
        current_version = "1.0.0"

        if self.version == current_version:
            return True

        logger.info(
            f"Migrating configuration from version {self.version} to {current_version}"
        )

        try:
            # Create backup before migration
            if not self.backup():
                logger.warning("Failed to create backup before migration")

            # Perform version-specific migrations here
            # For now, just update the version
            self.version = current_version
            self.updated_at = datetime.now()

            logger.info("Configuration migration completed successfully")
            return True

        except Exception as e:
            logger.error(f"Configuration migration failed: {e}")
            return False

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize configuration to dictionary.

        Returns:
            Dict[str, Any]: Serialized configuration data
        """
        return {
            "version": self.version,
            "projects": [project.to_dict() for project in self.projects],
            "preferences": self.preferences.to_dict(),
            "command_history": {
                path: history.to_dict()
                for path, history in self.command_history.items()
            },
            "last_selected_project": self.last_selected_project,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppConfig":
        """
        Deserialize configuration from dictionary.

        Args:
            data: Dictionary containing configuration data

        Returns:
            AppConfig: Deserialized configuration instance
        """
        from .command_execution import CommandHistory

        projects = [
            ProjectConfig.from_dict(project_data)
            for project_data in data.get("projects", [])
        ]

        preferences = UserPreferences.from_dict(data.get("preferences", {}))

        command_history = {}
        for path, history_data in data.get("command_history", {}).items():
            command_history[path] = CommandHistory.from_dict(history_data)

        return cls(
            version=data.get("version", "1.0.0"),
            projects=projects,
            preferences=preferences,
            command_history=command_history,
            last_selected_project=data.get("last_selected_project"),
            created_at=datetime.fromisoformat(
                data.get("created_at", datetime.now().isoformat())
            ),
            updated_at=datetime.fromisoformat(
                data.get("updated_at", datetime.now().isoformat())
            ),
        )

    def __str__(self) -> str:
        """String representation of the configuration."""
        return f"AppConfig(projects={len(self.projects)}, version={self.version})"

    def __repr__(self) -> str:
        """Detailed string representation of the configuration."""
        return (
            f"AppConfig(version='{self.version}', projects={len(self.projects)}, "
            f"command_history={len(self.command_history)}, "
            f"updated_at='{self.updated_at.isoformat()}')"
        )
