/-
Test theorems that aesop can solve trivially.
These theorems should be classified as "trivial" by the probe tool.
-/
import Aesop

-- Simple conjunction that aesop solves immediately
theorem aesop_trivial_and : True ∧ True := by
  aesop

-- Simple disjunction
theorem aesop_trivial_or : True ∨ False := by
  aesop

-- Simple implication
theorem aesop_trivial_imp : True → True := by
  aesop

-- Reflexivity
theorem aesop_trivial_eq : 1 = 1 := by
  aesop
