"""Find replacement theorem_ids for broken eval fixtures."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from lean_proof_auto_mcp.core.indexer import SourceText, build_index

base = "C:/Dev/lean-proof-auto-mcp-eval/fixtures/mathlib/Fixtures"

# Files that need replacements
broken = [
    "Algebra/Group/Defs.lean",
    "Algebra/Module/Defs.lean",
    "Data/Int/GCD.lean",
    "GroupTheory/GroupAction/Basic.lean",
    "RingTheory/Ideal/Quotient/Operations.lean",
]

for rel in broken:
    fp = os.path.join(base, rel)
    text = open(fp, encoding="utf-8").read()
    idx = build_index(SourceText(path=fp, text=text))
    # Show first 15 theorem-kind decls (skip instances/examples)
    theorems = [d for d in idx.decls if d.kind in ("theorem", "lemma")]
    print(f"\n=== {rel} ({len(theorems)} theorems/lemmas) ===")
    for d in theorems[:15]:
        print(f"  {d.theorem_id} ({d.kind})")
