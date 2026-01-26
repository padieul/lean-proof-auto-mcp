/-
Test fixture: Valid theorem with no errors
Used for integration testing of verify tool
-/

-- Simple valid theorem that should compile successfully
theorem simple_add_comm (a b : Nat) : a + b = b + a := by
  rw [Nat.add_comm]

-- Another valid theorem
theorem simple_identity (x : Nat) : x = x := by
  rfl

-- Valid theorem with explicit proof
theorem nat_zero_add (n : Nat) : 0 + n = n := by
  rw [Nat.zero_add]
