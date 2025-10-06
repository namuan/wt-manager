"""Test cases for the data models."""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
import pytest

from wt_manager.models import (
    CommandExecution,
    CommandHistory,
    CommandStatus,
    Project,
    ProjectStatus,
    Worktree,
)


class TestWorktreeModel:
    """Test cases for the Worktree model."""

    def test_worktree_creation(self):
        """Test basic worktree creation."""
        test_path = "/tmp/test-worktree"
        worktree = Worktree(
            path=test_path,
            branch="main",
            commit_hash="abc123def456",
            is_bare=False,
            is_detached=False,
            has_uncommitted_changes=True,
        )

        # Path should be resolved to absolute path
        assert worktree.path == str(Path(test_path).resolve())
        assert worktree.branch == "main"
        assert worktree.commit_hash == "abc123def456"
        assert worktree.has_uncommitted_changes is True

    def test_status_display(self):
        """Test status display functionality."""
        # Test clean worktree
        worktree = Worktree(path="/tmp/test", branch="main", commit_hash="abc123")
        assert worktree.get_status_display() == "clean"

        # Test modified worktree
        worktree.has_uncommitted_changes = True
        assert "modified" in worktree.get_status_display()

        # Test detached worktree
        worktree.is_detached = True
        assert "detached" in worktree.get_status_display()

    def test_branch_display(self):
        """Test branch display functionality."""
        worktree = Worktree(
            path="/tmp/test", branch="feature-branch", commit_hash="abc123def456"
        )
        assert worktree.get_branch_display() == "feature-branch"

        # Test detached state
        worktree.is_detached = True
        assert worktree.get_branch_display() == "(abc123de)"

    def test_commit_short_hash(self):
        """Test short commit hash functionality."""
        worktree = Worktree(
            path="/tmp/test", branch="main", commit_hash="abc123def456789"
        )
        assert worktree.get_commit_short_hash() == "abc123de"

    def test_serialization(self):
        """Test worktree serialization and deserialization."""
        original = Worktree(
            path="/tmp/test-worktree",
            branch="main",
            commit_hash="abc123def456",
            is_bare=False,
            is_detached=True,
            has_uncommitted_changes=True,
        )

        # Test dict serialization
        data = original.to_dict()
        restored = Worktree.from_dict(data)

        assert restored.path == original.path
        assert restored.branch == original.branch
        assert restored.commit_hash == original.commit_hash
        assert restored.is_detached == original.is_detached
        assert restored.has_uncommitted_changes == original.has_uncommitted_changes

        # Test JSON serialization
        json_str = original.to_json()
        from_json = Worktree.from_json(json_str)
        assert from_json == original

    def test_equality(self):
        """Test worktree equality comparison."""
        worktree1 = Worktree(path="/tmp/test", branch="main", commit_hash="abc123")
        worktree2 = Worktree(path="/tmp/test", branch="dev", commit_hash="def456")
        worktree3 = Worktree(path="/tmp/other", branch="main", commit_hash="abc123")

        assert worktree1 == worktree2  # Same path
        assert worktree1 != worktree3  # Different path


class TestProjectModel:
    """Test cases for the Project model."""

    def test_project_creation(self):
        """Test basic project creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Project(
                id="test-project-1",
                name="Test Project",
                path=temp_dir,
                status=ProjectStatus.ACTIVE,
                last_accessed=datetime.now(),
            )

            assert project.id == "test-project-1"
            assert project.name == "Test Project"
            assert project.path == str(Path(temp_dir).resolve())
            assert project.status == ProjectStatus.ACTIVE

    def test_project_validation(self):
        """Test project validation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a fake .git directory
            git_dir = Path(temp_dir) / ".git"
            git_dir.mkdir()

            project = Project(
                id="test-project",
                name="Test Project",
                path=temp_dir,
                status=ProjectStatus.ACTIVE,
                last_accessed=datetime.now(),
            )

            assert project.is_valid() is True

    def test_display_name(self):
        """Test display name functionality."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test with explicit name
            project = Project(
                id="test-1",
                name="My Project",
                path=temp_dir,
                status=ProjectStatus.ACTIVE,
                last_accessed=datetime.now(),
            )
            assert project.get_display_name() == "My Project"

            # Test with empty name (should use directory name)
            project.name = ""
            expected_name = Path(temp_dir).name
            assert project.get_display_name() == expected_name

    def test_worktree_management(self):
        """Test worktree management functionality."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Project(
                id="test-project",
                name="Test Project",
                path=temp_dir,
                status=ProjectStatus.ACTIVE,
                last_accessed=datetime.now(),
            )

            # Add worktree
            worktree = Worktree(
                path=f"{temp_dir}/worktree1",
                branch="feature-branch",
                commit_hash="def456abc123",
            )
            project.add_worktree(worktree)
            assert len(project.worktrees) == 1

            # Get worktree by path
            found = project.get_worktree_by_path(worktree.path)
            assert found == worktree

            # Remove worktree
            removed = project.remove_worktree(worktree.path)
            assert removed is True
            assert len(project.worktrees) == 0

            # Try to remove non-existent worktree
            removed = project.remove_worktree("/non/existent/path")
            assert removed is False

    def test_serialization(self):
        """Test project serialization and deserialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original = Project(
                id="test-project-1",
                name="Test Project",
                path=temp_dir,
                status=ProjectStatus.ACTIVE,
                last_accessed=datetime.now(),
            )

            # Add a worktree
            worktree = Worktree(
                path=f"{temp_dir}/worktree1", branch="main", commit_hash="abc123"
            )
            original.add_worktree(worktree)

            # Test dict serialization
            data = original.to_dict()
            restored = Project.from_dict(data)

            assert restored.id == original.id
            assert restored.name == original.name
            assert restored.path == original.path
            assert restored.status == original.status
            assert len(restored.worktrees) == len(original.worktrees)

            # Test JSON serialization
            json_str = original.to_json()
            from_json = Project.from_json(json_str)
            assert from_json == original

    def test_equality(self):
        """Test project equality comparison."""
        project1 = Project(
            id="test-1",
            name="Project 1",
            path="/tmp/proj1",
            status=ProjectStatus.ACTIVE,
            last_accessed=datetime.now(),
        )
        project2 = Project(
            id="test-1",
            name="Different Name",
            path="/tmp/proj2",
            status=ProjectStatus.INACTIVE,
            last_accessed=datetime.now(),
        )
        project3 = Project(
            id="test-2",
            name="Project 1",
            path="/tmp/proj1",
            status=ProjectStatus.ACTIVE,
            last_accessed=datetime.now(),
        )

        assert project1 == project2  # Same ID
        assert project1 != project3  # Different ID


class TestCommandExecutionModel:
    """Test cases for the CommandExecution model."""

    def test_command_execution_creation(self):
        """Test basic command execution creation."""
        start_time = datetime.now()
        execution = CommandExecution(
            id="test-cmd-1",
            command="git status",
            worktree_path="/tmp/test-worktree",
            start_time=start_time,
        )

        assert execution.id == "test-cmd-1"
        assert execution.command == "git status"
        assert execution.worktree_path == "/tmp/test-worktree"
        assert execution.start_time == start_time
        assert execution.status == CommandStatus.PENDING
        assert execution.is_running() is False
        assert execution.is_finished() is False

    def test_command_execution_lifecycle(self):
        """Test command execution lifecycle methods."""
        execution = CommandExecution(
            id="test-cmd",
            command="echo hello",
            worktree_path="/tmp/test",
            start_time=datetime.now(),
        )

        self._test_execution_started(execution)
        self._test_execution_output(execution)
        self._test_execution_completed(execution)

    def _test_execution_started(self, execution):
        """Helper to test execution start."""
        execution.mark_started(process_id=12345)
        assert execution.status == CommandStatus.RUNNING
        assert execution.process_id == 12345
        assert execution.is_running() is True
        assert execution.is_finished() is False

    def _test_execution_output(self, execution):
        """Helper to test execution output."""
        execution.append_stdout("hello\n")
        execution.append_stderr("warning: test\n")
        assert execution.stdout == "hello\n"
        assert execution.stderr == "warning: test\n"

    def _test_execution_completed(self, execution):
        """Helper to test execution completion."""
        execution.mark_completed(exit_code=0)
        assert execution.status == CommandStatus.COMPLETED
        assert execution.exit_code == 0
        assert execution.process_id is None
        assert execution.is_running() is False
        assert execution.is_finished() is True
        assert execution.is_successful() is True
        assert execution.end_time is not None

    def test_command_execution_failure(self):
        """Test command execution failure handling."""
        execution = CommandExecution(
            id="test-cmd",
            command="false",
            worktree_path="/tmp/test",
            start_time=datetime.now(),
        )

        execution.mark_started()
        execution.mark_completed(exit_code=1)

        assert execution.status == CommandStatus.FAILED
        assert execution.exit_code == 1
        assert execution.is_successful() is False
        assert execution.is_finished() is True

    def test_command_execution_cancellation(self):
        """Test command execution cancellation."""
        execution = CommandExecution(
            id="test-cmd",
            command="sleep 10",
            worktree_path="/tmp/test",
            start_time=datetime.now(),
        )

        execution.mark_started()
        execution.mark_cancelled()

        assert execution.status == CommandStatus.CANCELLED
        assert execution.is_finished() is True
        assert execution.is_successful() is False
        assert execution.end_time is not None

    def test_command_execution_timeout(self):
        """Test command execution timeout handling."""
        execution = CommandExecution(
            id="test-cmd",
            command="sleep 100",
            worktree_path="/tmp/test",
            start_time=datetime.now(),
            timeout_seconds=5,
        )

        execution.mark_started()
        execution.mark_timeout()

        assert execution.status == CommandStatus.TIMEOUT
        assert execution.is_finished() is True
        assert execution.is_successful() is False

    def test_duration_calculation(self):
        """Test duration calculation methods."""
        start_time = datetime.now()
        execution = CommandExecution(
            id="test-cmd",
            command="echo test",
            worktree_path="/tmp/test",
            start_time=start_time,
        )

        # Running command should return current duration
        execution.mark_started()
        duration = execution.get_duration()
        assert duration is not None
        assert duration.total_seconds() >= 0

        # Completed command should return exact duration
        end_time = start_time + timedelta(seconds=2.5)
        execution.end_time = end_time
        execution.status = CommandStatus.COMPLETED

        duration = execution.get_duration()
        assert duration == timedelta(seconds=2.5)

        # Test duration display
        duration_display = execution.get_duration_display()
        assert "2.5s" in duration_display

    def test_output_formatting(self):
        """Test output formatting methods."""
        execution = CommandExecution(
            id="test-cmd",
            command="echo test",
            worktree_path="/tmp/test",
            start_time=datetime.now(),
        )

        # Test with no output
        formatted = execution.get_formatted_output()
        assert formatted == "(no output)"

        # Test with stdout only
        execution.stdout = "Hello World\n"
        formatted = execution.get_formatted_output()
        assert "=== STDOUT ===" in formatted
        assert "Hello World" in formatted

        # Test with both stdout and stderr
        execution.stderr = "Warning: test\n"
        formatted = execution.get_formatted_output()
        assert "=== STDOUT ===" in formatted
        assert "=== STDERR ===" in formatted
        assert "Hello World" in formatted
        assert "Warning: test" in formatted

    def test_status_display(self):
        """Test status display methods."""
        execution = CommandExecution(
            id="test-cmd",
            command="echo test",
            worktree_path="/tmp/test",
            start_time=datetime.now(),
        )

        # Test pending status
        assert execution.get_status_display() == "Pending"

        # Test running status
        execution.status = CommandStatus.RUNNING
        assert execution.get_status_display() == "Running"

        # Test completed status with exit code
        execution.mark_completed(exit_code=0)
        status_display = execution.get_status_display()
        assert "Completed" in status_display
        assert "exit code: 0" in status_display

    def test_command_display_truncation(self):
        """Test command display truncation."""
        long_command = "echo " + "a" * 100
        execution = CommandExecution(
            id="test-cmd",
            command=long_command,
            worktree_path="/tmp/test",
            start_time=datetime.now(),
        )

        # Test truncation
        display = execution.get_command_display(max_length=20)
        assert len(display) <= 20
        assert display.endswith("...")

        # Test no truncation needed
        short_display = execution.get_command_display(max_length=200)
        assert short_display == long_command

    def test_timeout_detection(self):
        """Test timeout detection."""
        # Create execution with 1 second timeout
        past_time = datetime.now() - timedelta(seconds=2)
        execution = CommandExecution(
            id="test-cmd",
            command="sleep 10",
            worktree_path="/tmp/test",
            start_time=past_time,
            timeout_seconds=1,
        )

        execution.status = CommandStatus.RUNNING
        assert execution.is_timed_out() is True

        # Test no timeout when not running
        execution.status = CommandStatus.COMPLETED
        assert execution.is_timed_out() is False

    def _create_test_command_execution(self):
        """Create a test CommandExecution instance."""
        start_time = datetime.now()
        end_time = start_time + timedelta(seconds=5)

        return CommandExecution(
            id="test-cmd-1",
            command="git status",
            worktree_path="/tmp/test-worktree",
            start_time=start_time,
            end_time=end_time,
            exit_code=0,
            stdout="On branch main\n",
            stderr="",
            status=CommandStatus.COMPLETED,
            timeout_seconds=30,
        )

    def _assert_basic_attributes_equal(self, original, restored):
        """Assert basic attributes are equal."""
        assert restored.id == original.id
        assert restored.command == original.command
        assert restored.worktree_path == original.worktree_path

    def _assert_time_attributes_equal(self, original, restored):
        """Assert time attributes are equal."""
        assert restored.start_time == original.start_time
        assert restored.end_time == original.end_time

    def _assert_execution_results_equal(self, original, restored):
        """Assert execution results are equal."""
        assert restored.exit_code == original.exit_code
        assert restored.stdout == original.stdout
        assert restored.stderr == original.stderr

    def _assert_status_attributes_equal(self, original, restored):
        """Assert status and timeout attributes are equal."""
        assert restored.status == original.status
        assert restored.timeout_seconds == original.timeout_seconds

    def _assert_command_executions_equal(self, original, restored):
        """Assert that two CommandExecution instances are equal."""
        self._assert_basic_attributes_equal(original, restored)
        self._assert_time_attributes_equal(original, restored)
        self._assert_execution_results_equal(original, restored)
        self._assert_status_attributes_equal(original, restored)

    def test_serialization(self):
        """Test command execution serialization and deserialization."""
        original = self._create_test_command_execution()

        # Test dict serialization
        data = original.to_dict()
        restored = CommandExecution.from_dict(data)
        self._assert_command_executions_equal(original, restored)

        # Test JSON serialization
        json_str = original.to_json()
        from_json = CommandExecution.from_json(json_str)
        assert from_json == original

    def test_equality(self):
        """Test command execution equality comparison."""
        execution1 = CommandExecution(
            id="test-1",
            command="git status",
            worktree_path="/tmp/test",
            start_time=datetime.now(),
        )
        execution2 = CommandExecution(
            id="test-1",
            command="git log",
            worktree_path="/tmp/other",
            start_time=datetime.now(),
        )
        execution3 = CommandExecution(
            id="test-2",
            command="git status",
            worktree_path="/tmp/test",
            start_time=datetime.now(),
        )

        assert execution1 == execution2  # Same ID
        assert execution1 != execution3  # Different ID


class TestCommandHistoryModel:
    """Test cases for the CommandHistory model."""

    def test_command_history_creation(self):
        """Test basic command history creation."""
        history = CommandHistory(worktree_path="/tmp/test-worktree")

        assert history.worktree_path == "/tmp/test-worktree"
        assert len(history.executions) == 0
        assert history.max_history_size == 100

    def test_add_execution(self):
        """Test adding executions to history."""
        history = CommandHistory()

        execution1 = CommandExecution(
            id="cmd-1",
            command="git status",
            worktree_path="/tmp/test",
            start_time=datetime.now(),
        )
        execution2 = CommandExecution(
            id="cmd-2",
            command="git log",
            worktree_path="/tmp/test",
            start_time=datetime.now(),
        )

        history.add_execution(execution1)
        assert len(history) == 1

        history.add_execution(execution2)
        assert len(history) == 2

        # Most recent should be first
        assert history.executions[0] == execution2
        assert history.executions[1] == execution1

    def test_history_size_limit(self):
        """Test history size limiting."""
        history = CommandHistory(max_history_size=3)

        # Add more executions than the limit
        for i in range(5):
            execution = CommandExecution(
                id=f"cmd-{i}",
                command=f"echo {i}",
                worktree_path="/tmp/test",
                start_time=datetime.now(),
            )
            history.add_execution(execution)

        # Should only keep the most recent 3
        assert len(history) == 3
        assert history.executions[0].command == "echo 4"  # Most recent
        assert history.executions[2].command == "echo 2"  # Oldest kept

    def test_get_recent_executions(self):
        """Test getting recent executions."""
        history = CommandHistory()

        # Add several executions
        for i in range(10):
            execution = CommandExecution(
                id=f"cmd-{i}",
                command=f"echo {i}",
                worktree_path="/tmp/test",
                start_time=datetime.now(),
            )
            history.add_execution(execution)

        # Get recent executions
        recent = history.get_recent_executions(limit=3)
        assert len(recent) == 3
        assert recent[0].command == "echo 9"  # Most recent
        assert recent[2].command == "echo 7"

    def test_get_running_executions(self):
        """Test getting running executions."""
        history = CommandHistory()

        # Add mix of running and completed executions
        running_exec = CommandExecution(
            id="running-cmd",
            command="sleep 10",
            worktree_path="/tmp/test",
            start_time=datetime.now(),
        )
        running_exec.mark_started()

        completed_exec = CommandExecution(
            id="completed-cmd",
            command="echo done",
            worktree_path="/tmp/test",
            start_time=datetime.now(),
        )
        completed_exec.mark_completed(exit_code=0)

        history.add_execution(running_exec)
        history.add_execution(completed_exec)

        running = history.get_running_executions()
        assert len(running) == 1
        assert running[0] == running_exec

    def test_get_execution_by_id(self):
        """Test getting execution by ID."""
        history = CommandHistory()

        execution = CommandExecution(
            id="test-cmd-id",
            command="git status",
            worktree_path="/tmp/test",
            start_time=datetime.now(),
        )
        history.add_execution(execution)

        found = history.get_execution_by_id("test-cmd-id")
        assert found == execution

        not_found = history.get_execution_by_id("non-existent")
        assert not_found is None

    def test_get_executions_by_command(self):
        """Test getting executions by command."""
        history = CommandHistory()

        # Add multiple executions with same command
        for i in range(3):
            execution = CommandExecution(
                id=f"cmd-{i}",
                command="git status",
                worktree_path="/tmp/test",
                start_time=datetime.now(),
            )
            history.add_execution(execution)

        # Add different command
        other_execution = CommandExecution(
            id="other-cmd",
            command="git log",
            worktree_path="/tmp/test",
            start_time=datetime.now(),
        )
        history.add_execution(other_execution)

        status_executions = history.get_executions_by_command("git status")
        assert len(status_executions) == 3

        log_executions = history.get_executions_by_command("git log")
        assert len(log_executions) == 1

    def test_get_successful_and_failed_executions(self):
        """Test getting successful and failed executions."""
        history = CommandHistory()

        # Add successful execution
        success_exec = CommandExecution(
            id="success-cmd",
            command="echo success",
            worktree_path="/tmp/test",
            start_time=datetime.now(),
        )
        success_exec.mark_completed(exit_code=0)

        # Add failed execution
        failed_exec = CommandExecution(
            id="failed-cmd",
            command="false",
            worktree_path="/tmp/test",
            start_time=datetime.now(),
        )
        failed_exec.mark_completed(exit_code=1)

        history.add_execution(success_exec)
        history.add_execution(failed_exec)

        successful = history.get_successful_executions()
        assert len(successful) == 1
        assert successful[0] == success_exec

        failed = history.get_failed_executions()
        assert len(failed) == 1
        assert failed[0] == failed_exec

    def test_remove_execution(self):
        """Test removing execution from history."""
        history = CommandHistory()

        execution = CommandExecution(
            id="test-cmd",
            command="git status",
            worktree_path="/tmp/test",
            start_time=datetime.now(),
        )
        history.add_execution(execution)

        assert len(history) == 1

        # Remove existing execution
        removed = history.remove_execution("test-cmd")
        assert removed is True
        assert len(history) == 0

        # Try to remove non-existent execution
        removed = history.remove_execution("non-existent")
        assert removed is False

    def test_clear_history(self):
        """Test clearing history."""
        history = CommandHistory()

        # Add some executions
        for i in range(5):
            execution = CommandExecution(
                id=f"cmd-{i}",
                command=f"echo {i}",
                worktree_path="/tmp/test",
                start_time=datetime.now(),
            )
            history.add_execution(execution)

        assert len(history) == 5

        history.clear_history()
        assert len(history) == 0

    def test_get_statistics(self):
        """Test getting history statistics."""
        history = CommandHistory()

        # Empty history
        stats = history.get_statistics()
        assert stats["total_executions"] == 0
        assert stats["successful"] == 0
        assert stats["failed"] == 0

        # Add various executions
        success_exec = CommandExecution(
            id="success",
            command="echo success",
            worktree_path="/tmp/test",
            start_time=datetime.now() - timedelta(seconds=2),
        )
        success_exec.mark_completed(exit_code=0)

        failed_exec = CommandExecution(
            id="failed",
            command="false",
            worktree_path="/tmp/test",
            start_time=datetime.now() - timedelta(seconds=1),
        )
        failed_exec.mark_completed(exit_code=1)

        running_exec = CommandExecution(
            id="running",
            command="sleep 10",
            worktree_path="/tmp/test",
            start_time=datetime.now(),
        )
        running_exec.mark_started()

        history.add_execution(success_exec)
        history.add_execution(failed_exec)
        history.add_execution(running_exec)

        stats = history.get_statistics()
        assert stats["total_executions"] == 3
        assert stats["successful"] == 1
        assert stats["failed"] == 1
        assert stats["running"] == 1
        assert stats["average_duration"] is not None

    def test_serialization(self):
        """Test command history serialization and deserialization."""
        original = CommandHistory(
            worktree_path="/tmp/test-worktree", max_history_size=50
        )

        # Add some executions
        execution = CommandExecution(
            id="test-cmd",
            command="git status",
            worktree_path="/tmp/test-worktree",
            start_time=datetime.now(),
        )
        original.add_execution(execution)

        # Test dict serialization
        data = original.to_dict()
        restored = CommandHistory.from_dict(data)

        assert restored.worktree_path == original.worktree_path
        assert restored.max_history_size == original.max_history_size
        assert len(restored.executions) == len(original.executions)
        assert restored.executions[0] == original.executions[0]


class TestModelValidation:
    """Test cases for model validation and edge cases."""

    def test_worktree_invalid_data_handling(self):
        """Test worktree handling of invalid data."""
        # Test with empty commit hash
        worktree = Worktree(
            path="/tmp/test",
            branch="main",
            commit_hash="",
        )
        assert worktree.get_commit_short_hash() == ""

        # Test with None last_modified (should set default)
        worktree = Worktree(
            path="/tmp/test",
            branch="main",
            commit_hash="abc123",
            last_modified=None,
        )
        assert worktree.last_modified is not None
        assert isinstance(worktree.last_modified, datetime)

    def test_worktree_serialization_edge_cases(self):
        """Test worktree serialization with edge cases."""
        # Test with None last_modified in dict data
        data = {
            "path": "/tmp/test",
            "branch": "main",
            "commit_hash": "abc123",
            "is_bare": False,
            "is_detached": False,
            "has_uncommitted_changes": False,
            "last_modified": None,
        }

        # Should handle None gracefully and set default in __post_init__
        restored = Worktree.from_dict(data)
        assert restored.last_modified is not None
        assert isinstance(restored.last_modified, datetime)

        # Test serialization preserves the set datetime
        restored_data = restored.to_dict()
        assert restored_data["last_modified"] is not None

        # Test JSON serialization with datetime values
        json_str = restored.to_json()
        from_json = Worktree.from_json(json_str)
        assert from_json.last_modified is not None
        assert isinstance(from_json.last_modified, datetime)

    def test_worktree_invalid_json_handling(self):
        """Test worktree handling of invalid JSON."""
        with pytest.raises(json.JSONDecodeError):
            Worktree.from_json("invalid json")

        # Test with missing required fields
        with pytest.raises(KeyError):
            Worktree.from_dict({"path": "/tmp/test"})  # Missing branch and commit_hash

    def test_project_validation_edge_cases(self):
        """Test project validation with edge cases."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test project with empty name
            project = Project(
                id="test-id",
                name="",
                path=temp_dir,
                status=ProjectStatus.ACTIVE,
                last_accessed=datetime.now(),
            )
            # Should use directory name as display name
            assert project.get_display_name() == Path(temp_dir).name

            # Test project with non-existent path
            project = Project(
                id="test-id",
                name="Test",
                path="/non/existent/path",
                status=ProjectStatus.ACTIVE,
                last_accessed=datetime.now(),
            )
            assert not project.is_valid()

    def test_project_auto_id_generation(self):
        """Test project automatic ID generation."""
        project = Project(
            id="",  # Empty ID should trigger auto-generation
            name="Test Project",
            path="/tmp/test",
            status=ProjectStatus.ACTIVE,
            last_accessed=datetime.now(),
        )
        assert project.id != ""
        assert len(project.id) > 0

    def test_project_serialization_edge_cases(self):
        """Test project serialization with edge cases."""
        with tempfile.TemporaryDirectory() as temp_dir:
            Project(
                id="test-id",
                name="Test Project",
                path=temp_dir,
                status=ProjectStatus.ACTIVE,
                last_accessed=datetime.now(),
            )

            # Test with invalid JSON
            with pytest.raises(json.JSONDecodeError):
                Project.from_json("invalid json")

            # Test with missing required fields
            with pytest.raises(KeyError):
                Project.from_dict({"id": "test"})  # Missing required fields

    def test_command_execution_validation(self):
        """Test command execution validation and edge cases."""
        # Test with empty ID (should auto-generate)
        execution = CommandExecution(
            id="",
            command="test command",
            worktree_path="/tmp/test",
            start_time=datetime.now(),
        )
        assert execution.id != ""
        assert len(execution.id) > 0

        # Test with None start_time (should set default)
        execution = CommandExecution(
            id="test-id",
            command="test command",
            worktree_path="/tmp/test",
            start_time=None,
        )
        assert execution.start_time is not None
        assert isinstance(execution.start_time, datetime)

    def test_command_execution_state_transitions_initial_state(self):
        """Test command execution initial state."""
        execution = CommandExecution(
            id="test-cmd",
            command="echo test",
            worktree_path="/tmp/test",
            start_time=datetime.now(),
        )

        # Test initial state
        assert execution.status == CommandStatus.PENDING
        assert not execution.is_running()
        assert not execution.is_finished()
        assert not execution.is_successful()

    def test_command_execution_state_transitions_to_running(self):
        """Test command execution transition to running state."""
        execution = CommandExecution(
            id="test-cmd",
            command="echo test",
            worktree_path="/tmp/test",
            start_time=datetime.now(),
        )

        # Test transition to running
        execution.mark_started(process_id=12345)
        assert execution.status == CommandStatus.RUNNING
        assert execution.process_id == 12345
        assert execution.is_running()
        assert not execution.is_finished()

    def test_command_execution_state_transitions_to_completed(self):
        """Test command execution transition to completed state."""
        execution = CommandExecution(
            id="test-cmd",
            command="echo test",
            worktree_path="/tmp/test",
            start_time=datetime.now(),
        )

        # Test transition to completed (success)
        execution.mark_started(process_id=12345)
        execution.mark_completed(exit_code=0)
        assert execution.status == CommandStatus.COMPLETED
        assert execution.exit_code == 0
        assert execution.process_id is None
        assert not execution.is_running()
        assert execution.is_finished()
        assert execution.is_successful()

    def test_command_execution_state_transitions_to_failed(self):
        """Test command execution transition to failed state."""
        execution = CommandExecution(
            id="test-cmd-2",
            command="false",
            worktree_path="/tmp/test",
            start_time=datetime.now(),
        )
        execution.mark_started()
        execution.mark_completed(exit_code=1)
        assert execution.status == CommandStatus.FAILED
        assert not execution.is_successful()

    def test_command_execution_state_transitions_to_cancelled(self):
        """Test command execution transition to cancelled state."""
        execution = CommandExecution(
            id="test-cmd-3",
            command="sleep 10",
            worktree_path="/tmp/test",
            start_time=datetime.now(),
        )
        execution.mark_started()
        execution.mark_cancelled()
        assert execution.status == CommandStatus.CANCELLED
        assert execution.is_finished()
        assert not execution.is_successful()

    def test_command_execution_state_transitions_to_timeout(self):
        """Test command execution transition to timeout state."""
        execution = CommandExecution(
            id="test-cmd-4",
            command="sleep 100",
            worktree_path="/tmp/test",
            start_time=datetime.now(),
        )
        execution.mark_started()
        execution.mark_timeout()
        assert execution.status == CommandStatus.TIMEOUT
        assert execution.is_finished()
        assert not execution.is_successful()

    def test_command_execution_output_management(self):
        """Test command execution output management."""
        execution = CommandExecution(
            id="test-cmd",
            command="echo test",
            worktree_path="/tmp/test",
            start_time=datetime.now(),
        )

        # Test incremental output appending
        execution.append_stdout("line 1\n")
        execution.append_stdout("line 2\n")
        execution.append_stderr("warning 1\n")
        execution.append_stderr("warning 2\n")

        assert execution.stdout == "line 1\nline 2\n"
        assert execution.stderr == "warning 1\nwarning 2\n"

        # Test formatted output with both stdout and stderr
        formatted = execution.get_formatted_output()
        assert "=== STDOUT ===" in formatted
        assert "=== STDERR ===" in formatted
        assert "line 1" in formatted
        assert "warning 1" in formatted

    def test_command_execution_timeout_edge_cases(self):
        """Test command execution timeout edge cases."""
        # Test timeout detection with no timeout set
        execution = CommandExecution(
            id="test-cmd",
            command="sleep 10",
            worktree_path="/tmp/test",
            start_time=datetime.now() - timedelta(seconds=10),
            timeout_seconds=None,
        )
        execution.status = CommandStatus.RUNNING
        assert not execution.is_timed_out()

        # Test timeout detection when not running
        execution.timeout_seconds = 5
        execution.status = CommandStatus.COMPLETED
        assert not execution.is_timed_out()

    def test_command_execution_serialization_edge_cases(self):
        """Test command execution serialization edge cases."""
        execution = CommandExecution(
            id="test-cmd",
            command="echo test",
            worktree_path="/tmp/test",
            start_time=datetime.now(),
        )

        # Test serialization with None end_time
        data = execution.to_dict()
        assert data["end_time"] is None

        restored = CommandExecution.from_dict(data)
        assert restored.end_time is None

        # Test with invalid JSON
        with pytest.raises(json.JSONDecodeError):
            CommandExecution.from_json("invalid json")

        # Test with missing required fields
        with pytest.raises(KeyError):
            CommandExecution.from_dict({"id": "test"})

    def test_command_history_edge_cases(self):
        """Test command history edge cases."""
        # Test with None worktree_path (global history)
        history = CommandHistory(worktree_path=None)
        assert history.worktree_path is None

        # Test statistics with empty history
        stats = history.get_statistics()
        assert stats["total_executions"] == 0
        assert stats["average_duration"] is None

        # Test with executions that have no duration
        execution = CommandExecution(
            id="test-cmd",
            command="echo test",
            worktree_path="/tmp/test",
            start_time=datetime.now(),
        )
        # Don't set end_time, so duration is None
        history.add_execution(execution)

        stats = history.get_statistics()
        assert stats["total_executions"] == 1
        assert stats["average_duration"] is None  # No finished executions

    def test_worktree_string_representations(self):
        """Test Worktree string representations."""
        worktree = Worktree(
            path="/tmp/test-worktree",
            branch="feature-branch",
            commit_hash="abc123def456",
        )
        str_repr = str(worktree)
        assert "test-worktree" in str_repr
        assert "feature-branch" in str_repr

        repr_str = repr(worktree)
        assert "Worktree" in repr_str
        assert "/tmp/test-worktree" in repr_str

    def test_project_string_representations(self):
        """Test Project string representations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a fake .git directory to make project valid
            git_dir = Path(temp_dir) / ".git"
            git_dir.mkdir()

            project = Project(
                id="test-id",
                name="Test Project",
                path=temp_dir,
                status=ProjectStatus.ACTIVE,
                last_accessed=datetime.now(),
            )
            str_repr = str(project)
            assert "Test Project" in str_repr
            assert "active" in str_repr

            repr_str = repr(project)
            assert "Project" in repr_str
            assert "test-id" in repr_str

    def test_command_execution_string_representations(self):
        """Test CommandExecution string representations."""
        execution = CommandExecution(
            id="test-cmd",
            command="git status --porcelain",
            worktree_path="/tmp/test",
            start_time=datetime.now(),
        )
        str_repr = str(execution)
        assert "CommandExecution" in str_repr
        assert "pending" in str_repr

        repr_str = repr(execution)
        assert "test-cmd" in repr_str
        assert "git status --porcelain" in repr_str

    def test_command_history_string_representations(self):
        """Test CommandHistory string representations."""
        history = CommandHistory(worktree_path="/tmp/test-worktree")
        str_repr = str(history)
        assert "CommandHistory" in str_repr
        assert "test-worktree" in str_repr

        repr_str = repr(history)
        assert "/tmp/test-worktree" in repr_str

    def test_model_hash_and_equality_edge_cases(self):
        """Test model hash and equality edge cases."""
        # Test Worktree equality with different attributes but same path
        worktree1 = Worktree(
            path="/tmp/test",
            branch="main",
            commit_hash="abc123",
            has_uncommitted_changes=True,
        )
        worktree2 = Worktree(
            path="/tmp/test",
            branch="develop",
            commit_hash="def456",
            has_uncommitted_changes=False,
        )
        assert worktree1 == worktree2  # Same path
        assert hash(worktree1) == hash(worktree2)

        # Test Project equality with different attributes but same ID
        project1 = Project(
            id="same-id",
            name="Project 1",
            path="/tmp/proj1",
            status=ProjectStatus.ACTIVE,
            last_accessed=datetime.now(),
        )
        project2 = Project(
            id="same-id",
            name="Project 2",
            path="/tmp/proj2",
            status=ProjectStatus.INACTIVE,
            last_accessed=datetime.now(),
        )
        assert project1 == project2  # Same ID
        assert hash(project1) == hash(project2)

        # Test CommandExecution equality with different attributes but same ID
        execution1 = CommandExecution(
            id="same-id",
            command="echo 1",
            worktree_path="/tmp/test1",
            start_time=datetime.now(),
        )
        execution2 = CommandExecution(
            id="same-id",
            command="echo 2",
            worktree_path="/tmp/test2",
            start_time=datetime.now(),
        )
        assert execution1 == execution2  # Same ID
        assert hash(execution1) == hash(execution2)

        # Test inequality with different types
        assert worktree1 != "not a worktree"
        assert project1 != "not a project"
        assert execution1 != "not an execution"
