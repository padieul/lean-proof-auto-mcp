#!/usr/bin/env python3
"""
Generate test coverage report and verify 80%+ coverage requirement.

This script:
1. Runs pytest with coverage
2. Analyzes coverage.json
3. Identifies uncovered code
4. Verifies 80%+ coverage target
5. Generates recommendations for additional tests

Requirements: 25.6, 27.4
"""

import json
import sys
from pathlib import Path


def load_coverage_data(coverage_file: Path) -> dict:
    """Load coverage data from JSON file."""
    with open(coverage_file) as f:
        return json.load(f)


def analyze_coverage(coverage_data: dict) -> dict:
    """Analyze coverage data and compute statistics."""
    files = coverage_data.get("files", {})
    
    total_statements = 0
    total_covered = 0
    uncovered_files = []
    
    for file_path, file_data in files.items():
        # Skip test files and __init__.py
        if "test" in file_path or "__init__" in file_path:
            continue
        
        summary = file_data.get("summary", {})
        num_statements = summary.get("num_statements", 0)
        covered_lines = summary.get("covered_lines", 0)
        
        total_statements += num_statements
        total_covered += covered_lines
        
        # Calculate file coverage
        if num_statements > 0:
            file_coverage = (covered_lines / num_statements) * 100
            if file_coverage < 80:
                uncovered_files.append({
                    "file": file_path,
                    "coverage": file_coverage,
                    "statements": num_statements,
                    "covered": covered_lines,
                    "missing": num_statements - covered_lines,
                })
    
    # Calculate overall coverage
    overall_coverage = (total_covered / total_statements * 100) if total_statements > 0 else 0
    
    return {
        "overall_coverage": overall_coverage,
        "total_statements": total_statements,
        "total_covered": total_covered,
        "total_missing": total_statements - total_covered,
        "uncovered_files": sorted(uncovered_files, key=lambda x: x["coverage"]),
    }


def generate_report(analysis: dict) -> str:
    """Generate human-readable coverage report."""
    lines = []
    lines.append("=" * 80)
    lines.append("TEST COVERAGE REPORT")
    lines.append("=" * 80)
    lines.append("")
    
    # Overall statistics
    lines.append(f"Overall Coverage: {analysis['overall_coverage']:.1f}%")
    lines.append(f"Total Statements: {analysis['total_statements']}")
    lines.append(f"Covered Statements: {analysis['total_covered']}")
    lines.append(f"Missing Statements: {analysis['total_missing']}")
    lines.append("")
    
    # Coverage target
    target = 80.0
    if analysis['overall_coverage'] >= target:
        lines.append(f"✓ Coverage target met: {analysis['overall_coverage']:.1f}% >= {target}%")
    else:
        lines.append(f"✗ Coverage target NOT met: {analysis['overall_coverage']:.1f}% < {target}%")
        lines.append(f"  Need {target - analysis['overall_coverage']:.1f}% more coverage")
    lines.append("")
    
    # Files below 80% coverage
    uncovered = analysis['uncovered_files']
    if uncovered:
        lines.append(f"Files Below 80% Coverage ({len(uncovered)} files):")
        lines.append("-" * 80)
        for file_info in uncovered[:20]:  # Show top 20
            lines.append(f"  {file_info['file']}")
            lines.append(f"    Coverage: {file_info['coverage']:.1f}%")
            lines.append(f"    Missing: {file_info['missing']} / {file_info['statements']} statements")
            lines.append("")
    else:
        lines.append("✓ All files have 80%+ coverage")
        lines.append("")
    
    # Recommendations
    lines.append("Recommendations:")
    lines.append("-" * 80)
    if analysis['overall_coverage'] < target:
        lines.append("1. Add unit tests for uncovered files listed above")
        lines.append("2. Focus on files with lowest coverage first")
        lines.append("3. Add integration tests for end-to-end workflows")
        lines.append("4. Add property-based tests for universal properties")
    else:
        lines.append("✓ Coverage target met - maintain current test quality")
    lines.append("")
    
    lines.append("=" * 80)
    
    return "\n".join(lines)


def main():
    """Main entry point."""
    coverage_file = Path("coverage.json")
    
    if not coverage_file.exists():
        print("Error: coverage.json not found")
        print("Run: pytest --cov=src/lean_proof_auto_mcp --cov-report=json")
        sys.exit(1)
    
    # Load and analyze coverage
    coverage_data = load_coverage_data(coverage_file)
    analysis = analyze_coverage(coverage_data)
    
    # Generate and print report
    report = generate_report(analysis)
    print(report)
    
    # Exit with appropriate code
    if analysis['overall_coverage'] >= 80.0:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
