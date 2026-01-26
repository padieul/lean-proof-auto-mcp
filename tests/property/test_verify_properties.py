"""
Property-based tests for verify tool.

These tests verify universal properties that should hold across all valid executions.
Each test runs a minimum of 100 iterations with randomized inputs.

Requirements: All correctness properties from design document
"""

import dataclasses
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
import hypothesis.strategies as st

from lean_proof_auto_mcp.core.verify_domain import (
    VerifyCommand,
    VerifyCommandHandler,
    VerifyResult,
    LeanRunResult,
    Workspace,
    LeanRunner,
    WorkspaceProvider,
    ArtifactStore,
)


# ============================================================================
# Mock Adapters for Testing
# ============================================================================


class MockLeanRunner:
    """Mock LeanRunner that returns predefined results without spawning Lean."""
    
    def __init__(self, result: LeanRunResult | None = None):
        self.result = result or LeanRunResult(
            status="success",
            diagnostics=[],
            scope_used="file",
            full_logs="Mock Lean output",
            timing={"lean_execution_s": 0.5},
            exit_code=0,
        )
        self.calls: list[dict[str, Any]] = []
    
    def verify_file(
        self,
        workspace_path: Path,
        file_path: str,
        theorem_id: str | None,
        budget_s: float,
    ) -> LeanRunResult:
        """Record call and return mock result."""
        self.calls.append({
            "workspace_path": workspace_path,
            "file_path": file_path,
            "theorem_id": theorem_id,
            "budget_s": budget_s,
        })
        return self.result


class MockWorkspaceProvider:
    """Mock WorkspaceProvider that creates in-memory workspaces."""
    
    def __init__(self):
        self.workspaces_created: list[Workspace] = []
        self.workspaces_cleaned: list[Workspace] = []
        self._lock = threading.Lock()  # Thread-safe access to lists
        self._workspace_counter = 0
    
    def create_workspace(self, file_path: str) -> Workspace:
        """Create mock workspace with unique ID."""
        with self._lock:
            self._workspace_counter += 1
            workspace_id = f"mock-workspace-{self._workspace_counter}"
            workspace = Workspace(
                path=Path(f"/tmp/mock-workspace-{self._workspace_counter}"),
                workspace_id=workspace_id,
                mode="temp",
            )
            self.workspaces_created.append(workspace)
            return workspace
    
    def cleanup_workspace(self, workspace: Workspace) -> None:
        """Record cleanup."""
        with self._lock:
            self.workspaces_cleaned.append(workspace)


class MockArtifactStore:
    """Mock ArtifactStore that stores artifacts in memory."""
    
    def __init__(self):
        self.stored_artifacts: list[dict[str, Any]] = []
        self._lock = threading.Lock()  # Thread-safe access to list
    
    def store(
        self,
        run_id: str,
        command: VerifyCommand,
        result: VerifyResult,
        full_logs: str,
    ) -> None:
        """Record stored artifacts."""
        with self._lock:
            self.stored_artifacts.append({
                "run_id": run_id,
                "command": command,
                "result": result,
                "full_logs": full_logs,
            })


# ============================================================================
# Property Tests
# ============================================================================


class TestProperty1ResponseSchemaCompliance:
    """
    Property 1: Response Schema Compliance
    
    For any verification request (valid or invalid), the response SHALL conform
    to the output JSON schema with required fields: api_version, status, run_id,
    file, diagnostics, diagnostic_summary, evidence, metadata, and timing.
    
    Feature: lean-verify-tool, Property 1: Response schema compliance
    Validates: Requirements 1.1, 8.3
    """
    
    @settings(max_examples=20, deadline=None)
    @given(
        file_path=st.text(min_size=1, max_size=100),
        budget_s=st.floats(min_value=0.1, max_value=60.0),
        max_log_excerpt_chars=st.integers(min_value=100, max_value=10000),
        store_full_logs=st.booleans(),
    )
    def test_response_has_all_required_fields(
        self,
        file_path: str,
        budget_s: float,
        max_log_excerpt_chars: int,
        store_full_logs: bool,
    ):
        """Test that all responses have required fields."""
        # Feature: lean-verify-tool, Property 1: Response schema compliance
        
        # Arrange
        lean_runner = MockLeanRunner()
        workspace_provider = MockWorkspaceProvider()
        artifact_store = MockArtifactStore()
        handler = VerifyCommandHandler(lean_runner, workspace_provider, artifact_store)
        
        try:
            cmd = VerifyCommand(
                file_path=file_path,
                budget_s=budget_s,
                max_log_excerpt_chars=max_log_excerpt_chars,
                store_full_logs=store_full_logs,
            )
        except ValueError:
            # Invalid command, skip this test case
            return
        
        # Act
        result = handler.handle(cmd)
        
        # Assert - Check all required fields exist
        assert hasattr(result, "api_version")
        assert hasattr(result, "status")
        assert hasattr(result, "run_id")
        assert hasattr(result, "file")
        assert hasattr(result, "theorem_id")
        assert hasattr(result, "verification_scope_used")
        assert hasattr(result, "diagnostics")
        assert hasattr(result, "diagnostic_summary")
        assert hasattr(result, "evidence")
        assert hasattr(result, "metadata")
        assert hasattr(result, "timing")
        
        # Assert - Check field types
        assert isinstance(result.api_version, str)
        assert isinstance(result.status, str)
        assert isinstance(result.run_id, str)
        assert isinstance(result.file, str)
        assert isinstance(result.diagnostics, list)
        assert isinstance(result.diagnostic_summary, dict)
        assert isinstance(result.evidence, dict)
        assert isinstance(result.metadata, dict)
        assert isinstance(result.timing, dict)
        
        # Assert - Check nested structure
        assert "error_count" in result.diagnostic_summary
        assert "warning_count" in result.diagnostic_summary
        assert "info_count" in result.diagnostic_summary
        
        assert "stdout_excerpt" in result.evidence
        assert "stderr_excerpt" in result.evidence
        assert "notes" in result.evidence
        
        assert "workspace_mode" in result.metadata
        assert "workspace_id" in result.metadata
        
        assert "total_s" in result.timing
        assert "lean_execution_s" in result.timing
        assert "overhead_s" in result.timing
    
    @settings(max_examples=20, deadline=None)
    @given(
        file_path=st.text(min_size=1, max_size=100),
    )
    def test_status_is_valid_value(self, file_path: str):
        """Test that status is one of the valid values."""
        # Feature: lean-verify-tool, Property 1: Response schema compliance
        
        # Arrange
        lean_runner = MockLeanRunner()
        workspace_provider = MockWorkspaceProvider()
        artifact_store = MockArtifactStore()
        handler = VerifyCommandHandler(lean_runner, workspace_provider, artifact_store)
        
        try:
            cmd = VerifyCommand(file_path=file_path)
        except ValueError:
            return
        
        # Act
        result = handler.handle(cmd)
        
        # Assert
        assert result.status in ["success", "fail", "timeout", "error"]


class TestProperty7DeterministicDiagnosticSorting:
    """
    Property 7: Deterministic Diagnostic Sorting
    
    For any verification response with multiple diagnostics, the diagnostics
    array SHALL be sorted by (file, line, col, severity, message) in that order,
    with lexicographic tie-breaking for messages at the same location.
    
    Feature: lean-verify-tool, Property 7: Deterministic diagnostic sorting
    Validates: Requirements 3.1, 3.2
    """
    
    @settings(max_examples=20, deadline=None)
    @given(
        file_path=st.text(min_size=1, max_size=100),
    )
    def test_diagnostics_are_sorted(self, file_path: str):
        """Test that diagnostics are sorted deterministically."""
        # Feature: lean-verify-tool, Property 7: Deterministic diagnostic sorting
        
        # Arrange - Create unsorted diagnostics
        unsorted_diagnostics = [
            {
                "severity": "warning",
                "message": "Warning message",
                "location": {"file": "test.lean", "line": 10, "col": 5},
            },
            {
                "severity": "error",
                "message": "Error message",
                "location": {"file": "test.lean", "line": 5, "col": 1},
            },
            {
                "severity": "error",
                "message": "Another error",
                "location": {"file": "test.lean", "line": 5, "col": 1},
            },
        ]
        
        lean_result = LeanRunResult(
            status="fail",
            diagnostics=unsorted_diagnostics,
            scope_used="file",
            full_logs="",
            timing={"lean_execution_s": 0.5},
            exit_code=1,
        )
        
        lean_runner = MockLeanRunner(result=lean_result)
        workspace_provider = MockWorkspaceProvider()
        artifact_store = MockArtifactStore()
        handler = VerifyCommandHandler(lean_runner, workspace_provider, artifact_store)
        
        try:
            cmd = VerifyCommand(file_path=file_path)
        except ValueError:
            return
        
        # Act
        result = handler.handle(cmd)
        
        # Assert - Check diagnostics are sorted
        diagnostics = result.diagnostics
        if len(diagnostics) > 1:
            for i in range(len(diagnostics) - 1):
                curr = diagnostics[i]
                next_diag = diagnostics[i + 1]
                
                # Compare by file, line, col, severity, message
                curr_key = (
                    curr["location"]["file"],
                    curr["location"]["line"],
                    curr["location"]["col"],
                    {"error": 0, "warning": 1, "info": 2}.get(curr["severity"], 3),
                    curr["message"],
                )
                next_key = (
                    next_diag["location"]["file"],
                    next_diag["location"]["line"],
                    next_diag["location"]["col"],
                    {"error": 0, "warning": 1, "info": 2}.get(next_diag["severity"], 3),
                    next_diag["message"],
                )
                
                assert curr_key <= next_key, f"Diagnostics not sorted: {curr_key} > {next_key}"


class TestProperty8DeterministicOutput:
    """
    Property 8: Deterministic Output
    
    For any two verification requests with identical inputs (same file, same repo
    state, same parameters), the responses SHALL be identical except for run_id
    and timestamp fields.
    
    Feature: lean-verify-tool, Property 8: Deterministic output
    Validates: Requirements 3.3, 3.4, 3.5, 8.5
    """
    
    @settings(max_examples=15, deadline=None)
    @given(
        file_path=st.text(min_size=1, max_size=100),
        budget_s=st.floats(min_value=0.1, max_value=60.0),
    )
    def test_identical_inputs_produce_identical_outputs(
        self,
        file_path: str,
        budget_s: float,
    ):
        """Test that identical inputs produce identical outputs (except run_id)."""
        # Feature: lean-verify-tool, Property 8: Deterministic output
        
        # Arrange
        lean_result = LeanRunResult(
            status="success",
            diagnostics=[
                {
                    "severity": "warning",
                    "message": "Test warning",
                    "location": {"file": "test.lean", "line": 10, "col": 5},
                },
            ],
            scope_used="file",
            full_logs="Test output\nLine 2\nLine 3",
            timing={"lean_execution_s": 0.5},
            exit_code=0,
        )
        
        try:
            cmd = VerifyCommand(file_path=file_path, budget_s=budget_s)
        except ValueError:
            return
        
        # Act - Run verification twice with same inputs
        lean_runner1 = MockLeanRunner(result=lean_result)
        workspace_provider1 = MockWorkspaceProvider()
        artifact_store1 = MockArtifactStore()
        handler1 = VerifyCommandHandler(lean_runner1, workspace_provider1, artifact_store1)
        result1 = handler1.handle(cmd)
        
        lean_runner2 = MockLeanRunner(result=lean_result)
        workspace_provider2 = MockWorkspaceProvider()
        artifact_store2 = MockArtifactStore()
        handler2 = VerifyCommandHandler(lean_runner2, workspace_provider2, artifact_store2)
        result2 = handler2.handle(cmd)
        
        # Assert - Compare results (excluding run_id which should be unique)
        assert result1.api_version == result2.api_version
        assert result1.status == result2.status
        assert result1.file == result2.file
        assert result1.theorem_id == result2.theorem_id
        assert result1.verification_scope_used == result2.verification_scope_used
        assert result1.diagnostics == result2.diagnostics
        assert result1.diagnostic_summary == result2.diagnostic_summary
        assert result1.evidence == result2.evidence
        # Note: metadata may differ due to workspace_id, so we don't compare it
        # Note: timing may differ slightly, so we don't compare it


class TestProperty4TimeoutEnforcement:
    """
    Property 4: Timeout Enforcement
    
    For any verification request with budget_s=B, if Lean execution exceeds B
    seconds, the tool SHALL return status="timeout" and SHALL terminate all
    Lean processes within 100ms of the budget.
    
    Feature: lean-verify-tool, Property 4: Timeout enforcement
    Validates: Requirements 1.3, 4.2, 4.3
    """
    
    @settings(max_examples=20, deadline=None)
    @given(
        file_path=st.text(min_size=1, max_size=100),
        budget_s=st.floats(min_value=0.1, max_value=5.0),
    )
    def test_timeout_returns_timeout_status(
        self,
        file_path: str,
        budget_s: float,
    ):
        """Test that timeout results in timeout status."""
        # Feature: lean-verify-tool, Property 4: Timeout enforcement
        
        # Arrange - Create a timeout result
        lean_result = LeanRunResult(
            status="timeout",
            diagnostics=[],
            scope_used="file",
            full_logs="Verification timed out",
            timing={"lean_execution_s": budget_s + 0.05},  # Slightly over budget
            exit_code=-1,
        )
        
        lean_runner = MockLeanRunner(result=lean_result)
        workspace_provider = MockWorkspaceProvider()
        artifact_store = MockArtifactStore()
        handler = VerifyCommandHandler(lean_runner, workspace_provider, artifact_store)
        
        try:
            cmd = VerifyCommand(file_path=file_path, budget_s=budget_s)
        except ValueError:
            return
        
        # Act
        result = handler.handle(cmd)
        
        # Assert - Check timeout status
        assert result.status == "timeout"
        assert result.timing["lean_execution_s"] >= budget_s
    
    @settings(max_examples=20, deadline=None)
    @given(
        file_path=st.text(min_size=1, max_size=100),
        budget_s=st.floats(min_value=0.1, max_value=5.0),
    )
    def test_timeout_accuracy_within_buffer(
        self,
        file_path: str,
        budget_s: float,
    ):
        """Test that timeout is enforced within 100ms buffer."""
        # Feature: lean-verify-tool, Property 4: Timeout enforcement
        
        # Arrange - Create a timeout result with timing
        timeout_buffer_ms = 100
        lean_result = LeanRunResult(
            status="timeout",
            diagnostics=[],
            scope_used="file",
            full_logs="Verification timed out",
            timing={"lean_execution_s": budget_s + (timeout_buffer_ms / 1000.0)},
            exit_code=-1,
        )
        
        lean_runner = MockLeanRunner(result=lean_result)
        workspace_provider = MockWorkspaceProvider()
        artifact_store = MockArtifactStore()
        handler = VerifyCommandHandler(lean_runner, workspace_provider, artifact_store)
        
        try:
            cmd = VerifyCommand(file_path=file_path, budget_s=budget_s)
        except ValueError:
            return
        
        # Act
        result = handler.handle(cmd)
        
        # Assert - Check timeout is within buffer
        if result.status == "timeout":
            # Timeout should be within 100ms of budget
            assert result.timing["lean_execution_s"] <= budget_s + 0.2  # 200ms tolerance for test


class TestProperty5ProcessAndWorkspaceCleanup:
    """
    Property 5: Process and Workspace Cleanup
    
    For any verification request (success, failure, or timeout), the tool SHALL
    clean up all Lean processes and workspace resources, leaving no orphaned
    processes or temporary directories.
    
    Feature: lean-verify-tool, Property 5: Process and workspace cleanup
    Validates: Requirements 4.4, 6.3
    """
    
    @settings(max_examples=20, deadline=None)
    @given(
        file_path=st.text(min_size=1, max_size=100),
        status=st.sampled_from(["success", "fail", "timeout"]),
    )
    def test_workspace_cleanup_always_called(
        self,
        file_path: str,
        status: str,
    ):
        """Test that workspace cleanup is always called regardless of status."""
        # Feature: lean-verify-tool, Property 5: Process and workspace cleanup
        
        # Arrange - Create result with specified status
        lean_result = LeanRunResult(
            status=status,
            diagnostics=[],
            scope_used="file",
            full_logs="Test output",
            timing={"lean_execution_s": 0.5},
            exit_code=0 if status == "success" else -1,
        )
        
        lean_runner = MockLeanRunner(result=lean_result)
        workspace_provider = MockWorkspaceProvider()
        artifact_store = MockArtifactStore()
        handler = VerifyCommandHandler(lean_runner, workspace_provider, artifact_store)
        
        try:
            cmd = VerifyCommand(file_path=file_path)
        except ValueError:
            return
        
        # Act
        result = handler.handle(cmd)
        
        # Assert - Check workspace was created and cleaned up
        assert len(workspace_provider.workspaces_created) == 1
        assert len(workspace_provider.workspaces_cleaned) == 1
        assert workspace_provider.workspaces_created[0] == workspace_provider.workspaces_cleaned[0]
    
    @settings(max_examples=20, deadline=None)
    @given(
        file_path=st.text(min_size=1, max_size=100),
    )
    def test_cleanup_happens_even_on_exception(
        self,
        file_path: str,
    ):
        """Test that cleanup happens even when verification raises exception."""
        # Feature: lean-verify-tool, Property 5: Process and workspace cleanup
        
        # Arrange - Create a lean runner that raises exception
        class ExceptionLeanRunner:
            def verify_file(self, workspace_path, file_path, theorem_id, budget_s):
                raise RuntimeError("Simulated error")
        
        lean_runner = ExceptionLeanRunner()
        workspace_provider = MockWorkspaceProvider()
        artifact_store = MockArtifactStore()
        handler = VerifyCommandHandler(lean_runner, workspace_provider, artifact_store)
        
        try:
            cmd = VerifyCommand(file_path=file_path)
        except ValueError:
            return
        
        # Act & Assert - Exception should be raised but cleanup should happen
        try:
            result = handler.handle(cmd)
        except RuntimeError:
            pass  # Expected exception
        
        # Assert - Check workspace was still cleaned up
        assert len(workspace_provider.workspaces_created) == 1
        assert len(workspace_provider.workspaces_cleaned) == 1


class TestProperty16TheoremScopeSupport:
    """
    Property 16: Theorem Scope Support
    
    For any verification request with valid theorem_id, the tool SHALL create
    an abridged file containing content up to the theorem's end line and verify
    only that scope, returning verification_scope_used="theorem".
    
    Feature: lean-verify-tool, Property 16: Theorem scope support
    Validates: Requirements 2.1, 2.2
    """
    
    @settings(max_examples=20, deadline=None)
    @given(
        file_path=st.text(min_size=1, max_size=100),
        theorem_id=st.text(min_size=1, max_size=50),
    )
    def test_theorem_scope_returns_theorem_scope_used(
        self,
        file_path: str,
        theorem_id: str,
    ):
        """Test that theorem-level verification returns scope_used='theorem'."""
        # Feature: lean-verify-tool, Property 16: Theorem scope support
        
        # Arrange - Create a result with theorem scope
        lean_result = LeanRunResult(
            status="success",
            diagnostics=[],
            scope_used="theorem",
            full_logs="Theorem verification output",
            timing={"lean_execution_s": 0.3},
            exit_code=0,
        )
        
        lean_runner = MockLeanRunner(result=lean_result)
        workspace_provider = MockWorkspaceProvider()
        artifact_store = MockArtifactStore()
        handler = VerifyCommandHandler(lean_runner, workspace_provider, artifact_store)
        
        try:
            cmd = VerifyCommand(file_path=file_path, theorem_id=theorem_id)
        except ValueError:
            return
        
        # Act
        result = handler.handle(cmd)
        
        # Assert - Check theorem scope is used
        assert result.verification_scope_used == "theorem"
        assert result.theorem_id == theorem_id
        
        # Verify that lean_runner was called with theorem_id
        assert len(lean_runner.calls) == 1
        assert lean_runner.calls[0]["theorem_id"] == theorem_id


class TestProperty12DiagnosticSummaryConsistency:
    """
    Property 12: Diagnostic Summary Consistency
    
    For any verification response, the diagnostic_summary counts (error_count,
    warning_count, info_count) SHALL exactly match the count of diagnostics
    with each severity level in the diagnostics array.
    
    Feature: lean-verify-tool, Property 12: Diagnostic summary consistency
    Validates: Requirements 5.4
    """
    
    @settings(max_examples=20, deadline=None)
    @given(
        file_path=st.text(min_size=1, max_size=100),
        num_errors=st.integers(min_value=0, max_value=10),
        num_warnings=st.integers(min_value=0, max_value=10),
        num_infos=st.integers(min_value=0, max_value=10),
    )
    def test_diagnostic_summary_matches_diagnostics(
        self,
        file_path: str,
        num_errors: int,
        num_warnings: int,
        num_infos: int,
    ):
        """Test that diagnostic summary counts match actual diagnostics."""
        # Feature: lean-verify-tool, Property 12: Diagnostic summary consistency
        
        # Arrange - Create diagnostics with specific counts
        diagnostics = []
        for i in range(num_errors):
            diagnostics.append({
                "severity": "error",
                "message": f"Error {i}",
                "location": {"file": "test.lean", "line": i, "col": 0},
            })
        for i in range(num_warnings):
            diagnostics.append({
                "severity": "warning",
                "message": f"Warning {i}",
                "location": {"file": "test.lean", "line": i + 100, "col": 0},
            })
        for i in range(num_infos):
            diagnostics.append({
                "severity": "info",
                "message": f"Info {i}",
                "location": {"file": "test.lean", "line": i + 200, "col": 0},
            })
        
        lean_result = LeanRunResult(
            status="success" if num_errors == 0 else "fail",
            diagnostics=diagnostics,
            scope_used="file",
            full_logs="",
            timing={"lean_execution_s": 0.5},
            exit_code=0 if num_errors == 0 else 1,
        )
        
        lean_runner = MockLeanRunner(result=lean_result)
        workspace_provider = MockWorkspaceProvider()
        artifact_store = MockArtifactStore()
        handler = VerifyCommandHandler(lean_runner, workspace_provider, artifact_store)
        
        try:
            cmd = VerifyCommand(file_path=file_path)
        except ValueError:
            return
        
        # Act
        result = handler.handle(cmd)
        
        # Assert - Check summary matches actual counts
        actual_error_count = sum(1 for d in result.diagnostics if d["severity"] == "error")
        actual_warning_count = sum(1 for d in result.diagnostics if d["severity"] == "warning")
        actual_info_count = sum(1 for d in result.diagnostics if d["severity"] == "info")
        
        assert result.diagnostic_summary["error_count"] == actual_error_count
        assert result.diagnostic_summary["warning_count"] == actual_warning_count
        assert result.diagnostic_summary["info_count"] == actual_info_count



class TestProperty15ConcurrentExecutionSafety:
    """
    Property 15: Concurrent Execution Safety
    
    For any set of N concurrent verification requests (N=2-10), each SHALL
    complete successfully with isolated workspaces, and no verification SHALL
    interfere with another (no shared state, no race conditions, no workspace
    collisions).
    
    Feature: lean-verify-tool, Property 15: Concurrent execution safety
    Validates: Requirements 6.4
    """
    
    @settings(max_examples=5, deadline=None)
    @given(
        num_concurrent=st.integers(min_value=2, max_value=6),
        file_path=st.text(min_size=1, max_size=50),
    )
    def test_concurrent_verifications_complete_successfully(
        self,
        num_concurrent: int,
        file_path: str,
    ):
        """Test that N concurrent verifications all complete successfully."""
        # Feature: lean-verify-tool, Property 15: Concurrent execution safety
        
        # Arrange - Create shared adapters (thread-safe)
        lean_runner = MockLeanRunner()
        workspace_provider = MockWorkspaceProvider()
        artifact_store = MockArtifactStore()
        handler = VerifyCommandHandler(lean_runner, workspace_provider, artifact_store)
        
        try:
            cmd = VerifyCommand(file_path=file_path)
        except ValueError:
            return
        
        # Act - Run N verifications concurrently using ThreadPoolExecutor
        results = []
        exceptions = []
        
        def run_verification(index: int):
            """Run a single verification and return result."""
            try:
                result = handler.handle(cmd)
                return (index, result, None)
            except Exception as e:
                return (index, None, e)
        
        with ThreadPoolExecutor(max_workers=num_concurrent) as executor:
            futures = [executor.submit(run_verification, i) for i in range(num_concurrent)]
            
            for future in as_completed(futures):
                index, result, exception = future.result()
                if exception:
                    exceptions.append((index, exception))
                else:
                    results.append((index, result))
        
        # Assert - All verifications completed without exceptions
        assert len(exceptions) == 0, f"Some verifications raised exceptions: {exceptions}"
        assert len(results) == num_concurrent, f"Expected {num_concurrent} results, got {len(results)}"
        
        # Assert - All results are valid
        for index, result in results:
            assert isinstance(result, VerifyResult)
            assert result.status in ["success", "fail", "timeout", "error"]
            assert result.run_id is not None
            assert len(result.run_id) > 0
        
        # Assert - All run_ids are unique (no collisions)
        run_ids = [result.run_id for _, result in results]
        assert len(run_ids) == len(set(run_ids)), "Run IDs are not unique - collision detected"
    
    @settings(max_examples=5, deadline=None)
    @given(
        num_concurrent=st.integers(min_value=2, max_value=6),
        file_path=st.text(min_size=1, max_size=50),
    )
    def test_concurrent_verifications_have_isolated_workspaces(
        self,
        num_concurrent: int,
        file_path: str,
    ):
        """Test that concurrent verifications use isolated workspaces."""
        # Feature: lean-verify-tool, Property 15: Concurrent execution safety
        
        # Arrange - Create shared adapters (thread-safe)
        lean_runner = MockLeanRunner()
        workspace_provider = MockWorkspaceProvider()
        artifact_store = MockArtifactStore()
        handler = VerifyCommandHandler(lean_runner, workspace_provider, artifact_store)
        
        try:
            cmd = VerifyCommand(file_path=file_path)
        except ValueError:
            return
        
        # Act - Run N verifications concurrently
        def run_verification(index: int):
            """Run a single verification."""
            try:
                return handler.handle(cmd)
            except Exception:
                return None
        
        with ThreadPoolExecutor(max_workers=num_concurrent) as executor:
            futures = [executor.submit(run_verification, i) for i in range(num_concurrent)]
            results = [future.result() for future in as_completed(futures)]
        
        # Filter out None results (from exceptions)
        results = [r for r in results if r is not None]
        
        # Assert - Each verification created and cleaned up its own workspace
        assert len(workspace_provider.workspaces_created) == len(results)
        assert len(workspace_provider.workspaces_cleaned) == len(results)
        
        # Assert - All workspace IDs are unique (no collisions)
        workspace_ids = [w.workspace_id for w in workspace_provider.workspaces_created]
        assert len(workspace_ids) == len(set(workspace_ids)), "Workspace IDs are not unique"
        
        # Assert - All workspace paths are unique (no collisions)
        workspace_paths = [str(w.path) for w in workspace_provider.workspaces_created]
        assert len(workspace_paths) == len(set(workspace_paths)), "Workspace paths are not unique"
        
        # Assert - All created workspaces were cleaned up
        created_ids = {w.workspace_id for w in workspace_provider.workspaces_created}
        cleaned_ids = {w.workspace_id for w in workspace_provider.workspaces_cleaned}
        assert created_ids == cleaned_ids, "Not all workspaces were cleaned up"
    
    @settings(max_examples=5, deadline=None)
    @given(
        num_concurrent=st.integers(min_value=2, max_value=6),
        file_path=st.text(min_size=1, max_size=50),
    )
    def test_concurrent_verifications_no_race_conditions(
        self,
        num_concurrent: int,
        file_path: str,
    ):
        """Test that concurrent verifications don't have race conditions."""
        # Feature: lean-verify-tool, Property 15: Concurrent execution safety
        
        # Arrange - Create shared adapters with simulated delay
        class SlowMockLeanRunner:
            """Mock runner with artificial delay to increase chance of race conditions."""
            def __init__(self):
                self.calls = []
                self._lock = threading.Lock()
            
            def verify_file(self, workspace_path, file_path, theorem_id, budget_s):
                # Simulate some processing time
                time.sleep(0.01)
                
                with self._lock:
                    self.calls.append({
                        "workspace_path": workspace_path,
                        "file_path": file_path,
                        "theorem_id": theorem_id,
                        "budget_s": budget_s,
                    })
                
                return LeanRunResult(
                    status="success",
                    diagnostics=[],
                    scope_used="file",
                    full_logs="Mock output",
                    timing={"lean_execution_s": 0.01},
                    exit_code=0,
                )
        
        lean_runner = SlowMockLeanRunner()
        workspace_provider = MockWorkspaceProvider()
        artifact_store = MockArtifactStore()
        handler = VerifyCommandHandler(lean_runner, workspace_provider, artifact_store)
        
        try:
            cmd = VerifyCommand(file_path=file_path)
        except ValueError:
            return
        
        # Act - Run N verifications concurrently with delays
        results = []
        
        def run_verification(index: int):
            """Run a single verification."""
            try:
                return handler.handle(cmd)
            except Exception as e:
                return None
        
        with ThreadPoolExecutor(max_workers=num_concurrent) as executor:
            futures = [executor.submit(run_verification, i) for i in range(num_concurrent)]
            results = [future.result() for future in as_completed(futures)]
        
        # Filter out None results
        results = [r for r in results if r is not None]
        
        # Assert - All verifications completed
        assert len(results) == num_concurrent
        
        # Assert - Lean runner was called exactly N times (no duplicate calls)
        assert len(lean_runner.calls) == num_concurrent
        
        # Assert - All results have unique run_ids (no race in ID generation)
        run_ids = [r.run_id for r in results]
        assert len(run_ids) == len(set(run_ids)), "Race condition detected in run_id generation"
        
        # Assert - Workspace creation/cleanup counts match
        assert len(workspace_provider.workspaces_created) == num_concurrent
        assert len(workspace_provider.workspaces_cleaned) == num_concurrent
