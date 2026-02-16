"""Unit tests for result collection module.

Tests validate result recording, persistence, aggregation, and baseline comparison
functionality of the ResultCollector component.
"""

import json
import threading
import time
from pathlib import Path

import pytest
from result_collector import (
    ResultCollector,
    ToolResult,
)


class TestToolResult:
    """Test ToolResult dataclass."""

    def test_tool_result_is_frozen(self):
        """Test that ToolResult is immutable."""
        result = ToolResult(
            tool="verify",
            file_path="/path/to/file.lean",
            theorem_id="theorem1",
            mode="aesop",
            status="success",
            elapsed_ms=123.45,
            raw_response={"result": "ok"},
            timestamp="2024-01-01T12:00:00",
            domain="Algebra",
            subdomain="Group",
        )

        with pytest.raises(AttributeError):
            result.status = "failure"

    def test_tool_result_with_none_values(self):
        """Test ToolResult with optional None values."""
        result = ToolResult(
            tool="verify",
            file_path="/path/to/file.lean",
            theorem_id=None,
            mode=None,
            status="success",
            elapsed_ms=123.45,
            raw_response={"result": "ok"},
            timestamp="2024-01-01T12:00:00",
            domain="Algebra",
            subdomain="Group",
        )

        assert result.theorem_id is None
        assert result.mode is None


class TestResultCollectorRecording:
    """Test result recording functionality."""

    def test_record_adds_result_to_list(self):
        """Test that record() adds result to results list."""
        collector = ResultCollector()

        collector.record(
            tool="verify",
            file_path="/path/to/file.lean",
            status="success",
            elapsed_ms=123.45,
            raw_response={"result": "ok"},
            domain="Algebra",
            subdomain="Group",
        )

        assert len(collector.results) == 1
        result = collector.results[0]
        assert result.tool == "verify"
        assert result.status == "success"
        assert result.elapsed_ms == 123.45

    def test_record_with_optional_parameters(self):
        """Test record() with theorem_id and mode."""
        collector = ResultCollector()

        collector.record(
            tool="probe",
            file_path="/path/to/file.lean",
            status="success",
            elapsed_ms=200.0,
            raw_response={"result": "ok"},
            domain="Analysis",
            subdomain="Calculus",
            theorem_id="theorem1",
            mode="grind",
        )

        result = collector.results[0]
        assert result.theorem_id == "theorem1"
        assert result.mode == "grind"

    def test_timestamps_are_unique(self):
        """Test that consecutive records have different timestamps."""
        collector = ResultCollector()

        collector.record(
            tool="verify",
            file_path="/path/to/file1.lean",
            status="success",
            elapsed_ms=100.0,
            raw_response={},
            domain="Algebra",
            subdomain="Group",
        )

        # Small delay to ensure different timestamp
        time.sleep(0.001)

        collector.record(
            tool="verify",
            file_path="/path/to/file2.lean",
            status="success",
            elapsed_ms=100.0,
            raw_response={},
            domain="Algebra",
            subdomain="Group",
        )

        assert len(collector.results) == 2
        assert collector.results[0].timestamp != collector.results[1].timestamp

    def test_concurrent_recording(self):
        """Test that concurrent recording is thread-safe."""
        collector = ResultCollector()
        num_threads = 10
        records_per_thread = 10

        def record_results(thread_id: int):
            for i in range(records_per_thread):
                collector.record(
                    tool=f"tool_{thread_id}",
                    file_path=f"/path/to/file_{thread_id}_{i}.lean",
                    status="success",
                    elapsed_ms=100.0,
                    raw_response={},
                    domain="Algebra",
                    subdomain="Group",
                )

        threads = [threading.Thread(target=record_results, args=(i,)) for i in range(num_threads)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # Verify all results were recorded
        assert len(collector.results) == num_threads * records_per_thread


class TestResultCollectorPersistence:
    """Test result persistence functionality."""

    def test_save_creates_all_required_files(self, tmp_path):
        """Test that save() creates results.json, summary.json, and metadata.json."""
        collector = ResultCollector()

        collector.record(
            tool="verify",
            file_path="/path/to/file.lean",
            status="success",
            elapsed_ms=123.45,
            raw_response={"result": "ok"},
            domain="Algebra",
            subdomain="Group",
        )

        output_dir = tmp_path / "results"
        collector.save(output_dir)

        assert (output_dir / "results.json").exists()
        assert (output_dir / "summary.json").exists()
        assert (output_dir / "metadata.json").exists()

    def test_save_creates_directory_if_not_exists(self, tmp_path):
        """Test that save() creates output directory if it doesn't exist."""
        collector = ResultCollector()

        collector.record(
            tool="verify",
            file_path="/path/to/file.lean",
            status="success",
            elapsed_ms=123.45,
            raw_response={"result": "ok"},
            domain="Algebra",
            subdomain="Group",
        )

        output_dir = tmp_path / "nested" / "results"
        assert not output_dir.exists()

        collector.save(output_dir)

        assert output_dir.exists()
        assert (output_dir / "results.json").exists()

    def test_json_serialization_is_valid(self, tmp_path):
        """Test that saved JSON is valid and can be loaded."""
        collector = ResultCollector()

        collector.record(
            tool="verify",
            file_path="/path/to/file.lean",
            status="success",
            elapsed_ms=123.45,
            raw_response={"result": "ok"},
            domain="Algebra",
            subdomain="Group",
            theorem_id="theorem1",
            mode="aesop",
        )

        output_dir = tmp_path / "results"
        collector.save(output_dir)

        # Load and verify results.json
        with open(output_dir / "results.json") as f:
            results_data = json.load(f)

        assert len(results_data) == 1
        assert results_data[0]["tool"] == "verify"
        assert results_data[0]["status"] == "success"
        assert results_data[0]["theorem_id"] == "theorem1"

        # Load and verify summary.json
        with open(output_dir / "summary.json") as f:
            summary_data = json.load(f)

        assert "by_tool" in summary_data
        assert "by_domain" in summary_data
        assert "by_status" in summary_data

        # Load and verify metadata.json
        with open(output_dir / "metadata.json") as f:
            metadata = json.load(f)

        assert metadata["total_results"] == 1
        assert "generated_at" in metadata

    def test_all_results_are_saved(self, tmp_path):
        """Test that all recorded results are saved to JSON."""
        collector = ResultCollector()

        # Record multiple results
        for i in range(5):
            collector.record(
                tool=f"tool_{i}",
                file_path=f"/path/to/file_{i}.lean",
                status="success",
                elapsed_ms=100.0 * i,
                raw_response={"result": f"ok_{i}"},
                domain="Algebra",
                subdomain="Group",
            )

        output_dir = tmp_path / "results"
        collector.save(output_dir)

        with open(output_dir / "results.json") as f:
            results_data = json.load(f)

        assert len(results_data) == 5

        # Verify each result
        for i, result in enumerate(results_data):
            assert result["tool"] == f"tool_{i}"
            assert result["file_path"] == f"/path/to/file_{i}.lean"


class TestResultCollectorSummary:
    """Test summary aggregation functionality."""

    def test_summary_counts_by_tool(self):
        """Test that summary correctly aggregates by tool."""
        collector = ResultCollector()

        collector.record(
            tool="verify",
            file_path="/path/to/file1.lean",
            status="success",
            elapsed_ms=100.0,
            raw_response={},
            domain="Algebra",
            subdomain="Group",
        )

        collector.record(
            tool="verify",
            file_path="/path/to/file2.lean",
            status="failure",
            elapsed_ms=200.0,
            raw_response={},
            domain="Algebra",
            subdomain="Group",
        )

        collector.record(
            tool="probe",
            file_path="/path/to/file3.lean",
            status="success",
            elapsed_ms=150.0,
            raw_response={},
            domain="Analysis",
            subdomain="Calculus",
        )

        summary = collector.summary()

        assert summary["by_tool"]["verify"]["success"] == 1
        assert summary["by_tool"]["verify"]["failure"] == 1
        assert summary["by_tool"]["verify"]["total"] == 2
        assert summary["by_tool"]["probe"]["success"] == 1
        assert summary["by_tool"]["probe"]["total"] == 1

    def test_summary_counts_by_domain(self):
        """Test that summary correctly aggregates by domain."""
        collector = ResultCollector()

        collector.record(
            tool="verify",
            file_path="/path/to/file1.lean",
            status="success",
            elapsed_ms=100.0,
            raw_response={},
            domain="Algebra",
            subdomain="Group",
        )

        collector.record(
            tool="verify",
            file_path="/path/to/file2.lean",
            status="failure",
            elapsed_ms=200.0,
            raw_response={},
            domain="Algebra",
            subdomain="Ring",
        )

        collector.record(
            tool="probe",
            file_path="/path/to/file3.lean",
            status="success",
            elapsed_ms=150.0,
            raw_response={},
            domain="Analysis",
            subdomain="Calculus",
        )

        summary = collector.summary()

        assert summary["by_domain"]["Algebra"]["success"] == 1
        assert summary["by_domain"]["Algebra"]["failure"] == 1
        assert summary["by_domain"]["Algebra"]["total"] == 2
        assert summary["by_domain"]["Analysis"]["success"] == 1
        assert summary["by_domain"]["Analysis"]["total"] == 1

    def test_summary_counts_by_status(self):
        """Test that summary correctly aggregates by status."""
        collector = ResultCollector()

        collector.record(
            tool="verify",
            file_path="/path/to/file1.lean",
            status="success",
            elapsed_ms=100.0,
            raw_response={},
            domain="Algebra",
            subdomain="Group",
        )

        collector.record(
            tool="verify",
            file_path="/path/to/file2.lean",
            status="failure",
            elapsed_ms=200.0,
            raw_response={},
            domain="Algebra",
            subdomain="Group",
        )

        collector.record(
            tool="probe",
            file_path="/path/to/file3.lean",
            status="error",
            elapsed_ms=150.0,
            raw_response={},
            domain="Analysis",
            subdomain="Calculus",
        )

        summary = collector.summary()

        assert summary["by_status"]["success"] == 1
        assert summary["by_status"]["failure"] == 1
        assert summary["by_status"]["error"] == 1

    def test_summary_total_count(self):
        """Test that summary includes correct total count."""
        collector = ResultCollector()

        for i in range(10):
            collector.record(
                tool="verify",
                file_path=f"/path/to/file{i}.lean",
                status="success",
                elapsed_ms=100.0,
                raw_response={},
                domain="Algebra",
                subdomain="Group",
            )

        summary = collector.summary()

        assert summary["total_count"] == 10

    def test_summary_total_elapsed_ms(self):
        """Test that summary includes correct total elapsed time."""
        collector = ResultCollector()

        collector.record(
            tool="verify",
            file_path="/path/to/file1.lean",
            status="success",
            elapsed_ms=100.0,
            raw_response={},
            domain="Algebra",
            subdomain="Group",
        )

        collector.record(
            tool="verify",
            file_path="/path/to/file2.lean",
            status="success",
            elapsed_ms=200.0,
            raw_response={},
            domain="Algebra",
            subdomain="Group",
        )

        summary = collector.summary()

        assert summary["total_elapsed_ms"] == 300.0


class TestResultCollectorBaselineComparison:
    """Test baseline comparison functionality."""

    def test_compare_baseline_identifies_regressions(self, tmp_path):
        """Test that regressions (success→failure) are identified correctly."""
        # Create baseline
        baseline_data = [
            {
                "tool": "verify",
                "file_path": "/path/to/file.lean",
                "theorem_id": "theorem1",
                "mode": None,
                "status": "success",
                "elapsed_ms": 100.0,
                "raw_response": {},
                "timestamp": "2024-01-01T12:00:00",
                "domain": "Algebra",
                "subdomain": "Group",
            }
        ]

        baseline_path = tmp_path / "baseline.json"
        with open(baseline_path, "w") as f:
            json.dump(baseline_data, f)

        # Create current results with regression
        collector = ResultCollector()
        collector.record(
            tool="verify",
            file_path="/path/to/file.lean",
            status="failure",
            elapsed_ms=100.0,
            raw_response={},
            domain="Algebra",
            subdomain="Group",
            theorem_id="theorem1",
        )

        comparison = collector.compare_baseline(baseline_path)

        assert len(comparison["regressions"]) == 1
        assert comparison["regressions"][0]["tool"] == "verify"
        assert comparison["regressions"][0]["baseline_status"] == "success"
        assert comparison["regressions"][0]["current_status"] == "failure"

    def test_compare_baseline_identifies_improvements(self, tmp_path):
        """Test that improvements (failure→success) are identified correctly."""
        # Create baseline
        baseline_data = [
            {
                "tool": "verify",
                "file_path": "/path/to/file.lean",
                "theorem_id": "theorem1",
                "mode": None,
                "status": "failure",
                "elapsed_ms": 100.0,
                "raw_response": {},
                "timestamp": "2024-01-01T12:00:00",
                "domain": "Algebra",
                "subdomain": "Group",
            }
        ]

        baseline_path = tmp_path / "baseline.json"
        with open(baseline_path, "w") as f:
            json.dump(baseline_data, f)

        # Create current results with improvement
        collector = ResultCollector()
        collector.record(
            tool="verify",
            file_path="/path/to/file.lean",
            status="success",
            elapsed_ms=100.0,
            raw_response={},
            domain="Algebra",
            subdomain="Group",
            theorem_id="theorem1",
        )

        comparison = collector.compare_baseline(baseline_path)

        assert len(comparison["improvements"]) == 1
        assert comparison["improvements"][0]["tool"] == "verify"
        assert comparison["improvements"][0]["baseline_status"] == "failure"
        assert comparison["improvements"][0]["current_status"] == "success"

    def test_compare_baseline_identifies_unchanged(self, tmp_path):
        """Test that unchanged results are identified correctly."""
        # Create baseline
        baseline_data = [
            {
                "tool": "verify",
                "file_path": "/path/to/file.lean",
                "theorem_id": "theorem1",
                "mode": None,
                "status": "success",
                "elapsed_ms": 100.0,
                "raw_response": {},
                "timestamp": "2024-01-01T12:00:00",
                "domain": "Algebra",
                "subdomain": "Group",
            }
        ]

        baseline_path = tmp_path / "baseline.json"
        with open(baseline_path, "w") as f:
            json.dump(baseline_data, f)

        # Create current results with same status
        collector = ResultCollector()
        collector.record(
            tool="verify",
            file_path="/path/to/file.lean",
            status="success",
            elapsed_ms=100.0,
            raw_response={},
            domain="Algebra",
            subdomain="Group",
            theorem_id="theorem1",
        )

        comparison = collector.compare_baseline(baseline_path)

        assert len(comparison["unchanged"]) == 1
        assert comparison["unchanged"][0]["tool"] == "verify"
        assert comparison["unchanged"][0]["status"] == "success"

    def test_compare_baseline_with_mode_parameter(self, tmp_path):
        """Test baseline comparison with mode parameter."""
        # Create baseline with different modes
        baseline_data = [
            {
                "tool": "probe",
                "file_path": "/path/to/file.lean",
                "theorem_id": "theorem1",
                "mode": "aesop",
                "status": "success",
                "elapsed_ms": 100.0,
                "raw_response": {},
                "timestamp": "2024-01-01T12:00:00",
                "domain": "Algebra",
                "subdomain": "Group",
            },
            {
                "tool": "probe",
                "file_path": "/path/to/file.lean",
                "theorem_id": "theorem1",
                "mode": "grind",
                "status": "failure",
                "elapsed_ms": 100.0,
                "raw_response": {},
                "timestamp": "2024-01-01T12:00:00",
                "domain": "Algebra",
                "subdomain": "Group",
            },
        ]

        baseline_path = tmp_path / "baseline.json"
        with open(baseline_path, "w") as f:
            json.dump(baseline_data, f)

        # Create current results
        collector = ResultCollector()
        collector.record(
            tool="probe",
            file_path="/path/to/file.lean",
            status="failure",
            elapsed_ms=100.0,
            raw_response={},
            domain="Algebra",
            subdomain="Group",
            theorem_id="theorem1",
            mode="aesop",
        )
        collector.record(
            tool="probe",
            file_path="/path/to/file.lean",
            status="success",
            elapsed_ms=100.0,
            raw_response={},
            domain="Algebra",
            subdomain="Group",
            theorem_id="theorem1",
            mode="grind",
        )

        comparison = collector.compare_baseline(baseline_path)

        # aesop mode: success→failure (regression)
        assert len(comparison["regressions"]) == 1
        assert comparison["regressions"][0]["mode"] == "aesop"

        # grind mode: failure→success (improvement)
        assert len(comparison["improvements"]) == 1
        assert comparison["improvements"][0]["mode"] == "grind"

    def test_compare_baseline_raises_error_if_file_not_found(self):
        """Test that compare_baseline raises FileNotFoundError if baseline doesn't exist."""
        collector = ResultCollector()

        with pytest.raises(FileNotFoundError):
            collector.compare_baseline(Path("/nonexistent/baseline.json"))

    def test_compare_baseline_identifies_new_tests(self, tmp_path):
        """Test that new tests are identified correctly."""
        # Create baseline with one test
        baseline_data = [
            {
                "tool": "verify",
                "file_path": "/path/to/file1.lean",
                "theorem_id": None,
                "mode": None,
                "status": "success",
                "elapsed_ms": 100.0,
                "raw_response": {},
                "timestamp": "2024-01-01T12:00:00",
                "domain": "Algebra",
                "subdomain": "Group",
            }
        ]

        baseline_path = tmp_path / "baseline.json"
        with open(baseline_path, "w") as f:
            json.dump(baseline_data, f)

        # Create current results with additional test
        collector = ResultCollector()
        collector.record(
            tool="verify",
            file_path="/path/to/file1.lean",
            status="success",
            elapsed_ms=100.0,
            raw_response={},
            domain="Algebra",
            subdomain="Group",
        )
        collector.record(
            tool="verify",
            file_path="/path/to/file2.lean",
            status="success",
            elapsed_ms=100.0,
            raw_response={},
            domain="Algebra",
            subdomain="Group",
        )

        comparison = collector.compare_baseline(baseline_path)

        assert len(comparison["new_tests"]) == 1
        assert comparison["new_tests"][0]["file_path"] == "/path/to/file2.lean"

    def test_compare_baseline_identifies_removed_tests(self, tmp_path):
        """Test that removed tests are identified correctly."""
        # Create baseline with two tests
        baseline_data = [
            {
                "tool": "verify",
                "file_path": "/path/to/file1.lean",
                "theorem_id": None,
                "mode": None,
                "status": "success",
                "elapsed_ms": 100.0,
                "raw_response": {},
                "timestamp": "2024-01-01T12:00:00",
                "domain": "Algebra",
                "subdomain": "Group",
            },
            {
                "tool": "verify",
                "file_path": "/path/to/file2.lean",
                "theorem_id": None,
                "mode": None,
                "status": "success",
                "elapsed_ms": 100.0,
                "raw_response": {},
                "timestamp": "2024-01-01T12:00:00",
                "domain": "Algebra",
                "subdomain": "Group",
            },
        ]

        baseline_path = tmp_path / "baseline.json"
        with open(baseline_path, "w") as f:
            json.dump(baseline_data, f)

        # Create current results with only one test
        collector = ResultCollector()
        collector.record(
            tool="verify",
            file_path="/path/to/file1.lean",
            status="success",
            elapsed_ms=100.0,
            raw_response={},
            domain="Algebra",
            subdomain="Group",
        )

        comparison = collector.compare_baseline(baseline_path)

        assert len(comparison["removed_tests"]) == 1
        assert comparison["removed_tests"][0]["file_path"] == "/path/to/file2.lean"
