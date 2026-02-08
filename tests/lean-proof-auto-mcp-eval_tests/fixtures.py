"""
Path resolution and fixture discovery for evaluation testing framework.

This module provides cross-platform path resolution for the eval repository
and automatic discovery of fixture files for test parametrization.

Key Components:
- get_eval_repo_path(): Resolves eval repository path with platform detection
- discover_fixtures(): Enumerates all fixture files with metadata extraction
- FixtureFile: Dataclass representing a discovered fixture file
- ALL_FIXTURE_FILES: Module constant containing all discovered fixtures
"""

import os
import platform
from dataclasses import dataclass
from pathlib import Path


def get_eval_repo_path() -> Path:
    """
    Resolve the eval repository path with cross-platform support.
    
    Resolution order:
    1. LEAN_EVAL_REPO environment variable (if set)
    2. Platform-specific default:
       - Linux: /home/paul_d/Sources/lean-proof-auto-mcp-eval/
       - Windows: C:\\Dev\\lean-proof-auto-mcp-eval
       - Darwin (macOS): /home/paul_d/Sources/lean-proof-auto-mcp-eval/
    
    Returns:
        Path: Resolved eval repository path
        
    Raises:
        FileNotFoundError: If resolved path does not exist
    """
    # Check for environment variable override
    env_path = os.environ.get("LEAN_EVAL_REPO")
    if env_path:
        path = Path(env_path)
    else:
        # Use platform-specific default
        system = platform.system()
        if system == "Windows":
            path = Path("C:/Dev/lean-proof-auto-mcp-eval")
        else:  # Linux or Darwin (macOS)
            path = Path("/home/paul_d/Sources/lean-proof-auto-mcp-eval/")
    
    # Validate path exists
    if not path.exists():
        raise FileNotFoundError(
            f"Eval repository not found at {path}. "
            f"Set LEAN_EVAL_REPO environment variable to override."
        )
    
    return path


@dataclass(frozen=True)
class FixtureFile:
    """Represents a discovered fixture file."""
    path: Path                    # Absolute path to .lean file
    domain: str                   # Mathematical domain (e.g., "Algebra")
    subdomain: str                # Subdomain (e.g., "Group")
    relative_path: str            # Path relative to fixtures/ directory


def discover_fixtures(eval_repo_path: Path) -> list[FixtureFile]:
    """
    Discover all fixture files in the eval repository.
    
    Args:
        eval_repo_path: Path to eval repository root
        
    Returns:
        List of FixtureFile objects, one per discovered .lean file
        
    Raises:
        FileNotFoundError: If fixtures directory does not exist
    """
    fixtures_dir = eval_repo_path / "fixtures" / "mathlib" / "Fixtures"
    
    if not fixtures_dir.exists():
        raise FileNotFoundError(
            f"Fixtures directory not found at {fixtures_dir}"
        )
    
    fixture_files = []
    
    # Search recursively for all .lean files
    for lean_file in fixtures_dir.rglob("**/*.lean"):
        # Compute relative path from Fixtures directory
        relative_path = lean_file.relative_to(fixtures_dir)
        path_parts = relative_path.parts
        
        # Extract domain and subdomain from path structure
        # Expected structure: Domain/Subdomain/.../*.lean
        domain = path_parts[0] if len(path_parts) > 0 else ""
        subdomain = path_parts[1] if len(path_parts) > 1 else ""
        
        fixture_files.append(
            FixtureFile(
                path=lean_file,
                domain=domain,
                subdomain=subdomain,
                relative_path=str(relative_path)
            )
        )
    
    return fixture_files


# Module-level constant for parametrization
# This will be populated when the module is imported
# Note: This may raise FileNotFoundError if eval repo is not configured
try:
    ALL_FIXTURE_FILES: list[FixtureFile] = discover_fixtures(get_eval_repo_path())
except FileNotFoundError:
    # If eval repo is not found, set to empty list
    # Tests will skip if fixtures are not available
    ALL_FIXTURE_FILES = []
