"""Git operations service for Git Worktree Manager."""

import logging
import subprocess
from pathlib import Path

from ..utils.exceptions import GitError, ValidationError
from .base import CommandResult, GitServiceInterface

logger = logging.getLogger(__name__)


class GitService(GitServiceInterface):
    """
    Service for executing Git operations and managing worktrees.

    This service provides a high-level interface for Git operations including
    worktree management, branch operations, and repository validation.
    """

    def __init__(self, timeout: int = 30):
        """
        Initialize the Git service.

        Args:
            timeout: Default timeout for Git operations in seconds
        """
        super().__init__()
        self.timeout = timeout
        self._git_executable = "git"

    def _do_initialize(self) -> None:
        """Initialize the Git service by checking Git availability."""
        try:
            result = self._run_git_command(["--version"], cwd=".")
            if not result.success:
                raise GitError("Git is not available or not properly installed")
            logger.info(f"Git service initialized: {result.output.strip()}")
        except Exception as e:
            raise GitError(f"Failed to initialize Git service: {e}")

    def _run_git_command(
        self,
        args: list[str],
        cwd: str,
        timeout: int | None = None,
        capture_output: bool = True,
    ) -> CommandResult:
        """
        Execute a Git command with proper error handling.

        Args:
            args: Git command arguments (without 'git')
            cwd: Working directory for the command
            timeout: Command timeout in seconds
            capture_output: Whether to capture stdout/stderr

        Returns:
            CommandResult: Result of the command execution

        Raises:
            GitError: If the command execution fails
        """
        if timeout is None:
            timeout = self.timeout

        command = [self._git_executable] + args

        try:
            logger.debug(f"Executing Git command: {' '.join(command)} in {cwd}")

            result = subprocess.run(
                command,
                cwd=cwd,
                capture_output=capture_output,
                text=True,
                timeout=timeout,
                check=False,
            )

            success = result.returncode == 0
            output = result.stdout.strip() if result.stdout else ""
            error = result.stderr.strip() if result.stderr else ""

            if not success:
                logger.warning(
                    f"Git command failed: {' '.join(command)}, "
                    f"exit code: {result.returncode}, error: {error}"
                )

            return CommandResult(
                success=success, output=output, error=error, exit_code=result.returncode
            )

        except subprocess.TimeoutExpired:
            error_msg = (
                f"Git command timed out after {timeout} seconds: {' '.join(command)}"
            )
            logger.error(error_msg)
            raise GitError(error_msg)
        except subprocess.SubprocessError as e:
            error_msg = f"Failed to execute Git command: {e}"
            logger.error(error_msg)
            raise GitError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error executing Git command: {e}"
            logger.error(error_msg)
            raise GitError(error_msg)

    def execute_command(self, command: list[str], cwd: str) -> CommandResult:
        """
        Execute a Git command.

        Args:
            command: Git command arguments (without 'git')
            cwd: Working directory for the command

        Returns:
            CommandResult: Result of the command execution
        """
        return self._run_git_command(command, cwd)

    def get_worktree_list(self, repo_path: str) -> list[dict]:
        """
        Get list of worktrees for a repository.

        Args:
            repo_path: Path to the Git repository

        Returns:
            List[Dict]: List of worktree information dictionaries

        Raises:
            GitError: If the operation fails
        """
        try:
            # Use git worktree list --porcelain for machine-readable output
            result = self._run_git_command(
                ["worktree", "list", "--porcelain"], cwd=repo_path
            )

            if not result.success:
                raise GitError(f"Failed to list worktrees: {result.error}")

            return self._parse_worktree_list(result.output)

        except Exception as e:
            if isinstance(e, GitError):
                raise
            raise GitError(f"Failed to get worktree list: {e}")

    def _parse_worktree_list(self, output: str) -> list[dict]:
        """
        Parse the output of 'git worktree list --porcelain'.

        Args:
            output: Raw output from git worktree list --porcelain

        Returns:
            List[Dict]: Parsed worktree information
        """
        worktrees = []
        current_worktree = {}

        for line in output.split("\n"):
            line = line.strip()
            if not line:
                if current_worktree:
                    worktrees.append(current_worktree)
                    current_worktree = {}
                continue

            current_worktree = self._parse_worktree_line(line, current_worktree)

        # Add the last worktree if exists
        if current_worktree:
            worktrees.append(current_worktree)

        # Set default values for missing fields
        for worktree in worktrees:
            worktree.setdefault("is_bare", False)
            worktree.setdefault("is_detached", False)
            worktree.setdefault("branch", "HEAD")
            worktree.setdefault("commit_hash", "")

        return worktrees

    def _parse_worktree_line(self, line: str, worktree: dict) -> dict:
        """Parse a single line from git worktree list output."""
        if line.startswith("worktree "):
            worktree["path"] = line[9:]  # Remove 'worktree ' prefix
        elif line.startswith("HEAD "):
            worktree["commit_hash"] = line[5:]  # Remove 'HEAD ' prefix
        elif line.startswith("branch "):
            worktree = self._parse_branch_line(line, worktree)
        elif line == "detached":
            worktree["is_detached"] = True
            worktree["branch"] = "HEAD"
        elif line == "bare":
            worktree["is_bare"] = True

        return worktree

    def _parse_branch_line(self, line: str, worktree: dict) -> dict:
        """Parse a branch line from git worktree list output."""
        branch_ref = line[7:]  # Remove 'branch ' prefix
        # Extract branch name from refs/heads/branch_name
        if branch_ref.startswith("refs/heads/"):
            worktree["branch"] = branch_ref[11:]
        else:
            worktree["branch"] = branch_ref
        worktree["is_detached"] = False
        return worktree

    def create_worktree(
        self, repo_path: str, worktree_path: str, branch: str
    ) -> CommandResult:
        """
        Create a new worktree.

        Args:
            repo_path: Path to the Git repository
            worktree_path: Path where the new worktree should be created
            branch: Branch name for the worktree

        Returns:
            CommandResult: Result of the worktree creation

        Raises:
            GitError: If the operation fails
        """
        try:
            # Validate inputs
            if not repo_path or not worktree_path or not branch:
                raise ValidationError(
                    "Repository path, worktree path, and branch are required"
                )

            # Check if worktree path already exists
            if Path(worktree_path).exists():
                raise GitError(f"Worktree path already exists: {worktree_path}")

            # Create the worktree
            result = self._run_git_command(
                ["worktree", "add", worktree_path, branch], cwd=repo_path
            )

            if not result.success:
                # Handle common error cases
                if "already exists" in result.error.lower():
                    raise GitError(f"Worktree path already exists: {worktree_path}")
                elif "not a valid branch" in result.error.lower():
                    raise GitError(f"Branch '{branch}' does not exist")
                else:
                    raise GitError(f"Failed to create worktree: {result.error}")

            logger.info(f"Created worktree at {worktree_path} for branch {branch}")
            return result

        except Exception as e:
            if isinstance(e, (GitError, ValidationError)):
                raise
            raise GitError(f"Failed to create worktree: {e}")

    def remove_worktree(self, worktree_path: str, force: bool = False) -> CommandResult:
        """
        Remove a worktree.

        Args:
            worktree_path: Path to the worktree to remove
            force: Whether to force removal even with uncommitted changes

        Returns:
            CommandResult: Result of the worktree removal

        Raises:
            GitError: If the operation fails
        """
        try:
            if not worktree_path:
                raise ValidationError("Worktree path is required")

            # Build the command
            command = ["worktree", "remove"]
            if force:
                command.append("--force")
            command.append(worktree_path)

            # Find the main repository path by looking for .git directory
            # We need to run the command from the main repository
            repo_path = self._find_repository_root(worktree_path)

            result = self._run_git_command(command, cwd=repo_path)

            if not result.success:
                # Handle common error cases
                if "not a working tree" in result.error.lower():
                    raise GitError(f"Path is not a Git worktree: {worktree_path}")
                elif "uncommitted changes" in result.error.lower():
                    raise GitError(
                        f"Worktree has uncommitted changes. Use force=True to override: {worktree_path}"
                    )
                else:
                    raise GitError(f"Failed to remove worktree: {result.error}")

            logger.info(f"Removed worktree at {worktree_path}")
            return result

        except Exception as e:
            if isinstance(e, (GitError, ValidationError)):
                raise
            raise GitError(f"Failed to remove worktree: {e}")

    def _find_repository_root(self, path: str) -> str:
        """
        Find the root of the Git repository for a given path.

        Args:
            path: Path within a Git repository or worktree

        Returns:
            str: Path to the repository root

        Raises:
            GitError: If no repository root is found
        """
        try:
            result = self._run_git_command(["rev-parse", "--show-toplevel"], cwd=path)

            if result.success:
                return result.output.strip()
            else:
                # Try to find .git directory by walking up the directory tree
                current_path = Path(path).resolve()
                while current_path != current_path.parent:
                    git_dir = current_path / ".git"
                    if git_dir.exists():
                        return str(current_path)
                    current_path = current_path.parent

                raise GitError(f"No Git repository found for path: {path}")

        except Exception as e:
            if isinstance(e, GitError):
                raise
            raise GitError(f"Failed to find repository root: {e}")

    def fetch_remote(self, repo_path: str) -> CommandResult:
        """
        Fetch from remote repositories.

        Args:
            repo_path: Path to the Git repository

        Returns:
            CommandResult: Result of the fetch operation

        Raises:
            GitError: If the operation fails
        """
        try:
            result = self._run_git_command(["fetch", "--all"], cwd=repo_path)

            if not result.success:
                # Fetch can succeed with warnings, so check for actual errors
                if result.exit_code != 0:
                    raise GitError(f"Failed to fetch from remote: {result.error}")

            logger.info(f"Fetched remote changes for repository at {repo_path}")
            return result

        except Exception as e:
            if isinstance(e, GitError):
                raise
            raise GitError(f"Failed to fetch remote: {e}")

    def get_branch_list(self, repo_path: str) -> list[str]:
        """
        Get list of branches (local and remote).

        Args:
            repo_path: Path to the Git repository

        Returns:
            List[str]: List of branch names

        Raises:
            GitError: If the operation fails
        """
        try:
            local_branches = self._get_local_branches(repo_path)
            remote_branches = self._get_remote_branches(repo_path)

            all_branches = local_branches + remote_branches
            return self._remove_duplicate_branches(all_branches)

        except Exception as e:
            if isinstance(e, GitError):
                raise
            raise GitError(f"Failed to get branch list: {e}")

    def _get_local_branches(self, repo_path: str) -> list[str]:
        """Get list of local branches."""
        result = self._run_git_command(
            ["branch", "--format=%(refname:short)"], cwd=repo_path
        )

        if result.success and result.output:
            return [
                branch.strip() for branch in result.output.split("\n") if branch.strip()
            ]
        return []

    def _get_remote_branches(self, repo_path: str) -> list[str]:
        """Get list of remote branches, excluding HEAD references."""
        result = self._run_git_command(
            ["branch", "-r", "--format=%(refname:short)"], cwd=repo_path
        )

        if result.success and result.output:
            return [
                branch.strip()
                for branch in result.output.split("\n")
                if branch.strip() and not branch.strip().endswith("/HEAD")
            ]
        return []

    def _remove_duplicate_branches(self, branches: list[str]) -> list[str]:
        """Remove duplicates while preserving order."""
        seen = set()
        unique_branches = []
        for branch in branches:
            if branch not in seen:
                seen.add(branch)
                unique_branches.append(branch)
        return unique_branches

    def check_uncommitted_changes(self, repo_path: str) -> bool:
        """
        Check if there are uncommitted changes in a repository or worktree.

        Args:
            repo_path: Path to the Git repository or worktree

        Returns:
            bool: True if there are uncommitted changes, False otherwise

        Raises:
            GitError: If the operation fails
        """
        try:
            # Check for staged changes
            staged_result = self._run_git_command(
                ["diff", "--cached", "--quiet"], cwd=repo_path
            )

            # Check for unstaged changes
            unstaged_result = self._run_git_command(["diff", "--quiet"], cwd=repo_path)

            # Check for untracked files
            untracked_result = self._run_git_command(
                ["ls-files", "--others", "--exclude-standard"], cwd=repo_path
            )

            # If any check indicates changes, return True
            has_staged = not staged_result.success
            has_unstaged = not unstaged_result.success
            has_untracked = untracked_result.success and bool(
                untracked_result.output.strip()
            )

            return has_staged or has_unstaged or has_untracked

        except Exception as e:
            if isinstance(e, GitError):
                raise
            raise GitError(f"Failed to check uncommitted changes: {e}")

    def get_current_branch(self, repo_path: str) -> str:
        """
        Get the current branch name.

        Args:
            repo_path: Path to the Git repository or worktree

        Returns:
            str: Current branch name or commit hash if detached

        Raises:
            GitError: If the operation fails
        """
        try:
            result = self._run_git_command(["branch", "--show-current"], cwd=repo_path)

            if result.success and result.output.strip():
                return result.output.strip()

            # If no current branch (detached HEAD), get commit hash
            commit_result = self._run_git_command(
                ["rev-parse", "--short", "HEAD"], cwd=repo_path
            )

            if commit_result.success:
                return f"({commit_result.output.strip()})"

            raise GitError("Failed to determine current branch or commit")

        except Exception as e:
            if isinstance(e, GitError):
                raise
            raise GitError(f"Failed to get current branch: {e}")

    def is_git_repository(self, path: str) -> bool:
        """
        Check if a path is a Git repository.

        Args:
            path: Path to check

        Returns:
            bool: True if the path is a Git repository
        """
        try:
            result = self._run_git_command(["rev-parse", "--git-dir"], cwd=path)
            return result.success
        except Exception:
            return False
