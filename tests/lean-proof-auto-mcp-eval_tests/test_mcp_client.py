"""Unit tests for MCP Client.

Tests the MCPClient class in isolation using mocked subprocess to verify
lifecycle management, tool calling, and error handling without requiring
a real MCP server.

Integration tests at the bottom use the real server and log detailed
output to logs/test_mcp_client.log (append-only).
"""

import json
import subprocess
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mcp_client import MCPClient
from eval_logger import EvalLogger


def _make_jsonrpc_response(id: int, result: dict | None = None, error: dict | None = None) -> str:
    """Build a JSON-RPC response line."""
    resp: dict = {"jsonrpc": "2.0", "id": id}
    if error is not None:
        resp["error"] = error
    else:
        resp["result"] = result or {}
    return json.dumps(resp) + "\n"


def _mock_process_with_responses(*response_lines: str) -> MagicMock:
    """Create a mock Popen process that returns the given response lines in order."""
    mock_process = MagicMock()
    mock_process.stdin = MagicMock()
    mock_process.poll = MagicMock(return_value=None)

    mock_stdout = MagicMock()
    mock_stdout.readline = MagicMock(side_effect=list(response_lines))
    mock_process.stdout = mock_stdout

    # stderr.readline returns "" immediately so the drain thread exits
    mock_stderr = MagicMock()
    mock_stderr.readline = MagicMock(return_value="")
    mock_process.stderr = mock_stderr

    return mock_process


class TestMCPClientLifecycle:
    """Test MCP client lifecycle management."""

    def test_enter_starts_process_with_uv_run(self):
        """Test that __enter__ starts the server via 'uv run python -m ...'."""
        # initialize response + no extra reads needed
        init_response = _make_jsonrpc_response(1, {"protocolVersion": "2024-11-05"})
        mock_process = _mock_process_with_responses(init_response)

        with patch("mcp_client.subprocess.Popen", return_value=mock_process) as mock_popen:
            client = MCPClient(Path("/fake/server.py"), Path("/fake/workdir"))
            result = client.__enter__()

            call_args = mock_popen.call_args
            assert call_args[0][0] == ["uv", "run", "python", "-m", "lean_proof_auto_mcp.server"]
            assert call_args[1]["stdin"] == subprocess.PIPE
            assert call_args[1]["stdout"] == subprocess.PIPE
            assert call_args[1]["text"] is True
            assert call_args[1]["cwd"] == str(Path("/fake/workdir"))
            assert result is client
            assert client._initialized is True

            # Cleanup
            client.__exit__(None, None, None)

    def test_exit_terminates_process(self):
        """Test that __exit__ terminates the process gracefully."""
        init_response = _make_jsonrpc_response(1, {"protocolVersion": "2024-11-05"})
        mock_process = _mock_process_with_responses(init_response)

        with patch("mcp_client.subprocess.Popen", return_value=mock_process):
            client = MCPClient(Path("/fake/server.py"), Path("/fake/workdir"))
            client.__enter__()
            client.__exit__(None, None, None)

            mock_process.terminate.assert_called_once()
            mock_process.wait.assert_called_once_with(timeout=5)
            assert client._initialized is False

    def test_exit_kills_process_on_timeout(self):
        """Test that __exit__ kills process if terminate times out."""
        init_response = _make_jsonrpc_response(1, {"protocolVersion": "2024-11-05"})
        mock_process = _mock_process_with_responses(init_response)
        mock_process.wait = MagicMock(
            side_effect=[subprocess.TimeoutExpired("cmd", 5), None]
        )

        with patch("mcp_client.subprocess.Popen", return_value=mock_process):
            client = MCPClient(Path("/fake/server.py"), Path("/fake/workdir"))
            client.__enter__()
            client.__exit__(None, None, None)

            mock_process.terminate.assert_called_once()
            mock_process.kill.assert_called_once()

    def test_context_manager_protocol(self):
        """Test that client works as context manager."""
        init_response = _make_jsonrpc_response(1, {"protocolVersion": "2024-11-05"})
        mock_process = _mock_process_with_responses(init_response)

        with patch("mcp_client.subprocess.Popen", return_value=mock_process):
            with MCPClient(Path("/fake/server.py"), Path("/fake/workdir")) as client:
                assert client._process is mock_process
                assert client._initialized is True

            mock_process.terminate.assert_called_once()

    def test_enter_sends_initialize_handshake(self):
        """Test that __enter__ sends initialize request and initialized notification."""
        init_response = _make_jsonrpc_response(1, {"protocolVersion": "2024-11-05"})
        mock_process = _mock_process_with_responses(init_response)

        written_messages: list[str] = []
        mock_process.stdin.write = lambda data: written_messages.append(data)

        with patch("mcp_client.subprocess.Popen", return_value=mock_process):
            client = MCPClient(Path("/fake/server.py"), Path("/fake/workdir"))
            client.__enter__()

            # Should have sent 2 messages: initialize request + initialized notification
            assert len(written_messages) == 2

            init_req = json.loads(written_messages[0])
            assert init_req["method"] == "initialize"
            assert "protocolVersion" in init_req["params"]
            assert "clientInfo" in init_req["params"]

            init_notif = json.loads(written_messages[1])
            assert init_notif["method"] == "notifications/initialized"
            assert "id" not in init_notif  # notifications have no id

            client.__exit__(None, None, None)


class TestMCPClientCallTool:
    """Test MCP client tool calling functionality."""

    def _make_client_with_responses(self, *tool_responses: str):
        """Helper: create a client that's already initialized, with queued tool responses."""
        init_response = _make_jsonrpc_response(1, {"protocolVersion": "2024-11-05"})
        all_responses = [init_response] + list(tool_responses)
        mock_process = _mock_process_with_responses(*all_responses)
        return mock_process

    def test_call_tool_success(self):
        """Test successful tool call with correct parameter name."""
        tool_result = {
            "content": [
                {"type": "text", "text": json.dumps({
                    "api_version": "0.2.0",
                    "status": "success",
                    "run_id": "verify-test",
                    "file": "test.lean",
                })}
            ]
        }
        tool_response = _make_jsonrpc_response(2, tool_result)
        mock_process = self._make_client_with_responses(tool_response)

        with patch("mcp_client.subprocess.Popen", return_value=mock_process):
            with MCPClient(Path("/fake/server.py"), Path("/fake/workdir"), timeout=5.0) as client:
                result = client.call_tool("verify", {"file": "test.lean"})

        assert result["status"] == "success"
        assert result["api_version"] == "0.2.0"

    def test_call_tool_sends_correct_jsonrpc(self):
        """Test that call_tool sends properly formatted tools/call request."""
        tool_response = _make_jsonrpc_response(2, {"content": []})
        mock_process = self._make_client_with_responses(tool_response)

        written_messages: list[str] = []
        mock_process.stdin.write = lambda data: written_messages.append(data)

        with patch("mcp_client.subprocess.Popen", return_value=mock_process):
            with MCPClient(Path("/fake/server.py"), Path("/fake/workdir"), timeout=5.0) as client:
                client.call_tool("verify", {"file": "test.lean"})

        # Message 0 = initialize, 1 = initialized notification, 2 = tool call
        tool_req = json.loads(written_messages[2])
        assert tool_req["method"] == "tools/call"
        assert tool_req["params"]["name"] == "verify"
        assert tool_req["params"]["arguments"] == {"file": "test.lean"}

    def test_call_tool_timeout(self):
        """Test that timeout raises TimeoutError."""
        import time

        init_response = _make_jsonrpc_response(1, {"protocolVersion": "2024-11-05"})
        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        mock_process.poll = MagicMock(return_value=None)

        # stderr.readline returns "" so drain thread exits
        mock_stderr = MagicMock()
        mock_stderr.readline = MagicMock(return_value="")
        mock_process.stderr = mock_stderr

        # First readline returns init response, second blocks forever
        def slow_readline():
            time.sleep(10)
            return '{"result": "too late"}\n'

        mock_stdout = MagicMock()
        mock_stdout.readline = MagicMock(side_effect=[init_response, slow_readline])
        mock_process.stdout = mock_stdout

        # Override readline for the second call to actually block
        call_count = [0]
        original_readline = mock_stdout.readline

        def readline_with_delay():
            call_count[0] += 1
            if call_count[0] <= 1:
                return init_response
            time.sleep(10)
            return '{"result": "too late"}\n'

        mock_stdout.readline = readline_with_delay

        with patch("mcp_client.subprocess.Popen", return_value=mock_process):
            with MCPClient(Path("/fake/server.py"), Path("/fake/workdir"), timeout=0.5) as client:
                with pytest.raises(TimeoutError):
                    client.call_tool("verify", {"file": "test.lean"})

    def test_call_tool_dead_process(self):
        """Test that dead process raises RuntimeError."""
        init_response = _make_jsonrpc_response(1, {"protocolVersion": "2024-11-05"})
        mock_process = _mock_process_with_responses(init_response)

        with patch("mcp_client.subprocess.Popen", return_value=mock_process):
            with MCPClient(Path("/fake/server.py"), Path("/fake/workdir"), timeout=5.0) as client:
                # Kill the process after init
                mock_process.poll = MagicMock(return_value=1)
                mock_process.stderr.read = MagicMock(return_value="Server crashed!")

                with pytest.raises(RuntimeError, match="terminated"):
                    client.call_tool("verify", {"file": "test.lean"})

    def test_call_tool_not_initialized_raises(self):
        """Test that calling tool without initialization raises RuntimeError."""
        client = MCPClient(Path("/fake/server.py"), Path("/fake/workdir"))
        client._process = MagicMock()  # Fake a process but skip init

        with pytest.raises(RuntimeError, match="not initialized"):
            client.call_tool("verify", {"file": "test.lean"})

    def test_call_tool_increments_request_id(self):
        """Test that request IDs increment for each call."""
        tool_resp_1 = _make_jsonrpc_response(2, {"content": []})
        tool_resp_2 = _make_jsonrpc_response(3, {"content": []})
        mock_process = self._make_client_with_responses(tool_resp_1, tool_resp_2)

        written_messages: list[str] = []
        mock_process.stdin.write = lambda data: written_messages.append(data)

        with patch("mcp_client.subprocess.Popen", return_value=mock_process):
            with MCPClient(Path("/fake/server.py"), Path("/fake/workdir"), timeout=5.0) as client:
                client.call_tool("verify", {"file": "test1.lean"})
                client.call_tool("verify", {"file": "test2.lean"})

        # Messages: init(id=1), initialized(no id), tool1(id=2), tool2(id=3)
        tool_reqs = [json.loads(m) for m in written_messages if "tools/call" in m]
        assert len(tool_reqs) == 2
        assert tool_reqs[0]["id"] == 2
        assert tool_reqs[1]["id"] == 3


class TestMCPClientHealthCheck:
    """Test health check functionality."""

    def test_health_check_returns_true_on_success(self):
        """Test that health_check returns True when server responds."""
        init_response = _make_jsonrpc_response(1, {"protocolVersion": "2024-11-05"})
        list_response = _make_jsonrpc_response(2, {"tools": []})
        mock_process = _mock_process_with_responses(init_response, list_response)

        with patch("mcp_client.subprocess.Popen", return_value=mock_process):
            with MCPClient(Path("/fake/server.py"), Path("/fake/workdir")) as client:
                assert client.health_check() is True

    def test_health_check_returns_false_when_dead(self):
        """Test that health_check returns False when process is dead."""
        init_response = _make_jsonrpc_response(1, {"protocolVersion": "2024-11-05"})
        mock_process = _mock_process_with_responses(init_response)

        with patch("mcp_client.subprocess.Popen", return_value=mock_process):
            with MCPClient(Path("/fake/server.py"), Path("/fake/workdir")) as client:
                mock_process.poll = MagicMock(return_value=1)
                assert client.health_check() is False


class TestMCPClientRestart:
    """Test restart functionality."""

    def test_restart_terminates_and_starts_new_process(self):
        """Test that restart terminates old process and starts new one."""
        init_resp_1 = _make_jsonrpc_response(1, {"protocolVersion": "2024-11-05"})
        init_resp_2 = _make_jsonrpc_response(2, {"protocolVersion": "2024-11-05"})

        mock_process1 = _mock_process_with_responses(init_resp_1)
        mock_process2 = _mock_process_with_responses(init_resp_2)

        with patch("mcp_client.subprocess.Popen", side_effect=[mock_process1, mock_process2]):
            client = MCPClient(Path("/fake/server.py"), Path("/fake/workdir"))
            client.__enter__()
            assert client._process is mock_process1

            client.restart()
            mock_process1.terminate.assert_called()
            assert client._process is mock_process2
            assert client._initialized is True

            client.__exit__(None, None, None)


class TestMCPClientIntegration:
    """Integration tests with real MCP server.

    These require the actual MCP server and eval repository.
    Marked with pytest.mark.integration.
    """

    @pytest.mark.integration
    def test_full_lifecycle_with_real_server(self):
        """Test full lifecycle with actual MCP server."""
        try:
            from fixtures import get_eval_repo_path
            eval_repo_path = get_eval_repo_path()
        except (ImportError, FileNotFoundError) as e:
            pytest.skip(f"Eval repository not available: {e}")

        server_path = Path(__file__).parent.parent.parent / "src" / "lean_proof_auto_mcp" / "server.py"
        if not server_path.exists():
            pytest.skip(f"MCP server not found at {server_path}")

        with MCPClient(server_path, eval_repo_path, timeout=30.0) as client:
            assert client._process is not None
            assert client._process.poll() is None
            assert client._initialized is True

    @pytest.mark.integration
    def test_verify_tool_returns_valid_response(self):
        """Test that verify tool returns a response matching VerifyResult schema."""
        try:
            from fixtures import get_eval_repo_path, ALL_FIXTURE_FILES
            eval_repo_path = get_eval_repo_path()
        except (ImportError, FileNotFoundError) as e:
            pytest.skip(f"Eval repository not available: {e}")

        if not ALL_FIXTURE_FILES:
            pytest.skip("No fixture files available")

        server_path = Path(__file__).parent.parent.parent / "src" / "lean_proof_auto_mcp" / "server.py"
        if not server_path.exists():
            pytest.skip(f"MCP server not found at {server_path}")

        logger = EvalLogger("test_mcp_client")
        logger.start_session("integration", 1)

        with MCPClient(server_path, eval_repo_path, timeout=180.0) as client:
            fixture = ALL_FIXTURE_FILES[0]
            file_size = fixture.path.stat().st_size if fixture.path.exists() else 0
            logger.log_fixture_start(fixture.relative_path, file_size, 1, 1)

            t0 = time.perf_counter()
            response = client.call_tool("verify", {"file": str(fixture.path)})
            elapsed_s = time.perf_counter() - t0

            assert isinstance(response, dict)
            assert "status" in response, f"Missing 'status'. Keys: {list(response.keys())}"
            assert response["status"] in ("success", "fail", "timeout", "error")

            passed = "status" in response and response["status"] in ("success", "fail", "timeout", "error")
            failures = [] if passed else [f"Invalid response: {list(response.keys())}"]
            logger.log_fixture_result(response, elapsed_s, passed, failures)
