"""
Observability ports for metadata collection, logging, and monitoring.

This module defines abstract interfaces for observability concerns following
hexagonal architecture principles. These ports allow the core domain to
collect metadata about the execution environment without depending on
specific implementation details (subprocess, environment variables, etc.).

The primary use case is collecting version information (git commit, lean version,
lake version) for debugging, reproducibility, and auditing purposes.
"""

from typing import Protocol


class MetadataCollector(Protocol):
    """
    Port for collecting environment metadata.

    This port defines how the core domain collects metadata about the
    execution environment (git commit, tool versions, etc.) without
    depending on specific implementation (subprocess, environment variables, etc.).

    The metadata is used for:
    - Debugging: Understanding which versions were used
    - Reproducibility: Recreating the exact environment
    - Auditing: Tracking what ran when
    - Troubleshooting: Identifying version-specific issues

    Requirements: Observability, debugging, reproducibility

    Methods:
        collect_version_info: Collect version metadata from the environment
    """

    def collect_version_info(self) -> dict[str, str]:
        """
        Collect version metadata from the environment.

        This method attempts to collect version information from various
        sources (git, lean, lake, etc.). Missing tools or failures should
        result in missing keys, not errors.

        Returns:
            Dictionary with optional keys:
            - repo_commit: Git commit hash (if in a git repository)
            - lean_version: Lean version string (if lean is available)
            - lake_version: Lake version string (if lake is available)

        Note:
            This method should never raise exceptions. If a tool is not
            available or a command fails, the corresponding key should
            simply be omitted from the returned dictionary.

        Example:
            >>> collector = SubprocessMetadataCollector()
            >>> metadata = collector.collect_version_info()
            >>> print(metadata)
            {
                'repo_commit': 'a1b2c3d4e5f6...',
                'lean_version': 'Lean (version 4.26.0-rc1, ...)',
                'lake_version': 'Lake version 4.26.0-rc1 (...)'
            }
        """
        ...
