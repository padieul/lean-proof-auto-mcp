"""Benchmark test for declaration extraction accuracy.

This test measures the accuracy of declaration extraction using LeanInteract
against manually verified ground truth data.

Target: 95%+ accuracy for declaration extraction

Requirements: 1.4
"""

import pytest
from pathlib import Path
from typing import List, Set

from lean_proof_auto_mcp.lean.querier import LeanInteractQuerierImpl
from lean_proof_auto_mcp.lean.server_manager import ServerManagerImpl

# Import from relative path instead of absolute 'tests' module
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from fixtures.benchmark_ground_truth import (
    ALL_GROUND_TRUTH_FILES,
    GroundTruthDeclaration,
    GroundTruthFile,
    count_total_declarations,
)


@pytest.mark.benchmark
@pytest.mark.requires_lean
@pytest.mark.slow
class TestDeclarationExtractionAccuracy:
    """Benchmark tests for declaration extraction accuracy."""

    @pytest.fixture
    def querier(self):
        """Create a LeanInteractQuerier instance."""
        server_manager = ServerManagerImpl(workspace_path=Path.cwd())
        querier = LeanInteractQuerierImpl(server_manager=server_manager)
        yield querier
        # Cleanup
        server_manager.shutdown_all()

    def test_declaration_extraction_accuracy_all_files(self, querier):
        """Test declaration extraction accuracy across all ground truth files.

        Target: 95%+ accuracy

        Requirements: 1.4
        """
        total_declarations = 0
        correct_extractions = 0
        missing_declarations = []
        incorrect_extractions = []

        for gt_file in ALL_GROUND_TRUTH_FILES:
            file_path = str(Path(__file__).parent.parent / gt_file.file_path)

            # Skip if file doesn't exist
            if not Path(file_path).exists():
                pytest.skip(f"Test file not found: {file_path}")

            # Extract declarations using LeanInteract
            try:
                extracted_decls = querier.extract_declarations(file_path)
            except Exception as e:
                pytest.fail(f"Failed to extract declarations from {file_path}: {e}")

            # Compare with ground truth
            extracted_names = {decl.name for decl in extracted_decls}
            gt_names = {decl.name for decl in gt_file.declarations}

            # Count correct extractions
            for gt_decl in gt_file.declarations:
                total_declarations += 1

                if gt_decl.name in extracted_names:
                    # Found the declaration
                    extracted_decl = next(
                        d for d in extracted_decls if d.name == gt_decl.name
                    )

                    # Verify key properties
                    is_correct = self._verify_declaration(gt_decl, extracted_decl)

                    if is_correct:
                        correct_extractions += 1
                    else:
                        incorrect_extractions.append(
                            {
                                "file": file_path,
                                "name": gt_decl.name,
                                "reason": "Property mismatch",
                            }
                        )
                else:
                    # Missing declaration
                    missing_declarations.append(
                        {"file": file_path, "name": gt_decl.name}
                    )

        # Calculate accuracy
        accuracy = (
            correct_extractions / total_declarations if total_declarations > 0 else 0.0
        )

        # Report results
        print(f"\n{'='*60}")
        print("Declaration Extraction Accuracy Benchmark")
        print(f"{'='*60}")
        print(f"Total declarations: {total_declarations}")
        print(f"Correct extractions: {correct_extractions}")
        print(f"Missing declarations: {len(missing_declarations)}")
        print(f"Incorrect extractions: {len(incorrect_extractions)}")
        print(f"Accuracy: {accuracy * 100:.2f}%")
        print(f"Target: 95.00%")
        print(f"{'='*60}")

        if missing_declarations:
            print("\nMissing declarations:")
            for missing in missing_declarations:
                print(f"  - {missing['file']}: {missing['name']}")

        if incorrect_extractions:
            print("\nIncorrect extractions:")
            for incorrect in incorrect_extractions:
                print(
                    f"  - {incorrect['file']}: {incorrect['name']} ({incorrect['reason']})"
                )

        # Assert accuracy meets target
        assert (
            accuracy >= 0.95
        ), f"Declaration extraction accuracy {accuracy*100:.2f}% is below 95% target"

    def test_declaration_name_accuracy(self, querier):
        """Test accuracy of declaration name extraction.

        Requirements: 1.1, 1.2
        """
        total_names = 0
        correct_names = 0

        for gt_file in ALL_GROUND_TRUTH_FILES:
            file_path = str(Path(__file__).parent.parent / gt_file.file_path)

            if not Path(file_path).exists():
                continue

            try:
                extracted_decls = querier.extract_declarations(file_path)
            except Exception:
                continue

            extracted_names = {decl.name for decl in extracted_decls}

            for gt_decl in gt_file.declarations:
                total_names += 1
                if gt_decl.name in extracted_names:
                    correct_names += 1

        accuracy = correct_names / total_names if total_names > 0 else 0.0

        print(f"\nName extraction accuracy: {accuracy * 100:.2f}%")

        assert accuracy >= 0.95, f"Name accuracy {accuracy*100:.2f}% below 95% target"

    def test_declaration_type_accuracy(self, querier):
        """Test accuracy of type signature extraction.

        Requirements: 1.2
        """
        total_types = 0
        correct_types = 0

        for gt_file in ALL_GROUND_TRUTH_FILES:
            file_path = str(Path(__file__).parent.parent / gt_file.file_path)

            if not Path(file_path).exists():
                continue

            try:
                extracted_decls = querier.extract_declarations(file_path)
            except Exception:
                continue

            for gt_decl in gt_file.declarations:
                total_types += 1

                # Find matching extracted declaration
                matching_decl = next(
                    (d for d in extracted_decls if d.name == gt_decl.name), None
                )

                if matching_decl and matching_decl.type:
                    # Normalize type signatures for comparison
                    gt_type_normalized = self._normalize_type(gt_decl.type_signature)
                    extracted_type_normalized = self._normalize_type(
                        matching_decl.type.pp if hasattr(matching_decl.type, 'pp') else str(matching_decl.type)
                    )

                    if gt_type_normalized == extracted_type_normalized:
                        correct_types += 1

        accuracy = correct_types / total_types if total_types > 0 else 0.0

        print(f"\nType signature extraction accuracy: {accuracy * 100:.2f}%")

        assert accuracy >= 0.95, f"Type accuracy {accuracy*100:.2f}% below 95% target"

    def test_declaration_proof_presence_accuracy(self, querier):
        """Test accuracy of detecting whether declarations have proofs.

        Requirements: 1.3
        """
        total_checks = 0
        correct_checks = 0

        for gt_file in ALL_GROUND_TRUTH_FILES:
            file_path = str(Path(__file__).parent.parent / gt_file.file_path)

            if not Path(file_path).exists():
                continue

            try:
                extracted_decls = querier.extract_declarations(file_path)
            except Exception:
                continue

            for gt_decl in gt_file.declarations:
                total_checks += 1

                # Find matching extracted declaration
                matching_decl = next(
                    (d for d in extracted_decls if d.name == gt_decl.name), None
                )

                if matching_decl:
                    has_proof = matching_decl.value is not None
                    if has_proof == gt_decl.has_proof:
                        correct_checks += 1

        accuracy = correct_checks / total_checks if total_checks > 0 else 0.0

        print(f"\nProof presence detection accuracy: {accuracy * 100:.2f}%")

        assert (
            accuracy >= 0.95
        ), f"Proof presence accuracy {accuracy*100:.2f}% below 95% target"

    def test_declaration_completeness(self, querier):
        """Test that all expected declarations are extracted.

        Requirements: 1.1
        """
        total_expected = count_total_declarations()
        total_found = 0

        for gt_file in ALL_GROUND_TRUTH_FILES:
            file_path = str(Path(__file__).parent.parent / gt_file.file_path)

            if not Path(file_path).exists():
                continue

            try:
                extracted_decls = querier.extract_declarations(file_path)
            except Exception:
                continue

            extracted_names = {decl.name for decl in extracted_decls}
            gt_names = {decl.name for decl in gt_file.declarations}

            # Count how many ground truth declarations were found
            found_in_file = len(gt_names.intersection(extracted_names))
            total_found += found_in_file

        completeness = total_found / total_expected if total_expected > 0 else 0.0

        print(f"\nDeclaration completeness: {completeness * 100:.2f}%")
        print(f"Found {total_found} out of {total_expected} expected declarations")

        assert (
            completeness >= 0.95
        ), f"Completeness {completeness*100:.2f}% below 95% target"

    def _verify_declaration(
        self, gt_decl: GroundTruthDeclaration, extracted_decl
    ) -> bool:
        """Verify that an extracted declaration matches ground truth.

        Args:
            gt_decl: Ground truth declaration
            extracted_decl: Extracted declaration from LeanInteract

        Returns:
            True if declaration matches ground truth, False otherwise
        """
        # Check name
        if extracted_decl.name != gt_decl.name:
            return False

        # Check type signature (normalized)
        if extracted_decl.type:
            extracted_type = extracted_decl.type.pp if hasattr(extracted_decl.type, 'pp') else str(extracted_decl.type)
            gt_type = gt_decl.type_signature
            if self._normalize_type(extracted_type) != self._normalize_type(gt_type):
                return False

        # Check proof presence
        has_proof = extracted_decl.value is not None
        if has_proof != gt_decl.has_proof:
            return False

        # Check namespace
        if extracted_decl.namespace != gt_decl.namespace:
            # Allow empty string vs None
            if not (
                (extracted_decl.namespace == "" and gt_decl.namespace == "")
                or (extracted_decl.namespace is None and gt_decl.namespace == "")
                or (extracted_decl.namespace == "" and gt_decl.namespace is None)
            ):
                return False

        return True

    def _normalize_type(self, type_str: str) -> str:
        """Normalize a type signature for comparison.

        Removes whitespace variations and normalizes formatting.

        Args:
            type_str: Type signature string

        Returns:
            Normalized type signature
        """
        # Remove extra whitespace
        normalized = " ".join(type_str.split())

        # Remove spaces around parentheses and operators
        normalized = normalized.replace(" ( ", "(").replace(" )", ")")
        normalized = normalized.replace(" : ", ":")
        normalized = normalized.replace(" , ", ",")

        return normalized.strip()


@pytest.mark.benchmark
@pytest.mark.requires_lean
class TestDeclarationExtractionPerformance:
    """Benchmark tests for declaration extraction performance."""

    @pytest.fixture
    def querier(self):
        """Create a LeanInteractQuerier instance."""
        server_manager = ServerManagerImpl(workspace_path=Path.cwd())
        querier = LeanInteractQuerierImpl(server_manager=server_manager)
        yield querier
        server_manager.shutdown_all()

    def test_extraction_time_per_file(self, querier, benchmark):
        """Benchmark extraction time for a single file.

        Requirements: 10.6
        """
        file_path = str(
            Path(__file__).parent.parent
            / "fixtures"
            / "lean"
            / "valid_theorem.lean"
        )

        if not Path(file_path).exists():
            pytest.skip(f"Test file not found: {file_path}")

        # Benchmark the extraction
        result = benchmark(querier.extract_declarations, file_path)

        # Verify result is valid
        assert len(result) > 0, "Should extract at least one declaration"

        print(f"\nExtraction time: {benchmark.stats['mean'] * 1000:.2f}ms")

    def test_server_reuse_performance(self, querier):
        """Test that server reuse improves performance.

        Requirements: 10.6, 28.4
        """
        import time

        file_path = str(
            Path(__file__).parent.parent
            / "fixtures"
            / "lean"
            / "valid_theorem.lean"
        )

        if not Path(file_path).exists():
            pytest.skip(f"Test file not found: {file_path}")

        # First extraction (cold start)
        start = time.time()
        querier.extract_declarations(file_path)
        first_time = time.time() - start

        # Second extraction (warm start - server reuse)
        start = time.time()
        querier.extract_declarations(file_path)
        second_time = time.time() - start

        print(f"\nFirst extraction (cold): {first_time * 1000:.2f}ms")
        print(f"Second extraction (warm): {second_time * 1000:.2f}ms")
        print(f"Speedup: {first_time / second_time:.2f}x")

        # Second extraction should be faster due to server reuse
        # Allow some variance, but expect at least 20% improvement
        assert (
            second_time < first_time * 0.8
        ), "Server reuse should improve performance"
