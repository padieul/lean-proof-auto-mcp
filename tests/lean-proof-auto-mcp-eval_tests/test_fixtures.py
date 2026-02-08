"""
Unit tests for path resolution and fixture discovery.

Tests cover:
- Cross-platform path resolution
- Environment variable override
- Path validation
- Fixture discovery
- Metadata extraction
"""

import os
import platform
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from fixtures import (
    FixtureFile,
    discover_fixtures,
    get_eval_repo_path,
)


class TestGetEvalRepoPath:
    """Test cross-platform path resolution."""
    
    def test_linux_platform_returns_correct_default(self):
        """Test that Linux platform returns the correct default path."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("platform.system", return_value="Linux"):
                with patch("pathlib.Path.exists", return_value=True):
                    path = get_eval_repo_path()
                    assert path == Path("/home/paul_d/Sources/lean-proof-auto-mcp-eval/")
    
    def test_windows_platform_returns_correct_default(self):
        """Test that Windows platform returns the correct default path."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("platform.system", return_value="Windows"):
                with patch("pathlib.Path.exists", return_value=True):
                    path = get_eval_repo_path()
                    assert path == Path("C:/Dev/lean-proof-auto-mcp-eval")
    
    def test_darwin_platform_returns_correct_default(self):
        """Test that Darwin (macOS) platform returns the correct default path."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("platform.system", return_value="Darwin"):
                with patch("pathlib.Path.exists", return_value=True):
                    path = get_eval_repo_path()
                    assert path == Path("/home/paul_d/Sources/lean-proof-auto-mcp-eval/")
    
    def test_environment_variable_override(self):
        """Test that LEAN_EVAL_REPO environment variable overrides platform default."""
        custom_path = "/custom/eval/repo"
        with patch.dict(os.environ, {"LEAN_EVAL_REPO": custom_path}):
            with patch("pathlib.Path.exists", return_value=True):
                path = get_eval_repo_path()
                assert path == Path(custom_path)
    
    def test_file_not_found_error_when_path_does_not_exist(self):
        """Test that FileNotFoundError is raised when resolved path doesn't exist."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("platform.system", return_value="Linux"):
                with patch("pathlib.Path.exists", return_value=False):
                    with pytest.raises(FileNotFoundError) as exc_info:
                        get_eval_repo_path()
                    
                    assert "Eval repository not found" in str(exc_info.value)
                    assert "LEAN_EVAL_REPO" in str(exc_info.value)
    
    def test_environment_variable_override_with_nonexistent_path(self):
        """Test that FileNotFoundError is raised for env var path that doesn't exist."""
        custom_path = "/nonexistent/path"
        with patch.dict(os.environ, {"LEAN_EVAL_REPO": custom_path}):
            with patch("pathlib.Path.exists", return_value=False):
                with pytest.raises(FileNotFoundError) as exc_info:
                    get_eval_repo_path()
                
                # Check that error message contains path (may be normalized on Windows)
                error_msg = str(exc_info.value)
                assert "Eval repository not found" in error_msg
                assert "nonexistent" in error_msg
                assert "path" in error_msg


class TestDiscoverFixtures:
    """Test fixture discovery and metadata extraction."""
    
    def test_discover_fixtures_finds_all_lean_files(self):
        """Test that discover_fixtures finds all .lean files in the fixtures directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test directory structure
            fixtures_dir = Path(tmpdir) / "fixtures" / "mathlib" / "Fixtures"
            
            # Create some test .lean files
            algebra_dir = fixtures_dir / "Algebra" / "Group"
            algebra_dir.mkdir(parents=True)
            (algebra_dir / "Basic.lean").touch()
            (algebra_dir / "Subgroup.lean").touch()
            
            analysis_dir = fixtures_dir / "Analysis" / "Calculus"
            analysis_dir.mkdir(parents=True)
            (analysis_dir / "Derivative.lean").touch()
            
            # Discover fixtures
            fixtures = discover_fixtures(Path(tmpdir))
            
            # Verify all files are found
            assert len(fixtures) == 3
            assert all(isinstance(f, FixtureFile) for f in fixtures)
    
    def test_discover_fixtures_extracts_domain_correctly(self):
        """Test that domain is correctly extracted from path structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fixtures_dir = Path(tmpdir) / "fixtures" / "mathlib" / "Fixtures"
            
            algebra_dir = fixtures_dir / "Algebra" / "Group"
            algebra_dir.mkdir(parents=True)
            (algebra_dir / "Basic.lean").touch()
            
            fixtures = discover_fixtures(Path(tmpdir))
            
            assert len(fixtures) == 1
            assert fixtures[0].domain == "Algebra"
    
    def test_discover_fixtures_extracts_subdomain_correctly(self):
        """Test that subdomain is correctly extracted from path structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fixtures_dir = Path(tmpdir) / "fixtures" / "mathlib" / "Fixtures"
            
            algebra_dir = fixtures_dir / "Algebra" / "Group"
            algebra_dir.mkdir(parents=True)
            (algebra_dir / "Basic.lean").touch()
            
            fixtures = discover_fixtures(Path(tmpdir))
            
            assert len(fixtures) == 1
            assert fixtures[0].subdomain == "Group"
    
    def test_discover_fixtures_computes_relative_path_correctly(self):
        """Test that relative_path is correctly computed from Fixtures directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fixtures_dir = Path(tmpdir) / "fixtures" / "mathlib" / "Fixtures"
            
            algebra_dir = fixtures_dir / "Algebra" / "Group"
            algebra_dir.mkdir(parents=True)
            (algebra_dir / "Basic.lean").touch()
            
            fixtures = discover_fixtures(Path(tmpdir))
            
            assert len(fixtures) == 1
            # Use os.path.join for cross-platform path comparison
            expected_relative = str(Path("Algebra") / "Group" / "Basic.lean")
            assert fixtures[0].relative_path == expected_relative
    
    def test_discover_fixtures_raises_error_when_fixtures_dir_missing(self):
        """Test that FileNotFoundError is raised when fixtures directory doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Don't create fixtures directory
            with pytest.raises(FileNotFoundError) as exc_info:
                discover_fixtures(Path(tmpdir))
            
            assert "Fixtures directory not found" in str(exc_info.value)
    
    def test_discover_fixtures_handles_nested_subdirectories(self):
        """Test that fixtures in nested subdirectories are discovered correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fixtures_dir = Path(tmpdir) / "fixtures" / "mathlib" / "Fixtures"
            
            # Create deeply nested structure
            nested_dir = fixtures_dir / "Algebra" / "Group" / "Subgroup" / "Normal"
            nested_dir.mkdir(parents=True)
            (nested_dir / "Basic.lean").touch()
            
            fixtures = discover_fixtures(Path(tmpdir))
            
            assert len(fixtures) == 1
            assert fixtures[0].domain == "Algebra"
            assert fixtures[0].subdomain == "Group"
            # Relative path should include all nested directories
            assert "Subgroup" in fixtures[0].relative_path
            assert "Normal" in fixtures[0].relative_path
    
    def test_discover_fixtures_ignores_non_lean_files(self):
        """Test that non-.lean files are ignored during discovery."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fixtures_dir = Path(tmpdir) / "fixtures" / "mathlib" / "Fixtures"
            
            algebra_dir = fixtures_dir / "Algebra" / "Group"
            algebra_dir.mkdir(parents=True)
            (algebra_dir / "Basic.lean").touch()
            (algebra_dir / "README.md").touch()
            (algebra_dir / "notes.txt").touch()
            
            fixtures = discover_fixtures(Path(tmpdir))
            
            # Only .lean file should be discovered
            assert len(fixtures) == 1
            assert fixtures[0].path.suffix == ".lean"


class TestFixtureFile:
    """Test FixtureFile dataclass."""
    
    def test_fixture_file_is_frozen(self):
        """Test that FixtureFile is immutable (frozen)."""
        fixture = FixtureFile(
            path=Path("/test/path.lean"),
            domain="Algebra",
            subdomain="Group",
            relative_path="Algebra/Group/path.lean"
        )
        
        with pytest.raises(Exception):  # FrozenInstanceError
            fixture.domain = "Analysis"
    
    def test_fixture_file_stores_all_fields(self):
        """Test that FixtureFile correctly stores all fields."""
        test_path = Path("/test/path.lean")
        fixture = FixtureFile(
            path=test_path,
            domain="Algebra",
            subdomain="Group",
            relative_path="Algebra/Group/path.lean"
        )
        
        assert fixture.path == test_path
        assert fixture.domain == "Algebra"
        assert fixture.subdomain == "Group"
        assert fixture.relative_path == "Algebra/Group/path.lean"
