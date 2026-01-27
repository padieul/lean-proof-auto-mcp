/-
Test fixture: Theorems for testing grind automation
Used for integration testing of probe tool with grind mode
-/

-- Simple theorem that grind can solve
theorem grind_simple (a b : Nat) (h : a = b) : b = a := by
  grind

-- Another grind-solvable theorem
theorem grind_transitivity (a b c : Nat) (h1 : a = b) (h2 : b = c) : a = c := by
  grind
