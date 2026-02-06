"""
ProofValidator implementation.

This module implements the ProofValidator port for validating proof attempts
using LeanInteract.

Requirements: 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8
"""

import logging
import time

from .ports import ProofState, ValidationResult

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


class ProofValidatorImpl:
    """
    Concrete implementation of ProofValidator using LeanInteract library.

    This adapter uses LeanInteract to validate proof attempts, providing
    structured feedback including error messages, locations, and tactical
    suggestions.

    Requirements: 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8
    """

    def __init__(self, server: object | None = None):
        """
        Initialize ProofValidator.

        Args:
            server: Optional LeanServer instance to use

        Requirements: 7.2
        """
        self.server = server

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

        if self.server is None:
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
                code = self._construct_validation_with_import(
                    file_path, theorem_id, theorem_statement, proof_attempt
                )
            else:
                # Fallback: standalone validation (may fail due to missing context)
                logger.warning(
                    "Validating proof without file context - may fail due to missing "
                    "type class instances, variables, or namespace context"
                )
                code = f"theorem validation_theorem : {theorem_statement} := by\n{proof_attempt}\n"

            # Use Command to validate (note: parameter is 'cmd' not 'code')
            command = Command(cmd=code)
            response = self.server.run(command, timeout=timeout_s)  # type: ignore[attr-defined]

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
                # Validation failed with errors
                first_error = errors[0]
                error_location = self._extract_location(first_error)

                return ValidationResult(
                    status="error",
                    error_message=first_error["message"],
                    error_location=error_location,
                    proof_state=None,
                    suggestions=self._generate_error_suggestions(first_error["message"]),
                    time_s=elapsed,
                )

            # Check for incomplete proof (sorries)
            if hasattr(response, "sorries") and response.sorries:
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
            logger.error(f"Failed to validate proof: {e}")
            return ValidationResult(
                status="error",
                error_message=str(e),
                error_location=None,
                proof_state=None,
                suggestions=["Check proof syntax", "Verify theorem statement"],
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

        This method uses the ImportBasedHarnessConstructor to create a proper
        test harness that preserves ALL context from the original file.

        Args:
            file_path: Path to original file (e.g., "Fixtures/Algebra/Group.lean")
            theorem_id: Theorem identifier
            theorem_statement: Theorem type (not used - we get it from the file)
            proof_attempt: Proof to validate

        Returns:
            Validation code as string

        Requirements: 7.2, 7.3
        """
        from ..core.harness_construction import (
            HarnessConfig,
            HarnessError,
            ImportBasedHarnessConstructor,
            LeanInteractTheoremTypeExtractor,
            StandardImportPathConverter,
        )
        from ..lean.querier import LeanInteractQuerierImpl

        # Get server manager from server
        if not hasattr(self.server, "server_manager"):
            # Fallback to old approach if server doesn't have server_manager
            logger.warning("Server missing server_manager, using fallback import approach")
            return self._construct_validation_with_import_fallback(
                file_path, theorem_id, theorem_statement, proof_attempt
            )

        server_manager = self.server.server_manager

        # Create harness constructor components
        querier = LeanInteractQuerierImpl(server_manager)
        type_extractor = LeanInteractTheoremTypeExtractor(querier)
        path_converter = StandardImportPathConverter()

        harness_constructor = ImportBasedHarnessConstructor(
            type_extractor=type_extractor, path_converter=path_converter
        )

        # Build harness config
        config = HarnessConfig(
            theorem_id=theorem_id,
            file_path=file_path,
            proof_attempt=proof_attempt,
            additional_imports=[],
        )

        # Construct harness
        result = harness_constructor.construct(config)

        if isinstance(result, HarnessError):
            # Fall back to simple approach if construction fails
            logger.warning(f"Harness construction failed: {result.message}, using fallback")
            return self._construct_validation_with_import_fallback(
                file_path, theorem_id, theorem_statement, proof_attempt
            )

        return result.code

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
        """
        # Convert file path to import path
        import_path = file_path.replace("/", ".").replace("\\", ".").replace(".lean", "")

        # Build validation harness
        lines = []
        lines.append(f"import {import_path}")
        lines.append("")
        lines.append(f"-- Validate proof for {theorem_id}")
        lines.append(f"example : {theorem_statement} := by")

        # Indent proof attempt
        for line in proof_attempt.splitlines():
            lines.append(f"  {line}")

        return "\n".join(lines)
