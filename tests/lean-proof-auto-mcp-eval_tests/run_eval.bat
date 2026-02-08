@echo off
setlocal enabledelayedexpansion

REM Evaluation Testing Framework — Tiered Execution Script (Windows)
REM
REM Usage: run_eval.bat [tier]
REM   tier: smoke | quick | normal | full | deep (default: normal)

set "TIER=%~1"
if "%TIER%"=="" set "TIER=normal"
set "SCRIPT_DIR=%~dp0"
set "REPORT_DIR=%SCRIPT_DIR%reports"

REM Validate tier
if "%TIER%"=="smoke" goto :valid_tier
if "%TIER%"=="quick" goto :valid_tier
if "%TIER%"=="normal" goto :valid_tier
if "%TIER%"=="full" goto :valid_tier
if "%TIER%"=="deep" goto :valid_tier
echo Error: Invalid tier '%TIER%'. Must be one of: smoke, quick, normal, full, deep
exit /b 1

:valid_tier

REM Map tier to pytest marker expression
set "MARKERS="
if "%TIER%"=="smoke" set "MARKERS=-m eval_smoke"
if "%TIER%"=="quick" set "MARKERS=-m "eval_smoke or eval_quick""
if "%TIER%"=="normal" set "MARKERS=-m "eval_smoke or eval_quick or eval_normal""
if "%TIER%"=="full" set "MARKERS=-m "eval_smoke or eval_quick or eval_normal or eval_full""
if "%TIER%"=="deep" set "MARKERS="

REM Create timestamped report directory
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set "DT=%%I"
set "TIMESTAMP=%DT:~0,4%%DT:~4,2%%DT:~6,2%-%DT:~8,2%%DT:~10,2%%DT:~12,2%"
set "RUN_DIR=%REPORT_DIR%\eval-%TIMESTAMP%-%TIER%"
mkdir "%RUN_DIR%" 2>nul

echo === Evaluation Testing Framework ===
echo Tier:      %TIER%
echo Report:    %RUN_DIR%
echo Started:   %date% %time%
echo.

REM Run pytest
uv run pytest "%SCRIPT_DIR%" ^
    %MARKERS% ^
    -v ^
    --tb=short ^
    --junit-xml="%RUN_DIR%\junit.xml" ^
    -k "not integration"

set "EXIT_CODE=%ERRORLEVEL%"

echo.
echo Completed: %date% %time%
echo Exit code: %EXIT_CODE%
echo Report:    %RUN_DIR%

exit /b %EXIT_CODE%
