#!/bin/bash
# Script to run eval investigation tests with detailed output

set -e

echo "=========================================="
echo "Running Eval Investigation Tests"
echo "=========================================="
echo ""

# Check if eval repo exists
EVAL_REPO="$HOME/Sources/lean-proof-auto-mcp-eval"
if [ ! -d "$EVAL_REPO" ]; then
    echo "ERROR: Eval repository not found at $EVAL_REPO"
    echo "Please clone it first:"
    echo "  git clone <repo-url> $EVAL_REPO"
    exit 1
fi

echo "✓ Found eval repository at $EVAL_REPO"
echo ""

# Check if Basic.lean exists
BASIC_LEAN="$EVAL_REPO/fixtures/mathlib/Fixtures/Algebra/Group/Subgroup/Basic.lean"
if [ ! -f "$BASIC_LEAN" ]; then
    echo "ERROR: Basic.lean not found at $BASIC_LEAN"
    exit 1
fi

echo "✓ Found Basic.lean at $BASIC_LEAN"
echo ""

# Run tests with verbose output
echo "Running tests..."
echo ""

uv run pytest tests/lean-proof-auto-mcp-eval_tests/ -v -s --tb=short

echo ""
echo "=========================================="
echo "Investigation Complete"
echo "=========================================="
echo ""
echo "Review the output above for findings."
echo "Check the tmp_path directories for saved JSON files."
