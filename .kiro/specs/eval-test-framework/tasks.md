# Implementation Plan: Evaluation Testing Framework

## Overview

This plan implements a systematic test infrastructure for validating all 6 MCP tools against 23 mathlib fixture files across 7 mathematical domains. The framework follows hexagonal architecture principles with tiered execution capabilities (smoke, quick, normal, full, deep) and comprehensive result collection.

## Tasks

- [x] 1. Path Resolution Module
  - [x] 1.1 Create `tests/lean-proof-auto-mcp-eval_tests/fixtures.py`
    - Create new Python module file
    - Add module docstring describing path resolution functionality
    - _Requirements: 1.1, 1.2, 1.4_
  
  - [x] 1.2 Implement `get_eval_repo_path()` function
    - Use `os.environ.get("LEAN_EVAL_REPO")` to check for override
    - Use `platform.system()` to detect OS ("Linux", "Windows", "Darwin")
    - Return Linux default: `/home/paul_d/Sources/lean-proof-auto-mcp-eval/`
    - Return Windows default: `C:\Dev\lean-proof-auto-mcp-eval`
    - Use `pathlib.Path` for all path construction
    - _Requirements: 1.1, 1.2, 1.3, 1.4_
  
  - [x] 1.3 Add path validation
    - Check if resolved path exists using `Path.exists()`
    - Raise `FileNotFoundError` with descriptive message if path doesn't exist
    - _Requirements: 1.5_
  
  - [x] 1.4 Write unit tests for path resolution
    - Test Linux platform returns correct default
    - Test Windows platform returns correct default
    - Test environment variable override
    - Test FileNotFoundError when path doesn't exist
    - Use mocked `platform.system()` and `os.environ`
    - _Requirements: 1.1, 1.2, 1.3, 1.5_

- [x] 2. Fixture Discovery Module
  - [x] 2.1 Create `FixtureFile` dataclass
    - Add frozen dataclass with path, domain, subdomain, relative_path fields
    - Add docstring describing each field
    - _Requirements: 3.4_
  
  - [x] 2.2 Implement `discover_fixtures()` function
    - Search `{eval_repo_path}/fixtures/mathlib/Fixtures/**/*.lean` recursively
    - Use `Path.rglob("**/*.lean")` for recursive search
    - Return list of FixtureFile objects
    - _Requirements: 3.1, 3.7_
  
  - [x] 2.3 Add domain and subdomain extraction
    - Extract domain from first directory level after Fixtures/
    - Extract subdomain from second directory level
    - Compute relative path from Fixtures/ directory
    - _Requirements: 3.2, 3.3, 3.4_

  
  - [x] 2.4 Create `ALL_FIXTURE_FILES` module constant
    - Call `discover_fixtures(get_eval_repo_path())` at module level
    - Store result in module constant for parametrization
    - _Requirements: 3.5_
  
  - [x] 2.5 Write unit tests for fixture discovery
    - Create temporary directory structure with known `.lean` files
    - Test discovery finds all files
    - Test domain extraction is correct
    - Test subdomain extraction is correct
    - Test FileNotFoundError when fixtures directory doesn't exist
    - _Requirements: 3.1, 3.2, 3.3, 3.6, 3.7_
  
  - [ ]* 2.6 Write property-based tests for metadata extraction
    - Use hypothesis to generate various path structures
    - Verify domain and subdomain extraction logic
    - **Property 5: Fixture Metadata Extraction Correctness**
    - _Requirements: 3.2, 3.3, 3.4_

- [x] 3. MCP Client Module
  - [x] 3.1 Create `tests/lean-proof-auto-mcp-eval_tests/mcp_client.py`
    - Create new Python module file
    - Add module docstring describing MCP client functionality
    - _Requirements: 2.1, 2.2_
  
  - [x] 3.2 Implement `MCPClient.__init__()` method
    - Accept server_path, working_dir, timeout parameters
    - Store parameters as instance variables
    - Initialize process to None
    - _Requirements: 2.1_
  
  - [x] 3.3 Implement `MCPClient.__enter__()` method
    - Use `subprocess.Popen` with `uv run python {server_path}` command
    - Set `stdin=PIPE`, `stdout=PIPE`, `stderr=PIPE`, `text=True`
    - Set `cwd=working_dir` for server context
    - Store process in instance variable
    - Return self
    - _Requirements: 2.2_
  
  - [x] 3.4 Implement `MCPClient.__exit__()` method
    - Call `process.terminate()`
    - Call `process.wait(timeout=5)`
    - If process doesn't terminate, call `process.kill()`
    - Handle exceptions gracefully
    - _Requirements: 2.3_

  
  - [x] 3.5 Implement `MCPClient.call_tool()` method
    - Construct JSON-RPC request with sequential ID
    - Write request to stdin with newline
    - Flush stdin immediately
    - Read response from stdout with timeout
    - Parse JSON response and validate structure
    - Return response dictionary
    - _Requirements: 2.4_
  
  - [x] 3.6 Add timeout handling to `call_tool()`
    - Use `select` or `threading.Timer` for timeout
    - Raise `TimeoutError` with descriptive message on timeout
    - _Requirements: 2.5_
  
  - [x] 3.7 Add error handling to `call_tool()`
    - Raise `ValueError` for malformed JSON with raw response
    - Raise `RuntimeError` for dead process with stderr output
    - _Requirements: 2.6_
  
  - [x] 3.8 Implement `MCPClient.health_check()` method
    - Send ping request to server
    - Return True if server responds, False otherwise
    - _Requirements: 2.7_
  
  - [x] 3.9 Implement `MCPClient.restart()` method
    - Terminate current process
    - Start new process with same parameters
    - _Requirements: 2.8_
  
  - [x] 3.10 Write unit tests for MCP client lifecycle
    - Test `__enter__` starts process
    - Test `__exit__` terminates process
    - Test `__exit__` handles exceptions
    - Use mocked subprocess
    - _Requirements: 2.1, 2.2, 2.3_
  
  - [x] 3.11 Write unit tests for call_tool()
    - Test successful tool call
    - Test timeout raises TimeoutError
    - Test malformed JSON raises ValueError
    - Test dead process raises RuntimeError
    - _Requirements: 2.4, 2.5, 2.6_
  
  - [x] 3.12 Write integration tests with real MCP server
    - Test full lifecycle with actual server
    - Test tool calls return valid responses
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 4. Result Collection Module
  - [x] 4.1 Create `tests/lean-proof-auto-mcp-eval_tests/result_collector.py`
    - Create new Python module file
    - Add module docstring describing result collection functionality
    - _Requirements: 4.1_

  
  - [x] 4.2 Create `ToolResult` dataclass
    - Add frozen dataclass with all required fields
    - Include tool, file_path, theorem_id, mode, status, elapsed_ms, raw_response, timestamp, domain, subdomain
    - Add docstring describing each field
    - _Requirements: 4.1_
  
  - [x] 4.3 Implement `ResultCollector.__init__()` method
    - Initialize empty results list
    - _Requirements: 4.1_
  
  - [x] 4.4 Implement `ResultCollector.record()` method
    - Create ToolResult with `datetime.now().isoformat()` timestamp
    - Append to results list
    - Handle concurrent access if needed
    - _Requirements: 4.1, 4.2, 4.8_
  
  - [x] 4.5 Implement `ResultCollector.save()` method
    - Create output directory if it doesn't exist
    - Serialize results to `results.json`
    - Generate and save summary to `summary.json`
    - Save metadata to `metadata.json`
    - Use custom JSON encoder for datetime
    - _Requirements: 4.3, 4.4_
  
  - [x] 4.6 Implement `ResultCollector.summary()` method
    - Use collections.Counter for aggregations
    - Group by tool, domain, and status
    - Calculate total_count and total_elapsed_ms
    - Return dictionary with all aggregations
    - _Requirements: 4.5_
  
  - [x] 4.7 Implement `ResultCollector.compare_baseline()` method
    - Load baseline JSON from file
    - Compare by (tool, file, theorem, mode) key
    - Identify regressions (success→failure)
    - Identify improvements (failure→success)
    - Identify unchanged results
    - Return dictionary with categorized results
    - _Requirements: 4.6, 4.7_
  
  - [x] 4.8 Write unit tests for result recording
    - Test record() adds result to list
    - Test timestamps are unique
    - Test concurrent recording
    - _Requirements: 4.1, 4.2, 4.8_
  
  - [x] 4.9 Write unit tests for persistence
    - Test save() creates all required files
    - Test JSON serialization is valid
    - Test all results are saved
    - Use temporary directory
    - _Requirements: 4.3, 4.4_

  
  - [x] 4.10 Write unit tests for summary aggregation
    - Test summary counts match expected values
    - Test aggregations by tool, domain, status
    - _Requirements: 4.5_
  
  - [x] 4.11 Write unit tests for baseline comparison
    - Create baseline and current result sets
    - Test regressions are identified correctly
    - Test improvements are identified correctly
    - Test unchanged results are identified correctly
    - _Requirements: 4.6, 4.7_
  
  - [ ]* 4.12 Write property-based tests for summary correctness
    - Generate random result distributions
    - Verify summary aggregations are correct
    - **Property 8: Summary Aggregation Correctness**
    - _Requirements: 4.5_

- [x] 5. Pytest Configuration
  - [x] 5.1 Create `tests/lean-proof-auto-mcp-eval_tests/conftest.py`
    - Create new Python module file
    - Add module docstring describing pytest configuration
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_
  
  - [x] 5.2 Implement `eval_repo` fixture
    - Session-scoped fixture
    - Call `get_eval_repo_path()`
    - Skip test if path doesn't exist
    - Return Path object
    - _Requirements: 5.1_
  
  - [x] 5.3 Implement `mcp_server_path` fixture
    - Session-scoped fixture
    - Compute path relative to conftest.py
    - Return path to `src/lean_proof_auto_mcp/server.py`
    - _Requirements: 5.2_
  
  - [x] 5.4 Implement `result_collector` fixture
    - Session-scoped fixture
    - Create and return ResultCollector instance
    - _Requirements: 5.3_
  
  - [x] 5.5 Implement `mcp_client` fixture
    - Module-scoped fixture
    - Use context manager with MCPClient
    - Yield client instance
    - Depends on eval_repo and mcp_server_path
    - _Requirements: 5.4_
  
  - [x] 5.6 Implement `fixture_file` parametrized fixture
    - Parametrize over ALL_FIXTURE_FILES
    - Use relative_path as test ID
    - Return FixtureFile object
    - _Requirements: 5.5_

  
  - [x] 5.7 Register tier markers in `pytest_configure()`
    - Register eval_smoke, eval_quick, eval_normal, eval_full, eval_deep
    - Add descriptions with time estimates
    - _Requirements: 5.6_
  
  - [x] 5.8 Register domain markers in `pytest_configure()`
    - Register eval_algebra, eval_analysis, eval_data, eval_group_theory
    - Register eval_linear_algebra, eval_ring_theory, eval_topology
    - _Requirements: 5.7_
  
  - [x] 5.9 Write tests for fixture wiring
    - Test all fixtures are available
    - Test fixtures have correct scopes
    - Test parametrization works correctly
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 6. Verify Tool Tests
  - [x] 6.1 Create `tests/lean-proof-auto-mcp-eval_tests/test_verify_eval.py`
    - Create new test module file
    - Add module docstring
    - Set default tier marker to eval_normal
    - _Requirements: 6.1_
  
  - [x] 6.2 Implement smoke tier tests
    - Select 2 fixture files for smoke testing
    - Mark with @pytest.mark.eval_smoke
    - Test verify tool returns valid response
    - Record results with result_collector
    - _Requirements: 6.1, 6.2, 6.5_
  
  - [x] 6.3 Implement quick tier tests
    - Select 5 fixture files for quick testing
    - Mark with @pytest.mark.eval_quick
    - Test verify tool on all selected files
    - Record results
    - _Requirements: 6.1, 6.2, 6.5_
  
  - [x] 6.4 Implement normal tier tests
    - Test verify tool on all 23 fixture files
    - Mark with @pytest.mark.eval_normal
    - Validate response structure
    - Record success/failure status
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_
  
  - [x] 6.5 Add response validation assertions
    - Assert status is in ["success", "failure", "error"]
    - Assert response has required fields
    - _Requirements: 6.2_

- [x] 7. Probe Tool Tests
  - [x] 7.1 Create `tests/lean-proof-auto-mcp-eval_tests/test_probe_eval.py`
    - Create new test module file
    - Add module docstring
    - Set default tier marker to eval_normal
    - _Requirements: 7.1_

  
  - [x] 7.2 Implement smoke tier tests
    - Select 2 files with 5 theorems each
    - Test in one mode (aesop or grind)
    - Mark with @pytest.mark.eval_smoke
    - Record results for each theorem
    - _Requirements: 7.1, 7.3, 7.4, 7.5_
  
  - [x] 7.3 Implement quick tier tests
    - Select 5 files with 10 theorems each
    - Test in all three modes (aesop, grind, both)
    - Mark with @pytest.mark.eval_quick
    - Add parametrization for theorem-mode combinations
    - Record results
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.6_
  
  - [x] 7.4 Implement normal tier tests
    - Test on all 23 files with selected theorems
    - Test in all three modes
    - Mark with @pytest.mark.eval_normal
    - Validate response contains theorem information
    - Record results
    - _Requirements: 7.1, 7.2, 7.3, 7.4_
  
  - [x] 7.5 Add theorem-mode parametrization
    - Create parametrize decorator for theorem-mode combinations
    - Generate test cases for each combination
    - _Requirements: 7.2, 7.4_

- [x] 8. Probe File Tool Tests
  - [x] 8.1 Create `tests/lean-proof-auto-mcp-eval_tests/test_probe_file_eval.py`
    - Create new test module file
    - Add module docstring
    - Set default tier marker to eval_normal
    - _Requirements: 8.1_
  
  - [x] 8.2 Implement smoke tier tests
    - Select 2 files
    - Test in one mode
    - Mark with @pytest.mark.eval_smoke
    - Validate response contains theorem list
    - _Requirements: 8.1, 8.3, 8.5_
  
  - [x] 8.3 Implement quick tier tests
    - Select 5 files
    - Test in all three modes
    - Mark with @pytest.mark.eval_quick
    - Validate theorem counts
    - _Requirements: 8.1, 8.2, 8.3, 8.6_
  
  - [x] 8.4 Implement normal tier tests
    - Test all 23 files in all three modes
    - Mark with @pytest.mark.eval_normal
    - Verify theorem counts match expected ranges
    - Record results
    - _Requirements: 8.1, 8.2, 8.3, 8.4_


- [x] 9. Automated Proof Tool Tests
  - [x] 9.1 Create `tests/lean-proof-auto-mcp-eval_tests/test_search_automated_proof_eval.py`
    - Create new test module file
    - Add module docstring
    - Set default tier marker to eval_normal
    - _Requirements: 9.1_
  
  - [x] 9.2 Select representative theorems from each domain
    - Choose theorems that are good candidates for automated proof
    - Ensure coverage across all 7 domains
    - _Requirements: 9.1_
  
  - [x] 9.3 Implement normal tier tests for search_automated_proof
    - Test on selected theorems
    - Mark with @pytest.mark.eval_normal
    - Record proof success/failure
    - Extract and record proof tactic when found
    - _Requirements: 9.1, 9.3, 9.4, 9.5_
  
  - [x] 9.4 Create `tests/lean-proof-auto-mcp-eval_tests/test_try_automated_proof_eval.py`
    - Create new test module file
    - Add module docstring
    - Set default tier marker to eval_normal
    - _Requirements: 9.2_
  
  - [x] 9.5 Select validation theorems from each domain
    - Choose theorems for try_automated_proof validation
    - Ensure domain coverage
    - _Requirements: 9.2_
  
  - [x] 9.6 Implement normal tier tests for try_automated_proof
    - Test on validation cases
    - Mark with @pytest.mark.eval_normal
    - Record proof validation results
    - _Requirements: 9.2, 9.3, 9.5_

- [x] 10. Get Proof Context Tool Tests
  - [x] 10.1 Create `tests/lean-proof-auto-mcp-eval_tests/test_get_proof_context_eval.py`
    - Create new test module file
    - Add module docstring
    - Set default tier marker to eval_normal
    - _Requirements: 10.1_
  
  - [x] 10.2 Select theorems requiring context from each domain
    - Choose theorems that need context extraction
    - Ensure domain coverage
    - _Requirements: 10.1_
  
  - [x] 10.3 Implement normal tier tests
    - Test get_proof_context on selected theorems
    - Mark with @pytest.mark.eval_normal
    - Validate response contains relevant context
    - _Requirements: 10.1, 10.2_
  
  - [x] 10.4 Add context completeness validation
    - Verify context includes imports
    - Verify context includes definitions
    - Verify context includes related theorems
    - _Requirements: 10.3_
  
  - [x] 10.5 Add context quality metrics recording
    - Record completeness metrics
    - Record relevance metrics
    - _Requirements: 10.4_

- [ ] 11. Cross-Tool Consistency Tests
  - [ ] 11.1 Create `tests/lean-proof-auto-mcp-eval_tests/test_cross_tool_consistency.py`
    - Create new test module file
    - Add module docstring describing cross-tool validation
    - Set default tier marker to eval_full
    - _Requirements: 11.1, 11.2_
  
  - [ ] 11.2 Implement theorem existence consistency tests
    - For each fixture file, run probe_file to get theorem list
    - For each theorem, verify that verify tool can access it
    - Mark with @pytest.mark.eval_full
    - Record inconsistencies where probe finds theorem but verify cannot
    - _Requirements: 11.1_
  
  - [ ] 11.3 Add cross-tool response validation
    - Verify probe and verify agree on theorem names
    - Verify probe and get_proof_context agree on available context
    - Record any disagreements
    - _Requirements: 11.2_
  
  - [ ]* 11.4 Write property-based tests for cross-tool consistency
    - Generate random fixture selections
    - Verify theorem existence consistency holds
    - **Property 14: Cross-Tool Theorem Consistency**
    - _Requirements: 11.1, 11.2_

- [ ] 12. Domain Coverage Tests
  - [ ] 12.1 Create `tests/lean-proof-auto-mcp-eval_tests/test_domain_coverage.py`
    - Create new test module file
    - Add module docstring describing domain coverage reporting
    - Set default tier marker to eval_normal
    - _Requirements: 12.1, 12.2_
  
  - [ ] 12.2 Implement domain coverage reporting test
    - Collect all results from result_collector
    - Group by domain and count tests per domain
    - Mark with @pytest.mark.eval_normal
    - Assert all 7 domains have at least one test
    - _Requirements: 12.1_
  
  - [ ] 12.3 Add domain distribution validation
    - Calculate percentage of tests per domain
    - Verify no domain has < 5% of total tests
    - Log domain distribution for analysis
    - _Requirements: 12.2_
  
  - [ ]* 12.4 Write property-based tests for domain coverage
    - Generate random result distributions
    - Verify coverage calculation is correct
    - **Property 15: Domain Coverage Completeness**
    - _Requirements: 12.1, 12.2_

- [x] 13. Execution Scripts - Linux/macOS
  - [x] 13.1 Create `tests/lean-proof-auto-mcp-eval_tests/run_eval.sh`
    - Create bash script file
    - Add shebang: `#!/bin/bash`
    - Add `set -e` for error handling
    - _Requirements: 13.1, 13.2_
  
  - [x] 13.2 Implement tier argument parsing
    - Accept tier as first argument: `TIER=${1:-normal}`
    - Validate tier is one of: smoke, quick, normal, full, deep
    - Exit with error message if invalid tier
    - _Requirements: 13.3, 13.4, 13.5, 13.6, 13.7_
  
  - [x] 13.3 Implement timestamp and report directory creation
    - Generate timestamp: `TIMESTAMP=$(date +%Y%m%d-%H%M%S)`
    - Create report directory: `REPORT_DIR="reports/eval-${TIMESTAMP}-${TIER}"`
    - Create directory: `mkdir -p "$REPORT_DIR"`
    - _Requirements: 14.1, 14.2_
  
  - [x] 13.4 Implement tier marker mapping
    - Map smoke to `-m eval_smoke`
    - Map quick to `-m 'eval_smoke or eval_quick'`
    - Map normal to `-m 'eval_smoke or eval_quick or eval_normal'`
    - Map full to `-m 'eval_smoke or eval_quick or eval_normal or eval_full'`
    - Map deep to no marker (all tests)
    - _Requirements: 13.3, 13.4, 13.5, 13.6, 13.7_
  
  - [x] 13.5 Implement pytest execution
    - Run pytest with tier markers
    - Add `-v` for verbose output
    - Add `--tb=short` for concise tracebacks
    - Add `--junit-xml="$REPORT_DIR/junit.xml"` for CI integration
    - Echo start and completion messages
    - _Requirements: 13.8, 14.3_
  
  - [x] 13.6 Add result persistence hook
    - After pytest completes, call result_collector.save()
    - Save to `$REPORT_DIR` directory
    - _Requirements: 14.3_

- [x] 14. Execution Scripts - Windows
  - [x] 14.1 Create `tests/lean-proof-auto-mcp-eval_tests/run_eval.bat`
    - Create batch script file
    - Add `@echo off` and `setlocal enabledelayedexpansion`
    - _Requirements: 13.1, 13.2_
  
  - [x] 14.2 Implement tier argument parsing
    - Accept tier as first argument with default: `set TIER=%1` then `if "%TIER%"=="" set TIER=normal`
    - Validate tier is one of: smoke, quick, normal, full, deep
    - Exit with error message if invalid tier
    - _Requirements: 13.3, 13.4, 13.5, 13.6, 13.7_
  
  - [x] 14.3 Implement timestamp and report directory creation
    - Generate timestamp using date and time commands
    - Create report directory: `set REPORT_DIR=reports\eval-%TIMESTAMP%-%TIER%`
    - Create directory: `mkdir "%REPORT_DIR%" 2>nul`
    - _Requirements: 14.1, 14.2_
  
  - [x] 14.4 Implement tier marker mapping
    - Use same marker mapping as Linux script
    - Store in MARKERS variable
    - _Requirements: 13.3, 13.4, 13.5, 13.6, 13.7_
  
  - [x] 14.5 Implement pytest execution
    - Run pytest with tier markers using Windows path separators
    - Add same flags as Linux script
    - Use `^` for line continuation in batch
    - Echo start and completion messages
    - _Requirements: 13.8, 14.3_

- [x] 15. Documentation - README
  - [x] 15.1 Create `tests/lean-proof-auto-mcp-eval_tests/README.md`
    - Create markdown file
    - Add title: "Evaluation Testing Framework"
    - Add overview section describing purpose
    - _Requirements: 15.1, 15.2_
  
  - [x] 15.2 Document framework architecture
    - Add architecture section with component descriptions
    - Describe hexagonal architecture principles
    - List all modules and their responsibilities
    - _Requirements: 15.1_
  
  - [x] 15.3 Document tier system
    - Add tier system section
    - Document all 5 tiers with time estimates
    - Explain tier hierarchy and marker usage
    - _Requirements: 15.2_
  
  - [x] 15.4 Document execution instructions
    - Add quick start section
    - Document Linux execution: `./run_eval.sh [tier]`
    - Document Windows execution: `run_eval.bat [tier]`
    - Document environment variable: `LEAN_EVAL_REPO`
    - _Requirements: 15.2_
  
  - [x] 15.5 Document result interpretation
    - Add results section
    - Explain result directory structure
    - Document results.json, summary.json, metadata.json formats
    - Explain how to compare against baseline
    - _Requirements: 15.2_
  
  - [x] 15.6 Document domain markers
    - Add domain filtering section
    - List all 7 domain markers
    - Show examples of running tests for specific domains
    - _Requirements: 15.2_

- [ ] 16. Documentation - Architecture
  - [ ] 16.1 Add architecture diagram to README
    - Create mermaid diagram showing component relationships
    - Show test layer, infrastructure layer, fixture layer, execution layer
    - _Requirements: 15.1_
  
  - [ ] 16.2 Document component interfaces
    - Add API reference section
    - Document MCPClient interface with all methods
    - Document ResultCollector interface with all methods
    - Document fixture discovery functions
    - _Requirements: 15.1_
  
  - [ ] 16.3 Document extension points
    - Add extending section
    - Explain how to add new tool tests
    - Explain how to add new tiers
    - Explain how to add new domain markers
    - _Requirements: 15.2_

- [ ]* 17. Property-Based Test - Path Resolution Consistency
  - [ ]* 17.1 Create `tests/lean-proof-auto-mcp-eval_tests/test_properties_path_resolution.py`
    - Create new test module file
    - Import hypothesis strategies
    - Add module docstring
    - _Requirements: 1.1, 1.2, 1.3, 1.4_
  
  - [ ]* 17.2 Implement Property 1: Path Resolution Consistency
    - Use hypothesis to generate platform values (Linux, Windows, Darwin)
    - Use hypothesis to generate optional environment variable values
    - Mock platform.system() and os.environ
    - Call get_eval_repo_path()
    - Assert returned path matches expected value based on platform and env var
    - **Property 1: Path Resolution Consistency**
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [ ]* 18. Property-Based Test - MCP Client Lifecycle
  - [ ]* 18.1 Create `tests/lean-proof-auto-mcp-eval_tests/test_properties_mcp_client.py`
    - Create new test module file
    - Import hypothesis strategies
    - Add module docstring
    - _Requirements: 2.1, 2.2, 2.3_
  
  - [ ]* 18.2 Implement Property 2: MCP Client Lifecycle Integrity
    - Use hypothesis to generate various operations (normal, exception-raising)
    - Mock subprocess.Popen
    - Create MCPClient and use as context manager
    - Verify process started on entry
    - Execute operation (may raise exception)
    - Verify process terminated on exit
    - **Property 2: MCP Client Lifecycle Integrity**
    - _Requirements: 2.1, 2.2, 2.3_
  
  - [ ]* 18.3 Implement Property 3: Tool Call Timeout Enforcement
    - Use hypothesis to generate timeout values
    - Mock server with configurable response delay
    - Call call_tool() with timeout
    - Verify TimeoutError raised when delay > timeout
    - Verify success when delay <= timeout
    - **Property 3: Tool Call Timeout Enforcement**
    - _Requirements: 2.5_

- [ ]* 19. Property-Based Test - Fixture Discovery
  - [ ]* 19.1 Create `tests/lean-proof-auto-mcp-eval_tests/test_properties_fixture_discovery.py`
    - Create new test module file
    - Import hypothesis strategies
    - Add module docstring
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.7_
  
  - [ ]* 19.2 Implement Property 4: Fixture Discovery Completeness
    - Use hypothesis to generate directory structures with .lean files
    - Create temporary directory with generated structure
    - Call discover_fixtures()
    - Verify all .lean files are discovered
    - Verify no extra files are discovered
    - **Property 4: Fixture Discovery Completeness**
    - _Requirements: 3.1, 3.7_
  
  - [ ]* 19.3 Implement Property 5: Fixture Metadata Extraction Correctness
    - Use hypothesis to generate various path structures
    - Create FixtureFile objects with generated paths
    - Verify domain extraction is correct
    - Verify subdomain extraction is correct
    - Verify relative_path is correct
    - **Property 5: Fixture Metadata Extraction Correctness**
    - _Requirements: 3.2, 3.3, 3.4_

- [ ]* 20. Property-Based Test - Result Collection
  - [ ]* 20.1 Create `tests/lean-proof-auto-mcp-eval_tests/test_properties_result_collector.py`
    - Create new test module file
    - Import hypothesis strategies
    - Add module docstring
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8_
  
  - [ ]* 20.2 Implement Property 6: Result Recording Idempotency
    - Use hypothesis to generate result parameters
    - Create ResultCollector
    - Record same result twice with small delay
    - Verify both results are stored
    - Verify timestamps are different
    - **Property 6: Result Recording Idempotency**
    - _Requirements: 4.1, 4.2, 4.8_
  
  - [ ]* 20.3 Implement Property 7: Result Persistence Completeness
    - Use hypothesis to generate various numbers of results
    - Create ResultCollector and record N results
    - Save to temporary directory
    - Verify all files exist
    - Verify results.json contains N results
    - **Property 7: Result Persistence Completeness**
    - _Requirements: 4.3, 4.4_
  
  - [ ]* 20.4 Implement Property 8: Summary Aggregation Correctness
    - Use hypothesis to generate result distributions
    - Create ResultCollector and record results
    - Generate summary
    - Verify sum of by_tool totals equals total_count
    - Verify sum of by_domain totals equals total_count
    - Verify sum of by_status counts equals total_count
    - **Property 8: Summary Aggregation Correctness**
    - _Requirements: 4.5_
  
  - [ ]* 20.5 Implement Property 9: Baseline Comparison Accuracy
    - Use hypothesis to generate baseline and current result sets
    - Create known regressions, improvements, and unchanged results
    - Call compare_baseline()
    - Verify regressions are correctly identified
    - Verify improvements are correctly identified
    - Verify unchanged results are correctly identified
    - **Property 9: Baseline Comparison Accuracy**
    - _Requirements: 4.6, 4.7_

- [ ]* 21. Property-Based Test - Pytest Configuration
  - [ ]* 21.1 Create `tests/lean-proof-auto-mcp-eval_tests/test_properties_pytest_config.py`
    - Create new test module file
    - Import hypothesis strategies
    - Add module docstring
    - _Requirements: 5.5_
  
  - [ ]* 21.2 Implement Property 10: Fixture Parametrization Completeness
    - Use pytest collection API to collect test cases
    - Verify number of test cases equals len(ALL_FIXTURE_FILES)
    - Verify each fixture file appears exactly once
    - **Property 10: Fixture Parametrization Completeness**
    - _Requirements: 5.5_

- [ ]* 22. Property-Based Test - Tier Hierarchy
  - [ ]* 22.1 Create `tests/lean-proof-auto-mcp-eval_tests/test_properties_tier_hierarchy.py`
    - Create new test module file
    - Import hypothesis strategies
    - Add module docstring
    - _Requirements: 13.3, 13.4, 13.5, 13.6, 13.7_
  
  - [ ]* 22.2 Implement Property 11: Tier Marker Hierarchy
    - Use hypothesis to generate tier combinations
    - Mark dummy tests with various tiers
    - Run pytest with each tier level
    - Verify correct tests are executed based on hierarchy
    - **Property 11: Tier Marker Hierarchy**
    - _Requirements: 13.3, 13.4, 13.5, 13.6, 13.7_
  
  - [ ]* 22.3 Implement Property 12: Execution Time Bounds
    - Run each tier (smoke, quick, normal, full)
    - Measure execution time
    - Verify smoke completes in < 120 seconds
    - Verify quick completes in < 600 seconds
    - Verify normal completes in < 1800 seconds
    - Verify full completes in < 7200 seconds
    - **Property 12: Execution Time Bounds**
    - _Requirements: 13.3, 13.4, 13.5, 13.6_

- [ ]* 23. Property-Based Test - Result Directory Isolation
  - [ ]* 23.1 Create `tests/lean-proof-auto-mcp-eval_tests/test_properties_result_isolation.py`
    - Create new test module file
    - Import hypothesis strategies
    - Add module docstring
    - _Requirements: 14.2_
  
  - [ ]* 23.2 Implement Property 13: Result Directory Isolation
    - Run test execution multiple times in quick succession
    - Verify each run creates unique timestamped directory
    - Verify directory names match pattern "eval-YYYYMMDD-HHMMSS-{tier}"
    - Verify no directory conflicts occur
    - **Property 13: Result Directory Isolation**
    - _Requirements: 14.2_

- [ ]* 24. Property-Based Test - Cross-Tool Consistency
  - [ ]* 24.1 Create `tests/lean-proof-auto-mcp-eval_tests/test_properties_cross_tool.py`
    - Create new test module file
    - Import hypothesis strategies
    - Add module docstring
    - _Requirements: 11.1, 11.2_
  
  - [ ]* 24.2 Implement Property 14: Cross-Tool Theorem Consistency
    - Use hypothesis to generate fixture file selections
    - For each file, run probe_file to get theorems
    - For each theorem, run verify
    - Verify if probe finds theorem, verify can access it (or errors)
    - **Property 14: Cross-Tool Theorem Consistency**
    - _Requirements: 11.1, 11.2_

- [ ] 25. Integration Test - End-to-End Workflow
  - [ ] 25.1 Create `tests/lean-proof-auto-mcp-eval_tests/test_integration_end_to_end.py`
    - Create new test module file
    - Add module docstring
    - Mark with @pytest.mark.integration
    - _Requirements: 1.1, 2.1, 3.1, 4.1, 5.1_
  
  - [ ] 25.2 Implement end-to-end smoke tier test
    - Execute run_eval.sh smoke (or run_eval.bat on Windows)
    - Verify script completes successfully
    - Verify report directory is created
    - Verify results.json, summary.json, metadata.json exist
    - Verify junit.xml exists
    - _Requirements: 13.1, 13.2, 13.3, 14.1, 14.2, 14.3_
  
  - [ ] 25.3 Implement end-to-end result validation
    - Load results.json and validate structure
    - Verify all results have required fields
    - Verify summary aggregations are correct
    - _Requirements: 4.3, 4.4, 4.5_

- [ ] 26. Integration Test - Fixture Wiring
  - [ ] 26.1 Create `tests/lean-proof-auto-mcp-eval_tests/test_integration_conftest.py`
    - Create new test module file
    - Add module docstring
    - Mark with @pytest.mark.integration
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_
  
  - [ ] 26.2 Test fixture availability
    - Verify eval_repo fixture is available
    - Verify mcp_server_path fixture is available
    - Verify result_collector fixture is available
    - Verify mcp_client fixture is available
    - Verify fixture_file fixture is available
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_
  
  - [ ] 26.3 Test fixture scopes
    - Verify eval_repo is session-scoped
    - Verify mcp_server_path is session-scoped
    - Verify result_collector is session-scoped
    - Verify mcp_client is module-scoped
    - _Requirements: 5.1, 5.2, 5.3, 5.4_
  
  - [ ] 26.4 Test fixture parametrization
    - Collect tests using fixture_file
    - Verify parametrization generates correct number of test cases
    - Verify test IDs use relative_path
    - _Requirements: 5.5_

- [ ] 27. Integration Test - Cross-Platform Compatibility
  - [ ] 27.1 Create `tests/lean-proof-auto-mcp-eval_tests/test_integration_cross_platform.py`
    - Create new test module file
    - Add module docstring
    - Mark with @pytest.mark.integration
    - _Requirements: 1.1, 1.2, 1.3, 1.4_
  
  - [ ] 27.2 Test path resolution on current platform
    - Call get_eval_repo_path()
    - Verify returned path exists
    - Verify path is absolute
    - Verify path uses correct separators for platform
    - _Requirements: 1.1, 1.2, 1.3, 1.4_
  
  - [ ] 27.3 Test execution script on current platform
    - Detect platform (Windows vs Linux/macOS)
    - Execute appropriate script (run_eval.bat or run_eval.sh)
    - Verify script runs successfully
    - _Requirements: 13.1, 13.2_

- [ ] 28. CI/CD Integration
  - [ ] 28.1 Create `.github/workflows/eval-tests.yml`
    - Create GitHub Actions workflow file
    - Add workflow name: "Evaluation Tests"
    - Configure manual trigger: `workflow_dispatch` with tier input
    - _Requirements: 13.1, 13.2_
  
  - [ ] 28.2 Configure workflow jobs
    - Add job for Linux execution
    - Add job for Windows execution
    - Use matrix strategy for tier selection
    - _Requirements: 13.1, 13.2_
  
  - [ ] 28.3 Add result artifact upload
    - Upload report directory as artifact
    - Upload junit.xml for test reporting
    - Set artifact retention to 30 days
    - _Requirements: 14.3_
  
  - [ ] 28.4 Add baseline comparison step
    - Download baseline results from repository
    - Run compare_baseline()
    - Fail workflow if regressions detected
    - _Requirements: 4.6, 4.7_

- [ ] 29. Final Validation - Unit Tests
  - [ ] 29.1 Run all unit tests
    - Execute: `pytest tests/lean-proof-auto-mcp-eval_tests/ -m "not eval_" -v`
    - Verify all unit tests pass
    - Fix any failures
    - _Requirements: All_
  
  - [ ] 29.2 Verify test coverage
    - Run pytest with coverage: `pytest --cov=tests/lean-proof-auto-mcp-eval_tests/`
    - Verify coverage > 80% for all modules
    - Add tests for uncovered code paths
    - _Requirements: All_

- [ ] 30. Final Validation - Integration Tests
  - [ ] 30.1 Run all integration tests
    - Execute: `pytest tests/lean-proof-auto-mcp-eval_tests/ -m integration -v`
    - Verify all integration tests pass
    - Fix any failures
    - _Requirements: All_
  
  - [ ] 30.2 Run smoke tier end-to-end
    - Execute: `./run_eval.sh smoke` (or `run_eval.bat smoke` on Windows)
    - Verify completes in < 2 minutes
    - Verify results are valid
    - _Requirements: 13.3, 14.1_

- [ ] 31. Final Validation - Property-Based Tests
  - [ ] 31.1 Run all property-based tests
    - Execute: `pytest tests/lean-proof-auto-mcp-eval_tests/test_properties_*.py -v`
    - Verify all property tests pass
    - Fix any counterexamples found
    - _Requirements: All_
  
  - [ ] 31.2 Increase property test iterations
    - Set hypothesis max_examples to 1000
    - Re-run all property tests
    - Verify no new failures
    - _Requirements: All_

- [ ] 32. Final Validation - Documentation
  - [ ] 32.1 Review README completeness
    - Verify all sections are complete
    - Verify all examples are correct
    - Verify all links work
    - _Requirements: 15.1, 15.2_
  
  - [ ] 32.2 Test documentation examples
    - Execute all example commands from README
    - Verify they work as documented
    - Fix any discrepancies
    - _Requirements: 15.2_
  
  - [ ] 32.3 Add troubleshooting section
    - Document common issues and solutions
    - Document environment variable configuration
    - Document platform-specific considerations
    - _Requirements: 15.2_

## Notes

- Tasks marked with `*` are optional property-based tests
- Each task references specific requirements for traceability
- Property-based tests validate universal correctness properties using Hypothesis
- Integration tests validate component interactions with real MCP server
- The framework maintains strict isolation from source code (Requirements 16.1, 16.2, 16.3)
- All tests use pytest markers for tier and domain filtering
- Execution scripts provide cross-platform support for Linux, macOS, and Windows
