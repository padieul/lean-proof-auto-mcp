from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from .errors import ToolNotFoundError

Handler = Callable[[dict], dict]


@dataclass
class ToolRouter:
    """Minimal tool registry: tool_name -> handler."""

    handlers: dict[str, Handler] = field(default_factory=dict)

    def register(self, name: str, handler: Handler) -> None:
        if not name:
            raise ValueError("tool name must be non-empty")
        if name in self.handlers:
            raise ValueError(f"tool already registered: {name}")
        self.handlers[name] = handler

    def dispatch(
        self, name: str, args: dict | None = None, *, envelope: dict | None = None
    ) -> dict:
        handler = self.handlers.get(name)
        if handler is None:
            raise ToolNotFoundError(name)

        payload = handler(args or {})
        if envelope is None:
            return payload
        return {**envelope, **payload}
