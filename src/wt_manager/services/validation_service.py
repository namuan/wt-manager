"""Validation service for input validation and safety checks."""

import os
import re
import subprocess
from pathlib import Path

from ..services.base import ValidationResult, ValidationServiceInterface


class ValidationService(ValidationServiceInterface):
    """Service for validating user inputs and ensuring operation safety."""

    # Dangerous command patterns that should be blocked
    DANGEROUS_COMMANDS = {
        # System modification commands
        r"\brm\s+(-rf?|--recursive|--force)",
        r"\bsudo\b",
        r"\bsu\b",
        r"\bchmod\s+777",
        r"\bchown\b",
        r"\bmkfs\b",
        r"\bfdisk\b",
        r"\bdd\s+",
        r"\bformat\b",
        # Network and system access
        r"\bcurl\s+.*\|\s*(sh|bash|zsh)",
        r"\bwget\s+.*\|\s*(sh|bash|zsh)",
        r"\bssh\b",
        r"\bscp\b",
        r"\brsync\b.*--delete",
        # Process manipulation
        r"\bkill\s+(-9|--kill)",
        r"\bkillall\b",
        r"\bpkill\b",
        # File system manipulation
        r"\bmv\s+.*\s+/\w+",  # Moving to system directories
        r"\bcp\s+.*\s+/\w+",  # Copying to system directories
        # Shell injection patterns
        r"[;&|`$(){}]",  # Shell metacharacters
        r"\$\(",  # Command substitution
        r"`[^`]*`",  # Backtick command substitution
    }

    # Valid Git branch name pattern (simplified)
    VALID_BRANCH_PATTERN = re.compile(r"^[a-zA-Z0-9._/-]+$")

    # Invalid branch name patterns
    INVALID_BRANCH_PATTERNS = [
        r"^-",  # Cannot start with dash
        r"\.\.",  # Cannot contain double dots
        r"/$",  # Cannot end with slash
        r"//",  # Cannot contain double slashes
        r"@{",  # Cannot contain @{
        r"\\",  # Cannot contain backslashes
        r"\s",  # Cannot contain whitespace
        r"[\x00-\x1f\x7f]",  # Cannot contain control characters
    ]

    def __init__(self):
        """Initialize the validation service."""
        super().__init__()
        self._dangerous_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.DANGEROUS_COMMANDS
        ]
        self._invalid_branch_patterns = [
            re.compile(pattern) for pattern in self.INVALID_BRANCH_PATTERNS
        ]

    def _do_initialize(self) -> None:
        """Perform service-specific initialization."""
        # No specific initialization needed for validation service
        pass

    def validate_git_repository(self, path: str) -> ValidationResult:
        """
        Validate if the given path is a valid Git repository.

        Args:
            path: Path to validate as a Git repository

        Returns:
            ValidationResult indicating if the path is a valid Git repository
        """
        if not path or not path.strip():
            return ValidationResult(
                is_valid=False,
                message="Path cannot be empty",
                details={"error_type": "empty_path"},
            )

        try:
            repo_path = Path(path).resolve()

            # Check if path exists
            if not repo_path.exists():
                return ValidationResult(
                    is_valid=False,
                    message=f"Path does not exist: {path}",
                    details={"error_type": "path_not_found", "path": str(repo_path)},
                )

            # Check if it's a directory
            if not repo_path.is_dir():
                return ValidationResult(
                    is_valid=False,
                    message=f"Path is not a directory: {path}",
                    details={"error_type": "not_directory", "path": str(repo_path)},
                )

            # Check if it's a Git repository by looking for .git directory or file
            git_path = repo_path / ".git"
            if not git_path.exists():
                return ValidationResult(
                    is_valid=False,
                    message=f"Not a Git repository: {path}",
                    details={"error_type": "not_git_repo", "path": str(repo_path)},
                )

            # Verify with git command
            try:
                result = subprocess.run(
                    ["git", "rev-parse", "--git-dir"],
                    cwd=str(repo_path),
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

                if result.returncode != 0:
                    return ValidationResult(
                        is_valid=False,
                        message=f"Invalid Git repository: {path}",
                        details={
                            "error_type": "git_validation_failed",
                            "path": str(repo_path),
                            "git_error": result.stderr.strip(),
                        },
                    )

            except subprocess.TimeoutExpired:
                return ValidationResult(
                    is_valid=False,
                    message=f"Git validation timed out for: {path}",
                    details={"error_type": "git_timeout", "path": str(repo_path)},
                )
            except FileNotFoundError:
                return ValidationResult(
                    is_valid=False,
                    message="Git command not found. Please ensure Git is installed.",
                    details={"error_type": "git_not_found"},
                )

            return ValidationResult(
                is_valid=True,
                message=f"Valid Git repository: {path}",
                details={"path": str(repo_path)},
            )

        except Exception as e:
            return ValidationResult(
                is_valid=False,
                message=f"Error validating repository: {str(e)}",
                details={"error_type": "validation_exception", "exception": str(e)},
            )

    def validate_worktree_path(self, path: str) -> ValidationResult:
        """
        Validate a worktree path for creation.

        Args:
            path: Path where worktree should be created

        Returns:
            ValidationResult indicating if the path is valid for worktree creation
        """
        if not path or not path.strip():
            return ValidationResult(
                is_valid=False,
                message="Worktree path cannot be empty",
                details={"error_type": "empty_path"},
            )

        try:
            worktree_path = Path(path).resolve()

            # Check if path already exists and validate it
            existing_path_result = self._validate_existing_path(worktree_path, path)
            if not existing_path_result.is_valid:
                return existing_path_result

            # Check parent directory
            parent_result = self._validate_parent_directory(worktree_path)
            if not parent_result.is_valid:
                return parent_result

            # Check for invalid characters
            chars_result = self._validate_path_characters(worktree_path, path)
            if not chars_result.is_valid:
                return chars_result

            return ValidationResult(
                is_valid=True,
                message=f"Valid worktree path: {path}",
                details={"path": str(worktree_path)},
            )

        except Exception as e:
            return ValidationResult(
                is_valid=False,
                message=f"Error validating worktree path: {str(e)}",
                details={"error_type": "validation_exception", "exception": str(e)},
            )

    def _validate_existing_path(
        self, worktree_path: Path, original_path: str
    ) -> ValidationResult:
        """Validate if existing path is suitable for worktree creation."""
        if not worktree_path.exists():
            return ValidationResult(is_valid=True, message="Path does not exist")

        if worktree_path.is_file():
            return ValidationResult(
                is_valid=False,
                message=f"Path exists as a file: {original_path}",
                details={"error_type": "path_is_file", "path": str(worktree_path)},
            )

        if worktree_path.is_dir() and any(worktree_path.iterdir()):
            return ValidationResult(
                is_valid=False,
                message=f"Directory is not empty: {original_path}",
                details={
                    "error_type": "directory_not_empty",
                    "path": str(worktree_path),
                },
            )

        return ValidationResult(is_valid=True, message="Existing path is valid")

    def _validate_parent_directory(self, worktree_path: Path) -> ValidationResult:
        """Validate parent directory exists and is writable."""
        parent_dir = worktree_path.parent

        if not parent_dir.exists():
            return ValidationResult(
                is_valid=False,
                message=f"Parent directory does not exist: {parent_dir}",
                details={"error_type": "parent_not_found", "parent": str(parent_dir)},
            )

        if not os.access(parent_dir, os.W_OK):
            return ValidationResult(
                is_valid=False,
                message=f"Parent directory is not writable: {parent_dir}",
                details={
                    "error_type": "parent_not_writable",
                    "parent": str(parent_dir),
                },
            )

        return ValidationResult(is_valid=True, message="Parent directory is valid")

    def _validate_path_characters(
        self, worktree_path: Path, original_path: str
    ) -> ValidationResult:
        """Validate path doesn't contain invalid characters."""
        invalid_chars = set('<>:"|?*') if os.name == "nt" else set("\0")

        if any(char in str(worktree_path) for char in invalid_chars):
            return ValidationResult(
                is_valid=False,
                message=f"Path contains invalid characters: {original_path}",
                details={
                    "error_type": "invalid_characters",
                    "path": str(worktree_path),
                },
            )

        return ValidationResult(is_valid=True, message="Path characters are valid")

    def validate_branch_name(self, branch: str) -> ValidationResult:
        """
        Validate a Git branch name according to Git naming rules.

        Args:
            branch: Branch name to validate

        Returns:
            ValidationResult indicating if the branch name is valid
        """
        if not branch or not branch.strip():
            return ValidationResult(
                is_valid=False,
                message="Branch name cannot be empty",
                details={"error_type": "empty_branch"},
            )

        branch = branch.strip()

        # Check length (Git has a limit, but we'll be more conservative)
        if len(branch) > 250:
            return ValidationResult(
                is_valid=False,
                message="Branch name is too long (max 250 characters)",
                details={"error_type": "branch_too_long", "length": len(branch)},
            )

        # Check against invalid patterns
        for pattern in self._invalid_branch_patterns:
            if pattern.search(branch):
                return ValidationResult(
                    is_valid=False,
                    message=f"Branch name contains invalid pattern: {branch}",
                    details={"error_type": "invalid_pattern", "branch": branch},
                )

        # Check if it matches valid pattern
        if not self.VALID_BRANCH_PATTERN.match(branch):
            return ValidationResult(
                is_valid=False,
                message=f"Branch name contains invalid characters: {branch}",
                details={"error_type": "invalid_characters", "branch": branch},
            )

        # Check for reserved names
        reserved_names = {"HEAD", "ORIG_HEAD", "FETCH_HEAD", "MERGE_HEAD"}
        if branch.upper() in reserved_names:
            return ValidationResult(
                is_valid=False,
                message=f"Branch name is reserved: {branch}",
                details={"error_type": "reserved_name", "branch": branch},
            )

        return ValidationResult(
            is_valid=True,
            message=f"Valid branch name: {branch}",
            details={"branch": branch},
        )

    def check_uncommitted_changes(self, worktree_path: str) -> ValidationResult:
        """
        Check if a worktree has uncommitted changes.

        Args:
            worktree_path: Path to the worktree to check

        Returns:
            ValidationResult indicating if there are uncommitted changes
        """
        if not worktree_path or not worktree_path.strip():
            return ValidationResult(
                is_valid=False,
                message="Worktree path cannot be empty",
                details={"error_type": "empty_path"},
            )

        try:
            path = Path(worktree_path).resolve()

            if not path.exists():
                return ValidationResult(
                    is_valid=False,
                    message=f"Worktree path does not exist: {worktree_path}",
                    details={"error_type": "path_not_found", "path": str(path)},
                )

            # Check git status
            try:
                result = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=str(path),
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                if result.returncode != 0:
                    return ValidationResult(
                        is_valid=False,
                        message=f"Failed to check Git status: {result.stderr.strip()}",
                        details={
                            "error_type": "git_status_failed",
                            "path": str(path),
                            "git_error": result.stderr.strip(),
                        },
                    )

                has_changes = bool(result.stdout.strip())

                return ValidationResult(
                    is_valid=True,
                    message="Successfully checked for uncommitted changes",
                    details={
                        "path": str(path),
                        "has_uncommitted_changes": has_changes,
                        "changes": result.stdout.strip() if has_changes else "",
                    },
                )

            except subprocess.TimeoutExpired:
                return ValidationResult(
                    is_valid=False,
                    message=f"Git status check timed out for: {worktree_path}",
                    details={"error_type": "git_timeout", "path": str(path)},
                )
            except FileNotFoundError:
                return ValidationResult(
                    is_valid=False,
                    message="Git command not found. Please ensure Git is installed.",
                    details={"error_type": "git_not_found"},
                )

        except Exception as e:
            return ValidationResult(
                is_valid=False,
                message=f"Error checking uncommitted changes: {str(e)}",
                details={"error_type": "validation_exception", "exception": str(e)},
            )

    def validate_command_safety(self, command: str) -> ValidationResult:
        """
        Validate that a command is safe to execute.

        Args:
            command: Command string to validate

        Returns:
            ValidationResult indicating if the command is safe to execute
        """
        if not command or not command.strip():
            return ValidationResult(
                is_valid=False,
                message="Command cannot be empty",
                details={"error_type": "empty_command"},
            )

        command = command.strip()

        # Check command length (prevent extremely long commands)
        if len(command) > 1000:
            return ValidationResult(
                is_valid=False,
                message="Command is too long (max 1000 characters)",
                details={"error_type": "command_too_long", "length": len(command)},
            )

        # Check against dangerous patterns
        for pattern in self._dangerous_patterns:
            if pattern.search(command):
                return ValidationResult(
                    is_valid=False,
                    message=f"Command contains potentially dangerous pattern: {command}",
                    details={
                        "error_type": "dangerous_command",
                        "command": command,
                        "reason": "Contains potentially harmful operations",
                    },
                )

        # Check for null bytes (can be used for injection)
        if "\0" in command:
            return ValidationResult(
                is_valid=False,
                message="Command contains null bytes",
                details={"error_type": "null_bytes", "command": command},
            )

        # Check for extremely long arguments (potential buffer overflow)
        args = command.split()
        for arg in args:
            if len(arg) > 500:
                return ValidationResult(
                    is_valid=False,
                    message="Command contains extremely long argument",
                    details={
                        "error_type": "long_argument",
                        "argument_length": len(arg),
                    },
                )

        return ValidationResult(
            is_valid=True,
            message=f"Command appears safe to execute: {command}",
            details={"command": command},
        )

    def validate_path_safety(self, path: str) -> ValidationResult:
        """
        Validate that a path is safe to use (no directory traversal, etc.).

        Args:
            path: Path to validate

        Returns:
            ValidationResult indicating if the path is safe
        """
        if not path or not path.strip():
            return ValidationResult(
                is_valid=False,
                message="Path cannot be empty",
                details={"error_type": "empty_path"},
            )

        try:
            # Resolve the path to detect directory traversal attempts
            resolved_path = Path(path).resolve()
            Path(path)

            # Check for directory traversal patterns
            if ".." in path or path.startswith("/"):
                # Allow absolute paths but be cautious about traversal
                if ".." in str(resolved_path):
                    return ValidationResult(
                        is_valid=False,
                        message=f"Path contains directory traversal: {path}",
                        details={"error_type": "directory_traversal", "path": path},
                    )

            # Check for suspicious patterns
            suspicious_patterns = [
                r"\.\./",  # Directory traversal
                r"/\.\.",  # Directory traversal
                r"~/",  # Home directory (could be risky)
                r"/etc/",  # System directory
                r"/var/",  # System directory
                r"/usr/",  # System directory
                r"/bin/",  # System directory
                r"/sbin/",  # System directory
                r"/root/",  # Root directory
            ]

            for pattern in suspicious_patterns:
                if re.search(pattern, path, re.IGNORECASE):
                    return ValidationResult(
                        is_valid=False,
                        message=f"Path contains suspicious pattern: {path}",
                        details={"error_type": "suspicious_path", "path": path},
                    )

            return ValidationResult(
                is_valid=True,
                message=f"Path appears safe: {path}",
                details={"path": str(resolved_path)},
            )

        except Exception as e:
            return ValidationResult(
                is_valid=False,
                message=f"Error validating path safety: {str(e)}",
                details={"error_type": "validation_exception", "exception": str(e)},
            )
