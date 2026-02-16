"""Global pytest configuration for test categorization."""

from __future__ import annotations

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Tag expensive suites so CI can exclude them via `-m "not heavy"`."""
    del config  # Unused, but kept for pytest hook signature.

    for item in items:
        path = str(item.path).replace("\\", "/")
        if "/tests/property/" in path or "/tests/lean-proof-auto-mcp-eval_tests/" in path:
            item.add_marker(pytest.mark.heavy)
