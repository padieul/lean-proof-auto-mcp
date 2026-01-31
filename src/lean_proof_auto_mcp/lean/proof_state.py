"""
ProofStateInspector implementation.

This module implements the ProofStateInspector port for inspecting proof states
and applying tactics using LeanInteract.

Requirements: 16.1, 16.2, 16.3, 16.4
"""

import logging

from .ports import Declaration, ProofState, TacticResult

logger = logging.getLogger(__name__)

# Try to import LeanInteract, but allow module to load even if not installed
try:
    from lean_interact import LeanServer
    from lean_interact.config import LeanREPLConfig
    from lean_interact.interface import Command, LeanError, ProofStep

    LEAN_INTERACT_AVAILABLE = True
except ImportError:
    LeanServer = None  # type: ignore[assignment, misc]
    LeanREPLConfig = None  # type: ignore[assignment, misc]
    Command = None  # type: ignore[assignment, misc]
    LeanError = None  # type: ignore[assignment, misc]
    ProofStep = None  # type: ignore[assignment, misc]
    LEAN_INTERACT_AVAILABLE = False


class ProofStateInspectorImpl:
    """
    Concrete implementation of ProofStateInspector using LeanInteract library.

    This adapter uses LeanInteract to inspect proof states and apply tactics,
    enabling interactive proof development and analysis.

    Requirements: 16.1, 16.2, 16.3, 16.4
    """

    def __init__(self, server: object | None = None):
        """
        Initialize ProofStateInspector.

        Args:
            server: Optional LeanServer instance to use

        Requirements: 16.1
        """
        self.server = server

    def get_initial_proof_state(self, theorem: Declaration) -> ProofState:
        """
        Get initial proof state using Command with sorry.

        This method creates a proof harness with sorry and extracts the initial
        proof state, showing what needs to be proven.

        Args:
            theorem: Declaration to get proof state for

        Returns:
            Initial proof state

        Raises:
            RuntimeError: If LeanInteract fails or not available

        Requirements: 16.1, 16.2, 16.3, 16.4
        """
        if not LEAN_INTERACT_AVAILABLE or Command is None:
            raise RuntimeError(
                "LeanInteract library not installed. Install with: pip install lean-interact"
            )

        if self.server is None:
            raise RuntimeError("No server instance available")

        try:
            # Construct a proof harness with sorry
            harness = f"theorem {theorem.name} : {theorem.type} := by\n  sorry\n"

            # Use Command to check the harness (note: parameter is 'cmd' not 'code')
            command = Command(cmd=harness)
            response = self.server.run(command, timeout=10.0)  # type: ignore[attr-defined]

            # Check for errors
            if isinstance(response, LeanError):
                raise RuntimeError(f"LeanInteract error: {response}")

            # Extract proof state from response
            # The sorry should produce a proof state showing the goal
            proof_state = self._parse_proof_state(response)

            logger.info(f"Extracted initial proof state for {theorem.name}")
            return proof_state

        except Exception as e:
            logger.error(f"Failed to get initial proof state for {theorem.name}: {e}")
            raise RuntimeError(f"Failed to get initial proof state: {e}") from e

    def apply_tactic(self, proof_state_id: int, tactic: str) -> TacticResult:
        """
        Apply a tactic using ProofStep.

        This method applies a tactic to a proof state and returns the result,
        including the new proof state if successful.

        Args:
            proof_state_id: ID of proof state to apply tactic to
            tactic: Tactic to apply

        Returns:
            TacticResult with new proof state or error

        Raises:
            RuntimeError: If LeanInteract fails or not available

        Requirements: 16.2
        """
        if not LEAN_INTERACT_AVAILABLE or ProofStep is None:
            raise RuntimeError(
                "LeanInteract library not installed. Install with: pip install lean-interact"
            )

        if self.server is None:
            raise RuntimeError("No server instance available")

        try:
            # Use ProofStep to apply tactic
            proof_step = ProofStep(tactic=tactic, proof_state=proof_state_id)
            response = self.server.run(proof_step, timeout=10.0)  # type: ignore[attr-defined]

            # Check for errors
            if isinstance(response, LeanError):
                return TacticResult(
                    success=False,
                    new_proof_state=None,
                    error_message=str(response),
                )

            # Extract new proof state from response
            new_proof_state = self._parse_proof_state(response)

            logger.info(f"Applied tactic '{tactic}' to proof state {proof_state_id}")
            return TacticResult(
                success=True,
                new_proof_state=new_proof_state,
                error_message=None,
            )

        except Exception as e:
            logger.error(f"Failed to apply tactic '{tactic}': {e}")
            return TacticResult(
                success=False,
                new_proof_state=None,
                error_message=str(e),
            )

    def _parse_proof_state(self, response: object) -> ProofState:
        """
        Parse proof state from LeanInteract response.

        This method extracts the goal, hypotheses, type context, and number of
        goals remaining from the response.

        Args:
            response: LeanInteract response object

        Returns:
            ProofState with extracted information

        Requirements: 16.1, 16.2, 16.3, 16.4
        """
        # Extract goal
        goal = ""
        if hasattr(response, "goals") and response.goals:
            # Get first goal
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
                    elif hasattr(hyp, "body"):
                        hypotheses.append(hyp.body)

        # Extract type context (for now, empty string)
        type_context = ""

        # Extract number of goals remaining
        goals_remaining = 0
        if hasattr(response, "goals"):
            goals_remaining = len(response.goals)

        return ProofState(
            goal=goal,
            hypotheses=hypotheses,
            type_context=type_context,
            goals_remaining=goals_remaining,
        )
