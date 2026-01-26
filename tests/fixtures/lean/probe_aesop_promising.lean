/-
Test fixture: Theorems where aesop makes progress but doesn't close the goal
Used for integration testing of probe tool classification
-/

-- Theorem where aesop makes some progress but doesn't complete
theorem aesop_promising_example (p q r : Prop) (hp : p) (hq : q) (hr : r) : (p ∧ q) ∧ (q ∧ r) := by
  constructor
  · constructor
    · exact hp
    · exact hq
  · constructor
    · exact hq
    · exact hr
