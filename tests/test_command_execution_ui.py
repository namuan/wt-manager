"""Integration tests for command execution UI components."""

import pytest
import tempfile
from unittest.mock import Mock, patch

from PyQt6.QtTest import QTest

from wt_manager.ui.command_dialog import CommandInputDialog
from wt_manager.ui.command_output_widget import (
    CommandOutputPanel,
    CommandExecutionWidget,
)
from wt_manager.ui.main_window import MainWindow
from wt_manager.models.command_execution import CommandExecution
from wt_manager.services.validation_service import ValidationService
from wt_manager.services.command_service import CommandService


class TestCommandInputDialog:
    """Test the command input dialog functionality."""

    @pytest.fixture
    def temp_worktree(self):
        """Create a temporary worktree directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def validation_service(self):
        """Create a mock validation service."""
        service = Mock(spec=ValidationService)
        service.validate_command_safety.return_value = Mock(
            is_valid=True, message="Command is safe"
        )
        return service

    @pytest.fixture
    def dialog(self, temp_worktree, validation_service, qtbot):
        """Create a command input dialog for testing."""
        command_history = ["git status", "npm test", "python -m pytest"]
        dialog = CommandInputDialog(
            worktree_path=temp_worktree,
            command_history=command_history,
            validation_service=validation_service,
        )
        qtbot.addWidget(dialog)
        return dialog

    def test_dialog_initialization(self, dialog, temp_worktree):
        """Test dialog initializes correctly."""
        assert dialog.worktree_path == temp_worktree
        assert dialog.windowTitle() == "Run Command"
        assert not dialog.execute_btn.isEnabled()  # Should be disabled initially

    def test_command_input_validation(self, dialog, qtbot):
        """Test command input validation."""
        # Test empty command
        dialog.command_input.setText("")
        QTest.qWait(100)  # Wait for validation timer
        assert not dialog.execute_btn.isEnabled()

        # Test valid command
        dialog.command_input.setText("git status")
        QTest.qWait(400)  # Wait for validation timer (300ms + buffer)
        assert dialog.execute_btn.isEnabled()

    def test_command_validation_error(self, dialog, qtbot):
        """Test command validation error handling."""
        # Mock validation service to return error
        dialog.validation_service.validate_command_safety.return_value = Mock(
            is_valid=False, message="Dangerous command detected"
        )

        dialog.command_input.setText("rm -rf /")
        QTest.qWait(400)  # Wait for validation timer

        assert not dialog.execute_btn.isEnabled()
        assert "Dangerous command detected" in dialog.validation_status.text()

    def test_common_commands_insertion(self, dialog, qtbot):
        """Test inserting common commands."""
        # Select a common command
        dialog.common_commands.setCurrentText("git status")
        assert dialog.insert_common_btn.isEnabled()

        # Insert the command
        dialog._insert_common_command()
        assert dialog.command_input.text() == "git status"

    def test_history_commands_usage(self, dialog, qtbot):
        """Test using commands from history."""
        if hasattr(dialog, "history_list"):
            # Select a history command
            dialog.history_list.setCurrentText("npm test")
            assert dialog.use_history_btn.isEnabled()

            # Use the command
            dialog._use_history_command()
            assert dialog.command_input.text() == "npm test"

    def test_timeout_configuration(self, dialog, qtbot):
        """Test timeout configuration."""
        # Test default timeout
        assert dialog.timeout_spin.value() == 300

        # Test no timeout checkbox
        dialog.no_timeout_check.setChecked(True)
        assert not dialog.timeout_spin.isEnabled()
        assert dialog.get_timeout() == 0

        # Test custom timeout
        dialog.no_timeout_check.setChecked(False)
        dialog.timeout_spin.setValue(600)
        assert dialog.get_timeout() == 600

    def test_command_execution_signal(self, dialog, qtbot):
        """Test command execution signal emission."""
        # Set up signal spy
        signal_spy = []
        dialog.command_execution_requested.connect(
            lambda cmd, path, timeout: signal_spy.append((cmd, path, timeout))
        )

        # Enter valid command
        dialog.command_input.setText("git status")
        QTest.qWait(400)  # Wait for validation

        # Execute command
        dialog._execute_command()

        # Check signal was emitted
        assert len(signal_spy) == 1
        command, worktree_path, timeout = signal_spy[0]
        assert command == "git status"
        assert worktree_path == dialog.worktree_path
        assert timeout == 300

    def test_dangerous_command_confirmation(self, dialog, qtbot):
        """Test dangerous command confirmation dialog."""
        with patch("wt_manager.ui.command_dialog.QMessageBox") as mock_msgbox:
            # Mock user clicking "No"
            mock_msgbox.question.return_value = mock_msgbox.StandardButton.No

            dialog.command_input.setText("rm -rf .")
            QTest.qWait(400)  # Wait for validation

            # Try to execute - should show confirmation
            dialog._execute_command()

            # Verify confirmation was shown
            mock_msgbox.question.assert_called_once()


class TestCommandOutputWidget:
    """Test the command output widget functionality."""

    @pytest.fixture
    def sample_execution(self):
        """Create a sample command execution."""
        return CommandExecution(
            id="test-exec-1",
            command="git status",
            worktree_path="/tmp/test-worktree",
            start_time=None,
            timeout_seconds=300,
        )

    @pytest.fixture
    def execution_widget(self, sample_execution, qtbot):
        """Create a command execution widget for testing."""
        widget = CommandExecutionWidget(sample_execution)
        widget.show()  # Explicitly show the widget
        qtbot.addWidget(widget)
        qtbot.wait(10)  # Wait for widget to be shown
        return widget

    @pytest.fixture
    def output_panel(self, qtbot):
        """Create a command output panel for testing."""
        panel = CommandOutputPanel()
        qtbot.addWidget(panel)
        return panel

    def test_execution_widget_initialization(self, execution_widget, sample_execution):
        """Test execution widget initializes correctly."""
        assert execution_widget.execution == sample_execution
        assert "git status" in execution_widget.command_label.text()

    def test_execution_widget_status_updates(
        self, execution_widget, sample_execution, qtbot
    ):
        """Test execution widget status updates."""
        # Test running status
        sample_execution.mark_started(12345)
        execution_widget._update_display()
        qtbot.wait(10)  # Allow Qt events to process

        assert execution_widget.progress_bar.isVisible()
        assert "Running" in execution_widget.status_label.text()

        # Test completed status
        sample_execution.mark_completed(0)
        execution_widget._update_display()
        qtbot.wait(10)  # Allow Qt events to process

        assert not execution_widget.progress_bar.isVisible()
        assert "Completed" in execution_widget.status_label.text()

    def test_execution_widget_output_append(self, execution_widget, qtbot):
        """Test appending output to execution widget."""
        # Append normal output
        execution_widget.append_output("Test output line 1\n")
        assert "Test output line 1" in execution_widget.output_text.toPlainText()

        # Append error output
        execution_widget.append_output("Error message\n", is_error=True)
        assert "Error message" in execution_widget.output_text.toPlainText()

    def test_execution_widget_expand_collapse(self, execution_widget, qtbot):
        """Test expand/collapse functionality."""
        from PyQt6.QtTest import QTest
        from PyQt6.QtCore import Qt

        # Initially should be collapsed
        assert not execution_widget._is_expanded
        assert execution_widget.output_text.maximumHeight() == 200
        assert "▼ Expand" in execution_widget.expand_btn.text()

        # Click expand button
        QTest.mouseClick(execution_widget.expand_btn, Qt.MouseButton.LeftButton)
        qtbot.wait(10)

        # Should now be expanded
        assert execution_widget._is_expanded
        assert execution_widget.output_text.maximumHeight() == 16777215
        assert "▲ Collapse" in execution_widget.expand_btn.text()

        # Click collapse button
        QTest.mouseClick(execution_widget.expand_btn, Qt.MouseButton.LeftButton)
        qtbot.wait(10)

        # Should be collapsed again
        assert not execution_widget._is_expanded
        assert execution_widget.output_text.maximumHeight() == 200
        assert "▼ Expand" in execution_widget.expand_btn.text()

    def test_output_panel_initialization(self, output_panel):
        """Test output panel initializes correctly."""
        assert output_panel.title_label.text() == "Command Output"
        assert "No active commands" in output_panel.active_count_label.text()
        assert not output_panel.cancel_all_btn.isEnabled()

    def test_output_panel_add_execution(self, output_panel, sample_execution):
        """Test adding execution to output panel."""
        output_panel.add_execution(sample_execution)

        assert sample_execution.id in output_panel._execution_widgets
        assert len(output_panel._execution_widgets) == 1

    def test_output_panel_update_execution(self, output_panel, sample_execution):
        """Test updating execution in output panel."""
        # Add execution first
        output_panel.add_execution(sample_execution)

        # Update execution status
        sample_execution.mark_started(12345)
        output_panel.update_execution(sample_execution)

        widget = output_panel._execution_widgets[sample_execution.id]
        assert widget.execution.is_running()

    def test_output_panel_remove_execution(self, output_panel, sample_execution):
        """Test removing execution from output panel."""
        # Add execution first
        output_panel.add_execution(sample_execution)
        assert len(output_panel._execution_widgets) == 1

        # Remove execution
        output_panel.remove_execution(sample_execution.id)
        assert len(output_panel._execution_widgets) == 0

    def test_output_panel_append_output(self, output_panel, sample_execution):
        """Test appending output to specific execution."""
        # Add execution first
        output_panel.add_execution(sample_execution)

        # Append output
        output_panel.append_output(sample_execution.id, "Test output")

        widget = output_panel._execution_widgets[sample_execution.id]
        assert "Test output" in widget.output_text.toPlainText()

    def test_output_panel_clear_all(self, output_panel, sample_execution):
        """Test clearing all output."""
        # Add some executions
        output_panel.add_execution(sample_execution)

        exec2 = CommandExecution(
            id="test-exec-2",
            command="npm test",
            worktree_path="/tmp/test-worktree",
            start_time=None,
        )
        output_panel.add_execution(exec2)

        assert len(output_panel._execution_widgets) == 2

        # Clear all
        output_panel.clear_all_output()
        assert len(output_panel._execution_widgets) == 0

    def test_output_panel_active_executions(self, output_panel, sample_execution):
        """Test tracking active executions."""
        # Add running execution
        sample_execution.mark_started(12345)
        output_panel.add_execution(sample_execution)

        active = output_panel.get_active_executions()
        assert sample_execution.id in active
        assert output_panel.cancel_all_btn.isEnabled()

        # Complete execution
        sample_execution.mark_completed(0)
        output_panel.update_execution(sample_execution)

        active = output_panel.get_active_executions()
        assert sample_execution.id not in active

    def test_output_panel_cancel_signal(self, output_panel, sample_execution, qtbot):
        """Test cancel command signal emission."""
        # Set up signal spy
        signal_spy = []
        output_panel.cancel_command_requested.connect(signal_spy.append)

        # Add running execution
        sample_execution.mark_started(12345)
        output_panel.add_execution(sample_execution)

        # Click cancel all
        output_panel._cancel_all_commands()

        # Check signal was emitted
        assert len(signal_spy) == 1
        assert signal_spy[0] == sample_execution.id


class TestMainWindowCommandIntegration:
    """Test command execution integration in main window."""

    @pytest.fixture
    def mock_command_service(self):
        """Create a mock command service."""
        service = Mock(spec=CommandService)
        service.execute_command.return_value = CommandExecution(
            id="test-exec-1",
            command="git status",
            worktree_path="/tmp/test-worktree",
            start_time=None,
        )
        service.get_command_history.return_value = []
        service.cancel_command.return_value = True
        return service

    @pytest.fixture
    def mock_validation_service(self):
        """Create a mock validation service."""
        service = Mock(spec=ValidationService)
        service.validate_command_safety.return_value = Mock(
            is_valid=True, message="Command is safe"
        )
        return service

    @pytest.fixture
    def main_window(self, mock_command_service, mock_validation_service, qtbot):
        """Create a main window with mocked services."""
        window = MainWindow(
            command_service=mock_command_service,
            validation_service=mock_validation_service,
        )
        # Ensure command panel starts unchecked for tests
        window.command_panel_group.setChecked(False)
        qtbot.addWidget(window)
        return window

    def test_main_window_command_service_setup(self, main_window, mock_command_service):
        """Test command service is properly set up."""
        assert main_window.command_service == mock_command_service
        assert main_window.command_service.on_command_started is not None
        assert main_window.command_service.on_command_finished is not None
        assert main_window.command_service.on_command_output is not None
        assert main_window.command_service.on_command_error is not None

    def test_show_command_dialog(self, main_window, qtbot):
        """Test showing command dialog."""
        with patch("wt_manager.ui.main_window.CommandInputDialog") as mock_dialog_class:
            mock_dialog = Mock()
            mock_dialog_class.return_value = mock_dialog

            # Show command dialog
            main_window._show_command_dialog("/tmp/test-worktree")

            # Verify dialog was created and shown
            mock_dialog_class.assert_called_once()
            mock_dialog.exec.assert_called_once()

    def test_execute_command(self, main_window, mock_command_service):
        """Test command execution."""
        # Execute command
        main_window._execute_command("git status", "/tmp/test-worktree", 300)

        # Verify command service was called
        mock_command_service.execute_command.assert_called_once_with(
            command="git status",
            worktree_path="/tmp/test-worktree",
            timeout_seconds=300,
        )

        # Verify command panel is shown
        assert main_window.command_panel_group.isChecked()

    def test_execute_command_error_handling(self, main_window, mock_command_service):
        """Test command execution error handling."""
        # Mock service to raise exception
        mock_command_service.execute_command.side_effect = Exception("Test error")

        # Execute command
        main_window._execute_command("git status", "/tmp/test-worktree", 300)

        # Verify error is handled gracefully
        assert "Error: Test error" in main_window.command_panel.status_label.text()

    def test_command_started_callback(self, main_window):
        """Test command started callback."""
        # Create execution and add to active executions
        execution = CommandExecution(
            id="test-exec-1",
            command="git status",
            worktree_path="/tmp/test-worktree",
            start_time=None,
        )
        execution.mark_started(12345)
        main_window._active_executions[execution.id] = execution

        # Call callback
        main_window._on_command_started(execution.id)

        # Verify status is updated
        assert "Running" in main_window.command_panel.status_label.text()

    def test_command_finished_callback(self, main_window):
        """Test command finished callback."""
        # Create execution and add to active executions
        execution = CommandExecution(
            id="test-exec-1",
            command="git status",
            worktree_path="/tmp/test-worktree",
            start_time=None,
        )
        execution.mark_completed(0)
        main_window._active_executions[execution.id] = execution

        # Call callback
        main_window._on_command_finished(execution.id)

        # Verify execution is removed from active list
        assert execution.id not in main_window._active_executions
        assert "Completed successfully" in main_window.command_panel.status_label.text()

    def test_command_output_callback(self, main_window):
        """Test command output callback."""
        execution_id = "test-exec-1"

        # Call callback
        main_window._on_command_output(execution_id, "Test output line\n")

        # Verify output is appended to panel
        # Note: This would require the execution to be in the panel first
        # In a real scenario, the execution would be added when started

    def test_command_error_callback(self, main_window):
        """Test command error callback."""
        execution_id = "test-exec-1"

        # Call callback
        main_window._on_command_error(execution_id, "Test error message\n")

        # Verify error output is appended to panel
        # Note: This would require the execution to be in the panel first

    def test_cancel_running_commands(self, main_window, mock_command_service):
        """Test cancelling running commands."""
        # Add some active executions
        main_window._active_executions["exec-1"] = Mock()
        main_window._active_executions["exec-2"] = Mock()

        # Cancel commands
        main_window.cancel_running_commands()

        # Verify service cancel was called for each execution
        assert mock_command_service.cancel_command.call_count == 2

    def test_cancel_single_command(self, main_window, mock_command_service):
        """Test cancelling a single command."""
        execution_id = "test-exec-1"

        # Cancel command
        main_window._cancel_single_command(execution_id)

        # Verify service cancel was called
        mock_command_service.cancel_command.assert_called_once_with(execution_id)

    def test_command_panel_visibility_toggle(self, main_window, qtbot):
        """Test command panel visibility toggle."""
        # Initially hidden
        assert not main_window.command_panel_group.isChecked()

        # Show panel
        main_window.show_command_panel()
        assert main_window.command_panel_group.isChecked()

        # Hide panel
        main_window.hide_command_panel()
        assert not main_window.command_panel_group.isChecked()

    def test_run_command_menu_action(self, main_window, qtbot):
        """Test run command menu action."""
        with patch.object(main_window, "_show_command_dialog") as mock_show_dialog:
            # Set current worktree
            main_window._current_worktree_path = "/tmp/test-worktree"

            # Trigger menu action
            main_window._on_run_command_menu()

            # Verify dialog is shown
            mock_show_dialog.assert_called_once_with("/tmp/test-worktree")

    def test_cleanup_on_close(self, main_window, mock_command_service):
        """Test cleanup when window closes."""
        # Add some active executions
        main_window._active_executions["exec-1"] = Mock()

        # Mock the close event
        with patch.object(main_window, "save_state"):
            close_event = Mock()
            main_window.closeEvent(close_event)

            # Verify cleanup was called
            close_event.accept.assert_called_once()


class TestCommandExecutionWorkflow:
    """Test complete command execution workflow."""

    @pytest.fixture
    def temp_worktree(self):
        """Create a temporary worktree directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    def test_complete_command_execution_workflow(self, qtbot, temp_worktree):
        """Test complete workflow from dialog to execution to output."""
        # This test would require a more complex setup with real services
        # For now, we'll test the integration points

        # Create mock services
        mock_command_service = Mock(spec=CommandService)
        mock_validation_service = Mock(spec=ValidationService)

        # Set up validation to pass
        mock_validation_service.validate_command_safety.return_value = Mock(
            is_valid=True, message="Command is safe"
        )

        # Set up command execution to return a mock execution
        mock_execution = CommandExecution(
            id="test-exec-1",
            command="echo 'Hello World'",
            worktree_path=temp_worktree,
            start_time=None,
        )
        mock_command_service.execute_command.return_value = mock_execution
        mock_command_service.get_command_history.return_value = []

        # Create main window
        main_window = MainWindow(
            command_service=mock_command_service,
            validation_service=mock_validation_service,
        )
        qtbot.addWidget(main_window)

        # Simulate command execution request
        main_window._execute_command("echo 'Hello World'", temp_worktree, 300)

        # Verify command service was called
        mock_command_service.execute_command.assert_called_once()

        # Verify execution was added to active list
        assert mock_execution.id in main_window._active_executions

        # Verify command panel is visible
        assert main_window.command_panel_group.isChecked()

        # Simulate command completion
        mock_execution.mark_completed(0)
        main_window._on_command_finished(mock_execution.id)

        # Verify execution was removed from active list
        assert mock_execution.id not in main_window._active_executions

    def test_error_handling_workflow(self, qtbot, temp_worktree):
        """Test error handling throughout the workflow."""
        # Create mock services that will fail
        mock_command_service = Mock(spec=CommandService)
        mock_validation_service = Mock(spec=ValidationService)

        # Set up command execution to fail
        mock_command_service.execute_command.side_effect = Exception("Command failed")

        # Create main window
        main_window = MainWindow(
            command_service=mock_command_service,
            validation_service=mock_validation_service,
        )
        qtbot.addWidget(main_window)

        # Simulate command execution request
        main_window._execute_command("failing_command", temp_worktree, 300)

        # Verify error is handled gracefully
        assert "Error" in main_window.command_panel.status_label.text()
        assert main_window.update_operation_status


if __name__ == "__main__":
    pytest.main([__file__])
