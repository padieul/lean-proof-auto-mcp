"""
Search strategy implementations for hint set discovery.

This module provides the SearchStrategy protocol and concrete implementations
(GreedySearch and BeamSearch) for exploring hint combinations to find sets
that enable automation to close goals.

Requirements: 4.1, 4.2, 4.5, 4.6, 4.7
"""

import time
from typing import Callable, Protocol

from .search_annotations_domain import (
    Candidate,
    ExecutionOutcome,
    HintSet,
    SearchConfig,
    SearchResult,
)


class SearchStrategy(Protocol):
    """
    Abstract search strategy for hint set discovery.
    
    A search strategy explores combinations of hints to find sets that
    enable automation to close goals. Different strategies use different
    exploration algorithms (greedy, beam search, etc.).
    
    Requirements: 4.1, 4.2, 4.5, 4.6, 4.7
    """
    
    def search(
        self,
        candidates: list[Candidate],
        probe_fn: Callable[[HintSet], ExecutionOutcome],
        config: SearchConfig,
        budget_s: float
    ) -> SearchResult:
        """
        Search for closing hint set.
        
        Args:
            candidates: List of candidate hints to explore
            probe_fn: Function that tests a hint set and returns outcome
            config: Search configuration
            budget_s: Time budget in seconds
            
        Returns:
            SearchResult with outcome, best hint set, and statistics
            
        Requirements: 4.3, 4.4, 4.5, 4.6, 4.7, 4.8
        """
        ...


class GreedySearch:
    """
    Greedy search strategy.
    
    Starts with an empty hint set and incrementally adds the best candidate
    at each step. Stops when a closing set is found (if stop_on_first_close)
    or when max_steps/budget is reached.
    
    Requirements: 4.1, 4.5, 4.6, 4.7
    """
    
    def search(
        self,
        candidates: list[Candidate],
        probe_fn: Callable[[HintSet], ExecutionOutcome],
        config: SearchConfig,
        budget_s: float
    ) -> SearchResult:
        """
        Execute greedy search.
        
        Algorithm:
        1. Start with empty hint set
        2. For each step:
           a. Try adding each remaining candidate
           b. Select the candidate that produces the best outcome
           c. Add it to the current hint set
           d. If outcome is "success" and stop_on_first_close, terminate
        3. Continue until max_steps, budget exhaustion, or success
        
        Args:
            candidates: List of candidate hints to explore
            probe_fn: Function that tests a hint set and returns outcome
            config: Search configuration
            budget_s: Time budget in seconds
            
        Returns:
            SearchResult with outcome, best hint set, and statistics
            
        Requirements: 4.1, 4.5, 4.6, 4.7, 4.8
        """
        start_time = time.time()
        
        # Initialize search state
        current_hint_set = HintSet()
        best_hint_set = current_hint_set
        best_outcome: ExecutionOutcome | None = None
        attempts = 0
        explored_sets = 0
        remaining_candidates = list(candidates)
        
        # Search loop
        for step in range(config.max_steps):
            # Check budget
            elapsed = time.time() - start_time
            if elapsed >= budget_s:
                break
            
            # Check if we've reached max_hints
            if current_hint_set.size() >= config.max_hints:
                break
            
            # Check if we have remaining candidates
            if not remaining_candidates:
                break
            
            # Try adding each remaining candidate
            best_candidate: Candidate | None = None
            best_candidate_outcome: ExecutionOutcome | None = None
            best_candidate_score = -1.0
            
            for candidate in remaining_candidates:
                # Check budget before each probe
                elapsed = time.time() - start_time
                if elapsed >= budget_s:
                    break
                
                # Create hint set with this candidate added
                test_hint_set = current_hint_set.add(candidate.hint)
                
                # Probe this hint set
                outcome = probe_fn(test_hint_set)
                attempts += 1
                explored_sets += 1
                
                # Score this outcome
                score = self._score_outcome(outcome)
                
                # Track best candidate for this step
                if score > best_candidate_score:
                    best_candidate = candidate
                    best_candidate_outcome = outcome
                    best_candidate_score = score
                
                # If we found a closing set and should stop, do so
                if outcome.status == "success" and config.stop_on_first_close:
                    current_hint_set = test_hint_set
                    best_hint_set = test_hint_set
                    best_outcome = outcome
                    
                    return SearchResult(
                        outcome="closed",
                        best_hint_set=best_hint_set,
                        attempts=attempts,
                        explored_sets=explored_sets,
                        evidence=best_outcome
                    )
            
            # If we found a candidate to add, add it
            if best_candidate is not None:
                current_hint_set = current_hint_set.add(best_candidate.hint)
                remaining_candidates.remove(best_candidate)
                
                # Update best if this is better
                if best_candidate_outcome is not None:
                    if best_outcome is None or best_candidate_score > self._score_outcome(best_outcome):
                        best_hint_set = current_hint_set
                        best_outcome = best_candidate_outcome
                        
                        # Check if we found a closing set
                        if best_outcome.status == "success":
                            if config.stop_on_first_close:
                                return SearchResult(
                                    outcome="closed",
                                    best_hint_set=best_hint_set,
                                    attempts=attempts,
                                    explored_sets=explored_sets,
                                    evidence=best_outcome
                                )
            else:
                # No candidate improved the outcome, stop
                break
        
        # Determine final outcome
        if best_outcome is not None and best_outcome.status == "success":
            final_outcome = "closed"
        elif best_outcome is not None:
            final_outcome = "partial"
        else:
            final_outcome = "failed"
        
        return SearchResult(
            outcome=final_outcome,
            best_hint_set=best_hint_set if not best_hint_set.is_empty() else None,
            attempts=attempts,
            explored_sets=explored_sets,
            evidence=best_outcome
        )
    
    def _score_outcome(self, outcome: ExecutionOutcome) -> float:
        """
        Score an execution outcome.
        
        Higher scores are better. Success > partial > failure.
        
        Args:
            outcome: Execution outcome to score
            
        Returns:
            Score value (higher is better)
            
        Requirements: 4.9
        """
        if outcome.status == "success":
            return 100.0
        elif outcome.status == "failure":
            # Check if output suggests progress (e.g., fewer unsolved goals)
            # For now, use a base score
            return 10.0
        elif outcome.status == "timeout":
            return 5.0
        elif outcome.status == "error":
            return 1.0
        else:
            return 0.0


class BeamSearch:
    """
    Beam search strategy.
    
    Maintains beam_width hint sets and expands them by adding candidates.
    Prunes to keep only the top beam_width sets at each step.
    
    Requirements: 4.2, 4.5, 4.6, 4.7
    """
    
    def search(
        self,
        candidates: list[Candidate],
        probe_fn: Callable[[HintSet], ExecutionOutcome],
        config: SearchConfig,
        budget_s: float
    ) -> SearchResult:
        """
        Execute beam search.
        
        Algorithm:
        1. Start with beam containing empty hint set
        2. For each step:
           a. For each hint set in beam:
              - Try adding each candidate
              - Score the resulting hint sets
           b. Keep top beam_width hint sets
           c. If any set closes and stop_on_first_close, terminate
        3. Continue until max_steps, budget exhaustion, or success
        
        Args:
            candidates: List of candidate hints to explore
            probe_fn: Function that tests a hint set and returns outcome
            config: Search configuration
            budget_s: Time budget in seconds
            
        Returns:
            SearchResult with outcome, best hint set, and statistics
            
        Requirements: 4.2, 4.5, 4.6, 4.7, 4.8
        """
        start_time = time.time()
        
        # Initialize beam with empty hint set
        beam: list[tuple[HintSet, float, ExecutionOutcome | None]] = [
            (HintSet(), 0.0, None)
        ]
        
        best_hint_set = HintSet()
        best_outcome: ExecutionOutcome | None = None
        best_score = -1.0
        attempts = 0
        explored_sets = 0
        
        # Track explored hint sets to avoid duplicates
        explored: set[frozenset[str]] = set()
        explored.add(frozenset())  # Empty set
        
        # Search loop
        for step in range(config.max_steps):
            # Check budget
            elapsed = time.time() - start_time
            if elapsed >= budget_s:
                break
            
            # Expand beam
            candidates_for_expansion: list[tuple[HintSet, float, ExecutionOutcome | None]] = []
            
            for hint_set, score, outcome in beam:
                # Check if this set is at max_hints
                if hint_set.size() >= config.max_hints:
                    # Keep it in candidates but don't expand
                    candidates_for_expansion.append((hint_set, score, outcome))
                    continue
                
                # Try adding each candidate
                for candidate in candidates:
                    # Check budget before each probe
                    elapsed = time.time() - start_time
                    if elapsed >= budget_s:
                        break
                    
                    # Skip if hint already in set
                    if candidate.hint in hint_set.hints:
                        continue
                    
                    # Create expanded hint set
                    expanded_set = hint_set.add(candidate.hint)
                    
                    # Check if we've explored this set before
                    set_signature = frozenset(h.name for h in expanded_set.hints)
                    if set_signature in explored:
                        continue
                    
                    explored.add(set_signature)
                    
                    # Probe this hint set
                    expanded_outcome = probe_fn(expanded_set)
                    attempts += 1
                    explored_sets += 1
                    
                    # Score this outcome
                    expanded_score = self._score_outcome(expanded_outcome)
                    
                    # Add to candidates
                    candidates_for_expansion.append(
                        (expanded_set, expanded_score, expanded_outcome)
                    )
                    
                    # Track best overall
                    if expanded_score > best_score:
                        best_hint_set = expanded_set
                        best_outcome = expanded_outcome
                        best_score = expanded_score
                    
                    # If we found a closing set and should stop, do so
                    if expanded_outcome.status == "success" and config.stop_on_first_close:
                        return SearchResult(
                            outcome="closed",
                            best_hint_set=expanded_set,
                            attempts=attempts,
                            explored_sets=explored_sets,
                            evidence=expanded_outcome
                        )
            
            # Prune to beam_width
            # Sort by score (descending), then by set size (ascending) for determinism
            candidates_for_expansion.sort(
                key=lambda x: (-x[1], x[0].size(), tuple(sorted(h.name for h in x[0].hints)))
            )
            
            # Keep top beam_width
            beam = candidates_for_expansion[:config.beam_width]
            
            # If beam is empty, we're done
            if not beam:
                break
        
        # Determine final outcome
        if best_outcome is not None and best_outcome.status == "success":
            final_outcome = "closed"
        elif best_outcome is not None:
            final_outcome = "partial"
        else:
            final_outcome = "failed"
        
        return SearchResult(
            outcome=final_outcome,
            best_hint_set=best_hint_set if not best_hint_set.is_empty() else None,
            attempts=attempts,
            explored_sets=explored_sets,
            evidence=best_outcome
        )
    
    def _score_outcome(self, outcome: ExecutionOutcome) -> float:
        """
        Score an execution outcome.
        
        Higher scores are better. Success > partial > failure.
        
        Args:
            outcome: Execution outcome to score
            
        Returns:
            Score value (higher is better)
            
        Requirements: 4.9
        """
        if outcome.status == "success":
            return 100.0
        elif outcome.status == "failure":
            # Check if output suggests progress (e.g., fewer unsolved goals)
            # For now, use a base score
            return 10.0
        elif outcome.status == "timeout":
            return 5.0
        elif outcome.status == "error":
            return 1.0
        else:
            return 0.0
