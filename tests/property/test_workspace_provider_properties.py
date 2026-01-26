"""
Property-based tests for workspace provider adapters.

These tests verify universal properties for workspace isolation that should
hold across all valid executions.

Requirements: 1.2, 6.1, 6.2, 6.3, 6.4
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

from lean_proof_auto_mcp.adapters.workspace_provider import (
    GitWorktreeProvider,
    TempCopyProvider,
    create_workspace_provider,
    detect_workspace_mode,
)

# ============================================================================
# Helper Functions
# ============================================================================


def create_temp_git_repo():
    """Create a temporary git repository for testing."""
    temp_dir = Path(tempfile.mkdtemp(prefix="test_git_repo_"))
    repo_dir = temp_dir / "test_repo"
    repo_dir.mkdir()

    # Initialize git repo
    subprocess.run(
        ["git", "init"],
        cwd=repo_dir,
        capture_output=True,
        check=True,
    )

    # Configure git user
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_dir,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_dir,
        capture_output=True,
        check=True,
    )

    # Create a test file
    test_file = repo_dir / "test.lean"
    test_file.write_text("-- Test file\n")

    # Commit the file
    subprocess.run(
        ["git", "add", "."],
        cwd=repo_dir,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo_dir,
        capture_output=True,
        check=True,
    )

    return repo_dir


def create_temp_project_dir():
    """Create a temporary project directory (non-git) for testing."""
    temp_dir = Path(tempfile.mkdtemp(prefix="test_project_"))
    project_dir = temp_dir / "test_project"
    project_dir.mkdir()

    # Create some test files
    (project_dir / "test.lean").write_text("-- Test file\n")
    (project_dir / "subdir").mkdir()
    (project_dir / "subdir" / "test2.lean").write_text("-- Test file 2\n")

    return project_dir


def cleanup_temp_dir(path: Path):
    """Clean up temporary directory."""
    try:
        if path.exists():
            shutil.rmtree(
                path.parent if path.name == "test_repo" or path.name == "test_project" else path
            )
    except Exception:
        pass  # Ignore cleanup errors


# ============================================================================
# Property Tests
# ============================================================================


class TestProperty3WorkspaceIsolation:
    """
    Property 3: Workspace Isolation

    For any verification request, the tool SHALL create an isolated workspace
    and SHALL NOT modify any files in the original working tree.

    Feature: lean-verify-tool, Property 3: Workspace isolation
    Validates: Requirements 1.2, 6.1, 6.2
    """

    # Class-level shared git repo to avoid recreating for each test iteration
    _shared_git_repo = None
    _shared_project_dir = None

    @classmethod
    def setup_class(cls):
        """Create shared test repositories once for all tests."""
        cls._shared_git_repo = create_temp_git_repo()
        cls._shared_project_dir = create_temp_project_dir()

    @classmethod
    def teardown_class(cls):
        """Clean up shared test repositories."""
        if cls._shared_git_repo:
            cleanup_temp_dir(cls._shared_git_repo)
        if cls._shared_project_dir:
            cleanup_temp_dir(cls._shared_project_dir)

    def test_git_worktree_creates_isolated_workspace(self):
        """Test that GitWorktreeProvider creates isolated workspace."""
        # Feature: lean-verify-tool, Property 3: Workspace isolation

        # Arrange - Use shared git repo
        temp_git_repo = self._shared_git_repo
        worktree_dir = temp_git_repo / ".worktrees"
        provider = GitWorktreeProvider(worktree_dir, project_root=temp_git_repo)

        # Get original file content
        original_file = temp_git_repo / "test.lean"
        original_content = original_file.read_text()

        # Act
        workspace = provider.create_workspace("test_file.lean")

        try:
            # Assert - Workspace is created
            assert workspace.path.exists()
            assert workspace.path.is_dir()
            assert workspace.mode == "worktree"
            assert workspace.workspace_id.startswith("worktree-")

            # Assert - Workspace is isolated (different path)
            assert workspace.path != temp_git_repo
            assert workspace.path.parent == worktree_dir

            # Assert - Original file is unchanged
            assert original_file.read_text() == original_content

            # Assert - Workspace contains the file (git worktree shares the same files)
            workspace_file = workspace.path / "test.lean"
            assert workspace_file.exists(), f"File should exist in worktree: {workspace_file}"

            # Verify workspace file has same content initially
            assert workspace_file.read_text() == original_content

            # Modify file in workspace
            workspace_file.write_text("-- Modified in workspace\n")

            # Assert - Original file is still unchanged (worktrees are isolated)
            assert original_file.read_text() == original_content

        finally:
            # Cleanup
            provider.cleanup_workspace(workspace)

    def test_temp_copy_creates_isolated_workspace(self):
        """Test that TempCopyProvider creates isolated workspace."""
        # Feature: lean-verify-tool, Property 3: Workspace isolation

        # Arrange - Use shared project dir
        temp_project_dir = self._shared_project_dir
        provider = TempCopyProvider(temp_project_dir)

        # Get original file content
        original_file = temp_project_dir / "test.lean"
        original_content = original_file.read_text()

        # Act
        workspace = provider.create_workspace("test_file.lean")

        try:
            # Assert - Workspace is created
            assert workspace.path.exists()
            assert workspace.path.is_dir()
            assert workspace.mode == "temp"
            assert workspace.workspace_id.startswith("temp-")

            # Assert - Workspace is isolated (different path)
            assert workspace.path != temp_project_dir

            # Assert - Original file is unchanged
            assert original_file.read_text() == original_content

            # Assert - Workspace contains the file
            workspace_file = workspace.path / "test.lean"
            assert workspace_file.exists()

            # Modify file in workspace
            workspace_file.write_text("-- Modified in workspace\n")

            # Assert - Original file is still unchanged
            assert original_file.read_text() == original_content

        finally:
            # Cleanup
            provider.cleanup_workspace(workspace)

    def test_workspace_cleanup_removes_workspace(self):
        """Test that workspace cleanup removes the workspace directory."""
        # Feature: lean-verify-tool, Property 3: Workspace isolation

        # Arrange - Use shared git repo
        temp_git_repo = self._shared_git_repo
        worktree_dir = temp_git_repo / ".worktrees"
        provider = GitWorktreeProvider(worktree_dir, project_root=temp_git_repo)

        # Act
        workspace = provider.create_workspace("test_file.lean")
        workspace_path = workspace.path

        # Assert - Workspace exists before cleanup
        assert workspace_path.exists()

        # Cleanup
        provider.cleanup_workspace(workspace)

        # Assert - Workspace is removed after cleanup
        assert not workspace_path.exists()

    def test_temp_workspace_cleanup_removes_workspace(self):
        """Test that temp workspace cleanup removes the workspace directory."""
        # Feature: lean-verify-tool, Property 3: Workspace isolation

        # Arrange - Use shared project dir
        temp_project_dir = self._shared_project_dir
        provider = TempCopyProvider(temp_project_dir)

        # Act
        workspace = provider.create_workspace("test_file.lean")
        workspace_path = workspace.path

        # Assert - Workspace exists before cleanup
        assert workspace_path.exists()

        # Cleanup
        provider.cleanup_workspace(workspace)

        # Assert - Workspace is removed after cleanup
        assert not workspace_path.exists()

    def test_multiple_workspaces_are_isolated_from_each_other(self):
        """Test that multiple workspaces don't interfere with each other."""
        # Feature: lean-verify-tool, Property 3: Workspace isolation

        # Arrange - Use shared git repo
        temp_git_repo = self._shared_git_repo
        worktree_dir = temp_git_repo / ".worktrees"
        provider = GitWorktreeProvider(worktree_dir, project_root=temp_git_repo)

        # Act - Create multiple workspaces
        workspace1 = provider.create_workspace("test1.lean")
        workspace2 = provider.create_workspace("test2.lean")

        try:
            # Assert - Workspaces have different paths
            assert workspace1.path != workspace2.path
            assert workspace1.workspace_id != workspace2.workspace_id

            # Assert - Both workspaces exist
            assert workspace1.path.exists()
            assert workspace2.path.exists()

            # Assert - Both workspaces have the test file
            file1 = workspace1.path / "test.lean"
            file2 = workspace2.path / "test.lean"
            assert file1.exists(), f"File should exist in workspace1: {file1}"
            assert file2.exists(), f"File should exist in workspace2: {file2}"

            # Get original content
            original_content = "-- Test file\n"
            assert file1.read_text() == original_content
            assert file2.read_text() == original_content

            # Modify file in workspace1
            file1.write_text("-- Modified in workspace1\n")

            # Assert - File in workspace2 is unchanged
            assert file2.read_text() == original_content

        finally:
            # Cleanup
            provider.cleanup_workspace(workspace1)
            provider.cleanup_workspace(workspace2)


class TestProperty15ConcurrentExecutionSafety:
    """
    Property 15: Concurrent Execution Safety

    For any set of N concurrent verification requests, each SHALL complete
    successfully with isolated workspaces, and no verification SHALL interfere
    with another (no shared state, no race conditions).

    Feature: lean-verify-tool, Property 15: Concurrent execution safety
    Validates: Requirements 6.4
    """

    # Class-level shared repos
    _shared_git_repo = None
    _shared_project_dir = None

    @classmethod
    def setup_class(cls):
        """Create shared test repositories once for all tests."""
        cls._shared_git_repo = create_temp_git_repo()
        cls._shared_project_dir = create_temp_project_dir()

    @classmethod
    def teardown_class(cls):
        """Clean up shared test repositories."""
        if cls._shared_git_repo:
            cleanup_temp_dir(cls._shared_git_repo)
        if cls._shared_project_dir:
            cleanup_temp_dir(cls._shared_project_dir)

    def test_concurrent_workspace_creation_is_safe(self):
        """Test that concurrent workspace creation doesn't cause collisions."""
        # Feature: lean-verify-tool, Property 15: Concurrent execution safety

        # Arrange - Use shared git repo
        temp_git_repo = self._shared_git_repo
        worktree_dir = temp_git_repo / ".worktrees"
        provider = GitWorktreeProvider(worktree_dir, project_root=temp_git_repo)

        # Act - Create multiple workspaces (simulating concurrent requests)
        num_concurrent = 3
        workspaces = []
        for i in range(num_concurrent):
            workspace = provider.create_workspace(f"test{i}.lean")
            workspaces.append(workspace)

        try:
            # Assert - All workspaces have unique IDs
            workspace_ids = [w.workspace_id for w in workspaces]
            assert len(workspace_ids) == len(set(workspace_ids)), "Workspace IDs are not unique"

            # Assert - All workspaces have unique paths
            workspace_paths = [w.path for w in workspaces]
            assert len(workspace_paths) == len(set(workspace_paths)), (
                "Workspace paths are not unique"
            )

            # Assert - All workspaces exist
            for workspace in workspaces:
                assert workspace.path.exists()

        finally:
            # Cleanup all workspaces
            for workspace in workspaces:
                provider.cleanup_workspace(workspace)

    def test_concurrent_temp_workspace_creation_is_safe(self):
        """Test that concurrent temp workspace creation doesn't cause collisions."""
        # Feature: lean-verify-tool, Property 15: Concurrent execution safety

        # Arrange - Use shared project dir
        temp_project_dir = self._shared_project_dir
        provider = TempCopyProvider(temp_project_dir)

        # Act - Create multiple workspaces (simulating concurrent requests)
        num_concurrent = 3
        workspaces = []
        for i in range(num_concurrent):
            workspace = provider.create_workspace(f"test{i}.lean")
            workspaces.append(workspace)

        try:
            # Assert - All workspaces have unique IDs
            workspace_ids = [w.workspace_id for w in workspaces]
            assert len(workspace_ids) == len(set(workspace_ids)), "Workspace IDs are not unique"

            # Assert - All workspaces have unique paths
            workspace_paths = [w.path for w in workspaces]
            assert len(workspace_paths) == len(set(workspace_paths)), (
                "Workspace paths are not unique"
            )

            # Assert - All workspaces exist
            for workspace in workspaces:
                assert workspace.path.exists()

        finally:
            # Cleanup all workspaces
            for workspace in workspaces:
                provider.cleanup_workspace(workspace)


# ============================================================================
# Unit Tests for Workspace Mode Detection
# ============================================================================


class TestWorkspaceModeDetection:
    """
    Tests for workspace mode auto-detection.

    Validates: Requirements 6.5
    """

    def test_detect_workspace_mode_with_git_repo(self):
        """Test that git repositories are detected correctly."""
        temp_git_repo = create_temp_git_repo()

        try:
            # Act
            mode = detect_workspace_mode(temp_git_repo)

            # Assert
            assert mode == "worktree"

        finally:
            cleanup_temp_dir(temp_git_repo)

    def test_detect_workspace_mode_without_git_repo(self):
        """Test that non-git directories are detected correctly."""
        temp_project_dir = create_temp_project_dir()

        try:
            # Act
            mode = detect_workspace_mode(temp_project_dir)

            # Assert
            assert mode == "temp"

        finally:
            cleanup_temp_dir(temp_project_dir)

    def test_create_workspace_provider_auto_detects_git(self):
        """Test that factory auto-detects git repository."""
        temp_git_repo = create_temp_git_repo()

        try:
            # Act
            provider = create_workspace_provider(
                workspace_mode=None,
                project_root=temp_git_repo,
            )

            # Assert
            assert isinstance(provider, GitWorktreeProvider)

        finally:
            cleanup_temp_dir(temp_git_repo)

    def test_create_workspace_provider_auto_detects_temp(self):
        """Test that factory auto-detects non-git directory."""
        temp_project_dir = create_temp_project_dir()

        try:
            # Act
            provider = create_workspace_provider(
                workspace_mode=None,
                project_root=temp_project_dir,
            )

            # Assert
            assert isinstance(provider, TempCopyProvider)

        finally:
            cleanup_temp_dir(temp_project_dir)

    def test_create_workspace_provider_explicit_worktree(self):
        """Test that factory respects explicit worktree mode."""
        temp_git_repo = create_temp_git_repo()

        try:
            # Act
            provider = create_workspace_provider(
                workspace_mode="worktree",
                project_root=temp_git_repo,
            )

            # Assert
            assert isinstance(provider, GitWorktreeProvider)

        finally:
            cleanup_temp_dir(temp_git_repo)

    def test_create_workspace_provider_explicit_temp(self):
        """Test that factory respects explicit temp mode."""
        temp_project_dir = create_temp_project_dir()

        try:
            # Act
            provider = create_workspace_provider(
                workspace_mode="temp",
                project_root=temp_project_dir,
            )

            # Assert
            assert isinstance(provider, TempCopyProvider)

        finally:
            cleanup_temp_dir(temp_project_dir)
