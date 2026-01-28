/-
Test theorems with manual proofs (not automation).
These are used to verify that probe correctly extracts signatures
and constructs harnesses, replacing the manual proof with automation.
-/

-- Theorem with manual proof using constructor
theorem manual_and : True ∧ True := by
  constructor
  · trivial
  · trivial

-- Theorem with manual proof using intro
theorem manual_imp : True → True := by
  intro h
  exact h

-- Theorem with manual proof using left
theorem manual_or : True ∨ False := by
  left
  trivial

-- Theorem with manual proof using rfl
theorem manual_eq : 2 + 2 = 4 := by
  rfl

-- Theorem with manual proof using cases
theorem manual_cases : ∀ (b : Bool), b = true ∨ b = false := by
  intro b
  cases b
  · right
    rfl
  · left
    rfl

-- Theorem with multi-line signature
theorem manual_multiline_sig
    (n : Nat)
    (h : n > 0) :
    n ≥ 1 := by
  omega
