"""
Unit tests for LeanInteract adapter error handling.

These tests verify error handling for LeanInteract crash recovery,
timeout handling, and invalid input handling across the adapter layer.

Requirements: 11.1, 11.2, 11.3
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from lean_proof_auto_mcp.lean.ports import Declaration, Range
from lean_proof_auto_mcp.lean.proof_state import LeanInteractProofStateInspector
from lean_proof_auto_mcp.lean.server_manager import LeanInteractServerManager
from lean_proof_auto_mcp.lean.validator import LeanInteractProofValidator


class TestProofValidatorErrorHandling:
    """
    Test error handling in ProofValidator.

    Requirements: 11.1, 11.2, 11.3
    """

    def test_validate_without_lean_interact_installed(self):
        """
        Test validation when LeanInteract is not installed.

        Requirements: 11.3
        """
        # Arrange
        mock_server_manager = Mock()
        mock_server = Mock()
        mock_server_manager.get_server.return_value = mock_server
        validator = LeanInteractProofValidator(server_manager=mock_server_manager)

        # Patch LEAN_INTERACT_AVAILABLE to False
        with patch("lean_proof_auto_mcp.lean.validator.LEAN_INTERACT_AVAILABLE", False):
            # Act
            result = validator.validate_proof(
                theorem_statement="True",
                proof_attempt="trivial",
                timeout_s=10.0,
            )

        # Assert
        assert result.status == "error"
        assert "LeanInteract library not installed" in result.error_message
        assert result.error_location is None
        assert result.proof_state is None
        assert len(result.suggestions) > 0
        assert "Install LeanInteract" in result.suggestions[0]

    def test_validate_without_server_instance(self):
        """
        Test validation when no server instance is available.

        Requirements: 11.3
        """
        # Arrange
        mock_server_manager = Mock()
        mock_server_manager.get_server.return_value = None
        validator = LeanInteractProofValidator(server_manager=mock_server_manager)

        # Act
        result = validator.validate_proof(
            theorem_statement="True",
            proof_attempt="trivial",
            timeout_s=10.0,
        )

        # Assert
        assert result.status == "error"
        assert "No server instance available" in result.error_message
        assert result.error_location is None
        assert result.proof_state is None
        assert len(result.suggestions) > 0

    def test_validate_with_timeout_error(self):
        """
        Test validation when timeout occurs.

        Requirements: 11.2
        """
        # Arrange
        mock_server_manager = Mock()
        mock_server = Mock()
        mock_server.run.side_effect = TimeoutError("Validation timed out")
        mock_server_manager.get_server.return_value = mock_server

        # Patch Command to avoid validation errors
        with patch("lean_proof_auto_mcp.lean.validator.Command"):
            validator = LeanInteractProofValidator(server_manager=mock_server_manager)

            # Act
            result = validator.validate_proof(
                theorem_statement="True",
                proof_attempt="trivial",
                timeout_s=10.0,
            )

        # Assert
        assert result.status == "timeout"
        assert "timed out" in result.error_message.lower()
        assert result.error_location is None
        assert result.proof_state is None
        assert len(result.suggestions) > 0
        assert any("simplify" in s.lower() for s in result.suggestions)

    def test_validate_with_lean_error_timeout(self):
        """
        Test validation when LeanError indicates timeout.

        Requirements: 11.2
        """
        # Arrange
        mock_server_manager = Mock()
        mock_server = Mock()
        mock_lean_error = Mock()
        mock_lean_error.__str__ = lambda self: "Lean timed out after 10 seconds"
        mock_server.run.return_value = mock_lean_error
        mock_server_manager.get_server.return_value = mock_server

        # Patch both LeanError and Command
        with (
            patch("lean_proof_auto_mcp.lean.validator.LeanError", type(mock_lean_error)),
            patch("lean_proof_auto_mcp.lean.validator.Command"),
        ):
            validator = LeanInteractProofValidator(server_manager=mock_server_manager)

            # Act
            result = validator.validate_proof(
                theorem_statement="True",
                proof_attempt="trivial",
                timeout_s=10.0,
            )

        # Assert
        assert result.status == "timeout"
        assert "timed out" in result.error_message.lower()
        assert len(result.suggestions) > 0

    def test_validate_with_lean_error_other(self):
        """
        Test validation when LeanError indicates other error.

        Requirements: 11.3
        """
        # Arrange
        mock_server_manager = Mock()
        mock_server = Mock()
        mock_lean_error = Mock()
        mock_lean_error.__str__ = lambda self: "Syntax error in proof"
        mock_server.run.return_value = mock_lean_error
        mock_server_manager.get_server.return_value = mock_server

        # Patch both LeanError and Command
        with (
            patch("lean_proof_auto_mcp.lean.validator.LeanError", type(mock_lean_error)),
            patch("lean_proof_auto_mcp.lean.validator.Command"),
        ):
            validator = LeanInteractProofValidator(server_manager=mock_server_manager)

            # Act
            result = validator.validate_proof(
                theorem_statement="True",
                proof_attempt="trivial",
                timeout_s=10.0,
            )

        # Assert
        assert result.status == "error"
        assert "Syntax error" in result.error_message
        assert len(result.suggestions) > 0

    def test_validate_with_runtime_exception(self):
        """
        Test validation when unexpected exception occurs.

        Requirements: 11.3
        """
        # Arrange
        mock_server_manager = Mock()
        mock_server = Mock()
        mock_server.run.side_effect = RuntimeError("Unexpected server crash")
        mock_server_manager.get_server.return_value = mock_server

        # Patch Command to avoid validation errors
        with patch("lean_proof_auto_mcp.lean.validator.Command"):
            validator = LeanInteractProofValidator(server_manager=mock_server_manager)

            # Act
            result = validator.validate_proof(
                theorem_statement="True",
                proof_attempt="trivial",
                timeout_s=10.0,
            )

        # Assert
        assert result.status == "error"
        assert "Unexpected server crash" in result.error_message
        assert result.error_location is None
        assert result.proof_state is None
        assert len(result.suggestions) > 0

    def test_validate_with_type_mismatch_error(self):
        """
        Test validation with type mismatch error generates appropriate suggestions.

        Requirements: 11.3
        """
        # Arrange
        mock_server_manager = Mock()
        mock_server = Mock()
        mock_response = Mock()
        mock_message = Mock()
        mock_message.severity = "error"
        mock_message.data = "type mismatch: expected Nat, got Bool"
        mock_message.start_pos = Mock(line=5, column=10)
        mock_response.messages = [mock_message]
        mock_response.sorries = []
        mock_response.goals = []
        mock_server.run.return_value = mock_response
        mock_server_manager.get_server.return_value = mock_server

        # Patch Command to avoid validation errors
        with patch("lean_proof_auto_mcp.lean.validator.Command"):
            validator = LeanInteractProofValidator(server_manager=mock_server_manager)

            # Act
            result = validator.validate_proof(
                theorem_statement="True",
                proof_attempt="trivial",
                timeout_s=10.0,
            )

        # Assert
        assert result.status == "rejected"
        assert "type mismatch" in result.error_message.lower()
        assert result.error_location == (5, 10)
        assert any("type" in s.lower() for s in result.suggestions)

    def test_validate_with_unknown_identifier_error(self):
        """
        Test validation with unknown identifier error generates appropriate suggestions.

        Requirements: 11.3
        """
        # Arrange
        mock_server_manager = Mock()
        mock_server = Mock()
        mock_response = Mock()
        mock_message = Mock()
        mock_message.severity = "error"
        mock_message.data = "unknown identifier 'foo'"
        mock_message.start_pos = Mock(line=3, column=5)
        mock_response.messages = [mock_message]
        mock_response.sorries = []
        mock_response.goals = []
        mock_server.run.return_value = mock_response
        mock_server_manager.get_server.return_value = mock_server

        # Patch Command to avoid validation errors
        with patch("lean_proof_auto_mcp.lean.validator.Command"):
            validator = LeanInteractProofValidator(server_manager=mock_server_manager)

            # Act
            result = validator.validate_proof(
                theorem_statement="True",
                proof_attempt="trivial",
                timeout_s=10.0,
            )

        # Assert
        assert result.status == "rejected"
        assert "unknown identifier" in result.error_message.lower()
        assert any("spelling" in s.lower() or "import" in s.lower() for s in result.suggestions)


class TestProofStateInspectorErrorHandling:
    """
    Test error handling in ProofStateInspector.

    Requirements: 11.1, 11.2, 11.3
    """

    def test_get_initial_proof_state_without_lean_interact(self):
        """
        Test getting initial proof state when LeanInteract is not installed.

        Requirements: 11.3
        """
        # Arrange
        mock_server_manager = Mock()
        inspector = LeanInteractProofStateInspector(server_manager=mock_server_manager)
        theorem = Declaration(
            name="test_theorem",
            full_name="test_theorem",
            type="True",
            value=None,
            attributes=[],
            range=Range(start_line=1, start_col=0, end_line=1, end_col=10),
            namespace="",
        )

        # Patch LEAN_INTERACT_AVAILABLE to False
        with (
            patch("lean_proof_auto_mcp.lean.proof_state.LEAN_INTERACT_AVAILABLE", False),
            pytest.raises(RuntimeError, match="LeanInteract library not installed"),
        ):
            inspector.get_initial_proof_state(theorem)

    def test_get_initial_proof_state_without_server(self):
        """
        Test getting initial proof state when no server instance is available.

        Requirements: 11.3
        """
        # Arrange
        mock_server_manager = Mock()
        mock_server_manager.get_server.return_value = None
        inspector = LeanInteractProofStateInspector(server_manager=mock_server_manager)
        theorem = Declaration(
            name="test_theorem",
            full_name="test_theorem",
            type="True",
            value=None,
            attributes=[],
            range=Range(start_line=1, start_col=0, end_line=1, end_col=10),
            namespace="",
        )

        # Act & Assert
        # The implementation catches the AttributeError and wraps it in RuntimeError
        with pytest.raises(RuntimeError, match="Failed to get initial proof state"):
            inspector.get_initial_proof_state(theorem)

    def test_get_initial_proof_state_with_lean_error(self):
        """
        Test getting initial proof state when LeanError occurs.

        Requirements: 11.3
        """
        # Arrange
        mock_server_manager = Mock()
        mock_server = Mock()
        mock_lean_error = Mock()
        mock_lean_error.__str__ = lambda self: "Syntax error in theorem"
        mock_server.run.return_value = mock_lean_error
        mock_server_manager.get_server.return_value = mock_server

        # Patch both LeanError and Command
        with (
            patch("lean_proof_auto_mcp.lean.proof_state.LeanError", type(mock_lean_error)),
            patch("lean_proof_auto_mcp.lean.proof_state.Command"),
        ):
            inspector = LeanInteractProofStateInspector(server_manager=mock_server_manager)
            theorem = Declaration(
                name="test_theorem",
                full_name="test_theorem",
                type="True",
                value=None,
                attributes=[],
                range=Range(start_line=1, start_col=0, end_line=1, end_col=10),
                namespace="",
            )

            # Act & Assert
            with pytest.raises(RuntimeError, match="LeanInteract error"):
                inspector.get_initial_proof_state(theorem)

    def test_get_initial_proof_state_with_exception(self):
        """
        Test getting initial proof state when unexpected exception occurs.

        Requirements: 11.3
        """
        # Arrange
        mock_server_manager = Mock()
        mock_server = Mock()
        mock_server.run.side_effect = RuntimeError("Server crashed")
        mock_server_manager.get_server.return_value = mock_server
        inspector = LeanInteractProofStateInspector(server_manager=mock_server_manager)
        theorem = Declaration(
            name="test_theorem",
            full_name="test_theorem",
            type="True",
            value=None,
            attributes=[],
            range=Range(start_line=1, start_col=0, end_line=1, end_col=10),
            namespace="",
        )

        # Act & Assert
        with pytest.raises(RuntimeError, match="Failed to get initial proof state"):
            inspector.get_initial_proof_state(theorem)

    def test_apply_tactic_without_lean_interact(self):
        """
        Test applying tactic when LeanInteract is not installed.

        Requirements: 11.3
        """
        # Arrange
        mock_server_manager = Mock()
        inspector = LeanInteractProofStateInspector(server_manager=mock_server_manager)

        # Patch LEAN_INTERACT_AVAILABLE to False
        with (
            patch("lean_proof_auto_mcp.lean.proof_state.LEAN_INTERACT_AVAILABLE", False),
            pytest.raises(RuntimeError, match="LeanInteract library not installed"),
        ):
            inspector.apply_tactic(proof_state_id=1, tactic="trivial")

    def test_apply_tactic_without_server(self):
        """
        Test applying tactic when no server instance is available.

        Requirements: 11.3
        """
        # Arrange
        mock_server_manager = Mock()
        mock_server_manager.get_server.return_value = None
        inspector = LeanInteractProofStateInspector(server_manager=mock_server_manager)

        # Act
        # The implementation catches exceptions and returns TacticResult with success=False
        result = inspector.apply_tactic(proof_state_id=1, tactic="trivial")

        # Assert
        assert result.success is False
        assert result.new_proof_state is None
        assert result.error_message is not None
        assert "'NoneType'" in result.error_message or "has no attribute" in result.error_message

    def test_apply_tactic_with_lean_error(self):
        """
        Test applying tactic when LeanError occurs.

        Requirements: 11.3
        """
        # Arrange
        mock_server_manager = Mock()
        mock_server = Mock()
        mock_lean_error = Mock()
        mock_lean_error.__str__ = lambda self: "Tactic failed"
        mock_server.run.return_value = mock_lean_error
        mock_server_manager.get_server.return_value = mock_server

        # Patch LeanError to match the mock
        with patch("lean_proof_auto_mcp.lean.proof_state.LeanError", type(mock_lean_error)):
            inspector = LeanInteractProofStateInspector(server_manager=mock_server_manager)

            # Act
            result = inspector.apply_tactic(proof_state_id=1, tactic="trivial")

        # Assert
        assert result.success is False
        assert result.new_proof_state is None
        assert "Tactic failed" in result.error_message

    def test_apply_tactic_with_exception(self):
        """
        Test applying tactic when unexpected exception occurs.

        Requirements: 11.3
        """
        # Arrange
        mock_server_manager = Mock()
        mock_server = Mock()
        mock_server.run.side_effect = RuntimeError("Server crashed")
        mock_server_manager.get_server.return_value = mock_server
        inspector = LeanInteractProofStateInspector(server_manager=mock_server_manager)

        # Act
        result = inspector.apply_tactic(proof_state_id=1, tactic="trivial")

        # Assert
        assert result.success is False
        assert result.new_proof_state is None
        assert "Server crashed" in result.error_message


class TestServerManagerErrorHandling:
    """
    Test error handling in ServerManager.

    Requirements: 11.1, 11.2, 11.3
    """

    def test_get_server_without_lean_interact(self):
        """
        Test getting server when LeanInteract is not installed.

        Requirements: 11.3
        """
        # Patch LEAN_INTERACT_AVAILABLE before creating manager
        with patch("lean_proof_auto_mcp.lean.server_manager.LEAN_INTERACT_AVAILABLE", False):
            # Arrange
            manager = LeanInteractServerManager()

            # Act & Assert
            with pytest.raises(RuntimeError, match="LeanInteract library not installed"):
                manager.get_server("/path/to/file.lean")

    def test_get_server_with_creation_failure(self):
        """
        Test getting server when server creation fails.

        Requirements: 11.3
        """
        # Patch LeanServer before creating manager to avoid real server creation
        with (
            patch("lean_proof_auto_mcp.lean.server_manager.LeanServer") as mock_lean_server,
            patch("lean_proof_auto_mcp.lean.server_manager.LeanREPLConfig"),
        ):
            mock_lean_server.side_effect = RuntimeError("Failed to start server")

            # Arrange
            manager = LeanInteractServerManager()

            # Act & Assert
            with pytest.raises(RuntimeError, match="Failed to create server"):
                manager.get_server("/path/to/file.lean")

    def test_restart_server_with_dead_server(self):
        """
        Test restarting server when existing server is dead.

        Requirements: 11.1
        """
        # Patch LeanServer before creating manager
        with (
            patch("lean_proof_auto_mcp.lean.server_manager.LeanServer") as mock_lean_server,
            patch("lean_proof_auto_mcp.lean.server_manager.LeanREPLConfig"),
        ):
            # Arrange — use workspace_path so cache key is predictable
            manager = LeanInteractServerManager(workspace_path=Path("/path/to"))

            # Create a mock dead server keyed by project root
            cache_key = str(Path("/path/to"))
            mock_dead_server = Mock()
            mock_dead_server.run = None  # Missing method indicates dead server
            manager._servers[cache_key] = mock_dead_server

            # Setup new server creation
            mock_new_server = Mock()
            mock_lean_server.return_value = mock_new_server

            # Act
            manager.restart_server("/path/to/file.lean")

            # Assert
            assert manager._servers[cache_key] == mock_new_server
            mock_dead_server.kill.assert_called_once()

    def test_restart_server_with_kill_failure(self):
        """
        Test restarting server when killing old server fails.

        Requirements: 11.1
        """
        # Patch LeanServer before creating manager
        with (
            patch("lean_proof_auto_mcp.lean.server_manager.LeanServer") as mock_lean_server,
            patch("lean_proof_auto_mcp.lean.server_manager.LeanREPLConfig"),
        ):
            # Arrange — use workspace_path so cache key is predictable
            manager = LeanInteractServerManager(workspace_path=Path("/path/to"))

            # Create a mock server that fails to kill, keyed by project root
            cache_key = str(Path("/path/to"))
            mock_old_server = Mock()
            mock_old_server.kill.side_effect = RuntimeError("Failed to kill")
            manager._servers[cache_key] = mock_old_server

            # Setup new server creation
            mock_new_server = Mock()
            mock_lean_server.return_value = mock_new_server

            # Act - should not raise exception
            manager.restart_server("/path/to/file.lean")

            # Assert - new server created despite kill failure
            assert manager._servers[cache_key] == mock_new_server

    def test_get_server_reuses_alive_server(self):
        """
        Test that get_server reuses an alive server instance.

        Requirements: 11.1
        """
        # Patch to avoid real server creation
        with (
            patch("lean_proof_auto_mcp.lean.server_manager.LeanServer"),
            patch("lean_proof_auto_mcp.lean.server_manager.LeanREPLConfig"),
        ):
            # Arrange — use workspace_path so cache key is predictable
            manager = LeanInteractServerManager(workspace_path=Path("/path/to"))

            # Create a mock alive server keyed by project root
            cache_key = str(Path("/path/to"))
            mock_server = Mock()
            mock_server.run = Mock()  # Has run method
            mock_server.kill = Mock()  # Has kill method
            manager._servers[cache_key] = mock_server

            # Act
            result = manager.get_server("/path/to/file.lean")

            # Assert
            assert result == mock_server

    def test_get_server_recreates_dead_server(self):
        """
        Test that get_server recreates a dead server instance.

        Requirements: 11.1
        """
        # Arrange — use workspace_path so cache key is predictable
        manager = LeanInteractServerManager(workspace_path=Path("/path/to"))

        # Create a mock dead server (missing run method) keyed by project root
        cache_key = str(Path("/path/to"))
        mock_dead_server = Mock(spec=[])  # Empty spec means no methods
        manager._servers[cache_key] = mock_dead_server

        # Patch LeanServer and LeanREPLConfig to create new server
        with (
            patch("lean_proof_auto_mcp.lean.server_manager.LeanServer") as mock_lean_server,
            patch("lean_proof_auto_mcp.lean.server_manager.LeanREPLConfig"),
        ):
            mock_new_server = Mock()
            mock_new_server.run = Mock()
            mock_new_server.kill = Mock()
            mock_lean_server.return_value = mock_new_server

            # Act
            result = manager.get_server("/path/to/file.lean")

        # Assert
        assert result == mock_new_server
        assert manager._servers[cache_key] == mock_new_server

    def test_shutdown_all_with_kill_failures(self):
        """
        Test shutdown_all continues even when some servers fail to kill.

        Requirements: 11.1
        """
        # Patch to avoid real server creation
        with (
            patch("lean_proof_auto_mcp.lean.server_manager.LeanServer"),
            patch("lean_proof_auto_mcp.lean.server_manager.LeanREPLConfig"),
        ):
            # Arrange
            manager = LeanInteractServerManager()

            # Create multiple mock servers, some fail to kill
            mock_server1 = Mock()
            mock_server1.kill.side_effect = RuntimeError("Kill failed")

            mock_server2 = Mock()
            mock_server2.kill = Mock()  # Succeeds

            mock_server3 = Mock()
            mock_server3.kill.side_effect = RuntimeError("Kill failed")

            manager._servers["/path/to/file1.lean"] = mock_server1
            manager._servers["/path/to/file2.lean"] = mock_server2
            manager._servers["/path/to/file3.lean"] = mock_server3

            # Act - should not raise exception
            manager.shutdown_all()

            # Assert - all servers removed despite failures
            assert len(manager._servers) == 0
            mock_server1.kill.assert_called_once()
            mock_server2.kill.assert_called_once()
            mock_server3.kill.assert_called_once()

    def test_create_server_with_invalid_workspace(self):
        """
        Test creating server with invalid workspace path.

        Requirements: 11.3
        """
        # Arrange
        from pathlib import Path

        # Patch before creating manager
        with (
            patch("lean_proof_auto_mcp.lean.server_manager.LeanServer") as mock_lean_server,
            patch("lean_proof_auto_mcp.lean.server_manager.LeanREPLConfig"),
        ):
            mock_server = Mock()
            mock_lean_server.return_value = mock_server

            manager = LeanInteractServerManager(workspace_path=Path("/nonexistent/path"))

            # Act
            result = manager.get_server("/path/to/file.lean")

            # Assert - should create standalone server
            assert result == mock_server

    def test_is_server_alive_with_is_alive_method(self):
        """
        Test _is_server_alive delegates to server.is_alive() when available.

        LeanInteract's LeanServer exposes is_alive() which checks the
        underlying subprocess (_proc.poll()). After a timeout kills the
        REPL, is_alive() returns False, triggering server recreation.

        Requirements: 11.1
        """
        with (
            patch("lean_proof_auto_mcp.lean.server_manager.LeanServer"),
            patch("lean_proof_auto_mcp.lean.server_manager.LeanREPLConfig"),
        ):
            manager = LeanInteractServerManager()

            # Server with is_alive() returning True (process running)
            alive_server = Mock()
            alive_server.is_alive.return_value = True
            assert manager._is_server_alive(alive_server) is True

            # Server with is_alive() returning False (process dead after timeout)
            dead_server = Mock()
            dead_server.is_alive.return_value = False
            assert manager._is_server_alive(dead_server) is False

    def test_is_server_alive_fallback_without_is_alive(self):
        """
        Test _is_server_alive falls back to structural checks for non-LeanInteract servers.

        Test doubles or alternative implementations that lack is_alive()
        are checked via hasattr(server, "run") and hasattr(server, "kill").

        Requirements: 11.1
        """
        with (
            patch("lean_proof_auto_mcp.lean.server_manager.LeanServer"),
            patch("lean_proof_auto_mcp.lean.server_manager.LeanREPLConfig"),
        ):
            manager = LeanInteractServerManager()

            # Server missing is_alive and run → dead
            mock_server1 = Mock(spec=["kill"])
            assert manager._is_server_alive(mock_server1) is False

            # Server missing is_alive and kill → dead
            mock_server2 = Mock(spec=["run"])
            assert manager._is_server_alive(mock_server2) is False

            # Server missing is_alive but has run + kill → alive (fallback)
            mock_server3 = Mock(spec=["run", "kill"])
            assert manager._is_server_alive(mock_server3) is True

    def test_is_server_alive_with_exception(self):
        """
        Test _is_server_alive handles exceptions gracefully.

        Requirements: 11.1
        """
        with (
            patch("lean_proof_auto_mcp.lean.server_manager.LeanServer"),
            patch("lean_proof_auto_mcp.lean.server_manager.LeanREPLConfig"),
        ):
            manager = LeanInteractServerManager()

            # Server whose is_alive() raises → treated as dead
            broken_server = Mock()
            broken_server.is_alive.side_effect = RuntimeError("process check failed")
            assert manager._is_server_alive(broken_server) is False

            # Server with no methods at all → dead
            mock_server_no_methods = Mock(spec=[])
            assert manager._is_server_alive(mock_server_no_methods) is False
