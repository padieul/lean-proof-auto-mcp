# Benchmark Tests

This directory contains benchmark tests for measuring system accuracy and performance against defined targets.

## Test Files

### test_declaration_extraction_accuracy.py

Benchmark tests for declaration extraction accuracy using LeanInteract.

**Target:** 95%+ accuracy for declaration extraction

**Test Classes:**

- `TestDeclarationExtractionAccuracy`: Accuracy benchmarks
  - `test_declaration_extraction_accuracy_all_files`: Overall accuracy across all ground truth files
  - `test_declaration_name_accuracy`: Accuracy of name extraction
  - `test_declaration_type_accuracy`: Accuracy of type signature extraction
  - `test_declaration_proof_presence_accuracy`: Accuracy of detecting proof presence
  - `test_declaration_completeness`: Completeness of declaration extraction

- `TestDeclarationExtractionPerformance`: Performance benchmarks
  - `test_extraction_time_per_file`: Benchmark extraction time
  - `test_server_reuse_performance`: Test server reuse improves performance

**Requirements Validated:** 1.4

**Running Tests:**
```bash
# Run all benchmark tests (requires Lean)
uv run pytest tests/benchmark/ -v -m benchmark

# Run specific benchmark
uv run pytest tests/benchmark/test_declaration_extraction_accuracy.py::TestDeclarationExtractionAccuracy::test_declaration_extraction_accuracy_all_files -v

# Run with performance benchmarking
uv run pytest tests/benchmark/test_declaration_extraction_accuracy.py::TestDeclarationExtractionPerformance::test_extraction_time_per_file -v --benchmark-only
```

## Ground Truth Data

Ground truth data is maintained in `tests/fixtures/benchmark_ground_truth.py`.

**Current Coverage:**
- `valid_theorem.lean`: 3 declarations
- `probe_file_multi_theorem.lean`: 3 declarations
- `probe_aesop_trivial.lean`: 3 declarations
- `probe_manual_proofs.lean`: 4 declarations

**Total:** 13 declarations with manually verified:
- Names
- Type signatures
- Proof presence
- Proof references
- Attributes
- Namespaces

## Accuracy Targets

| Metric | Target | Test |
|--------|--------|------|
| Declaration extraction | 95%+ | `test_declaration_extraction_accuracy_all_files` |
| Name extraction | 95%+ | `test_declaration_name_accuracy` |
| Type signature extraction | 95%+ | `test_declaration_type_accuracy` |
| Proof presence detection | 95%+ | `test_declaration_proof_presence_accuracy` |
| Completeness | 95%+ | `test_declaration_completeness` |

## Performance Targets

| Metric | Target | Test |
|--------|--------|------|
| Server reuse speedup | 1.25x+ | `test_server_reuse_performance` |

## Test Markers

- `@pytest.mark.benchmark`: Benchmark tests
- `@pytest.mark.requires_lean`: Tests that require Lean installation
- `@pytest.mark.slow`: Slow tests (may take several seconds)

## Adding New Ground Truth

To add new ground truth data:

1. Create or identify a Lean test file in `tests/fixtures/lean/`
2. Manually verify all declarations in the file
3. Add a `GroundTruthFile` entry to `benchmark_ground_truth.py`
4. Include all declarations with complete information
5. Run the benchmark tests to verify accuracy

Example:
```python
NEW_FILE_GROUND_TRUTH = GroundTruthFile(
    file_path="tests/fixtures/lean/new_file.lean",
    declarations=[
        GroundTruthDeclaration(
            name="theorem_name",
            full_name="theorem_name",
            type_signature="∀ (n : Nat), n = n",
            has_proof=True,
            proof_references=[],
            attributes=[],
            namespace="",
            line_number=1,
        ),
    ],
)
```

## Future Benchmarks

Additional benchmarks to be implemented:
- Proof reference extraction accuracy (95%+ target) - Task 11.3
- Success rates by complexity tier (20-35% overall) - Task 11.4
- Iteration efficiency (2-3 iterations average) - Task 11.5
- False positive rate (< 5%) - Task 11.6
- Performance metrics (search times, validation times) - Task 11.7
