/-
Test fixture: File with type error
Used for integration testing of verify tool error handling
-/

-- This theorem has a type error: trying to add Nat and String
theorem type_mismatch : 5 + "hello" = 5 := by
  rfl
