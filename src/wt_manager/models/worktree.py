"""Worktree data model for Git Worktree Manager."""

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class Worktree:
    """
    Represents a Git worktree with its associated metadata.

    Attributes:
        path: Filesystem path to the worktree
        branch: Git branch associated with the worktree
        commit_hash: Current commit hash of the worktree
        is_bare: Whether this is a bare worktree
        is_detached: Whether the worktree is in detached HEAD state
        has_uncommitted_changes: Whether there are uncommitted changes
        last_modified: Timestamp of last modification
    """

    path: str
    branch: str
    commit_hash: str
    is_bare: bool = False
    is_detached: bool = False
    has_uncommitted_changes: bool = False
    last_modified: datetime = None

    def __post_init__(self):
        """Post-initialization setup."""
        # Ensure path is absolute and normalized
        self.path = str(Path(self.path).resolve())

        # Set default last_modified if not provided
        if self.last_modified is None:
            self.last_modified = datetime.now()

    def get_status_display(self) -> str:
        """
        Get a human-readable status display string.

        Returns:
            str: Status display string with indicators
        """
        status_parts = []

        if self.is_bare:
            status_parts.append("bare")

        if self.is_detached:
            status_parts.append("detached")

        if self.has_uncommitted_changes:
            status_parts.append("modified")

        if not status_parts:
            status_parts.append("clean")

        return " | ".join(status_parts)

    def is_current_directory(self) -> bool:
        """
        Check if this worktree is the current working directory.

        Returns:
            bool: True if this worktree is the current directory
        """
        try:
            current_dir = Path.cwd().resolve()
            worktree_path = Path(self.path).resolve()

            # Check if current directory is within the worktree
            try:
                current_dir.relative_to(worktree_path)
                return True
            except ValueError:
                return False
        except (OSError, RuntimeError):
            return False

    def get_relative_path(self, base_path: str) -> str:
        """
        Get the relative path from a base path.

        Args:
            base_path: Base path to calculate relative path from

        Returns:
            str: Relative path string
        """
        try:
            worktree_path = Path(self.path)
            base = Path(base_path)
            return str(worktree_path.relative_to(base))
        except ValueError:
            # If paths are not related, return the absolute path
            return self.path

    def get_directory_name(self) -> str:
        """
        Get the directory name of the worktree.

        Returns:
            str: Directory name
        """
        return Path(self.path).name

    def exists(self) -> bool:
        """
        Check if the worktree path exists on the filesystem.

        Returns:
            bool: True if the worktree path exists
        """
        return Path(self.path).exists()

    def is_accessible(self) -> bool:
        """
        Check if the worktree is accessible (exists and readable).

        Returns:
            bool: True if the worktree is accessible
        """
        path_obj = Path(self.path)
        return path_obj.exists() and os.access(path_obj, os.R_OK)

    def get_branch_display(self) -> str:
        """
        Get a display-friendly branch name.

        Returns:
            str: Branch name with status indicators
        """
        if self.is_detached:
            return f"({self.commit_hash[:8]})"
        return self.branch

    def get_commit_short_hash(self) -> str:
        """
        Get the short version of the commit hash.

        Returns:
            str: Short commit hash (first 8 characters)
        """
        return self.commit_hash[:8] if self.commit_hash else ""

    def get_age_display(self) -> str:
        """
        Get a human-readable age display.

        Returns:
            str: Age display string (e.g., "2 hours ago", "3 days ago")
        """
        if not self.last_modified:
            return "unknown"

        now = datetime.now()
        delta = now - self.last_modified

        if delta.days > 0:
            return f"{delta.days} day{'s' if delta.days != 1 else ''} ago"
        elif delta.seconds > 3600:
            hours = delta.seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif delta.seconds > 60:
            minutes = delta.seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        else:
            return "just now"

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize the worktree to a dictionary.

        Returns:
            Dict[str, Any]: Serialized worktree data
        """
        return {
            "path": self.path,
            "branch": self.branch,
            "commit_hash": self.commit_hash,
            "is_bare": self.is_bare,
            "is_detached": self.is_detached,
            "has_uncommitted_changes": self.has_uncommitted_changes,
            "last_modified": self.last_modified.isoformat()
            if self.last_modified
            else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Worktree":
        """
        Deserialize a worktree from a dictionary.

        Args:
            data: Dictionary containing worktree data

        Returns:
            Worktree: Deserialized worktree instance
        """
        last_modified = None
        if data.get("last_modified"):
            last_modified = datetime.fromisoformat(data["last_modified"])

        return cls(
            path=data["path"],
            branch=data["branch"],
            commit_hash=data["commit_hash"],
            is_bare=data.get("is_bare", False),
            is_detached=data.get("is_detached", False),
            has_uncommitted_changes=data.get("has_uncommitted_changes", False),
            last_modified=last_modified,
        )

    def to_json(self) -> str:
        """
        Serialize the worktree to JSON string.

        Returns:
            str: JSON representation of the worktree
        """
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "Worktree":
        """
        Deserialize a worktree from JSON string.

        Args:
            json_str: JSON string containing worktree data

        Returns:
            Worktree: Deserialized worktree instance
        """
        data = json.loads(json_str)
        return cls.from_dict(data)

    def __eq__(self, other) -> bool:
        """Check equality based on worktree path."""
        if not isinstance(other, Worktree):
            return False
        return self.path == other.path

    def __hash__(self) -> int:
        """Hash based on worktree path."""
        return hash(self.path)

    def __str__(self) -> str:
        """String representation of the worktree."""
        return f"Worktree(path='{self.get_directory_name()}', branch='{self.get_branch_display()}')"

    def __repr__(self) -> str:
        """Detailed string representation of the worktree."""
        return (
            f"Worktree(path='{self.path}', branch='{self.branch}', "
            f"commit='{self.get_commit_short_hash()}', status='{self.get_status_display()}')"
        )
