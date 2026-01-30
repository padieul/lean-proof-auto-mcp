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
    ) -> ValidationResult:
        """
        Validate a proof attempt using Command.

        This method validates a proof by constructing a complete theorem with
        the proof attempt and checking it with LeanInteract.

        Args:
            theorem_statement: Theorem statement
            proof_attempt: Proof to validate
            timeout_s: Timeout in seconds

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
            # Construct complete theorem with proof attempt
            code = f"theorem validation_theorem : {theorem_statement} := by\n{proof_attempt}\n"

            # Use Command to validate
            command = Command(code=code)
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
