"""
LeanInteractRunner adapter for Lean verification.

This module implements the LeanRunner port using the LeanInteract library,
which provides programmatic access to Lean 4 through the Lean REPL.

Requirements: 1.1, 1.3, 2.1, 2.2, 4.2, 4.3, 4.4
"""

import logging
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from ..core.verify_domain import LeanRunResult

logger = logging.getLogger(__name__)

# Try to import LeanInteract, but allow module to load even if not installed
try:
    from lean_interact import LeanServer
    from lean_interact.config import LeanREPLConfig
    from lean_interact.interface import FileCommand, LeanError
    from lean_interact.project import LocalProject

    LEAN_INTERACT_AVAILABLE = True
except ImportError:
    LeanServer = None  # type: ignore[assignment, misc]
    LeanREPLConfig = None  # type: ignore[assignment, misc]
    FileCommand = None  # type: ignore[assignment, misc]
    LeanError = None  # type: ignore[assignment, misc]
    LocalProject = None  # type: ignore[assignment, misc]
    LEAN_INTERACT_AVAILABLE = False


class LeanInteractRunner:
    """
    Concrete implementation of LeanRunner using LeanInteract library.

    This adapter uses LeanInteract to execute Lean verification in a project
    context with timeout enforcement and structured diagnostic parsing.

    Requirements: 1.1, 1.3, 2.1, 2.2
    """

    def __init__(self, timeout_buffer_ms: int = 100):
        """
        Initialize LeanInteractRunner with timeout buffer.

        Args:
            timeout_buffer_ms: Buffer time in milliseconds for timeout enforcement

        Requirements: 1.1
        """
        self.timeout_buffer_ms = timeout_buffer_ms

    @staticmethod
    @contextmanager
    def _working_directory(path: Path) -> Iterator[None]:
        """
        Context manager to temporarily change working directory.

        This ensures elan can find the lean-toolchain file in the project directory.

        Args:
            path: Directory to change to

        Yields:
            None

        Requirements: 1.1, 1.3
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(path)
            yield
        finally:
            os.chdir(original_cwd)

    def create_server(self, workspace_path: Path) -> "ReusableLeanServer":
        """
        Create a reusable Lean server for the given workspace.

        This method creates a long-lived server that can be reused across
        multiple verification requests, avoiding repeated initialization overhead.

        Args:
            workspace_path: Path to isolated workspace

        Returns:
            ReusableLeanServer instance that can be reused

        Raises:
            RuntimeError: If server creation fails or LeanInteract not available

        Requirements: Performance optimization for batch operations
        """
        if not LEAN_INTERACT_AVAILABLE or LeanServer is None:
            raise RuntimeError(
                "LeanInteract library not installed. Install with: pip install lean-interact"
            )

        # Initialize LeanServer with project context
        try:
            # Check if workspace has lakefile
            lakefile_path = workspace_path / "lakefile.toml"
            lakefile_lean_path = workspace_path / "lakefile.lean"

            if lakefile_path.exists() or lakefile_lean_path.exists():
                # Has Lake project - use it
                try:
                    # Detect Lean version for logging purposes
                    lean_version = self._detect_lean_version(workspace_path)
                    
                    # Set working directory to workspace so elan can find lean-toolchain
                    # This is critical because elan walks up from CWD to find lean-toolchain
                    # When using LocalProject, lean-interact infers the version from the project
                    # IMPORTANT: We must create BOTH the config AND the server inside the context
                    # because LeanServer spawns subprocesses that need to see the correct CWD
                    with self._working_directory(workspace_path):
                        project = LocalProject(directory=str(workspace_path), auto_build=False)
                        config = LeanREPLConfig(project=project)
                        server = LeanServer(config)
                    
                    logger.info(
                        f"Created reusable server with Lake project context from "
                        f"{workspace_path}, Lean version: {lean_version}"
                    )
                    return ReusableLeanServer(server, workspace_path, self)
                except Exception as e:
                    logger.warning(f"Failed to initialize Lake project, using standalone mode: {e}")
                    # Detect Lean version from lean-toolchain file
                    lean_version = self._detect_lean_version(workspace_path)
                    config = LeanREPLConfig(lean_version=lean_version)
                    server = LeanServer(config)
                    return ReusableLeanServer(server, workspace_path, self)
            else:
                # No Lake project - use standalone mode with detected version
                logger.info("Created reusable server in standalone mode")
                lean_version = self._detect_lean_version(workspace_path)
                config = LeanREPLConfig(lean_version=lean_version)
                server = LeanServer(config)
                return ReusableLeanServer(server, workspace_path, self)

        except Exception as e:
            raise RuntimeError(f"Failed to create Lean server: {e}") from e

    def verify_file(
        self,
        workspace_path: Path,
        file_path: str,
        theorem_id: str | None,
        budget_s: float,
    ) -> LeanRunResult:
        """
        Run Lean verification on file or theorem using LeanInteract.

        This method implements the core verification logic:
        1. If theorem_id provided, find theorem's line range for filtering
        2. Initialize LeanServer in workspace context (lake env)
        3. Use FileCommand to check full file
        4. Filter diagnostics to theorem's line range if theorem-level
        5. Parse response for errors, warnings, sorries
        6. Enforce timeout with process tree kill
        6. Return structured result

        Args:
            workspace_path: Path to isolated workspace
            file_path: Path to Lean file (relative to workspace)
            theorem_id: Optional theorem identifier for theorem-level verification
            budget_s: Time budget in seconds

        Returns:
            LeanRunResult with status, diagnostics, logs, timing

        Raises:
            ValueError: If theorem_id is invalid or not found
            RuntimeError: If Lean process fails unexpectedly

        Requirements: 1.1, 1.3, 2.1, 2.2, 4.2, 4.3
        """
        start_time = time.time()
        
        # CRITICAL: Change to workspace directory so elan can find lean-toolchain
        # This must happen BEFORE any LeanServer operations because subprocesses
        # spawned by lean-interact will inherit this working directory
        original_cwd = os.getcwd()
        os.chdir(workspace_path)
        logger.info(f"Changed working directory to {workspace_path} for elan toolchain resolution")

        # Determine verification scope and theorem line range
        theorem_line_range = None
        if theorem_id:
            # Theorem-level: get theorem's line range for filtering
            target_file, theorem_line_range = self._prepare_theorem_verification(
                workspace_path, file_path, theorem_id
            )
            scope_used = "theorem"
        else:
            # File-level: verify entire file
            target_file = file_path
            scope_used = "file"

        # Check if LeanInteract is available
        if not LEAN_INTERACT_AVAILABLE or LeanServer is None:
            os.chdir(original_cwd)  # Restore before raising
            raise RuntimeError(
                "LeanInteract library not installed. Install with: pip install lean-interact"
            )

        # Initialize LeanServer with project context
        server = None
        try:
            # For workspace isolation, we need to decide:
            # - If workspace has a Lake project (lakefile.toml), use it for import resolution
            # - But DON'T let LocalProject rebuild - it should use existing .lake/
            #
            # Strategy: Check if workspace has lakefile, if so try to use project context
            lakefile_path = workspace_path / "lakefile.toml"
            lakefile_lean_path = workspace_path / "lakefile.lean"

            if lakefile_path.exists() or lakefile_lean_path.exists():
                # Has Lake project - try to use it
                try:
                    # CRITICAL: auto_build=False prevents rebuilding
                    # Detect Lean version for logging purposes
                    lean_version = self._detect_lean_version(workspace_path)
                    
                    project = LocalProject(directory=str(workspace_path), auto_build=False)
                    config = LeanREPLConfig(project=project)
                    server = LeanServer(config)
                    
                    logger.info(
                        f"Using Lake project context from {workspace_path}, "
                        f"Lean version: {lean_version}"
                    )
                except Exception as e:
                    # If project initialization fails, fall back to standalone with detected version
                    logger.warning(f"Failed to initialize Lake project, using standalone mode: {e}")
                    lean_version = self._detect_lean_version(workspace_path)
                    config = LeanREPLConfig(lean_version=lean_version)
                    server = LeanServer(config)
            else:
                # No Lake project - use standalone mode with detected version
                logger.info("No lakefile found, using standalone mode")
                lean_version = self._detect_lean_version(workspace_path)
                config = LeanREPLConfig(lean_version=lean_version)
                server = LeanServer(config)

            # Run file verification with timeout
            command = FileCommand(path=target_file)
            response = server.run(command, timeout=budget_s)

            # Check if response indicates an error (including timeout)
            if isinstance(response, LeanError):
                # LeanError response - could be timeout or other error
                elapsed = time.time() - start_time
                error_msg = str(response)

                # Check if it's a timeout error
                if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                    return LeanRunResult(
                        status="timeout",
                        diagnostics=[],
                        scope_used=scope_used,
                        full_logs=error_msg,
                        timing={"lean_execution_s": elapsed},
                        exit_code=-1,
                    )
                else:
                    # Other error
                    return LeanRunResult(
                        status="error",
                        diagnostics=[],
                        scope_used=scope_used,
                        full_logs=error_msg,
                        timing={"lean_execution_s": elapsed},
                        exit_code=1,
                    )

            # Parse diagnostics from response
            diagnostics = self._parse_diagnostics(response)

            # Filter diagnostics to theorem's line range if theorem-level verification
            if theorem_id and theorem_line_range:
                start_line, end_line = theorem_line_range
                diagnostics = self._filter_diagnostics_by_range(diagnostics, start_line, end_line)

            elapsed = time.time() - start_time

            # Determine status based on diagnostics
            has_errors = any(d["severity"] == "error" for d in diagnostics)
            status = "fail" if has_errors else "success"

            return LeanRunResult(
                status=status,
                diagnostics=diagnostics,
                scope_used=scope_used,
                full_logs=self._capture_logs(response),
                timing={"lean_execution_s": elapsed},
                exit_code=0,
            )

        except TimeoutError:
            elapsed = time.time() - start_time
            return LeanRunResult(
                status="timeout",
                diagnostics=[],
                scope_used="theorem" if theorem_id else "file",
                full_logs="Verification timed out",
                timing={"lean_execution_s": elapsed},
                exit_code=-1,
            )

        finally:
            # Always close server to cleanup Lean process
            if server is not None:
                from contextlib import suppress

                with suppress(Exception):
                    server.kill()
            
            # Restore original working directory
            os.chdir(original_cwd)
            logger.info(f"Restored working directory to {original_cwd}")

    def _prepare_theorem_verification(
        self,
        workspace_path: Path,
        file_path: str,
        theorem_id: str,
    ) -> tuple[str, tuple[int, int]]:
        """
        Prepare theorem-level verification by finding theorem's line range.

        Instead of extracting the theorem into a separate file (which breaks
        context and dependencies), this method finds the theorem's line range
        so we can filter diagnostics after verifying the full file.

        Strategy:
        1. Parse the file to find the theorem by theorem_id
        2. Get the theorem's line range (start_line, end_line)
        3. Return the original file path and line range
        4. Caller will verify full file and filter diagnostics

        Args:
            workspace_path: Path to isolated workspace
            file_path: Path to original Lean file
            theorem_id: Theorem identifier to verify

        Returns:
            Tuple of (target_file_path, (start_line, end_line))

        Raises:
            ValueError: If theorem_id not found in file

        Requirements: 2.1, 2.2
        """
        from ..core.indexer import build_index, find_by_id
        from ..core.source import SourceText

        # Read the original file
        full_path = workspace_path / file_path
        if not full_path.exists():
            raise ValueError(f"File not found: {file_path}")

        file_content = full_path.read_text(encoding='utf-8')

        # Parse file to find theorem
        source = SourceText(path=file_path, text=file_content)
        index = build_index(source)
        theorem = find_by_id(index, theorem_id)

        if not theorem:
            raise ValueError(f"Theorem not found: {theorem_id}")

        # Get theorem's line range for filtering diagnostics
        start_line = theorem.decl_span.start_line
        end_line = theorem.decl_span.end_line

        # Return relative file path (consistent with file-level verification)
        # and line range for filtering
        return file_path, (start_line, end_line)

    def _filter_diagnostics_by_range(
        self,
        diagnostics: list[dict],
        start_line: int,
        end_line: int,
    ) -> list[dict]:
        """
        Filter diagnostics to only those within the specified line range.

        This enables theorem-specific verification by filtering full-file
        diagnostics to only those relevant to the target theorem.

        Args:
            diagnostics: List of diagnostic dicts from full-file verification
            start_line: Start line of theorem (inclusive)
            end_line: End line of theorem (inclusive)

        Returns:
            Filtered list of diagnostics within the line range

        Requirements: 2.1, 2.2
        """
        filtered = []
        for diag in diagnostics:
            location = diag.get("location")
            if location is None:
                # Diagnostics without location are file-level, exclude them
                continue

            line = location.get("line", 0)

            # Include diagnostic if its line is within the theorem's range
            if start_line <= line <= end_line:
                filtered.append(diag)

        return filtered

    def _parse_diagnostics(self, response: Any) -> list[dict]:
        """
        Parse diagnostics from LeanInteract response.

        This method extracts:
        - Error and warning messages from the messages array
        - Sorry (incomplete proof) warnings from the sorries array

        Args:
            response: LeanInteract CommandResponse object

        Returns:
            List of normalized diagnostic dicts

        Requirements: 1.4, 5.1, 5.2, 5.3
        """
        diagnostics = []

        # Parse messages array for errors/warnings
        if hasattr(response, "messages"):
            for msg in response.messages:
                severity = self._normalize_severity(msg.severity)

                # Safely extract position info - check both hasattr and not None
                start_pos = getattr(msg, "start_pos", None)
                end_pos = getattr(msg, "end_pos", None)

                diagnostic = {
                    "severity": severity,
                    "message": msg.data,
                    "location": {
                        "file": "",  # Will be set by caller
                        "line": start_pos.line if start_pos is not None else 0,
                        "col": start_pos.column if start_pos is not None else 0,
                        "end_line": end_pos.line if end_pos is not None else None,
                        "end_col": end_pos.column if end_pos is not None else None,
                    },
                }
                diagnostics.append(diagnostic)

        # Parse sorries array for incomplete proofs
        if hasattr(response, "sorries"):
            for sorry in response.sorries:
                # Safely extract position info - check both hasattr and not None
                start_pos = getattr(sorry, "start_pos", None)
                end_pos = getattr(sorry, "end_pos", None)

                diagnostic = {
                    "severity": "warning",
                    "message": "Incomplete proof (sorry)",
                    "location": {
                        "file": "",  # Will be set by caller
                        "line": start_pos.line if start_pos is not None else 0,
                        "col": start_pos.column if start_pos is not None else 0,
                        "end_line": end_pos.line if end_pos is not None else None,
                        "end_col": end_pos.column if end_pos is not None else None,
                    },
                }
                diagnostics.append(diagnostic)

        return diagnostics

    def _normalize_severity(self, severity: str) -> str:
        """
        Normalize severity string to standard values.

        Args:
            severity: Raw severity string from LeanInteract

        Returns:
            Normalized severity ("error", "warning", or "info")

        Requirements: 5.1, 5.2
        """
        severity_lower = severity.lower()
        if "error" in severity_lower:
            return "error"
        elif "warn" in severity_lower:
            return "warning"
        else:
            return "info"

    def _capture_logs(self, response: Any) -> str:
        """
        Capture full logs from LeanInteract response.

        Args:
            response: LeanInteract CommandResponse object

        Returns:
            Full log string combining all output

        Requirements: 1.4
        """
        logs = []

        # Capture messages
        if hasattr(response, "messages"):
            for msg in response.messages:
                logs.append(f"[{msg.severity}] {msg.data}")

        # Capture sorries
        if hasattr(response, "sorries"):
            for sorry in response.sorries:
                logs.append(f"[sorry] {sorry.goal}")

        return "\n".join(logs) if logs else ""

    def _detect_lean_version(self, workspace_path: Path) -> str:
        """
        Detect Lean version from lean-toolchain file in workspace.

        This method searches for a lean-toolchain file in the workspace and
        extracts the Lean version. If not found, falls back to a default version.

        Args:
            workspace_path: Path to workspace directory

        Returns:
            Lean version string (e.g., "v4.15.0" or "leanprover/lean4:v4.27.0")

        Requirements: 1.1, 1.3
        """
        toolchain_path = workspace_path / "lean-toolchain"

        if toolchain_path.exists():
            try:
                toolchain_content = toolchain_path.read_text().strip()
                logger.info(f"Detected Lean version from lean-toolchain: {toolchain_content}")
                return toolchain_content
            except Exception as e:
                logger.warning(f"Failed to read lean-toolchain file: {e}")

        # Fallback to default version
        default_version = "v4.15.0"
        logger.info(f"No lean-toolchain found, using default version: {default_version}")
        return default_version


class ReusableLeanServer:
    """
    Reusable Lean server wrapper for batch operations.

    This class wraps a LeanServer instance and provides the LeanServer protocol
    interface, enabling efficient batch verification by reusing the same server
    across multiple theorems.

    Requirements: Performance optimization for batch operations
    """

    def __init__(
        self,
        server: Any,  # LeanServer from lean_interact
        workspace_path: Path,
        runner: LeanInteractRunner,
    ):
        """
        Initialize reusable server wrapper.

        Args:
            server: LeanServer instance from lean_interact
            workspace_path: Path to workspace
            runner: Parent LeanInteractRunner for helper methods
        """
        self.server = server
        self.workspace_path = workspace_path
        self.runner = runner

    def verify_file(
        self,
        file_path: str,
        theorem_id: str | None,
        budget_s: float,
    ) -> LeanRunResult:
        """
        Run Lean verification using this server instance.

        This method reuses the existing server instead of creating a new one,
        avoiding the LocalProject/LeanServer initialization overhead.

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

        Requirements: Performance optimization for batch operations
        """
        start_time = time.time()

        # Determine verification scope and theorem line range
        theorem_line_range = None
        if theorem_id:
            # Theorem-level: get theorem's line range for filtering
            target_file, theorem_line_range = self.runner._prepare_theorem_verification(
                self.workspace_path, file_path, theorem_id
            )
            scope_used = "theorem"
        else:
            # File-level: verify entire file
            target_file = file_path
            scope_used = "file"

        try:
            # Run file verification with timeout using the reusable server
            command = FileCommand(path=target_file)
            response = self.server.run(command, timeout=budget_s)

            # Check if response indicates an error (including timeout)
            if isinstance(response, LeanError):
                # LeanError response - could be timeout or other error
                elapsed = time.time() - start_time
                error_msg = str(response)

                # Check if it's a timeout error
                if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                    return LeanRunResult(
                        status="timeout",
                        diagnostics=[],
                        scope_used=scope_used,
                        full_logs=error_msg,
                        timing={"lean_execution_s": elapsed},
                        exit_code=-1,
                    )
                else:
                    # Other error
                    return LeanRunResult(
                        status="error",
                        diagnostics=[],
                        scope_used=scope_used,
                        full_logs=error_msg,
                        timing={"lean_execution_s": elapsed},
                        exit_code=1,
                    )

            # Parse diagnostics from response
            diagnostics = self.runner._parse_diagnostics(response)

            # Filter diagnostics to theorem's line range if theorem-level verification
            if theorem_id and theorem_line_range:
                start_line, end_line = theorem_line_range
                diagnostics = self.runner._filter_diagnostics_by_range(
                    diagnostics, start_line, end_line
                )

            elapsed = time.time() - start_time

            # Determine status based on diagnostics
            has_errors = any(d["severity"] == "error" for d in diagnostics)
            status = "fail" if has_errors else "success"

            return LeanRunResult(
                status=status,
                diagnostics=diagnostics,
                scope_used=scope_used,
                full_logs=self.runner._capture_logs(response),
                timing={"lean_execution_s": elapsed},
                exit_code=0,
            )

        except TimeoutError:
            elapsed = time.time() - start_time
            return LeanRunResult(
                status="timeout",
                diagnostics=[],
                scope_used="theorem" if theorem_id else "file",
                full_logs="Verification timed out",
                timing={"lean_execution_s": elapsed},
                exit_code=-1,
            )

    def close(self) -> None:
        """
        Close the server and cleanup resources.

        This method kills the Lean server process and cleans up resources.
        It does not raise exceptions - cleanup errors are logged.

        Requirements: Performance optimization for batch operations
        """
        if self.server is not None:
            from contextlib import suppress

            with suppress(Exception):
                self.server.kill()
                logger.info("Closed reusable Lean server")
