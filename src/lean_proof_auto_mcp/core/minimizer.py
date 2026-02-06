"""
Minimizer service for hint set minimization using delta-debugging.

This module implements delta-debugging minimization to reduce hint sets
to their minimal stable configuration while preserving the closing property.

Requirements: 5.1, 5.2, 5.3, 5.5, 5.6
"""

from collections.abc import Callable

from lean_proof_auto_mcp.core.search_automated_proof_domain import (
    ExecutionOutcome,
    HintSet,
)


class Minimizer:
    """
    Delta-debugging minimizer for hint sets.

    The minimizer iteratively removes hints from a closing hint set,
    verifying that the reduced set still closes the goal. Hints that
    cause failure when removed are restored. The process continues
    until a fixed point is reached where no more hints can be removed.

    Requirements: 5.1, 5.2, 5.3, 5.5, 5.6
    """

    def minimize(
        self, hint_set: HintSet, probe_fn: Callable[[HintSet], ExecutionOutcome]
    ) -> HintSet:
        """
        Minimize hint set using delta-debugging algorithm.

        The algorithm:
        1. Start with the full hint set
        2. Try removing each hint one at a time
        3. If removal still closes the goal, keep the reduced set
        4. If removal causes failure, restore the hint
        5. Repeat until no more hints can be removed (fixed point)

        Args:
            hint_set: Initial closing hint set to minimize
            probe_fn: Callback to test if a hint set closes the goal
                     Returns ExecutionOutcome with status "success" if closes

        Returns:
            Minimized hint set that still closes the goal

        Requirements: 5.1, 5.2, 5.3, 5.5, 5.6
        """
        if hint_set.is_empty():
            return hint_set

        current = hint_set
        changed = True

        # Iterate until fixed point (no more removals possible)
        while changed:
            changed = False

            # Try removing each hint
            for hint in current.hints:
                candidate = current.remove(hint)

                # Test if reduced set still closes
                result = probe_fn(candidate)

                if result.status == "success":
                    # Removal successful, keep reduced set
                    current = candidate
                    changed = True
                    # Break to restart iteration with new current set
                    break
                # else: Removal caused failure, restore hint (implicit)

        return current
