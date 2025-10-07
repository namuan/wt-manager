"""Command execution manager for advanced state management and persistence."""

import json
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ..models.command_execution import CommandExecution, CommandHistory, CommandStatus
from ..services.base import ServiceError
from ..utils.path_manager import PathManager


class CommandExecutionState:
    """
    Manages the state of command executions across the application.

    This class provides thread-safe access to command execution state
    and handles persistence of command history.
    """

    def __init__(self):
        """Initialize the command execution state."""
        self._lock = threading.RLock()
        self._active_executions: dict[str, CommandExecution] = {}
        self._execution_history: dict[
            str, CommandHistory
        ] = {}  # worktree_path -> history
        self._global_history = CommandHistory()
        self._state_file: Path | None = None
        self._logger = logging.getLogger(__name__)

        # State tracking
        self._total_executions = 0
        self._successful_executions = 0
        self._failed_executions = 0

    def initialize(self, persist_state: bool = True) -> None:
        """
        Initialize the state manager.

        Args:
            persist_state: Whether to enable state persistence
        """
        if persist_state:
            try:
                config_dir = PathManager.get_config_dir()
                self._state_file = config_dir / "command_state.json"
                self._load_state()
            except Exception as e:
                self._logger.warning(f"Failed to initialize state persistence: {e}")

        self._logger.info("CommandExecutionState initialized")

    def add_execution(self, execution: CommandExecution) -> None:
        """
        Add a command execution to the state.

        Args:
            execution: CommandExecution to add
        """
        with self._lock:
            # Add to active executions if running
            if execution.is_running():
                self._active_executions[execution.id] = execution

            # Add to global history
            self._global_history.add_execution(execution)

            # Add to worktree-specific history
            worktree_path = execution.worktree_path
            if worktree_path not in self._execution_history:
                self._execution_history[worktree_path] = CommandHistory(worktree_path)

            self._execution_history[worktree_path].add_execution(execution)

            # Update statistics
            self._total_executions += 1

            self._logger.debug(f"Added execution to state: {execution.id}")

    def update_execution(self, execution: CommandExecution) -> None:
        """
        Update an existing execution in the state.

        Args:
            execution: Updated CommandExecution
        """
        with self._lock:
            # Check if this execution was previously active
            was_active = execution.id in self._active_executions

            # Update active executions
            if was_active:
                if execution.is_finished():
                    # Move from active to finished
                    self._active_executions.pop(execution.id, None)

                    # Update statistics
                    if execution.is_successful():
                        self._successful_executions += 1
                    else:
                        self._failed_executions += 1
                else:
                    # Update active execution
                    self._active_executions[execution.id] = execution
            elif execution.is_finished():
                # This is a finished execution that wasn't previously tracked as active
                # Update statistics directly
                if execution.is_successful():
                    self._successful_executions += 1
                else:
                    self._failed_executions += 1

            self._logger.debug(f"Updated execution state: {execution.id}")

    def get_execution(self, execution_id: str) -> CommandExecution | None:
        """
        Get an execution by ID.

        Args:
            execution_id: ID of the execution to retrieve

        Returns:
            Optional[CommandExecution]: Execution if found, None otherwise
        """
        with self._lock:
            # Check active executions first
            if execution_id in self._active_executions:
                return self._active_executions[execution_id]

            # Check global history
            return self._global_history.get_execution_by_id(execution_id)

    def get_active_executions(self) -> list[CommandExecution]:
        """
        Get all active (running) executions.

        Returns:
            List[CommandExecution]: List of active executions
        """
        with self._lock:
            return list(self._active_executions.values())

    def get_executions_for_worktree(
        self, worktree_path: str, limit: int = 50
    ) -> list[CommandExecution]:
        """
        Get executions for a specific worktree.

        Args:
            worktree_path: Path to the worktree
            limit: Maximum number of executions to return

        Returns:
            List[CommandExecution]: List of executions for the worktree
        """
        with self._lock:
            history = self._execution_history.get(worktree_path)
            if history:
                return history.get_recent_executions(limit)
            return []

    def get_global_history(self, limit: int = 100) -> list[CommandExecution]:
        """
        Get global execution history.

        Args:
            limit: Maximum number of executions to return

        Returns:
            List[CommandExecution]: List of executions from global history
        """
        with self._lock:
            return self._global_history.get_recent_executions(limit)

    def get_statistics(self) -> dict[str, Any]:
        """
        Get execution statistics.

        Returns:
            Dict[str, Any]: Statistics about executions
        """
        with self._lock:
            active_count = len(self._active_executions)
            success_rate = (
                (
                    self._successful_executions
                    / max(1, self._total_executions - active_count)
                )
                * 100
                if self._total_executions > active_count
                else 0
            )

            return {
                "total_executions": self._total_executions,
                "active_executions": active_count,
                "successful_executions": self._successful_executions,
                "failed_executions": self._failed_executions,
                "success_rate": round(success_rate, 2),
                "worktree_count": len(self._execution_history),
                "global_history_size": len(self._global_history),
            }

    def cleanup_finished_executions(self, older_than_hours: int = 24) -> int:
        """
        Clean up old finished executions from memory.

        Args:
            older_than_hours: Remove executions older than this many hours

        Returns:
            int: Number of executions cleaned up
        """
        cutoff_time = datetime.now() - timedelta(hours=older_than_hours)

        with self._lock:
            # Clean global history (this is the authoritative count)
            original_count = len(self._global_history.executions)
            self._global_history.executions = [
                exec
                for exec in self._global_history.executions
                if exec.start_time > cutoff_time or exec.is_running()
            ]
            cleaned_count = original_count - len(self._global_history.executions)

            # Clean worktree histories (don't count these separately)
            for history in self._execution_history.values():
                history.executions = [
                    exec
                    for exec in history.executions
                    if exec.start_time > cutoff_time or exec.is_running()
                ]

        if cleaned_count > 0:
            self._logger.info(f"Cleaned up {cleaned_count} old executions")

        return cleaned_count

    def clear_history(self, worktree_path: str | None = None) -> None:
        """
        Clear execution history.

        Args:
            worktree_path: Optional worktree path to clear (None for all)
        """
        with self._lock:
            if worktree_path:
                if worktree_path in self._execution_history:
                    self._execution_history[worktree_path].clear_history()
                    self._logger.info(f"Cleared history for worktree: {worktree_path}")
            else:
                self._global_history.clear_history()
                self._execution_history.clear()
                self._total_executions = 0
                self._successful_executions = 0
                self._failed_executions = 0
                self._logger.info("Cleared all execution history")

    def save_state(self) -> None:
        """Save the current state to disk."""
        if not self._state_file:
            return

        try:
            with self._lock:
                state_data = {
                    "timestamp": datetime.now().isoformat(),
                    "statistics": {
                        "total_executions": self._total_executions,
                        "successful_executions": self._successful_executions,
                        "failed_executions": self._failed_executions,
                    },
                    "global_history": self._global_history.to_dict(),
                    "worktree_histories": {
                        path: history.to_dict()
                        for path, history in self._execution_history.items()
                    },
                }

            # Ensure parent directory exists
            self._state_file.parent.mkdir(parents=True, exist_ok=True)

            # Write state to file
            with open(self._state_file, "w", encoding="utf-8") as f:
                json.dump(state_data, f, indent=2)

            self._logger.debug(f"Saved command state to {self._state_file}")

        except Exception as e:
            self._logger.error(f"Failed to save command state: {e}")

    def _load_state(self) -> None:
        """Load state from disk."""
        if not self._state_file or not self._state_file.exists():
            return

        try:
            with open(self._state_file, encoding="utf-8") as f:
                state_data = json.load(f)

            with self._lock:
                # Load statistics
                stats = state_data.get("statistics", {})
                self._total_executions = stats.get("total_executions", 0)
                self._successful_executions = stats.get("successful_executions", 0)
                self._failed_executions = stats.get("failed_executions", 0)

                # Load global history
                global_history_data = state_data.get("global_history", {})
                if global_history_data:
                    self._global_history = CommandHistory.from_dict(global_history_data)

                # Load worktree histories
                worktree_histories = state_data.get("worktree_histories", {})
                for path, history_data in worktree_histories.items():
                    self._execution_history[path] = CommandHistory.from_dict(
                        history_data
                    )

            self._logger.info(f"Loaded command state from {self._state_file}")

        except Exception as e:
            self._logger.error(f"Failed to load command state: {e}")


class CommandManager:
    """
    High-level manager for command execution state and operations.

    This class provides a unified interface for managing command executions,
    including state persistence, concurrent execution tracking, and history management.
    """

    def __init__(self):
        """Initialize the command manager."""
        self._state = CommandExecutionState()
        self._logger = logging.getLogger(__name__)
        self._initialized = False

        # Configuration
        self._auto_save_interval = 300  # 5 minutes
        self._max_history_per_worktree = 100
        self._cleanup_interval_hours = 24

    def initialize(self, persist_state: bool = True) -> None:
        """
        Initialize the command manager.

        Args:
            persist_state: Whether to enable state persistence
        """
        if self._initialized:
            return

        self._state.initialize(persist_state)
        self._initialized = True

        self._logger.info("CommandManager initialized")

    def register_execution(self, execution: CommandExecution) -> None:
        """
        Register a new command execution.

        Args:
            execution: CommandExecution to register
        """
        if not self._initialized:
            raise ServiceError("CommandManager not initialized")

        self._state.add_execution(execution)

        # Auto-save state periodically
        self._maybe_auto_save()

    def update_execution_status(self, execution: CommandExecution) -> None:
        """
        Update the status of an existing execution.

        Args:
            execution: Updated CommandExecution
        """
        if not self._initialized:
            raise ServiceError("CommandManager not initialized")

        self._state.update_execution(execution)

        # Auto-save on completion
        if execution.is_finished():
            self._maybe_auto_save()

    def get_execution(self, execution_id: str) -> CommandExecution | None:
        """
        Get an execution by ID.

        Args:
            execution_id: ID of the execution

        Returns:
            Optional[CommandExecution]: Execution if found, None otherwise
        """
        if not self._initialized:
            raise ServiceError("CommandManager not initialized")

        return self._state.get_execution(execution_id)

    def get_active_executions(self) -> list[CommandExecution]:
        """
        Get all currently active executions.

        Returns:
            List[CommandExecution]: List of active executions
        """
        if not self._initialized:
            raise ServiceError("CommandManager not initialized")

        return self._state.get_active_executions()

    def get_worktree_history(
        self, worktree_path: str, limit: int = 50
    ) -> list[CommandExecution]:
        """
        Get command history for a specific worktree.

        Args:
            worktree_path: Path to the worktree
            limit: Maximum number of executions to return

        Returns:
            List[CommandExecution]: List of executions for the worktree
        """
        if not self._initialized:
            raise ServiceError("CommandManager not initialized")

        return self._state.get_executions_for_worktree(worktree_path, limit)

    def get_global_history(self, limit: int = 100) -> list[CommandExecution]:
        """
        Get global command history.

        Args:
            limit: Maximum number of executions to return

        Returns:
            List[CommandExecution]: List of executions from global history
        """
        if not self._initialized:
            raise ServiceError("CommandManager not initialized")

        return self._state.get_global_history(limit)

    def get_execution_statistics(self) -> dict[str, Any]:
        """
        Get comprehensive execution statistics.

        Returns:
            Dict[str, Any]: Statistics about command executions
        """
        if not self._initialized:
            raise ServiceError("CommandManager not initialized")

        return self._state.get_statistics()

    def get_concurrent_execution_count(self) -> int:
        """
        Get the number of currently running executions.

        Returns:
            int: Number of concurrent executions
        """
        return len(self.get_active_executions())

    def get_executions_by_status(self, status: CommandStatus) -> list[CommandExecution]:
        """
        Get executions filtered by status.

        Args:
            status: CommandStatus to filter by

        Returns:
            List[CommandExecution]: List of executions with the specified status
        """
        if not self._initialized:
            raise ServiceError("CommandManager not initialized")

        all_executions = self._state.get_global_history(1000)  # Get more for filtering
        return [exec for exec in all_executions if exec.status == status]

    def get_executions_by_command(self, command_pattern: str) -> list[CommandExecution]:
        """
        Get executions that match a command pattern.

        Args:
            command_pattern: Pattern to match against command strings

        Returns:
            List[CommandExecution]: List of matching executions
        """
        if not self._initialized:
            raise ServiceError("CommandManager not initialized")

        all_executions = self._state.get_global_history(1000)
        return [
            exec
            for exec in all_executions
            if command_pattern.lower() in exec.command.lower()
        ]

    def cleanup_old_executions(self, older_than_hours: int = 24) -> int:
        """
        Clean up old finished executions.

        Args:
            older_than_hours: Remove executions older than this many hours

        Returns:
            int: Number of executions cleaned up
        """
        if not self._initialized:
            raise ServiceError("CommandManager not initialized")

        return self._state.cleanup_finished_executions(older_than_hours)

    def clear_history(self, worktree_path: str | None = None) -> None:
        """
        Clear execution history.

        Args:
            worktree_path: Optional worktree path to clear (None for all)
        """
        if not self._initialized:
            raise ServiceError("CommandManager not initialized")

        self._state.clear_history(worktree_path)
        self._state.save_state()

    def save_state(self) -> None:
        """Manually save the current state."""
        if not self._initialized:
            raise ServiceError("CommandManager not initialized")

        self._state.save_state()

    def set_configuration(
        self,
        auto_save_interval: int | None = None,
        max_history_per_worktree: int | None = None,
        cleanup_interval_hours: int | None = None,
    ) -> None:
        """
        Set configuration parameters.

        Args:
            auto_save_interval: Auto-save interval in seconds
            max_history_per_worktree: Maximum history entries per worktree
            cleanup_interval_hours: Cleanup interval in hours
        """
        if auto_save_interval is not None:
            self._auto_save_interval = auto_save_interval

        if max_history_per_worktree is not None:
            self._max_history_per_worktree = max_history_per_worktree

        if cleanup_interval_hours is not None:
            self._cleanup_interval_hours = cleanup_interval_hours

        self._logger.info("Updated CommandManager configuration")

    def _maybe_auto_save(self) -> None:
        """Auto-save state if conditions are met."""
        # Simple auto-save logic - could be enhanced with timing
        try:
            self._state.save_state()
        except Exception as e:
            self._logger.error(f"Auto-save failed: {e}")

    def shutdown(self) -> None:
        """Shutdown the command manager and save state."""
        if not self._initialized:
            return

        try:
            self._state.save_state()
            self._logger.info("CommandManager shutdown completed")
        except Exception as e:
            self._logger.error(f"Error during CommandManager shutdown: {e}")

        self._initialized = False


# Global instance for application-wide use
_command_manager_instance: CommandManager | None = None


def get_command_manager() -> CommandManager:
    """
    Get the global CommandManager instance.

    Returns:
        CommandManager: Global command manager instance
    """
    global _command_manager_instance

    if _command_manager_instance is None:
        _command_manager_instance = CommandManager()

    return _command_manager_instance


def initialize_command_manager(persist_state: bool = True) -> CommandManager:
    """
    Initialize the global CommandManager instance.

    Args:
        persist_state: Whether to enable state persistence

    Returns:
        CommandManager: Initialized command manager instance
    """
    manager = get_command_manager()
    manager.initialize(persist_state)
    return manager
