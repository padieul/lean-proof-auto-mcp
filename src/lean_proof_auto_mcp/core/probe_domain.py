"""
Core domain structures and ports for the probe and probe_file tools.

This module defines the immutable data structures and abstract interfaces (ports)
for automation probing following hexagonal architecture principles.

Requirements: 1.1, 1.8, 2.1-2.6, 3.1-3.8, 4.1-4.7, 5.1-5.6
"""

from dataclasses import dataclass
from typing import Any, Protocol

# ============================================================================
# Command and Result Data Structures (Immutable)
# ============================================================================


@dataclass(frozen=True)
class ProbeCommand:
    """
    Immutable command representing a probe request.

    This command encapsulates a single-theorem automation attempt with
    controlled conditions (mode, budget, trace configuration).

    Requirements: 1.1, 1.8, 3.1

    Attributes:
        file_path: Path to Lean file
        theorem_id: Theorem identifier to probe
        mode: Automation mode ("aesop", "aesop?", or "grind")
        budget_s: Time budget in seconds (default: 10.0)
        trace_config: Optional trace configuration for debugging
    """

    file_path: str
    theorem_id: str
    mode: str
    budget_s: float = 10.0
    trace_config: dict[str, bool] | None = None

    def __post_init__(self) -> None:
        """
        Validate command parameters.

        Raises:
            ValueError: If any parameter is invalid

        Requirements: 1.8, 3.1, 10.3, 10.5
        """
        if not self.file_path:
            raise ValueError("file_path must be non-empty")
        if not self.theorem_id:
            raise ValueError("theorem_id must be non-empty")
        if self.mode not in ("aesop", "aesop?", "grind"):
            raise ValueError("mode must be 'aesop', 'aesop?', or 'grind'")
        if self.budget_s <= 0:
            raise ValueError("budget_s must be positive")


@dataclass(frozen=True)
class ProbeOutcome:
    """
    Structured outcome of automation attempt.

    This dataclass encapsulates the result of running automation on a theorem,
    including the raw outcome, deterministic classification, and optional
    suggested script (for aesop? mode).

    Requirements: 2.1-2.6, 3.3, 3.4, 3.5

    Attributes:
        mode: Automation mode used
        outcome: Raw outcome ("closed", "not_closed", "timeout", "error")
        classification: Deterministic classification ("trivial", "promising", "failed", "timed_out", "error")
        suggested_script: Optional suggested script (for aesop? mode)
    """

    mode: str
    outcome: str
    classification: str
    suggested_script: str | None = None


@dataclass(frozen=True)
class ProbeResult:
    """
    Final result from single-theorem automation probe.

    This is the complete result returned to the user, containing all
    information about the probe attempt including outcome, diagnostics,
    timing, and metadata.

    Requirements: 1.5, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8

    Attributes:
        api_version: API version string
        status: Overall status ("success", "fail", "timeout", "error")
        run_id: Unique identifier for this probe run
        probe_result: Detailed probe outcome
        diagnostics: List of diagnostic messages
        timing: Timing information
        metadata: Metadata about execution environment
    """

    api_version: str
    status: str
    run_id: str
    probe_result: ProbeOutcome
    diagnostics: list[dict]
    timing: dict[str, float]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ProbeFileCommand:
    """
    Immutable command for batch automation probing.

    This command encapsulates a batch probe request across multiple theorems
    in a file, with controlled conditions and ordering.

    Requirements: 4.1-4.7, 5.1-5.6

    Attributes:
        file_path: Path to Lean file
        mode: Automation mode ("aesop", "aesop?", or "grind")
        budget_s_per: Time budget per theorem in seconds (default: 5.0)
        limit: Maximum number of theorems to probe (default: 50)
        ordering: Ordering mode ("file_order" or "rank_targets", default: "file_order")
    """

    file_path: str
    mode: str
    budget_s_per: float = 5.0
    limit: int = 50
    ordering: str = "file_order"

    def __post_init__(self) -> None:
        """
        Validate command parameters.

        Raises:
            ValueError: If any parameter is invalid

        Requirements: 5.1, 5.5, 5.6, 10.3, 10.5
        """
        if not self.file_path:
            raise ValueError("file_path must be non-empty")
        if self.mode not in ("aesop", "aesop?", "grind"):
            raise ValueError("mode must be 'aesop', 'aesop?', or 'grind'")
        if self.budget_s_per <= 0:
            raise ValueError("budget_s_per must be positive")
        if self.limit <= 0:
            raise ValueError("limit must be positive")
        if self.ordering not in ("file_order", "rank_targets"):
            raise ValueError("ordering must be 'file_order' or 'rank_targets'")


@dataclass(frozen=True)
class ProbeFileResult:
    """
    Final result from batch automation probing.

    This is the complete result returned to the user, containing both
    per-theorem results and file-level summary statistics.

    Requirements: 4.5, 5.2, 5.3, 5.4

    Attributes:
        api_version: API version string
        status: Overall status ("success", "partial", "error")
        file: Path to probed file
        summary: Summary statistics (total, closed, promising, failed, timed_out)
        results: Per-theorem results
        metadata: Metadata about execution
    """

    api_version: str
    status: str
    file: str
    summary: dict[str, int]
    results: list[dict]
    metadata: dict[str, Any]


# ============================================================================
# Port Interfaces (Abstract)
# ============================================================================


class AutomationClassifier(Protocol):
    """
    Abstract interface for classifying automation outcomes.

    This port encapsulates the logic for deterministically classifying
    automation attempts into categories (trivial, promising, failed, timed_out, error).

    The classifier uses heuristics based on outcome, diagnostics, timing, and budget
    to determine the classification.

    Requirements: 2.1-2.6

    Methods:
        classify: Classify automation outcome based on execution results
    """

    def classify(
        self,
        outcome: str,
        diagnostics: list[dict],
        timing: dict[str, float],
        budget_s: float,
    ) -> str:
        """
        Classify automation outcome.

        This method applies deterministic rules to classify the outcome of an
        automation attempt. The classification helps downstream tools decide
        whether to pursue further search or annotation.

        Args:
            outcome: Raw outcome ("closed", "not_closed", "timeout", "error")
            diagnostics: Diagnostic messages from Lean
            timing: Timing information
            budget_s: Time budget that was allocated

        Returns:
            Classification string ("trivial", "promising", "failed", "timed_out", "error")

        Requirements: 2.1-2.6
        """
        ...


# ============================================================================
# Command Handler (Core Orchestrator)
# ============================================================================

import hashlib
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


class ProbeCommandHandler:
    """
    Orchestrates single-theorem automation probing.

    This handler implements the core probe workflow following hexagonal
    architecture principles. It depends only on abstract ports (LeanRunner,
    WorkspaceProvider, AutomationClassifier) and contains no infrastructure logic.

    The workflow:
    1. Generate unique run_id
    2. Create isolated workspace
    3. Construct automation harness
    4. Run Lean with automation tactic
    5. Parse and classify outcome
    6. Build structured result
    7. Ensure workspace cleanup

    Requirements: 1.1-1.6, 3.2-3.8, 6.1-6.4, 7.1-7.4, 8.1-8.2, 10.1-10.5
    """

    def __init__(
        self,
        lean_runner: "LeanRunner",
        workspace_provider: "WorkspaceProvider",
        classifier: AutomationClassifier,
    ):
        """
        Initialize handler with dependency injection.

        Args:
            lean_runner: Port for running Lean verification
            workspace_provider: Port for workspace isolation
            classifier: Port for classifying automation outcomes

        Requirements: 1.1, 6.1, 6.2
        """
        self.lean_runner = lean_runner
        self.workspace_provider = workspace_provider
        self.classifier = classifier

    def handle(self, cmd: ProbeCommand) -> ProbeResult:
        """
        Execute probe workflow with comprehensive error handling.

        This method orchestrates the entire probe process with explicit
        error handling at each stage following the Result/Either pattern.

        Error handling strategy:
        - Validation errors: Early return with error result
        - Workspace errors: Return error result with workspace details
        - Execution errors: Convert to appropriate error/timeout results
        - Classification: Should not fail (defensive)
        - Cleanup: Always runs, errors logged but not propagated

        Args:
            cmd: Probe command with all parameters

        Returns:
            ProbeResult with complete probe information

        Requirements: 1.1-1.6, 3.2-3.8, 6.1-6.4, 7.1-7.4, 8.1-8.2, 10.1-10.5
        """
        start_time = time.time()

        # 1. Generate run_id
        run_id = self._generate_run_id(cmd)

        # 2. Create isolated workspace
        workspace = None
        try:
            workspace = self.workspace_provider.create_workspace(cmd.file_path)
        except Exception as e:
            logger.error(f"Workspace creation failed: {e}")
            return self._build_error_result(
                cmd, run_id, "workspace_error", f"Failed to create workspace: {e}", start_time
            )

        try:
            # 3. Construct automation harness
            try:
                harness_content = self._construct_harness(cmd, workspace.path)
            except ValueError as e:
                # Theorem not found or invalid
                logger.error(f"Harness construction failed: {e}")
                return self._build_error_result(
                    cmd, run_id, "theorem_not_found", str(e), start_time
                )
            except Exception as e:
                logger.error(f"Unexpected harness construction error: {e}")
                return self._build_error_result(
                    cmd, run_id, "harness_error", f"Failed to construct harness: {e}", start_time
                )

            # 4. Run Lean with automation tactic
            try:
                lean_result = self.lean_runner.verify_file(
                    workspace_path=workspace.path,
                    file_path=cmd.file_path,
                    theorem_id=cmd.theorem_id,
                    budget_s=cmd.budget_s,
                )
            except TimeoutError:
                # Timeout is expected, convert to timeout result
                logger.info(f"Probe timed out after {cmd.budget_s}s")
                return self._build_timeout_result(cmd, run_id, start_time)
            except ValueError as e:
                # Theorem not found or invalid
                logger.error(f"Theorem validation failed: {e}")
                return self._build_error_result(
                    cmd, run_id, "theorem_not_found", str(e), start_time
                )
            except Exception as e:
                # Toolchain or execution error
                logger.error(f"Lean execution failed: {e}")
                return self._build_error_result(
                    cmd, run_id, "execution_error", f"Lean execution failed: {e}", start_time
                )

            # 5. Parse and classify outcome
            # Normalize diagnostics
            diagnostics = self._normalize_diagnostics(lean_result.diagnostics)

            # Determine raw outcome
            if lean_result.status == "timeout":
                outcome = "timeout"
            elif lean_result.status == "error":
                outcome = "error"
            elif lean_result.status == "success":
                outcome = "closed"
            else:
                outcome = "not_closed"

            # Classify outcome
            classification = self.classifier.classify(
                outcome, diagnostics, lean_result.timing, cmd.budget_s
            )

            # Extract suggested script for aesop? mode
            suggested_script = None
            if cmd.mode == "aesop?" and outcome == "closed":
                suggested_script = self._extract_suggested_script(lean_result.full_logs)

            # 6. Build structured result
            return self._build_result(
                cmd, run_id, outcome, classification, suggested_script, diagnostics, lean_result, start_time
            )

        finally:
            # 7. Cleanup workspace (always runs)
            if workspace:
                try:
                    self.workspace_provider.cleanup_workspace(workspace)
                except Exception as e:
                    # Log but don't propagate cleanup errors
                    logger.warning(f"Workspace cleanup failed: {e}")

    def _generate_run_id(self, cmd: ProbeCommand) -> str:
        """
        Generate unique run_id with timestamp, file hash, and random suffix.

        Format: probe-YYYYMMDD-HHMMSS-<file_hash>-<random_suffix>

        The random suffix ensures uniqueness even when multiple probes
        run concurrently on the same file within the same second.

        Args:
            cmd: Probe command

        Returns:
            Unique run_id string

        Requirements: 3.2, 7.2 (stateless execution)
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        file_hash = hashlib.md5(cmd.file_path.encode()).hexdigest()[:8]
        # Add random suffix for uniqueness in concurrent executions
        random_suffix = uuid.uuid4().hex[:6]
        return f"probe-{timestamp}-{file_hash}-{random_suffix}"

    def _construct_harness(self, cmd: ProbeCommand, workspace_path: Path) -> str:
        """
        Build automation test harness.

        The harness imports the original file, extracts the theorem signature,
        and replaces the proof with the automation tactic.

        Format:
        ```lean
        import <original_file>

        -- Optional trace configuration
        set_option trace.aesop true

        theorem <theorem_name> : <theorem_type> := by
          <automation_tactic>
        ```

        Args:
            cmd: Probe command with file, theorem, mode
            workspace_path: Path to workspace

        Returns:
            Harness content as string

        Raises:
            ValueError: If theorem not found or invalid

        Requirements: 1.2, 3.2
        """
        # Read the original file to find the theorem
        file_path = workspace_path / cmd.file_path
        if not file_path.exists():
            raise ValueError(f"File not found: {cmd.file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Find the theorem declaration
        # Simple pattern: "theorem <name> :" or "theorem <name> (...) :"
        import re

        # Pattern to match theorem declarations
        theorem_pattern = rf"theorem\s+{re.escape(cmd.theorem_id)}\s*[^:]*:"
        match = re.search(theorem_pattern, content)

        if not match:
            raise ValueError(f"Theorem '{cmd.theorem_id}' not found in {cmd.file_path}")

        # Extract theorem signature (everything up to ":=")
        theorem_start = match.start()
        theorem_decl_end = content.find(":=", theorem_start)
        if theorem_decl_end == -1:
            # No ":=" found, might be a sorry or axiom
            raise ValueError(f"Theorem '{cmd.theorem_id}' has no proof body")

        theorem_signature = content[theorem_start:theorem_decl_end].strip()

        # Build harness
        # Convert file path to module import path (remove .lean, replace / with .)
        import_path = cmd.file_path.replace(".lean", "").replace("/", ".").replace("\\", ".")

        harness_lines = [
            f"import {import_path}",
            "",
        ]

        # Add trace configuration if requested
        if cmd.trace_config:
            for key, value in cmd.trace_config.items():
                harness_lines.append(f"set_option {key} {str(value).lower()}")
            harness_lines.append("")

        # Add theorem with automation tactic
        harness_lines.append(f"{theorem_signature} := by")
        harness_lines.append(f"  {cmd.mode}")

        return "\n".join(harness_lines)

    def _extract_suggested_script(self, logs: str) -> str | None:
        """
        Extract suggested script from aesop? output.

        Aesop? mode outputs a suggested proof script when successful.
        This method parses the logs to extract that script.

        Args:
            logs: Full log output from Lean

        Returns:
            Suggested script or None if not found

        Requirements: 3.5
        """
        if not logs:
            return None

        # Look for aesop? suggestion pattern
        # Typically appears as "Try this: <script>"
        import re

        match = re.search(r"Try this:\s*(.+?)(?:\n|$)", logs, re.DOTALL)
        if match:
            return match.group(1).strip()

        return None

    def _normalize_diagnostics(self, diagnostics: list[dict]) -> list[dict]:
        """
        Normalize and sort diagnostics for deterministic output.

        This method reuses the same normalization logic as verify to ensure
        consistent behavior across tools.

        Args:
            diagnostics: Raw diagnostics from Lean

        Returns:
            Normalized and sorted diagnostics

        Requirements: 6.4, 9.1, 9.3
        """
        # Normalize each diagnostic
        normalized = []
        for diag in diagnostics:
            # Safely extract location, handling None case
            location = diag.get("location")

            # If location is explicitly None, keep it as None
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

    def _normalize_severity(self, severity: str) -> str:
        """
        Map severity strings to standard values.

        Args:
            severity: Raw severity string

        Returns:
            Normalized severity ("error", "warning", or "info")

        Requirements: 9.3
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

        Requirements: 9.1
        """
        severity_order = {"error": 0, "warning": 1, "info": 2}

        def sort_key(d: dict) -> tuple:
            location = d["location"]
            if location is None:
                # Sort None locations last using high values
                return ("~" * 100, 999999, 999999, severity_order.get(d["severity"], 3), d["message"])
            else:
                return (
                    location["file"],
                    location["line"],
                    location["col"],
                    severity_order.get(d["severity"], 3),
                    d["message"],
                )

        return sorted(diagnostics, key=sort_key)

    def _build_result(
        self,
        cmd: ProbeCommand,
        run_id: str,
        outcome: str,
        classification: str,
        suggested_script: str | None,
        diagnostics: list[dict],
        lean_result: Any,
        start_time: float,
    ) -> ProbeResult:
        """
        Construct ProbeResult with all required fields.

        Args:
            cmd: Original probe command
            run_id: Unique run identifier
            outcome: Raw outcome
            classification: Deterministic classification
            suggested_script: Optional suggested script (aesop? mode)
            diagnostics: Normalized diagnostics
            lean_result: Result from Lean execution
            start_time: Start time for timing calculation

        Returns:
            Complete ProbeResult

        Requirements: 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8
        """
        elapsed_s = time.time() - start_time
        elapsed_ms = elapsed_s * 1000.0

        # Build probe outcome
        probe_outcome = ProbeOutcome(
            mode=cmd.mode,
            outcome=outcome,
            classification=classification,
            suggested_script=suggested_script,
        )

        # Determine status
        if outcome == "error":
            status = "error"
        elif outcome == "timeout":
            status = "timeout"
        elif outcome == "closed":
            status = "success"
        else:
            status = "fail"

        # Build timing
        timing = {
            "elapsed_ms": round(elapsed_ms, 2),
            "budget_s": cmd.budget_s,
        }

        # Build metadata
        metadata = self._build_metadata(lean_result)

        return ProbeResult(
            api_version="0.1.0",
            status=status,
            run_id=run_id,
            probe_result=probe_outcome,
            diagnostics=diagnostics,
            timing=timing,
            metadata=metadata,
        )

    def _build_error_result(
        self,
        cmd: ProbeCommand,
        run_id: str,
        error_type: str,
        error_message: str,
        start_time: float,
    ) -> ProbeResult:
        """
        Build error result for various error cases.

        Args:
            cmd: Original probe command
            run_id: Unique run identifier
            error_type: Type of error (validation_error, workspace_error, etc.)
            error_message: Error message
            start_time: Start time for timing calculation

        Returns:
            ProbeResult with error status

        Requirements: 10.1, 10.2, 10.3, 10.5
        """
        elapsed_s = time.time() - start_time
        elapsed_ms = elapsed_s * 1000.0

        # Build error outcome
        probe_outcome = ProbeOutcome(
            mode=cmd.mode,
            outcome="error",
            classification="error",
            suggested_script=None,
        )

        # Build error diagnostic
        diagnostics = [
            {
                "severity": "error",
                "message": f"{error_type}: {error_message}",
                "location": None,
            }
        ]

        # Build timing
        timing = {
            "elapsed_ms": round(elapsed_ms, 2),
            "budget_s": cmd.budget_s,
        }

        # Build minimal metadata
        metadata = {
            "error_type": error_type,
        }

        return ProbeResult(
            api_version="0.1.0",
            status="error",
            run_id=run_id,
            probe_result=probe_outcome,
            diagnostics=diagnostics,
            timing=timing,
            metadata=metadata,
        )

    def _build_timeout_result(
        self,
        cmd: ProbeCommand,
        run_id: str,
        start_time: float,
    ) -> ProbeResult:
        """
        Build timeout result.

        Args:
            cmd: Original probe command
            run_id: Unique run identifier
            start_time: Start time for timing calculation

        Returns:
            ProbeResult with timeout status

        Requirements: 8.1, 8.2
        """
        elapsed_s = time.time() - start_time
        elapsed_ms = elapsed_s * 1000.0

        # Build timeout outcome
        probe_outcome = ProbeOutcome(
            mode=cmd.mode,
            outcome="timeout",
            classification="timed_out",
            suggested_script=None,
        )

        # Build timing
        timing = {
            "elapsed_ms": round(elapsed_ms, 2),
            "budget_s": cmd.budget_s,
        }

        # Build minimal metadata
        metadata = {
            "timeout": True,
        }

        return ProbeResult(
            api_version="0.1.0",
            status="timeout",
            run_id=run_id,
            probe_result=probe_outcome,
            diagnostics=[],
            timing=timing,
            metadata=metadata,
        )

    def _build_metadata(self, lean_result: Any) -> dict[str, Any]:
        """
        Build metadata section with workspace and version information.

        Args:
            lean_result: Result from Lean execution

        Returns:
            Metadata dict

        Requirements: 3.8
        """
        import subprocess

        metadata: dict[str, Any] = {}

        # Detect repo commit
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=1.0,
                check=False,
            )
            if result.returncode == 0:
                metadata["repo_commit"] = result.stdout.strip()
        except Exception:
            pass  # Git not available or not a git repo

        # Detect Lean version
        try:
            result = subprocess.run(
                ["lean", "--version"],
                capture_output=True,
                text=True,
                timeout=1.0,
                check=False,
            )
            if result.returncode == 0:
                metadata["lean_version"] = result.stdout.strip()
        except Exception:
            pass  # Lean not available

        # Detect Lake version
        try:
            result = subprocess.run(
                ["lake", "--version"],
                capture_output=True,
                text=True,
                timeout=1.0,
                check=False,
            )
            if result.returncode == 0:
                metadata["lake_version"] = result.stdout.strip()
        except Exception:
            pass  # Lake not available

        return metadata


# Import LeanRunner and WorkspaceProvider from verify_domain for type hints
from .verify_domain import LeanRunner, Workspace, WorkspaceProvider  # noqa: E402
