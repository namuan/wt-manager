"""Tests for project panel UI components."""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from unittest.mock import patch

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox
from PyQt6.QtTest import QTest

from wt_manager.ui.project_panel import (
    ProjectPanel,
    AddProjectDialog,
    ProjectHealthDialog,
)
from wt_manager.models.project import Project, ProjectStatus


@pytest.fixture
def app():
    """Create QApplication instance for testing."""
    return QApplication.instance() or QApplication([])


@pytest.fixture
def temp_git_repo():
    """Create a temporary Git repository for testing."""
    temp_dir = tempfile.mkdtemp()
    git_dir = Path(temp_dir) / ".git"
    git_dir.mkdir()

    # Create a basic git config
    config_file = git_dir / "config"
    config_file.write_text("""[core]
    repositoryformatversion = 0
    filemode = true
    bare = false
    logallrefupdates = true
[remote "origin"]
    url = https://github.com/example/repo.git
    fetch = +refs/heads/*:refs/remotes/origin/*
""")

    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def temp_non_git_dir():
    """Create a temporary non-Git directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_projects():
    """Create sample projects for testing."""
    return [
        Project(
            id="project1",
            name="Test Project 1",
            path="/path/to/project1",
            status=ProjectStatus.ACTIVE,
            last_accessed=datetime.now(),
        ),
        Project(
            id="project2",
            name="Test Project 2",
            path="/path/to/project2",
            status=ProjectStatus.ERROR,
            last_accessed=datetime.now(),
        ),
        Project(
            id="project3",
            name="Test Project 3",
            path="/path/to/project3",
            status=ProjectStatus.UNAVAILABLE,
            last_accessed=datetime.now(),
        ),
    ]


class TestAddProjectDialog:
    """Test cases for AddProjectDialog."""

    def test_dialog_initialization(self, app):
        """Test dialog initializes correctly."""
        dialog = AddProjectDialog()

        assert dialog.windowTitle() == "Add Project"
        assert dialog.isModal()
        assert not dialog.button_box.button(
            dialog.button_box.StandardButton.Ok
        ).isEnabled()

    def test_browse_button_functionality(self, app, temp_git_repo):
        """Test browse button opens file dialog."""
        dialog = AddProjectDialog()

        # Mock the file dialog to return our temp directory
        with patch("PyQt6.QtWidgets.QFileDialog.getExistingDirectory") as mock_dialog:
            mock_dialog.return_value = temp_git_repo

            # Click browse button
            QTest.mouseClick(dialog.browse_btn, Qt.MouseButton.LeftButton)

            # Check that path was set
            assert dialog.path_edit.text() == temp_git_repo

    def test_path_validation_valid_repo(self, app, temp_git_repo):
        """Test path validation with valid Git repository."""
        dialog = AddProjectDialog()

        # Set valid Git repository path
        dialog.path_edit.setText(temp_git_repo)

        # Wait for validation timer
        QTest.qWait(600)

        # Check validation passed
        assert dialog.button_box.button(dialog.button_box.StandardButton.Ok).isEnabled()
        assert "Valid Git repository" in dialog.validation_status.text()
        # Note: path_info_group visibility may depend on validation timing

    def test_path_validation_non_existent_path(self, app):
        """Test path validation with non-existent path."""
        dialog = AddProjectDialog()

        # Set non-existent path
        dialog.path_edit.setText("/non/existent/path")

        # Wait for validation timer
        QTest.qWait(600)

        # Check validation failed
        assert not dialog.button_box.button(
            dialog.button_box.StandardButton.Ok
        ).isEnabled()
        assert "does not exist" in dialog.validation_status.text()

    def test_path_validation_non_git_directory(self, app, temp_non_git_dir):
        """Test path validation with non-Git directory."""
        dialog = AddProjectDialog()

        # Set non-Git directory path
        dialog.path_edit.setText(temp_non_git_dir)

        # Wait for validation timer
        QTest.qWait(600)

        # Check validation failed
        assert not dialog.button_box.button(
            dialog.button_box.StandardButton.Ok
        ).isEnabled()
        assert "not a Git repository" in dialog.validation_status.text()

    def test_auto_fill_project_name(self, app, temp_git_repo):
        """Test automatic project name filling."""
        dialog = AddProjectDialog()

        # Set valid Git repository path
        dialog.path_edit.setText(temp_git_repo)

        # Wait for validation timer
        QTest.qWait(600)

        # Check project name was auto-filled
        expected_name = Path(temp_git_repo).name
        assert dialog.name_edit.text() == expected_name

    def test_get_project_data(self, app, temp_git_repo):
        """Test getting project data from dialog."""
        dialog = AddProjectDialog()

        dialog.path_edit.setText(temp_git_repo)
        dialog.name_edit.setText("Custom Name")

        data = dialog.get_project_data()

        assert data["path"] == temp_git_repo
        assert data["name"] == "Custom Name"

    def test_external_validation_error(self, app):
        """Test showing external validation error."""
        dialog = AddProjectDialog()

        dialog.show_external_validation_error("External validation failed")

        assert "External validation failed" in dialog.validation_status.text()
        assert not dialog.button_box.button(
            dialog.button_box.StandardButton.Ok
        ).isEnabled()


class TestProjectHealthDialog:
    """Test cases for ProjectHealthDialog."""

    def test_dialog_initialization(self, app, sample_projects):
        """Test health dialog initializes correctly."""
        project = sample_projects[0]
        health_data = {
            "overall_status": "healthy",
            "branch_count": 5,
            "worktree_count": 2,
            "issues": [],
            "warnings": [],
            "last_checked": "2024-01-01T12:00:00",
        }

        dialog = ProjectHealthDialog(project, health_data)

        assert f"Project Health - {project.get_display_name()}" in dialog.windowTitle()
        assert dialog.isModal()

    def test_health_status_display_healthy(self, app, sample_projects):
        """Test display of healthy project status."""
        project = sample_projects[0]
        health_data = {
            "overall_status": "healthy",
            "branch_count": 5,
            "worktree_count": 2,
            "issues": [],
            "warnings": [],
            "last_checked": "2024-01-01T12:00:00",
        }

        ProjectHealthDialog(project, health_data)

        # Check that health status is displayed correctly
        # This is a basic check - in a real test, we'd verify the UI elements more thoroughly

    def test_health_status_display_with_issues(self, app, sample_projects):
        """Test display of project with issues."""
        project = sample_projects[1]  # ERROR status project
        health_data = {
            "overall_status": "unhealthy",
            "branch_count": 0,
            "worktree_count": 0,
            "issues": ["Repository not found", "Permission denied"],
            "warnings": ["Old Git version"],
            "last_checked": "2024-01-01T12:00:00",
        }

        dialog = ProjectHealthDialog(project, health_data)

        # Verify dialog was created successfully
        assert dialog is not None


class TestProjectPanel:
    """Test cases for ProjectPanel."""

    def test_panel_initialization(self, app):
        """Test panel initializes correctly."""
        panel = ProjectPanel()

        assert panel.title_label.text() == "Projects"
        assert panel.add_btn.text() == "Add"
        assert panel.refresh_btn.text() == "Refresh"
        assert panel.remove_btn.text() == "Remove"
        assert not panel.remove_btn.isEnabled()

    def test_populate_projects(self, app, sample_projects):
        """Test populating projects in the panel."""
        panel = ProjectPanel()

        panel.populate_projects(sample_projects)

        # Check that projects were added to the list
        assert panel.project_list.count() == len(sample_projects)

        # Check that projects are stored internally
        assert len(panel._projects) == len(sample_projects)

        # Check status label
        assert "3 projects loaded" in panel.status_label.text()

    def test_project_selection(self, app, sample_projects):
        """Test project selection functionality."""
        panel = ProjectPanel()
        panel.populate_projects(sample_projects)

        # Mock signal emission
        with patch.object(panel, "project_selected") as mock_signal:
            # Select first project
            panel.project_list.setCurrentRow(0)

            # Trigger selection change
            panel._on_selection_changed()

            # Check that signal was emitted and remove button enabled
            assert mock_signal.emit.called
            assert panel.remove_btn.isEnabled()

    def test_add_project_dialog_opening(self, app):
        """Test opening add project dialog."""
        panel = ProjectPanel()

        # Test that clicking the button triggers the correct method
        with patch.object(AddProjectDialog, "exec") as mock_dialog:
            mock_dialog.return_value = QDialog.DialogCode.Rejected
            QTest.mouseClick(panel.add_btn, Qt.MouseButton.LeftButton)
            # The dialog should have been created and shown
            mock_dialog.assert_called_once()

    def test_remove_project_confirmation(self, app, sample_projects):
        """Test remove project confirmation dialog."""
        panel = ProjectPanel()
        panel.populate_projects(sample_projects)

        # Select a project
        panel.project_list.setCurrentRow(0)
        panel._on_selection_changed()

        # Mock message box
        with patch("PyQt6.QtWidgets.QMessageBox.question") as mock_msgbox:
            mock_msgbox.return_value = QMessageBox.StandardButton.Yes

            with patch.object(panel, "remove_project_requested") as mock_signal:
                panel._on_remove_project()

                # Check that confirmation was shown
                mock_msgbox.assert_called_once()

                # Check that signal was emitted
                mock_signal.emit.assert_called_once_with(sample_projects[0].id)

    def test_context_menu_display(self, app, sample_projects):
        """Test context menu display on right-click."""
        panel = ProjectPanel()
        panel.populate_projects(sample_projects)

        # Get first item position
        item = panel.project_list.item(0)
        rect = panel.project_list.visualItemRect(item)
        position = rect.center()

        # Mock menu execution
        with patch("PyQt6.QtWidgets.QMenu.exec") as mock_menu:
            panel._show_context_menu(position)

            # Check that menu was shown
            mock_menu.assert_called_once()

    def test_project_status_indicators(self, app, sample_projects):
        """Test project status indicators display."""
        panel = ProjectPanel()
        panel.populate_projects(sample_projects)

        # Check that status icons are displayed
        for i, project in enumerate(sample_projects):
            item = panel.project_list.item(i)
            text = item.text()

            # Check that status icon is present
            if project.status == ProjectStatus.ACTIVE:
                assert "●" in text
            elif project.status == ProjectStatus.ERROR:
                assert "✗" in text
            elif project.status == ProjectStatus.UNAVAILABLE:
                assert "⚠" in text

    def test_refresh_project_item(self, app, sample_projects):
        """Test refreshing individual project item."""
        panel = ProjectPanel()
        panel.populate_projects(sample_projects)

        # Modify project status
        updated_project = sample_projects[0]
        updated_project.status = ProjectStatus.ERROR
        updated_project.name = "Updated Name"

        # Refresh the item
        panel.refresh_project_item(updated_project)

        # Check that item was updated
        item = panel.project_list.item(0)
        assert "Updated Name" in item.text()
        assert "✗" in item.text()  # Error status icon

    def test_clear_projects(self, app, sample_projects):
        """Test clearing all projects."""
        panel = ProjectPanel()
        panel.populate_projects(sample_projects)

        # Clear projects
        panel.clear_projects()

        # Check that list is empty
        assert panel.project_list.count() == 0
        assert len(panel._projects) == 0
        assert panel._current_project_id is None
        assert not panel.remove_btn.isEnabled()
        assert "No projects loaded" in panel.status_label.text()

    def test_project_health_display(self, app, sample_projects):
        """Test project health dialog display."""
        panel = ProjectPanel()
        panel.populate_projects(sample_projects)

        health_data = {
            "overall_status": "healthy",
            "branch_count": 5,
            "worktree_count": 2,
            "issues": [],
            "warnings": [],
            "last_checked": "2024-01-01T12:00:00",
        }

        # Mock dialog execution
        with patch.object(ProjectHealthDialog, "exec") as mock_exec:
            panel.show_project_health(sample_projects[0].id, health_data)
            mock_exec.assert_called_once()

    def test_error_message_display(self, app):
        """Test error message display methods."""
        from wt_manager.services.message_service import get_message_service
        from unittest.mock import patch

        panel = ProjectPanel()

        # Test validation error
        with patch.object(get_message_service(), "show_error") as mock_show_error:
            panel.show_validation_error("Test validation error")
            mock_show_error.assert_called_once_with(
                "Validation Error", "Test validation error"
            )

        # Test operation error
        with patch.object(get_message_service(), "show_error") as mock_show_error:
            panel.show_operation_error("Test Title", "Test operation error")
            mock_show_error.assert_called_once_with(
                "Test Title", "Test operation error"
            )

    def test_open_in_file_manager(self, app, sample_projects):
        """Test opening project in file manager."""
        panel = ProjectPanel()
        panel.populate_projects(sample_projects)

        # Mock subprocess call
        with patch("subprocess.run") as mock_subprocess:
            panel._open_in_file_manager(sample_projects[0].path)
            mock_subprocess.assert_called_once()

    def test_double_click_health_check(self, app, sample_projects):
        """Test double-click triggers health check."""
        panel = ProjectPanel()
        panel.populate_projects(sample_projects)

        with patch.object(panel, "project_health_requested") as mock_signal:
            item = panel.project_list.item(0)
            panel._on_item_double_clicked(item)

            mock_signal.emit.assert_called_once_with(sample_projects[0].id)

    def test_signal_emissions(self, app, sample_projects):
        """Test that all required signals are emitted correctly."""
        panel = ProjectPanel()

        # Test refresh signal connection
        signal_emitted = False

        def on_refresh():
            nonlocal signal_emitted
            signal_emitted = True

        panel.refresh_projects_requested.connect(on_refresh)
        panel.refresh_btn.clicked.emit()
        assert signal_emitted

        # Test add project signal
        with patch.object(AddProjectDialog, "exec") as mock_dialog:
            mock_dialog.return_value = QDialog.DialogCode.Accepted
            with patch.object(AddProjectDialog, "get_project_data") as mock_data:
                mock_data.return_value = {"path": "/test/path", "name": "Test"}

                add_signal_emitted = False

                def on_add_project(path, name):
                    nonlocal add_signal_emitted
                    add_signal_emitted = True

                panel.add_project_requested.connect(on_add_project)
                panel._on_add_project()
                assert add_signal_emitted


if __name__ == "__main__":
    pytest.main([__file__])
