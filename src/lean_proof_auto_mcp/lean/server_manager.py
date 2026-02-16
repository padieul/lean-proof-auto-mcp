"""
LeanInteract ServerManager implementation.

This module provides the LeanInteract-specific implementation of the ServerManager
port for managing LeanInteract server lifecycle, including crash detection,
automatic restart, and a global registry for cross-tool-call server reuse.

The global registry (get_shared_server_manager) ensures that Lean REPL processes
survive across MCP tool calls within the same session, eliminating redundant
server startups. Servers are keyed by project root, not by file path, because
a single LeanInteract server can handle any file within its Lake project.

Requirements: 10.6, 28.3, 28.4, 28.5, 28.6
"""

import atexit
import logging
import os
from collections import OrderedDict
from pathlib import Path
from typing import Any, cast

from .ports import LeanServer as LeanServerProtocol

logger = logging.getLogger(__name__)


# Try to import LeanInteract, but allow module to load even if not installed
try:
    from lean_interact import LeanServer
    from lean_interact.config import LeanREPLConfig
    from lean_interact.project import LocalProject

    LEAN_INTERACT_AVAILABLE = True
except ImportError:
    LeanServer = None  # type: ignore[assignment, misc]
    LeanREPLConfig = None  # type: ignore[assignment, misc]
    LocalProject = None  # type: ignore[assignment, misc]
    LEAN_INTERACT_AVAILABLE = False


# Maximum number of concurrent servers (configurable via environment variable)
# Set LEAN_MAX_SERVERS environment variable to override the default value of 3
MAX_SERVERS = int(os.environ.get("LEAN_MAX_SERVERS", "3"))


# ---------------------------------------------------------------------------
# Fix 1: Global ServerManager registry
# ---------------------------------------------------------------------------
# One ServerManager per project root, shared across ALL MCP tool calls within
# the same session. This eliminates the #1 performance killer: creating a new
# Lean REPL process for every tool invocation.

_global_managers: dict[Path, "LeanInteractServerManager"] = {}


def get_shared_server_manager(project_root: Path) -> "LeanInteractServerManager":
    """
    Get or create a shared ServerManager for the given project root.

    This is the composition-root entry point. All MCP tools should call this
    instead of constructing LeanInteractServerManager directly. The returned
    manager persists across tool calls, so Lean REPL processes stay alive.

    Args:
        project_root: Resolved absolute path to the Lake project root.

    Returns:
        LeanInteractServerManager instance (cached per project_root).
    """
    resolved = project_root.resolve()
    if resolved not in _global_managers:
        logger.info(f"Creating shared ServerManager for project: {resolved}")
        _global_managers[resolved] = LeanInteractServerManager(workspace_path=resolved)
    else:
        logger.debug(f"Reusing shared ServerManager for project: {resolved}")
    return _global_managers[resolved]


def shutdown_all_shared_managers() -> None:
    """Shutdown every cached ServerManager. Called at process exit."""
    for project_root, manager in list(_global_managers.items()):
        logger.info(f"Shutting down shared ServerManager for {project_root}")
        manager.shutdown_all()
    _global_managers.clear()


# Ensure servers are cleaned up when the MCP process exits.
atexit.register(shutdown_all_shared_managers)


class LeanInteractServerManager:
    """
    Manages LeanInteract server lifecycle with project-keyed caching.

    Key design decisions:
    - Servers are keyed by PROJECT ROOT, not by file path. A single LeanInteract
      LeanServer can run FileCommand on any .lean file within its Lake project.
      This eliminates redundant REPL startups when probing different files or
      harnesses in the same project.
    - LRU eviction bounds memory when working across multiple projects.
    - Crash detection with automatic restart.

    Use get_shared_server_manager() to obtain instances — do not construct
    directly in tool composition roots.

    Requirements: 10.6, 28.3, 28.4, 28.5, 28.6
    """

    def __init__(self, workspace_path: Path | None = None):
        """
        Initialize ServerManager.

        Args:
            workspace_path: Workspace path for project context (Lake project root).

        Requirements: 10.6
        """
        self.workspace_path = workspace_path
        # Keyed by resolved project root (or workspace_path itself for the
        # common single-project case). Most sessions will have exactly 1 entry.
        self._servers: OrderedDict[str, LeanServerProtocol] = OrderedDict()
        self._request_log: list[tuple[str, str, object]] = []

    def get_server(self, file_path: str) -> "LeanServerProtocol":
        """
        Get or create a server instance for the project containing file_path.

        Fix 2: Servers are keyed by project root, not by individual file path.
        A LeanInteract LeanServer can execute FileCommand on ANY file in the
        project, so one REPL per project is sufficient. This means:
        - extract_declarations("MyFile.lean") and verify_file("_harness.lean")
          share the same REPL.
        - probe_file with 10 theorems uses one REPL, not 10.

        Args:
            file_path: Path to Lean file (used only for logging, not as cache key).

        Returns:
            LeanServer instance.

        Raises:
            RuntimeError: If LeanInteract not available or server creation fails.

        Requirements: 10.6, 28.4
        """
        if not LEAN_INTERACT_AVAILABLE or LeanServer is None:
            raise RuntimeError(
                "LeanInteract library not installed. Install with: pip install lean-interact"
            )

        # Key by project root so all files in the same project share one REPL.
        cache_key = str(self.workspace_path) if self.workspace_path else str(Path(file_path).parent)

        # Check if server exists and is alive
        if cache_key in self._servers:
            server = self._servers[cache_key]
            if self._is_server_alive(server):
                logger.debug(f"Reusing project server for {cache_key} (file: {file_path})")
                # Move to end to mark as most recently used (LRU tracking)
                self._servers.move_to_end(cache_key)
                return server
            else:
                logger.warning(f"Server for project {cache_key} is dead, creating new one")
                self._shutdown_server(server)
                del self._servers[cache_key]

        # Check if we need to evict (LRU eviction)
        if len(self._servers) >= MAX_SERVERS:
            oldest_key, oldest_server = self._servers.popitem(last=False)
            self._shutdown_server(oldest_server)
            logger.info(f"Evicted LRU server for {oldest_key} (cache at capacity: {MAX_SERVERS})")

        # Create new server
        server = self._create_server(file_path)
        self._servers[cache_key] = server
        logger.info(f"Created project server for {cache_key} (file: {file_path})")
        return server

    def restart_server(self, file_path: str) -> None:
        """
        Restart crashed server for the project containing file_path.

        Args:
            file_path: Path to Lean file.

        Requirements: 28.5
        """
        cache_key = str(self.workspace_path) if self.workspace_path else str(Path(file_path).parent)
        logger.info(f"Restarting server for project {cache_key}")

        if cache_key in self._servers:
            server = self._servers[cache_key]
            self._shutdown_server(server)
            del self._servers[cache_key]

        server = self._create_server(file_path)
        self._servers[cache_key] = server
        logger.info(f"Server restarted for project {cache_key}")

    def shutdown_all(self) -> None:
        """
        Shutdown all server instances.

        Requirements: 28.6
        """
        logger.info(f"Shutting down {len(self._servers)} servers")
        for _key, server in list(self._servers.items()):
            self._shutdown_server(server)
        self._servers.clear()
        logger.info("All servers shut down")

    def log_request(self, file_path: str, request: str, response: object) -> None:
        """
        Log a request/response for debugging.

        Args:
            file_path: Path to Lean file.
            request: Request description.
            response: Response object.

        Requirements: 28.6
        """
        self._request_log.append((file_path, request, response))
        logger.debug(f"Logged request for {file_path}: {request}")

    def get_request_log(self) -> list[tuple[str, str, object]]:
        """
        Get the request log.

        Returns:
            List of (file_path, request, response) tuples.

        Requirements: 28.6
        """
        return self._request_log.copy()

    def _create_server(self, file_path: str) -> "LeanServerProtocol":
        """
        Create a new LeanServer for the project.

        Args:
            file_path: Path to Lean file (used for fallback workspace detection).

        Returns:
            LeanServer instance.

        Raises:
            RuntimeError: If server creation fails.

        Requirements: 28.3, 28.4
        """
        try:
            assert LeanServer is not None
            assert LeanREPLConfig is not None
            workspace = self.workspace_path or Path(file_path).parent

            lakefile_path = workspace / "lakefile.toml"
            lakefile_lean_path = workspace / "lakefile.lean"

            if (lakefile_path.exists() or lakefile_lean_path.exists()) and LocalProject is not None:
                try:
                    project = LocalProject(directory=str(workspace), auto_build=False)
                    config = LeanREPLConfig(project=project)
                    server = LeanServer(config)
                    logger.info(f"Created server with Lake project context: {workspace}")
                    return server
                except Exception as e:
                    logger.warning(f"Failed to create project context, using standalone: {e}")

            config = LeanREPLConfig()
            server = LeanServer(config)
            logger.info(f"Created standalone server for {file_path}")
            return server

        except Exception as e:
            raise RuntimeError(f"Failed to create server for {file_path}: {e}") from e

    def _is_server_alive(self, server: object) -> bool:
        """
        Check if a server's underlying REPL process is alive.

        Uses LeanInteract's is_alive() when available (checks _proc.poll()),
        falling back to structural checks for non-LeanInteract implementations.

        IMPORTANT: We do NOT special-case _proc=None as "lazy-init alive".
        LeanInteract's kill() sets _proc=None after terminating the process,
        making it indistinguishable from a never-started server. Treating
        _proc=None as alive causes a cascade failure: after a timeout kills
        the REPL, every subsequent get_server() call returns the dead server
        object, and every run() immediately raises ChildProcessError.

        Instead, when _proc is None we return False, which triggers
        get_server() to create a fresh LeanServer object. This is cheap
        (the expensive part is the first run() call that loads the
        environment, not the object construction).

        Args:
            server: LeanServer instance.

        Returns:
            True if server process is confirmed alive, False otherwise.

        Requirements: 28.5
        """
        try:
            # Prefer LeanInteract's real process check.
            # is_alive() returns: _proc is not None and _proc.poll() is None
            # This correctly returns False for both killed (_proc=None) and
            # crashed (_proc.poll() != None) servers.
            if hasattr(server, "is_alive"):
                return bool(cast(Any, server).is_alive())
            # Fallback for non-LeanInteract implementations (e.g. test doubles)
            return hasattr(server, "run") and hasattr(server, "kill")
        except Exception:
            return False

    def _shutdown_server(self, server: object) -> None:
        """
        Gracefully shutdown a server by killing it.

        Args:
            server: LeanServer instance.

        Requirements: 28.6
        """
        try:
            if hasattr(server, "kill"):
                server.kill()
                logger.debug("Server killed successfully")
        except Exception as e:
            logger.warning(f"Failed to kill server: {e}")
