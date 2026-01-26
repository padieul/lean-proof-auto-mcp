/-
Test fixture: Multiple theorems for testing probe_file batch processing
Used for integration testing of probe_file tool
-/

-- First theorem - trivial for aesop
theorem multi_theorem_1 (p q : Prop) (hp : p) (hq : q) : p ∧ q := by
  aesop

-- Second theorem - also trivial
theorem multi_theorem_2 (p : Prop) (hp : p) : p ∨ False := by
  aesop

-- Third theorem - simple
theorem multi_theorem_3 (p q : Prop) (hp : p) (hpq : p → q) : q := by
  aesop

-- Fourth theorem - another simple one
theorem multi_theorem_4 (p : Prop) (hp : p) : p := by
  exact hp

-- Fifth theorem - one more
theorem multi_theorem_5 (a b : Nat) (h : a = b) : b = a := by
  grind
