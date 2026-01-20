-- Simple test theorem for MCP tool testing

theorem simple_add (a b : Nat) : a + b = b + a := by
  rw [Nat.add_comm]

lemma zero_add (n : Nat) : 0 + n = n := by
  rfl

example (x : Nat) : x + 0 = x := by
  simp