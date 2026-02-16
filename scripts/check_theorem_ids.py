"""Diagnostic: check what theorem_ids the indexer produces for each eval fixture."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from lean_proof_auto_mcp.core.indexer import SourceText, build_index

files = [
    ("Algebra/Group/Defs.lean", "Group.mul_left_cancel"),
    ("Algebra/Module/Defs.lean", "Module.zero_smul"),
    ("Algebra/Polynomial/Basic.lean", "Polynomial.coeff_zero"),
    ("Analysis/Calculus/Deriv/Basic.lean", "deriv_const"),
    ("Analysis/Calculus/Deriv/MeanValue.lean", "exists_hasDerivAt_eq_slope"),
    ("Data/Int/GCD.lean", "Int.gcd_comm"),
    ("Data/Nat/Totient.lean", "Nat.totient_one"),
    ("GroupTheory/GroupAction/Basic.lean", "MulAction.one_smul"),
    ("GroupTheory/QuotientGroup/Defs.lean", "QuotientGroup.mk_one"),
    ("LinearAlgebra/Basis/Defs.lean", "Basis.repr_self"),
    ("LinearAlgebra/Matrix/Defs.lean", "Matrix.zero_apply"),
    ("RingTheory/Ideal/Defs.lean", "Ideal.zero_mem"),
    ("RingTheory/Ideal/Quotient/Operations.lean", "Ideal.Quotient.mk_zero"),
]

base = "C:/Dev/lean-proof-auto-mcp-eval/fixtures/mathlib/Fixtures"
for rel, expected in files:
    fp = os.path.join(base, rel)
    if not os.path.exists(fp):
        print(f"MISSING: {rel}")
        continue
    text = open(fp, encoding="utf-8").read()
    idx = build_index(SourceText(path=fp, text=text))
    short = expected.split(".")[-1]
    matches = [d.theorem_id for d in idx.decls if short in d.theorem_id]
    print(f"{rel} | expected={expected} | matches={matches[:5]} | total={len(idx.decls)}")
