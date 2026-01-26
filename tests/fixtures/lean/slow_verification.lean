/-
Test fixture: File that takes significant time to verify
Used for integration testing of verify tool timeout handling
-/

-- This theorem uses a computationally expensive tactic
-- The `decide` tactic will enumerate many cases
theorem slow_computation : (List.range 1000).length = 1000 := by
  decide

-- Another potentially slow verification
theorem slow_proof (n : Nat) (h : n < 100) : n + 1 ≤ 100 := by
  omega
