"""
Property-based tests for ServerManager.

These tests verify universal properties that should hold across all valid executions.
Each test runs a minimum of 100 iterations with randomized inputs.

Requirements: 10.6, 28.4, 28.5, 28.6
"""

from pathlib import Path
from unittest.mock import Mock, patch

import hypothesis.strategies as st
import pytest
from hypothesis import given, settings

from lean_proof_auto_mcp.lean.server_manager import ServerManagerImpl

# ============================================================================
# Hypothesis Strategies
# ============================================================================


@st.composite
def file_paths(draw):
    """Generate valid file paths."""
    # Generate realistic Lean file paths
    directory = draw(st.sampled_from(["src", "test", "lib", "examples", "."]))
    filename = draw(st.text(min_size=1, max_size=50, alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"),
        whitelist_characters="_-"
    )))
    return f"{directory}/{filename}.lean"


@st.composite
def workspace_paths(draw):
    """Generate valid workspace paths."""
    has_workspace = draw(st.booleans())
    if has_workspace:
        return Path(draw(st.text(min_size=1, max_size=100)))
    return None


# ============================================================================
# Property 19: Server Instance Reuse
# ============================================================================


@given(
    file_path=file_paths(),
    num_calls=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=100, deadline=None)
def test_property_19_server_instance_reuse(file_path, num_calls):
    """
    Feature: iterative-orchestration-enhancements
    Property 19: Server Instance Reuse

    For any file being processed, the system SHALL maintain a single LeanInteract
    server instance for that file across multiple operations.

    Validates: Requirements 10.6, 28.4
    """
    # Setup: Create manager with mocked LeanServer
    manager = ServerManagerImpl()
    
    # Mock LeanServer creation
    mock_server = Mock()
    mock_server.run = Mock(return_value=Mock())
    mock_server.kill = Mock()
    
    with patch.object(manager, "_create_server", return_value=mock_server):
        with patch.object(manager, "_is_server_alive", return_value=True):
            # Execute: Get server multiple times for same file
            servers = []
            for _ in range(num_calls):
                server = manager.get_server(file_path)
                servers.append(server)
            
            # Verify: All calls returned the same server instance
            for server in servers:
                assert server is mock_server
            
            # Verify: Only one server instance in cache
            assert len(manager._servers) == 1
            assert file_path in manager._servers
            
            # Verify: _create_server was called only once
            manager._create_server.assert_called_once()


@given(
    file_paths_list=st.lists(file_paths(), min_size=1, max_size=5, unique=True),
)
@settings(max_examples=100, deadline=None)
def test_property_19_multiple_files_separate_servers(file_paths_list):
    """
    Feature: iterative-orchestration-enhancements
    Property 19: Server Instance Reuse (Multiple Files)

    For any set of different files, the system SHALL maintain separate server
    instances for each file.

    Validates: Requirements 10.6, 28.4
    """
    # Setup: Create manager
    manager = ServerManagerImpl()
    
    # Mock LeanServer creation
    mock_servers = {}
    
    def create_mock_server(fp):
        if fp not in mock_servers:
            mock_server = Mock()
            mock_server.run = Mock(return_value=Mock())
            mock_server.kill = Mock()
            mock_servers[fp] = mock_server
        return mock_servers[fp]
    
    with patch.object(manager, "_create_server", side_effect=create_mock_server):
        with patch.object(manager, "_is_server_alive", return_value=True):
            # Execute: Get server for each file
            for file_path in file_paths_list:
                manager.get_server(file_path)
            
            # Verify: One server per file
            assert len(manager._servers) == len(file_paths_list)
            
            # Verify: Each file has its own server
            for file_path in file_paths_list:
                assert file_path in manager._servers
                assert manager._servers[file_path] is mock_servers[file_path]


@given(
    file_path=file_paths(),
)
@settings(max_examples=100, deadline=None)
def test_property_19_dead_server_recreation(file_path):
    """
    Feature: iterative-orchestration-enhancements
    Property 19: Server Instance Reuse (Dead Server)

    When a server is dead, the system SHALL detect it and create a new server
    instance automatically.

    Validates: Requirements 28.5
    """
    # Setup: Create manager
    manager = ServerManagerImpl()
    
    # Mock LeanServer creation
    mock_server_1 = Mock()
    mock_server_1.run = Mock(return_value=Mock())
    mock_server_1.kill = Mock()
    
    mock_server_2 = Mock()
    mock_server_2.run = Mock(return_value=Mock())
    mock_server_2.kill = Mock()
    
    servers_created = [mock_server_1, mock_server_2]
    create_call_count = [0]
    
    def create_mock_server(fp):
        server = servers_created[create_call_count[0]]
        create_call_count[0] += 1
        return server
    
    with patch.object(manager, "_create_server", side_effect=create_mock_server):
        # Execute: First call creates server
        with patch.object(manager, "_is_server_alive", return_value=True):
            server_1 = manager.get_server(file_path)
            assert server_1 is mock_server_1
        
        # Execute: Second call detects dead server and recreates
        with patch.object(manager, "_is_server_alive", return_value=False):
            server_2 = manager.get_server(file_path)
            assert server_2 is mock_server_2
            
            # Verify: Old server was cleaned up
            mock_server_1.kill.assert_called_once()
            
            # Verify: New server is in cache
            assert manager._servers[file_path] is mock_server_2


@given(
    file_path=file_paths(),
)
@settings(max_examples=100, deadline=None)
def test_property_19_restart_server(file_path):
    """
    Feature: iterative-orchestration-enhancements
    Property 19: Server Instance Reuse (Restart)

    When restart_server is called, the system SHALL kill the existing server
    and create a new one.

    Validates: Requirements 28.5
    """
    # Setup: Create manager with existing server
    manager = ServerManagerImpl()
    
    mock_server_1 = Mock()
    mock_server_1.kill = Mock()
    
    mock_server_2 = Mock()
    mock_server_2.kill = Mock()
    
    # Add existing server to cache
    manager._servers[file_path] = mock_server_1
    
    with patch.object(manager, "_create_server", return_value=mock_server_2):
        # Execute: Restart server
        manager.restart_server(file_path)
        
        # Verify: Old server was killed
        mock_server_1.kill.assert_called_once()
        
        # Verify: New server is in cache
        assert manager._servers[file_path] is mock_server_2
        
        # Verify: New server was created
        manager._create_server.assert_called_once_with(file_path)


@given(
    file_paths_list=st.lists(file_paths(), min_size=1, max_size=5, unique=True),
)
@settings(max_examples=100, deadline=None)
def test_property_19_shutdown_all(file_paths_list):
    """
    Feature: iterative-orchestration-enhancements
    Property 19: Server Instance Reuse (Shutdown All)

    When shutdown_all is called, the system SHALL kill all servers and clear
    the cache.

    Validates: Requirements 28.6
    """
    # Setup: Create manager with multiple servers
    manager = ServerManagerImpl()
    
    mock_servers = []
    for file_path in file_paths_list:
        mock_server = Mock()
        mock_server.kill = Mock()
        manager._servers[file_path] = mock_server
        mock_servers.append(mock_server)
    
    # Execute: Shutdown all servers
    manager.shutdown_all()
    
    # Verify: All servers were killed
    for mock_server in mock_servers:
        mock_server.kill.assert_called_once()
    
    # Verify: Cache was cleared
    assert len(manager._servers) == 0


@given(
    file_path=file_paths(),
    request_desc=st.text(min_size=1, max_size=100),
)
@settings(max_examples=100, deadline=None)
def test_property_19_request_logging(file_path, request_desc):
    """
    Feature: iterative-orchestration-enhancements
    Property 19: Server Instance Reuse (Request Logging)

    For any request, the system SHALL log all LeanInteract requests and responses.

    Validates: Requirements 28.6
    """
    # Setup: Create manager
    manager = ServerManagerImpl()
    
    # Mock response
    mock_response = Mock()
    
    # Execute: Log request
    manager.log_request(file_path, request_desc, mock_response)
    
    # Verify: Request was logged
    log = manager.get_request_log()
    assert len(log) == 1
    assert log[0] == (file_path, request_desc, mock_response)


@given(
    file_path=file_paths(),
    num_requests=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=100, deadline=None)
def test_property_19_request_log_accumulation(file_path, num_requests):
    """
    Feature: iterative-orchestration-enhancements
    Property 19: Server Instance Reuse (Log Accumulation)

    For any sequence of requests, the system SHALL accumulate all logs in order.

    Validates: Requirements 28.6
    """
    # Setup: Create manager
    manager = ServerManagerImpl()
    
    # Execute: Log multiple requests
    for i in range(num_requests):
        manager.log_request(file_path, f"request_{i}", f"response_{i}")
    
    # Verify: All requests were logged in order
    log = manager.get_request_log()
    assert len(log) == num_requests
    
    for i in range(num_requests):
        assert log[i] == (file_path, f"request_{i}", f"response_{i}")


# ============================================================================
# Error Handling Tests
# ============================================================================


def test_property_19_lean_interact_not_available():
    """
    Feature: iterative-orchestration-enhancements
    Property 19: Server Instance Reuse (Error Handling)

    When LeanInteract is not available, get_server should raise RuntimeError
    with clear message.

    Validates: Requirements 11.3
    """
    # Setup: Create manager
    manager = ServerManagerImpl()
    
    # Mock LeanInteract as unavailable
    import lean_proof_auto_mcp.lean.server_manager as manager_module
    original_available = manager_module.LEAN_INTERACT_AVAILABLE
    original_server = manager_module.LeanServer
    
    try:
        manager_module.LEAN_INTERACT_AVAILABLE = False
        manager_module.LeanServer = None
        
        # Execute & Verify
        with pytest.raises(RuntimeError, match="LeanInteract library not installed"):
            manager.get_server("test.lean")
    finally:
        # Restore
        manager_module.LEAN_INTERACT_AVAILABLE = original_available
        manager_module.LeanServer = original_server


@given(
    file_path=file_paths(),
)
@settings(max_examples=100, deadline=None)
def test_property_19_server_creation_failure(file_path):
    """
    Feature: iterative-orchestration-enhancements
    Property 19: Server Instance Reuse (Creation Failure)

    When server creation fails, get_server should raise RuntimeError with
    error details.

    Validates: Requirements 11.1, 11.3
    """
    # Setup: Create manager
    manager = ServerManagerImpl()
    
    # Mock _create_server to raise exception
    with patch.object(manager, "_create_server", side_effect=RuntimeError("Failed to create server for test.lean: Creation failed")):
        # Execute & Verify
        with pytest.raises(RuntimeError, match="Failed to create server"):
            manager.get_server(file_path)


@given(
    file_path=file_paths(),
)
@settings(max_examples=50, deadline=None)
def test_property_19_cleanup_failure_graceful(file_path):
    """
    Feature: iterative-orchestration-enhancements
    Property 19: Server Instance Reuse (Cleanup Failure)

    When server cleanup fails, the system should log the error but continue
    without crashing.

    Validates: Requirements 11.2
    """
    # Setup: Create manager with server that fails to kill
    manager = ServerManagerImpl()
    
    mock_server = Mock()
    mock_server.kill = Mock(side_effect=Exception("Kill failed"))
    manager._servers[file_path] = mock_server
    
    # Execute: Shutdown should not raise exception
    try:
        manager.shutdown_all()
        # Verify: Cache was still cleared despite kill failure
        assert len(manager._servers) == 0
    except Exception as e:
        pytest.fail(f"shutdown_all raised exception: {e}")


# ============================================================================
# Workspace Context Tests
# ============================================================================


@given(
    workspace_path=workspace_paths(),
    file_path=file_paths(),
)
@settings(max_examples=50, deadline=None)
def test_property_19_workspace_context(workspace_path, file_path):
    """
    Feature: iterative-orchestration-enhancements
    Property 19: Server Instance Reuse (Workspace Context)

    The system SHALL support optional workspace context for project-aware
    server creation.

    Validates: Requirements 28.3, 28.4
    """
    # Setup: Create manager with workspace path
    manager = ServerManagerImpl(workspace_path=workspace_path)
    
    # Verify: Workspace path is stored
    assert manager.workspace_path == workspace_path
    
    # Mock server creation
    mock_server = Mock()
    mock_server.run = Mock(return_value=Mock())
    mock_server.kill = Mock()
    
    with patch.object(manager, "_create_server", return_value=mock_server):
        with patch.object(manager, "_is_server_alive", return_value=True):
            # Execute: Get server
            server = manager.get_server(file_path)
            
            # Verify: Server was created
            assert server is mock_server


# ============================================================================
# Concurrency Safety Tests
# ============================================================================


@given(
    file_path=file_paths(),
)
@settings(max_examples=50, deadline=None)
def test_property_19_get_request_log_returns_copy(file_path):
    """
    Feature: iterative-orchestration-enhancements
    Property 19: Server Instance Reuse (Log Safety)

    get_request_log should return a copy of the log to prevent external
    modification.

    Validates: Requirements 28.6
    """
    # Setup: Create manager with some logs
    manager = ServerManagerImpl()
    manager.log_request(file_path, "request_1", "response_1")
    
    # Execute: Get log
    log_1 = manager.get_request_log()
    
    # Modify the returned log
    log_1.append((file_path, "request_2", "response_2"))
    
    # Verify: Internal log was not modified
    log_2 = manager.get_request_log()
    assert len(log_2) == 1
    assert log_2[0] == (file_path, "request_1", "response_1")
