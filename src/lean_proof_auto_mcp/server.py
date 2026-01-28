from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .adapters.router import ToolRouter
from .config import Config
from .tools.probe import probe
from .tools.probe_file import probe_file
from .tools.rank_targets import rank_targets
from .tools.scan_file import scan_file
from .tools.scan_theorem import scan_theorem
from .tools.search_annotations import search_annotations
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
    router.register("search_annotations", search_annotations)

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
        budget_s: float = 10.0,
        trace_config: dict | None = None,
    ) -> dict:
        """Run single-theorem automation probe with deterministic classification.

        Measures what happens when automation (aesop, aesop?, or grind) is applied
        to a single theorem under controlled conditions. Returns structured outcome
        with classification (trivial, promising, failed, timed_out).

        Args:
            file: Path to Lean file
            theorem_id: Theorem identifier to probe
            mode: Automation mode - "aesop", "aesop?", or "grind"
            budget_s: Time budget in seconds (default: 10.0)
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
        budget_s_per: float = 5.0,
        limit: int = 50,
        ordering: str = "file_order",
    ) -> dict:
        """Run batch automation probing across multiple theorems in a file.

        Produces a heatmap of automation behavior for triage and prioritization.
        Runs probe on each theorem with fixed parameters and aggregates results
        into summary statistics.

        Args:
            file: Path to Lean file
            mode: Automation mode - "aesop", "aesop?", or "grind"
            budget_s_per: Time budget per theorem in seconds (default: 5.0)
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

    @app.tool(name="search_annotations")
    def search_annotations_tool(
        file: str,
        theorem_id: str,
        mode: str = "local_only",
        automation: dict | None = None,
        budgets: dict | None = None,
        search: dict | None = None,
        candidates: dict | None = None,
        skeleton: dict | None = None,
        style: dict | None = None,
        workspace: dict | None = None,
        allow_global_edits: bool = False,
    ) -> dict:
        """Search for minimal local proof hints to make a theorem provable by automation.

        Discovers the minimal set of local hints (lemmas, definitions, rules) that
        enable automation to close a goal. Uses search strategies (greedy or beam)
        to explore hint combinations, then minimizes the result using delta-debugging.

        Args:
            file: Path to Lean file
            theorem_id: Theorem identifier to search
            mode: Operation mode - "local_only" or "suggest_global" (default: "local_only")
            automation: Automation configuration dict (optional)
            budgets: Budget configuration dict (optional)
            search: Search configuration dict (optional)
            candidates: Candidate configuration dict (optional)
            skeleton: Skeleton configuration dict (optional)
            style: Style configuration dict (optional)
            workspace: Workspace configuration dict (optional)
            allow_global_edits: Allow global edits (default: False)

        Returns:
            Search result with status, minimized hint set, proof patch, timing, and artifacts
        """
        return router.dispatch(
            "search_annotations",
            {
                "file": file,
                "theorem_id": theorem_id,
                "mode": mode,
                "automation": automation or {},
                "budgets": budgets or {},
                "search": search or {},
                "candidates": candidates or {},
                "skeleton": skeleton or {},
                "style": style or {},
                "workspace": workspace or {},
                "allow_global_edits": allow_global_edits,
            },
        )

    return app


def main() -> None:
    cfg = Config.from_env()

    # Change to the configured working directory
    import os

    if cfg.working_directory != os.getcwd():
        print(f"{cfg.server_name}: changing working directory to {cfg.working_directory}")
        os.chdir(cfg.working_directory)

    print(f"{cfg.server_name}: server started (api_version={cfg.api_version}, cwd={os.getcwd()})")
    create_app(cfg).run()  # stdio transport by default


if __name__ == "__main__":
    main()
