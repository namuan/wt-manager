"""Command execution data model for Git Worktree Manager."""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any


class CommandStatus(Enum):
    """Status enumeration for command execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class CommandExecution:
    """
    Represents a command execution with its status, output, and metadata.

    Attributes:
        id: Unique identifier for the command execution
        command: The command string that was executed
        worktree_path: Path to the worktree where command was executed
        start_time: Timestamp when command execution started
        end_time: Timestamp when command execution ended (None if still running)
        exit_code: Exit code returned by the command (None if still running)
        stdout: Standard output captured from the command
        stderr: Standard error output captured from the command
        status: Current status of the command execution
        timeout_seconds: Timeout value in seconds (None for no timeout)
        process_id: Process ID of the running command (None if not running)
    """

    id: str
    command: str
    worktree_path: str
    start_time: datetime
    end_time: datetime | None = None
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    status: CommandStatus = CommandStatus.PENDING
    timeout_seconds: int | None = None
    process_id: int | None = None

    def __post_init__(self):
        """Post-initialization validation and setup."""
        if not self.id:
            self.id = str(uuid.uuid4())

        # Ensure we have a valid start time
        if not self.start_time:
            self.start_time = datetime.now()

    def is_running(self) -> bool:
        """
        Check if the command is currently running.

        Returns:
            bool: True if command is running, False otherwise
        """
        return self.status == CommandStatus.RUNNING

    def is_finished(self) -> bool:
        """
        Check if the command has finished execution (completed, failed, cancelled, or timeout).

        Returns:
            bool: True if command has finished, False otherwise
        """
        return self.status in {
            CommandStatus.COMPLETED,
            CommandStatus.FAILED,
            CommandStatus.CANCELLED,
            CommandStatus.TIMEOUT,
        }

    def is_successful(self) -> bool:
        """
        Check if the command completed successfully.

        Returns:
            bool: True if command completed with exit code 0, False otherwise
        """
        return self.status == CommandStatus.COMPLETED and self.exit_code == 0

    def get_duration(self) -> timedelta | None:
        """
        Calculate the duration of command execution.

        Returns:
            Optional[timedelta]: Duration if command has ended, None if still running
        """
        if not self.end_time:
            if self.is_running():
                # Return current duration for running commands
                return datetime.now() - self.start_time
            return None

        return self.end_time - self.start_time

    def get_duration_display(self) -> str:
        """
        Get a human-readable duration display.

        Returns:
            str: Duration display string (e.g., "2.5s", "1m 30s", "running...")
        """
        duration = self.get_duration()
        if not duration:
            return "unknown"

        if self.is_running():
            suffix = " (running)"
        else:
            suffix = ""

        total_seconds = duration.total_seconds()

        if total_seconds < 1:
            return f"{total_seconds:.2f}s{suffix}"
        elif total_seconds < 60:
            return f"{total_seconds:.1f}s{suffix}"
        elif total_seconds < 3600:
            minutes = int(total_seconds // 60)
            seconds = int(total_seconds % 60)
            return f"{minutes}m {seconds}s{suffix}"
        else:
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            return f"{hours}h {minutes}m{suffix}"

    def get_formatted_output(self) -> str:
        """
        Get formatted output combining stdout and stderr.

        Returns:
            str: Formatted output with clear separation of stdout and stderr
        """
        output_parts = []

        if self.stdout.strip():
            output_parts.append("=== STDOUT ===")
            output_parts.append(self.stdout.rstrip())

        if self.stderr.strip():
            if output_parts:
                output_parts.append("")  # Add blank line separator
            output_parts.append("=== STDERR ===")
            output_parts.append(self.stderr.rstrip())

        if not output_parts:
            return "(no output)"

        return "\n".join(output_parts)

    def get_status_display(self) -> str:
        """
        Get a human-readable status display with additional context.

        Returns:
            str: Status display string with context
        """
        status_map = {
            CommandStatus.PENDING: "Pending",
            CommandStatus.RUNNING: "Running",
            CommandStatus.COMPLETED: "Completed",
            CommandStatus.FAILED: "Failed",
            CommandStatus.CANCELLED: "Cancelled",
            CommandStatus.TIMEOUT: "Timeout",
        }

        base_status = status_map.get(self.status, self.status.value)

        if self.is_finished() and self.exit_code is not None:
            return f"{base_status} (exit code: {self.exit_code})"

        return base_status

    def get_command_display(self, max_length: int = 50) -> str:
        """
        Get a truncated command display for UI purposes.

        Args:
            max_length: Maximum length of the command display

        Returns:
            str: Truncated command string
        """
        if len(self.command) <= max_length:
            return self.command

        return self.command[: max_length - 3] + "..."

    def append_stdout(self, data: str) -> None:
        """
        Append data to stdout buffer.

        Args:
            data: Data to append to stdout
        """
        self.stdout += data

    def append_stderr(self, data: str) -> None:
        """
        Append data to stderr buffer.

        Args:
            data: Data to append to stderr
        """
        self.stderr += data

    def mark_started(self, process_id: int | None = None) -> None:
        """
        Mark the command as started.

        Args:
            process_id: Optional process ID of the running command
        """
        self.status = CommandStatus.RUNNING
        self.process_id = process_id
        if not self.start_time:
            self.start_time = datetime.now()

    def mark_completed(self, exit_code: int) -> None:
        """
        Mark the command as completed.

        Args:
            exit_code: Exit code returned by the command
        """
        self.end_time = datetime.now()
        self.exit_code = exit_code
        self.process_id = None

        if exit_code == 0:
            self.status = CommandStatus.COMPLETED
        else:
            self.status = CommandStatus.FAILED

    def mark_cancelled(self) -> None:
        """Mark the command as cancelled."""
        self.end_time = datetime.now()
        self.status = CommandStatus.CANCELLED
        self.process_id = None

    def mark_timeout(self) -> None:
        """Mark the command as timed out."""
        self.end_time = datetime.now()
        self.status = CommandStatus.TIMEOUT
        self.process_id = None

    def is_timed_out(self) -> bool:
        """
        Check if the command has exceeded its timeout.

        Returns:
            bool: True if command has timed out, False otherwise
        """
        if not self.timeout_seconds or not self.is_running():
            return False

        duration = self.get_duration()
        if not duration:
            return False

        return duration.total_seconds() > self.timeout_seconds

    def get_worktree_name(self) -> str:
        """
        Get the worktree directory name for display purposes.

        Returns:
            str: Worktree directory name
        """
        from pathlib import Path

        return Path(self.worktree_path).name

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize the command execution to a dictionary.

        Returns:
            Dict[str, Any]: Serialized command execution data
        """
        return {
            "id": self.id,
            "command": self.command,
            "worktree_path": self.worktree_path,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "status": self.status.value,
            "timeout_seconds": self.timeout_seconds,
            "process_id": self.process_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CommandExecution":
        """
        Deserialize a command execution from a dictionary.

        Args:
            data: Dictionary containing command execution data

        Returns:
            CommandExecution: Deserialized command execution instance
        """
        end_time = None
        if data.get("end_time"):
            end_time = datetime.fromisoformat(data["end_time"])

        return cls(
            id=data["id"],
            command=data["command"],
            worktree_path=data["worktree_path"],
            start_time=datetime.fromisoformat(data["start_time"]),
            end_time=end_time,
            exit_code=data.get("exit_code"),
            stdout=data.get("stdout", ""),
            stderr=data.get("stderr", ""),
            status=CommandStatus(data["status"]),
            timeout_seconds=data.get("timeout_seconds"),
            process_id=data.get("process_id"),
        )

    def to_json(self) -> str:
        """
        Serialize the command execution to JSON string.

        Returns:
            str: JSON representation of the command execution
        """
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "CommandExecution":
        """
        Deserialize a command execution from JSON string.

        Args:
            json_str: JSON string containing command execution data

        Returns:
            CommandExecution: Deserialized command execution instance
        """
        data = json.loads(json_str)
        return cls.from_dict(data)

    def __eq__(self, other) -> bool:
        """Check equality based on command execution ID."""
        if not isinstance(other, CommandExecution):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        """Hash based on command execution ID."""
        return hash(self.id)

    def __str__(self) -> str:
        """String representation of the command execution."""
        return f"CommandExecution(command='{self.get_command_display()}', status={self.status.value})"

    def __repr__(self) -> str:
        """Detailed string representation of the command execution."""
        return (
            f"CommandExecution(id='{self.id}', command='{self.command}', "
            f"status={self.status.value}, worktree='{self.get_worktree_name()}')"
        )


@dataclass
class CommandHistory:
    """
    Manages command execution history for a specific worktree or globally.

    Attributes:
        worktree_path: Path to the worktree (None for global history)
        executions: List of command executions
        max_history_size: Maximum number of executions to keep in history
    """

    worktree_path: str | None = None
    executions: list[CommandExecution] = field(default_factory=list)
    max_history_size: int = 100

    def add_execution(self, execution: CommandExecution) -> None:
        """
        Add a command execution to the history.

        Args:
            execution: CommandExecution instance to add
        """
        # Add to the beginning of the list (most recent first)
        self.executions.insert(0, execution)

        # Trim history if it exceeds max size
        if len(self.executions) > self.max_history_size:
            self.executions = self.executions[: self.max_history_size]

    def get_recent_executions(self, limit: int = 10) -> list[CommandExecution]:
        """
        Get the most recent command executions.

        Args:
            limit: Maximum number of executions to return

        Returns:
            List[CommandExecution]: Most recent executions
        """
        return self.executions[:limit]

    def get_running_executions(self) -> list[CommandExecution]:
        """
        Get all currently running command executions.

        Returns:
            List[CommandExecution]: Currently running executions
        """
        return [exec for exec in self.executions if exec.is_running()]

    def get_execution_by_id(self, execution_id: str) -> CommandExecution | None:
        """
        Get a command execution by its ID.

        Args:
            execution_id: ID of the execution to find

        Returns:
            Optional[CommandExecution]: Execution if found, None otherwise
        """
        for execution in self.executions:
            if execution.id == execution_id:
                return execution
        return None

    def get_executions_by_command(self, command: str) -> list[CommandExecution]:
        """
        Get all executions for a specific command.

        Args:
            command: Command string to search for

        Returns:
            List[CommandExecution]: Executions matching the command
        """
        return [exec for exec in self.executions if exec.command == command]

    def get_successful_executions(self) -> list[CommandExecution]:
        """
        Get all successful command executions.

        Returns:
            List[CommandExecution]: Successful executions
        """
        return [exec for exec in self.executions if exec.is_successful()]

    def get_failed_executions(self) -> list[CommandExecution]:
        """
        Get all failed command executions.

        Returns:
            List[CommandExecution]: Failed executions
        """
        return [exec for exec in self.executions if exec.status == CommandStatus.FAILED]

    def clear_history(self) -> None:
        """Clear all command execution history."""
        self.executions.clear()

    def remove_execution(self, execution_id: str) -> bool:
        """
        Remove a specific execution from history.

        Args:
            execution_id: ID of the execution to remove

        Returns:
            bool: True if execution was found and removed, False otherwise
        """
        for i, execution in enumerate(self.executions):
            if execution.id == execution_id:
                del self.executions[i]
                return True
        return False

    def get_statistics(self) -> dict[str, Any]:
        """
        Get statistics about the command history.

        Returns:
            Dict[str, Any]: Statistics including counts by status, average duration, etc.
        """
        if not self.executions:
            return {
                "total_executions": 0,
                "successful": 0,
                "failed": 0,
                "cancelled": 0,
                "running": 0,
                "average_duration": None,
            }

        status_counts = {}
        durations = []

        for execution in self.executions:
            status = execution.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

            if execution.is_finished():
                duration = execution.get_duration()
                if duration:
                    durations.append(duration.total_seconds())

        avg_duration = sum(durations) / len(durations) if durations else None

        return {
            "total_executions": len(self.executions),
            "successful": status_counts.get("completed", 0),
            "failed": status_counts.get("failed", 0),
            "cancelled": status_counts.get("cancelled", 0),
            "running": status_counts.get("running", 0),
            "timeout": status_counts.get("timeout", 0),
            "average_duration": avg_duration,
        }

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize the command history to a dictionary.

        Returns:
            Dict[str, Any]: Serialized command history data
        """
        return {
            "worktree_path": self.worktree_path,
            "executions": [exec.to_dict() for exec in self.executions],
            "max_history_size": self.max_history_size,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CommandHistory":
        """
        Deserialize a command history from a dictionary.

        Args:
            data: Dictionary containing command history data

        Returns:
            CommandHistory: Deserialized command history instance
        """
        executions = [
            CommandExecution.from_dict(exec_data)
            for exec_data in data.get("executions", [])
        ]

        return cls(
            worktree_path=data.get("worktree_path"),
            executions=executions,
            max_history_size=data.get("max_history_size", 100),
        )

    def __len__(self) -> int:
        """Return the number of executions in history."""
        return len(self.executions)

    def __str__(self) -> str:
        """String representation of the command history."""
        worktree_name = (
            Path(self.worktree_path).name if self.worktree_path else "global"
        )
        return f"CommandHistory(worktree='{worktree_name}', executions={len(self.executions)})"

    def __repr__(self) -> str:
        """Detailed string representation of the command history."""
        return (
            f"CommandHistory(worktree_path='{self.worktree_path}', "
            f"executions={len(self.executions)}, max_size={self.max_history_size})"
        )
