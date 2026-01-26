"""
Unit tests for LeanInteractRunner adapter.

These tests verify specific examples, edge cases, and error conditions
for the LeanInteract adapter implementation.

Requirements: 2.3, 1.4, 5.1, 5.2, 5.3
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from lean_proof_auto_mcp.adapters.lean_interact_runner import LeanInteractRunner
from lean_proof_auto_mcp.core.verify_domain import LeanRunResult


class TestTheoremNotFoundHandling:
    """
    Test theorem not found error handling.
    
    Requirements: 2.3
    """
    
    def test_invalid_theorem_id_raises_value_error(self, tmp_path):
        """Test that invalid theorem_id raises ValueError."""
        # Arrange
        runner = LeanInteractRunner()
        
        # Create a test file
        test_file = tmp_path / "test.lean"
        test_file.write_text("theorem test_theorem : True := trivial\n")
        
        # Act & Assert
        with pytest.raises(ValueError, match="Theorem not found"):
            runner.verify_file(
                workspace_path=tmp_path,
                file_path="test.lean",
                theorem_id="nonexistent_theorem",
                budget_s=30.0,
            )
    
    def test_theorem_not_found_with_helpful_message(self, tmp_path):
        """Test that theorem not found error includes helpful message."""
        # Arrange
        runner = LeanInteractRunner()
        
        # Create a test file
        test_file = tmp_path / "test.lean"
        test_file.write_text("theorem test_theorem : True := trivial\n")
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            runner.verify_file(
                workspace_path=tmp_path,
                file_path="test.lean",
                theorem_id="invalid_theorem_id",
                budget_s=30.0,
            )
        
        assert "Theorem not found" in str(exc_info.value)
        assert "invalid_theorem_id" in str(exc_info.value)


class TestDiagnosticParsing:
    """
    Test diagnostic parsing from LeanInteract response.
    
    Requirements: 1.4, 5.1, 5.2, 5.3
    """
    
    def test_parse_error_messages(self):
        """Test parsing error messages from LeanInteract response."""
        # Arrange
        runner = LeanInteractRunner()
        
        # Create mock response with error message
        mock_response = Mock()
        mock_message = Mock()
        mock_message.severity = "error"
        mock_message.data = "type mismatch"
        mock_message.start_pos = Mock(line=10, column=5)
        mock_message.end_pos = Mock(line=10, column=15)
        mock_response.messages = [mock_message]
        mock_response.sorries = []
        
        # Act
        diagnostics = runner._parse_diagnostics(mock_response)
        
        # Assert
        assert len(diagnostics) == 1
        assert diagnostics[0]["severity"] == "error"
        assert diagnostics[0]["message"] == "type mismatch"
        assert diagnostics[0]["location"]["line"] == 10
        assert diagnostics[0]["location"]["col"] == 5
        assert diagnostics[0]["location"]["end_line"] == 10
        assert diagnostics[0]["location"]["end_col"] == 15
    
    def test_parse_warning_messages(self):
        """Test parsing warning messages from LeanInteract response."""
        # Arrange
        runner = LeanInteractRunner()
        
        # Create mock response with warning message
        mock_response = Mock()
        mock_message = Mock()
        mock_message.severity = "warning"
        mock_message.data = "unused variable"
        mock_message.start_pos = Mock(line=5, column=2)
        mock_message.end_pos = Mock(line=5, column=10)
        mock_response.messages = [mock_message]
        mock_response.sorries = []
        
        # Act
        diagnostics = runner._parse_diagnostics(mock_response)
        
        # Assert
        assert len(diagnostics) == 1
        assert diagnostics[0]["severity"] == "warning"
        assert diagnostics[0]["message"] == "unused variable"
    
    def test_parse_sorry_proofs(self):
        """Test parsing sorry (incomplete proof) from LeanInteract response."""
        # Arrange
        runner = LeanInteractRunner()
        
        # Create mock response with sorry
        mock_response = Mock()
        mock_response.messages = []
        mock_sorry = Mock()
        mock_sorry.start_pos = Mock(line=15, column=10)
        mock_sorry.end_pos = Mock(line=15, column=15)
        mock_sorry.goal = "n : Nat\n⊢ n = 5 → n = 5"
        mock_response.sorries = [mock_sorry]
        
        # Act
        diagnostics = runner._parse_diagnostics(mock_response)
        
        # Assert
        assert len(diagnostics) == 1
        assert diagnostics[0]["severity"] == "warning"
        assert "Incomplete proof" in diagnostics[0]["message"]
        assert diagnostics[0]["location"]["line"] == 15
        assert diagnostics[0]["location"]["col"] == 10
    
    def test_parse_multiple_diagnostics(self):
        """Test parsing multiple diagnostics from LeanInteract response."""
        # Arrange
        runner = LeanInteractRunner()
        
        # Create mock response with multiple messages and sorries
        mock_response = Mock()
        
        mock_error = Mock()
        mock_error.severity = "error"
        mock_error.data = "type error"
        mock_error.start_pos = Mock(line=10, column=5)
        mock_error.end_pos = Mock(line=10, column=15)
        
        mock_warning = Mock()
        mock_warning.severity = "warning"
        mock_warning.data = "unused variable"
        mock_warning.start_pos = Mock(line=5, column=2)
        mock_warning.end_pos = Mock(line=5, column=10)
        
        mock_response.messages = [mock_error, mock_warning]
        
        mock_sorry = Mock()
        mock_sorry.start_pos = Mock(line=20, column=10)
        mock_sorry.end_pos = Mock(line=20, column=15)
        mock_sorry.goal = "goal"
        mock_response.sorries = [mock_sorry]
        
        # Act
        diagnostics = runner._parse_diagnostics(mock_response)
        
        # Assert
        assert len(diagnostics) == 3
        assert diagnostics[0]["severity"] == "error"
        assert diagnostics[1]["severity"] == "warning"
        assert diagnostics[2]["severity"] == "warning"
    
    def test_normalize_severity_values(self):
        """Test that severity values are normalized correctly."""
        # Arrange
        runner = LeanInteractRunner()
        
        # Act & Assert
        assert runner._normalize_severity("error") == "error"
        assert runner._normalize_severity("ERROR") == "error"
        assert runner._normalize_severity("warning") == "warning"
        assert runner._normalize_severity("WARNING") == "warning"
        assert runner._normalize_severity("warn") == "warning"
        assert runner._normalize_severity("info") == "info"
        assert runner._normalize_severity("INFO") == "info"
        assert runner._normalize_severity("unknown") == "info"


class TestProcessCleanup:
    """
    Test process cleanup guarantees.
    
    Requirements: 4.4
    """
    
    @patch('lean_proof_auto_mcp.adapters.lean_interact_runner.LeanServer', create=True)
    def test_server_close_called_on_success(self, mock_lean_server_class, tmp_path):
        """Test that server.close() is called on successful verification."""
        # Skip this test if LeanInteract is not installed
        pytest.importorskip("lean_interact")
        
        # Arrange
        runner = LeanInteractRunner()
        
        # Create test file
        test_file = tmp_path / "test.lean"
        test_file.write_text("theorem test : True := trivial\n")
        
        # Setup mock
        mock_server = MagicMock()
        mock_response = Mock()
        mock_response.messages = []
        mock_response.sorries = []
        mock_server.run_file.return_value = mock_response
        mock_lean_server_class.return_value = mock_server
        
        # Act
        runner.verify_file(
            workspace_path=tmp_path,
            file_path="test.lean",
            theorem_id=None,
            budget_s=30.0,
        )
        
        # Assert
        mock_server.close.assert_called_once()
    
    @patch('lean_proof_auto_mcp.adapters.lean_interact_runner.LeanServer', create=True)
    def test_server_close_called_on_timeout(self, mock_lean_server_class, tmp_path):
        """Test that server.close() is called even on timeout."""
        # Skip this test if LeanInteract is not installed
        pytest.importorskip("lean_interact")
        
        # Arrange
        runner = LeanInteractRunner()
        
        # Create test file
        test_file = tmp_path / "test.lean"
        test_file.write_text("theorem test : True := trivial\n")
        
        # Setup mock to raise TimeoutError
        mock_server = MagicMock()
        mock_server.run_file.side_effect = TimeoutError("Timeout")
        mock_lean_server_class.return_value = mock_server
        
        # Act
        result = runner.verify_file(
            workspace_path=tmp_path,
            file_path="test.lean",
            theorem_id=None,
            budget_s=30.0,
        )
        
        # Assert
        assert result.status == "timeout"
        mock_server.close.assert_called_once()
    
    @patch('lean_proof_auto_mcp.adapters.lean_interact_runner.LeanServer', create=True)
    def test_server_close_called_on_exception(self, mock_lean_server_class, tmp_path):
        """Test that server.close() is called even on unexpected exception."""
        # Skip this test if LeanInteract is not installed
        pytest.importorskip("lean_interact")
        
        # Arrange
        runner = LeanInteractRunner()
        
        # Create test file
        test_file = tmp_path / "test.lean"
        test_file.write_text("theorem test : True := trivial\n")
        
        # Setup mock to raise exception
        mock_server = MagicMock()
        mock_server.run_file.side_effect = RuntimeError("Unexpected error")
        mock_lean_server_class.return_value = mock_server
        
        # Act & Assert
        with pytest.raises(RuntimeError):
            runner.verify_file(
                workspace_path=tmp_path,
                file_path="test.lean",
                theorem_id=None,
                budget_s=30.0,
            )
        
        # Assert cleanup happened
        mock_server.close.assert_called_once()
