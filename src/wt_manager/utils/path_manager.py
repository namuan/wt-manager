"""OS-specific path management utilities."""

import sys
from pathlib import Path


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
        """Create necessary directories if they don't exist."""
        directories = [
            PathManager.get_config_dir(),
            PathManager.get_log_dir(),
            PathManager.get_cache_dir(),
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

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
        """
        # Remove any path traversal attempts
        sanitized = path.replace("..", "").replace("~", "")

        # Normalize path separators
        sanitized = sanitized.replace("\\", "/")

        # Remove leading/trailing whitespace and path separators
        sanitized = sanitized.strip().strip("/")

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
