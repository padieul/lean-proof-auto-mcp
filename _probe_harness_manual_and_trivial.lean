import tests.fixtures.lean.probe_manual_proofs

theorem manual_and_trivial (p q : Prop) (hp : p) (hq : q) : p ∧ q := by
  aesop