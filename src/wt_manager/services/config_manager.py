"""Configuration management service for Git Worktree Manager."""

import logging
from pathlib import Path

from ..models.config import AppConfig, ProjectConfig
from ..models.project import Project
from ..utils.path_manager import PathManager


logger = logging.getLogger(__name__)


class ConfigManager:
    """
    Manages application configuration loading, saving, and operations.

    This service provides a centralized way to manage application configuration,
    including project settings, user preferences, and command history.
    """

    def __init__(self, config_file: Path | None = None):
        """
        Initialize the configuration manager.

        Args:
            config_file: Optional path to config file (uses default if None)
        """
        self._config_file = config_file or PathManager.get_config_file(
            "app_config.json"
        )
        self._config: AppConfig | None = None

    @property
    def config(self) -> AppConfig:
        """
        Get the current configuration, loading it if necessary.

        Returns:
            AppConfig: Current application configuration
        """
        if self._config is None:
            self._config = self.load_config()
        return self._config

    def load_config(self) -> AppConfig:
        """
        Load configuration from file.

        Returns:
            AppConfig: Loaded configuration
        """
        try:
            config = AppConfig.load(self._config_file)

            # Perform migration if needed
            if not config.migrate_if_needed():
                logger.warning("Configuration migration failed, using current config")

            self._config = config
            logger.info("Configuration loaded successfully")
            return config

        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            logger.info("Creating default configuration")
            config = AppConfig()
            self._config = config
            return config

    def save_config(self) -> bool:
        """
        Save current configuration to file.

        Returns:
            bool: True if save was successful, False otherwise
        """
        if self._config is None:
            logger.warning("No configuration to save")
            return False

        try:
            success = self._config.save(self._config_file)
            if success:
                logger.info("Configuration saved successfully")
            else:
                logger.error("Failed to save configuration")
            return success

        except Exception as e:
            logger.error(f"Exception while saving configuration: {e}")
            return False

    def reload_config(self) -> AppConfig:
        """
        Reload configuration from file, discarding current changes.

        Returns:
            AppConfig: Reloaded configuration
        """
        logger.info("Reloading configuration from file")
        self._config = None
        return self.config

    def reset_config(self) -> AppConfig:
        """
        Reset configuration to defaults.

        Returns:
            AppConfig: New default configuration
        """
        logger.info("Resetting configuration to defaults")
        self._config = AppConfig()
        return self._config

    def backup_config(self, backup_file: Path | None = None) -> bool:
        """
        Create a backup of the current configuration.

        Args:
            backup_file: Optional path to backup file

        Returns:
            bool: True if backup was successful, False otherwise
        """
        if self._config is None:
            logger.warning("No configuration to backup")
            return False

        try:
            success = self._config.backup(backup_file)
            if success:
                logger.info(
                    f"Configuration backup created: {backup_file or 'default location'}"
                )
            else:
                logger.error("Failed to create configuration backup")
            return success

        except Exception as e:
            logger.error(f"Exception while creating configuration backup: {e}")
            return False

    def restore_config(self, backup_file: Path) -> bool:
        """
        Restore configuration from a backup file.

        Args:
            backup_file: Path to the backup file

        Returns:
            bool: True if restore was successful, False otherwise
        """
        if self._config is None:
            self._config = AppConfig()

        try:
            success = self._config.restore_from_backup(backup_file)
            if success:
                logger.info(f"Configuration restored from backup: {backup_file}")
                # Save the restored configuration
                self.save_config()
            else:
                logger.error("Failed to restore configuration from backup")
            return success

        except Exception as e:
            logger.error(f"Exception while restoring configuration: {e}")
            return False

    def add_project(self, project: Project) -> bool:
        """
        Add a project to the configuration.

        Args:
            project: Project instance to add

        Returns:
            bool: True if project was added successfully, False otherwise
        """
        try:
            project_config = ProjectConfig.from_project(project)
            self.config.add_project(project_config)

            success = self.save_config()
            if success:
                logger.info(f"Project added to configuration: {project.name}")
            else:
                logger.error(
                    f"Failed to save configuration after adding project: {project.name}"
                )
            return success

        except Exception as e:
            logger.error(f"Exception while adding project to configuration: {e}")
            return False

    def remove_project(self, project_id: str) -> bool:
        """
        Remove a project from the configuration.

        Args:
            project_id: ID of the project to remove

        Returns:
            bool: True if project was removed successfully, False otherwise
        """
        try:
            removed = self.config.remove_project(project_id)
            if not removed:
                logger.warning(f"Project not found in configuration: {project_id}")
                return False

            success = self.save_config()
            if success:
                logger.info(f"Project removed from configuration: {project_id}")
            else:
                logger.error(
                    f"Failed to save configuration after removing project: {project_id}"
                )
            return success

        except Exception as e:
            logger.error(f"Exception while removing project from configuration: {e}")
            return False

    def update_project(self, project: Project) -> bool:
        """
        Update a project in the configuration.

        Args:
            project: Updated project instance

        Returns:
            bool: True if project was updated successfully, False otherwise
        """
        try:
            project_config = ProjectConfig.from_project(project)
            updated = self.config.update_project(project_config)

            if not updated:
                logger.warning(
                    f"Project not found in configuration for update: {project.id}"
                )
                return False

            success = self.save_config()
            if success:
                logger.info(f"Project updated in configuration: {project.name}")
            else:
                logger.error(
                    f"Failed to save configuration after updating project: {project.name}"
                )
            return success

        except Exception as e:
            logger.error(f"Exception while updating project in configuration: {e}")
            return False

    def get_project_config(self, project_id: str) -> ProjectConfig | None:
        """
        Get project configuration by ID.

        Args:
            project_id: ID of the project to find

        Returns:
            Optional[ProjectConfig]: Project config if found, None otherwise
        """
        return self.config.get_project(project_id)

    def get_all_project_configs(self) -> list[ProjectConfig]:
        """
        Get all project configurations.

        Returns:
            List[ProjectConfig]: All project configurations
        """
        return self.config.projects.copy()

    def get_recent_projects(self, limit: int = 5) -> list[ProjectConfig]:
        """
        Get recently accessed projects.

        Args:
            limit: Maximum number of projects to return

        Returns:
            List[ProjectConfig]: Recently accessed projects
        """
        return self.config.get_recent_projects(limit)

    def get_favorite_projects(self) -> list[ProjectConfig]:
        """
        Get favorite projects.

        Returns:
            List[ProjectConfig]: Favorite projects
        """
        return self.config.get_favorite_projects()

    def set_last_selected_project(self, project_id: str | None) -> bool:
        """
        Set the last selected project.

        Args:
            project_id: ID of the project to set as last selected (None to clear)

        Returns:
            bool: True if setting was saved successfully, False otherwise
        """
        try:
            self.config.last_selected_project = project_id
            success = self.save_config()
            if success:
                logger.debug(f"Last selected project set to: {project_id}")
            return success

        except Exception as e:
            logger.error(f"Exception while setting last selected project: {e}")
            return False

    def get_last_selected_project(self) -> str | None:
        """
        Get the last selected project ID.

        Returns:
            Optional[str]: Last selected project ID, None if not set
        """
        return self.config.last_selected_project

    def update_preferences(self, **kwargs) -> bool:
        """
        Update user preferences.

        Args:
            **kwargs: Preference key-value pairs to update

        Returns:
            bool: True if preferences were updated successfully, False otherwise
        """
        try:
            preferences = self.config.preferences

            # Update preferences with provided values
            for key, value in kwargs.items():
                if hasattr(preferences, key):
                    setattr(preferences, key, value)
                    logger.debug(f"Updated preference {key} to {value}")
                else:
                    logger.warning(f"Unknown preference key: {key}")

            success = self.save_config()
            if success:
                logger.info("User preferences updated successfully")
            return success

        except Exception as e:
            logger.error(f"Exception while updating preferences: {e}")
            return False

    def get_config_file_path(self) -> Path:
        """
        Get the path to the configuration file.

        Returns:
            Path: Path to the configuration file
        """
        return self._config_file

    def get_config_info(self) -> dict:
        """
        Get information about the current configuration.

        Returns:
            Dict: Configuration information including file path, version, etc.
        """
        config = self.config
        return {
            "config_file": str(self._config_file),
            "version": config.version,
            "project_count": len(config.projects),
            "command_history_count": len(config.command_history),
            "created_at": config.created_at.isoformat(),
            "updated_at": config.updated_at.isoformat(),
            "file_exists": self._config_file.exists(),
            "file_size": self._config_file.stat().st_size
            if self._config_file.exists()
            else 0,
        }

    def validate_config(self) -> dict:
        """
        Validate the current configuration and return validation results.

        Returns:
            Dict: Validation results with issues and warnings
        """
        issues = []
        warnings = []

        try:
            config = self.config

            # Validate project configurations
            self._validate_projects(config.projects, issues, warnings)

            # Validate configuration file structure
            self._validate_config_file_structure(issues)

            # Validate preferences
            self._validate_preferences(config.preferences, warnings)

        except Exception as e:
            issues.append(f"Exception during validation: {e}")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
        }

    def _validate_projects(self, projects: list, issues: list, warnings: list) -> None:
        """Validate project configurations."""
        # Check for duplicate project IDs
        project_ids = [p.id for p in projects]
        if len(project_ids) != len(set(project_ids)):
            issues.append("Duplicate project IDs found")

        # Check for invalid project paths
        for project in projects:
            self._validate_project_path(project, warnings)

    def _validate_project_path(self, project, warnings: list) -> None:
        """Validate a single project path."""
        project_path = Path(project.path)
        if not project_path.exists():
            warnings.append(f"Project path does not exist: {project.path}")
        elif not (project_path / ".git").exists():
            warnings.append(f"Project path is not a Git repository: {project.path}")

    def _validate_config_file_structure(self, issues: list) -> None:
        """Validate configuration file structure."""
        if not self._config_file.parent.exists():
            issues.append(
                f"Configuration directory does not exist: {self._config_file.parent}"
            )
        elif not self._config_file.parent.is_dir():
            issues.append(
                f"Configuration directory is not a directory: {self._config_file.parent}"
            )

    def _validate_preferences(self, prefs, warnings: list) -> None:
        """Validate preference values."""
        if prefs.auto_refresh_interval < 1:
            warnings.append("Auto refresh interval is too low (< 1 second)")
        if prefs.command_timeout < 1:
            warnings.append("Command timeout is too low (< 1 second)")
        if prefs.max_command_history < 1:
            warnings.append("Max command history is too low (< 1)")

    def __str__(self) -> str:
        """String representation of the configuration manager."""
        return f"ConfigManager(config_file='{self._config_file}')"

    def __repr__(self) -> str:
        """Detailed string representation of the configuration manager."""
        config_loaded = self._config is not None
        return (
            f"ConfigManager(config_file='{self._config_file}', "
            f"config_loaded={config_loaded})"
        )
