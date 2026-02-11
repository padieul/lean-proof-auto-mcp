"""Helper script to run search_automated_proof eval test and capture output."""
import subprocess
import sys

result = subprocess.run(
    [
        sys.executable, "-m", "pytest",
        "tests/lean-proof-auto-mcp-eval_tests/test_search_automated_proof_eval.py",
        "-v", "--tb=short",
    ],
    capture_output=True,
    text=True,
    encoding="utf-8",
    timeout=1800,  # 30 min max
)

# Write output to logs
output = result.stdout + "\n" + result.stderr
log_path = "tests/lean-proof-auto-mcp-eval_tests/logs/_search_output.txt"
with open(log_path, "w", encoding="utf-8") as f:
    f.write(output)

print(output)
sys.exit(result.returncode)
