"""
Workspace provider adapters for isolated verification environments.

This module implements concrete workspace isolation strategies following
hexagonal architecture principles. Adapters implement the WorkspaceProvider
port defined in core.verify_domain.

Requirements: 1.2, 6.1, 6.3
"""

import logging
import random
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from ..core.verify_domain import Workspace

logger = logging.getLogger(__name__)


class GitWorktreeProvider:
    """
    Concrete implementation using git worktree for workspace isolation.

    This adapter creates isolated workspaces using git worktree, which provides
    fast, space-efficient isolation by sharing .git objects while maintaining
    separate working directories.

    Requirements: 1.2, 6.1, 6.3

    Attributes:
        worktree_dir: Base directory for creating worktrees
        project_root: Root directory of the git repository
    """

    def __init__(self, worktree_dir: Path, project_root: Path | None = None):
        """
        Initialize GitWorktreeProvider with worktree base directory.

        Args:
            worktree_dir: Base directory where worktrees will be created
            project_root: Root directory of the git repository (defaults to current directory)

        Requirements: 1.2, 6.1
        """
        self.worktree_dir = Path(worktree_dir)
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.worktree_dir.mkdir(parents=True, exist_ok=True)

    def create_workspace(self, file_path: str) -> Workspace:
        """
        Create git worktree for isolated verification.

        Strategy:
        1. Generate unique workspace_id (timestamp + random suffix)
        2. Run: git worktree add <path> HEAD (in project_root context)
        3. Create symlink to main project's .lake/ directory (share build artifacts)
        4. Return Workspace with path, workspace_id, mode="worktree"
        5. Handle git command errors gracefully

        Args:
            file_path: Path to file being verified (for context)

        Returns:
            Workspace with path and metadata

        Raises:
            RuntimeError: If git worktree creation fails

        Requirements: 1.2, 6.1
        """
        # Generate unique workspace_id
        workspace_id = self._generate_workspace_id()
        worktree_path = self.worktree_dir / workspace_id

        try:
            # Create worktree at HEAD (run command in project_root context)
            subprocess.run(
                ["git", "worktree", "add", str(worktree_path), "HEAD"],
                cwd=self.project_root,  # Run in project root context
                capture_output=True,
                text=True,
                timeout=10.0,
                check=True,
            )

            # Note: Git worktrees share .git but not .lake/
            # For now, each worktree will have its own .lake/ which may trigger rebuilds
            # TODO: Investigate Lake's LAKE_BUILD_DIR or other mechanisms for sharing builds

            logger.info(f"Created git worktree: {workspace_id}")

            return Workspace(
                path=worktree_path,
                workspace_id=workspace_id,
                mode="worktree",
            )

        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to create git worktree: {e.stderr}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

        except subprocess.TimeoutExpired as e:
            error_msg = "Git worktree creation timed out"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

        except Exception as e:
            error_msg = f"Unexpected error creating git worktree: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def cleanup_workspace(self, workspace: Workspace) -> None:
        """
        Remove git worktree.

        Strategy:
        1. Run: git worktree remove <path> --force (in project_root context)
        2. Handle cleanup errors (log but don't fail)

        Args:
            workspace: Workspace to clean up

        Note:
            This method does not raise exceptions. Cleanup errors are logged
            but not propagated to ensure cleanup always completes.

        Requirements: 6.3
        """
        try:
            subprocess.run(
                ["git", "worktree", "remove", str(workspace.path), "--force"],
                cwd=self.project_root,  # Run in project root context
                capture_output=True,
                text=True,
                timeout=10.0,
                check=True,
            )

            logger.info(f"Cleaned up git worktree: {workspace.workspace_id}")

        except subprocess.CalledProcessError as e:
            # Log error but don't raise - cleanup should always complete
            logger.warning(f"Failed to remove git worktree {workspace.workspace_id}: {e.stderr}")

        except subprocess.TimeoutExpired:
            logger.warning(f"Git worktree removal timed out for {workspace.workspace_id}")

        except Exception as e:
            logger.warning(f"Unexpected error removing git worktree {workspace.workspace_id}: {e}")

    def _generate_workspace_id(self) -> str:
        """
        Generate unique workspace_id with timestamp and random suffix.

        Format: worktree-YYYYMMDD-HHMMSS-<random>

        Returns:
            Unique workspace_id string

        Requirements: 1.2, 6.1
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        random_suffix = f"{random.randint(1000, 9999)}"
        return f"worktree-{timestamp}-{random_suffix}"


class TempCopyProvider:
    """
    Fallback implementation using temporary directory copy.

    This adapter creates isolated workspaces by copying the entire project
    directory to a temporary location. It's slower than git worktree but
    works without requiring a git repository.

    Requirements: 1.2, 6.1

    Attributes:
        project_root: Root directory of the project to copy
        temp_base_dir: Base directory for temporary workspaces (optional)
    """

    def __init__(self, project_root: Path, temp_base_dir: Path | None = None):
        """
        Initialize TempCopyProvider with project root.

        Args:
            project_root: Root directory of the project to copy
            temp_base_dir: Optional base directory for temp workspaces

        Requirements: 1.2, 6.1
        """
        self.project_root = Path(project_root)
        self.temp_base_dir = Path(temp_base_dir) if temp_base_dir else None

        if not self.project_root.exists():
            raise ValueError(f"Project root does not exist: {project_root}")

    def create_workspace(self, file_path: str) -> Workspace:
        """
        Copy project directory to temp location.

        Strategy:
        1. Generate unique workspace_id
        2. Create temp directory
        3. Copy project files to temp directory
        4. Return Workspace with mode="temp"

        Args:
            file_path: Path to file being verified (for context)

        Returns:
            Workspace with path and metadata

        Raises:
            RuntimeError: If workspace creation fails

        Requirements: 1.2, 6.1
        """
        # Generate unique workspace_id
        workspace_id = self._generate_workspace_id()

        try:
            # Create temp directory
            if self.temp_base_dir:
                self.temp_base_dir.mkdir(parents=True, exist_ok=True)
                temp_dir = self.temp_base_dir / workspace_id
                temp_dir.mkdir(parents=True, exist_ok=True)
            else:
                temp_dir = Path(tempfile.mkdtemp(prefix=f"{workspace_id}_"))

            # Copy project files
            shutil.copytree(
                self.project_root,
                temp_dir,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(
                    ".git",
                    ".lake",  # Don't copy .lake - it's huge and causes rebuilds
                    "__pycache__",
                    "*.pyc",
                    ".hypothesis",
                    ".pytest_cache",
                    ".mypy_cache",
                    ".ruff_cache",
                    ".venv",
                    "venv",
                    "node_modules",
                ),
            )

            logger.info(f"Created temp workspace: {workspace_id}")

            return Workspace(
                path=temp_dir,
                workspace_id=workspace_id,
                mode="temp",
            )

        except Exception as e:
            error_msg = f"Failed to create temp workspace: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def cleanup_workspace(self, workspace: Workspace) -> None:
        """
        Clean up temp directory.

        Strategy:
        1. Remove temp directory recursively
        2. Handle cleanup errors (log but don't fail)

        Args:
            workspace: Workspace to clean up

        Note:
            This method does not raise exceptions. Cleanup errors are logged
            but not propagated to ensure cleanup always completes.

        Requirements: 6.3
        """
        try:
            if workspace.path.exists():
                shutil.rmtree(workspace.path)
                logger.info(f"Cleaned up temp workspace: {workspace.workspace_id}")

        except Exception as e:
            logger.warning(f"Failed to remove temp workspace {workspace.workspace_id}: {e}")

    def _generate_workspace_id(self) -> str:
        """
        Generate unique workspace_id with timestamp and random suffix.

        Format: temp-YYYYMMDD-HHMMSS-<random>

        Returns:
            Unique workspace_id string

        Requirements: 1.2, 6.1
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        random_suffix = f"{random.randint(1000, 9999)}"
        return f"temp-{timestamp}-{random_suffix}"


class NoIsolationProvider:
    """
    No-isolation implementation that uses the project directory directly.

    This adapter skips workspace isolation entirely and runs verification
    directly in the user's project directory. This is fast and works correctly
    with Lake projects, but provides no isolation.

    Use this for read-only verification where isolation isn't needed.

    Requirements: 1.2, 6.1

    Attributes:
        project_root: Root directory of the project
    """

    def __init__(self, project_root: Path):
        """
        Initialize NoIsolationProvider with project root.

        Args:
            project_root: Root directory of the project

        Requirements: 1.2, 6.1
        """
        self.project_root = Path(project_root)

        if not self.project_root.exists():
            raise ValueError(f"Project root does not exist: {project_root}")

    def create_workspace(self, file_path: str) -> Workspace:
        """
        Return the project directory as the "workspace" (no isolation).

        Args:
            file_path: Path to file being verified (for context)

        Returns:
            Workspace pointing to the project root

        Requirements: 1.2, 6.1
        """
        workspace_id = "no-isolation"

        logger.info(f"Using project directory directly (no isolation): {self.project_root}")

        return Workspace(
            path=self.project_root,
            workspace_id=workspace_id,
            mode="none",
        )

    def cleanup_workspace(self, workspace: Workspace) -> None:
        """
        No-op cleanup (nothing to clean up).

        Args:
            workspace: Workspace to clean up (ignored)

        Requirements: 6.3
        """
        # Nothing to clean up
        pass


def detect_workspace_mode(project_root: Path | None = None) -> str:
    """
    Auto-detect appropriate workspace mode.

    Returns "none" for all projects (no isolation, fastest, works with Lake).

    Rationale:
    - Verification is read-only, so isolation isn't strictly necessary
    - No isolation = no copying = instant startup
    - Works perfectly with Lake projects and Mathlib
    - Worktrees and temp copies have issues with Lake build artifacts

    Args:
        project_root: Project root directory (defaults to current directory)

    Returns:
        "none" for all projects

    Requirements: 6.5
    """
    return "none"


def create_workspace_provider(
    workspace_mode: str | None = None,
    project_root: Path | None = None,
    worktree_dir: Path | None = None,
    temp_base_dir: Path | None = None,
) -> GitWorktreeProvider | TempCopyProvider | NoIsolationProvider:
    """
    Factory function to create appropriate workspace provider.

    This function implements the strategy pattern by selecting the appropriate
    workspace provider based on the requested mode or auto-detection.

    Args:
        workspace_mode: Explicit mode ("worktree", "temp", "none"), or None for auto-detect
        project_root: Project root directory (defaults to current directory)
        worktree_dir: Directory for git worktrees (defaults to .worktrees)
        temp_base_dir: Base directory for temp workspaces (optional)

    Returns:
        Appropriate workspace provider instance

    Requirements: 6.5
    """
    project_root = Path.cwd() if project_root is None else Path(project_root)

    # Auto-detect mode if not specified
    if workspace_mode is None:
        workspace_mode = detect_workspace_mode(project_root)

    # Create appropriate provider
    if workspace_mode == "worktree":
        if worktree_dir is None:
            worktree_dir = project_root / ".worktrees"
        return GitWorktreeProvider(worktree_dir, project_root)

    elif workspace_mode == "temp":
        return TempCopyProvider(project_root, temp_base_dir)

    elif workspace_mode == "none":
        return NoIsolationProvider(project_root)

    else:
        raise ValueError(f"Invalid workspace_mode: {workspace_mode}")
