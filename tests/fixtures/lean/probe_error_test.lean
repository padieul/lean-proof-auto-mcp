/-
Test fixture: File with errors for testing probe error handling
Used for integration testing of probe tool error handling
-/

-- Theorem with type error
theorem error_example : 5 + "hello" = 5 := by
  rfl
