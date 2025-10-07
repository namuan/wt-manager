"""Unit tests for command execution service."""

import os
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from PyQt6.QtCore import QCoreApplication

from wt_manager.models.command_execution import CommandExecution, CommandStatus
from wt_manager.services.base import ValidationResult
from wt_manager.services.command_service import CommandService, CommandExecutionWorker
from wt_manager.services.validation_service import ValidationService


class TestCommandExecutionWorker:
    """Test cases for CommandExecutionWorker."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.execution = CommandExecution(
            id="test-exec-1",
            command="echo 'Hello World'",
            worktree_path=self.temp_dir,
            start_time=None,
            timeout_seconds=30,
        )

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_worker_initialization(self):
        """Test worker initialization."""
        worker = CommandExecutionWorker(self.execution, self.temp_dir)

        assert worker.execution == self.execution
        assert worker.working_directory == self.temp_dir
        assert worker.process is None
        assert not worker._cancelled

    @pytest.mark.skipif(os.name == "nt", reason="Unix-specific test")
    def test_simple_command_execution(self):
        """Test execution of a simple command."""
        app = QCoreApplication.instance()
        if not app:
            app = QCoreApplication([])

        worker = CommandExecutionWorker(self.execution, self.temp_dir)

        # Track signals
        started_signal = Mock()
        finished_signal = Mock()
        output_signal = Mock()

        worker.execution_started.connect(started_signal)
        worker.execution_finished.connect(finished_signal)
        worker.output_received.connect(output_signal)

        # Run worker
        worker.start()
        worker.wait(5000)  # Wait up to 5 seconds

        # Process Qt events to ensure signals are delivered
        app.processEvents()

        # Verify execution completed
        assert self.execution.is_finished()
        assert self.execution.exit_code == 0
        assert "Hello World" in self.execution.stdout

        # Verify signals were emitted
        started_signal.assert_called_once()
        finished_signal.assert_called_once()
        output_signal.assert_called()

    def test_command_cancellation(self):
        """Test command cancellation."""
        app = QCoreApplication.instance()
        if not app:
            app = QCoreApplication([])

        # Use a long-running command
        self.execution.command = "sleep 10"
        worker = CommandExecutionWorker(self.execution, self.temp_dir)

        # Start worker
        worker.start()

        # Wait a bit then cancel
        time.sleep(0.1)
        worker.cancel()

        # Wait for completion
        worker.wait(5000)

        # Process Qt events to ensure signals are delivered
        app.processEvents()

        # Verify cancellation
        assert self.execution.status == CommandStatus.CANCELLED

    def test_command_timeout(self):
        """Test command timeout handling."""
        app = QCoreApplication.instance()
        if not app:
            app = QCoreApplication([])

        # Set short timeout and long-running command
        self.execution.timeout_seconds = 1
        self.execution.command = "sleep 5"

        worker = CommandExecutionWorker(self.execution, self.temp_dir)

        # Start worker
        worker.start()
        worker.wait(3000)  # Wait up to 3 seconds

        # Process Qt events to ensure signals are delivered
        app.processEvents()

        # Verify timeout
        assert self.execution.status == CommandStatus.TIMEOUT

    def test_invalid_command(self):
        """Test handling of invalid commands."""
        app = QCoreApplication.instance()
        if not app:
            app = QCoreApplication([])

        self.execution.command = "nonexistent_command_12345"
        worker = CommandExecutionWorker(self.execution, self.temp_dir)

        # Start worker
        worker.start()
        worker.wait(5000)

        # Process Qt events to ensure signals are delivered
        app.processEvents()

        # Verify failure
        assert self.execution.status == CommandStatus.FAILED
        assert self.execution.exit_code != 0

    def test_stderr_capture(self):
        """Test stderr capture."""
        app = QCoreApplication.instance()
        if not app:
            app = QCoreApplication([])

        # Command that writes to stderr
        if os.name == "nt":
            self.execution.command = 'echo "Error message" 1>&2'
        else:
            self.execution.command = 'echo "Error message" >&2'

        worker = CommandExecutionWorker(self.execution, self.temp_dir)

        # Start worker
        worker.start()
        worker.wait(5000)

        # Process Qt events to ensure signals are delivered
        app.processEvents()

        # Verify stderr capture
        assert "Error message" in self.execution.stderr


class TestCommandService:
    """Test cases for CommandService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.validation_service = Mock(spec=ValidationService)
        self.service = CommandService(self.validation_service)

        # Mock validation to always pass
        self.validation_service.validate_command_safety.return_value = ValidationResult(
            is_valid=True, message="Command is safe"
        )
        self.validation_service.validate_worktree_path.return_value = ValidationResult(
            is_valid=True, message="Path is valid"
        )

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        self.service.cleanup()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_service_initialization(self):
        """Test service initialization."""
        assert not self.service.is_initialized()

        self.service.initialize()

        assert self.service.is_initialized()
        self.validation_service.initialize.assert_called_once()

    def test_execute_command_validation(self):
        """Test command execution with validation."""
        self.service.initialize()

        execution = self.service.execute_command("echo 'test'", self.temp_dir)

        assert execution is not None
        assert execution.command == "echo 'test'"
        assert execution.worktree_path == self.temp_dir

        # Verify validation was called
        self.validation_service.validate_command_safety.assert_called_with(
            "echo 'test'"
        )

    def test_execute_command_validation_failure(self):
        """Test command execution with validation failure."""
        self.service.initialize()

        # Mock validation failure
        self.validation_service.validate_command_safety.return_value = ValidationResult(
            is_valid=False, message="Dangerous command"
        )

        with pytest.raises(ValueError, match="Command validation failed"):
            self.service.execute_command("rm -rf /", self.temp_dir)

    def test_execute_command_path_validation_failure(self):
        """Test command execution with path validation failure."""
        self.service.initialize()

        # Mock path validation failure
        self.validation_service.validate_worktree_path.return_value = ValidationResult(
            is_valid=False, message="Invalid path"
        )

        with pytest.raises(ValueError, match="Worktree path does not exist"):
            self.service.execute_command("echo 'test'", "/invalid/path")

    def test_concurrent_execution_limit(self):
        """Test concurrent execution limit enforcement."""
        self.service.initialize()
        self.service.set_max_concurrent_executions(2)

        # Start two executions (should succeed)
        self.service.execute_command("sleep 1", self.temp_dir)
        self.service.execute_command("sleep 1", self.temp_dir)

        # Third execution should fail
        with pytest.raises(RuntimeError, match="Maximum concurrent executions"):
            self.service.execute_command("sleep 1", self.temp_dir)

    def test_cancel_command(self):
        """Test command cancellation."""
        self.service.initialize()

        execution = self.service.execute_command("sleep 5", self.temp_dir)

        # Cancel the command
        result = self.service.cancel_command(execution.id)
        assert result is True

        # Try to cancel non-existent command
        result = self.service.cancel_command("non-existent")
        assert result is False

    def test_get_command_history(self):
        """Test command history retrieval."""
        # Mock command manager before initialization
        with patch(
            "wt_manager.services.command_service.get_command_manager"
        ) as mock_manager:
            mock_manager_instance = Mock()
            mock_manager.return_value = mock_manager_instance

            self.service.initialize()

            # Test global history
            self.service.get_command_history()
            mock_manager_instance.get_global_history.assert_called_with(50)

            # Test worktree-specific history
            self.service.get_command_history(self.temp_dir, 25)
            mock_manager_instance.get_worktree_history.assert_called_with(
                self.temp_dir, 25
            )

    def test_get_running_executions(self):
        """Test getting running executions."""
        with patch(
            "wt_manager.services.command_service.get_command_manager"
        ) as mock_manager:
            mock_manager_instance = Mock()
            mock_manager.return_value = mock_manager_instance
            mock_manager_instance.get_active_executions.return_value = []

            self.service.initialize()

            result = self.service.get_running_executions()

            mock_manager_instance.get_active_executions.assert_called_once()
            assert result == []

    def test_get_execution_by_id(self):
        """Test getting execution by ID."""
        with patch(
            "wt_manager.services.command_service.get_command_manager"
        ) as mock_manager:
            mock_manager_instance = Mock()
            mock_manager.return_value = mock_manager_instance

            self.service.initialize()

            self.service.get_execution_by_id("test-id")

            mock_manager_instance.get_execution.assert_called_with("test-id")

    def test_validate_command(self):
        """Test command validation."""
        self.service.initialize()

        result = self.service.validate_command("echo 'test'")

        assert result.is_valid
        self.validation_service.validate_command_safety.assert_called_with(
            "echo 'test'"
        )

    def test_get_execution_statistics(self):
        """Test execution statistics retrieval."""
        with patch(
            "wt_manager.services.command_service.get_command_manager"
        ) as mock_manager:
            mock_manager_instance = Mock()
            mock_manager.return_value = mock_manager_instance
            mock_manager_instance.get_execution_statistics.return_value = {
                "total_executions": 10,
                "active_executions": 2,
            }

            self.service.initialize()

            stats = self.service.get_execution_statistics()

            assert "total_executions" in stats
            assert "max_concurrent" in stats
            assert "default_timeout" in stats

    def test_clear_history(self):
        """Test clearing command history."""
        with patch(
            "wt_manager.services.command_service.get_command_manager"
        ) as mock_manager:
            mock_manager_instance = Mock()
            mock_manager.return_value = mock_manager_instance

            self.service.initialize()

            # Clear all history
            self.service.clear_history()
            mock_manager_instance.clear_history.assert_called_with(None)

            # Clear worktree-specific history
            self.service.clear_history(self.temp_dir)
            mock_manager_instance.clear_history.assert_called_with(self.temp_dir)

    def test_set_default_timeout(self):
        """Test setting default timeout."""
        self.service.initialize()

        self.service.set_default_timeout(600)
        assert self.service.default_timeout == 600

        with pytest.raises(ValueError):
            self.service.set_default_timeout(-1)

    def test_set_max_concurrent_executions(self):
        """Test setting max concurrent executions."""
        self.service.initialize()

        self.service.set_max_concurrent_executions(10)
        assert self.service.max_concurrent_executions == 10

        with pytest.raises(ValueError):
            self.service.set_max_concurrent_executions(0)

    def test_cleanup(self):
        """Test service cleanup."""
        self.service.initialize()

        # Start an execution
        self.service.execute_command("sleep 1", self.temp_dir)

        # Cleanup should cancel all executions
        self.service.cleanup()

        # Verify no active executions
        assert len(self.service._active_executions) == 0


class TestCommandServiceIntegration:
    """Integration tests for CommandService with real command execution."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.service = CommandService()

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        self.service.cleanup()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @pytest.mark.skipif(os.name == "nt", reason="Unix-specific test")
    def test_real_command_execution(self):
        """Test real command execution end-to-end."""
        app = QCoreApplication.instance()
        if not app:
            app = QCoreApplication([])

        self.service.initialize()

        # Execute a simple command
        execution = self.service.execute_command(
            "echo 'Integration Test'", self.temp_dir
        )

        # Wait for completion with more aggressive event processing
        timeout = 10  # 10 seconds
        start_time = time.time()
        while execution.is_running() and (time.time() - start_time) < timeout:
            app.processEvents()  # Process events first
            time.sleep(0.01)  # Shorter sleep for more responsive event processing
            app.processEvents()  # Process events again

        # Final event processing
        for _ in range(10):  # Multiple rounds to ensure all signals are processed
            app.processEvents()
            time.sleep(0.01)

        # Debug output if still failing
        if not execution.is_finished():
            print(f"Execution status: {execution.status}")
            print(f"Exit code: {execution.exit_code}")
            print(f"Stdout: {execution.stdout}")
            print(f"Stderr: {execution.stderr}")

        # Verify results
        assert execution.is_finished()
        assert execution.is_successful()
        assert "Integration Test" in execution.stdout

    @pytest.mark.skipif(os.name == "nt", reason="Unix-specific test")
    def test_command_with_working_directory(self):
        """Test command execution in specific working directory."""
        app = QCoreApplication.instance()
        if not app:
            app = QCoreApplication([])

        self.service.initialize()

        # Create a test file in the temp directory
        test_file = Path(self.temp_dir) / "test.txt"
        test_file.write_text("test content")

        # Execute command to list files
        execution = self.service.execute_command("ls -la", self.temp_dir)

        # Wait for completion with more aggressive event processing
        timeout = 10
        start_time = time.time()
        while execution.is_running() and (time.time() - start_time) < timeout:
            app.processEvents()  # Process events first
            time.sleep(0.01)  # Shorter sleep for more responsive event processing
            app.processEvents()  # Process events again

        # Final event processing
        for _ in range(10):  # Multiple rounds to ensure all signals are processed
            app.processEvents()
            time.sleep(0.01)

        # Debug output if still failing
        if not execution.is_finished():
            print(f"Execution status: {execution.status}")
            print(f"Exit code: {execution.exit_code}")
            print(f"Stdout: {execution.stdout}")
            print(f"Stderr: {execution.stderr}")

        # Verify the file is listed
        assert execution.is_finished()
        assert execution.is_successful()
        assert "test.txt" in execution.stdout

    def test_command_validation_integration(self):
        """Test command validation integration."""
        self.service.initialize()

        # Test safe command
        result = self.service.validate_command("echo 'safe command'")
        assert result.is_valid

        # Test potentially dangerous command
        result = self.service.validate_command("rm -rf /")
        assert not result.is_valid

    def test_concurrent_execution_management(self):
        """Test concurrent execution management."""
        app = QCoreApplication.instance()
        if not app:
            app = QCoreApplication([])

        self.service.initialize()
        self.service.set_max_concurrent_executions(3)

        # Start multiple executions
        executions = []
        for i in range(3):
            exec = self.service.execute_command("sleep 0.5", self.temp_dir)
            executions.append(exec)

        # Verify all are running
        running = self.service.get_running_executions()
        assert len(running) <= 3

        # Wait for completion
        timeout = 10
        start_time = time.time()
        while (
            any(exec.is_running() for exec in executions)
            and (time.time() - start_time) < timeout
        ):
            time.sleep(0.1)
            app.processEvents()  # Process events during wait

        # Process Qt events to ensure signals are delivered
        app.processEvents()

        # Verify all completed
        for exec in executions:
            assert exec.is_finished()


if __name__ == "__main__":
    pytest.main([__file__])
