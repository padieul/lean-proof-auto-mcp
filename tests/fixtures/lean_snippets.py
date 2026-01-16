"""Inline Lean code snippets for testing.

This module contains Lean code as strings to avoid external file dependencies.
Tests can use these snippets to validate parsing and analysis without requiring
a Lean installation or external test files.
"""

# Simple theorem with proof
SIMPLE_THEOREM = """
theorem add_zero (n : Nat) : n + 0 = n := by
  rfl
"""

# Theorem with induction
INDUCTION_THEOREM = """
theorem add_comm (n m : Nat) : n + m = m + n := by
  induction n with
  | zero => simp
  | succ n ih => 
    simp [Nat.add_succ]
    rw [ih]
"""

# Theorem with cases
CASES_THEOREM = """
theorem nat_eq_zero_or_pos (n : Nat) : n = 0 ∨ 0 < n := by
  cases n with
  | zero => left; rfl
  | succ n => right; simp
"""

# Theorem with rewrites
REWRITE_THEOREM = """
theorem mul_comm (n m : Nat) : n * m = m * n := by
  induction n with
  | zero => 
    rw [Nat.zero_mul, Nat.mul_zero]
  | succ n ih =>
    rw [Nat.succ_mul, Nat.mul_succ, ih]
"""

# Lemma example
SIMPLE_LEMMA = """
lemma double_eq_add (n : Nat) : 2 * n = n + n := by
  rw [Nat.two_mul]
"""

# Example with comments
COMMENTED_THEOREM = """
-- This theorem proves commutativity
theorem example_with_comments (a b : Nat) : a + b = b + a := by
  /- We use the standard library theorem -/
  exact Nat.add_comm a b
"""

# File with multiple theorems
MULTI_THEOREM_FILE = """
namespace MyNamespace

theorem first (n : Nat) : n + 0 = n := by
  rfl

theorem second (n : Nat) : 0 + n = n := by
  rfl

lemma helper (n : Nat) : n = n := by
  rfl

end MyNamespace
"""

# Theorem with local lemmas (have, suffices)
LOCAL_LEMMAS_THEOREM = """
theorem with_local_lemmas (n m : Nat) : n + m = m + n := by
  have h1 : n + 0 = n := by rfl
  have h2 : 0 + m = m := by rfl
  suffices n + m = m + n by exact this
  exact Nat.add_comm n m
"""

# Empty file
EMPTY_FILE = ""

# File with only comments
ONLY_COMMENTS = """
-- This file has no theorems
/- Just comments -/
"""

# Malformed theorem (for error handling tests)
MALFORMED_THEOREM = """
theorem incomplete (n : Nat) : n + 0 = n
  -- missing proof
"""
