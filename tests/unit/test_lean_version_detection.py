"""
Unit tests for Lean version detection in LeanInteractRunner.

This module tests the _detect_lean_version method to ensure it correctly
reads lean-toolchain files and falls back to defaults when needed.
"""

import tempfile
from pathlib import Path

import pytest

from lean_proof_auto_mcp.adapters.lean_interact_runner import LeanInteractRunner


class TestLeanVersionDetection:
    """Test suite for Lean version detection."""

    def test_detect_version_from_toolchain_file(self):
        """Test that version is correctly read from lean-toolchain file."""
        runner = LeanInteractRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            toolchain_file = workspace / "lean-toolchain"
            toolchain_file.write_text("leanprover/lean4:v4.27.0\n")

            version = runner._detect_lean_version(workspace)

            assert version == "leanprover/lean4:v4.27.0"

    def test_detect_version_with_simple_format(self):
        """Test that simple version format is correctly read."""
        runner = LeanInteractRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            toolchain_file = workspace / "lean-toolchain"
            toolchain_file.write_text("v4.15.0")

            version = runner._detect_lean_version(workspace)

            assert version == "v4.15.0"

    def test_detect_version_fallback_when_no_toolchain(self):
        """Test that default version is used when no lean-toolchain exists."""
        runner = LeanInteractRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            # No lean-toolchain file created

            version = runner._detect_lean_version(workspace)

            assert version == "v4.15.0"  # Default fallback

    def test_detect_version_fallback_on_read_error(self):
        """Test that default version is used when lean-toolchain cannot be read."""
        runner = LeanInteractRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            toolchain_file = workspace / "lean-toolchain"
            # Create file but make it unreadable (on Unix systems)
            toolchain_file.write_text("v4.27.0")
            toolchain_file.chmod(0o000)

            try:
                version = runner._detect_lean_version(workspace)
                # Should fall back to default
                assert version == "v4.15.0"
            finally:
                # Restore permissions for cleanup
                toolchain_file.chmod(0o644)

    def test_detect_version_strips_whitespace(self):
        """Test that whitespace is stripped from lean-toolchain content."""
        runner = LeanInteractRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            toolchain_file = workspace / "lean-toolchain"
            toolchain_file.write_text("  leanprover/lean4:v4.27.0  \n\n")

            version = runner._detect_lean_version(workspace)

            assert version == "leanprover/lean4:v4.27.0"
