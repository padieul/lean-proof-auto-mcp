@echo off
REM Helper script to run search_automated_proof eval tests
REM Output is tee'd to logs for inspection

echo === Running search_automated_proof eval tests ===
echo Started: %date% %time%
echo.

uv run pytest tests/lean-proof-auto-mcp-eval_tests/test_search_automated_proof_eval.py -v --tb=short

set "EXIT_CODE=%ERRORLEVEL%"

echo.
echo Completed: %date% %time%
echo Exit code: %EXIT_CODE%

exit /b %EXIT_CODE%
