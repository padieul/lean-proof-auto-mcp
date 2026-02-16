"""Result collection and persistence for evaluation testing framework.

This module provides components for recording, persisting, and analyzing test results
from MCP tool evaluations. It follows hexagonal architecture principles by separating
result collection logic from persistence concerns.

Key Components:
- ToolResult: Immutable data structure representing a single tool invocation result
- ResultCollector: Collects results and provides persistence and analysis operations

Design Principles:
- Immutable result objects prevent accidental modification
- Explicit error handling with descriptive exceptions
- Dependency injection for testability
- Result/Either pattern for operations that can fail
"""

import json
import threading
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from itertools import groupby
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ToolResult:
    """Represents the result of a single tool invocation.

    This immutable data structure captures all relevant information about a tool
    execution, including timing, status, and domain metadata.

    Attributes:
        tool: Tool name (e.g., "verify", "probe", "probe_file")
        file_path: Path to the fixture file that was tested
        theorem_id: Name of the theorem tested (None for file-level tools)
        mode: Execution mode (aesop/grind/both, None if not applicable)
        status: Result status ("success", "failure", "timeout", "error")
        elapsed_ms: Execution time in milliseconds
        raw_response: Full JSON-RPC response from the tool
        timestamp: ISO 8601 timestamp of when the result was recorded
        domain: Mathematical domain (e.g., "Algebra", "Analysis")
        subdomain: Mathematical subdomain (e.g., "Group", "Ring")
    """

    tool: str
    file_path: str
    theorem_id: str | None
    mode: str | None
    status: str
    elapsed_ms: float
    raw_response: dict[str, Any]
    timestamp: str
    domain: str
    subdomain: str


class ResultCollector:
    """Collects and persists test results with thread-safe recording.

    This class provides the core result collection functionality for the evaluation
    framework. It maintains an in-memory collection of results and provides methods
    for persistence, aggregation, and baseline comparison.

    Thread Safety:
        All public methods are thread-safe and can be called from parallel test
        execution contexts.

    Example:
        collector = ResultCollector()
        collector.record(
            tool="verify",
            file_path="/path/to/file.lean",
            status="success",
            elapsed_ms=123.45,
            raw_response={"result": "ok"},
            domain="Algebra",
            subdomain="Group"
        )
        collector.save(Path("reports/eval-20240101-120000-normal"))
    """

    def __init__(self):
        """Initialize result collector with empty results list and thread lock."""
        self._results: list[ToolResult] = []
        self._lock = threading.Lock()

    def record(
        self,
        tool: str,
        file_path: str,
        status: str,
        elapsed_ms: float,
        raw_response: dict[str, Any],
        domain: str,
        subdomain: str,
        theorem_id: str | None = None,
        mode: str | None = None,
    ) -> None:
        """Record a tool invocation result.

        This method creates a ToolResult with the current timestamp and appends it
        to the results collection. It is thread-safe and can be called from parallel
        test execution contexts.

        Args:
            tool: Tool name (e.g., "verify", "probe")
            file_path: Path to fixture file
            status: Result status (success/failure/timeout/error)
            elapsed_ms: Execution time in milliseconds
            raw_response: Full JSON-RPC response
            domain: Mathematical domain
            subdomain: Mathematical subdomain
            theorem_id: Theorem name (optional, None for file-level tools)
            mode: Execution mode (optional, None if not applicable)

        Thread Safety:
            This method uses a lock to ensure thread-safe appending to the results list.
        """
        timestamp = datetime.now().isoformat()
        result = ToolResult(
            tool=tool,
            file_path=file_path,
            theorem_id=theorem_id,
            mode=mode,
            status=status,
            elapsed_ms=elapsed_ms,
            raw_response=raw_response,
            timestamp=timestamp,
            domain=domain,
            subdomain=subdomain,
        )

        with self._lock:
            self._results.append(result)

    def save(self, output_dir: Path) -> None:
        """Save results to JSON files.

        Creates the output directory if it doesn't exist and writes three JSON files:
        - results.json: All recorded results
        - summary.json: Aggregated summary statistics
        - metadata.json: Execution metadata

        Args:
            output_dir: Directory to save results

        Raises:
            OSError: If directory creation or file writing fails
            ValueError: If results cannot be serialized to JSON
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save all results
        results_path = output_dir / "results.json"
        with open(results_path, "w", encoding="utf-8") as f:
            # Convert dataclasses to dictionaries for JSON serialization
            results_data = [
                {
                    "tool": r.tool,
                    "file_path": r.file_path,
                    "theorem_id": r.theorem_id,
                    "mode": r.mode,
                    "status": r.status,
                    "elapsed_ms": r.elapsed_ms,
                    "raw_response": r.raw_response,
                    "timestamp": r.timestamp,
                    "domain": r.domain,
                    "subdomain": r.subdomain,
                }
                for r in self._results
            ]
            json.dump(results_data, f, indent=2)

        # Save summary
        summary_path = output_dir / "summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(self.summary(), f, indent=2)

        # Save metadata
        metadata_path = output_dir / "metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            metadata = {
                "total_results": len(self._results),
                "generated_at": datetime.now().isoformat(),
            }
            json.dump(metadata, f, indent=2)

    def summary(self) -> dict[str, Any]:
        """Generate summary statistics.

        Aggregates results by tool, domain, and status using collections.Counter
        for efficient counting.

        Returns:
            Dictionary with aggregations:
            - by_tool: Results grouped by tool with success/failure/error counts
            - by_domain: Results grouped by domain with success/failure/error counts
            - by_status: Results grouped by status with counts
            - total_count: Total number of results
            - total_elapsed_ms: Total execution time across all results
        """
        # Calculate total elapsed time
        total_elapsed_ms = sum(r.elapsed_ms for r in self._results)

        # Group by tool
        by_tool: dict[str, dict[str, int]] = {}
        for tool, results in groupby(
            sorted(self._results, key=lambda r: r.tool), key=lambda r: r.tool
        ):
            results_list = list(results)
            status_counts = Counter(r.status for r in results_list)
            by_tool[tool] = {
                "success": status_counts.get("success", 0),
                "failure": status_counts.get("failure", 0),
                "timeout": status_counts.get("timeout", 0),
                "error": status_counts.get("error", 0),
                "total": len(results_list),
            }

        # Group by domain
        by_domain: dict[str, dict[str, int]] = {}
        for domain, results in groupby(
            sorted(self._results, key=lambda r: r.domain), key=lambda r: r.domain
        ):
            results_list = list(results)
            status_counts = Counter(r.status for r in results_list)
            by_domain[domain] = {
                "success": status_counts.get("success", 0),
                "failure": status_counts.get("failure", 0),
                "timeout": status_counts.get("timeout", 0),
                "error": status_counts.get("error", 0),
                "total": len(results_list),
            }

        # Group by status
        by_status = dict(Counter(r.status for r in self._results))

        return {
            "by_tool": by_tool,
            "by_domain": by_domain,
            "by_status": by_status,
            "total_count": len(self._results),
            "total_elapsed_ms": total_elapsed_ms,
        }

    def compare_baseline(self, baseline_path: Path) -> dict[str, Any]:
        """Compare current results against a baseline.

        Loads baseline results from a JSON file and compares them against current
        results using a composite key of (tool, file, theorem, mode). Identifies
        regressions (success→failure), improvements (failure→success), and unchanged
        results.

        Args:
            baseline_path: Path to baseline results.json file

        Returns:
            Dictionary with:
            - regressions: List of tests that changed from success to failure
            - improvements: List of tests that changed from failure to success
            - unchanged: List of tests with same status
            - new_tests: List of tests in current but not in baseline
            - removed_tests: List of tests in baseline but not in current

        Raises:
            FileNotFoundError: If baseline file doesn't exist
            ValueError: If baseline file contains invalid JSON
        """
        if not baseline_path.exists():
            raise FileNotFoundError(f"Baseline file not found: {baseline_path}")

        with open(baseline_path, encoding="utf-8") as f:
            baseline_data = json.load(f)

        # Build lookup dictionaries using composite key
        def make_key(result: dict[str, Any]) -> tuple:
            return (
                result["tool"],
                result["file_path"],
                result.get("theorem_id"),
                result.get("mode"),
            )

        baseline_map = {make_key(r): r for r in baseline_data}
        current_map = {
            make_key(
                {
                    "tool": r.tool,
                    "file_path": r.file_path,
                    "theorem_id": r.theorem_id,
                    "mode": r.mode,
                    "status": r.status,
                }
            ): r
            for r in self._results
        }

        regressions = []
        improvements = []
        unchanged = []

        # Compare results that exist in both baseline and current
        for key, current_result in current_map.items():
            if key in baseline_map:
                baseline_result = baseline_map[key]
                baseline_status = baseline_result["status"]
                current_status = current_result.status

                if baseline_status == "success" and current_status in [
                    "failure",
                    "error",
                    "timeout",
                ]:
                    regressions.append(
                        {
                            "tool": current_result.tool,
                            "file_path": current_result.file_path,
                            "theorem_id": current_result.theorem_id,
                            "mode": current_result.mode,
                            "baseline_status": baseline_status,
                            "current_status": current_status,
                        }
                    )
                elif (
                    baseline_status in ["failure", "error", "timeout"]
                    and current_status == "success"
                ):
                    improvements.append(
                        {
                            "tool": current_result.tool,
                            "file_path": current_result.file_path,
                            "theorem_id": current_result.theorem_id,
                            "mode": current_result.mode,
                            "baseline_status": baseline_status,
                            "current_status": current_status,
                        }
                    )
                else:
                    unchanged.append(
                        {
                            "tool": current_result.tool,
                            "file_path": current_result.file_path,
                            "theorem_id": current_result.theorem_id,
                            "mode": current_result.mode,
                            "status": current_status,
                        }
                    )

        # Identify new and removed tests
        new_tests = [
            {
                "tool": current_map[key].tool,
                "file_path": current_map[key].file_path,
                "theorem_id": current_map[key].theorem_id,
                "mode": current_map[key].mode,
            }
            for key in current_map.keys() - baseline_map.keys()
        ]

        removed_tests = [
            {
                "tool": baseline_map[key]["tool"],
                "file_path": baseline_map[key]["file_path"],
                "theorem_id": baseline_map[key].get("theorem_id"),
                "mode": baseline_map[key].get("mode"),
            }
            for key in baseline_map.keys() - current_map.keys()
        ]

        return {
            "regressions": regressions,
            "improvements": improvements,
            "unchanged": unchanged,
            "new_tests": new_tests,
            "removed_tests": removed_tests,
        }

    @property
    def results(self) -> list[ToolResult]:
        """Get a copy of all recorded results.

        Returns:
            List of all ToolResult objects recorded so far
        """
        with self._lock:
            return list(self._results)
