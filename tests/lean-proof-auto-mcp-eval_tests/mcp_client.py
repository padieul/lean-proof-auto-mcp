"""MCP Client for Evaluation Testing Framework.

This module provides a reusable MCP client that communicates with the MCP server
via the official MCP SDK's ClientSession over stdio transport. This ensures full
protocol compliance including the initialize handshake.

Key Features:
- Context manager support for automatic server lifecycle management
- Full MCP protocol compliance (initialize handshake, tools/call)
- Timeout handling on tool calls
- Health check and restart capabilities

Design Patterns:
- Context Manager: Ensures proper server startup and cleanup
- Dependency Injection: Server path and working directory injected at construction
- Explicit Error Handling: All failures represented as typed exceptions
"""

import asyncio
import json
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any


class MCPClient:
    """Reusable MCP client with context manager support.

    Communicates with the MCP server using newline-delimited JSON-RPC over stdio,
    including the required MCP initialize handshake. Uses uv run to ensure the
    correct virtual environment.

    Example:
        >>> with MCPClient(server_path, working_dir) as client:
        ...     result = client.call_tool("verify", {"file": "test.lean"})
        ...     print(result)
    """

    def __init__(self, server_path: Path, working_dir: Path, timeout: float = 60.0):
        """Initialize MCP client.

        Args:
            server_path: Path to MCP server.py script
            working_dir: Working directory for server process (eval repo root)
            timeout: Timeout in seconds for tool calls (default: 60.0)
        """
        self._server_path = server_path
        self._working_dir = working_dir
        self._timeout = timeout
        self._process: subprocess.Popen[str] | None = None
        self._request_id = 0
        self._initialized = False
        self._stderr_lines: list[str] = []
        self._stderr_thread: threading.Thread | None = None

    def __enter__(self) -> "MCPClient":
        """Start the MCP server process and perform initialize handshake.

        Returns:
            Self for context manager protocol

        Raises:
            RuntimeError: If server process fails to start or initialize
        """
        self._start_process()
        self._perform_initialize()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Terminate the MCP server process.

        Attempts graceful termination first, then forceful kill if needed.
        """
        if self._process is None:
            return

        try:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
        except Exception:
            try:
                self._process.kill()
                self._process.wait()
            except Exception:
                pass
        finally:
            self._initialized = False

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call an MCP tool and return the result.

        Args:
            name: Tool name (e.g., "verify", "probe")
            arguments: Tool arguments as dictionary

        Returns:
            Parsed result content from the MCP response. For tools that return
            JSON in a text content block, this is the parsed JSON dict.

        Raises:
            TimeoutError: If tool call exceeds timeout
            ValueError: If server returns malformed JSON or unexpected format
            RuntimeError: If server process has terminated or client not initialized
        """
        if self._process is None:
            raise RuntimeError("MCP client not started (use as context manager)")

        if not self._initialized:
            raise RuntimeError("MCP client not initialized")

        if self._process.poll() is not None:
            stderr_tail = "\n".join(self._stderr_lines[-20:])
            raise RuntimeError(f"MCP server process has terminated. stderr: {stderr_tail}")

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

        self._send_message(request)
        response = self._read_response()

        # Extract tool result from MCP response
        if "error" in response:
            return response

        # MCP tools/call returns result with "content" array
        result = response.get("result", {})
        content = result.get("content", [])

        # Parse the first text content block as JSON (tool convention)
        for block in content:
            if block.get("type") == "text":
                try:
                    return json.loads(block["text"])
                except (json.JSONDecodeError, KeyError):
                    return {"raw_text": block.get("text", "")}

        return result

    def health_check(self) -> bool:
        """Check if server is responsive.

        Sends a tools/list request to verify the server is alive.

        Returns:
            True if server responds, False otherwise
        """
        if self._process is None or self._process.poll() is not None:
            return False

        try:
            self._request_id += 1
            request = {
                "jsonrpc": "2.0",
                "id": self._request_id,
                "method": "tools/list",
                "params": {},
            }
            self._send_message(request)
            response = self._read_response()
            return "result" in response
        except Exception:
            return False

    def restart(self) -> None:
        """Terminate and restart the server process.

        Raises:
            RuntimeError: If server fails to restart
        """
        self.__exit__(None, None, None)
        self._start_process()
        self._perform_initialize()

    def _start_process(self) -> None:
        """Start the MCP server subprocess using uv run.

        Also starts a background thread to drain stderr, preventing the
        server from blocking when the stderr pipe buffer fills up (Windows
        pipe buffers are ~4KB — the server's log output can easily exceed
        that during long-running verify calls).
        """
        env = os.environ.copy()

        # Get the src directory for PYTHONPATH
        src_dir = self._server_path.parent.parent
        if "PYTHONPATH" in env:
            env["PYTHONPATH"] = f"{src_dir}{os.pathsep}{env['PYTHONPATH']}"
        else:
            env["PYTHONPATH"] = str(src_dir)

        # Ensure UTF-8 encoding for the subprocess on Windows
        env["PYTHONIOENCODING"] = "utf-8"

        self._process = subprocess.Popen(
            ["uv", "run", "python", "-m", "lean_proof_auto_mcp.server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=env,
            cwd=str(self._working_dir),
        )

        # Drain stderr in background to prevent pipe buffer deadlock
        self._stderr_lines = []
        process_ref = self._process

        def _drain_stderr() -> None:
            while process_ref and process_ref.stderr:
                try:
                    line = process_ref.stderr.readline()
                    if not line:
                        break
                    self._stderr_lines.append(line.rstrip())
                except (ValueError, OSError):
                    break

        self._stderr_thread = threading.Thread(
            target=_drain_stderr, daemon=True
        )
        self._stderr_thread.start()

    def _perform_initialize(self) -> None:
        """Perform the MCP initialize handshake.

        Sends initialize request and initialized notification as required
        by the MCP protocol before any tool calls can be made.

        Raises:
            RuntimeError: If initialize handshake fails
        """
        self._request_id += 1
        init_request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "eval-test-client",
                    "version": "1.0.0",
                },
            },
        }

        try:
            self._send_message(init_request)
            response = self._read_response()

            if "error" in response:
                raise RuntimeError(
                    f"MCP initialize failed: {response['error']}"
                )

            # Send initialized notification (no id, no response expected)
            initialized_notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            }
            self._send_message(initialized_notification)
            self._initialized = True

        except Exception as e:
            if self._process:
                self._process.kill()
                self._process.wait()
                self._process = None
            raise RuntimeError(f"MCP initialize handshake failed: {e}") from e

    def _send_message(self, message: dict[str, Any]) -> None:
        """Send a JSON-RPC message to the server via stdin."""
        if self._process is None or self._process.stdin is None:
            raise RuntimeError("Process stdin is not available")

        message_json = json.dumps(message) + "\n"
        self._process.stdin.write(message_json)
        self._process.stdin.flush()

    def _read_response(self) -> dict[str, Any]:
        """Read a JSON-RPC response from stdout with timeout.

        Skips non-JSON lines (server log output) and notification messages
        (no "id" field), returning the first valid JSON-RPC response.

        Returns:
            Parsed JSON-RPC response dict

        Raises:
            TimeoutError: If no response received within timeout
            ValueError: If server returns malformed JSON after filtering
            RuntimeError: If process terminates while waiting
        """
        if self._process is None or self._process.stdout is None:
            raise RuntimeError("Process not available")

        deadline = time.monotonic() + self._timeout

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"Tool call timed out after {self._timeout} seconds")

            line = self._read_line_with_timeout(remaining)

            if not line or not line.strip():
                continue

            # Skip non-JSON lines (server log output written to stdout)
            stripped = line.strip()
            if not stripped.startswith("{"):
                continue

            try:
                message = json.loads(stripped)
            except json.JSONDecodeError:
                # Not valid JSON — likely a log line that starts with {
                continue

            if not isinstance(message, dict):
                continue

            # Skip notifications (messages without "id")
            if "id" in message:
                return message

    def _read_line_with_timeout(self, timeout: float) -> str:
        """Read a single line from stdout with timeout.

        Args:
            timeout: Maximum seconds to wait

        Returns:
            Line read from stdout

        Raises:
            TimeoutError: If no line received within timeout
            RuntimeError: If process terminates while waiting
        """
        container: list[str] = []
        exception_container: list[Exception] = []

        def read_line() -> None:
            try:
                if self._process and self._process.stdout:
                    line = self._process.stdout.readline()
                    container.append(line)
            except Exception as e:
                exception_container.append(e)

        reader_thread = threading.Thread(target=read_line, daemon=True)
        reader_thread.start()
        reader_thread.join(timeout=timeout)

        if reader_thread.is_alive():
            raise TimeoutError(f"Read timed out after {timeout:.1f} seconds")

        if exception_container:
            raise exception_container[0]

        if not container:
            if self._process and self._process.poll() is not None:
                stderr_tail = "\n".join(self._stderr_lines[-20:])
                raise RuntimeError(f"Server process terminated. stderr: {stderr_tail}")
            raise RuntimeError("No response received from server")

        return container[0]
