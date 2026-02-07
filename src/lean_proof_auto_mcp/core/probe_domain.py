"""

Core domain structures and ports for the probe and probe_file tools.


This module defines the immutable data structures and abstract interfaces (ports)

for automation probing following hexagonal architecture principles.


Requirements: 1.1, 1.8, 2.1-2.6, 3.1-3.8, 4.1-4.7, 5.1-5.6
"""


import contextlib

import hashlib
import logging
import time
import uuid

from collections.abc import Callable
from dataclasses import dataclass

from datetime import datetime, timezone

from pathlib import Path

from typing import TYPE_CHECKING, Any, Protocol


if TYPE_CHECKING:

    from ..observability.ports import MetadataCollector

    from .harness_construction import HarnessConstructor


logger = logging.getLogger(__name__)


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

        classification: Deterministic classification

            ("trivial", "promising", "failed", "timed_out", "error")

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



class ArtifactStore(Protocol):
    """

    Abstract interface for artifact storage.


    This port defines how the core domain stores probe artifacts,

    without depending on specific storage implementation (filesystem, S3, etc.).


    Requirements: Logging and debugging support
    """


    def store(

        self,

        run_id: str,

        command: Any,

        result: Any,

        full_logs: str,

    ) -> None:
        """

        Store probe artifacts under run_id directory.


        Args:

            run_id: Unique identifier for this probe run

            command: Original probe command

            result: Probe result

            full_logs: Complete logs from Lean execution


        Raises:

            RuntimeError: If artifact storage fails
        """
        ...



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



class ProbeCommandHandler:
    """

    Orchestrates single-theorem automation probing.


    This handler implements the core probe workflow following hexagonal

    architecture principles. It depends only on abstract ports (LeanRunner,

    WorkspaceProvider, AutomationClassifier, HarnessConstructor) and contains
    no infrastructure logic.


    The workflow:

    1. Generate unique run_id

    2. Create isolated workspace

    3. Construct automation harness (via HarnessConstructor)

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

        harness_constructor: "HarnessConstructor | None" = None,

        artifact_store: ArtifactStore | None = None,

        metadata_collector: "MetadataCollector | None" = None,

    ):
        """

        Initialize handler with dependency injection.


        Args:

            lean_runner: Port for running Lean verification

            workspace_provider: Port for workspace isolation

            classifier: Port for classifying automation outcomes

            harness_constructor: Optional port for constructing test harnesses

            artifact_store: Optional port for artifact storage

            metadata_collector: Optional port for collecting environment metadata


        Requirements: 1.1, 6.1, 6.2
        """
        self.lean_runner = lean_runner

        self.workspace_provider = workspace_provider
        self.classifier = classifier
        self.harness_constructor = harness_constructor
        self.artifact_store = artifact_store
        self.metadata_collector = metadata_collector


    def handle(self, cmd: ProbeCommand, lean_server: "LeanServer | None" = None) -> ProbeResult:
        """

        Execute probe workflow with comprehensive error handling.


        This method orchestrates the entire probe process with explicit

        error handling at each stage following the Result/Either pattern.


        If a lean_server is provided, it will be reused instead of creating

        a new workspace and server. This enables efficient batch probing.


        Error handling strategy:

        - Validation errors: Early return with error result

        - Workspace errors: Return error result with workspace details

        - Execution errors: Convert to appropriate error/timeout results

        - Classification: Should not fail (defensive)

        - Cleanup: Always runs, errors logged but not propagated


        Args:

            cmd: Probe command with all parameters

            lean_server: Optional reusable Lean server (for batch operations)


        Returns:

            ProbeResult with complete probe information


        Requirements: 1.1-1.6, 3.2-3.8, 6.1-6.4, 7.1-7.4, 8.1-8.2, 10.1-10.5
        """

        start_time = time.time()


        # 1. Generate run_id

        run_id = self._generate_run_id(cmd)


        # 2. Determine if we're using a reusable server or creating a workspace

        if lean_server is not None:

            # Server reuse mode: skip workspace creation

            return self._handle_with_server(cmd, run_id, lean_server, start_time)
        else:

            # Traditional mode: create workspace and use lean_runner

            return self._handle_with_workspace(cmd, run_id, start_time)


    def _handle_with_workspace(

        self, cmd: ProbeCommand, run_id: str, start_time: float

    ) -> ProbeResult:
        """

        Execute probe with workspace creation (traditional mode).


        This is the original implementation that creates a workspace,

        runs verification, and cleans up.


        Args:

            cmd: Probe command

            run_id: Unique run identifier

            start_time: Start time for timing


        Returns:

            ProbeResult


        Requirements: 1.1-1.6, 3.2-3.8, 6.1-6.4, 7.1-7.4, 8.1-8.2, 10.1-10.5
        """

        # 2. Create isolated workspace

        workspace = None

        harness_file_path = None

        try:

            workspace = self.workspace_provider.create_workspace(cmd.file_path)

        except Exception as e:

            logger.error(f"Workspace creation failed: {e}")

            return self._build_error_result(

                cmd, run_id, "workspace_error", f"Failed to create workspace: {e}", start_time

            )


        try:

            # 3. Construct automation harness and write to file

            try:

                harness_content = self._construct_harness(cmd, workspace.path)

                harness_file_path = self._write_harness(cmd, workspace.path, harness_content)

                logger.info(f"Wrote harness file: {harness_file_path}")

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


            # 4. Run Lean with automation tactic on the harness file

            try:

                lean_result = self.lean_runner.verify_file(

                    workspace_path=workspace.path,

                    file_path=harness_file_path,

                    theorem_id=None,  # Harness has only one theorem, no need to filter

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

            logger.info("Processing Lean result...")

            result = self._process_lean_result(cmd, run_id, lean_result, start_time, workspace)

            logger.info("Lean result processed, preparing to return...")


            # 6. Store artifacts if artifact_store is configured (async to not block response)

            if self.artifact_store is not None:
                import threading


                def store_async():

                    try:

                        self.artifact_store.store(run_id, cmd, result, lean_result.full_logs)

                    except Exception as e:

                        logger.warning(f"Failed to store artifacts for {run_id}: {e}")


                thread = threading.Thread(target=store_async, daemon=True)

                thread.start()

                logger.info("Started background thread for artifact storage")


            logger.info("About to return result from handle()")
            return result


        finally:

            # 7. Cleanup harness file and workspace (always runs)

            logger.info("Entering finally block for cleanup...")
            if harness_file_path:

                try:

                    harness_path = workspace.path / harness_file_path

                    if harness_path.exists():

                        harness_path.unlink()

                        logger.debug(f"Cleaned up harness file: {harness_file_path}")

                except Exception as e:

                    logger.warning(f"Harness file cleanup failed: {e}")

            logger.info("Finally block completed")


            if workspace:

                try:

                    self.workspace_provider.cleanup_workspace(workspace)

                except Exception as e:

                    # Log but don't propagate cleanup errors

                    logger.warning(f"Workspace cleanup failed: {e}")


    def _handle_with_server(

        self,

        cmd: ProbeCommand,

        run_id: str,

        lean_server: "LeanServer",

        start_time: float,

    ) -> ProbeResult:
        """

        Execute probe with reusable server (optimized mode).


        This mode skips workspace creation and reuses an existing Lean server,

        significantly reducing overhead for batch operations.


        Note: The workspace must already exist and contain the harness file.


        Args:

            cmd: Probe command

            run_id: Unique run identifier

            lean_server: Reusable Lean server

            start_time: Start time for timing


        Returns:

            ProbeResult


        Requirements: Performance optimization for batch operations
        """

        # Note: In server reuse mode, the workspace and harness are managed

        # by ProbeFileCommandHandler, so we just need to construct the harness

        # filename and verify it


        # Generate harness filename (must match _write_harness logic)

        safe_theorem_id = "".join(c if c.isalnum() else "_" for c in cmd.theorem_id)

        harness_filename = f"_probe_harness_{safe_theorem_id}.lean"


        try:

            # Run verification using the reusable server on the harness file

            lean_result = lean_server.verify_file(

                file_path=harness_filename,

                theorem_id=None,  # Harness has only one theorem

                budget_s=cmd.budget_s,

            )

        except TimeoutError:

            logger.info(f"Probe timed out after {cmd.budget_s}s")

            return self._build_timeout_result(cmd, run_id, start_time)

        except ValueError as e:

            logger.error(f"Theorem validation failed: {e}")

            return self._build_error_result(cmd, run_id, "theorem_not_found", str(e), start_time)

        except Exception as e:

            logger.error(f"Lean execution failed: {e}")

            return self._build_error_result(

                cmd, run_id, "execution_error", f"Lean execution failed: {e}", start_time

            )


        # Process the result (no workspace object in server reuse mode)

        result = self._process_lean_result(cmd, run_id, lean_result, start_time, workspace=None)


        # Store artifacts if artifact_store is configured (async to not block response)

        if self.artifact_store is not None:
            import threading


            def store_async():

                try:

                    self.artifact_store.store(run_id, cmd, result, lean_result.full_logs)

                except Exception as e:

                    logger.warning(f"Failed to store artifacts for {run_id}: {e}")


            thread = threading.Thread(target=store_async, daemon=True)

            thread.start()

        return result


    def _process_lean_result(

        self,

        cmd: ProbeCommand,

        run_id: str,

        lean_result: Any,

        start_time: float,

        workspace: Any | None,

    ) -> ProbeResult:
        """

        Process Lean result and build ProbeResult.


        This method handles the common logic for processing Lean results,

        whether from workspace mode or server reuse mode.


        Args:

            cmd: Probe command

            run_id: Unique run identifier

            lean_result: Result from Lean execution

            start_time: Start time for timing

            workspace: Optional workspace object (for metadata)


        Returns:

            ProbeResult


        Requirements: 3.2-3.8
        """

        # Normalize diagnostics

        logger.info("Normalizing diagnostics...")

        diagnostics = self._normalize_diagnostics(lean_result.diagnostics)


        # Determine raw outcome

        logger.info(f"Determining outcome from status={lean_result.status}...")
        if lean_result.status == "timeout":
            outcome = "timeout"
        elif lean_result.status == "error":
            outcome = "error"
        elif lean_result.status == "success":
            outcome = "closed"
        else:
            outcome = "not_closed"


        # Classify outcome

        logger.info(f"Calling classifier.classify() with outcome={outcome}...")

        classification = self.classifier.classify(

            outcome, diagnostics, lean_result.timing, cmd.budget_s

        )

        logger.info(f"Classification complete: {classification}")


        # Extract suggested script for aesop? mode

        logger.info("Extracting suggested script...")

        suggested_script = None

        if cmd.mode == "aesop?" and outcome == "closed":

            suggested_script = self._extract_suggested_script(lean_result.full_logs)


        # Build structured result

        logger.info("Building result...")

        return self._build_result(

            cmd,

            run_id,

            outcome,

            classification,

            suggested_script,

            diagnostics,

            lean_result,

            start_time,

        )


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


    def _write_harness(self, cmd: ProbeCommand, workspace_path: Path, harness_content: str) -> str:
        """

        Write harness content to a temporary file in the workspace.


        The harness file is named based on the theorem_id to avoid collisions

        when multiple probes run concurrently.


        Args:

            cmd: Probe command

            workspace_path: Path to workspace

            harness_content: Harness content to write


        Returns:

            Relative path to harness file (for passing to lean_runner)


        Raises:

            IOError: If file writing fails


        Requirements: 1.2, 3.2
        """

        # Generate harness filename based on theorem_id

        # Use a safe filename by replacing non-alphanumeric characters

        safe_theorem_id = "".join(c if c.isalnum() else "_" for c in cmd.theorem_id)

        harness_filename = f"_probe_harness_{safe_theorem_id}.lean"

        harness_path = workspace_path / harness_filename


        try:

            with open(harness_path, "w", encoding="utf-8") as f:

                f.write(harness_content)
            return harness_filename

        except Exception as e:

            raise OSError(f"Failed to write harness file: {e}") from e


    def _construct_harness(self, cmd: ProbeCommand, workspace_path: Path) -> str:
        """

        Build automation test harness using ImportBasedHarnessConstructor.


        This method creates a HarnessConstructor with the workspace context
        to ensure correct import path resolution.


        Args:

            cmd: Probe command with file, theorem, mode

            workspace_path: Path to workspace


        Returns:

            Harness content as string


        Raises:

            ValueError: If theorem not found or invalid


        Requirements: 1.2, 3.2
        """

        # Always use ImportBasedHarnessConstructor with workspace context

        # This ensures correct import path resolution

        from ..lean.querier import LeanInteractQuerierImpl

        from ..lean.server_manager import LeanInteractServerManager
        from .harness_construction import (
            HarnessConfig,
            HarnessError,
            ImportBasedHarnessConstructor,

            LeanInteractTheoremTypeExtractor,

            StandardImportPathConverter,

        )


        # Create ServerManager with workspace context

        server_manager = LeanInteractServerManager(workspace_path=workspace_path)


        # Build HarnessConstructor with workspace context

        querier = LeanInteractQuerierImpl(server_manager=server_manager)

        type_extractor = LeanInteractTheoremTypeExtractor(querier)

        path_converter = StandardImportPathConverter()

        harness_constructor = ImportBasedHarnessConstructor(

            type_extractor=type_extractor, path_converter=path_converter

        )


        # Convert absolute file_path to relative path from project root

        # The workspace is a copy of the project, so we need the relative path

        file_path_obj = Path(cmd.file_path)

        if file_path_obj.is_absolute():

            # Find the project root by looking for lakefile.toml or lakefile.lean

            project_root = self._find_project_root(file_path_obj)

            if project_root:

                try:

                    relative_path = file_path_obj.relative_to(project_root)

                    file_path_for_harness = str(relative_path)

                except ValueError:

                    # Fallback: use the original path
                    file_path_for_harness = cmd.file_path
            else:

                # No project root found, use original path
                file_path_for_harness = cmd.file_path
        else:
            file_path_for_harness = cmd.file_path


        # For type extraction, we need to find the file in the workspace

        # The workspace_path is the Lean project root (where lakefile is)

        # We need to find where the file is relative to that workspace

        #

        # Strategy: Look for the file in the workspace by checking if it exists

        # at workspace_path / file_path_for_harness

        file_in_workspace = workspace_path / file_path_for_harness

        if file_in_workspace.exists():

            # File exists at this location, use relative path for extraction
            pass
        else:

            # File doesn't exist there, try to find it

            # Maybe the workspace is at a different level

            # Try using just the filename parts after "Fixtures" or other capital letter

            parts = Path(file_path_for_harness).parts

            # Find first capitalized part (likely the module root)

            for i, part in enumerate(parts):

                if part and part[0].isupper():

                    # Try from this part onwards

                    relative_from_capital = Path(*parts[i:])

                    candidate = workspace_path / relative_from_capital

                    if candidate.exists():

                        str(relative_from_capital)

                        file_path_for_harness = str(relative_from_capital)

                        break
            else:

                # Fallback: use the relative path as-is
                pass


        # Determine additional imports based on mode

        additional_imports = []

        if cmd.mode in ("aesop", "aesop?"):

            additional_imports.append("import Aesop")


        # Use ImportBasedHarnessConstructor to build the harness properly

        config = HarnessConfig(

            theorem_id=cmd.theorem_id,

            file_path=file_path_for_harness,

            proof_attempt=cmd.mode,

            additional_imports=additional_imports,

        )


        result = harness_constructor.construct(config)


        # Check if construction was successful

        if isinstance(result, HarnessError):

            raise ValueError(f"Harness construction failed: {result.message}")

        harness_content = result.code


        # Add trace configuration if requested
        if cmd.trace_config:

            # Insert trace options after imports

            lines = harness_content.split("\n")

            import_end = 0

            for i, line in enumerate(lines):

                if line.strip() and not line.strip().startswith("import"):
                    import_end = i

                    break


            trace_lines = []

            for key, value in cmd.trace_config.items():

                trace_lines.append(f"set_option {key} {str(value).lower()}")


            # Insert trace options after imports

            lines = lines[:import_end] + trace_lines + [""] + lines[import_end:]

            harness_content = "\n".join(lines)

        return harness_content


    def _find_project_root(self, file_path: Path) -> Path | None:
        """

        Find the Lean project root by looking for lakefile.toml or lakefile.lean.


        Args:

            file_path: Path to a file in the project


        Returns:

            Path to project root, or None if not found
        """

        current = file_path if file_path.is_dir() else file_path.parent


        # Search up to 10 levels

        for _ in range(10):

            if (current / "lakefile.toml").exists() or (current / "lakefile.lean").exists():
                return current

            parent = current.parent

            if parent == current:  # Reached filesystem root

                break
            current = parent


        return None


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

                return (

                    "~" * 100,

                    999999,

                    999999,

                    severity_order.get(d["severity"], 3),

                    d["message"],

                )
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

        logger.info("Building metadata...")

        metadata = self._build_metadata(lean_result)

        logger.info("Metadata built, creating ProbeResult...")


        result = ProbeResult(

            api_version="0.1.0",

            status=status,

            run_id=run_id,

            probe_result=probe_outcome,

            diagnostics=diagnostics,

            timing=timing,

            metadata=metadata,

        )

        logger.info("ProbeResult created successfully")
        return result


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

        Build metadata section with version information.


        Uses the injected MetadataCollector port to gather environment

        metadata (git commit, lean version, lake version). If no collector

        is provided, returns an empty dictionary.


        Args:

            lean_result: Result from Lean execution


        Returns:

            Metadata dict with version information


        Requirements: 3.8
        """

        if self.metadata_collector is None:

            logger.debug("No metadata collector configured, skipping metadata collection")

            return {}


        logger.info("Building metadata...")

        metadata = self.metadata_collector.collect_version_info()

        logger.info("Metadata built, creating ProbeResult...")
        return metadata



class ProbeFileCommandHandler:
    """

    Orchestrates batch automation probing.


    This handler implements the batch probe workflow following hexagonal

    architecture principles. It depends on ProbeCommandHandler for individual

    probes and scan_file/rank_targets functions for theorem enumeration.


    The workflow:

    1. Enumerate theorems using scan_file

    2. Apply ordering (file_order or rank_targets)

    3. Apply limit

    4. For each theorem, call ProbeCommandHandler

    5. Aggregate results into summary

    6. Return both per-theorem and file-level statistics


    Partial success semantics: If some theorems fail, continue processing
    remaining theorems and return status="partial".


    Requirements: 4.1-4.7, 5.2-5.6, 10.4
    """


    def __init__(

        self,

        probe_handler: ProbeCommandHandler,

        scan_file_fn: Callable,

        rank_targets_fn: Callable | None = None,

    ):
        """

        Initialize handler with dependency injection.


        Args:

            probe_handler: Handler for individual probe operations

            scan_file_fn: Function to call scan_file tool

            rank_targets_fn: Optional function to call rank_targets tool


        Requirements: 4.1, 5.5
        """

        self.probe_handler = probe_handler
        self.scan_file_fn = scan_file_fn

        self.rank_targets_fn = rank_targets_fn


    def handle(self, cmd: ProbeFileCommand) -> ProbeFileResult:
        """

        Execute batch probe workflow with server reuse for optimal performance.


        This method orchestrates the entire batch probe process:

        1. Enumerate theorems (fail fast if scan_file fails)

        2. Create workspace and Lean server ONCE

        3. Probe each theorem (reuse server for all theorems)

        4. Aggregate results into summary

        5. Determine overall status

        6. Cleanup server and workspace


        Server reuse eliminates repeated LocalProject/LeanServer initialization,

        providing significant performance improvement for large batches.


        Args:

            cmd: ProbeFileCommand with all parameters


        Returns:

            ProbeFileResult with per-theorem and file-level statistics


        Requirements: 4.1-4.7, 5.2-5.6, 10.4, Performance optimization
        """

        start_time = time.time()


        # 1. Enumerate theorems (fail fast if scan_file fails)

        try:

            theorem_ids = self._enumerate_theorems(cmd)

        except Exception as e:

            logger.error(f"Theorem enumeration failed: {e}")

            return self._build_error_result(cmd, str(e), start_time)


        # Handle empty file case
        if not theorem_ids:

            logger.warning(f"No theorems found in {cmd.file_path}")

            return ProbeFileResult(

                api_version="0.1.0",

                status="success",

                file=cmd.file_path,

                summary={"total": 0, "closed": 0, "promising": 0, "failed": 0, "timed_out": 0},

                results=[],

                metadata={"elapsed_ms": round((time.time() - start_time) * 1000.0, 2)},

            )


        # 2. Create workspace and Lean server ONCE for all theorems

        workspace = None

        try:

            # Create workspace

            workspace = self.probe_handler.workspace_provider.create_workspace(cmd.file_path)

            logger.info(f"Created workspace for batch probe: {workspace.workspace_id}")


            # Note: ServerManager handles server lifecycle automatically

            # No need to explicitly create server - it will be created on first use

            logger.info(f"Workspace ready for {len(theorem_ids)} theorems")


        except Exception as e:

            logger.error(f"Workspace creation failed: {e}")

            # Cleanup if partially created

            if workspace:

                with contextlib.suppress(Exception):

                    self.probe_handler.workspace_provider.cleanup_workspace(workspace)

            return self._build_error_result(cmd, f"Failed to create workspace: {e}", start_time)


        try:

            # 3. Probe each theorem (reuse server for all theorems)

            results = []

            errors = []

            harness_files = []  # Track harness files for cleanup

            for theorem_id in theorem_ids:

                try:

                    # Create probe command for this theorem

                    probe_cmd = ProbeCommand(

                        file_path=cmd.file_path,

                        theorem_id=theorem_id,

                        mode=cmd.mode,

                        budget_s=cmd.budget_s_per,

                    )


                    # Construct and write harness for this theorem

                    try:

                        harness_content = self.probe_handler._construct_harness(

                            probe_cmd, workspace.path

                        )

                        harness_file = self.probe_handler._write_harness(

                            probe_cmd, workspace.path, harness_content

                        )

                        harness_files.append(harness_file)

                        logger.debug(f"Wrote harness for theorem '{theorem_id}': {harness_file}")

                    except Exception as e:

                        logger.warning(

                            f"Failed to construct harness for theorem '{theorem_id}': {e}"

                        )

                        errors.append(

                            {"theorem_id": theorem_id, "error": f"Harness construction failed: {e}"}

                        )
                        continue


                    # Execute probe (ServerManager handles server reuse automatically)

                    probe_result = self.probe_handler.handle(probe_cmd)


                    # Extract summary for this theorem

                    theorem_summary = self._extract_summary(probe_result, theorem_id)

                    results.append(theorem_summary)


                except Exception as e:

                    # Log error but continue processing

                    logger.warning(f"Probe failed for theorem '{theorem_id}': {e}")

                    errors.append({"theorem_id": theorem_id, "error": str(e)})


            # 4. Aggregate results into summary

            summary = self._aggregate_results(results)


            # 5. Determine overall status

            if len(results) == 0:
                status = "error"

            elif len(errors) > 0:
                status = "partial"
            else:
                status = "success"


            # 6. Build final result

            elapsed_ms = round((time.time() - start_time) * 1000.0, 2)


            metadata: dict[str, Any] = {

                "elapsed_ms": elapsed_ms,

                "total_theorems": len(theorem_ids),

                "successful_probes": len(results),

                "failed_probes": len(errors),

                "server_reused": True,  # Indicate that server reuse was used

            }

            if errors:

                metadata["errors"] = errors


            return ProbeFileResult(

                api_version="0.1.0",

                status=status,

                file=cmd.file_path,

                summary=summary,

                results=results,

                metadata=metadata,

            )


        finally:

            # 7. Cleanup harness files, server, and workspace (always runs)

            # Clean up harness files
            for harness_file in harness_files:

                try:

                    harness_path = workspace.path / harness_file

                    if harness_path.exists():

                        harness_path.unlink()

                        logger.debug(f"Cleaned up harness file: {harness_file}")

                except Exception as e:

                    logger.warning(f"Harness file cleanup failed for {harness_file}: {e}")


            # Note: ServerManager handles server cleanup automatically

            # No need to explicitly close server


            if workspace:

                try:

                    self.probe_handler.workspace_provider.cleanup_workspace(workspace)

                    logger.info(f"Cleaned up workspace: {workspace.workspace_id}")

                except Exception as e:

                    logger.warning(f"Workspace cleanup failed: {e}")


    def _enumerate_theorems(self, cmd: ProbeFileCommand) -> list[str]:
        """

        Enumerate theorems using scan_file and optionally rank_targets.


        This method calls scan_file to get all theorems, applies the specified

        ordering mode, and enforces the limit.


        Args:

            cmd: ProbeFileCommand with file_path, ordering, and limit


        Returns:

            List of theorem_ids in specified order, limited to cmd.limit


        Raises:

            RuntimeError: If scan_file or rank_targets fails

            ValueError: If ordering mode requires rank_targets but it's not available


        Requirements: 4.1, 5.5, 5.6
        """

        # Call scan_file to get all theorems

        scan_result = self.scan_file_fn({"file": cmd.file_path})


        if scan_result.get("status") != "success":

            raise RuntimeError(f"scan_file failed: {scan_result.get('error', 'Unknown error')}")


        theorems = scan_result.get("theorems", [])


        # Apply ordering
        if cmd.ordering == "file_order":

            # Use file order (already sorted by scan_file)

            theorem_ids = [t["theorem_id"] for t in theorems]


        elif cmd.ordering == "rank_targets":

            # Use rank_targets to prioritize

            if self.rank_targets_fn is None:

                raise ValueError("rank_targets_fn required for rank_targets ordering")


            rank_result = self.rank_targets_fn(

                {

                    "file": cmd.file_path,

                    "objective": "maximize_success",

                    "limit": len(theorems),

                }

            )


            if rank_result.get("status") != "success":

                raise RuntimeError(

                    f"rank_targets failed: {rank_result.get('error', 'Unknown error')}"

                )


            # Extract theorem_ids from ranking

            theorem_ids = [t["theorem_id"] for t in rank_result.get("ranking", [])]

        else:

            raise ValueError(f"Invalid ordering mode: {cmd.ordering}")


        # Apply limit

        return theorem_ids[: cmd.limit]


    def _aggregate_results(self, results: list[dict]) -> dict[str, int]:
        """

        Build summary statistics from individual probe results.


        This method counts the number of theorems in each classification

        category to provide file-level statistics.


        Args:

            results: List of per-theorem result summaries


        Returns:

            Summary dict with total, closed, promising, failed, timed_out counts


        Requirements: 4.4, 5.3
        """

        summary = {

            "total": len(results),

            "closed": 0,

            "promising": 0,

            "failed": 0,

            "timed_out": 0,

        }

        for result in results:

            classification = result.get("classification", "")

            if classification == "trivial":

                summary["closed"] += 1
            elif classification == "promising":

                summary["promising"] += 1
            elif classification == "failed":

                summary["failed"] += 1
            elif classification == "timed_out":

                summary["timed_out"] += 1

            # Note: "error" classification is not counted in summary categories


        return summary


    def _extract_summary(self, probe_result: ProbeResult, theorem_id: str) -> dict:
        """

        Extract summary information from individual probe result.


        This method converts a full ProbeResult into a compact per-theorem

        summary suitable for inclusion in the probe_file results array.


        Args:

            probe_result: Full probe result from ProbeCommandHandler

            theorem_id: Theorem identifier


        Returns:

            Dict with theorem_id, outcome, classification, elapsed_ms


        Requirements: 5.4
        """

        return {

            "theorem_id": theorem_id,

            "outcome": probe_result.probe_result.outcome,

            "classification": probe_result.probe_result.classification,

            "elapsed_ms": probe_result.timing.get("elapsed_ms", 0.0),

        }


    def _build_error_result(

        self,

        cmd: ProbeFileCommand,

        error_message: str,

        start_time: float,

    ) -> ProbeFileResult:
        """

        Build error result for scan_file failures.


        Args:

            cmd: Original probe_file command

            error_message: Error message

            start_time: Start time for timing calculation


        Returns:

            ProbeFileResult with error status


        Requirements: 10.4
        """

        elapsed_ms = round((time.time() - start_time) * 1000.0, 2)


        return ProbeFileResult(

            api_version="0.1.0",

            status="error",

            file=cmd.file_path,

            summary={"total": 0, "closed": 0, "promising": 0, "failed": 0, "timed_out": 0},

            results=[],

            metadata={

                "elapsed_ms": elapsed_ms,

                "error": error_message,

            },

        )



# Import LeanRunner, LeanServer, and WorkspaceProvider from verify_domain for type hints

from .verify_domain import LeanRunner, LeanServer, WorkspaceProvider  # noqa: E402

