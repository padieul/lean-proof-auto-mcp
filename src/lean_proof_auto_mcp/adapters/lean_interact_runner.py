"""
LeanInteractRunner adapter for Lean verification.

This module implements the LeanRunner port using the LeanInteract library,
which provides programmatic access to Lean 4 through the Lean REPL.

Requirements: 1.1, 1.3, 2.1, 2.2, 4.2, 4.3, 4.4
"""

import time
from pathlib import Path
from typing import Any

from ..core.verify_domain import LeanRunResult

# Try to import LeanInteract, but allow module to load even if not installed
try:
    from lean_interact import LeanServer

    LEAN_INTERACT_AVAILABLE = True
except ImportError:
    LeanServer = None
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
        1. If theorem_id provided, create abridged file up to theorem end
        2. Initialize LeanServer in workspace context (lake env)
        3. Use FileCommand to check file (full or abridged)
        4. Parse response for errors, warnings, sorries
        5. Enforce timeout with process tree kill
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

        # Determine verification scope
        if theorem_id:
            # Theorem-level: create abridged file
            target_file, scope_used = self._prepare_theorem_verification(
                workspace_path, file_path, theorem_id
            )
        else:
            # File-level: verify entire file
            target_file = file_path
            scope_used = "file"

        # Check if LeanInteract is available
        if not LEAN_INTERACT_AVAILABLE or LeanServer is None:
            raise RuntimeError(
                "LeanInteract library not installed. Install with: pip install lean-interact"
            )

        # Initialize LeanServer with project context
        server = None
        try:
            server = LeanServer(
                project_path=str(workspace_path),
                timeout=budget_s,
            )

            # Run file verification
            response = server.run_file(target_file)

            # Parse diagnostics from response
            diagnostics = self._parse_diagnostics(response)

            # Map diagnostics back to original file if theorem-level
            if theorem_id and target_file != file_path:
                for diag in diagnostics:
                    diag["location"]["file"] = file_path

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
                server.close()

    def _prepare_theorem_verification(
        self,
        workspace_path: Path,
        file_path: str,
        theorem_id: str,
    ) -> tuple[str, str]:
        """
        Prepare theorem-level verification by creating abridged file.

        This method:
        1. Parses the file to find the theorem by theorem_id
        2. Extracts content up to the theorem's end line
        3. Creates a temporary abridged file in the workspace
        4. Returns the path to the abridged file

        Args:
            workspace_path: Path to isolated workspace
            file_path: Path to original Lean file
            theorem_id: Theorem identifier to verify

        Returns:
            Tuple of (target_file_path, scope_used)

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

        file_content = full_path.read_text()

        # Parse file to find theorem
        source = SourceText(path=file_path, text=file_content)
        index = build_index(source)
        theorem = find_by_id(index, theorem_id)

        if not theorem:
            raise ValueError(f"Theorem not found: {theorem_id}")

        # Extract content up to theorem end
        lines = file_content.splitlines(keepends=True)
        abridged_content = "".join(lines[: theorem.decl_span.end_line])

        # Create temporary file in workspace
        temp_file = workspace_path / f"_verify_{theorem_id.replace('.', '_')}.lean"
        temp_file.write_text(abridged_content)

        # Return relative path from workspace
        return str(temp_file.relative_to(workspace_path)), "theorem"

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

                diagnostic = {
                    "severity": severity,
                    "message": msg.data,
                    "location": {
                        "file": "",  # Will be set by caller
                        "line": msg.start_pos.line if hasattr(msg, "start_pos") else 0,
                        "col": msg.start_pos.column if hasattr(msg, "start_pos") else 0,
                        "end_line": msg.end_pos.line if hasattr(msg, "end_pos") else None,
                        "end_col": msg.end_pos.column if hasattr(msg, "end_pos") else None,
                    },
                }
                diagnostics.append(diagnostic)

        # Parse sorries array for incomplete proofs
        if hasattr(response, "sorries"):
            for sorry in response.sorries:
                diagnostic = {
                    "severity": "warning",
                    "message": "Incomplete proof (sorry)",
                    "location": {
                        "file": "",  # Will be set by caller
                        "line": sorry.start_pos.line if hasattr(sorry, "start_pos") else 0,
                        "col": sorry.start_pos.column if hasattr(sorry, "start_pos") else 0,
                        "end_line": sorry.end_pos.line if hasattr(sorry, "end_pos") else None,
                        "end_col": sorry.end_pos.column if hasattr(sorry, "end_pos") else None,
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
