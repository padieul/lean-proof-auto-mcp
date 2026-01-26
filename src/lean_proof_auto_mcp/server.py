from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .adapters.router import ToolRouter
from .config import Config
from .tools.rank_targets import rank_targets
from .tools.scan_file import scan_file
from .tools.scan_theorem import scan_theorem
from .tools.verify import verify


def create_app(cfg: Config) -> FastMCP:
    router = ToolRouter()

    # Register core tool handlers
    router.register("scan_file", scan_file)
    router.register("scan_theorem", scan_theorem)
    router.register("rank_targets", rank_targets)
    router.register("verify", verify)

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
