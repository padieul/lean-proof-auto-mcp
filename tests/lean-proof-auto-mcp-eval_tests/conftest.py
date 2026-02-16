"""Pytest configuration and fixtures for evaluation testing framework.

This module provides pytest fixtures that wire together the evaluation framework
components following hexagonal architecture and dependency injection principles.

Fixture Scopes:
- Session: eval_repo, mcp_server_path, result_collector
- Module: mcp_client (one server instance per test module)
- Function: fixture_file (parametrized per fixture file)

Markers:
- Tier: eval_smoke, eval_quick, eval_normal, eval_full, eval_deep
- Domain: eval_algebra, eval_analysis, eval_data, eval_group_theory,
          eval_linear_algebra, eval_ring_theory, eval_topology
"""

import importlib.util
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

# Ensure the eval tests directory is on sys.path for bare imports
# (pytest adds it by default, but be explicit for robustness)
_this_dir = Path(__file__).parent
if str(_this_dir) not in sys.path:
    sys.path.insert(0, str(_this_dir))

# Force `fixtures` to resolve to this directory's `fixtures.py` to avoid
# collisions with `tests/fixtures` package during collection.
_fixtures_path = _this_dir / "fixtures.py"
_fixtures_spec = importlib.util.spec_from_file_location("fixtures", _fixtures_path)
if _fixtures_spec is None or _fixtures_spec.loader is None:
    raise RuntimeError(f"Failed to load eval fixtures module from {_fixtures_path}")
_fixtures_module = importlib.util.module_from_spec(_fixtures_spec)
sys.modules["fixtures"] = _fixtures_module
_fixtures_spec.loader.exec_module(_fixtures_module)

from eval_logger import EvalLogger
from mcp_client import MCPClient
from result_collector import ResultCollector

from fixtures import ALL_FIXTURE_FILES, FixtureFile, get_eval_repo_path


@pytest.fixture(scope="session")
def eval_repo() -> Path:
    """Session-scoped fixture providing eval repository path.

    Skips all tests if the eval repository is not configured or missing.
    """
    try:
        path = get_eval_repo_path()
    except FileNotFoundError as e:
        pytest.skip(f"Eval repository not found: {e}")

    if not path.exists():
        pytest.skip(f"Eval repository not found at {path}")

    return path


@pytest.fixture(scope="session")
def mcp_server_path() -> Path:
    """Session-scoped fixture providing MCP server path.

    Computes the path to server.py relative to this conftest.py file.
    """
    conftest_dir = Path(__file__).parent
    repo_root = conftest_dir.parent.parent
    return repo_root / "src" / "lean_proof_auto_mcp" / "server.py"


@pytest.fixture(scope="session")
def result_collector() -> ResultCollector:
    """Session-scoped fixture providing shared result collector."""
    return ResultCollector()


@pytest.fixture(scope="module")
def eval_logger(request: pytest.FixtureRequest) -> EvalLogger:
    """Module-scoped fixture providing an append-only eval logger.

    Creates one logger per test module, writing to logs/{module_name}.log.
    Logs are appended across runs, never overwritten.
    """
    module_name = request.module.__name__.rsplit(".", 1)[-1]
    return EvalLogger(module_name)


@pytest.fixture(scope="module")
def mcp_client(eval_repo: Path, mcp_server_path: Path) -> Iterator[MCPClient]:
    """Module-scoped fixture providing MCP client with running server.

    Uses context manager to ensure proper server lifecycle. The server
    is started once per test module and shared across all tests in that module.
    """
    with MCPClient(mcp_server_path, eval_repo, timeout=1800.0) as client:
        yield client


@pytest.fixture(
    params=ALL_FIXTURE_FILES if ALL_FIXTURE_FILES else [],
    ids=lambda f: f.relative_path,
)
def fixture_file(request: pytest.FixtureRequest) -> FixtureFile:
    """Parametrized fixture yielding each discovered fixture file.

    If ALL_FIXTURE_FILES is empty (eval repo not found), no tests are generated.
    """
    return request.param


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers for tier and domain filtering."""
    # Tier markers
    config.addinivalue_line("markers", "eval_smoke: Smoke tier (~2 min)")
    config.addinivalue_line("markers", "eval_quick: Quick tier (~10 min)")
    config.addinivalue_line("markers", "eval_normal: Normal tier (~30 min)")
    config.addinivalue_line("markers", "eval_full: Full tier (~2 hours)")
    config.addinivalue_line("markers", "eval_deep: Deep tier (unlimited)")

    # Domain markers
    config.addinivalue_line("markers", "eval_algebra: Algebra domain")
    config.addinivalue_line("markers", "eval_analysis: Analysis domain")
    config.addinivalue_line("markers", "eval_data: Data structures domain")
    config.addinivalue_line("markers", "eval_group_theory: Group theory domain")
    config.addinivalue_line("markers", "eval_linear_algebra: Linear algebra domain")
    config.addinivalue_line("markers", "eval_ring_theory: Ring theory domain")
    config.addinivalue_line("markers", "eval_topology: Topology domain")
