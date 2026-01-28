/-
Test fixture: Theorems with manual proofs (not automation)
Used to test that probe correctly replaces proofs with automation tactics
-/

-- Theorem with manual proof that aesop CAN solve
theorem manual_and_trivial (p q : Prop) (hp : p) (hq : q) : p ∧ q := by
  exact ⟨hp, hq⟩

-- Theorem with manual proof that aesop CAN solve
theorem manual_or_trivial (p : Prop) (hp : p) : p ∨ False := by
  left
  exact hp

-- Theorem with manual proof that aesop CAN solve
theorem manual_impl_trivial (p q : Prop) (hp : p) (hpq : p → q) : q := by
  apply hpq
  exact hp

-- Theorem with manual proof that aesop CANNOT solve easily
theorem manual_complex (p q r : Prop) (h1 : p → q) (h2 : q → r) (hp : p) : r := by
  apply h2
  apply h1
  exact hp
