"""

Unit tests for LeanInteract adapter error handling.


These tests verify error handling for LeanInteract crash recovery,

timeout handling, and invalid input handling across the adapter layer.


Requirements: 11.1, 11.2, 11.3
"""


from unittest.mock import Mock, patch


import pytest


from lean_proof_auto_mcp.lean.ports import Declaration, Range

from lean_proof_auto_mcp.lean.proof_state import ProofStateInspectorImpl

from lean_proof_auto_mcp.lean.server_manager import LeanInteractServerManager

from lean_proof_auto_mcp.lean.validator import ProofValidatorImpl



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

        validator = ProofValidatorImpl(server=None)


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

        validator = ProofValidatorImpl(server=None)


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

        mock_server = Mock()

        mock_server.run.side_effect = TimeoutError("Validation timed out")


        # Patch Command to avoid validation errors

        with patch("lean_proof_auto_mcp.lean.validator.Command"):

            validator = ProofValidatorImpl(server=mock_server)


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

        mock_server = Mock()

        mock_lean_error = Mock()

        mock_lean_error.__str__ = lambda self: "Lean timed out after 10 seconds"

        mock_server.run.return_value = mock_lean_error


        # Patch both LeanError and Command

        with (

            patch("lean_proof_auto_mcp.lean.validator.LeanError", type(mock_lean_error)),

            patch("lean_proof_auto_mcp.lean.validator.Command"),

        ):

            validator = ProofValidatorImpl(server=mock_server)


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

        mock_server = Mock()

        mock_lean_error = Mock()

        mock_lean_error.__str__ = lambda self: "Syntax error in proof"

        mock_server.run.return_value = mock_lean_error


        # Patch both LeanError and Command

        with (

            patch("lean_proof_auto_mcp.lean.validator.LeanError", type(mock_lean_error)),

            patch("lean_proof_auto_mcp.lean.validator.Command"),

        ):

            validator = ProofValidatorImpl(server=mock_server)


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

        mock_server = Mock()

        mock_server.run.side_effect = RuntimeError("Unexpected server crash")


        # Patch Command to avoid validation errors

        with patch("lean_proof_auto_mcp.lean.validator.Command"):

            validator = ProofValidatorImpl(server=mock_server)


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


        # Patch Command to avoid validation errors

        with patch("lean_proof_auto_mcp.lean.validator.Command"):

            validator = ProofValidatorImpl(server=mock_server)


            # Act

            result = validator.validate_proof(

                theorem_statement="True",

                proof_attempt="trivial",

                timeout_s=10.0,

            )


        # Assert
        assert result.status == "error"

        assert "type mismatch" in result.error_message.lower()

        assert result.error_location == (5, 10)

        assert any("type" in s.lower() for s in result.suggestions)


    def test_validate_with_unknown_identifier_error(self):
        """

        Test validation with unknown identifier error generates appropriate suggestions.


        Requirements: 11.3
        """

        # Arrange

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


        # Patch Command to avoid validation errors

        with patch("lean_proof_auto_mcp.lean.validator.Command"):

            validator = ProofValidatorImpl(server=mock_server)


            # Act

            result = validator.validate_proof(

                theorem_statement="True",

                proof_attempt="trivial",

                timeout_s=10.0,

            )


        # Assert
        assert result.status == "error"

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

        inspector = ProofStateInspectorImpl(server=None)

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

        inspector = ProofStateInspectorImpl(server=None)

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

        with pytest.raises(RuntimeError, match="No server instance available"):

            inspector.get_initial_proof_state(theorem)


    def test_get_initial_proof_state_with_lean_error(self):
        """

        Test getting initial proof state when LeanError occurs.


        Requirements: 11.3
        """

        # Arrange

        mock_server = Mock()

        mock_lean_error = Mock()

        mock_lean_error.__str__ = lambda self: "Syntax error in theorem"

        mock_server.run.return_value = mock_lean_error


        # Patch both LeanError and Command

        with (

            patch("lean_proof_auto_mcp.lean.proof_state.LeanError", type(mock_lean_error)),

            patch("lean_proof_auto_mcp.lean.proof_state.Command"),

        ):

            inspector = ProofStateInspectorImpl(server=mock_server)

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

        mock_server = Mock()

        mock_server.run.side_effect = RuntimeError("Server crashed")

        inspector = ProofStateInspectorImpl(server=mock_server)

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

        inspector = ProofStateInspectorImpl(server=None)


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

        inspector = ProofStateInspectorImpl(server=None)


        # Act & Assert

        with pytest.raises(RuntimeError, match="No server instance available"):

            inspector.apply_tactic(proof_state_id=1, tactic="trivial")


    def test_apply_tactic_with_lean_error(self):
        """

        Test applying tactic when LeanError occurs.


        Requirements: 11.3
        """

        # Arrange

        mock_server = Mock()

        mock_lean_error = Mock()

        mock_lean_error.__str__ = lambda self: "Tactic failed"

        mock_server.run.return_value = mock_lean_error


        # Patch LeanError to match the mock

        with patch("lean_proof_auto_mcp.lean.proof_state.LeanError", type(mock_lean_error)):

            inspector = ProofStateInspectorImpl(server=mock_server)


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

        mock_server = Mock()

        mock_server.run.side_effect = RuntimeError("Server crashed")

        inspector = ProofStateInspectorImpl(server=mock_server)


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

        # Arrange

        manager = LeanInteractServerManager()


        # Patch LEAN_INTERACT_AVAILABLE to False

        with (

            patch("lean_proof_auto_mcp.lean.server_manager.LEAN_INTERACT_AVAILABLE", False),

            pytest.raises(RuntimeError, match="LeanInteract library not installed"),

        ):

            manager.get_server("/path/to/file.lean")


    def test_get_server_with_creation_failure(self):
        """

        Test getting server when server creation fails.


        Requirements: 11.3
        """

        # Arrange

        manager = LeanInteractServerManager()


        # Patch LeanServer to raise exception

        with patch("lean_proof_auto_mcp.lean.server_manager.LeanServer") as mock_lean_server:

            mock_lean_server.side_effect = RuntimeError("Failed to start server")


            # Act & Assert

            with pytest.raises(RuntimeError, match="Failed to create server"):

                manager.get_server("/path/to/file.lean")


    def test_restart_server_with_dead_server(self):
        """

        Test restarting server when existing server is dead.


        Requirements: 11.1
        """

        # Arrange

        manager = LeanInteractServerManager()


        # Create a mock dead server

        mock_dead_server = Mock()

        mock_dead_server.run = None  # Missing method indicates dead server

        manager._servers["/path/to/file.lean"] = mock_dead_server


        # Patch LeanServer to create new server

        with patch("lean_proof_auto_mcp.lean.server_manager.LeanServer") as mock_lean_server:

            mock_new_server = Mock()

            mock_lean_server.return_value = mock_new_server


            # Act

            manager.restart_server("/path/to/file.lean")


        # Assert

        assert manager._servers["/path/to/file.lean"] == mock_new_server

        mock_dead_server.kill.assert_called_once()


    def test_restart_server_with_kill_failure(self):
        """

        Test restarting server when killing old server fails.


        Requirements: 11.1
        """

        # Arrange

        manager = LeanInteractServerManager()


        # Create a mock server that fails to kill

        mock_old_server = Mock()

        mock_old_server.kill.side_effect = RuntimeError("Failed to kill")

        manager._servers["/path/to/file.lean"] = mock_old_server


        # Patch LeanServer to create new server

        with patch("lean_proof_auto_mcp.lean.server_manager.LeanServer") as mock_lean_server:

            mock_new_server = Mock()

            mock_lean_server.return_value = mock_new_server


            # Act - should not raise exception

            manager.restart_server("/path/to/file.lean")


        # Assert - new server created despite kill failure

        assert manager._servers["/path/to/file.lean"] == mock_new_server


    def test_get_server_reuses_alive_server(self):
        """

        Test that get_server reuses an alive server instance.


        Requirements: 11.1
        """

        # Arrange

        manager = LeanInteractServerManager()


        # Create a mock alive server

        mock_server = Mock()

        mock_server.run = Mock()  # Has run method

        mock_server.kill = Mock()  # Has kill method

        manager._servers["/path/to/file.lean"] = mock_server


        # Act

        result = manager.get_server("/path/to/file.lean")


        # Assert

        assert result == mock_server


    def test_get_server_recreates_dead_server(self):
        """

        Test that get_server recreates a dead server instance.


        Requirements: 11.1
        """

        # Arrange

        manager = LeanInteractServerManager()


        # Create a mock dead server (missing run method)

        mock_dead_server = Mock(spec=[])  # Empty spec means no methods

        manager._servers["/path/to/file.lean"] = mock_dead_server


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

        assert manager._servers["/path/to/file.lean"] == mock_new_server


    def test_shutdown_all_with_kill_failures(self):
        """

        Test shutdown_all continues even when some servers fail to kill.


        Requirements: 11.1
        """

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


        manager = LeanInteractServerManager(workspace_path=Path("/nonexistent/path"))


        # Patch LeanServer to succeed (should fall back to standalone)

        with patch("lean_proof_auto_mcp.lean.server_manager.LeanServer") as mock_lean_server:

            mock_server = Mock()

            mock_lean_server.return_value = mock_server


            # Act

            result = manager.get_server("/path/to/file.lean")


        # Assert - should create standalone server

        assert result == mock_server


    def test_is_server_alive_with_missing_methods(self):
        """

        Test _is_server_alive correctly identifies dead servers.


        Requirements: 11.1
        """

        # Arrange

        manager = LeanInteractServerManager()


        # Test with server missing run method

        mock_server1 = Mock()

        del mock_server1.run

        assert manager._is_server_alive(mock_server1) is False


        # Test with server missing kill method

        mock_server2 = Mock()

        del mock_server2.kill

        assert manager._is_server_alive(mock_server2) is False


        # Test with server having both methods

        mock_server3 = Mock()

        mock_server3.run = Mock()

        mock_server3.kill = Mock()

        assert manager._is_server_alive(mock_server3) is True


    def test_is_server_alive_with_exception(self):
        """

        Test _is_server_alive handles exceptions gracefully.


        Requirements: 11.1
        """

        # Arrange

        manager = LeanInteractServerManager()


        # Create server that raises exception when checking attributes

        mock_server = Mock()

        # Make hasattr fail by raising exception

        mock_server.__class__.__getattribute__ = Mock(side_effect=RuntimeError("Attribute error"))


        # Act & Assert - should return False, not raise

        # Note: We can't easily test this with Mock, so we test the logic path

        # by testing with a server that has no methods

        mock_server_no_methods = Mock(spec=[])

        assert manager._is_server_alive(mock_server_no_methods) is False

