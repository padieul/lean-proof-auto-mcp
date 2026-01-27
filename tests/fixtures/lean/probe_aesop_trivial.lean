/-
Test fixture: Theorems that aesop can solve trivially
Used for integration testing of probe tool with aesop mode
-/

-- Simple theorem that aesop solves immediately
theorem aesop_trivial_and (p q : Prop) (hp : p) (hq : q) : p ∧ q := by
  aesop

-- Another trivial theorem for aesop
theorem aesop_trivial_or (p : Prop) (hp : p) : p ∨ False := by
  aesop

-- Trivial implication
theorem aesop_trivial_impl (p q : Prop) (hp : p) (hpq : p → q) : q := by
  aesop
