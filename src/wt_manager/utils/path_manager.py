"""OS-specific path management utilities."""

import os
import stat
import sys
from pathlib import Path

from ..utils.exceptions import PathError


class PathManager:
    """Manages OS-specific paths for configuration, logs, and cache."""

    APP_NAME = "GitWorktreeManager"

    @staticmethod
    def get_config_dir() -> Path:
        """
        Get OS-appropriate configuration directory.

        Returns:
            Path to configuration directory
        """
        if sys.platform == "darwin":  # macOS
            base_dir = Path.home() / "Library" / "Application Support"
        elif sys.platform == "win32":  # Windows
            base_dir = Path.home() / "AppData" / "Roaming"
        else:  # Linux and other Unix-like systems
            base_dir = Path.home() / ".config"

        return base_dir / PathManager.APP_NAME

    @staticmethod
    def get_log_dir() -> Path:
        """
        Get OS-appropriate log directory.

        Returns:
            Path to log directory
        """
        if sys.platform == "darwin":  # macOS
            base_dir = Path.home() / "Library" / "Logs"
        elif sys.platform == "win32":  # Windows
            base_dir = Path.home() / "AppData" / "Local" / PathManager.APP_NAME / "Logs"
        else:  # Linux and other Unix-like systems
            base_dir = (
                Path.home() / ".local" / "share" / "git-worktree-manager" / "logs"
            )

        return base_dir / PathManager.APP_NAME if sys.platform != "win32" else base_dir

    @staticmethod
    def get_cache_dir() -> Path:
        """
        Get OS-appropriate cache directory.

        Returns:
            Path to cache directory
        """
        if sys.platform == "darwin":  # macOS
            base_dir = Path.home() / "Library" / "Caches"
        elif sys.platform == "win32":  # Windows
            base_dir = (
                Path.home() / "AppData" / "Local" / PathManager.APP_NAME / "Cache"
            )
        else:  # Linux and other Unix-like systems
            base_dir = Path.home() / ".cache"

        return base_dir / PathManager.APP_NAME if sys.platform != "win32" else base_dir

    @staticmethod
    def ensure_directories() -> None:
        """
        Create necessary directories if they don't exist.

        Raises:
            PathError: If directories cannot be created or permissions are insufficient
        """
        directories = [
            PathManager.get_config_dir(),
            PathManager.get_log_dir(),
            PathManager.get_cache_dir(),
        ]

        for directory in directories:
            try:
                directory.mkdir(parents=True, exist_ok=True)
                # Validate directory permissions after creation
                PathManager.validate_directory_permissions(directory)
            except (OSError, PermissionError) as e:
                raise PathError(f"Failed to create directory {directory}: {e}") from e

    @staticmethod
    def get_config_file(filename: str) -> Path:
        """
        Get path to a configuration file.

        Args:
            filename: Name of the configuration file

        Returns:
            Path to the configuration file
        """
        return PathManager.get_config_dir() / filename

    @staticmethod
    def get_log_file(filename: str) -> Path:
        """
        Get path to a log file.

        Args:
            filename: Name of the log file

        Returns:
            Path to the log file
        """
        return PathManager.get_log_dir() / filename

    @staticmethod
    def get_cache_file(filename: str) -> Path:
        """
        Get path to a cache file.

        Args:
            filename: Name of the cache file

        Returns:
            Path to the cache file
        """
        return PathManager.get_cache_dir() / filename

    @staticmethod
    def sanitize_path(path: str) -> str:
        """
        Sanitize a path string to prevent directory traversal attacks.

        Args:
            path: Path string to sanitize

        Returns:
            Sanitized path string

        Raises:
            PathError: If path contains invalid characters or patterns
        """
        if not path or not isinstance(path, str):
            raise PathError("Path must be a non-empty string")

        # Check for null bytes and other dangerous characters
        if "\x00" in path:
            raise PathError("Path contains null bytes")

        # Store original to check if it was absolute
        was_absolute = path.startswith("/") or path.startswith("~")

        # Remove any path traversal attempts
        sanitized = path.replace("..", "")

        # Remove ~ only if it's not at the start (preserve home directory expansion)
        if not path.startswith("~"):
            sanitized = sanitized.replace("~", "")

        # Normalize path separators
        sanitized = sanitized.replace("\\", "/")

        # Remove leading/trailing whitespace
        sanitized = sanitized.strip()

        # Remove leading/trailing slashes unless it was originally absolute
        if not was_absolute:
            sanitized = sanitized.strip("/")
        elif sanitized.startswith("/"):
            # For absolute paths, remove extra leading slashes but keep one
            sanitized = "/" + sanitized.lstrip("/")
            # Remove trailing slashes
            sanitized = sanitized.rstrip("/")
            # But don't let root become empty
            if sanitized == "":
                sanitized = "/"

        # Check for empty result after sanitization
        if not sanitized:
            raise PathError("Path becomes empty after sanitization")

        return sanitized

    @staticmethod
    def is_safe_path(path: Path, base_path: Path) -> bool:
        """
        Check if a path is safe (within the base path).

        Args:
            path: Path to check
            base_path: Base path that should contain the path

        Returns:
            True if path is safe, False otherwise
        """
        try:
            # Resolve both paths to absolute paths
            abs_path = path.resolve()
            abs_base = base_path.resolve()

            # Check if the path is within the base path
            return abs_base in abs_path.parents or abs_path == abs_base
        except (OSError, ValueError):
            return False

    @staticmethod
    def validate_directory_permissions(directory: Path) -> None:
        """
        Validate that a directory has appropriate read/write permissions.

        Args:
            directory: Directory path to validate

        Raises:
            PathError: If directory doesn't exist or lacks required permissions
        """
        if not directory.exists():
            raise PathError(f"Directory does not exist: {directory}")

        if not directory.is_dir():
            raise PathError(f"Path is not a directory: {directory}")

        # Check read permission
        if not os.access(directory, os.R_OK):
            raise PathError(f"Directory is not readable: {directory}")

        # Check write permission
        if not os.access(directory, os.W_OK):
            raise PathError(f"Directory is not writable: {directory}")

    @staticmethod
    def validate_path_writable(path: Path) -> bool:
        """
        Check if a path is writable (either exists and is writable, or parent is writable).

        Args:
            path: Path to check

        Returns:
            True if path is writable, False otherwise
        """
        try:
            if path.exists():
                return os.access(path, os.W_OK)
            else:
                # Check if parent directory is writable
                parent = path.parent
                return parent.exists() and os.access(parent, os.W_OK)
        except (OSError, ValueError):
            return False

    @staticmethod
    def create_directory_safe(directory: Path, mode: int | None = None) -> None:
        """
        Safely create a directory with proper permissions.

        Args:
            directory: Directory path to create
            mode: Optional file mode (permissions) for the directory

        Raises:
            PathError: If directory cannot be created
        """
        try:
            directory.mkdir(parents=True, exist_ok=True)

            # Set permissions if specified
            if mode is not None:
                directory.chmod(mode)
            elif sys.platform != "win32":
                # Set secure permissions on Unix-like systems (owner read/write/execute only)
                directory.chmod(stat.S_IRWXU)

            # Validate the created directory
            PathManager.validate_directory_permissions(directory)

        except (OSError, PermissionError) as e:
            raise PathError(f"Failed to create directory {directory}: {e}") from e

    @staticmethod
    def get_safe_filename(filename: str) -> str:
        """
        Convert a string to a safe filename by removing/replacing invalid characters.

        Args:
            filename: Original filename

        Returns:
            Safe filename string
        """
        if not filename:
            return "unnamed"

        # Characters that are invalid in filenames on various OS
        invalid_chars = '<>:"/\\|?*'

        # Replace invalid characters with underscores
        safe_name = filename
        for char in invalid_chars:
            safe_name = safe_name.replace(char, "_")

        # Remove control characters
        safe_name = "".join(char for char in safe_name if ord(char) >= 32)

        # Trim whitespace and dots (problematic on Windows)
        safe_name = safe_name.strip(". ")

        # Ensure it's not empty after cleaning
        if not safe_name:
            return "unnamed"

        # Truncate if too long (255 is typical filesystem limit)
        if len(safe_name) > 255:
            safe_name = safe_name[:255]

        return safe_name

    @staticmethod
    def _validate_traversal_attempt(path: str, base_path: Path | None) -> None:
        """
        Validate path for directory traversal attempts.

        Args:
            path: Path string to validate
            base_path: Optional base path for validation

        Raises:
            PathError: If path contains unsafe traversal
        """
        if not base_path or ".." not in path:
            return

        temp_path = Path(path)
        if not temp_path.is_absolute():
            temp_path = base_path / temp_path

        try:
            resolved_temp = temp_path.resolve()
            if not PathManager.is_safe_path(resolved_temp, base_path.resolve()):
                raise PathError(
                    f"Path {path} resolves outside of base path {base_path}"
                )
        except (OSError, ValueError):
            # If resolution fails, we'll catch it later in main function
            pass

    @staticmethod
    def _resolve_with_base(path_obj: Path, base_path: Path | None) -> Path:
        """
        Resolve path object with optional base path.

        Args:
            path_obj: Path object to resolve
            base_path: Optional base path for relative paths

        Returns:
            Resolved Path object
        """
        if not path_obj.is_absolute() and base_path:
            path_obj = base_path / path_obj
        return path_obj.resolve()

    @staticmethod
    def _validate_final_path(resolved: Path, path: str, base_path: Path | None) -> None:
        """
        Perform final safety validation on resolved path.

        Args:
            resolved: Resolved path to validate
            path: Original path string for error messages
            base_path: Optional base path for validation

        Raises:
            PathError: If path is unsafe
        """
        if base_path and not PathManager.is_safe_path(resolved, base_path.resolve()):
            raise PathError(f"Path {path} resolves outside of base path {base_path}")

    @staticmethod
    def resolve_path_safely(path: str, base_path: Path | None = None) -> Path:
        """
        Safely resolve a path string to a Path object with validation.

        Args:
            path: Path string to resolve
            base_path: Optional base path for relative paths

        Returns:
            Resolved Path object

        Raises:
            PathError: If path is invalid or unsafe
        """
        try:
            # Check for obvious traversal attempts before sanitization
            PathManager._validate_traversal_attempt(path, base_path)

            # Sanitize the input path
            sanitized = PathManager.sanitize_path(path)
            path_obj = Path(sanitized)

            # Resolve path with optional base
            resolved = PathManager._resolve_with_base(path_obj, base_path)

            # Final safety check after sanitization
            PathManager._validate_final_path(resolved, path, base_path)

            return resolved

        except (OSError, ValueError) as e:
            raise PathError(f"Invalid path {path}: {e}") from e
