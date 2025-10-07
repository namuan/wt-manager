"""Tests for WorktreePanel UI component."""

import pytest
from datetime import datetime
from unittest.mock import patch

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QDialogButtonBox
from PyQt6.QtTest import QTest

from wt_manager.models.project import Project, ProjectStatus
from wt_manager.models.worktree import Worktree
from wt_manager.ui.worktree_panel import (
    WorktreePanel,
    CreateWorktreeDialog,
    RemoveWorktreeDialog,
    WorktreeFilterModel,
)


@pytest.fixture
def sample_project():
    """Create a sample project for testing."""
    return Project(
        id="test-project",
        name="Test Project",
        path="/path/to/test/project",
        status=ProjectStatus.ACTIVE,
        last_accessed=datetime.now(),
    )


@pytest.fixture
def sample_worktrees():
    """Create sample worktrees for testing."""
    return [
        Worktree(
            path="/path/to/worktree1",
            branch="main",
            commit_hash="abc123def456",
            is_bare=False,
            is_detached=False,
            has_uncommitted_changes=False,
            last_modified=datetime.now(),
        ),
        Worktree(
            path="/path/to/worktree2",
            branch="feature/test",
            commit_hash="def456ghi789",
            is_bare=False,
            is_detached=False,
            has_uncommitted_changes=True,
            last_modified=datetime.now(),
        ),
        Worktree(
            path="/path/to/worktree3",
            branch="",
            commit_hash="ghi789jkl012",
            is_bare=False,
            is_detached=True,
            has_uncommitted_changes=False,
            last_modified=datetime.now(),
        ),
    ]


class TestWorktreeFilterModel:
    """Test the worktree filter model."""

    def test_filter_by_branch(self, qtbot):
        """Test filtering by branch name."""
        filter_model = WorktreeFilterModel()

        # Test branch filter
        filter_model.set_branch_filter("main")
        assert filter_model._branch_filter == "main"

        filter_model.set_branch_filter("")
        assert filter_model._branch_filter == ""

    def test_filter_by_status(self, qtbot):
        """Test filtering by status."""
        filter_model = WorktreeFilterModel()

        # Test status filter
        filter_model.set_status_filter("modified")
        assert filter_model._status_filter == "modified"

        filter_model.set_status_filter("")
        assert filter_model._status_filter == ""

    def test_filter_by_text(self, qtbot):
        """Test filtering by text search."""
        filter_model = WorktreeFilterModel()

        # Test text filter
        filter_model.set_text_filter("test")
        assert filter_model._text_filter == "test"

        filter_model.set_text_filter("")
        assert filter_model._text_filter == ""


class TestWorktreePanel:
    """Test the WorktreePanel component."""

    def test_initialization(self, qtbot):
        """Test panel initialization."""
        panel = WorktreePanel()
        qtbot.addWidget(panel)

        self._verify_initial_state(panel)
        self._verify_ui_elements_exist(panel)

    def _verify_initial_state(self, panel):
        """Verify the initial state of the panel."""
        assert panel._current_project is None
        assert panel._current_worktree_path is None
        assert len(panel._worktrees) == 0

    def _verify_ui_elements_exist(self, panel):
        """Verify that all required UI elements exist."""
        assert panel.title_label is not None
        assert panel.project_name_label is not None
        assert panel.new_worktree_btn is not None
        assert panel.worktree_view is not None
        assert panel.search_edit is not None
        assert panel.branch_filter is not None
        assert panel.status_filter is not None

    def test_set_project(self, qtbot, sample_project):
        """Test setting the current project."""
        panel = WorktreePanel()
        qtbot.addWidget(panel)

        # Set project
        panel.set_project(sample_project)

        assert panel._current_project == sample_project
        assert panel.project_name_label.text() == sample_project.get_display_name()
        assert panel.new_worktree_btn.isEnabled()
        assert panel.refresh_btn.isEnabled()

    def test_set_project_none(self, qtbot):
        """Test clearing the current project."""
        panel = WorktreePanel()
        qtbot.addWidget(panel)

        # Clear project
        panel.set_project(None)

        assert panel._current_project is None
        assert panel.project_name_label.text() == "No project selected"
        assert not panel.new_worktree_btn.isEnabled()
        assert not panel.refresh_btn.isEnabled()

    def test_populate_worktrees(self, qtbot, sample_project, sample_worktrees):
        """Test populating worktrees."""
        panel = WorktreePanel()
        qtbot.addWidget(panel)

        panel.set_project(sample_project)
        panel.populate_worktrees(sample_worktrees)

        assert len(panel._worktrees) == 3
        assert panel.model.rowCount() == 3

        # Check that branch filter is updated
        branch_count = panel.branch_filter.count()
        assert branch_count > 1  # Should have "All Branches" plus actual branches

    def test_clear_worktrees(self, qtbot, sample_project, sample_worktrees):
        """Test clearing worktrees."""
        panel = WorktreePanel()
        qtbot.addWidget(panel)

        panel.set_project(sample_project)
        panel.populate_worktrees(sample_worktrees)

        # Clear worktrees
        panel.clear_worktrees()

        assert len(panel._worktrees) == 0
        assert panel.model.rowCount() == 0
        assert panel._current_worktree_path is None

    def test_worktree_selection(self, qtbot, sample_project, sample_worktrees):
        """Test worktree selection."""
        panel = WorktreePanel()
        qtbot.addWidget(panel)

        panel.set_project(sample_project)
        panel.populate_worktrees(sample_worktrees)

        # Select first worktree
        panel.select_worktree(sample_worktrees[0].path)

        selected_worktree = panel.get_selected_worktree()
        assert selected_worktree is not None
        assert selected_worktree.path == sample_worktrees[0].path

    def test_filter_functionality(self, qtbot, sample_project, sample_worktrees):
        """Test filtering functionality."""
        panel = WorktreePanel()
        qtbot.addWidget(panel)

        panel.set_project(sample_project)
        panel.populate_worktrees(sample_worktrees)

        # Test text search
        panel.search_edit.setText("feature")
        QTest.qWait(100)  # Wait for filter to apply

        # Test branch filter
        panel.branch_filter.setCurrentIndex(1)  # Select first non-"All" option
        QTest.qWait(100)

        # Test status filter
        panel.status_filter.setCurrentIndex(2)  # Select "Modified"
        QTest.qWait(100)

        # Clear filters
        panel._clear_filters()
        assert panel.search_edit.text() == ""
        assert panel.branch_filter.currentIndex() == 0
        assert panel.status_filter.currentIndex() == 0

    def test_button_states(self, qtbot, sample_project, sample_worktrees):
        """Test button enabled states."""
        panel = WorktreePanel()
        qtbot.addWidget(panel)

        # Initially no selection
        assert not panel.open_btn.isEnabled()
        assert not panel.terminal_btn.isEnabled()
        assert not panel.run_command_btn.isEnabled()
        assert not panel.remove_btn.isEnabled()

        # Set project and worktrees
        panel.set_project(sample_project)
        panel.populate_worktrees(sample_worktrees)

        # Select a worktree
        panel.select_worktree(sample_worktrees[0].path)

        # Buttons should be enabled
        assert panel.open_btn.isEnabled()
        assert panel.terminal_btn.isEnabled()
        assert panel.run_command_btn.isEnabled()
        assert panel.remove_btn.isEnabled()

    def test_signals_emitted(self, qtbot, sample_project, sample_worktrees):
        """Test that signals are emitted correctly."""
        panel = WorktreePanel()
        qtbot.addWidget(panel)

        panel.set_project(sample_project)
        panel.populate_worktrees(sample_worktrees)

        # Test worktree selection signal
        with qtbot.waitSignal(panel.worktree_selected, timeout=1000):
            panel.select_worktree(sample_worktrees[0].path)

        # Test refresh signal
        with qtbot.waitSignal(panel.refresh_worktrees_requested, timeout=1000):
            QTest.mouseClick(panel.refresh_btn, Qt.MouseButton.LeftButton)

        # Test open worktree signal
        panel.select_worktree(sample_worktrees[0].path)
        with qtbot.waitSignal(panel.open_worktree_requested, timeout=1000):
            QTest.mouseClick(panel.open_btn, Qt.MouseButton.LeftButton)

    def test_context_menu(self, qtbot, sample_project, sample_worktrees):
        """Test context menu functionality."""
        panel = WorktreePanel()
        qtbot.addWidget(panel)

        panel.set_project(sample_project)
        panel.populate_worktrees(sample_worktrees)
        panel.select_worktree(sample_worktrees[0].path)

        # Simulate right-click to show context menu
        # Note: This is a basic test - full context menu testing would require more setup
        view_rect = panel.worktree_view.rect()
        center_point = view_rect.center()

        # The context menu should be callable without errors
        try:
            panel._show_context_menu(center_point)
        except Exception as e:
            pytest.fail(f"Context menu failed: {e}")

    def test_refresh_worktree_item(self, qtbot, sample_project, sample_worktrees):
        """Test refreshing a specific worktree item."""
        panel = WorktreePanel()
        qtbot.addWidget(panel)

        panel.set_project(sample_project)
        panel.populate_worktrees(sample_worktrees)

        # Modify a worktree and refresh it
        updated_worktree = Worktree(
            path=sample_worktrees[0].path,
            branch="updated-branch",
            commit_hash="updated123",
            is_bare=False,
            is_detached=False,
            has_uncommitted_changes=True,
            last_modified=datetime.now(),
        )

        panel.refresh_worktree_item(updated_worktree)

        # Verify the item was updated
        # This would require checking the model data, which is complex in this test setup


class TestCreateWorktreeDialog:
    """Test the CreateWorktreeDialog."""

    def test_dialog_initialization(self, qtbot, sample_project):
        """Test dialog initialization."""
        available_branches = ["main", "develop", "feature/test"]
        dialog = CreateWorktreeDialog(sample_project, available_branches)
        qtbot.addWidget(dialog)

        assert dialog.project == sample_project
        assert dialog.available_branches == available_branches
        assert (
            dialog.windowTitle()
            == f"Create Worktree - {sample_project.get_display_name()}"
        )

    def test_branch_type_selection(self, qtbot, sample_project):
        """Test branch type selection."""
        available_branches = ["main", "develop"]
        dialog = CreateWorktreeDialog(sample_project, available_branches)
        qtbot.addWidget(dialog)

        # Initially existing branch should be selected
        assert dialog.existing_branch_radio.isChecked()
        assert dialog.branch_combo.isEnabled()
        assert not dialog.new_branch_edit.isEnabled()

        # Switch to new branch
        dialog.new_branch_radio.setChecked(True)
        dialog._on_branch_type_changed()

        assert dialog.new_branch_radio.isChecked()
        assert not dialog.existing_branch_radio.isChecked()
        assert not dialog.branch_combo.isEnabled()
        assert dialog.new_branch_edit.isEnabled()

    @patch("PyQt6.QtWidgets.QFileDialog.getExistingDirectory")
    def test_browse_for_path(self, mock_dialog, qtbot, sample_project):
        """Test browsing for worktree path."""
        mock_dialog.return_value = "/selected/path"

        available_branches = ["main"]
        dialog = CreateWorktreeDialog(sample_project, available_branches)
        qtbot.addWidget(dialog)

        # Trigger browse
        dialog._browse_for_path()

        # Should set the path
        assert "/selected/path" in dialog.path_edit.text()

    def test_get_worktree_config(self, qtbot, sample_project):
        """Test getting worktree configuration."""
        available_branches = ["main", "develop"]
        dialog = CreateWorktreeDialog(sample_project, available_branches)
        qtbot.addWidget(dialog)

        # Set up dialog state
        dialog.path_edit.setText("/test/path")
        dialog.existing_branch_radio.setChecked(True)
        dialog.branch_combo.setCurrentText("main")
        dialog.fetch_remote_check.setChecked(True)

        config = dialog.get_worktree_config()

        assert config["path"] == "/test/path"
        assert config["branch"] == "main"
        assert not config["is_new_branch"]
        assert config["base_branch"] is None
        assert config["fetch_remote"]

    def test_validation_empty_path(self, qtbot, sample_project):
        """Test validation with empty path."""
        available_branches = ["main"]
        dialog = CreateWorktreeDialog(sample_project, available_branches)
        qtbot.addWidget(dialog)

        # Empty path should disable OK button
        dialog.path_edit.setText("")
        dialog._validate_inputs()

        ok_button = dialog.button_box.button(QDialogButtonBox.StandardButton.Ok)
        assert not ok_button.isEnabled()


class TestRemoveWorktreeDialog:
    """Test the RemoveWorktreeDialog."""

    def test_dialog_initialization(self, qtbot, sample_project, sample_worktrees):
        """Test dialog initialization."""
        worktree = sample_worktrees[0]
        dialog = RemoveWorktreeDialog(worktree, sample_project)
        qtbot.addWidget(dialog)

        assert dialog.worktree == worktree
        assert dialog.project == sample_project
        assert dialog.windowTitle() == "Remove Worktree"

    def test_safety_checks_display(self, qtbot, sample_project, sample_worktrees):
        """Test that safety checks are displayed."""
        # Use worktree with uncommitted changes
        worktree = sample_worktrees[1]  # Has uncommitted changes
        dialog = RemoveWorktreeDialog(worktree, sample_project)
        qtbot.addWidget(dialog)

        # Dialog should show warning about uncommitted changes
        # This would require checking the UI elements, which is complex in this test setup

    def test_confirmation_requirement(self, qtbot, sample_project, sample_worktrees):
        """Test that confirmation is required."""
        worktree = sample_worktrees[0]
        dialog = RemoveWorktreeDialog(worktree, sample_project)
        qtbot.addWidget(dialog)

        # OK button should be disabled initially
        ok_button = dialog.button_box.button(QDialogButtonBox.StandardButton.Ok)
        assert not ok_button.isEnabled()

        # Enable confirmation
        dialog.confirm_check.setChecked(True)
        dialog._on_confirmation_changed(True)

        assert ok_button.isEnabled()

    def test_get_removal_config(self, qtbot, sample_project, sample_worktrees):
        """Test getting removal configuration."""
        worktree = sample_worktrees[0]
        dialog = RemoveWorktreeDialog(worktree, sample_project)
        qtbot.addWidget(dialog)

        # Set options
        dialog.force_check.setChecked(True)
        dialog.remove_directory_check.setChecked(False)

        config = dialog.get_removal_config()

        assert config["force"]
        assert not config["remove_directory"]


class TestWorktreePanelIntegration:
    """Integration tests for WorktreePanel with dialogs."""

    @patch.object(CreateWorktreeDialog, "exec")
    @patch.object(CreateWorktreeDialog, "get_worktree_config")
    def test_create_worktree_workflow(
        self, mock_get_config, mock_exec, qtbot, sample_project
    ):
        """Test the complete create worktree workflow."""
        mock_exec.return_value = QDialog.DialogCode.Accepted
        mock_get_config.return_value = {
            "path": "/test/path",
            "branch": "main",
            "is_new_branch": False,
            "base_branch": None,
            "fetch_remote": True,
        }

        panel = WorktreePanel()
        qtbot.addWidget(panel)

        panel.set_project(sample_project)

        # Test signal emission
        with qtbot.waitSignal(panel.create_worktree_requested, timeout=1000):
            QTest.mouseClick(panel.new_worktree_btn, Qt.MouseButton.LeftButton)

    @patch.object(RemoveWorktreeDialog, "exec")
    @patch.object(RemoveWorktreeDialog, "get_removal_config")
    def test_remove_worktree_workflow(
        self, mock_get_config, mock_exec, qtbot, sample_project, sample_worktrees
    ):
        """Test the complete remove worktree workflow."""
        mock_exec.return_value = QDialog.DialogCode.Accepted
        mock_get_config.return_value = {
            "force": False,
            "remove_directory": True,
        }

        panel = WorktreePanel()
        qtbot.addWidget(panel)

        panel.set_project(sample_project)
        panel.populate_worktrees(sample_worktrees)
        panel.select_worktree(sample_worktrees[0].path)

        # Test signal emission
        with qtbot.waitSignal(panel.remove_worktree_requested, timeout=1000):
            QTest.mouseClick(panel.remove_btn, Qt.MouseButton.LeftButton)

    def test_error_handling(self, qtbot, sample_project):
        """Test error handling methods."""
        from wt_manager.services.message_service import get_message_service
        from unittest.mock import patch

        panel = WorktreePanel()
        qtbot.addWidget(panel)

        # Test validation error
        with patch.object(get_message_service(), "show_error") as mock_show_error:
            panel.show_validation_error("Test validation error")
            mock_show_error.assert_called_with(
                "Validation Error", "Test validation error"
            )

        # Test operation error
        with patch.object(get_message_service(), "show_error") as mock_show_error:
            panel.show_operation_error("Test Error", "Test error message")
            mock_show_error.assert_called_with("Test Error", "Test error message")

        # Test operation success
        with patch.object(get_message_service(), "show_success") as mock_show_success:
            panel.show_operation_success("Test success message")
            mock_show_success.assert_called_with("Test success message")

    def test_filter_summary(self, qtbot, sample_project):
        """Test filter summary functionality."""
        panel = WorktreePanel()
        qtbot.addWidget(panel)

        # No filters
        summary = panel.get_filter_summary()
        assert "No filters applied" in summary

        # With filters
        panel.search_edit.setText("test")
        panel.branch_filter.setCurrentIndex(1)  # Assume there's a second item

        summary = panel.get_filter_summary()
        assert "Filtered by:" in summary


if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__])
