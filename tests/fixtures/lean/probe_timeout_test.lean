/-
Test fixture: Theorem that may timeout with small budget
Used for integration testing of probe tool timeout handling
-/

-- Complex theorem that might take longer to solve
theorem timeout_candidate (n : Nat) : n + 0 = n := by
  induction n with
  | zero => rfl
  | succ n ih => simp [Nat.add_succ, ih]
