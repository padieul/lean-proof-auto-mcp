"""
Core domain structures and ports for the verify tool.

This module defines the immutable data structures and abstract interfaces (ports)
for Lean verification following hexagonal architecture principles.

Requirements: 1.1, 1.2, 1.5, 6.1, 7.1
"""

import hashlib
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)

# ============================================================================
# Command and Result Data Structures (Immutable)
# ============================================================================


@dataclass(frozen=True)
class VerifyCommand:
    """
    Immutable command representing a verification request.

    Requirements: 1.1

    Attributes:
        file_path: Path to the Lean file to verify
        theorem_id: Optional theorem identifier for theorem-level verification
        budget_s: Time budget in seconds (default: 30.0)
        max_log_excerpt_chars: Maximum characters for log excerpts (default: 2000)
        store_full_logs: Whether to store full logs as artifacts (default: True)
        workspace_mode: Workspace isolation mode ("worktree", "temp", or None for auto)
    """

    file_path: str
    theorem_id: str | None = None
    budget_s: float = 30.0
    max_log_excerpt_chars: int = 2000
    store_full_logs: bool = True
    workspace_mode: str | None = None

    def __post_init__(self) -> None:
        """Validate command parameters."""
        if not self.file_path:
            raise ValueError("file_path must be non-empty")
        if self.budget_s <= 0:
            raise ValueError("budget_s must be positive")
        if self.max_log_excerpt_chars <= 0:
            raise ValueError("max_log_excerpt_chars must be positive")
        valid_modes = ("worktree", "temp", "none")
        if self.workspace_mode is not None and self.workspace_mode not in valid_modes:
            raise ValueError("workspace_mode must be 'worktree', 'temp', 'none', or None")


@dataclass(frozen=True)
class VerifyResult:
    """
    Final verification result returned to the user.

    Requirements: 1.1, 8.3

    Attributes:
        api_version: API version string (e.g., "0.2.0")
        status: Verification status ("success", "fail", "timeout", "error")
        run_id: Unique identifier for this verification run
        file: Path to the verified file
        theorem_id: Theorem identifier if theorem-level verification
        verification_scope_used: Actual scope used ("file", "theorem", "file_fallback")
        diagnostics: List of diagnostic messages
        diagnostic_summary: Summary counts by severity
        evidence: Evidence section with log excerpts and notes
        metadata: Metadata about the verification environment
        timing: Timing information
    """

    api_version: str
    status: str
    run_id: str
    file: str
    theorem_id: str | None
    verification_scope_used: str
    diagnostics: list[dict]
    diagnostic_summary: dict
    evidence: dict
    metadata: dict
    timing: dict


# ============================================================================
# Internal Data Structures
# ============================================================================


@dataclass(frozen=True)
class LeanRunResult:
    """
    Result from Lean execution (internal adapter output).

    Requirements: 1.1, 1.3, 1.4

    Attributes:
        status: Execution status ("success", "fail", "timeout")
        diagnostics: Raw diagnostics from Lean
        scope_used: Scope that was verified ("file", "theorem", "file_fallback")
        full_logs: Complete stdout/stderr logs
        timing: Timing information dict
        exit_code: Lean process exit code
    """

    status: str
    diagnostics: list[dict]
    scope_used: str
    full_logs: str
    timing: dict[str, float]
    exit_code: int


@dataclass(frozen=True)
class Workspace:
    """
    Isolated workspace metadata.

    Requirements: 1.2, 6.1

    Attributes:
        path: Path to the workspace directory
        workspace_id: Unique identifier for this workspace
        mode: Workspace mode ("worktree" or "temp")
    """

    path: Path
    workspace_id: str
    mode: str


# ============================================================================
# Port Interfaces (Abstract)
# ============================================================================


class LeanServer(Protocol):
    """
    Abstract interface for a reusable Lean server instance.

    This port represents a long-lived Lean server that can be reused
    across multiple verification requests, avoiding repeated initialization overhead.

    Requirements: Performance optimization for batch operations
    """

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
        ...

    def close(self) -> None:
        """
        Close the server and cleanup resources.

        This method should be called when the server is no longer needed.
        It should not raise exceptions - cleanup errors should be logged.
        """
        ...


class LeanRunner(Protocol):
    """
    Abstract interface for running Lean verification.

    This port defines how the core domain interacts with Lean execution,
    without depending on specific implementation details (LeanInteract, etc.).

    Requirements: 1.1, 1.3, 2.1, 2.2
    """

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
        """
        ...

    def create_server(self, workspace_path: Path) -> LeanServer:
        """
        Create a reusable Lean server for the given workspace.

        This method creates a long-lived server that can be reused across
        multiple verification requests, avoiding repeated initialization overhead.

        Args:
            workspace_path: Path to isolated workspace

        Returns:
            LeanServer instance that can be reused

        Raises:
            RuntimeError: If server creation fails
        """
        ...


class WorkspaceProvider(Protocol):
    """
    Abstract interface for workspace isolation.

    This port defines how the core domain creates and manages isolated
    workspaces, without depending on specific implementation (git worktree, temp copy).

    Requirements: 1.2, 6.1, 6.3
    """

    def create_workspace(self, file_path: str) -> Workspace:
        """
        Create isolated workspace for verification.

        Args:
            file_path: Path to file being verified (for context)

        Returns:
            Workspace with path and metadata

        Raises:
            RuntimeError: If workspace creation fails
        """
        ...

    def cleanup_workspace(self, workspace: Workspace) -> None:
        """
        Clean up workspace resources.

        Args:
            workspace: Workspace to clean up

        Note:
            This method should not raise exceptions. Cleanup errors should be
            logged but not propagated to ensure cleanup always completes.
        """
        ...


class ArtifactStore(Protocol):
    """
    Abstract interface for artifact storage.

    This port defines how the core domain stores verification artifacts,
    without depending on specific storage implementation (filesystem, S3, etc.).

    Requirements: 1.5, 7.1
    """

    def store(
        self,
        run_id: str,
        command: VerifyCommand,
        result: VerifyResult,
        full_logs: str,
    ) -> None:
        """
        Store verification artifacts under run_id directory.

        Args:
            run_id: Unique identifier for this verification run
            command: Original verification command
            result: Verification result
            full_logs: Complete stdout/stderr logs

        Raises:
            RuntimeError: If artifact storage fails
        """
        ...


# ============================================================================
# Command Handler (Core Orchestrator)
# ============================================================================


class VerifyCommandHandler:
    """
    Orchestrates verification using injected ports.

    This handler implements the core verification workflow following hexagonal
    architecture principles. It depends only on abstract ports (LeanRunner,
    WorkspaceProvider, ArtifactStore) and contains no infrastructure logic.

    Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 4.1, 4.2, 6.3
    """

    def __init__(
        self,
        lean_runner: LeanRunner,
        workspace_provider: WorkspaceProvider,
        artifact_store: ArtifactStore,
        metadata_collector: "MetadataCollector | None" = None,
    ):
        """
        Initialize handler with dependency injection.

        Args:
            lean_runner: Port for running Lean verification
            workspace_provider: Port for workspace isolation
            artifact_store: Port for artifact storage
            metadata_collector: Optional port for collecting environment metadata

        Requirements: 1.1
        """
        self.lean_runner = lean_runner
        self.workspace_provider = workspace_provider
        self.artifact_store = artifact_store
        self.metadata_collector = metadata_collector

    def handle(self, cmd: VerifyCommand) -> VerifyResult:
        """
        Execute verification workflow.

        This method orchestrates the entire verification process:
        1. Generate unique run_id
        2. Create isolated workspace
        3. Run Lean verification with timeout
        4. Parse and normalize diagnostics
        5. Determine status from results
        6. Build complete result with all sections
        7. Store artifacts if requested
        8. Ensure workspace cleanup

        Args:
            cmd: Verification command with all parameters

        Returns:
            VerifyResult with complete verification information

        Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 4.1, 4.2, 6.3
        """
        start_time = time.time()

        # 1. Generate run_id
        run_id = self._generate_run_id(cmd)

        # 2. Create isolated workspace
        workspace = self.workspace_provider.create_workspace(cmd.file_path)

        try:
            # 3. Run Lean verification with timeout
            lean_result = self.lean_runner.verify_file(
                workspace_path=workspace.path,
                file_path=cmd.file_path,
                theorem_id=cmd.theorem_id,
                budget_s=cmd.budget_s,
            )

            # 4. Parse and normalize diagnostics
            diagnostics = self._normalize_diagnostics(lean_result.diagnostics)

            # 4b. Check for errors in logs (e.g., LeanError messages)
            if lean_result.status == "error" and not diagnostics:
                # Parse error from logs
                error_diagnostic = self._parse_error_from_logs(lean_result.full_logs)
                if error_diagnostic:
                    diagnostics.append(error_diagnostic)

            # 5. Determine status
            status = self._determine_status(lean_result, diagnostics)

            # Calculate timing
            total_time = time.time() - start_time
            lean_execution_s = lean_result.timing.get("lean_execution_s", 0.0)
            overhead_s = total_time - lean_execution_s

            # 6. Build result
            result = VerifyResult(
                api_version="0.2.0",
                status=status,
                run_id=run_id,
                file=cmd.file_path,
                theorem_id=cmd.theorem_id,
                verification_scope_used=lean_result.scope_used,
                diagnostics=diagnostics,
                diagnostic_summary=self._build_diagnostic_summary(diagnostics),
                evidence=self._build_evidence(lean_result, cmd.max_log_excerpt_chars),
                metadata=self._build_metadata(workspace, lean_result),
                timing=self._build_timing(total_time, lean_execution_s, overhead_s),
            )

            # 7. Store artifacts if requested
            if cmd.store_full_logs:
                self.artifact_store.store(run_id, cmd, result, lean_result.full_logs)

            # 8. Ensure deterministic output
            return result

        finally:
            # 9. Cleanup workspace (always runs)
            self.workspace_provider.cleanup_workspace(workspace)

    def _generate_run_id(self, cmd: VerifyCommand) -> str:
        """
        Generate unique run_id with timestamp, file hash, and random suffix.

        Format: verify-YYYYMMDD-HHMMSS-<file_hash>-<random_suffix>

        The random suffix ensures uniqueness even when multiple verifications
        run concurrently on the same file within the same second.

        Args:
            cmd: Verification command

        Returns:
            Unique run_id string

        Requirements: 1.5, 7.3, 6.4 (concurrent execution safety)
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        file_hash = hashlib.md5(cmd.file_path.encode()).hexdigest()[:8]
        # Add random suffix for uniqueness in concurrent executions
        random_suffix = uuid.uuid4().hex[:6]
        return f"verify-{timestamp}-{file_hash}-{random_suffix}"

    def _normalize_diagnostics(self, diagnostics: list[dict]) -> list[dict]:
        """
        Normalize and sort diagnostics for deterministic output.

        This method:
        - Ensures all diagnostics have required fields
        - Maps severity strings to standard values
        - Sorts by (file, line, col, severity, message)
        - Handles None/missing location data safely

        Args:
            diagnostics: Raw diagnostics from Lean

        Returns:
            Normalized and sorted diagnostics

        Requirements: 1.4, 3.1, 3.2, 5.1, 5.2
        """
        # Normalize each diagnostic
        normalized = []
        for diag in diagnostics:
            # Safely extract location, handling None case
            location = diag.get("location")

            # If location is explicitly None, keep it as None (for errors without location)
            if location is None:
                normalized_location = None
            elif isinstance(location, dict):
                # Normalize dict location
                normalized_location = {
                    "file": location.get("file", ""),
                    "line": location.get("line", 0),
                    "col": location.get("col", 0),
                    "end_line": location.get("end_line"),
                    "end_col": location.get("end_col"),
                }
            else:
                # Invalid location type, treat as None
                normalized_location = None

            normalized_diag = {
                "severity": self._normalize_severity(diag.get("severity", "error")),
                "message": diag.get("message", ""),
                "location": normalized_location,
            }
            normalized.append(normalized_diag)

        # Sort diagnostics deterministically
        return self._sort_diagnostics(normalized)

    def _parse_error_from_logs(self, logs: str) -> dict | None:
        """
        Parse error messages from logs when no structured diagnostics available.

        This handles cases where LeanError or other errors appear in logs but
        weren't captured as structured diagnostics.

        Args:
            logs: Full log output

        Returns:
            Diagnostic dict or None if no error found

        Requirements: 5.1, 5.2
        """
        if not logs:
            return None

        # Check for LeanError pattern
        if "LeanError" in logs or "error" in logs.lower():
            # Extract the error message
            message = logs.strip()

            # Try to extract just the message part from LeanError(message='...')
            import re

            match = re.search(r"LeanError\(message='([^']+)'\)", message)
            if match:
                message = match.group(1)

            return {
                "severity": "error",
                "message": message,
                "location": None,  # No location info available for log-based errors
            }

        return None

    def _normalize_severity(self, severity: str) -> str:
        """
        Map severity strings to standard values.

        Args:
            severity: Raw severity string

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

    def _sort_diagnostics(self, diagnostics: list[dict]) -> list[dict]:
        """
        Sort diagnostics by (file, line, col, severity, message).

        Diagnostics with None locations are sorted last.

        Args:
            diagnostics: List of normalized diagnostics

        Returns:
            Sorted diagnostics list

        Requirements: 3.1, 3.2
        """
        severity_order = {"error": 0, "warning": 1, "info": 2}

        def sort_key(d: dict) -> tuple:
            location = d["location"]
            if location is None:
                # Sort None locations last
                return ("", 999999, 999999, severity_order.get(d["severity"], 3), d["message"])
            else:
                return (
                    location["file"],
                    location["line"],
                    location["col"],
                    severity_order.get(d["severity"], 3),
                    d["message"],
                )

        return sorted(diagnostics, key=sort_key)

    def _determine_status(self, lean_result: LeanRunResult, diagnostics: list[dict]) -> str:
        """
        Determine verification status from Lean result and diagnostics.

        Args:
            lean_result: Result from Lean execution
            diagnostics: Normalized diagnostics

        Returns:
            Status string ("success", "fail", "timeout", or "error")

        Requirements: 1.1
        """
        # If Lean reported timeout, return timeout
        if lean_result.status == "timeout":
            return "timeout"

        # If Lean reported error status, return error
        if lean_result.status == "error":
            return "error"

        # If exit code is non-zero, return error
        if lean_result.exit_code != 0:
            return "error"

        # If there are error diagnostics, return fail
        if any(d["severity"] == "error" for d in diagnostics):
            return "fail"

        # Otherwise, return success
        return "success"

    def _build_diagnostic_summary(self, diagnostics: list[dict]) -> dict[str, int]:
        """
        Build diagnostic summary with counts by severity.

        Args:
            diagnostics: List of normalized diagnostics

        Returns:
            Dict with error_count, warning_count, info_count

        Requirements: 5.4
        """
        error_count = sum(1 for d in diagnostics if d["severity"] == "error")
        warning_count = sum(1 for d in diagnostics if d["severity"] == "warning")
        info_count = sum(1 for d in diagnostics if d["severity"] == "info")

        return {
            "error_count": error_count,
            "warning_count": warning_count,
            "info_count": info_count,
        }

    def _build_evidence(
        self, lean_result: LeanRunResult, max_log_excerpt_chars: int
    ) -> dict[str, Any]:
        """
        Build evidence section with log excerpts and notes.

        Args:
            lean_result: Result from Lean execution
            max_log_excerpt_chars: Maximum characters for excerpts

        Returns:
            Evidence dict with stdout_excerpt, stderr_excerpt, notes

        Requirements: 5.5
        """
        # Extract stdout and stderr from full logs
        # For now, treat full_logs as stdout (adapters will separate if needed)
        stdout_excerpt = self._truncate_log(lean_result.full_logs, max_log_excerpt_chars)
        stderr_excerpt = ""

        # Build notes array
        notes = []
        if lean_result.exit_code != 0:
            notes.append(f"exit_code: {lean_result.exit_code}")

        # Add note if status is error or timeout
        if lean_result.status in ("error", "timeout"):
            notes.append(f"lean_status: {lean_result.status}")

        return {
            "stdout_excerpt": stdout_excerpt,
            "stderr_excerpt": stderr_excerpt,
            "notes": notes,
        }

    def _truncate_log(self, log: str, max_chars: int) -> str:
        """
        Truncate log deterministically at last newline before limit.

        Args:
            log: Full log string
            max_chars: Maximum characters

        Returns:
            Truncated log with "... (truncated)" suffix if needed

        Requirements: 3.3, 1.6, 7.2
        """
        if len(log) <= max_chars:
            return log

        # Find last newline before max_chars
        truncate_point = log.rfind("\n", 0, max_chars)
        if truncate_point == -1:
            truncate_point = max_chars

        return log[:truncate_point] + "\n... (truncated)"

    def _build_metadata(self, workspace: Workspace, lean_result: LeanRunResult) -> dict[str, Any]:
        """
        Build metadata section with workspace and version information.

        Uses the injected MetadataCollector port to gather environment
        metadata (git commit, lean version, lake version). If no collector
        is provided, returns only workspace information.

        Args:
            workspace: Workspace metadata
            lean_result: Result from Lean execution

        Returns:
            Metadata dict with workspace_mode, workspace_id, and version info

        Requirements: 6.5, 8.4
        """
        metadata: dict[str, Any] = {
            "workspace_mode": workspace.mode,
            "workspace_id": workspace.workspace_id,
        }

        # Collect version information if metadata collector is available
        if self.metadata_collector is not None:
            version_info = self.metadata_collector.collect_version_info()
            metadata.update(version_info)
        else:
            logger.debug("No metadata collector configured, skipping version metadata collection")

        return metadata

    def _build_timing(
        self, total_s: float, lean_execution_s: float, overhead_s: float
    ) -> dict[str, float]:
        """
        Build timing section with execution times.

        Args:
            total_s: Total elapsed time
            lean_execution_s: Time spent in Lean execution
            overhead_s: Overhead time (total - lean_execution)

        Returns:
            Timing dict with total_s, lean_execution_s, overhead_s

        Requirements: 4.5
        """
        return {
            "total_s": round(total_s, 2),
            "lean_execution_s": round(lean_execution_s, 2),
            "overhead_s": round(overhead_s, 2),
        }
