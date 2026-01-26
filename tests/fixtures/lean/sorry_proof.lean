/-
Test fixture: File with incomplete proof (sorry)
Used for integration testing of verify tool warning detection
-/

-- Theorem with sorry - incomplete proof
theorem incomplete_proof (a b : Nat) : a + b = b + a := by
  sorry

-- Another theorem with sorry
theorem another_incomplete (x : Nat) : x * 0 = 0 := by
  sorry
