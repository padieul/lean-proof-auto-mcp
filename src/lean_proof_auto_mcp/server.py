from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .adapters.router import ToolRouter
from .config import Config
from .tools.scan_file import scan_file
from .tools.scan_theorem import scan_theorem


def create_app(cfg: Config) -> FastMCP:
    router = ToolRouter()

    # Register core tool handlers
    router.register("scan_file", scan_file)
    router.register("scan_theorem", scan_theorem)

    app = FastMCP(cfg.server_name)

    @app.tool(name="scan_file")
    def scan_file_tool(file: str) -> dict:
        """Scan a Lean file and return summary information about theorems."""
        return router.dispatch("scan_file", {"file": file})

    @app.tool(name="scan_theorem")
    def scan_theorem_tool(file: str, target: dict) -> dict:
        """Analyze a single theorem in a Lean file with detailed structure and automation insights."""
        return router.dispatch("scan_theorem", {"file": file, "target": target})

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
