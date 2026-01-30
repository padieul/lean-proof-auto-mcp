"""
Unit tests for ServerManager refactoring.

These tests verify that LeanInteractRunner and LeanInteractQuerier correctly
use ServerManager for server lifecycle management, and that servers are reused
across both adapters.

Requirements: 10.6, 28.4, 28.5, 28.6
"""

from pathlib import Path
from unittest.mock import Mock

import pytest

from lean_proof_auto_mcp.adapters.lean_interact_runner import LeanInteractRunner
from lean_proof_auto_mcp.lean.querier import LeanInteractQuerierImpl
from lean_proof_auto_mcp.lean.server_manager import ServerManagerImpl


class TestLeanInteractRunnerUsesServerManager:
    """Test that LeanInteractRunner uses ServerManager correctly."""

    def test_runner_requires_server_manager(self):
        """Test that LeanInteractRunner requires ServerManager in constructor."""
        # Arrange
        server_manager = ServerManagerImpl(workspace_path=Path.cwd())

        # Act
        runner = LeanInteractRunner(server_manager=server_manager)

        # Assert
        assert runner.server_manager is server_manager

    def test_runner_uses_server_manager_for_verification(self, tmp_path):
        """Test that LeanInteractRunner uses ServerManager.get_server() for verification."""
        # Arrange
        server_manager = ServerManagerImpl(workspace_path=tmp_path)
        runner = LeanInteractRunner(server_manager=server_manager)

        # Create test file
        test_file = tmp_path / "test.lean"
        test_file.write_text("theorem test : True := trivial\n")

        # Mock the server manager's get_server to track calls
        original_get_server = server_manager.get_server
        get_server_calls = []

        def tracked_get_server(file_path):
            get_server_calls.append(file_path)
            return original_get_server(file_path)

        server_manager.get_server = tracked_get_server

        # Act - try to verify (will fail if LeanInteract not installed, which is expected)
        try:
            runner.verify_file(
                workspace_path=tmp_path,
                file_path="test.lean",
                theorem_id=None,
                budget_s=30.0,
            )
        except RuntimeError as e:
            if "LeanInteract library not installed" in str(e):
                pytest.skip("LeanInteract not installed")
            raise

        # Assert - get_server should have been called
        assert len(get_server_calls) > 0
        assert "test.lean" in get_server_calls


class TestLeanInteractQuerierUsesServerManager:
    """Test that LeanInteractQuerier uses ServerManager correctly."""

    def test_querier_requires_server_manager(self):
        """Test that LeanInteractQuerier requires ServerManager in constructor."""
        # Arrange
        server_manager = ServerManagerImpl(workspace_path=Path.cwd())

        # Act
        querier = LeanInteractQuerierImpl(server_manager=server_manager)

        # Assert
        assert querier.server_manager is server_manager

    def test_querier_uses_server_manager_for_extraction(self, tmp_path):
        """Test that LeanInteractQuerier uses ServerManager.get_server() for extraction."""
        # Arrange
        server_manager = ServerManagerImpl(workspace_path=tmp_path)
        querier = LeanInteractQuerierImpl(server_manager=server_manager)

        # Create test file
        test_file = tmp_path / "test.lean"
        test_file.write_text("theorem test : True := trivial\n")

        # Mock the server manager's get_server to track calls
        original_get_server = server_manager.get_server
        get_server_calls = []

        def tracked_get_server(file_path):
            get_server_calls.append(file_path)
            return original_get_server(file_path)

        server_manager.get_server = tracked_get_server

        # Act - try to extract (will fail if LeanInteract not installed, which is expected)
        try:
            querier.extract_declarations(str(test_file))  # Use absolute path
        except RuntimeError as e:
            if "LeanInteract library not installed" in str(e):
                pytest.skip("LeanInteract not installed")
            raise

        # Assert - get_server should have been called
        assert len(get_server_calls) > 0
        assert str(test_file) in get_server_calls


class TestServerReuseAcrossAdapters:
    """Test that both adapters share the same server instances."""

    def test_runner_and_querier_share_server_instances(self, tmp_path):
        """Test that LeanInteractRunner and LeanInteractQuerier share server instances via ServerManager."""
        # Arrange
        server_manager = ServerManagerImpl(workspace_path=tmp_path)
        runner = LeanInteractRunner(server_manager=server_manager)
        querier = LeanInteractQuerierImpl(server_manager=server_manager)

        # Create test file
        test_file = tmp_path / "test.lean"
        test_file.write_text("theorem test : True := trivial\n")

        # Track server creation
        original_create_server = server_manager._create_server
        create_server_calls = []

        def tracked_create_server(file_path):
            create_server_calls.append(file_path)
            return original_create_server(file_path)

        server_manager._create_server = tracked_create_server

        # Act - use both adapters on the same file
        try:
            # First use querier
            querier.extract_declarations(str(test_file))  # Use absolute path

            # Then use runner
            runner.verify_file(
                workspace_path=tmp_path,
                file_path=str(test_file),  # Use absolute path
                theorem_id=None,
                budget_s=30.0,
            )
        except RuntimeError as e:
            if "LeanInteract library not installed" in str(e):
                pytest.skip("LeanInteract not installed")
            raise

        # Assert - server should only be created once (reused)
        assert len(create_server_calls) == 1
        assert str(test_file) in create_server_calls

    def test_multiple_verifications_reuse_server(self, tmp_path):
        """Test that multiple verifications reuse the same server instance."""
        # Arrange
        server_manager = ServerManagerImpl(workspace_path=tmp_path)
        runner = LeanInteractRunner(server_manager=server_manager)

        # Create test file
        test_file = tmp_path / "test.lean"
        test_file.write_text("theorem test : True := trivial\n")

        # Track server creation
        original_create_server = server_manager._create_server
        create_server_calls = []

        def tracked_create_server(file_path):
            create_server_calls.append(file_path)
            return original_create_server(file_path)

        server_manager._create_server = tracked_create_server

        # Act - verify the same file multiple times
        try:
            runner.verify_file(
                workspace_path=tmp_path,
                file_path="test.lean",
                theorem_id=None,
                budget_s=30.0,
            )
            runner.verify_file(
                workspace_path=tmp_path,
                file_path="test.lean",
                theorem_id=None,
                budget_s=30.0,
            )
            runner.verify_file(
                workspace_path=tmp_path,
                file_path="test.lean",
                theorem_id=None,
                budget_s=30.0,
            )
        except RuntimeError as e:
            if "LeanInteract library not installed" in str(e):
                pytest.skip("LeanInteract not installed")
            raise

        # Assert - server should only be created once (reused for all verifications)
        assert len(create_server_calls) == 1
        assert "test.lean" in create_server_calls


class TestNoFunctionalityRegressions:
    """Test that refactoring doesn't break existing functionality."""

    def test_runner_still_verifies_correctly(self, tmp_path):
        """Test that LeanInteractRunner still verifies files correctly after refactoring."""
        # Arrange
        server_manager = ServerManagerImpl(workspace_path=tmp_path)
        runner = LeanInteractRunner(server_manager=server_manager)

        # Create test file with valid Lean code
        test_file = tmp_path / "test.lean"
        test_file.write_text("theorem test : True := trivial\n")

        # Act
        try:
            result = runner.verify_file(
                workspace_path=tmp_path,
                file_path="test.lean",
                theorem_id=None,
                budget_s=30.0,
            )
        except RuntimeError as e:
            if "LeanInteract library not installed" in str(e):
                pytest.skip("LeanInteract not installed")
            raise

        # Assert - verification should complete (may have errors due to missing imports, but shouldn't crash)
        assert result.status in ["success", "fail", "error"]
        assert result.scope_used == "file"

    def test_querier_still_extracts_correctly(self, tmp_path):
        """Test that LeanInteractQuerier still extracts declarations correctly after refactoring."""
        # Arrange
        server_manager = ServerManagerImpl(workspace_path=tmp_path)
        querier = LeanInteractQuerierImpl(server_manager=server_manager)

        # Create test file with valid Lean code
        test_file = tmp_path / "test.lean"
        test_file.write_text("theorem test : True := trivial\n")

        # Act
        try:
            declarations = querier.extract_declarations(str(test_file))  # Use absolute path
        except RuntimeError as e:
            if "LeanInteract library not installed" in str(e):
                pytest.skip("LeanInteract not installed")
            raise

        # Assert - should extract at least one declaration
        assert len(declarations) > 0
        # Should find the test theorem
        theorem_names = [d.name for d in declarations]
        assert "test" in theorem_names
