"""Unit tests for command execution manager."""

import tempfile
import threading
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from wt_manager.models.command_execution import CommandExecution, CommandStatus
from wt_manager.services.command_manager import (
    CommandExecutionState,
    CommandManager,
    get_command_manager,
    initialize_command_manager,
)


class TestCommandExecutionState:
    """Test cases for CommandExecutionState."""

    def setup_method(self):
        """Set up test fixtures."""
        self.state = CommandExecutionState()
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initialization(self):
        """Test state initialization."""
        assert len(self.state._active_executions) == 0
        assert len(self.state._execution_history) == 0
        assert len(self.state._global_history) == 0

    def test_add_execution(self):
        """Test adding executions to state."""
        execution = CommandExecution(
            id="test-1",
            command="echo 'test'",
            worktree_path=self.temp_dir,
            start_time=datetime.now(),
        )
        execution.mark_started()

        self.state.add_execution(execution)

        # Should be in active executions
        assert execution.id in self.state._active_executions

        # Should be in global history
        global_history = self.state.get_global_history()
        assert len(global_history) == 1
        assert global_history[0].id == execution.id

        # Should be in worktree history
        worktree_history = self.state.get_executions_for_worktree(self.temp_dir)
        assert len(worktree_history) == 1
        assert worktree_history[0].id == execution.id

    def test_update_execution(self):
        """Test updating execution state."""
        execution = CommandExecution(
            id="test-1",
            command="echo 'test'",
            worktree_path=self.temp_dir,
            start_time=datetime.now(),
        )
        execution.mark_started()

        self.state.add_execution(execution)
        assert execution.id in self.state._active_executions

        # Mark as completed
        execution.mark_completed(0)
        self.state.update_execution(execution)

        # Should no longer be in active executions
        assert execution.id not in self.state._active_executions

        # Should still be in history
        assert self.state.get_execution(execution.id) is not None

    def test_get_active_executions(self):
        """Test getting active executions."""
        # Add running execution
        running_exec = CommandExecution(
            id="running-1",
            command="sleep 10",
            worktree_path=self.temp_dir,
            start_time=datetime.now(),
        )
        running_exec.mark_started()

        # Add completed execution
        completed_exec = CommandExecution(
            id="completed-1",
            command="echo 'done'",
            worktree_path=self.temp_dir,
            start_time=datetime.now(),
        )
        completed_exec.mark_started()
        completed_exec.mark_completed(0)

        self.state.add_execution(running_exec)
        self.state.add_execution(completed_exec)
        self.state.update_execution(completed_exec)

        active = self.state.get_active_executions()
        assert len(active) == 1
        assert active[0].id == running_exec.id

    def test_get_statistics(self):
        """Test getting execution statistics."""
        # Add some executions
        for i in range(5):
            execution = CommandExecution(
                id=f"test-{i}",
                command=f"echo 'test {i}'",
                worktree_path=self.temp_dir,
                start_time=datetime.now(),
            )
            execution.mark_started()

            if i < 3:
                execution.mark_completed(0)  # Successful
            else:
                execution.mark_completed(1)  # Failed

            self.state.add_execution(execution)
            if execution.is_finished():
                self.state.update_execution(execution)

        stats = self.state.get_statistics()

        assert stats["total_executions"] == 5
        assert stats["successful_executions"] == 3
        assert stats["failed_executions"] == 2
        assert stats["active_executions"] == 0
        assert stats["success_rate"] == 60.0

    def test_cleanup_finished_executions(self):
        """Test cleanup of old executions."""
        # Add old execution
        old_execution = CommandExecution(
            id="old-1",
            command="echo 'old'",
            worktree_path=self.temp_dir,
            start_time=datetime.now() - timedelta(hours=25),
        )
        old_execution.mark_completed(0)

        # Add recent execution
        recent_execution = CommandExecution(
            id="recent-1",
            command="echo 'recent'",
            worktree_path=self.temp_dir,
            start_time=datetime.now(),
        )
        recent_execution.mark_completed(0)

        self.state.add_execution(old_execution)
        self.state.add_execution(recent_execution)

        # Cleanup executions older than 24 hours
        cleaned_count = self.state.cleanup_finished_executions(24)

        assert cleaned_count == 1

        # Recent execution should still be there
        assert self.state.get_execution(recent_execution.id) is not None

        # Old execution should be gone
        assert self.state.get_execution(old_execution.id) is None

    def test_clear_history(self):
        """Test clearing execution history."""
        execution1 = CommandExecution(
            id="test-1",
            command="echo 'test1'",
            worktree_path=self.temp_dir,
            start_time=datetime.now(),
        )

        execution2 = CommandExecution(
            id="test-2",
            command="echo 'test2'",
            worktree_path="/other/path",
            start_time=datetime.now(),
        )

        self.state.add_execution(execution1)
        self.state.add_execution(execution2)

        # Clear specific worktree history
        self.state.clear_history(self.temp_dir)

        assert len(self.state.get_executions_for_worktree(self.temp_dir)) == 0
        assert len(self.state.get_executions_for_worktree("/other/path")) == 1

        # Clear all history
        self.state.clear_history()

        assert len(self.state.get_global_history()) == 0
        assert len(self.state._execution_history) == 0

    def test_state_persistence(self):
        """Test state persistence to file."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            state_file = Path(f.name)

        try:
            # Initialize with persistence
            self.state._state_file = state_file

            # Add some executions
            execution = CommandExecution(
                id="persist-test",
                command="echo 'persist'",
                worktree_path=self.temp_dir,
                start_time=datetime.now(),
            )
            execution.mark_completed(0)

            self.state.add_execution(execution)

            # Save state
            self.state.save_state()

            assert state_file.exists()

            # Load state in new instance
            new_state = CommandExecutionState()
            new_state._state_file = state_file
            new_state._load_state()

            # Verify loaded state
            loaded_execution = new_state.get_execution("persist-test")
            assert loaded_execution is not None
            assert loaded_execution.command == "echo 'persist'"

        finally:
            if state_file.exists():
                state_file.unlink()

    def test_thread_safety(self):
        """Test thread safety of state operations."""
        threads = []

        def add_executions(start_id):
            for i in range(10):
                execution = CommandExecution(
                    id=f"thread-{start_id}-{i}",
                    command=f"echo 'thread {start_id} exec {i}'",
                    worktree_path=self.temp_dir,
                    start_time=datetime.now(),
                )
                execution.mark_completed(0)
                self.state.add_execution(execution)

        # Start multiple threads
        for i in range(10):
            thread = threading.Thread(target=add_executions, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify all executions were added
        global_history = self.state.get_global_history(200)
        assert len(global_history) == 100


class TestCommandManager:
    """Test cases for CommandManager."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = CommandManager()
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        if self.manager._initialized:
            self.manager.shutdown()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initialization(self):
        """Test manager initialization."""
        assert not self.manager._initialized

        self.manager.initialize(persist_state=False)

        assert self.manager._initialized

    def test_register_execution(self):
        """Test registering executions."""
        self.manager.initialize(persist_state=False)

        execution = CommandExecution(
            id="manager-test-1",
            command="echo 'manager test'",
            worktree_path=self.temp_dir,
            start_time=datetime.now(),
        )

        self.manager.register_execution(execution)

        retrieved = self.manager.get_execution(execution.id)
        assert retrieved is not None
        assert retrieved.id == execution.id

    def test_update_execution_status(self):
        """Test updating execution status."""
        self.manager.initialize(persist_state=False)

        execution = CommandExecution(
            id="status-test-1",
            command="echo 'status test'",
            worktree_path=self.temp_dir,
            start_time=datetime.now(),
        )
        execution.mark_started()

        self.manager.register_execution(execution)

        # Update to completed
        execution.mark_completed(0)
        self.manager.update_execution_status(execution)

        # Verify update
        retrieved = self.manager.get_execution(execution.id)
        assert retrieved.status == CommandStatus.COMPLETED

    def test_get_active_executions(self):
        """Test getting active executions."""
        self.manager.initialize(persist_state=False)

        # Add running execution
        running_exec = CommandExecution(
            id="active-1",
            command="sleep 10",
            worktree_path=self.temp_dir,
            start_time=datetime.now(),
        )
        running_exec.mark_started()

        self.manager.register_execution(running_exec)

        active = self.manager.get_active_executions()
        assert len(active) == 1
        assert active[0].id == running_exec.id

    def test_get_worktree_history(self):
        """Test getting worktree-specific history."""
        self.manager.initialize(persist_state=False)

        # Add executions for different worktrees
        exec1 = CommandExecution(
            id="wt1-1",
            command="echo 'worktree1'",
            worktree_path=self.temp_dir,
            start_time=datetime.now(),
        )

        exec2 = CommandExecution(
            id="wt2-1",
            command="echo 'worktree2'",
            worktree_path="/other/worktree",
            start_time=datetime.now(),
        )

        self.manager.register_execution(exec1)
        self.manager.register_execution(exec2)

        # Get worktree-specific history
        wt1_history = self.manager.get_worktree_history(self.temp_dir)
        assert len(wt1_history) == 1
        assert wt1_history[0].id == exec1.id

        wt2_history = self.manager.get_worktree_history("/other/worktree")
        assert len(wt2_history) == 1
        assert wt2_history[0].id == exec2.id

    def test_get_global_history(self):
        """Test getting global history."""
        self.manager.initialize(persist_state=False)

        # Add multiple executions
        for i in range(5):
            execution = CommandExecution(
                id=f"global-{i}",
                command=f"echo 'global {i}'",
                worktree_path=self.temp_dir,
                start_time=datetime.now(),
            )
            self.manager.register_execution(execution)

        global_history = self.manager.get_global_history()
        assert len(global_history) == 5

    def test_get_execution_statistics(self):
        """Test getting execution statistics."""
        self.manager.initialize(persist_state=False)

        # Add executions with different statuses
        for i in range(3):
            execution = CommandExecution(
                id=f"stats-{i}",
                command=f"echo 'stats {i}'",
                worktree_path=self.temp_dir,
                start_time=datetime.now(),
            )
            execution.mark_started()
            execution.mark_completed(0 if i < 2 else 1)  # 2 success, 1 failure

            self.manager.register_execution(execution)
            self.manager.update_execution_status(execution)

        stats = self.manager.get_execution_statistics()

        assert stats["total_executions"] == 3
        assert stats["successful_executions"] == 2
        assert stats["failed_executions"] == 1

    def test_get_executions_by_status(self):
        """Test filtering executions by status."""
        self.manager.initialize(persist_state=False)

        # Add executions with different statuses
        completed_exec = CommandExecution(
            id="completed-1",
            command="echo 'completed'",
            worktree_path=self.temp_dir,
            start_time=datetime.now(),
        )
        completed_exec.mark_completed(0)

        failed_exec = CommandExecution(
            id="failed-1",
            command="echo 'failed'",
            worktree_path=self.temp_dir,
            start_time=datetime.now(),
        )
        failed_exec.mark_completed(1)

        self.manager.register_execution(completed_exec)
        self.manager.register_execution(failed_exec)

        # Filter by status
        completed = self.manager.get_executions_by_status(CommandStatus.COMPLETED)
        failed = self.manager.get_executions_by_status(CommandStatus.FAILED)

        assert len(completed) == 1
        assert completed[0].id == completed_exec.id

        assert len(failed) == 1
        assert failed[0].id == failed_exec.id

    def test_get_executions_by_command(self):
        """Test filtering executions by command pattern."""
        self.manager.initialize(persist_state=False)

        # Add executions with different commands
        npm_exec = CommandExecution(
            id="npm-1",
            command="npm test",
            worktree_path=self.temp_dir,
            start_time=datetime.now(),
        )

        git_exec = CommandExecution(
            id="git-1",
            command="git status",
            worktree_path=self.temp_dir,
            start_time=datetime.now(),
        )

        self.manager.register_execution(npm_exec)
        self.manager.register_execution(git_exec)

        # Filter by command pattern
        npm_executions = self.manager.get_executions_by_command("npm")
        git_executions = self.manager.get_executions_by_command("git")

        assert len(npm_executions) == 1
        assert npm_executions[0].id == npm_exec.id

        assert len(git_executions) == 1
        assert git_executions[0].id == git_exec.id

    def test_cleanup_old_executions(self):
        """Test cleanup of old executions."""
        self.manager.initialize(persist_state=False)

        # Add old execution
        old_exec = CommandExecution(
            id="old-cleanup",
            command="echo 'old'",
            worktree_path=self.temp_dir,
            start_time=datetime.now() - timedelta(hours=25),
        )
        old_exec.mark_completed(0)

        self.manager.register_execution(old_exec)

        # Cleanup
        cleaned_count = self.manager.cleanup_old_executions(24)

        assert cleaned_count == 1
        assert self.manager.get_execution(old_exec.id) is None

    def test_clear_history(self):
        """Test clearing history."""
        self.manager.initialize(persist_state=False)

        execution = CommandExecution(
            id="clear-test",
            command="echo 'clear'",
            worktree_path=self.temp_dir,
            start_time=datetime.now(),
        )

        self.manager.register_execution(execution)

        # Clear all history
        self.manager.clear_history()

        assert len(self.manager.get_global_history()) == 0

    def test_configuration(self):
        """Test setting configuration."""
        self.manager.initialize(persist_state=False)

        self.manager.set_configuration(
            auto_save_interval=600,
            max_history_per_worktree=200,
            cleanup_interval_hours=48,
        )

        assert self.manager._auto_save_interval == 600
        assert self.manager._max_history_per_worktree == 200
        assert self.manager._cleanup_interval_hours == 48

    def test_shutdown(self):
        """Test manager shutdown."""
        self.manager.initialize(persist_state=False)

        execution = CommandExecution(
            id="shutdown-test",
            command="echo 'shutdown'",
            worktree_path=self.temp_dir,
            start_time=datetime.now(),
        )

        self.manager.register_execution(execution)

        # Shutdown should save state
        with patch.object(self.manager._state, "save_state") as mock_save:
            self.manager.shutdown()
            mock_save.assert_called_once()

        assert not self.manager._initialized


class TestCommandManagerGlobal:
    """Test cases for global command manager functions."""

    def test_get_command_manager_singleton(self):
        """Test global command manager singleton."""
        manager1 = get_command_manager()
        manager2 = get_command_manager()

        assert manager1 is manager2

    def test_initialize_command_manager(self):
        """Test global command manager initialization."""
        manager = initialize_command_manager(persist_state=False)

        assert manager._initialized
        assert manager is get_command_manager()


if __name__ == "__main__":
    pytest.main([__file__])
