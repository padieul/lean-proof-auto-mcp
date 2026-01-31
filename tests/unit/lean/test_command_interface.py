"""
Unit tests for LeanInteract Command interface.

This test verifies that the Command interface is used correctly with the 'cmd'
parameter, not 'code'. This prevents Pydantic validation errors.
"""

import pytest


def test_command_uses_cmd_parameter():
    """
    Verify Command is called with 'cmd' parameter, not 'code'.
    
    This test ensures we don't regress to using Command(code=...) which
    causes Pydantic validation errors.
    """
    try:
        from lean_interact.interface import Command
    except ImportError:
        pytest.skip("lean-interact not installed")
    
    # This should not raise Pydantic validation error
    code = "theorem test : True := by trivial"
    command = Command(cmd=code)
    
    # Verify the command was created successfully
    assert command.cmd == code


def test_command_rejects_code_parameter():
    """
    Verify Command rejects 'code' parameter (the bug we're fixing).
    
    This test documents the bug: Command(code=...) should fail with
    Pydantic validation error.
    """
    try:
        from lean_interact.interface import Command
        from pydantic import ValidationError
    except ImportError:
        pytest.skip("lean-interact not installed")
    
    # This should raise Pydantic validation error
    code = "theorem test : True := by trivial"
    
    with pytest.raises(ValidationError) as exc_info:
        command = Command(code=code)
    
    # Verify it's the expected error
    error_msg = str(exc_info.value)
    assert "cmd" in error_msg.lower()
    assert "required" in error_msg.lower() or "missing" in error_msg.lower()
