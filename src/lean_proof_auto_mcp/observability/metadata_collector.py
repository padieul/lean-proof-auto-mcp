"""
Subprocess-based metadata collector implementation.

This adapter collects metadata by running subprocess commands (git, lean, lake).
Uses threading to avoid Windows pipe deadlock issues when running as a nested
subprocess (e.g., MCP server spawned by IDE).

The threading approach solves a critical Windows issue:
- MCP server runs as subprocess of IDE (e.g., GitHub Copilot)
- MCP server spawns nested subprocesses (git, lean, lake)
- Windows has small pipe buffers (4KB vs 64KB on Linux)
- Nested subprocess output fills pipe buffer
- Child blocks waiting for parent to read, parent blocks waiting for child
- Result: Deadlock

Solution: Read subprocess output in separate thread while waiting for completion.
"""

import logging
import subprocess
import threading

logger = logging.getLogger(__name__)


class SubprocessMetadataCollector:
    """
    Collects metadata using subprocess commands.

    This implementation uses threading to read subprocess output, avoiding
    pipe buffer deadlock issues on Windows when running as a nested subprocess
    (e.g., MCP server spawned by IDE).

    The collector attempts to run git, lean, and lake commands to gather
    version information. Failures are logged but do not raise exceptions,
    ensuring metadata collection never breaks the main workflow.

    Thread Safety:
        This class is thread-safe. Multiple threads can call collect_version_info()
        concurrently without issues.

    Platform Support:
        - Windows: Uses threading to avoid pipe deadlock
        - Linux: Works correctly (threading adds minimal overhead)
        - macOS: Works correctly (threading adds minimal overhead)

    Example:
        >>> collector = SubprocessMetadataCollector()
        >>> metadata = collector.collect_version_info()
        >>> print(metadata.get('lean_version', 'Not available'))
        Lean (version 4.26.0-rc1, ...)
    """

    def collect_version_info(self) -> dict[str, str]:
        """
        Collect version metadata from git, lean, and lake commands.

        This method attempts to run three commands:
        1. git rev-parse HEAD - Get current git commit hash
        2. lean --version - Get Lean version string
        3. lake --version - Get Lake version string

        Each command is run with a 1-second timeout. Failures (command not found,
        timeout, non-zero exit code) are logged at debug level and result in
        the corresponding key being omitted from the result.

        Returns:
            Dictionary with available version information. Keys are only
            present if the corresponding command succeeded:
            - repo_commit: Git commit hash
            - lean_version: Lean version string
            - lake_version: Lake version string

        Note:
            This method never raises exceptions. All errors are caught and logged.

        Example:
            >>> collector = SubprocessMetadataCollector()
            >>> metadata = collector.collect_version_info()
            >>> # In a git repo with lean and lake installed:
            >>> assert 'repo_commit' in metadata
            >>> assert 'lean_version' in metadata
            >>> assert 'lake_version' in metadata
            >>> # Outside git repo or without tools:
            >>> # Some keys may be missing, but no exception is raised
        """
        metadata = {}

        # Git commit
        commit = self._run_command_safe(["git", "rev-parse", "HEAD"])
        if commit:
            metadata["repo_commit"] = commit

        # Lean version
        lean_version = self._run_command_safe(["lean", "--version"])
        if lean_version:
            metadata["lean_version"] = lean_version

        # Lake version
        lake_version = self._run_command_safe(["lake", "--version"])
        if lake_version:
            metadata["lake_version"] = lake_version

        return metadata

    def _run_command_safe(self, cmd: list[str], timeout: float = 1.0) -> str | None:
        """
        Run command with timeout, avoiding pipe deadlock using threads.

        This method uses threading to read subprocess output while waiting
        for the process to complete. This prevents pipe buffer deadlock on
        Windows when the MCP server runs as a subprocess.

        The Problem (Windows-specific):
        1. MCP server is spawned as subprocess by IDE
        2. MCP server spawns nested subprocess (git/lean/lake)
        3. Nested subprocess writes output to pipe
        4. Pipe buffer fills (4KB on Windows)
        5. Nested subprocess blocks waiting for parent to read
        6. Parent (MCP server) blocks waiting for child to finish
        7. Deadlock!

        The Solution:
        - Spawn subprocess with Popen (not run)
        - Start thread to read stdout
        - Main thread waits for process with timeout
        - Thread reads output asynchronously, preventing buffer fill
        - No deadlock!

        Args:
            cmd: Command to run as list of strings (e.g., ["git", "rev-parse", "HEAD"])
            timeout: Timeout in seconds (default: 1.0)

        Returns:
            Command stdout stripped of whitespace if successful, None otherwise

        Note:
            This method never raises exceptions. All errors are caught and
            logged at debug level.

        Example:
            >>> collector = SubprocessMetadataCollector()
            >>> commit = collector._run_command_safe(["git", "rev-parse", "HEAD"])
            >>> if commit:
            ...     print(f"Current commit: {commit}")
            Current commit: a1b2c3d4e5f6...
        """
        try:
            # Use Popen instead of run to enable async reading
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Read output in separate thread to avoid blocking
            stdout_data = []

            def read_stdout():
                """Thread target: Read stdout until EOF."""
                try:
                    stdout_data.append(proc.stdout.read())
                except Exception as e:
                    logger.debug(f"Error reading stdout from {cmd[0]}: {e}")

            # Start reading thread (daemon so it doesn't block shutdown)
            stdout_thread = threading.Thread(target=read_stdout, daemon=True)
            stdout_thread.start()

            # Wait for process with timeout
            proc.wait(timeout=timeout)

            # Wait for thread to finish reading (with short timeout)
            stdout_thread.join(timeout=0.5)

            # Return output if successful
            if proc.returncode == 0 and stdout_data:
                return stdout_data[0].strip()
            return None

        except subprocess.TimeoutExpired:
            # Process exceeded timeout, kill it
            proc.kill()
            logger.debug(f"Command timed out after {timeout}s: {' '.join(cmd)}")
            return None
        except FileNotFoundError:
            # Command not found (e.g., git not installed)
            logger.debug(f"Command not found: {cmd[0]}")
            return None
        except Exception as e:
            # Unexpected error
            logger.debug(f"Command failed: {' '.join(cmd)}, error: {e}")
            return None
