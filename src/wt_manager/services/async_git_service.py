"""Asynchronous Git operations service using QThread."""

import logging
import time
from enum import Enum
from typing import Any

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from ..utils.exceptions import GitError
from .git_service import GitService

logger = logging.getLogger(__name__)


class OperationType(Enum):
    """Types of Git operations that can be performed asynchronously."""

    LIST_WORKTREES = "list_worktrees"
    CREATE_WORKTREE = "create_worktree"
    REMOVE_WORKTREE = "remove_worktree"
    FETCH_REMOTE = "fetch_remote"
    GET_BRANCHES = "get_branches"
    CHECK_UNCOMMITTED = "check_uncommitted"


class GitOperationResult:
    """Result of an asynchronous Git operation."""

    def __init__(
        self,
        operation_type: OperationType,
        success: bool,
        data: Any = None,
        error: str = "",
        operation_id: str = "",
    ):
        self.operation_type = operation_type
        self.success = success
        self.data = data
        self.error = error
        self.operation_id = operation_id
        self.timestamp = time.time()


class GitWorker(QObject):
    """
    Worker class for executing Git operations in a separate thread.

    This class handles the actual Git operations and emits signals
    to communicate progress and results back to the main thread.
    """

    # Signals for communication with the main thread
    progress = pyqtSignal(str, int)  # message, percentage
    finished = pyqtSignal(GitOperationResult)
    error = pyqtSignal(str)

    def __init__(self, git_service: GitService):
        super().__init__()
        self.git_service = git_service
        self._cancelled = False

    def cancel(self):
        """Cancel the current operation."""
        self._cancelled = True
        logger.info("Git operation cancelled by user")

    def is_cancelled(self) -> bool:
        """Check if the operation has been cancelled."""
        return self._cancelled

    def list_worktrees(self, repo_path: str, operation_id: str = ""):
        """
        List worktrees for a repository.

        Args:
            repo_path: Path to the Git repository
            operation_id: Unique identifier for this operation
        """
        try:
            if self.is_cancelled():
                return

            self.progress.emit("Listing worktrees...", 10)

            worktrees = self.git_service.get_worktree_list(repo_path)

            if self.is_cancelled():
                return

            self.progress.emit("Processing worktree information...", 80)

            # Add status information for each worktree
            for worktree_info in worktrees:
                if self.is_cancelled():
                    return

                try:
                    # Check for uncommitted changes
                    has_changes = self.git_service.check_uncommitted_changes(
                        worktree_info["path"]
                    )
                    worktree_info["has_uncommitted_changes"] = has_changes
                except Exception as e:
                    logger.warning(
                        f"Failed to check uncommitted changes for {worktree_info['path']}: {e}"
                    )
                    worktree_info["has_uncommitted_changes"] = False

            self.progress.emit("Complete", 100)

            result = GitOperationResult(
                operation_type=OperationType.LIST_WORKTREES,
                success=True,
                data=worktrees,
                operation_id=operation_id,
            )
            self.finished.emit(result)

        except Exception as e:
            error_msg = f"Failed to list worktrees: {e}"
            logger.error(error_msg)
            result = GitOperationResult(
                operation_type=OperationType.LIST_WORKTREES,
                success=False,
                error=error_msg,
                operation_id=operation_id,
            )
            self.finished.emit(result)

    def create_worktree(
        self, repo_path: str, worktree_path: str, branch: str, operation_id: str = ""
    ):
        """
        Create a new worktree.

        Args:
            repo_path: Path to the Git repository
            worktree_path: Path for the new worktree
            branch: Branch name for the worktree
            operation_id: Unique identifier for this operation
        """
        try:
            if self.is_cancelled():
                return

            self.progress.emit("Fetching latest changes...", 20)

            # Fetch remote changes first
            try:
                self.git_service.fetch_remote(repo_path)
            except GitError as e:
                logger.warning(f"Failed to fetch remote changes: {e}")
                # Continue with worktree creation even if fetch fails

            if self.is_cancelled():
                return

            self.progress.emit(f"Creating worktree at {worktree_path}...", 60)

            result = self.git_service.create_worktree(repo_path, worktree_path, branch)

            if self.is_cancelled():
                return

            self.progress.emit("Worktree created successfully", 100)

            operation_result = GitOperationResult(
                operation_type=OperationType.CREATE_WORKTREE,
                success=True,
                data=result,
                operation_id=operation_id,
            )
            self.finished.emit(operation_result)

        except Exception as e:
            error_msg = f"Failed to create worktree: {e}"
            logger.error(error_msg)
            result = GitOperationResult(
                operation_type=OperationType.CREATE_WORKTREE,
                success=False,
                error=error_msg,
                operation_id=operation_id,
            )
            self.finished.emit(result)

    def remove_worktree(
        self, worktree_path: str, force: bool = False, operation_id: str = ""
    ):
        """
        Remove a worktree.

        Args:
            worktree_path: Path to the worktree to remove
            force: Whether to force removal
            operation_id: Unique identifier for this operation
        """
        try:
            if self.is_cancelled():
                return

            self.progress.emit("Checking worktree status...", 20)

            # Check for uncommitted changes if not forcing
            if not force:
                try:
                    has_changes = self.git_service.check_uncommitted_changes(
                        worktree_path
                    )
                    if has_changes:
                        raise GitError(
                            "Worktree has uncommitted changes. Use force removal to override."
                        )
                except GitError:
                    raise
                except Exception as e:
                    logger.warning(f"Failed to check uncommitted changes: {e}")

            if self.is_cancelled():
                return

            self.progress.emit(f"Removing worktree at {worktree_path}...", 70)

            result = self.git_service.remove_worktree(worktree_path, force)

            if self.is_cancelled():
                return

            self.progress.emit("Worktree removed successfully", 100)

            operation_result = GitOperationResult(
                operation_type=OperationType.REMOVE_WORKTREE,
                success=True,
                data=result,
                operation_id=operation_id,
            )
            self.finished.emit(operation_result)

        except Exception as e:
            error_msg = f"Failed to remove worktree: {e}"
            logger.error(error_msg)
            result = GitOperationResult(
                operation_type=OperationType.REMOVE_WORKTREE,
                success=False,
                error=error_msg,
                operation_id=operation_id,
            )
            self.finished.emit(result)

    def fetch_remote(self, repo_path: str, operation_id: str = ""):
        """
        Fetch from remote repositories.

        Args:
            repo_path: Path to the Git repository
            operation_id: Unique identifier for this operation
        """
        try:
            if self.is_cancelled():
                return

            self.progress.emit("Fetching from remote repositories...", 50)

            result = self.git_service.fetch_remote(repo_path)

            if self.is_cancelled():
                return

            self.progress.emit("Fetch completed", 100)

            operation_result = GitOperationResult(
                operation_type=OperationType.FETCH_REMOTE,
                success=True,
                data=result,
                operation_id=operation_id,
            )
            self.finished.emit(operation_result)

        except Exception as e:
            error_msg = f"Failed to fetch remote: {e}"
            logger.error(error_msg)
            result = GitOperationResult(
                operation_type=OperationType.FETCH_REMOTE,
                success=False,
                error=error_msg,
                operation_id=operation_id,
            )
            self.finished.emit(result)

    def get_branches(self, repo_path: str, operation_id: str = ""):
        """
        Get list of branches.

        Args:
            repo_path: Path to the Git repository
            operation_id: Unique identifier for this operation
        """
        try:
            if self.is_cancelled():
                return

            self.progress.emit("Getting branch list...", 50)

            branches = self.git_service.get_branch_list(repo_path)

            if self.is_cancelled():
                return

            self.progress.emit("Branch list retrieved", 100)

            result = GitOperationResult(
                operation_type=OperationType.GET_BRANCHES,
                success=True,
                data=branches,
                operation_id=operation_id,
            )
            self.finished.emit(result)

        except Exception as e:
            error_msg = f"Failed to get branches: {e}"
            logger.error(error_msg)
            result = GitOperationResult(
                operation_type=OperationType.GET_BRANCHES,
                success=False,
                error=error_msg,
                operation_id=operation_id,
            )
            self.finished.emit(result)


class AsyncGitService(QObject):
    """
    Asynchronous Git service that manages background Git operations.

    This service provides a high-level interface for performing Git operations
    asynchronously using QThread, with progress reporting and cancellation support.
    """

    # Signals for operation status
    operation_started = pyqtSignal(str, str)  # operation_type, operation_id
    operation_progress = pyqtSignal(str, str, int)  # operation_id, message, percentage
    operation_finished = pyqtSignal(GitOperationResult)
    operation_error = pyqtSignal(str, str)  # operation_id, error_message

    def __init__(self, git_service: GitService):
        super().__init__()
        self.git_service = git_service
        self._active_operations: dict[str, tuple[QThread, GitWorker]] = {}
        self._operation_counter = 0

    def _generate_operation_id(self) -> str:
        """Generate a unique operation ID."""
        self._operation_counter += 1
        return f"git_op_{self._operation_counter}_{int(time.time())}"

    def _start_operation(
        self, operation_type: OperationType, worker_method: str, *args, **kwargs
    ) -> str:
        """
        Start an asynchronous Git operation.

        Args:
            operation_type: Type of operation to perform
            worker_method: Name of the worker method to call
            *args: Arguments to pass to the worker method
            **kwargs: Keyword arguments to pass to the worker method

        Returns:
            str: Operation ID for tracking
        """
        operation_id = self._generate_operation_id()

        # Create worker and thread
        worker = GitWorker(self.git_service)
        thread = QThread()

        # Move worker to thread
        worker.moveToThread(thread)

        # Connect signals
        worker.progress.connect(
            lambda msg, pct: self.operation_progress.emit(operation_id, msg, pct)
        )
        worker.finished.connect(self._on_operation_finished)
        worker.error.connect(
            lambda error: self.operation_error.emit(operation_id, error)
        )

        # Connect thread signals
        thread.started.connect(
            lambda: getattr(worker, worker_method)(
                *args, operation_id=operation_id, **kwargs
            )
        )
        thread.finished.connect(thread.deleteLater)

        # Store the operation
        self._active_operations[operation_id] = (thread, worker)

        # Start the operation
        thread.start()
        self.operation_started.emit(operation_type.value, operation_id)

        logger.info(f"Started {operation_type.value} operation with ID: {operation_id}")

        return operation_id

    def _on_operation_finished(self, result: GitOperationResult):
        """Handle operation completion."""
        operation_id = result.operation_id

        # Clean up the operation
        if operation_id in self._active_operations:
            thread, worker = self._active_operations[operation_id]
            thread.quit()
            thread.wait()
            del self._active_operations[operation_id]

        # Emit the result
        self.operation_finished.emit(result)

        logger.info(
            f"Completed {result.operation_type.value} operation "
            f"(ID: {operation_id}, Success: {result.success})"
        )

    def list_worktrees_async(self, repo_path: str) -> str:
        """
        List worktrees asynchronously.

        Args:
            repo_path: Path to the Git repository

        Returns:
            str: Operation ID for tracking
        """
        return self._start_operation(
            OperationType.LIST_WORKTREES, "list_worktrees", repo_path
        )

    def create_worktree_async(
        self, repo_path: str, worktree_path: str, branch: str
    ) -> str:
        """
        Create a worktree asynchronously.

        Args:
            repo_path: Path to the Git repository
            worktree_path: Path for the new worktree
            branch: Branch name for the worktree

        Returns:
            str: Operation ID for tracking
        """
        return self._start_operation(
            OperationType.CREATE_WORKTREE,
            "create_worktree",
            repo_path,
            worktree_path,
            branch,
        )

    def remove_worktree_async(self, worktree_path: str, force: bool = False) -> str:
        """
        Remove a worktree asynchronously.

        Args:
            worktree_path: Path to the worktree to remove
            force: Whether to force removal

        Returns:
            str: Operation ID for tracking
        """
        return self._start_operation(
            OperationType.REMOVE_WORKTREE, "remove_worktree", worktree_path, force
        )

    def fetch_remote_async(self, repo_path: str) -> str:
        """
        Fetch from remote repositories asynchronously.

        Args:
            repo_path: Path to the Git repository

        Returns:
            str: Operation ID for tracking
        """
        return self._start_operation(
            OperationType.FETCH_REMOTE, "fetch_remote", repo_path
        )

    def get_branches_async(self, repo_path: str) -> str:
        """
        Get list of branches asynchronously.

        Args:
            repo_path: Path to the Git repository

        Returns:
            str: Operation ID for tracking
        """
        return self._start_operation(
            OperationType.GET_BRANCHES, "get_branches", repo_path
        )

    def cancel_operation(self, operation_id: str) -> bool:
        """
        Cancel an active operation.

        Args:
            operation_id: ID of the operation to cancel

        Returns:
            bool: True if operation was found and cancelled
        """
        if operation_id in self._active_operations:
            thread, worker = self._active_operations[operation_id]
            worker.cancel()
            thread.quit()
            thread.wait()
            del self._active_operations[operation_id]

            logger.info(f"Cancelled operation: {operation_id}")
            return True

        return False

    def cancel_all_operations(self):
        """Cancel all active operations."""
        operation_ids = list(self._active_operations.keys())
        for operation_id in operation_ids:
            self.cancel_operation(operation_id)

        logger.info("Cancelled all active operations")

    def get_active_operations(self) -> list[str]:
        """
        Get list of active operation IDs.

        Returns:
            List[str]: List of active operation IDs
        """
        return list(self._active_operations.keys())

    def is_operation_active(self, operation_id: str) -> bool:
        """
        Check if an operation is currently active.

        Args:
            operation_id: ID of the operation to check

        Returns:
            bool: True if operation is active
        """
        return operation_id in self._active_operations

    def shutdown(self):
        """Shutdown the service and clean up all operations."""
        self.cancel_all_operations()
        logger.info("AsyncGitService shutdown complete")
