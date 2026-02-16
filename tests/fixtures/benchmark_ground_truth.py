"""Ground truth data for benchmark tests.

This module contains manually verified ground truth data for testing
declaration extraction accuracy and other benchmarks.

The ground truth is based on actual Lean files in the fixtures directory
and has been manually verified to be correct.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class GroundTruthDeclaration:
    """Ground truth for a single declaration."""

    name: str
    full_name: str
    type_signature: str
    has_proof: bool
    proof_references: list[str]  # Lemmas/theorems used in proof
    attributes: list[str]
    namespace: str
    line_number: int  # Approximate line number in file


@dataclass(frozen=True)
class GroundTruthFile:
    """Ground truth for a complete file."""

    file_path: str
    declarations: list[GroundTruthDeclaration]


# Ground truth for valid_theorem.lean
VALID_THEOREM_GROUND_TRUTH = GroundTruthFile(
    file_path="tests/fixtures/lean/valid_theorem.lean",
    declarations=[
        GroundTruthDeclaration(
            name="simple_add_comm",
            full_name="simple_add_comm",
            type_signature="∀ (a b : Nat), a + b = b + a",
            has_proof=True,
            proof_references=["Nat.add_comm"],
            attributes=[],
            namespace="",
            line_number=1,
        ),
        GroundTruthDeclaration(
            name="simple_identity",
            full_name="simple_identity",
            type_signature="∀ (x : Nat), x = x",
            has_proof=True,
            proof_references=[],  # Uses rfl, no external references
            attributes=[],
            namespace="",
            line_number=4,
        ),
        GroundTruthDeclaration(
            name="nat_zero_add",
            full_name="nat_zero_add",
            type_signature="∀ (n : Nat), 0 + n = n",
            has_proof=True,
            proof_references=["Nat.zero_add"],
            attributes=[],
            namespace="",
            line_number=7,
        ),
    ],
)

# Ground truth for probe_file_multi_theorem.lean
MULTI_THEOREM_GROUND_TRUTH = GroundTruthFile(
    file_path="tests/fixtures/lean/probe_file_multi_theorem.lean",
    declarations=[
        GroundTruthDeclaration(
            name="theorem_one",
            full_name="theorem_one",
            type_signature="∀ (n : Nat), n + 0 = n",
            has_proof=True,
            proof_references=[],  # Uses rfl
            attributes=[],
            namespace="",
            line_number=1,
        ),
        GroundTruthDeclaration(
            name="theorem_two",
            full_name="theorem_two",
            type_signature="∀ (n : Nat), 0 + n = n",
            has_proof=True,
            proof_references=[],  # Uses rfl
            attributes=[],
            namespace="",
            line_number=4,
        ),
        GroundTruthDeclaration(
            name="theorem_three",
            full_name="theorem_three",
            type_signature="∀ (n m : Nat), n + m = m + n",
            has_proof=True,
            proof_references=["Nat.add_comm"],
            attributes=[],
            namespace="",
            line_number=7,
        ),
    ],
)

# Ground truth for probe_aesop_trivial.lean
AESOP_TRIVIAL_GROUND_TRUTH = GroundTruthFile(
    file_path="tests/fixtures/lean/probe_aesop_trivial.lean",
    declarations=[
        GroundTruthDeclaration(
            name="trivial_refl",
            full_name="trivial_refl",
            type_signature="∀ (n : Nat), n = n",
            has_proof=True,
            proof_references=[],  # Uses rfl
            attributes=[],
            namespace="",
            line_number=1,
        ),
        GroundTruthDeclaration(
            name="trivial_symm",
            full_name="trivial_symm",
            type_signature="∀ (n m : Nat), n = m → m = n",
            has_proof=True,
            proof_references=["Eq.symm"],
            attributes=[],
            namespace="",
            line_number=4,
        ),
        GroundTruthDeclaration(
            name="trivial_trans",
            full_name="trivial_trans",
            type_signature="∀ (n m k : Nat), n = m → m = k → n = k",
            has_proof=True,
            proof_references=["Eq.trans"],
            attributes=[],
            namespace="",
            line_number=7,
        ),
    ],
)

# Ground truth for probe_manual_proofs.lean
MANUAL_PROOFS_GROUND_TRUTH = GroundTruthFile(
    file_path="tests/fixtures/lean/probe_manual_proofs.lean",
    declarations=[
        GroundTruthDeclaration(
            name="manual_add_zero",
            full_name="manual_add_zero",
            type_signature="∀ (n : Nat), n + 0 = n",
            has_proof=True,
            proof_references=[],  # Uses rfl
            attributes=[],
            namespace="",
            line_number=1,
        ),
        GroundTruthDeclaration(
            name="manual_zero_add",
            full_name="manual_zero_add",
            type_signature="∀ (n : Nat), 0 + n = n",
            has_proof=True,
            proof_references=["Nat.zero_add"],
            attributes=[],
            namespace="",
            line_number=4,
        ),
        GroundTruthDeclaration(
            name="manual_add_comm",
            full_name="manual_add_comm",
            type_signature="∀ (n m : Nat), n + m = m + n",
            has_proof=True,
            proof_references=["Nat.add_comm"],
            attributes=[],
            namespace="",
            line_number=7,
        ),
        GroundTruthDeclaration(
            name="manual_add_assoc",
            full_name="manual_add_assoc",
            type_signature="∀ (n m k : Nat), n + (m + k) = (n + m) + k",
            has_proof=True,
            proof_references=["Nat.add_assoc"],
            attributes=[],
            namespace="",
            line_number=10,
        ),
    ],
)

# All ground truth files
ALL_GROUND_TRUTH_FILES = [
    VALID_THEOREM_GROUND_TRUTH,
    MULTI_THEOREM_GROUND_TRUTH,
    AESOP_TRIVIAL_GROUND_TRUTH,
    MANUAL_PROOFS_GROUND_TRUTH,
]


def count_total_declarations() -> int:
    """Count total number of declarations in ground truth."""
    return sum(len(gt_file.declarations) for gt_file in ALL_GROUND_TRUTH_FILES)
