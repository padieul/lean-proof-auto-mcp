"""
LeanInteractProofValidator implementation.

This module implements the ProofValidator port for validating proof attempts
using LeanInteract. The LeanInteractProofValidator class is a concrete adapter
that provides LeanInteract-based implementation of the ProofValidator protocol.

Requirements: 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8
"""

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

from .ports import ProofState, ServerManager, ValidationResult

if TYPE_CHECKING:
    from ..core.harness_construction import HarnessConstructor
    from ..core.verify_domain import LeanRunResult
    from .ports import Querier


logger = logging.getLogger(__name__)


# Try to import LeanInteract, but allow module to load even if not installed

try:
    from lean_interact import LeanServer
    from lean_interact.config import LeanREPLConfig
    from lean_interact.interface import Command, LeanError

    LEAN_INTERACT_AVAILABLE = True

except ImportError:
    LeanServer = None  # type: ignore[assignment, misc]

    LeanREPLConfig = None  # type: ignore[assignment, misc]

    Command = None  # type: ignore[assignment, misc]

    LeanError = None  # type: ignore[assignment, misc]

    LEAN_INTERACT_AVAILABLE = False


def _is_server_dead_error(exc: Exception) -> bool:
    """Check if an exception indicates the REPL process has died.

    LeanInteract signals server death through:
    - ChildProcessError: "The Lean server is not running" (_proc is None)
    - ConnectionAbortedError: "The Lean server closed unexpectedly" (broken pipe)

    These are distinct from verification errors (wrong proof, type mismatch)
    which come back as normal responses, not exceptions.
    """
    if isinstance(exc, (ChildProcessError, ConnectionAbortedError)):
        return True
    msg = str(exc).lower()
    return "server is not running" in msg or "server closed unexpectedly" in msg


class LeanInteractProofValidator:
    """
    LeanInteract-based adapter implementing the ProofValidator protocol.

    This adapter uses LeanInteract to validate proof attempts, providing
    structured feedback including error messages, locations, and tactical
    suggestions. It follows hexagonal architecture principles where the
    adapter depends inward on the ProofValidator protocol.

    Requirements: 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8
    """

    def __init__(
        self,
        server_manager: "ServerManager",
        harness_constructor: "HarnessConstructor | None" = None,
        querier: "Querier | None" = None,
    ):
        """
        Initialize ProofValidator with ServerManager via dependency injection.

        Args:
            server_manager: ServerManager instance for obtaining server instances
            harness_constructor: Optional HarnessConstructor for import-based validation
            querier: Optional Querier for extracting declarations and reading files

        Requirements: 8.3
        """
        self._server_manager = server_manager
        self._harness_constructor = harness_constructor
        self._querier = querier

    def verify_file(
        self,
        workspace_path: Path,
        file_path: str,
        theorem_id: str | None,
        budget_s: float,
    ) -> "LeanRunResult":
        """
        Run Lean verification on file or theorem.

        This method performs file-level or theorem-level verification using LeanInteract.
        Includes automatic server recovery: if the REPL process has died (e.g. killed
        by a previous timeout or OOM), the server is restarted and the command retried
        once. This prevents a single crashed probe from cascading failures across an
        entire batch.

        Args:
            workspace_path: Path to workspace root
            file_path: Path to Lean file (relative to workspace)
            theorem_id: Optional theorem identifier for theorem-level verification
            budget_s: Time budget in seconds

        Returns:
            LeanRunResult with status, diagnostics, logs, timing

        Raises:
            TimeoutError: If verification exceeds budget
            ValueError: If theorem_id is invalid or not found
            RuntimeError: If Lean process fails unexpectedly

        Requirements: 6.3, 6.4, 6.5, 7.1, 7.4
        """
        return self._verify_file_with_retry(
            file_path=file_path,
            theorem_id=theorem_id,
            budget_s=budget_s,
            retries_left=1,
        )

    def _verify_file_with_retry(
        self,
        file_path: str,
        theorem_id: str | None,
        budget_s: float,
        retries_left: int,
    ) -> "LeanRunResult":
        """
        Internal verify_file implementation with dead-server retry.

        When LeanInteract raises ChildProcessError ("The Lean server is not
        running"), the REPL was killed by a previous timeout or crash. We
        restart the server via ServerManager and retry the command once.

        This keeps recovery logic in the adapter layer (hexagonal architecture)
        so the core domain never sees infrastructure failures it can't handle.

        Args:
            file_path: Path to Lean file
            theorem_id: Optional theorem identifier
            budget_s: Time budget in seconds
            retries_left: Number of restart-and-retry attempts remaining

        Returns:
            LeanRunResult

        Raises:
            TimeoutError: If verification exceeds budget
            RuntimeError: If Lean process fails after all retries
        """
        from ..core.verify_domain import LeanRunResult

        # Get or create server for this file
        server = self._server_manager.get_server(file_path)

        # Use FileCommand to verify
        try:
            from lean_interact.interface import FileCommand

            command = FileCommand(path=file_path)
            response = server.run(command, timeout=budget_s)

            # Parse response into LeanRunResult
            diagnostics = self._parse_diagnostics_for_verify(response)
            status = self._determine_status(diagnostics)

            # exit_code reflects the Lean *process* outcome, not the
            # verification result. LeanInteract ran successfully (exit_code=0)
            # even when the file contains errors — those are reported via
            # diagnostics and status ("fail"). Setting exit_code=1 for "fail"
            # caused the handler to escalate "fail" → "error", hiding valid
            # diagnostic-only failures.
            return LeanRunResult(
                status=status,
                diagnostics=diagnostics,
                scope_used="file" if theorem_id is None else "theorem",
                full_logs="",  # LeanInteract doesn't provide full logs
                timing={"verification_s": 0.0},  # TODO: Add timing
                exit_code=0,
            )

        except TimeoutError as e:
            raise TimeoutError(f"Verification timed out after {budget_s}s") from e
        except ChildProcessError as err:
            # LeanInteract raises ChildProcessError when _proc is None
            # (killed by previous timeout). Restart and retry once.
            if retries_left > 0:
                logger.warning(
                    f"Server dead for {file_path}, restarting and retrying "
                    f"({retries_left} retries left)"
                )
                self._server_manager.restart_server(file_path)
                return self._verify_file_with_retry(
                    file_path=file_path,
                    theorem_id=theorem_id,
                    budget_s=budget_s,
                    retries_left=retries_left - 1,
                )
            logger.error(f"Server dead for {file_path}, no retries left")
            raise RuntimeError(
                "Lean verification failed: server not running after restart"
            ) from err
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            # Check if the error message indicates a dead server
            # (ConnectionAbortedError from broken pipe also means server died)
            if retries_left > 0 and _is_server_dead_error(e):
                logger.warning(
                    f"Server appears dead for {file_path}, restarting and retrying "
                    f"({retries_left} retries left)"
                )
                self._server_manager.restart_server(file_path)
                return self._verify_file_with_retry(
                    file_path=file_path,
                    theorem_id=theorem_id,
                    budget_s=budget_s,
                    retries_left=retries_left - 1,
                )
            raise RuntimeError(f"Lean verification failed: {e}") from e

    def validate_proof(
        self,
        theorem_statement: str,
        proof_attempt: str,
        timeout_s: float = 10.0,
        file_path: str | None = None,
        theorem_id: str | None = None,
    ) -> ValidationResult:
        """

        Validate a proof attempt using Command.


        This method validates a proof by constructing a complete theorem with

        the proof attempt and checking it with LeanInteract.


        IMPORTANT: If file_path and theorem_id are provided, this method will

        use an import-based approach to preserve all context (type class instances,

        variables, namespaces, notation). Otherwise, it falls back to standalone

        validation which may fail due to missing context.


        Args:

            theorem_statement: Theorem statement (type only, not full signature)

            proof_attempt: Proof to validate

            timeout_s: Timeout in seconds

            file_path: Optional path to original file (for context preservation)

            theorem_id: Optional theorem identifier (for context preservation)


        Returns:

            ValidationResult with status and feedback


        Requirements: 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8
        """

        if not LEAN_INTERACT_AVAILABLE or Command is None:
            return ValidationResult(
                status="error",
                error_message="LeanInteract library not installed",
                error_location=None,
                proof_state=None,
                suggestions=["Install LeanInteract: pip install lean-interact"],
                time_s=0.0,
            )

        # Get server instance from ServerManager
        server = self._server_manager.get_server(file_path or "default")

        if server is None:
            return ValidationResult(
                status="error",
                error_message="No server instance available",
                error_location=None,
                proof_state=None,
                suggestions=["Create a server instance before validating"],
                time_s=0.0,
            )

        start_time = time.time()

        try:
            # Construct validation code

            if file_path and theorem_id:
                # Import-based approach: preserves all context
                # When using the harness constructor, non-target theorems
                # are intentionally sorry'd. We must not treat those
                # sorries as "proof incomplete" for the target theorem.
                uses_harness_constructor = self._harness_constructor is not None

                code = self._construct_validation_with_import(
                    file_path, theorem_id, theorem_statement, proof_attempt
                )

            else:
                # Fallback: standalone validation (may fail due to missing context)
                uses_harness_constructor = False

                logger.warning(
                    "Validating proof without file context - may fail due to missing "
                    "type class instances, variables, or namespace context"
                )

                code = f"theorem validation_theorem : {theorem_statement} := by\n{proof_attempt}\n"

            # Use Command to validate (note: parameter is 'cmd' not 'code')

            command = Command(cmd=code)

            response = server.run(command, timeout=timeout_s)

            elapsed = time.time() - start_time

            # Check for timeout

            if isinstance(response, LeanError):
                error_msg = str(response)

                if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                    return ValidationResult(
                        status="timeout",
                        error_message="Validation timed out",
                        error_location=None,
                        proof_state=None,
                        suggestions=["Try simplifying the proof", "Increase timeout"],
                        time_s=elapsed,
                    )

                else:
                    # Other error

                    return ValidationResult(
                        status="error",
                        error_message=error_msg,
                        error_location=None,
                        proof_state=None,
                        suggestions=self._generate_error_suggestions(error_msg),
                        time_s=elapsed,
                    )

            # Parse diagnostics from response

            diagnostics = self._parse_diagnostics(response)

            # Check for errors

            errors = [d for d in diagnostics if d["severity"] == "error"]

            if errors:
                # Lean processed the proof but rejected it (type mismatch,
                # tactic failure, etc.) — this is NOT a tool error.

                first_error = errors[0]

                error_location = self._extract_location(first_error)

                return ValidationResult(
                    status="rejected",
                    error_message=first_error["message"],
                    error_location=error_location,
                    proof_state=None,
                    suggestions=self._generate_error_suggestions(first_error["message"]),
                    time_s=elapsed,
                )

            # Check for incomplete proof (sorries)
            # When using the harness constructor, non-target theorems are
            # intentionally replaced with sorry. Only flag "incomplete" if
            # we're NOT using the harness path (standalone validation).
            if not uses_harness_constructor and hasattr(response, "sorries") and response.sorries:
                # Proof is incomplete

                proof_state = self._extract_proof_state(response)

                return ValidationResult(
                    status="incomplete",
                    error_message="Proof is incomplete (contains sorry)",
                    error_location=None,
                    proof_state=proof_state,
                    suggestions=["Complete the proof", "Remove sorry placeholders"],
                    time_s=elapsed,
                )

            # Check for remaining goals

            if hasattr(response, "goals") and response.goals:
                # Proof is incomplete (goals remaining)

                proof_state = self._extract_proof_state(response)

                return ValidationResult(
                    status="incomplete",
                    error_message="Proof is incomplete (goals remaining)",
                    error_location=None,
                    proof_state=proof_state,
                    suggestions=["Complete all goals", "Add more tactics"],
                    time_s=elapsed,
                )

            # Validation succeeded

            return ValidationResult(
                status="success",
                error_message=None,
                error_location=None,
                proof_state=None,
                suggestions=["Proof verified successfully"],
                time_s=elapsed,
            )

        except TimeoutError:
            elapsed = time.time() - start_time

            return ValidationResult(
                status="timeout",
                error_message="Validation timed out",
                error_location=None,
                proof_state=None,
                suggestions=["Try simplifying the proof", "Increase timeout"],
                time_s=elapsed,
            )

        except Exception as e:
            elapsed = time.time() - start_time

            # If the server died, restart it so the next call gets a fresh one.
            # We don't retry here (validate_proof is a single-shot call), but
            # restarting ensures the next tool invocation doesn't hit the same
            # dead server.
            if _is_server_dead_error(e):
                logger.warning(f"Server died during validate_proof, restarting: {e}")
                self._server_manager.restart_server(file_path or "default")

            logger.error(f"Failed to validate proof: {e}")

            return ValidationResult(
                status="error",
                error_message=str(e),
                error_location=None,
                proof_state=None,
                suggestions=["Check proof syntax", "Verify theorem statement"],
                time_s=elapsed,
            )

    def validate_harness_code(
        self,
        harness_code: str,
        timeout_s: float = 10.0,
        file_path: str | None = None,
    ) -> ValidationResult:
        """Validate prebuilt harness code exactly as provided."""
        if not LEAN_INTERACT_AVAILABLE or Command is None:
            return ValidationResult(
                status="error",
                error_message="LeanInteract library not installed",
                error_location=None,
                proof_state=None,
                suggestions=["Install LeanInteract: pip install lean-interact"],
                time_s=0.0,
            )

        server_key = file_path or "default"
        server = self._server_manager.get_server(server_key)
        if server is None:
            return ValidationResult(
                status="error",
                error_message="No server instance available",
                error_location=None,
                proof_state=None,
                suggestions=["Create a server instance before validating"],
                time_s=0.0,
            )

        start_time = time.time()
        try:
            command = Command(cmd=harness_code)
            response = server.run(command, timeout=timeout_s)
            elapsed = time.time() - start_time

            if isinstance(response, LeanError):
                error_msg = str(response)
                if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                    return ValidationResult(
                        status="timeout",
                        error_message="Validation timed out",
                        error_location=None,
                        proof_state=None,
                        suggestions=["Try simplifying the proof", "Increase timeout"],
                        time_s=elapsed,
                    )

                return ValidationResult(
                    status="error",
                    error_message=error_msg,
                    error_location=None,
                    proof_state=None,
                    suggestions=self._generate_error_suggestions(error_msg),
                    time_s=elapsed,
                )

            diagnostics = self._parse_diagnostics(response)
            errors = [d for d in diagnostics if d["severity"] == "error"]
            if errors:
                first_error = errors[0]
                error_location = self._extract_location(first_error)
                return ValidationResult(
                    status="rejected",
                    error_message=first_error["message"],
                    error_location=error_location,
                    proof_state=None,
                    suggestions=self._generate_error_suggestions(first_error["message"]),
                    time_s=elapsed,
                )

            # Do not treat response.sorries as incomplete here: prebuilt harness
            # intentionally contains non-target sorry placeholders.
            if hasattr(response, "goals") and response.goals:
                proof_state = self._extract_proof_state(response)
                return ValidationResult(
                    status="incomplete",
                    error_message="Proof is incomplete (goals remaining)",
                    error_location=None,
                    proof_state=proof_state,
                    suggestions=["Complete all goals", "Add more tactics"],
                    time_s=elapsed,
                )

            return ValidationResult(
                status="success",
                error_message=None,
                error_location=None,
                proof_state=None,
                suggestions=["Proof verified successfully"],
                time_s=elapsed,
            )

        except TimeoutError:
            elapsed = time.time() - start_time
            return ValidationResult(
                status="timeout",
                error_message="Validation timed out",
                error_location=None,
                proof_state=None,
                suggestions=["Try simplifying the proof", "Increase timeout"],
                time_s=elapsed,
            )
        except Exception as e:
            elapsed = time.time() - start_time
            if _is_server_dead_error(e):
                logger.warning(f"Server died during validate_harness_code, restarting: {e}")
                self._server_manager.restart_server(server_key)

            logger.error(f"Failed to validate harness code: {e}")
            return ValidationResult(
                status="error",
                error_message=str(e),
                error_location=None,
                proof_state=None,
                suggestions=["Check harness syntax", "Verify theorem context"],
                time_s=elapsed,
            )

    def _parse_diagnostics(self, response: object) -> list[dict]:
        """

        Parse diagnostics from LeanInteract response.


        Args:

            response: LeanInteract response object


        Returns:

            List of diagnostic dicts


        Requirements: 7.3, 7.4
        """

        diagnostics = []

        # Parse messages array for errors/warnings

        if hasattr(response, "messages"):
            for msg in response.messages:
                severity = self._normalize_severity(msg.severity)

                diagnostic = {
                    "severity": severity,
                    "message": msg.data,
                    "location": self._extract_location_from_message(msg),
                }

                diagnostics.append(diagnostic)

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

    def _extract_location(self, diagnostic: dict) -> tuple[int, int] | None:
        """

        Extract location from diagnostic.


        Args:

            diagnostic: Diagnostic dict


        Returns:

            Tuple of (line, column) or None


        Requirements: 7.4
        """

        location = diagnostic.get("location")

        if location:
            line = location.get("line", 0)

            col = location.get("col", 0)

            return (line, col)

        return None

    def _extract_location_from_message(self, msg: object) -> dict | None:
        """

        Extract location from message object.


        Args:

            msg: Message object from LeanInteract


        Returns:

            Location dict or None
        """

        start_pos = getattr(msg, "start_pos", None)

        if start_pos:
            return {
                "line": getattr(start_pos, "line", 0),
                "col": getattr(start_pos, "column", 0),
            }

        return None

    def _extract_proof_state(self, response: object) -> ProofState | None:
        """

        Extract proof state from response.


        Args:

            response: LeanInteract response object


        Returns:

            ProofState or None


        Requirements: 7.6
        """

        # Extract goal

        goal = ""

        if hasattr(response, "goals") and response.goals:
            first_goal = response.goals[0]

            if hasattr(first_goal, "goal"):
                goal = first_goal.goal

            elif hasattr(first_goal, "conclusion"):
                goal = first_goal.conclusion

        # Extract hypotheses

        hypotheses = []

        if hasattr(response, "goals") and response.goals:
            first_goal = response.goals[0]

            if hasattr(first_goal, "hypotheses"):
                for hyp in first_goal.hypotheses:
                    if hasattr(hyp, "name") and hasattr(hyp, "type"):
                        hypotheses.append(f"{hyp.name} : {hyp.type}")

        # Extract number of goals remaining

        goals_remaining = 0

        if hasattr(response, "goals"):
            goals_remaining = len(response.goals)

        if goal or hypotheses or goals_remaining > 0:
            return ProofState(
                goal=goal,
                hypotheses=hypotheses,
                type_context="",
                goals_remaining=goals_remaining,
            )

        return None

    def _generate_error_suggestions(self, error_message: str) -> list[str]:
        """

        Generate tactical suggestions based on error message.


        Args:

            error_message: Error message from Lean


        Returns:

            List of suggestions


        Requirements: 7.7
        """

        suggestions = []

        error_lower = error_message.lower()

        # Type mismatch

        if "type mismatch" in error_lower or "expected" in error_lower:
            suggestions.append("Check types match expected values")

            suggestions.append("Try using type annotations")

        # Unknown identifier

        if "unknown identifier" in error_lower or "not found" in error_lower:
            suggestions.append("Check spelling of identifiers")

            suggestions.append("Ensure all imports are included")

        # Tactic failed

        if "tactic" in error_lower and "failed" in error_lower:
            suggestions.append("Try a different tactic")

            suggestions.append("Break down the proof into smaller steps")

        # Unsolved goals

        if "unsolved goals" in error_lower or "goals remaining" in error_lower:
            suggestions.append("Complete all proof goals")

            suggestions.append("Use 'sorry' to see remaining goals")

        # Default suggestions

        if not suggestions:
            suggestions.append("Review proof syntax")

            suggestions.append("Check theorem statement")

        return suggestions

    def _construct_validation_with_import(
        self,
        file_path: str,
        theorem_id: str,
        theorem_statement: str,
        proof_attempt: str,
    ) -> str:
        """

        Construct validation code using import-based harness construction.


        This method uses the injected HarnessConstructor (if available) or falls
        back to a simple import-based approach. Dependencies are NOT created
        internally — they must be injected via the constructor or passed as
        pre-constructed harness code through proof_attempt.


        Args:

            file_path: Path to original file (e.g., "Fixtures/Algebra/Group.lean")

            theorem_id: Theorem identifier

            theorem_statement: Theorem type expression

            proof_attempt: Proof to validate (or pre-constructed harness code)


        Returns:

            Validation code as string


        Requirements: 7.2, 7.3
        """

        if self._harness_constructor is not None:
            from ..core.harness_construction import (
                HarnessConfig,
                HarnessError,
            )

            # Populate file_content and declarations if querier is available
            file_content = ""
            declarations: list = []
            if self._querier is not None:
                declarations = self._querier.extract_declarations(file_path)
                file_content = self._querier.read_source_file(file_path)

            # Build harness config

            config = HarnessConfig(
                theorem_id=theorem_id,
                file_path=file_path,
                proof_attempt=proof_attempt,
                file_content=file_content,
                declarations=declarations,
                additional_imports=[],
            )

            # Construct harness using injected constructor

            result = self._harness_constructor.construct(config)

            if isinstance(result, HarnessError):
                # Fall back to simple approach if construction fails

                logger.warning(f"Harness construction failed: {result.message}, using fallback")

                return self._construct_validation_with_import_fallback(
                    file_path, theorem_id, theorem_statement, proof_attempt
                )

            return result.code

        else:
            # No harness constructor injected — use simple fallback

            logger.warning("No HarnessConstructor injected, using simple import fallback")

            return self._construct_validation_with_import_fallback(
                file_path, theorem_id, theorem_statement, proof_attempt
            )

    def _construct_validation_with_import_fallback(
        self,
        file_path: str,
        theorem_id: str,
        theorem_statement: str,
        proof_attempt: str,
    ) -> str:
        """

        Fallback: Construct validation code using simple import approach.


        This is the old approach that may fail due to missing context.
        Uses classify_proof_attempt to handle both tactic-mode and term-mode
        proofs correctly.
        """

        from ..core.harness_construction import classify_proof_attempt

        # Convert file path to import path

        import_path = file_path.replace("/", ".").replace("\\", ".").replace(".lean", "")

        mode, cleaned_proof = classify_proof_attempt(proof_attempt)

        # Build validation harness

        lines = []

        lines.append(f"import {import_path}")

        lines.append("")

        lines.append(f"-- Validate proof for {theorem_id}")

        if mode == "tactic":
            lines.append(f"example : {theorem_statement} := by")
            for line in cleaned_proof.splitlines():
                lines.append(f"  {line}")
        else:
            lines.append(f"example : {theorem_statement} := {cleaned_proof}")

        return "\n".join(lines)

    def _parse_diagnostics_for_verify(self, response: object) -> list[dict]:
        """
        Parse diagnostics from LeanInteract response for verify_file().

        This is a separate method from _parse_diagnostics() to handle
        the specific format needed for LeanRunResult.

        Args:
            response: LeanInteract response object

        Returns:
            List of diagnostic dicts

        Requirements: 7.3, 7.4
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

                diagnostics.append({"severity": severity, "message": message, "location": location})
        return diagnostics

    def _determine_status(self, diagnostics: list[dict]) -> str:
        """
        Determine verification status from diagnostics.

        Args:
            diagnostics: List of diagnostic dicts

        Returns:
            Status string ("success", "fail", or "timeout")

        Requirements: 6.3, 6.4
        """
        # Check for errors
        has_errors = any(d["severity"] == "error" for d in diagnostics)

        if has_errors:
            return "fail"
        else:
            return "success"
