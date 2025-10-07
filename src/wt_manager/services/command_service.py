"""Command execution service for Git Worktree Manager."""

import logging
import os
import signal
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any
from collections.abc import Callable

from PyQt6.QtCore import QThread, pyqtSignal

from ..models.command_execution import CommandExecution
from ..services.base import CommandServiceInterface, ValidationResult
from ..services.validation_service import ValidationService
from ..services.command_manager import get_command_manager


class CommandExecutionWorker(QThread):
    """
    Worker thread for executing commands asynchronously.

    This worker runs in a separate thread to prevent blocking the UI
    and provides real-time output streaming through Qt signals.
    """

    # Signals for communicating with the main thread
    output_received = pyqtSignal(str, str)  # execution_id, output_data
    error_received = pyqtSignal(str, str)  # execution_id, error_data
    execution_finished = pyqtSignal(str, int)  # execution_id, exit_code
    execution_started = pyqtSignal(str, int)  # execution_id, process_id

    def __init__(self, execution: CommandExecution, working_directory: str):
        """
        Initialize the command execution worker.

        Args:
            execution: CommandExecution instance to track the command
            working_directory: Directory where the command should be executed
        """
        super().__init__()
        self.execution = execution
        self.working_directory = working_directory
        self.process: subprocess.Popen | None = None
        self._cancelled = False
        self._logger = logging.getLogger(__name__)

    def run(self):
        """Execute the command in the worker thread."""
        try:
            self._logger.info(f"Starting command execution: {self.execution.command}")

            # Mark execution as started
            self.execution.mark_started()

            # Start the process
            self.process = subprocess.Popen(
                self.execution.command,
                shell=True,
                cwd=self.working_directory,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
                universal_newlines=True,
                preexec_fn=os.setsid
                if os.name != "nt"
                else None,  # Create process group on Unix
            )

            # Update execution with process ID
            self.execution.process_id = self.process.pid
            self.execution_started.emit(self.execution.id, self.process.pid)

            # Start threads for reading stdout and stderr
            stdout_thread = threading.Thread(
                target=self._read_stream,
                args=(self.process.stdout, "stdout"),
                daemon=True,
            )
            stderr_thread = threading.Thread(
                target=self._read_stream,
                args=(self.process.stderr, "stderr"),
                daemon=True,
            )

            stdout_thread.start()
            stderr_thread.start()

            # Wait for process completion or timeout
            self._wait_for_completion()

            # Wait for stream reading threads to finish
            stdout_thread.join(timeout=1.0)
            stderr_thread.join(timeout=1.0)

            # Get final exit code
            exit_code = self.process.returncode if self.process else -1

            if self._cancelled:
                self.execution.mark_cancelled()
            elif self.execution.is_timed_out():
                self.execution.mark_timeout()
            else:
                self.execution.mark_completed(exit_code)

            self.execution_finished.emit(self.execution.id, exit_code)

            self._logger.info(
                f"Command execution finished: {self.execution.command} "
                f"(exit code: {exit_code}, status: {self.execution.status.value})"
            )

        except Exception as e:
            self._logger.error(f"Error during command execution: {e}")
            self.execution.mark_completed(-1)
            self.execution_finished.emit(self.execution.id, -1)

    def _read_stream(self, stream, stream_type: str):
        """
        Read from stdout or stderr stream and emit signals.

        Args:
            stream: The stream to read from (stdout or stderr)
            stream_type: Type of stream ('stdout' or 'stderr')
        """
        try:
            while True:
                if self._cancelled or not self.process:
                    break

                line = stream.readline()
                if not line:
                    break

                # Append to execution buffer
                if stream_type == "stdout":
                    self.execution.append_stdout(line)
                    self.output_received.emit(self.execution.id, line)
                else:
                    self.execution.append_stderr(line)
                    self.error_received.emit(self.execution.id, line)

        except Exception as e:
            self._logger.error(f"Error reading {stream_type}: {e}")

    def _wait_for_completion(self):
        """Wait for process completion with timeout checking."""
        poll_interval = 0.1  # Check every 100ms

        while self.process and self.process.poll() is None:
            if self._cancelled:
                self._terminate_process()
                break

            if self.execution.is_timed_out():
                self._logger.warning(f"Command timed out: {self.execution.command}")
                self._terminate_process()
                break

            time.sleep(poll_interval)

    def _terminate_process(self):
        """Terminate the running process."""
        if not self.process:
            return

        try:
            if os.name == "nt":
                # Windows
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
            else:
                # Unix-like systems
                # Send SIGTERM to the process group
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Force kill if SIGTERM didn't work
                    os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)

        except (ProcessLookupError, OSError) as e:
            # Process already terminated
            self._logger.debug(f"Process already terminated: {e}")

    def cancel(self):
        """Cancel the command execution."""
        self._cancelled = True
        self._terminate_process()


class CommandService(CommandServiceInterface):
    """
    Service for executing user commands within worktree contexts.

    This service provides:
    - Command execution in specific worktree directories
    - Real-time stdout/stderr capture and streaming
    - Command cancellation and timeout handling
    - Command history and state management
    - Command validation and security checks
    """

    # Note: Signals will be created dynamically on the internal QObject

    def __init__(self, validation_service: ValidationService | None = None):
        """
        Initialize the command service.

        Args:
            validation_service: Optional validation service for command safety checks
        """
        super().__init__()

        self._validation_service = validation_service or ValidationService()
        self._active_executions: dict[str, CommandExecutionWorker] = {}
        self._command_manager = None
        self._logger = logging.getLogger(__name__)

        # Default timeout for commands (5 minutes)
        self.default_timeout = 300

        # Maximum concurrent executions
        self.max_concurrent_executions = 5

        # Callback functions for events (can be set by UI)
        self.on_command_started: Callable[[str], None] | None = None
        self.on_command_finished: Callable[[str], None] | None = None
        self.on_command_output: Callable[[str, str], None] | None = None
        self.on_command_error: Callable[[str, str], None] | None = None

    def _do_initialize(self) -> None:
        """Perform service-specific initialization."""
        self._validation_service.initialize()
        self._command_manager = get_command_manager()
        self._command_manager.initialize()
        self._logger.info("CommandService initialized")

    def execute_command(
        self, command: str, worktree_path: str, timeout_seconds: int | None = None
    ) -> CommandExecution:
        """
        Execute a command in the specified worktree directory.

        Args:
            command: Command string to execute
            worktree_path: Path to the worktree where command should be executed
            timeout_seconds: Optional timeout in seconds (uses default if None)

        Returns:
            CommandExecution: Execution instance for tracking the command

        Raises:
            ValueError: If command validation fails
            RuntimeError: If maximum concurrent executions exceeded
        """
        # Validate command safety
        validation_result = self.validate_command(command)
        if not validation_result.is_valid:
            raise ValueError(f"Command validation failed: {validation_result.message}")

        # Validate worktree path exists and is accessible
        worktree_path_obj = Path(worktree_path)
        if not worktree_path_obj.exists():
            raise ValueError(f"Worktree path does not exist: {worktree_path}")
        if not worktree_path_obj.is_dir():
            raise ValueError(f"Worktree path is not a directory: {worktree_path}")

        # Check concurrent execution limit
        if len(self._active_executions) >= self.max_concurrent_executions:
            raise RuntimeError(
                f"Maximum concurrent executions ({self.max_concurrent_executions}) exceeded"
            )

        # Create execution instance
        execution = CommandExecution(
            id=str(uuid.uuid4()),
            command=command,
            worktree_path=worktree_path,
            start_time=None,  # Will be set when execution starts
            timeout_seconds=timeout_seconds or self.default_timeout,
        )

        # Create and start worker thread
        worker = CommandExecutionWorker(execution, worktree_path)

        # Connect worker signals
        worker.output_received.connect(self._on_output_received)
        worker.error_received.connect(self._on_error_received)
        worker.execution_finished.connect(self._on_execution_finished)
        worker.execution_started.connect(self._on_execution_started)

        # Store active execution
        self._active_executions[execution.id] = worker

        # Register with command manager
        self._command_manager.register_execution(execution)

        # Start execution
        worker.start()

        self._logger.info(f"Started command execution: {command} in {worktree_path}")

        return execution

    def cancel_command(self, execution_id: str) -> bool:
        """
        Cancel a running command execution.

        Args:
            execution_id: ID of the execution to cancel

        Returns:
            bool: True if cancellation was initiated, False if execution not found
        """
        worker = self._active_executions.get(execution_id)
        if not worker:
            self._logger.warning(f"Cannot cancel execution {execution_id}: not found")
            return False

        worker.cancel()
        self._logger.info(f"Cancellation requested for execution: {execution_id}")
        return True

    def get_command_history(
        self, worktree_path: str | None = None, limit: int = 50
    ) -> list[CommandExecution]:
        """
        Get command execution history.

        Args:
            worktree_path: Optional worktree path to filter history (None for global)
            limit: Maximum number of executions to return

        Returns:
            List[CommandExecution]: List of command executions
        """
        if worktree_path:
            return self._command_manager.get_worktree_history(worktree_path, limit)
        else:
            return self._command_manager.get_global_history(limit)

    def get_running_executions(self) -> list[CommandExecution]:
        """
        Get all currently running command executions.

        Returns:
            List[CommandExecution]: List of running executions
        """
        return self._command_manager.get_active_executions()

    def get_execution_by_id(self, execution_id: str) -> CommandExecution | None:
        """
        Get a command execution by its ID.

        Args:
            execution_id: ID of the execution to find

        Returns:
            Optional[CommandExecution]: Execution if found, None otherwise
        """
        return self._command_manager.get_execution(execution_id)

    def validate_command(self, command: str) -> ValidationResult:
        """
        Validate a command for safety and correctness.

        Args:
            command: Command string to validate

        Returns:
            ValidationResult: Result of the validation
        """
        return self._validation_service.validate_command_safety(command)

    def get_execution_statistics(self) -> dict[str, Any]:
        """
        Get statistics about command executions.

        Returns:
            Dict[str, Any]: Statistics including counts, success rates, etc.
        """
        stats = self._command_manager.get_execution_statistics()
        stats.update(
            {
                "max_concurrent": self.max_concurrent_executions,
                "default_timeout": self.default_timeout,
            }
        )
        return stats

    def clear_history(self, worktree_path: str | None = None) -> None:
        """
        Clear command execution history.

        Args:
            worktree_path: Optional worktree path to clear (None for global)
        """
        self._command_manager.clear_history(worktree_path)
        self._logger.info(f"Cleared command history for: {worktree_path or 'all'}")

    def set_default_timeout(self, timeout_seconds: int) -> None:
        """
        Set the default timeout for command executions.

        Args:
            timeout_seconds: Default timeout in seconds
        """
        if timeout_seconds <= 0:
            raise ValueError("Timeout must be positive")

        self.default_timeout = timeout_seconds
        self._logger.info(f"Set default command timeout to {timeout_seconds} seconds")

    def set_max_concurrent_executions(self, max_concurrent: int) -> None:
        """
        Set the maximum number of concurrent command executions.

        Args:
            max_concurrent: Maximum number of concurrent executions
        """
        if max_concurrent <= 0:
            raise ValueError("Max concurrent executions must be positive")

        self.max_concurrent_executions = max_concurrent
        self._logger.info(f"Set max concurrent executions to {max_concurrent}")

    def _update_execution_status(self, execution: CommandExecution) -> None:
        """Update execution status in command manager."""
        self._command_manager.update_execution_status(execution)

    def _on_execution_started(self, execution_id: str, process_id: int) -> None:
        """Handle execution started signal."""
        if self.on_command_started:
            self.on_command_started(execution_id)
        self._logger.debug(f"Execution started: {execution_id} (PID: {process_id})")

    def _on_output_received(self, execution_id: str, output: str) -> None:
        """Handle output received signal."""
        if self.on_command_output:
            self.on_command_output(execution_id, output)

    def _on_error_received(self, execution_id: str, error: str) -> None:
        """Handle error received signal."""
        if self.on_command_error:
            self.on_command_error(execution_id, error)

    def _on_execution_finished(self, execution_id: str, exit_code: int) -> None:
        """Handle execution finished signal."""
        # Remove from active executions
        worker = self._active_executions.pop(execution_id, None)
        if worker:
            # Update execution status in command manager
            self._update_execution_status(worker.execution)

            # Clean up worker thread
            worker.quit()
            worker.wait(5000)  # Wait up to 5 seconds for thread to finish

            if self.on_command_finished:
                self.on_command_finished(execution_id)
            self._logger.debug(
                f"Execution finished: {execution_id} (exit code: {exit_code})"
            )

    def cleanup(self) -> None:
        """Clean up resources and cancel all running executions."""
        self._logger.info("Cleaning up CommandService...")

        # Cancel all active executions
        for execution_id in list(self._active_executions.keys()):
            self.cancel_command(execution_id)

        # Wait for all workers to finish
        for worker in list(self._active_executions.values()):
            try:
                if worker and not worker.isFinished():
                    worker.quit()
                    worker.wait(5000)
            except RuntimeError:
                # Worker already deleted, ignore
                pass

        self._active_executions.clear()
        self._logger.info("CommandService cleanup completed")

    def __del__(self):
        """Destructor to ensure cleanup."""
        self.cleanup()
