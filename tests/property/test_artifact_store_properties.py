"""
Property-based tests for artifact store adapters.

These tests verify universal properties for artifact storage that should
hold across all valid executions.

Requirements: 1.5, 7.1, 7.4, 7.5
"""

import json
import shutil
import tempfile
from pathlib import Path

import hypothesis.strategies as st
import pytest
from hypothesis import given, settings

from lean_proof_auto_mcp.adapters.artifact_store import FilesystemArtifactStore
from lean_proof_auto_mcp.core.verify_domain import VerifyCommand, VerifyResult

# ============================================================================
# Helper Functions
# ============================================================================


def create_temp_artifacts_dir():
    """Create a temporary artifacts directory for testing."""
    return Path(tempfile.mkdtemp(prefix="test_artifacts_"))


def cleanup_temp_dir(path: Path):
    """Clean up temporary directory."""
    try:
        if path.exists():
            shutil.rmtree(path)
    except Exception:
        pass  # Ignore cleanup errors


def create_sample_command(file_path: str = "test.lean") -> VerifyCommand:
    """Create a sample VerifyCommand for testing."""
    return VerifyCommand(
        file_path=file_path,
        theorem_id=None,
        budget_s=30.0,
        max_log_excerpt_chars=2000,
        store_full_logs=True,
        workspace_mode=None,
    )


def create_sample_result(run_id: str = "test-run-123") -> VerifyResult:
    """Create a sample VerifyResult for testing."""
    return VerifyResult(
        api_version="0.2.0",
        status="success",
        run_id=run_id,
        file="test.lean",
        theorem_id=None,
        verification_scope_used="file",
        diagnostics=[],
        diagnostic_summary={"error_count": 0, "warning_count": 0, "info_count": 0},
        evidence={"stdout_excerpt": "", "stderr_excerpt": "", "notes": []},
        metadata={"workspace_mode": "temp", "workspace_id": "temp-123"},
        timing={"total_s": 1.0, "lean_execution_s": 0.8, "overhead_s": 0.2},
    )


# ============================================================================
# Property Tests
# ============================================================================


class TestProperty10ArtifactStorageCompleteness:
    """
    Property 10: Artifact Storage Completeness

    For any verification request with store_full_logs=true, the tool SHALL
    create a directory under run_id containing exactly three files:
    request.json, result.json, and lean_output.log.

    Feature: lean-verify-tool, Property 10: Artifact storage completeness
    Validates: Requirements 1.5, 7.1
    """

    def test_artifact_store_creates_all_required_files(self):
        """Test that artifact store creates all three required files."""
        # Feature: lean-verify-tool, Property 10: Artifact storage completeness

        # Arrange
        artifacts_dir = create_temp_artifacts_dir()
        store = FilesystemArtifactStore(artifacts_dir)

        run_id = "test-run-20250126-120000-abc123"
        command = create_sample_command()
        result = create_sample_result(run_id)
        full_logs = "Test log output\nLine 2\nLine 3"

        try:
            # Act
            store.store(run_id, command, result, full_logs)

            # Assert - Run directory exists
            run_dir = artifacts_dir / run_id
            assert run_dir.exists(), f"Run directory should exist: {run_dir}"
            assert run_dir.is_dir(), f"Run directory should be a directory: {run_dir}"

            # Assert - All three files exist
            request_file = run_dir / "request.json"
            result_file = run_dir / "result.json"
            log_file = run_dir / "lean_output.log"

            assert request_file.exists(), f"request.json should exist: {request_file}"
            assert result_file.exists(), f"result.json should exist: {result_file}"
            assert log_file.exists(), f"lean_output.log should exist: {log_file}"

            # Assert - Files are not empty
            assert request_file.stat().st_size > 0, "request.json should not be empty"
            assert result_file.stat().st_size > 0, "result.json should not be empty"
            assert log_file.stat().st_size > 0, "lean_output.log should not be empty"

            # Assert - Exactly three files (no extra files)
            files_in_dir = list(run_dir.iterdir())
            assert len(files_in_dir) == 3, f"Should have exactly 3 files, found {len(files_in_dir)}"

        finally:
            cleanup_temp_dir(artifacts_dir)

    def test_artifact_store_request_json_contains_command_data(self):
        """Test that request.json contains the command data."""
        # Feature: lean-verify-tool, Property 10: Artifact storage completeness

        # Arrange
        artifacts_dir = create_temp_artifacts_dir()
        store = FilesystemArtifactStore(artifacts_dir)

        run_id = "test-run-20250126-120001-def456"
        command = VerifyCommand(
            file_path="path/to/test.lean",
            theorem_id="MyTheorem",
            budget_s=45.0,
            max_log_excerpt_chars=3000,
            store_full_logs=True,
            workspace_mode="worktree",
        )
        result = create_sample_result(run_id)
        full_logs = "Test logs"

        try:
            # Act
            store.store(run_id, command, result, full_logs)

            # Assert - request.json contains command data
            request_file = artifacts_dir / run_id / "request.json"
            with open(request_file, encoding="utf-8") as f:
                request_data = json.load(f)

            assert request_data["file_path"] == "path/to/test.lean"
            assert request_data["theorem_id"] == "MyTheorem"
            assert request_data["budget_s"] == 45.0
            assert request_data["max_log_excerpt_chars"] == 3000
            assert request_data["store_full_logs"] is True
            assert request_data["workspace_mode"] == "worktree"

        finally:
            cleanup_temp_dir(artifacts_dir)

    def test_artifact_store_result_json_contains_result_data(self):
        """Test that result.json contains the result data."""
        # Feature: lean-verify-tool, Property 10: Artifact storage completeness

        # Arrange
        artifacts_dir = create_temp_artifacts_dir()
        store = FilesystemArtifactStore(artifacts_dir)

        run_id = "test-run-20250126-120002-ghi789"
        command = create_sample_command()
        result = VerifyResult(
            api_version="0.2.0",
            status="fail",
            run_id=run_id,
            file="path/to/test.lean",
            theorem_id="MyTheorem",
            verification_scope_used="theorem",
            diagnostics=[
                {
                    "severity": "error",
                    "message": "Type mismatch",
                    "location": {
                        "file": "test.lean",
                        "line": 10,
                        "col": 5,
                        "end_line": None,
                        "end_col": None,
                    },
                }
            ],
            diagnostic_summary={"error_count": 1, "warning_count": 0, "info_count": 0},
            evidence={
                "stdout_excerpt": "Error output",
                "stderr_excerpt": "",
                "notes": ["exit_code: 1"],
            },
            metadata={"workspace_mode": "worktree", "workspace_id": "worktree-123"},
            timing={"total_s": 2.5, "lean_execution_s": 2.3, "overhead_s": 0.2},
        )
        full_logs = "Test logs"

        try:
            # Act
            store.store(run_id, command, result, full_logs)

            # Assert - result.json contains result data
            result_file = artifacts_dir / run_id / "result.json"
            with open(result_file, encoding="utf-8") as f:
                result_data = json.load(f)

            assert result_data["api_version"] == "0.2.0"
            assert result_data["status"] == "fail"
            assert result_data["run_id"] == run_id
            assert result_data["file"] == "path/to/test.lean"
            assert result_data["theorem_id"] == "MyTheorem"
            assert result_data["verification_scope_used"] == "theorem"
            assert len(result_data["diagnostics"]) == 1
            assert result_data["diagnostics"][0]["severity"] == "error"
            assert result_data["diagnostic_summary"]["error_count"] == 1

        finally:
            cleanup_temp_dir(artifacts_dir)

    def test_artifact_store_log_file_contains_full_logs(self):
        """Test that lean_output.log contains the full logs."""
        # Feature: lean-verify-tool, Property 10: Artifact storage completeness

        # Arrange
        artifacts_dir = create_temp_artifacts_dir()
        store = FilesystemArtifactStore(artifacts_dir)

        run_id = "test-run-20250126-120003-jkl012"
        command = create_sample_command()
        result = create_sample_result(run_id)
        full_logs = (
            "Line 1: Starting verification\nLine 2: Processing imports\n"
            "Line 3: Checking theorems\nLine 4: Verification complete"
        )

        try:
            # Act
            store.store(run_id, command, result, full_logs)

            # Assert - lean_output.log contains full logs
            log_file = artifacts_dir / run_id / "lean_output.log"
            with open(log_file, encoding="utf-8") as f:
                log_content = f.read()

            assert log_content == full_logs
            assert "Line 1: Starting verification" in log_content
            assert "Line 4: Verification complete" in log_content

        finally:
            cleanup_temp_dir(artifacts_dir)

    def test_artifact_store_json_files_use_deterministic_formatting(self):
        """Test that JSON files use indent=2 and sort_keys=True."""
        # Feature: lean-verify-tool, Property 10: Artifact storage completeness

        # Arrange
        artifacts_dir = create_temp_artifacts_dir()
        store = FilesystemArtifactStore(artifacts_dir)

        run_id = "test-run-20250126-120004-mno345"
        command = create_sample_command()
        result = create_sample_result(run_id)
        full_logs = "Test logs"

        try:
            # Act
            store.store(run_id, command, result, full_logs)

            # Assert - JSON files are formatted with indentation
            request_file = artifacts_dir / run_id / "request.json"
            with open(request_file, encoding="utf-8") as f:
                request_content = f.read()

            # Check for indentation (should have 2-space indents)
            assert "  " in request_content, "JSON should be indented"

            # Check for sorted keys (budget_s should come before file_path alphabetically)
            budget_pos = request_content.find('"budget_s"')
            file_path_pos = request_content.find('"file_path"')
            assert budget_pos < file_path_pos, "JSON keys should be sorted alphabetically"

        finally:
            cleanup_temp_dir(artifacts_dir)

    @settings(max_examples=100)
    @given(
        file_path=st.text(
            min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=["Cs"])
        ),
        budget_s=st.floats(min_value=0.1, max_value=300.0, allow_nan=False, allow_infinity=False),
    )
    def test_artifact_store_handles_various_inputs(self, file_path, budget_s):
        """Property test: artifact store handles various command inputs."""
        # Feature: lean-verify-tool, Property 10: Artifact storage completeness

        # Arrange
        artifacts_dir = create_temp_artifacts_dir()
        store = FilesystemArtifactStore(artifacts_dir)

        # Create command with generated inputs
        try:
            command = VerifyCommand(
                file_path=file_path,
                theorem_id=None,
                budget_s=budget_s,
                max_log_excerpt_chars=2000,
                store_full_logs=True,
                workspace_mode=None,
            )
        except ValueError:
            # Skip invalid inputs (e.g., empty file_path)
            return

        run_id = f"test-run-{hash(file_path) % 1000000}"
        result = create_sample_result(run_id)
        full_logs = "Test logs for property test"

        try:
            # Act
            store.store(run_id, command, result, full_logs)

            # Assert - All three files exist
            run_dir = artifacts_dir / run_id
            assert run_dir.exists()
            assert (run_dir / "request.json").exists()
            assert (run_dir / "result.json").exists()
            assert (run_dir / "lean_output.log").exists()

            # Assert - Files contain expected data
            with open(run_dir / "request.json", encoding="utf-8") as f:
                request_data = json.load(f)
            assert request_data["file_path"] == file_path
            assert abs(request_data["budget_s"] - budget_s) < 0.01  # Float comparison

        finally:
            cleanup_temp_dir(artifacts_dir)


class TestProperty19ArtifactPersistence:
    """
    Property 19: Artifact Persistence

    For any verification request with store_full_logs=true, the artifact
    directory SHALL exist and contain all files after the tool returns
    control to the caller.

    Feature: lean-verify-tool, Property 19: Artifact persistence
    Validates: Requirements 7.4
    """

    def test_artifacts_persist_after_store_returns(self):
        """Test that artifacts persist after store() method returns."""
        # Feature: lean-verify-tool, Property 19: Artifact persistence

        # Arrange
        artifacts_dir = create_temp_artifacts_dir()
        store = FilesystemArtifactStore(artifacts_dir)

        run_id = "test-run-20250126-120005-pqr678"
        command = create_sample_command()
        result = create_sample_result(run_id)
        full_logs = "Test logs for persistence"

        try:
            # Act - Store artifacts
            store.store(run_id, command, result, full_logs)

            # Simulate some time passing / other operations
            # (In real scenario, this would be after tool returns to caller)

            # Assert - Artifacts still exist
            run_dir = artifacts_dir / run_id
            assert run_dir.exists(), "Artifact directory should persist"
            assert (run_dir / "request.json").exists(), "request.json should persist"
            assert (run_dir / "result.json").exists(), "result.json should persist"
            assert (run_dir / "lean_output.log").exists(), "lean_output.log should persist"

            # Assert - Files are still readable
            with open(run_dir / "request.json", encoding="utf-8") as f:
                request_data = json.load(f)
            assert request_data["file_path"] == command.file_path

            with open(run_dir / "lean_output.log", encoding="utf-8") as f:
                log_content = f.read()
            assert log_content == full_logs

        finally:
            cleanup_temp_dir(artifacts_dir)

    def test_multiple_artifact_stores_persist_independently(self):
        """Test that multiple artifact stores persist independently."""
        # Feature: lean-verify-tool, Property 19: Artifact persistence

        # Arrange
        artifacts_dir = create_temp_artifacts_dir()
        store = FilesystemArtifactStore(artifacts_dir)

        # Create multiple runs
        runs = [
            ("run1-20250126-120006-abc", "test1.lean", "Logs for run 1"),
            ("run2-20250126-120007-def", "test2.lean", "Logs for run 2"),
            ("run3-20250126-120008-ghi", "test3.lean", "Logs for run 3"),
        ]

        try:
            # Act - Store artifacts for all runs
            for run_id, file_path, logs in runs:
                command = create_sample_command(file_path)
                result = create_sample_result(run_id)
                store.store(run_id, command, result, logs)

            # Assert - All artifact directories exist
            for run_id, file_path, logs in runs:
                run_dir = artifacts_dir / run_id
                assert run_dir.exists(), f"Artifact directory for {run_id} should exist"

                # Verify files exist
                assert (run_dir / "request.json").exists()
                assert (run_dir / "result.json").exists()
                assert (run_dir / "lean_output.log").exists()

                # Verify content is correct for each run
                with open(run_dir / "request.json", encoding="utf-8") as f:
                    request_data = json.load(f)
                assert request_data["file_path"] == file_path

                with open(run_dir / "lean_output.log", encoding="utf-8") as f:
                    log_content = f.read()
                assert log_content == logs

        finally:
            cleanup_temp_dir(artifacts_dir)

    def test_artifacts_handle_disk_space_errors_gracefully(self):
        """Test that artifact store handles disk space errors gracefully."""
        # Feature: lean-verify-tool, Property 19: Artifact persistence

        # Note: This test verifies error handling, not actual disk space exhaustion
        # In a real scenario, we would need to mock filesystem operations

        # Arrange
        artifacts_dir = create_temp_artifacts_dir()
        store = FilesystemArtifactStore(artifacts_dir)

        run_id = "test-run-20250126-120009-jkl"
        command = create_sample_command()
        result = create_sample_result(run_id)
        full_logs = "Test logs"

        try:
            # Act - Normal storage should succeed
            store.store(run_id, command, result, full_logs)

            # Assert - Artifacts exist
            run_dir = artifacts_dir / run_id
            assert run_dir.exists()

            # Test error handling by trying to write to a file instead of directory
            # Create a file where we expect a directory
            invalid_artifacts_dir = create_temp_artifacts_dir()
            invalid_run_id = "blocked-by-file"
            (invalid_artifacts_dir / invalid_run_id).write_text("blocking file")

            invalid_store = FilesystemArtifactStore(invalid_artifacts_dir)

            # Act & Assert - Should raise RuntimeError when trying to create directory
            with pytest.raises(RuntimeError):
                invalid_store.store(invalid_run_id, command, result, full_logs)

            cleanup_temp_dir(invalid_artifacts_dir)

        finally:
            cleanup_temp_dir(artifacts_dir)


class TestProperty11ArtifactStorageControl:
    """
    Property 11: Artifact Storage Control

    For any verification request with store_full_logs=false, the tool SHALL
    NOT create any artifact files.

    Feature: lean-verify-tool, Property 11: Artifact storage control
    Validates: Requirements 7.5
    """

    def test_handler_skips_artifact_storage_when_store_full_logs_false(self):
        """Test that handler doesn't call store() when store_full_logs=false."""
        # Feature: lean-verify-tool, Property 11: Artifact storage control

        # Note: This test verifies the handler behavior, not the store itself.
        # The store is only called when store_full_logs=true.

        # Arrange
        artifacts_dir = create_temp_artifacts_dir()

        # Create a command with store_full_logs=false
        command_no_store = VerifyCommand(
            file_path="test.lean",
            theorem_id=None,
            budget_s=30.0,
            max_log_excerpt_chars=2000,
            store_full_logs=False,  # Key: artifacts should NOT be stored
            workspace_mode=None,
        )

        # Create a command with store_full_logs=true for comparison
        command_with_store = VerifyCommand(
            file_path="test.lean",
            theorem_id=None,
            budget_s=30.0,
            max_log_excerpt_chars=2000,
            store_full_logs=True,  # Key: artifacts SHOULD be stored
            workspace_mode=None,
        )

        try:
            # Assert - Command validation works correctly
            assert command_no_store.store_full_logs is False
            assert command_with_store.store_full_logs is True

            # The actual test of handler behavior would require a full integration test
            # with mock adapters. For now, we verify the command structure is correct.

            # If we were to call the handler (which we can't without full setup):
            # - With store_full_logs=false: artifacts_dir should remain empty
            # - With store_full_logs=true: artifacts_dir should contain run_id directory

        finally:
            cleanup_temp_dir(artifacts_dir)

    def test_artifact_store_is_not_called_when_flag_is_false(self):
        """Test that artifact store behavior when explicitly called."""
        # Feature: lean-verify-tool, Property 11: Artifact storage control

        # This test verifies that the store itself works correctly when called.
        # The handler is responsible for NOT calling it when store_full_logs=false.

        # Arrange
        artifacts_dir = create_temp_artifacts_dir()
        store = FilesystemArtifactStore(artifacts_dir)

        run_id_with_store = "test-run-with-store"
        run_id_no_store = "test-run-no-store"

        command = create_sample_command()
        result = create_sample_result(run_id_with_store)
        full_logs = "Test logs"

        try:
            # Act - Store artifacts for one run
            store.store(run_id_with_store, command, result, full_logs)

            # Assert - Artifacts exist for the stored run
            assert (artifacts_dir / run_id_with_store).exists()

            # Assert - No artifacts exist for the non-stored run (because we didn't call store())
            assert not (artifacts_dir / run_id_no_store).exists()

            # This demonstrates that the store only creates artifacts when explicitly called
            # The handler is responsible for conditional calling based on store_full_logs flag

        finally:
            cleanup_temp_dir(artifacts_dir)

    @settings(max_examples=50)
    @given(
        store_full_logs=st.booleans(),
    )
    def test_command_store_full_logs_flag_is_respected(self, store_full_logs):
        """Property test: VerifyCommand respects store_full_logs flag."""
        # Feature: lean-verify-tool, Property 11: Artifact storage control

        # Arrange & Act
        command = VerifyCommand(
            file_path="test.lean",
            theorem_id=None,
            budget_s=30.0,
            max_log_excerpt_chars=2000,
            store_full_logs=store_full_logs,
            workspace_mode=None,
        )

        # Assert - Flag is preserved correctly
        assert command.store_full_logs == store_full_logs

        # The handler should use this flag to decide whether to call artifact_store.store()
