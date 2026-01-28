"""
Artifact store adapters for verification result persistence.

This module implements concrete artifact storage strategies following
hexagonal architecture principles. Adapters implement the ArtifactStore
port defined in core.verify_domain.

Requirements: 1.5, 7.1, 9.8, 10.9, 10.10, 13.1, 13.2, 13.3, 13.4, 13.5
"""

import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ..core.json_serialization import to_json_serializable

logger = logging.getLogger(__name__)


class FilesystemArtifactStore:
    """
    Concrete implementation using filesystem for artifact storage.

    This adapter stores verification artifacts (request, result, logs) in a
    directory structure organized by run_id. Each verification creates a
    subdirectory containing three files: request.json, result.json, and
    lean_output.log.

    Requirements: 1.5, 7.1

    Attributes:
        artifacts_dir: Base directory for storing artifacts
    """

    def __init__(self, artifacts_dir: Path):
        """
        Initialize FilesystemArtifactStore with artifacts directory.

        Args:
            artifacts_dir: Base directory where artifacts will be stored

        Requirements: 1.5, 7.1
        """
        self.artifacts_dir = Path(artifacts_dir)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def store(
        self,
        run_id: str,
        command: Any,
        result: Any,
        full_logs: str,
    ) -> None:
        """
        Store verification artifacts under run_id directory.

        This method creates a directory structure:
        artifacts/
          <run_id>/
            request.json    - Original verification command
            result.json     - Verification result
            lean_output.log - Complete stdout/stderr logs

        All JSON files are written with indent=2 and sort_keys=True for
        deterministic formatting and readability.

        Args:
            run_id: Unique identifier for this verification run
            command: Original verification command (VerifyCommand or SearchAnnotationsCommand)
            result: Verification result (VerifyResult or SearchAnnotationsResult)
            full_logs: Complete stdout/stderr logs

        Raises:
            RuntimeError: If artifact storage fails (disk space, permissions, etc.)

        Requirements: 1.5, 7.1, 9.8, 10.9, 10.10, 13.1, 13.2, 13.3, 13.4, 13.5
        """
        try:
            # Create run_id directory
            run_dir = self.artifacts_dir / run_id
            run_dir.mkdir(parents=True, exist_ok=True)

            # Convert command and result to JSON-serializable dicts
            command_dict = to_json_serializable(asdict(command))
            result_dict = to_json_serializable(asdict(result))

            # Write request.json with command data
            request_path = run_dir / "request.json"
            with open(request_path, "w", encoding="utf-8") as f:
                json.dump(command_dict, f, indent=2, sort_keys=True)

            # Write result.json with result data
            result_path = run_dir / "result.json"
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump(result_dict, f, indent=2, sort_keys=True)

            # Write lean_output.log with full logs
            log_path = run_dir / "lean_output.log"
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(full_logs)

            logger.info(f"Stored artifacts for run_id: {run_id}")

        except OSError as e:
            error_msg = f"Failed to store artifacts for {run_id}: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

        except Exception as e:
            error_msg = f"Unexpected error storing artifacts for {run_id}: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e
