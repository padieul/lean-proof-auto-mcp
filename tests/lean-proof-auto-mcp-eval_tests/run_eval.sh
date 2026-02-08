#!/bin/bash
set -e

# Evaluation Testing Framework — Tiered Execution Script (Linux/macOS)
#
# Usage: ./run_eval.sh [tier]
#   tier: smoke | quick | normal | full | deep (default: normal)

TIER="${1:-normal}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPORT_DIR="$SCRIPT_DIR/reports"

# Validate tier
case "$TIER" in
    smoke|quick|normal|full|deep) ;;
    *)
        echo "Error: Invalid tier '$TIER'. Must be one of: smoke, quick, normal, full, deep"
        exit 1
        ;;
esac

# Map tier to pytest marker expression
case "$TIER" in
    smoke)  MARKERS="-m eval_smoke" ;;
    quick)  MARKERS="-m 'eval_smoke or eval_quick'" ;;
    normal) MARKERS="-m 'eval_smoke or eval_quick or eval_normal'" ;;
    full)   MARKERS="-m 'eval_smoke or eval_quick or eval_normal or eval_full'" ;;
    deep)   MARKERS="" ;;
esac

# Create timestamped report directory
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
RUN_DIR="$REPORT_DIR/eval-${TIMESTAMP}-${TIER}"
mkdir -p "$RUN_DIR"

echo "=== Evaluation Testing Framework ==="
echo "Tier:      $TIER"
echo "Report:    $RUN_DIR"
echo "Started:   $(date)"
echo ""

# Run pytest
uv run pytest "$SCRIPT_DIR" \
    $MARKERS \
    -v \
    --tb=short \
    --junit-xml="$RUN_DIR/junit.xml" \
    -k "not integration" \
    2>&1 | tee "$RUN_DIR/output.log"

EXIT_CODE=${PIPESTATUS[0]}

echo ""
echo "Completed: $(date)"
echo "Exit code: $EXIT_CODE"
echo "Report:    $RUN_DIR"

exit $EXIT_CODE
