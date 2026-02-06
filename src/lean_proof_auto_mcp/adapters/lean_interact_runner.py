"""
LeanRunner adapter using LeanInteract library.

This module implements the LeanRunner port using LeanInteract for Lean execution.
It provides both single-use verification and reusable server instances.

Requirements: 1.1, 1.3, 2.1, 2.2
"""

import logging
from pathlib import Path

from ..core.verify_domain import LeanRunResult
from ..lean.server_manager import ServerManagerImpl

logger = logging.getLogger(__name__)


class LeanInteractRunner:
    """
    Concrete implementation of LeanRunner using LeanInteract library.

    This adapter uses ServerManager to manage Lean server instances and
    provides verification capabilities for both files and theorems.

    Requirements: 1.1, 1.3, 2.1, 2.2
    """

    def __init__(self, server_manager: ServerManagerImpl, timeout_buffer_ms: int = 100) -> None:
        """
        Initialize LeanInteractRunner.

        Args:
            server_manager: ServerManager instance for server lifecycle management
            timeout_buffer_ms: Buffer time in milliseconds for timeout handling
        """
        self.server_manager = server_manager
        self.timeout_buffer_ms = timeout_buffer_ms

    def verify_file(
        self,
        workspace_path: Path,
        file_path: str,
        theorem_id: str | None,
        budget_s: float,
    ) -> LeanRunResult:
        """
        Run Lean verification on file or theorem.

        Args:
            workspace_path: Path to isolated workspace
            file_path: Path to Lean file (relative to workspace)
            theorem_id: Optional theorem identifier for theorem-level verification
            budget_s: Time budget in seconds

        Returns:
            LeanRunResult with status, diagnostics, logs, timing

        Raises:
            TimeoutError: If verification exceeds budget
            ValueError: If theorem_id is invalid or not found
            RuntimeError: If Lean process fails unexpectedly

        Requirements: 1.1, 1.3, 2.1, 2.2
        """
        # Get or create server for this file
        server = self.server_manager.get_server(file_path)

        # Use FileCommand to verify
        try:
            from lean_interact.interface import FileCommand

            command = FileCommand(path=file_path)
            response = server.run(command, timeout=budget_s)  # type: ignore[attr-defined]

            # Parse response into LeanRunResult
            diagnostics = self._parse_diagnostics(response)
            status = self._determine_status(diagnostics)

            return LeanRunResult(
                status=status,
                diagnostics=diagnostics,
                scope_used="file" if theorem_id is None else "theorem",
                full_logs="",  # LeanInteract doesn't provide full logs
                timing={"verification_s": 0.0},  # TODO: Add timing
                exit_code=0 if status == "success" else 1,
            )

        except TimeoutError as e:
            raise TimeoutError(f"Verification timed out after {budget_s}s") from e
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            raise RuntimeError(f"Lean verification failed: {e}") from e

    def create_server(self, workspace_path: Path) -> "LeanInteractServer":
        """
        Create a reusable Lean server for the given workspace.

        Args:
            workspace_path: Path to isolated workspace

        Returns:
            LeanServer instance that can be reused

        Raises:
            RuntimeError: If server creation fails

        Requirements: Performance optimization
        """
        # For now, return a wrapper around the server manager
        # This allows reusing the same server instance
        return LeanInteractServer(self.server_manager, workspace_path)

    def _parse_diagnostics(self, response: object) -> list[dict]:
        """
        Parse diagnostics from LeanInteract response.

        Args:
            response: LeanInteract response object

        Returns:
            List of diagnostic dicts
        """
        diagnostics = []

        if hasattr(response, "messages"):
            for msg in response.messages:
                severity = self._normalize_severity(getattr(msg, "severity", "info"))
                message = getattr(msg, "data", "")

                # Extract location
                location = None
                if hasattr(msg, "start_pos"):
                    start_pos = msg.start_pos
                    location = {
                        "line": getattr(start_pos, "line", 0),
                        "col": getattr(start_pos, "column", 0),
                    }

                diagnostics.append(
                    {"severity": severity, "message": message, "location": location}
                )

        return diagnostics

    def _normalize_severity(self, severity: str) -> str:
        """
        Normalize severity string to standard values.

        Args:
            severity: Raw severity string

        Returns:
            Normalized severity ("error", "warning", or "info")
        """
        severity_lower = severity.lower()
        if "error" in severity_lower:
            return "error"
        elif "warn" in severity_lower:
            return "warning"
        else:
            return "info"

    def _determine_status(self, diagnostics: list[dict]) -> str:
        """
        Determine verification status from diagnostics.

        Args:
            diagnostics: List of diagnostic dicts

        Returns:
            Status string ("success", "fail", or "timeout")
        """
        # Check for errors
        has_errors = any(d["severity"] == "error" for d in diagnostics)

        if has_errors:
            return "fail"
        else:
            return "success"


class LeanInteractServer:
    """
    Reusable Lean server instance wrapper.

    This class wraps a ServerManager and provides a reusable server interface.
    """

    def __init__(self, server_manager: ServerManagerImpl, workspace_path: Path) -> None:
        """
        Initialize LeanInteractServer.

        Args:
            server_manager: ServerManager instance
            workspace_path: Path to workspace
        """
        self.server_manager = server_manager
        self.workspace_path = workspace_path

    def verify_file(
        self,
        file_path: str,
        theorem_id: str | None,
        budget_s: float,
    ) -> LeanRunResult:
        """
        Run Lean verification using this server instance.

        Args:
            file_path: Path to Lean file (relative to workspace)
            theorem_id: Optional theorem identifier for theorem-level verification
            budget_s: Time budget in seconds

        Returns:
            LeanRunResult with status, diagnostics, logs, timing

        Raises:
            TimeoutError: If verification exceeds budget
            ValueError: If theorem_id is invalid or not found
            RuntimeError: If Lean process fails unexpectedly
        """
        # Delegate to server manager
        server = self.server_manager.get_server(file_path)

        try:
            from lean_interact.interface import FileCommand

            command = FileCommand(path=file_path)
            response = server.run(command, timeout=budget_s)  # type: ignore[attr-defined]

            # Parse response
            runner = LeanInteractRunner(self.server_manager, timeout_buffer_ms=100)
            diagnostics = runner._parse_diagnostics(response)
            status = runner._determine_status(diagnostics)

            return LeanRunResult(
                status=status,
                diagnostics=diagnostics,
                scope_used="file" if theorem_id is None else "theorem",
                full_logs="",
                timing={"verification_s": 0.0},
                exit_code=0 if status == "success" else 1,
            )

        except TimeoutError as e:
            raise TimeoutError(f"Verification timed out after {budget_s}s") from e
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            raise RuntimeError(f"Lean verification failed: {e}") from e

    def close(self) -> None:
        """
        Close the server and cleanup resources.

        This method shuts down all servers managed by the server manager.
        """
        try:
            self.server_manager.shutdown_all()
        except Exception as e:
            logger.warning(f"Error closing server: {e}")
