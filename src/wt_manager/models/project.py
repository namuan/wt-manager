"""Project data model for Git Worktree Manager."""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from .worktree import Worktree


class ProjectStatus(Enum):
    """Status enumeration for projects."""

    ACTIVE = "active"
    MODIFIED = "modified"
    INACTIVE = "inactive"
    ERROR = "error"
    UNAVAILABLE = "unavailable"


@dataclass
class Project:
    """
    Represents a Git project with its associated worktrees.

    Attributes:
        id: Unique identifier for the project
        name: Display name of the project
        path: Filesystem path to the Git repository
        status: Current status of the project
        last_accessed: Timestamp of last access
        worktrees: List of associated worktrees
    """

    id: str
    name: str
    path: str
    status: ProjectStatus
    last_accessed: datetime
    worktrees: list[Worktree] = field(default_factory=list)

    def __post_init__(self):
        """Post-initialization validation and setup."""
        if not self.id:
            self.id = str(uuid.uuid4())

        # Ensure path is absolute and normalized
        self.path = str(Path(self.path).resolve())

        # Validate the project on creation
        if not self._validate_basic_structure():
            self.status = ProjectStatus.ERROR

    def is_valid(self) -> bool:
        """
        Check if the project is valid and accessible.

        Returns:
            bool: True if project is valid, False otherwise
        """
        return self._validate_basic_structure() and self._validate_git_repository()

    def _validate_basic_structure(self) -> bool:
        """Validate basic project structure."""
        if not self.name or not self.path:
            return False

        path_obj = Path(self.path)
        return path_obj.exists() and path_obj.is_dir()

    def _validate_git_repository(self) -> bool:
        """Validate that the path contains a Git repository."""
        git_dir = Path(self.path) / ".git"
        return git_dir.exists()

    def get_display_name(self) -> str:
        """
        Get the display name for the project.

        Returns:
            str: Display name, falls back to directory name if name is empty
        """
        if self.name:
            return self.name
        return Path(self.path).name

    def refresh_worktrees(self) -> None:
        """
        Refresh the worktrees list for this project.
        Note: This method signature is defined for interface compatibility.
        Actual implementation will be handled by the WorktreeService.
        """
        # This will be implemented by the service layer
        pass

    def add_worktree(self, worktree: Worktree) -> None:
        """
        Add a worktree to this project.

        Args:
            worktree: Worktree instance to add
        """
        if worktree not in self.worktrees:
            self.worktrees.append(worktree)

    def remove_worktree(self, worktree_path: str) -> bool:
        """
        Remove a worktree from this project.

        Args:
            worktree_path: Path of the worktree to remove

        Returns:
            bool: True if worktree was found and removed, False otherwise
        """
        for i, worktree in enumerate(self.worktrees):
            if worktree.path == worktree_path:
                del self.worktrees[i]
                return True
        return False

    def get_worktree_by_path(self, path: str) -> Worktree | None:
        """
        Get a worktree by its path.

        Args:
            path: Path of the worktree to find

        Returns:
            Optional[Worktree]: Worktree if found, None otherwise
        """
        for worktree in self.worktrees:
            if worktree.path == path:
                return worktree
        return None

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize the project to a dictionary.

        Returns:
            Dict[str, Any]: Serialized project data
        """
        return {
            "id": self.id,
            "name": self.name,
            "path": self.path,
            "status": self.status.value,
            "last_accessed": self.last_accessed.isoformat(),
            "worktrees": [worktree.to_dict() for worktree in self.worktrees],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Project":
        """
        Deserialize a project from a dictionary.

        Args:
            data: Dictionary containing project data

        Returns:
            Project: Deserialized project instance
        """
        worktrees = [
            Worktree.from_dict(wt_data) for wt_data in data.get("worktrees", [])
        ]

        return cls(
            id=data["id"],
            name=data["name"],
            path=data["path"],
            status=ProjectStatus(data["status"]),
            last_accessed=datetime.fromisoformat(data["last_accessed"]),
            worktrees=worktrees,
        )

    def to_json(self) -> str:
        """
        Serialize the project to JSON string.

        Returns:
            str: JSON representation of the project
        """
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "Project":
        """
        Deserialize a project from JSON string.

        Args:
            json_str: JSON string containing project data

        Returns:
            Project: Deserialized project instance
        """
        data = json.loads(json_str)
        return cls.from_dict(data)

    def __eq__(self, other) -> bool:
        """Check equality based on project ID."""
        if not isinstance(other, Project):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        """Hash based on project ID."""
        return hash(self.id)

    def __str__(self) -> str:
        """String representation of the project."""
        return f"Project(name='{self.get_display_name()}', path='{self.path}', status={self.status.value})"

    def __repr__(self) -> str:
        """Detailed string representation of the project."""
        return (
            f"Project(id='{self.id}', name='{self.name}', path='{self.path}', "
            f"status={self.status.value}, worktrees={len(self.worktrees)})"
        )
