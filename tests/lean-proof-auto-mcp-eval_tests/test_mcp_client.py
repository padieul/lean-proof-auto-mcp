"""Unit tests for MCP Client.

This module tests the MCPClient class in isolation using mocked subprocess
to verify lifecycle management, tool calling, and error handling without
requiring a real MCP server.
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from mcp_client import MCPClient


class TestMCPClientLifecycle:
    """Test MCP client lifecycle management."""
    
    def test_enter_starts_process(self):
        """Test that __enter__ starts the MCP server process."""
        with patch("mcp_client.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_popen.return_value = mock_process
            
            server_path = Path("/fake/server.py")
            working_dir = Path("/fake/workdir")
            
            client = MCPClient(server_path, working_dir)
            result = client.__enter__()
            
            # Verify process was started with correct command
            assert mock_popen.call_count == 1
            call_args = mock_popen.call_args
            
            # Check that python -m lean_proof_auto_mcp.server was called
            assert call_args[0][0] == ["python", "-m", "lean_proof_auto_mcp.server"]
            assert call_args[1]["stdin"] == subprocess.PIPE
            assert call_args[1]["stdout"] == subprocess.PIPE
            assert call_args[1]["stderr"] == subprocess.PIPE
            assert call_args[1]["text"] is True
            assert "env" in call_args[1]  # PYTHONPATH should be set
            assert call_args[1]["cwd"] == str(working_dir)
            
            # Verify client returned self
            assert result is client
            
            # Verify process stored
            assert client._process is mock_process
    
    def test_exit_terminates_process(self):
        """Test that __exit__ terminates the process gracefully."""
        with patch("mcp_client.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.wait = MagicMock()
            mock_popen.return_value = mock_process
            
            server_path = Path("/fake/server.py")
            working_dir = Path("/fake/workdir")
            
            client = MCPClient(server_path, working_dir)
            client.__enter__()
            client.__exit__(None, None, None)
            
            # Verify terminate was called
            mock_process.terminate.assert_called_once()
            
            # Verify wait was called with timeout
            mock_process.wait.assert_called_once_with(timeout=5)
    
    def test_exit_kills_process_on_timeout(self):
        """Test that __exit__ kills process if terminate times out."""
        with patch("mcp_client.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.wait = MagicMock(side_effect=[
                subprocess.TimeoutExpired("cmd", 5),
                None
            ])
            mock_popen.return_value = mock_process
            
            server_path = Path("/fake/server.py")
            working_dir = Path("/fake/workdir")
            
            client = MCPClient(server_path, working_dir)
            client.__enter__()
            client.__exit__(None, None, None)
            
            # Verify terminate was called
            mock_process.terminate.assert_called_once()
            
            # Verify kill was called after timeout
            mock_process.kill.assert_called_once()
    
    def test_exit_handles_exceptions_gracefully(self):
        """Test that __exit__ handles exceptions during cleanup."""
        with patch("mcp_client.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.terminate = MagicMock(side_effect=Exception("terminate failed"))
            mock_process.kill = MagicMock()
            mock_popen.return_value = mock_process
            
            server_path = Path("/fake/server.py")
            working_dir = Path("/fake/workdir")
            
            client = MCPClient(server_path, working_dir)
            client.__enter__()
            
            # Should not raise exception
            client.__exit__(None, None, None)
            
            # Verify kill was attempted
            mock_process.kill.assert_called_once()
    
    def test_context_manager_protocol(self):
        """Test that client works as context manager."""
        with patch("mcp_client.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_popen.return_value = mock_process
            
            server_path = Path("/fake/server.py")
            working_dir = Path("/fake/workdir")
            
            with MCPClient(server_path, working_dir) as client:
                assert client._process is mock_process
            
            # Verify cleanup happened
            mock_process.terminate.assert_called_once()



class TestMCPClientCallTool:
    """Test MCP client tool calling functionality."""
    
    def test_call_tool_success(self):
        """Test successful tool call."""
        with patch("mcp_client.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_stdin = MagicMock()
            mock_stdout = MagicMock()
            
            # Mock successful response
            response_data = {"jsonrpc": "2.0", "id": 1, "result": {"status": "success"}}
            mock_stdout.readline = MagicMock(return_value=json.dumps(response_data) + "\n")
            
            mock_process.stdin = mock_stdin
            mock_process.stdout = mock_stdout
            mock_process.stderr = MagicMock()
            mock_process.poll = MagicMock(return_value=None)  # Process is alive
            
            mock_popen.return_value = mock_process
            
            server_path = Path("/fake/server.py")
            working_dir = Path("/fake/workdir")
            
            with MCPClient(server_path, working_dir, timeout=5.0) as client:
                result = client.call_tool("verify", {"file_path": "test.lean"})
            
            # Verify request was sent
            assert mock_stdin.write.called
            assert mock_stdin.flush.called
            
            # Verify response was parsed correctly
            assert result == response_data
    
    def test_call_tool_timeout(self):
        """Test that timeout raises TimeoutError."""
        with patch("mcp_client.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_stdin = MagicMock()
            mock_stdout = MagicMock()
            
            # Mock slow response (readline blocks)
            import time
            def slow_readline():
                time.sleep(10)  # Longer than timeout
                return '{"result": "too late"}\n'
            
            mock_stdout.readline = slow_readline
            
            mock_process.stdin = mock_stdin
            mock_process.stdout = mock_stdout
            mock_process.stderr = MagicMock()
            mock_process.poll = MagicMock(return_value=None)
            
            mock_popen.return_value = mock_process
            
            server_path = Path("/fake/server.py")
            working_dir = Path("/fake/workdir")
            
            with MCPClient(server_path, working_dir, timeout=0.1) as client:
                with pytest.raises(TimeoutError) as exc_info:
                    client.call_tool("verify", {"file_path": "test.lean"})
                
                assert "timed out" in str(exc_info.value).lower()
    
    def test_call_tool_malformed_json(self):
        """Test that malformed JSON raises ValueError."""
        with patch("mcp_client.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_stdin = MagicMock()
            mock_stdout = MagicMock()
            
            # Mock malformed JSON response
            mock_stdout.readline = MagicMock(return_value="not valid json\n")
            
            mock_process.stdin = mock_stdin
            mock_process.stdout = mock_stdout
            mock_process.stderr = MagicMock()
            mock_process.poll = MagicMock(return_value=None)
            
            mock_popen.return_value = mock_process
            
            server_path = Path("/fake/server.py")
            working_dir = Path("/fake/workdir")
            
            with MCPClient(server_path, working_dir, timeout=5.0) as client:
                with pytest.raises(ValueError) as exc_info:
                    client.call_tool("verify", {"file_path": "test.lean"})
                
                assert "malformed json" in str(exc_info.value).lower()
    
    def test_call_tool_dead_process(self):
        """Test that dead process raises RuntimeError."""
        with patch("mcp_client.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_stderr = MagicMock()
            mock_stderr.read = MagicMock(return_value="Server crashed!")
            
            mock_process.stdin = MagicMock()
            mock_process.stdout = MagicMock()
            mock_process.stderr = mock_stderr
            mock_process.poll = MagicMock(return_value=1)  # Process terminated
            
            mock_popen.return_value = mock_process
            
            server_path = Path("/fake/server.py")
            working_dir = Path("/fake/workdir")
            
            with MCPClient(server_path, working_dir, timeout=5.0) as client:
                with pytest.raises(RuntimeError) as exc_info:
                    client.call_tool("verify", {"file_path": "test.lean"})
                
                assert "terminated" in str(exc_info.value).lower()
    
    def test_call_tool_increments_request_id(self):
        """Test that request IDs increment for each call."""
        with patch("mcp_client.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_stdin = MagicMock()
            mock_stdout = MagicMock()
            
            # Track written requests
            written_requests = []
            
            def capture_write(data):
                written_requests.append(data)
            
            mock_stdin.write = capture_write
            
            # Mock responses
            response1 = {"jsonrpc": "2.0", "id": 1, "result": {}}
            response2 = {"jsonrpc": "2.0", "id": 2, "result": {}}
            mock_stdout.readline = MagicMock(side_effect=[
                json.dumps(response1) + "\n",
                json.dumps(response2) + "\n",
            ])
            
            mock_process.stdin = mock_stdin
            mock_process.stdout = mock_stdout
            mock_process.stderr = MagicMock()
            mock_process.poll = MagicMock(return_value=None)
            
            mock_popen.return_value = mock_process
            
            server_path = Path("/fake/server.py")
            working_dir = Path("/fake/workdir")
            
            with MCPClient(server_path, working_dir, timeout=5.0) as client:
                client.call_tool("verify", {"file_path": "test1.lean"})
                client.call_tool("verify", {"file_path": "test2.lean"})
            
            # Verify request IDs incremented
            assert len(written_requests) == 2
            req1 = json.loads(written_requests[0].strip())
            req2 = json.loads(written_requests[1].strip())
            
            assert req1["id"] == 1
            assert req2["id"] == 2



class TestMCPClientIntegration:
    """Integration tests with real MCP server.
    
    These tests require the actual MCP server and eval repository to be available.
    They are marked with pytest.mark.integration and can be skipped in CI.
    """
    
    @pytest.mark.integration
    def test_full_lifecycle_with_real_server(self):
        """Test full lifecycle with actual MCP server."""
        # Import fixtures module to get eval repo path
        try:
            from fixtures import get_eval_repo_path
            eval_repo_path = get_eval_repo_path()
        except (ImportError, FileNotFoundError) as e:
            pytest.skip(f"Eval repository not available: {e}")
        
        # Get server path relative to this test file
        server_path = Path(__file__).parent.parent.parent / "src" / "lean_proof_auto_mcp" / "server.py"
        
        if not server_path.exists():
            pytest.skip(f"MCP server not found at {server_path}")
        
        # Test full lifecycle
        with MCPClient(server_path, eval_repo_path, timeout=10.0) as client:
            # Verify client is initialized
            assert client._process is not None
            assert client._process.poll() is None  # Process is running
        
        # After context exit, process should be terminated
        # Note: We can't check the process directly as it's been cleaned up
    
    @pytest.mark.integration
    def test_tool_calls_return_valid_responses(self):
        """Test that tool calls return valid JSON-RPC responses."""
        # Import fixtures module to get eval repo path
        try:
            from fixtures import get_eval_repo_path, ALL_FIXTURE_FILES
            eval_repo_path = get_eval_repo_path()
        except (ImportError, FileNotFoundError) as e:
            pytest.skip(f"Eval repository not available: {e}")
        
        if not ALL_FIXTURE_FILES:
            pytest.skip("No fixture files available for testing")
        
        # Get server path
        server_path = Path(__file__).parent.parent.parent / "src" / "lean_proof_auto_mcp" / "server.py"
        
        if not server_path.exists():
            pytest.skip(f"MCP server not found at {server_path}")
        
        # Test tool calls with real server
        with MCPClient(server_path, eval_repo_path, timeout=30.0) as client:
            # Use first fixture file for testing
            fixture = ALL_FIXTURE_FILES[0]
            
            # Test verify tool with proper MCP protocol and correct parameter names
            try:
                response = client.call_tool("verify", {
                    "file": str(fixture.path),
                })
                
                # Verify response structure
                assert isinstance(response, dict)
                assert "jsonrpc" in response
                assert response["jsonrpc"] == "2.0"
                assert "id" in response
                
                # Response should have either "result" or "error"
                assert "result" in response or "error" in response
                
                # If we got a result, that's great!
                # If we got an error, that's also fine - we're just testing communication
                
            except (TimeoutError, ValueError, RuntimeError) as e:
                # These exceptions indicate communication issues
                pytest.fail(f"Server communication failed: {e}")


class TestMCPClientHealthCheck:
    """Test health check functionality."""
    
    def test_health_check_returns_true_on_success(self):
        """Test that health_check returns True when server responds."""
        with patch("mcp_client.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_stdin = MagicMock()
            mock_stdout = MagicMock()
            
            # Mock successful ping response
            response_data = {"jsonrpc": "2.0", "id": 1, "result": {"status": "ok"}}
            mock_stdout.readline = MagicMock(return_value=json.dumps(response_data) + "\n")
            
            mock_process.stdin = mock_stdin
            mock_process.stdout = mock_stdout
            mock_process.stderr = MagicMock()
            mock_process.poll = MagicMock(return_value=None)
            
            mock_popen.return_value = mock_process
            
            server_path = Path("/fake/server.py")
            working_dir = Path("/fake/workdir")
            
            with MCPClient(server_path, working_dir) as client:
                result = client.health_check()
            
            assert result is True
    
    def test_health_check_returns_false_on_failure(self):
        """Test that health_check returns False when server fails."""
        with patch("mcp_client.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.stdin = MagicMock()
            mock_process.stdout = MagicMock()
            mock_process.stderr = MagicMock()
            mock_process.poll = MagicMock(return_value=1)  # Dead process
            
            mock_popen.return_value = mock_process
            
            server_path = Path("/fake/server.py")
            working_dir = Path("/fake/workdir")
            
            with MCPClient(server_path, working_dir) as client:
                result = client.health_check()
            
            assert result is False


class TestMCPClientRestart:
    """Test restart functionality."""
    
    def test_restart_terminates_and_starts_new_process(self):
        """Test that restart terminates old process and starts new one."""
        with patch("mcp_client.subprocess.Popen") as mock_popen:
            mock_process1 = MagicMock()
            mock_process2 = MagicMock()
            
            # First call returns process1, second call returns process2
            mock_popen.side_effect = [mock_process1, mock_process2]
            
            server_path = Path("/fake/server.py")
            working_dir = Path("/fake/workdir")
            
            with MCPClient(server_path, working_dir) as client:
                assert client._process is mock_process1
                
                # Restart
                client.restart()
                
                # Verify old process was terminated
                mock_process1.terminate.assert_called()
                
                # Verify new process was started
                assert client._process is mock_process2
                assert mock_popen.call_count == 2
