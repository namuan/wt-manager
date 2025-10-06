"""Test cases for the data models."""

import tempfile
from datetime import datetime
from pathlib import Path


from wt_manager.models import Project, ProjectStatus, Worktree


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
