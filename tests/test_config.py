"""Tests for configuration models and management."""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from wt_manager.models.config import AppConfig, ProjectConfig, UserPreferences
from wt_manager.models.project import Project, ProjectStatus
from wt_manager.services.config_manager import ConfigManager


class TestUserPreferences(unittest.TestCase):
    """Test cases for UserPreferences model."""

    def test_default_preferences(self):
        """Test default preference values."""
        prefs = UserPreferences()

        self.assertEqual(prefs.theme, "auto")
        self.assertEqual(prefs.auto_refresh_interval, 30)
        self.assertFalse(prefs.show_hidden_files)
        self.assertEqual(prefs.default_editor, "")
        self.assertEqual(prefs.default_terminal, "")
        self.assertTrue(prefs.confirm_destructive_actions)
        self.assertEqual(prefs.max_command_history, 100)
        self.assertEqual(prefs.command_timeout, 300)
        self.assertTrue(prefs.git_fetch_on_create)
        self.assertEqual(prefs.window_geometry, {})
        self.assertEqual(prefs.panel_sizes, {})

    def test_preferences_serialization(self):
        """Test preferences serialization and deserialization."""
        prefs = UserPreferences(
            theme="dark",
            auto_refresh_interval=60,
            show_hidden_files=True,
            default_editor="code",
            default_terminal="terminal",
            window_geometry={"width": 800, "height": 600},
            panel_sizes={"left": 300, "right": 500},
        )

        # Test to_dict
        data = prefs.to_dict()
        self.assertEqual(data["theme"], "dark")
        self.assertEqual(data["auto_refresh_interval"], 60)
        self.assertTrue(data["show_hidden_files"])
        self.assertEqual(data["default_editor"], "code")
        self.assertEqual(data["window_geometry"], {"width": 800, "height": 600})

        # Test from_dict
        restored_prefs = UserPreferences.from_dict(data)
        self.assertEqual(restored_prefs.theme, "dark")
        self.assertEqual(restored_prefs.auto_refresh_interval, 60)
        self.assertTrue(restored_prefs.show_hidden_files)
        self.assertEqual(restored_prefs.default_editor, "code")
        self.assertEqual(restored_prefs.window_geometry, {"width": 800, "height": 600})


class TestProjectConfig(unittest.TestCase):
    """Test cases for ProjectConfig model."""

    def test_project_config_creation(self):
        """Test project config creation."""
        now = datetime.now()
        config = ProjectConfig(
            id="test-id",
            name="Test Project",
            path="/path/to/project",
            last_accessed=now,
            is_favorite=True,
            custom_commands={"build": "npm run build"},
            notes="Test notes",
        )

        self.assertEqual(config.id, "test-id")
        self.assertEqual(config.name, "Test Project")
        self.assertEqual(config.path, "/path/to/project")
        self.assertEqual(config.last_accessed, now)
        self.assertTrue(config.is_favorite)
        self.assertEqual(config.custom_commands, {"build": "npm run build"})
        self.assertEqual(config.notes, "Test notes")

    def test_project_config_serialization(self):
        """Test project config serialization and deserialization."""
        now = datetime.now()
        config = ProjectConfig(
            id="test-id",
            name="Test Project",
            path="/path/to/project",
            last_accessed=now,
            is_favorite=True,
            custom_commands={"build": "npm run build"},
            notes="Test notes",
        )

        # Test to_dict
        data = config.to_dict()
        self.assertEqual(data["id"], "test-id")
        self.assertEqual(data["name"], "Test Project")
        self.assertEqual(data["path"], "/path/to/project")
        self.assertEqual(data["last_accessed"], now.isoformat())
        self.assertTrue(data["is_favorite"])
        self.assertEqual(data["custom_commands"], {"build": "npm run build"})
        self.assertEqual(data["notes"], "Test notes")

        # Test from_dict
        restored_config = ProjectConfig.from_dict(data)
        self.assertEqual(restored_config.id, "test-id")
        self.assertEqual(restored_config.name, "Test Project")
        self.assertEqual(restored_config.path, "/path/to/project")
        self.assertEqual(restored_config.last_accessed, now)
        self.assertTrue(restored_config.is_favorite)
        self.assertEqual(restored_config.custom_commands, {"build": "npm run build"})
        self.assertEqual(restored_config.notes, "Test notes")

    def test_from_project(self):
        """Test creating project config from project instance."""
        now = datetime.now()
        project = Project(
            id="test-id",
            name="Test Project",
            path="/path/to/project",
            status=ProjectStatus.ACTIVE,
            last_accessed=now,
        )

        config = ProjectConfig.from_project(project)
        self.assertEqual(config.id, project.id)
        self.assertEqual(config.name, project.name)
        self.assertEqual(config.path, project.path)
        self.assertEqual(config.last_accessed, project.last_accessed)
        self.assertFalse(config.is_favorite)  # Default value
        self.assertEqual(config.custom_commands, {})  # Default value
        self.assertEqual(config.notes, "")  # Default value


class TestAppConfig(unittest.TestCase):
    """Test cases for AppConfig model."""

    def test_default_app_config(self):
        """Test default app config values."""
        config = AppConfig()

        self.assertEqual(config.version, "1.0.0")
        self.assertEqual(config.projects, [])
        self.assertIsInstance(config.preferences, UserPreferences)
        self.assertEqual(config.command_history, {})
        self.assertIsNone(config.last_selected_project)
        self.assertIsInstance(config.created_at, datetime)
        self.assertIsInstance(config.updated_at, datetime)

    def test_add_remove_project(self):
        """Test adding and removing projects."""
        config = AppConfig()
        now = datetime.now()

        project_config = ProjectConfig(
            id="test-id",
            name="Test Project",
            path="/path/to/project",
            last_accessed=now,
        )

        # Test add project
        config.add_project(project_config)
        self.assertEqual(len(config.projects), 1)
        self.assertEqual(config.projects[0].id, "test-id")

        # Test get project
        retrieved = config.get_project("test-id")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.id, "test-id")

        # Test remove project
        removed = config.remove_project("test-id")
        self.assertTrue(removed)
        self.assertEqual(len(config.projects), 0)

        # Test remove non-existent project
        removed = config.remove_project("non-existent")
        self.assertFalse(removed)

    def test_update_project(self):
        """Test updating project configuration."""
        config = AppConfig()
        now = datetime.now()

        project_config = ProjectConfig(
            id="test-id",
            name="Test Project",
            path="/path/to/project",
            last_accessed=now,
        )

        config.add_project(project_config)

        # Update project
        updated_config = ProjectConfig(
            id="test-id",
            name="Updated Project",
            path="/path/to/updated",
            last_accessed=now,
            is_favorite=True,
        )

        updated = config.update_project(updated_config)
        self.assertTrue(updated)

        retrieved = config.get_project("test-id")
        self.assertEqual(retrieved.name, "Updated Project")
        self.assertEqual(retrieved.path, "/path/to/updated")
        self.assertTrue(retrieved.is_favorite)

    def test_recent_projects(self):
        """Test getting recent projects."""
        config = AppConfig()

        # Add projects with different access times
        for i in range(5):
            project_config = ProjectConfig(
                id=f"project-{i}",
                name=f"Project {i}",
                path=f"/path/to/project{i}",
                last_accessed=datetime(2023, 1, i + 1),
            )
            config.add_project(project_config)

        recent = config.get_recent_projects(3)
        self.assertEqual(len(recent), 3)

        # Should be sorted by last_accessed descending
        self.assertEqual(recent[0].id, "project-4")  # Jan 5
        self.assertEqual(recent[1].id, "project-3")  # Jan 4
        self.assertEqual(recent[2].id, "project-2")  # Jan 3

    def test_favorite_projects(self):
        """Test getting favorite projects."""
        config = AppConfig()
        now = datetime.now()

        # Add projects, some favorites
        for i in range(3):
            project_config = ProjectConfig(
                id=f"project-{i}",
                name=f"Project {i}",
                path=f"/path/to/project{i}",
                last_accessed=now,
                is_favorite=(i % 2 == 0),  # Even indices are favorites
            )
            config.add_project(project_config)

        favorites = config.get_favorite_projects()
        self.assertEqual(len(favorites), 2)  # Projects 0 and 2
        self.assertTrue(all(p.is_favorite for p in favorites))

    def test_config_serialization(self):
        """Test app config serialization and deserialization."""
        config = AppConfig()
        now = datetime.now()

        # Add some data
        project_config = ProjectConfig(
            id="test-id",
            name="Test Project",
            path="/path/to/project",
            last_accessed=now,
        )
        config.add_project(project_config)
        config.last_selected_project = "test-id"

        # Test to_dict
        data = config.to_dict()
        self.assertEqual(data["version"], "1.0.0")
        self.assertEqual(len(data["projects"]), 1)
        self.assertEqual(data["projects"][0]["id"], "test-id")
        self.assertEqual(data["last_selected_project"], "test-id")

        # Test from_dict
        restored_config = AppConfig.from_dict(data)
        self.assertEqual(restored_config.version, "1.0.0")
        self.assertEqual(len(restored_config.projects), 1)
        self.assertEqual(restored_config.projects[0].id, "test-id")
        self.assertEqual(restored_config.last_selected_project, "test-id")


class TestConfigManager(unittest.TestCase):
    """Test cases for ConfigManager service."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "test_config.json"
        self.manager = ConfigManager(self.config_file)

    def test_config_manager_initialization(self):
        """Test config manager initialization."""
        self.assertEqual(self.manager.get_config_file_path(), self.config_file)

        # Config should be loaded on first access
        config = self.manager.config
        self.assertIsInstance(config, AppConfig)

    def test_save_and_load_config(self):
        """Test saving and loading configuration."""
        # Modify config
        now = datetime.now()
        project = Project(
            id="test-id",
            name="Test Project",
            path="/path/to/project",
            status=ProjectStatus.ACTIVE,
            last_accessed=now,
        )

        success = self.manager.add_project(project)
        self.assertTrue(success)
        self.assertTrue(self.config_file.exists())

        # Create new manager and load config
        new_manager = ConfigManager(self.config_file)
        loaded_config = new_manager.config

        self.assertEqual(len(loaded_config.projects), 1)
        self.assertEqual(loaded_config.projects[0].id, "test-id")

    def test_add_remove_project(self):
        """Test adding and removing projects through manager."""
        now = datetime.now()
        project = Project(
            id="test-id",
            name="Test Project",
            path="/path/to/project",
            status=ProjectStatus.ACTIVE,
            last_accessed=now,
        )

        # Add project
        success = self.manager.add_project(project)
        self.assertTrue(success)

        project_config = self.manager.get_project_config("test-id")
        self.assertIsNotNone(project_config)
        self.assertEqual(project_config.name, "Test Project")

        # Remove project
        success = self.manager.remove_project("test-id")
        self.assertTrue(success)

        project_config = self.manager.get_project_config("test-id")
        self.assertIsNone(project_config)

    def test_update_preferences(self):
        """Test updating user preferences."""
        success = self.manager.update_preferences(
            theme="dark", auto_refresh_interval=60, show_hidden_files=True
        )
        self.assertTrue(success)

        prefs = self.manager.config.preferences
        self.assertEqual(prefs.theme, "dark")
        self.assertEqual(prefs.auto_refresh_interval, 60)
        self.assertTrue(prefs.show_hidden_files)

    def test_backup_and_restore(self):
        """Test configuration backup and restore."""
        # Add some data
        now = datetime.now()
        project = Project(
            id="test-id",
            name="Test Project",
            path="/path/to/project",
            status=ProjectStatus.ACTIVE,
            last_accessed=now,
        )
        self.manager.add_project(project)

        # Create backup
        backup_file = Path(self.temp_dir) / "backup.json"
        success = self.manager.backup_config(backup_file)
        self.assertTrue(success)
        self.assertTrue(backup_file.exists())

        # Modify config
        self.manager.remove_project("test-id")
        self.assertEqual(len(self.manager.config.projects), 0)

        # Restore from backup
        success = self.manager.restore_config(backup_file)
        self.assertTrue(success)
        self.assertEqual(len(self.manager.config.projects), 1)
        self.assertEqual(self.manager.config.projects[0].id, "test-id")

    def test_config_validation(self):
        """Test configuration validation."""
        validation = self.manager.validate_config()
        self.assertIsInstance(validation, dict)
        self.assertIn("valid", validation)
        self.assertIn("issues", validation)
        self.assertIn("warnings", validation)

    def test_config_info(self):
        """Test getting configuration information."""
        info = self.manager.get_config_info()
        self.assertIsInstance(info, dict)
        self.assertIn("config_file", info)
        self.assertIn("version", info)
        self.assertIn("project_count", info)
        self.assertIn("file_exists", info)


if __name__ == "__main__":
    unittest.main()
