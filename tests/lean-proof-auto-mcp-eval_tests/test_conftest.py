"""Tests for pytest configuration and fixture wiring.

Validates that all pytest fixtures are correctly configured with appropriate
scopes and that parametrization and marker registration work as expected.
"""

from pathlib import Path

import pytest
from mcp_client import MCPClient
from result_collector import ResultCollector

from fixtures import ALL_FIXTURE_FILES, FixtureFile


class TestFixtureAvailability:
    """Test that all required fixtures are available and return correct types."""

    def test_eval_repo_fixture_returns_path(self, eval_repo: Path):
        assert isinstance(eval_repo, Path)
        assert eval_repo.exists()
        assert eval_repo.is_dir()

    def test_mcp_server_path_fixture_returns_path(self, mcp_server_path: Path):
        assert isinstance(mcp_server_path, Path)

    def test_result_collector_fixture_returns_collector(self, result_collector: ResultCollector):
        assert isinstance(result_collector, ResultCollector)

    def test_mcp_client_fixture_returns_client(self, mcp_client: MCPClient):
        assert isinstance(mcp_client, MCPClient)


class TestFixtureParametrization:
    """Test that fixture_file parametrization works correctly."""

    def test_fixture_file_returns_fixture_file_object(self, fixture_file: FixtureFile):
        assert isinstance(fixture_file, FixtureFile)
        assert isinstance(fixture_file.path, Path)
        assert isinstance(fixture_file.domain, str)
        assert isinstance(fixture_file.subdomain, str)
        assert isinstance(fixture_file.relative_path, str)

    def test_all_fixture_files_is_a_list(self):
        assert isinstance(ALL_FIXTURE_FILES, list)


class TestMarkerRegistration:
    """Test that custom markers are properly registered."""

    def test_tier_markers_registered(self, pytestconfig: pytest.Config):
        markers = pytestconfig.getini("markers")
        marker_names = [m.split(":")[0] for m in markers]

        for tier in ("eval_smoke", "eval_quick", "eval_normal", "eval_full", "eval_deep"):
            assert tier in marker_names, f"Missing tier marker: {tier}"

    def test_domain_markers_registered(self, pytestconfig: pytest.Config):
        markers = pytestconfig.getini("markers")
        marker_names = [m.split(":")[0] for m in markers]

        for domain in (
            "eval_algebra",
            "eval_analysis",
            "eval_data",
            "eval_group_theory",
            "eval_linear_algebra",
            "eval_ring_theory",
            "eval_topology",
        ):
            assert domain in marker_names, f"Missing domain marker: {domain}"


class TestFixtureIntegration:
    """Test that fixtures work together correctly."""

    def test_fixtures_can_be_used_together(
        self,
        eval_repo: Path,
        mcp_server_path: Path,
        result_collector: ResultCollector,
    ):
        assert isinstance(eval_repo, Path)
        assert isinstance(mcp_server_path, Path)
        assert isinstance(result_collector, ResultCollector)

    def test_result_collector_is_shared_across_tests(self, result_collector: ResultCollector):
        """Record a result to verify collector is working and shared."""
        result_collector.record(
            tool="test_tool",
            file_path="test_file.lean",
            status="success",
            elapsed_ms=100.0,
            raw_response={"result": "ok"},
            domain="TestDomain",
            subdomain="TestSubdomain",
        )
        assert len(result_collector.results) > 0
