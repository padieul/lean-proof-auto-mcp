"""MCP Client for Evaluation Testing Framework.

This module provides a reusable MCP (Model Context Protocol) client that communicates
with the MCP server via JSON-RPC protocol. The client follows hexagonal architecture
principles, providing a clean interface for test modules to interact with MCP tools
without coupling to server implementation details.

Key Features:
- Context manager support for automatic server lifecycle management
- JSON-RPC communication with timeout handling
- Graceful error handling for malformed responses and dead processes
- Health check and restart capabilities for robust test execution

Design Patterns:
- Context Manager: Ensures proper server startup and cleanup
- Dependency Injection: Server path and working directory injected at construction
- Explicit Error Handling: All failures represented as typed exceptions
"""

import json
import subprocess
import threading
import time
from pathlib import Path
from typing import Any


class MCPClient:
    """Reusable MCP client with context manager support.
    
    This client manages the lifecycle of an MCP server process and provides
    methods for calling tools via JSON-RPC protocol. It follows the context
    manager protocol to ensure proper resource cleanup.
    
    Example:
        >>> with MCPClient(server_path, working_dir) as client:
        ...     result = client.call_tool("verify", {"file_path": "test.lean"})
        ...     print(result)
    """
    
    def __init__(self, server_path: Path, working_dir: Path, timeout: float = 30.0):
        """Initialize MCP client.
        
        Args:
            server_path: Path to MCP server.py script
            working_dir: Working directory for server process (eval repo root)
            timeout: Timeout in seconds for tool calls (default: 30.0)
        """
        self._server_path = server_path
        self._working_dir = working_dir
        self._timeout = timeout
        self._process: subprocess.Popen[str] | None = None
        self._request_id = 0

    def __enter__(self) -> "MCPClient":
        """Start the MCP server process.
        
        Returns:
            Self for context manager protocol
            
        Raises:
            RuntimeError: If server process fails to start
        """
        # Run server as a module to handle relative imports
        # We need to add the src directory to PYTHONPATH
        import os
        env = os.environ.copy()
        
        # Get the src directory (parent of lean_proof_auto_mcp)
        src_dir = self._server_path.parent.parent
        
        # Add src to PYTHONPATH
        if 'PYTHONPATH' in env:
            env['PYTHONPATH'] = f"{src_dir}{os.pathsep}{env['PYTHONPATH']}"
        else:
            env['PYTHONPATH'] = str(src_dir)
        
        self._process = subprocess.Popen(
            ["python", "-m", "lean_proof_auto_mcp.server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            cwd=str(self._working_dir),
        )
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Terminate the MCP server process.
        
        Attempts graceful termination first, then forceful kill if needed.
        Handles exceptions gracefully to ensure cleanup always completes.
        
        Args:
            exc_type: Exception type (if any)
            exc_val: Exception value (if any)
            exc_tb: Exception traceback (if any)
        """
        if self._process is None:
            return
        
        try:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Process didn't terminate gracefully, force kill
                self._process.kill()
                self._process.wait()
        except Exception:
            # Ensure we always try to kill if terminate fails
            try:
                self._process.kill()
                self._process.wait()
            except Exception:
                # Suppress all exceptions during cleanup
                pass

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call an MCP tool and return the result.
        
        Constructs a JSON-RPC request, sends it to the server, and waits for
        a response with timeout handling.
        
        Args:
            name: Tool name (e.g., "verify", "probe")
            arguments: Tool arguments as dictionary
            
        Returns:
            JSON-RPC response as dictionary
            
        Raises:
            TimeoutError: If tool call exceeds timeout
            ValueError: If server returns malformed JSON
            RuntimeError: If server process has terminated
        """
        if self._process is None:
            raise RuntimeError("MCP client not started (use as context manager)")
        
        # Check if process is still alive
        if self._process.poll() is not None:
            stderr_output = self._process.stderr.read() if self._process.stderr else ""
            raise RuntimeError(f"MCP server process has terminated. stderr: {stderr_output}")
        
        # Construct JSON-RPC request with MCP protocol
        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments,
            },
        }
        
        # Send request
        request_json = json.dumps(request) + "\n"
        if self._process.stdin is None:
            raise RuntimeError("Process stdin is not available")
        
        self._process.stdin.write(request_json)
        self._process.stdin.flush()
        
        # Read response with timeout
        response_line = self._read_response_with_timeout()
        
        # Parse JSON response
        try:
            response = json.loads(response_line)
        except json.JSONDecodeError as e:
            raise ValueError(f"Malformed JSON response: {response_line}") from e
        
        # Validate response structure
        if not isinstance(response, dict):
            raise ValueError(f"Response is not a dictionary: {response_line}")
        
        return response
    
    def _read_response_with_timeout(self) -> str:
        """Read a response line from stdout with timeout.
        
        Returns:
            Response line as string
            
        Raises:
            TimeoutError: If no response received within timeout
            RuntimeError: If process terminates while waiting
        """
        if self._process is None or self._process.stdout is None:
            raise RuntimeError("Process not available")
        
        response_container: list[str] = []
        exception_container: list[Exception] = []
        
        def read_line() -> None:
            try:
                if self._process and self._process.stdout:
                    line = self._process.stdout.readline()
                    response_container.append(line)
            except Exception as e:
                exception_container.append(e)
        
        reader_thread = threading.Thread(target=read_line, daemon=True)
        reader_thread.start()
        reader_thread.join(timeout=self._timeout)
        
        if reader_thread.is_alive():
            # Timeout occurred
            raise TimeoutError(f"Tool call timed out after {self._timeout} seconds")
        
        if exception_container:
            raise exception_container[0]
        
        if not response_container:
            raise RuntimeError("No response received from server")
        
        return response_container[0]

    def health_check(self) -> bool:
        """Check if server is responsive.
        
        Sends a ping request to verify the server is alive and responding.
        
        Returns:
            True if server responds to ping, False otherwise
        """
        try:
            # Send a simple ping/health check request
            response = self.call_tool("ping", {})
            return True
        except Exception:
            return False

    def restart(self) -> None:
        """Terminate and restart the server process.
        
        Useful for recovering from server errors or resetting server state.
        
        Raises:
            RuntimeError: If server fails to restart
        """
        # Terminate current process
        self.__exit__(None, None, None)
        
        # Start new process
        self.__enter__()
