"""
Observability module for metadata collection, logging, and monitoring.

This module provides ports and adapters for observability concerns following
hexagonal architecture principles. It enables the core domain to collect
metadata about the execution environment without depending on specific
implementation details.

Exports:
    MetadataCollector: Protocol for collecting environment metadata
    SubprocessMetadataCollector: Implementation using subprocess commands
"""

from .metadata_collector import SubprocessMetadataCollector
from .ports import MetadataCollector

__all__ = [
    "MetadataCollector",
    "SubprocessMetadataCollector",
]
