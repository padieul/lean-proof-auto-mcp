"""Append-only evaluation logger for detailed test run output.

Produces human-readable, timestamped logs in the same style as
_debug_test_verify_eval.py. Each test run appends to the log file
(never overwrites), building a persistent history of all runs.

Logs are written to tests/lean-proof-auto-mcp-eval_tests/logs/.

Design Patterns:
- Strategy: Logger interface can be swapped (file, console, null)
- Builder: LogEntry constructed step-by-step during test execution
- Dependency Injection: Logger injected into tests via pytest fixture
"""

import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol


LOGS_DIR = Path(__file__).resolve().parent / "logs"


class LogWriter(Protocol):
    """Port for writing log lines."""

    def write_line(self, line: str) -> None: ...


class FileLogWriter:
    """Adapter: appends timestamped lines to a file."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)

    def write_line(self, line: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        formatted = f"[{ts}] {line}"
        with self._lock:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(formatted + "\n")


class EvalLogger:
    """Detailed evaluation logger that mirrors _debug_test_verify_eval.py output.

    Appends to a log file in logs/ — one file per test module. Each test run
    writes a session header followed by per-fixture entries with status,
    diagnostics, timing, and assertion results.

    Example:
        logger = EvalLogger("test_verify_eval")
        logger.start_session("quick", 8)
        logger.log_fixture_start("Algebra/Group/Defs.lean", 53090, 1, 8)
        logger.log_fixture_result(response, 27.2, True, [])
        logger.log_summary(results)
    """

    def __init__(self, module_name: str, writer: LogWriter | None = None) -> None:
        if writer is None:
            log_path = LOGS_DIR / f"{module_name}.log"
            writer = FileLogWriter(log_path)
        self._writer = writer

    def _log(self, msg: str) -> None:
        self._writer.write_line(msg)

    def start_session(self, tier: str, fixture_count: int) -> None:
        """Write session header at the start of a test run."""
        self._log("")
        self._log(f"{'=' * 60}")
        self._log(f"SESSION START — {datetime.now().isoformat()}")
        self._log(f"Tier: {tier}, Fixtures: {fixture_count}")
        self._log(f"{'=' * 60}")

    def log_fixture_start(
        self, relative_path: str, file_size: int, index: int, total: int
    ) -> None:
        """Log the start of a fixture verification."""
        self._log("")
        self._log(f"{'=' * 60}")
        self._log(f"[{index}/{total}] {relative_path}")
        self._log(f"  File size: {file_size} bytes")

    def log_fixture_result(
        self,
        response: dict[str, Any],
        elapsed_s: float,
        passed: bool,
        failures: list[str],
    ) -> None:
        """Log the result of a fixture verification."""
        status = response.get("status", "???")
        diag_count = len(response.get("diagnostics", []))
        summary = response.get("diagnostic_summary", {})
        run_id = response.get("run_id", "N/A")

        self._log(f"  Status: {status}")
        self._log(
            f"  Diagnostics: {diag_count} ("
            f"errors={summary.get('error_count', '?')}, "
            f"warnings={summary.get('warning_count', '?')}, "
            f"info={summary.get('info_count', '?')})"
        )
        self._log(f"  Run ID: {run_id}")
        self._log(f"  Elapsed: {elapsed_s:.1f}s")

        if passed:
            self._log("  ASSERTION: PASS")
        else:
            self._log("  ASSERTION: FAIL")
            for f in failures:
                self._log(f"    - {f}")

        # First 3 diagnostics for context
        for j, d in enumerate(response.get("diagnostics", [])[:3]):
            sev = d.get("severity", "?")
            msg = d.get("message", "")[:120]
            loc = d.get("location", {})
            line_no = loc.get("line", "?") if isinstance(loc, dict) else "?"
            self._log(f"  diag[{j}]: {sev} L{line_no}: {msg}")

        if not passed:
            self._log(f"  FULL RESPONSE KEYS: {list(response.keys())}")

    def log_error(self, elapsed_s: float, error: str) -> None:
        """Log a timeout or exception."""
        self._log(f"  ERROR after {elapsed_s:.1f}s: {error}")

    def log_summary(self, results: list[dict[str, Any]]) -> None:
        """Log a summary block at the end of a session."""
        passed = sum(1 for r in results if r.get("passed"))
        failed = len(results) - passed
        total_elapsed = sum(r.get("elapsed_s", 0) for r in results)

        statuses: dict[str, int] = {}
        for r in results:
            s = r.get("status", "???")
            statuses[s] = statuses.get(s, 0) + 1

        self._log("")
        self._log(f"{'=' * 60}")
        self._log(f"SUMMARY ({len(results)} fixtures, {total_elapsed:.1f}s total)")
        self._log(f"{'=' * 60}")
        self._log(f"  Assertions passed: {passed}/{len(results)}")
        self._log(f"  Assertions failed: {failed}/{len(results)}")
        self._log(f"  Status breakdown: {statuses}")
        self._log("")

        for r in results:
            mark = "PASS" if r.get("passed") else "FAIL"
            self._log(
                f"  [{mark}] {r.get('file', '?')} -> "
                f"{r.get('status', '?')} ({r.get('elapsed_s', 0):.1f}s)"
            )
            if not r.get("passed"):
                for f in r.get("failures", []):
                    self._log(f"         {f}")
