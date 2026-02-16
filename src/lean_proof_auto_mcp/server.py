from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .adapters.router import ToolRouter
from .config import Config
from .tools.get_proof_context import get_proof_context
from .tools.probe import probe
from .tools.probe_file import probe_file
from .tools.rank_targets import rank_targets
from .tools.scan_file import scan_file
from .tools.scan_theorem import scan_theorem
from .tools.search_automated_proof import search_automated_proof
from .tools.try_automated_proof import try_automated_proof
from .tools.verify import verify


def create_app(cfg: Config) -> FastMCP:
    router = ToolRouter()

    # Register core tool handlers
    router.register("scan_file", scan_file)
    router.register("scan_theorem", scan_theorem)
    router.register("rank_targets", rank_targets)
    router.register("verify", verify)
    router.register("probe", probe)
    router.register("probe_file", probe_file)
    router.register("search_automated_proof", search_automated_proof)
    router.register("try_automated_proof", try_automated_proof)
    router.register("get_proof_context", get_proof_context)

    app = FastMCP(cfg.server_name)

    @app.tool(name="scan_file")
    def scan_file_tool(file: str) -> dict:
        """Scan a Lean file and return summary information about theorems."""
        return router.dispatch("scan_file", {"file": file})

    @app.tool(name="scan_theorem")
    def scan_theorem_tool(file: str, target: dict) -> dict:
        """Analyze a single theorem in a Lean file with detailed structure and automation."""
        return router.dispatch("scan_theorem", {"file": file, "target": target})

    @app.tool(name="rank_targets")
    def rank_targets_tool(
        file: str,
        objective: str = "balanced",
        limit: int = 30,
        include_components: bool = True,
        include_reasons: bool = True,
        use_deep_structure: bool = False,
        min_confidence: float = 0.0,
    ) -> dict:
        """Rank theorem automation targets in a Lean file by objective."""
        return router.dispatch(
            "rank_targets",
            {
                "file": file,
                "objective": objective,
                "limit": limit,
                "include_components": include_components,
                "include_reasons": include_reasons,
                "use_deep_structure": use_deep_structure,
                "min_confidence": min_confidence,
            },
        )

    @app.tool(name="verify")
    def verify_tool(
        file: str,
        theorem_id: str | None = None,
        budget_s: float = 30.0,
        max_log_excerpt_chars: int = 2000,
        store_full_logs: bool = True,
        workspace_mode: str | None = None,
    ) -> dict:
        """Verify a Lean file or theorem with deterministic, sandboxed execution."""
        return router.dispatch(
            "verify",
            {
                "file": file,
                "theorem_id": theorem_id,
                "budget_s": budget_s,
                "max_log_excerpt_chars": max_log_excerpt_chars,
                "store_full_logs": store_full_logs,
                "workspace_mode": workspace_mode,
            },
        )

    @app.tool(name="probe")
    def probe_tool(
        file: str,
        theorem_id: str,
        mode: str,
        budget_s: float = 30.0,
        trace_config: dict | None = None,
    ) -> dict:
        """Run single-theorem automation probe with deterministic classification.

        Measures what happens when automation (aesop, aesop?, or grind) is applied
        to a single theorem under controlled conditions. Returns structured outcome
        with classification (trivial, promising, failed, timed_out).

        IMPORTANT: For Mathlib-scale projects, the Lean REPL environment loads in
        10-20 seconds on first use. Set budget_s to at least 30 seconds to allow
        the environment to load before verification begins. Budgets under 15 seconds
        will almost always timeout on first probe of a file.

        Args:
            file: Path to Lean file
            theorem_id: Theorem identifier to probe
            mode: Automation mode - "aesop", "aesop?", or "grind"
            budget_s: Time budget in seconds (default: 30.0, minimum recommended: 30.0 for Mathlib)
            trace_config: Optional trace configuration dict

        Returns:
            Probe result with status, classification, diagnostics, timing, and metadata
        """
        return router.dispatch(
            "probe",
            {
                "file": file,
                "theorem_id": theorem_id,
                "mode": mode,
                "budget_s": budget_s,
                "trace_config": trace_config,
            },
        )

    @app.tool(name="probe_file")
    def probe_file_tool(
        file: str,
        mode: str,
        budget_s_per: float = 30.0,
        limit: int = 50,
        ordering: str = "file_order",
    ) -> dict:
        """Run batch automation probing across multiple theorems in a file.

        Produces a heatmap of automation behavior for triage and prioritization.
        Runs probe on each theorem with fixed parameters and aggregates results
        into summary statistics.

        IMPORTANT: For Mathlib-scale projects, the Lean REPL environment loads in
        10-20 seconds on first use, then stays warm for subsequent theorems in the
        same batch. Set budget_s_per to at least 30 seconds to allow the first
        theorem's environment load. Budgets under 15 seconds will almost always
        timeout on the first theorem, then create a new REPL for each subsequent
        theorem (defeating batch efficiency).

        Args:
            file: Path to Lean file
            mode: Automation mode - "aesop", "aesop?", or "grind"
            budget_s_per: Time budget per theorem in seconds (default: 30.0, minimum recommended: 30.0 for Mathlib)
            limit: Maximum number of theorems to probe (default: 50)
            ordering: Ordering mode - "file_order" or "rank_targets" (default: "file_order")

        Returns:
            Batch probe result with summary statistics and per-theorem results
        """
        return router.dispatch(
            "probe_file",
            {
                "file": file,
                "mode": mode,
                "budget_s_per": budget_s_per,
                "limit": limit,
                "ordering": ordering,
            },
        )

    @app.tool(name="search_automated_proof")
    def search_automated_proof_tool(
        file: str,
        theorem_id: str,
        search_depth: str = "normal",
        search_budget_s: float | None = None,
        max_candidates: int | None = None,
        candidate_sources: list[str] | None = None,
        max_candidates_per_source: int | None = None,
        automation_mode: str = "aesop",
        automation_secondary: str | None = None,
        search_strategy: str = "greedy",
        beam_width: int = 3,
        max_search_steps: int | None = None,
        max_hints_in_set: int = 10,
        allow_simp_hints: bool = True,
        allow_unfold_hints: bool = True,
        allow_unsafe_hints: bool = False,
        minimize_hints: bool = True,
        minimize_budget_s: float | None = None,
        return_proof_states: bool = True,
        return_partial_progress: bool = True,
        return_context: bool = False,
        return_similar_proofs: bool = False,
        return_search_trace: bool = False,
    ) -> dict:
        """Search for automated proof with rich feedback and LLM-controlled parameters.

        Enhanced search tool with LLM-controlled search depth presets, rich feedback
        mechanisms, and support for all candidate sources including original_proof_refs.

        Args:
            file: Path to Lean file
            theorem_id: Theorem identifier to search
            search_depth: Search depth preset - "quick", "normal", "deep",
                "exhaustive" (default: "normal")
            search_budget_s: Override search budget in seconds (optional)
            max_candidates: Override max candidates (optional)
            candidate_sources: List of candidate sources to use (optional)
            max_candidates_per_source: Max candidates per source (optional)
            automation_mode: Automation mode - "aesop", "simp", "omega",
                "grind" (default: "aesop")
            automation_secondary: Secondary automation for fallback (optional)
            search_strategy: Search strategy - "greedy", "beam", "exhaustive" (default: "greedy")
            beam_width: Beam width for beam search (default: 3)
            max_search_steps: Maximum search steps (optional)
            max_hints_in_set: Maximum hints in a set (default: 10)
            allow_simp_hints: Allow simp hints (default: True)
            allow_unfold_hints: Allow unfold hints (default: True)
            allow_unsafe_hints: Allow unsafe hints (default: False)
            minimize_hints: Minimize hint set after finding solution (default: True)
            minimize_budget_s: Override minimization budget (optional)
            return_proof_states: Return initial and final proof states (default: True)
            return_partial_progress: Return partial progress information (default: True)
            return_context: Return theorem context (default: False)
            return_similar_proofs: Return similar proofs (default: False)
            return_search_trace: Return detailed search trace (default: False)

        Returns:
            Search result with outcome, hints, feedback, metadata, and optional trace
        """
        # Build args dict, filtering out None values
        args_dict: dict[str, int | float | str | bool | list | None] = {
            "file": file,
            "theorem_id": theorem_id,
            "search_depth": search_depth,
            "automation_mode": automation_mode,
            "automation_secondary": automation_secondary,
            "search_strategy": search_strategy,
            "beam_width": beam_width,
            "max_hints_in_set": max_hints_in_set,
            "allow_simp_hints": allow_simp_hints,
            "allow_unfold_hints": allow_unfold_hints,
            "allow_unsafe_hints": allow_unsafe_hints,
            "minimize_hints": minimize_hints,
            "return_proof_states": return_proof_states,
            "return_partial_progress": return_partial_progress,
            "return_context": return_context,
            "return_similar_proofs": return_similar_proofs,
            "return_search_trace": return_search_trace,
        }

        # Add optional overrides if provided
        if search_budget_s is not None:
            args_dict["search_budget_s"] = search_budget_s
        if max_candidates is not None:
            args_dict["max_candidates"] = max_candidates
        if candidate_sources is not None:
            args_dict["candidate_sources"] = candidate_sources
        if max_candidates_per_source is not None:
            args_dict["max_candidates_per_source"] = max_candidates_per_source
        if max_search_steps is not None:
            args_dict["max_search_steps"] = max_search_steps
        if minimize_budget_s is not None:
            args_dict["minimize_budget_s"] = minimize_budget_s

        return router.dispatch("search_automated_proof", args_dict)

    @app.tool(name="try_automated_proof")
    def try_automated_proof_tool(
        file: str,
        theorem_id: str,
        proof_attempt: str,
        timeout_s: float = 10.0,
        return_proof_state: bool = True,
    ) -> dict:
        """Validate a proof attempt with detailed feedback.

        Fast validation of LLM-generated proof attempts with structured feedback
        including error messages, locations, remaining proof state, and tactical
        suggestions.

        Args:
            file: Path to Lean file
            theorem_id: Theorem identifier
            proof_attempt: Proof code to validate
            timeout_s: Timeout in seconds (default: 10.0)
            return_proof_state: Return proof state for incomplete proofs (default: True)

        Returns:
            Validation result with status, error info, proof state, suggestions, and metadata
        """
        return router.dispatch(
            "try_automated_proof",
            {
                "file": file,
                "theorem_id": theorem_id,
                "proof_attempt": proof_attempt,
                "timeout_s": timeout_s,
                "return_proof_state": return_proof_state,
            },
        )

    @app.tool(name="get_proof_context")
    def get_proof_context_tool(
        file: str,
        theorem_id: str,
        include_similar_proofs: bool = True,
        similarity_threshold: float = 0.7,
    ) -> dict:
        """Get rich context about a theorem.

        Extract comprehensive context for LLM reasoning including theorem statement,
        original proof, hypotheses, in-scope declarations, namespace, and similar
        proofs with similarity scores.

        Args:
            file: Path to Lean file
            theorem_id: Theorem identifier
            include_similar_proofs: Include similar proofs (default: True)
            similarity_threshold: Minimum similarity score (default: 0.7)

        Returns:
            Context with statement, proof, hypotheses, scope, similar proofs, and metadata
        """
        return router.dispatch(
            "get_proof_context",
            {
                "file": file,
                "theorem_id": theorem_id,
                "include_similar_proofs": include_similar_proofs,
                "similarity_threshold": similarity_threshold,
            },
        )

    return app


def main() -> None:
    cfg = Config.from_env()

    # Change to the configured working directory
    import os
    import sys

    if cfg.working_directory != os.getcwd():
        print(
            f"{cfg.server_name}: changing working directory to {cfg.working_directory}",
            file=sys.stderr,
        )
        os.chdir(cfg.working_directory)

    print(
        f"{cfg.server_name}: server started (api_version={cfg.api_version}, cwd={os.getcwd()})",
        file=sys.stderr,
    )
    create_app(cfg).run()  # stdio transport by default


if __name__ == "__main__":
    main()
