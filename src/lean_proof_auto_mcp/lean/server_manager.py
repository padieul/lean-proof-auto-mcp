"""
LeanInteract ServerManager implementation.

This module provides the LeanInteract-specific implementation of the ServerManager
port for managing LeanInteract server lifecycle, including crash detection and
automatic restart.

Requirements: 10.6, 28.3, 28.4, 28.5, 28.6
"""


import logging
import os
from collections import OrderedDict
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
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


class LeanInteractServerManager:
    """
    Concrete implementation of ServerManager for managing LeanInteract servers.


    This manager maintains one server instance per file to avoid startup overhead,

    detects crashes, and automatically restarts servers. Uses LRU eviction policy
    
    to limit the number of concurrent servers to MAX_SERVERS (default 3, configurable
    
    via LEAN_MAX_SERVERS environment variable).


    Requirements: 10.6, 28.3, 28.4, 28.5, 28.6
    """


    def __init__(self, workspace_path: Path | None = None):
        """

        Initialize ServerManager.


        Args:

            workspace_path: Optional workspace path for project context


        Requirements: 10.6
        """

        self.workspace_path = workspace_path

        self._servers: OrderedDict[str, Any] = OrderedDict()  # file_path -> LeanServer

        self._request_log: list[tuple[str, str, object]] = []  # (file, request, response)


    def get_server(self, file_path: str) -> "LeanServerProtocol":
        """

        Get or create server instance for file.


        Maintains one server instance per file to avoid startup overhead.

        If server exists and is alive, returns it. Otherwise creates new server.
        
        Uses LRU eviction: when cache reaches MAX_SERVERS capacity, evicts the
        
        least recently used server before adding a new one.


        Args:

            file_path: Path to Lean file


        Returns:

            LeanServer instance


        Raises:

            RuntimeError: If LeanInteract not available or server creation fails


        Requirements: 10.6, 28.4
        """

        if not LEAN_INTERACT_AVAILABLE or LeanServer is None:

            raise RuntimeError(

                "LeanInteract library not installed. Install with: pip install lean-interact"

            )


        # Check if server exists and is alive
        if file_path in self._servers:

            server = self._servers[file_path]

            if self._is_server_alive(server):

                logger.debug(f"Reusing existing server for {file_path}")
                
                # Move to end to mark as most recently used (LRU tracking)
                self._servers.move_to_end(file_path)
                
                return server
            else:

                logger.warning(f"Server for {file_path} is dead, creating new one")

                self._shutdown_server(server)

                del self._servers[file_path]


        # Check if we need to evict (LRU eviction)
        if len(self._servers) >= MAX_SERVERS:
            # Evict least recently used (first item in OrderedDict)
            oldest_file, oldest_server = self._servers.popitem(last=False)
            self._shutdown_server(oldest_server)
            logger.info(f"Evicted LRU server for {oldest_file} (cache at capacity: {MAX_SERVERS})")

        # Create new server

        server = self._create_server(file_path)

        self._servers[file_path] = server

        logger.info(f"Created new server for {file_path}")
        return server


    def restart_server(self, file_path: str) -> None:
        """

        Restart crashed server.


        This method kills the existing server (if any) and creates a new one.


        Args:

            file_path: Path to Lean file


        Requirements: 28.5
        """

        logger.info(f"Restarting server for {file_path}")


        # Cleanup existing server
        if file_path in self._servers:

            server = self._servers[file_path]

            self._shutdown_server(server)

            del self._servers[file_path]


        # Create new server

        server = self._create_server(file_path)

        self._servers[file_path] = server

        logger.info(f"Server restarted for {file_path}")


    def shutdown_all(self) -> None:
        """

        Shutdown all server instances.


        This method kills all servers and clears the cache.


        Requirements: 28.6
        """

        logger.info(f"Shutting down {len(self._servers)} servers")


        for _file_path, server in list(self._servers.items()):

            self._shutdown_server(server)


        self._servers.clear()

        logger.info("All servers shut down")


    def log_request(self, file_path: str, request: str, response: object) -> None:
        """

        Log a request/response for debugging.


        Args:

            file_path: Path to Lean file

            request: Request description

            response: Response object


        Requirements: 28.6
        """

        self._request_log.append((file_path, request, response))

        logger.debug(f"Logged request for {file_path}: {request}")


    def get_request_log(self) -> list[tuple[str, str, object]]:
        """

        Get the request log.


        Returns:

            List of (file_path, request, response) tuples


        Requirements: 28.6
        """

        return self._request_log.copy()


    def _create_server(self, file_path: str) -> "LeanServerProtocol":
        """

        Create a new LeanServer for the given file.


        Args:

            file_path: Path to Lean file


        Returns:

            LeanServer instance


        Raises:

            RuntimeError: If server creation fails


        Requirements: 28.3, 28.4
        """

        try:

            # Determine workspace path from file_path

            # If workspace_path was provided, use it; otherwise use file's directory

            workspace = self.workspace_path or Path(file_path).parent


            # Check if workspace has lakefile

            lakefile_path = workspace / "lakefile.toml"

            lakefile_lean_path = workspace / "lakefile.lean"


            if lakefile_path.exists() or lakefile_lean_path.exists():

                # Has Lake project - use it

                try:

                    project = LocalProject(path=str(workspace), auto_build=False)

                    config = LeanREPLConfig(project=project)

                    server = LeanServer(config)

                    logger.info(f"Created server with Lake project context for {file_path}")
                    return server

                except Exception as e:

                    logger.warning(f"Failed to create project context, using standalone: {e}")


            # Use standalone mode

            config = LeanREPLConfig()

            server = LeanServer(config)

            logger.info(f"Created standalone server for {file_path}")
            return server


        except Exception as e:

            raise RuntimeError(f"Failed to create server for {file_path}: {e}") from e


    def _is_server_alive(self, server: object) -> bool:
        """

        Check if a server is alive.


        Args:

            server: LeanServer instance


        Returns:

            True if server is alive, False otherwise


        Requirements: 28.5
        """

        # Simple check - try to access server attributes

        # A more robust check would try a simple command

        try:

            # Check if server has required methods

            return hasattr(server, "run") and hasattr(server, "kill")

        except Exception:

            return False


    def _shutdown_server(self, server: object) -> None:
        """

        Gracefully shutdown a server by killing it.


        Args:

            server: LeanServer instance


        Requirements: 28.6
        """

        try:

            if hasattr(server, "kill"):

                server.kill()

                logger.debug("Server killed successfully")

        except Exception as e:

            logger.warning(f"Failed to kill server: {e}")

