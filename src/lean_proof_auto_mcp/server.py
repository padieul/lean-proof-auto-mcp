from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .adapters.router import ToolRouter
from .config import Config
from .tools.scan_file import scan_file


def create_app(cfg: Config) -> FastMCP:
    router = ToolRouter()

    # Register core tool handlers
    router.register("hello", lambda args: {"message": f"hello, {args.get('name', 'world')}"})
    router.register("scan_file", scan_file)

    app = FastMCP(cfg.server_name)

    @app.tool(name="hello")
    def hello(name: str = "world") -> dict:
        return router.dispatch(
            "hello",
            {"name": name},
            envelope={"status": "success", "run_id": "run-0001", "api_version": cfg.api_version},
        )

    @app.tool(name="scan_file")
    def scan_file_tool(file: str) -> dict:
        """Scan a Lean file and return summary information about theorems."""
        return router.dispatch("scan_file", {"file": file})

    return app


def main() -> None:
    cfg = Config.from_env()
    print(f"{cfg.server_name}: server started (api_version={cfg.api_version})")
    create_app(cfg).run()  # stdio transport by default


if __name__ == "__main__":
    main()
