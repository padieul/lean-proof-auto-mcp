from __future__ import annotations


class MCPServerError(Exception):
    """Base server error (domain-level)."""


class ToolNotFoundError(MCPServerError):
    def __init__(self, tool_name: str) -> None:
        super().__init__(f"tool not found: {tool_name}")
        self.tool_name = tool_name
