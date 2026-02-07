"""

Tests for ProofValidator import-based validation approach.


This test verifies that the validator correctly uses the import-based

approach when file_path and theorem_id are provided, preserving all

context (type class instances, variables, namespaces, notation).


Requirements: 7.2, 7.3
"""


from unittest.mock import Mock

from lean_proof_auto_mcp.lean.validator import LeanInteractProofValidator


class TestValidatorImportBased:

    """Test import-based validation approach."""


    def test_construct_validation_with_import_basic(self):

        """Test basic import-based validation construction."""

        # Arrange
        mock_server_manager = Mock()
        validator = LeanInteractProofValidator(server_manager=mock_server_manager)


        file_path = "Fixtures/Algebra/Group.lean"
        theorem_id = "mul_left_cancel"

        theorem_statement = "∀ (a b c : G), a * b = a * c → b = c"

        proof_attempt = "intro a b c h\nexact mul_left_cancel h"


        # Act

        result = validator._construct_validation_with_import(

            file_path, theorem_id, theorem_statement, proof_attempt

        )


        # Assert

        assert "import Fixtures.Algebra.Group" in result

        assert f"-- Validate proof for {theorem_id}" in result

        assert f"example : {theorem_statement} := by" in result

        assert "  intro a b c h" in result

        assert "  exact mul_left_cancel h" in result

        # Should NOT contain "theorem validation_theorem"
        assert "theorem validation_theorem" not in result


    def test_construct_validation_with_import_nested_path(self):

        """Test import path conversion for nested directories."""

        # Arrange
        mock_server_manager = Mock()
        validator = LeanInteractProofValidator(server_manager=mock_server_manager)


        file_path = "Fixtures/Algebra/Group/Subgroup/Basic.lean"

        theorem_id = "subgroup_closure"

        theorem_statement = "IsClosed (closure s)"

        proof_attempt = "apply closure_is_closed"


        # Act

        result = validator._construct_validation_with_import(

            file_path, theorem_id, theorem_statement, proof_attempt

        )


        # Assert

        assert "import Fixtures.Algebra.Group.Subgroup.Basic" in result

        assert ".lean" not in result  # Should strip .lean extension


    def test_construct_validation_with_import_multiline_proof(self):

        """Test import-based validation with multiline proof."""

        # Arrange
        mock_server_manager = Mock()
        validator = LeanInteractProofValidator(server_manager=mock_server_manager)


        file_path = "Test.lean"
        theorem_id = "test_theorem"

        theorem_statement = "True"

        proof_attempt = "intro\napply And.intro\n· trivial\n· trivial"


        # Act

        result = validator._construct_validation_with_import(

            file_path, theorem_id, theorem_statement, proof_attempt

        )


        # Assert

        result.splitlines()

        # Check that proof lines are properly indented
        assert "  intro" in result

        assert "  apply And.intro" in result

        assert "  · trivial" in result


    def test_validate_proof_uses_import_when_context_provided(self):

        """Test that validate_proof uses import-based approach when file_path and
        theorem_id provided."""

        # Arrange
        mock_server_manager = Mock()
        mock_server = Mock()
        mock_server_manager.get_server.return_value = mock_server

        mock_response = Mock()

        mock_response.messages = []

        mock_response.sorries = []

        mock_response.goals = []

        mock_server.run.return_value = mock_response

        validator = LeanInteractProofValidator(server_manager=mock_server_manager)


        # Act

        validator.validate_proof(

            theorem_statement="True",

            proof_attempt="trivial",

            timeout_s=10.0,

            file_path="Test.lean",

            theorem_id="test_theorem",

        )


        # Assert

        # Check that server.run was called

        assert mock_server.run.called

        # Get the command that was passed

        call_args = mock_server.run.call_args

        command = call_args[0][0]
        code = command.cmd


        # Verify it uses import-based approach

        assert "import Test" in code

        assert "example : True := by" in code
        assert "  trivial" in code

        # Should NOT use standalone approach
        assert "theorem validation_theorem" not in code


    def test_validate_proof_fallback_without_context(self):

        """Test that validate_proof falls back to standalone when context not provided."""

        # Arrange
        mock_server_manager = Mock()
        mock_server = Mock()
        mock_server_manager.get_server.return_value = mock_server

        mock_response = Mock()

        mock_response.messages = []

        mock_response.sorries = []

        mock_response.goals = []

        mock_server.run.return_value = mock_response

        validator = LeanInteractProofValidator(server_manager=mock_server_manager)


        # Act

        validator.validate_proof(

            theorem_statement="True",

            proof_attempt="trivial",

            timeout_s=10.0,

            # Note: NOT providing file_path and theorem_id

        )


        # Assert

        # Check that server.run was called

        assert mock_server.run.called

        # Get the command that was passed

        call_args = mock_server.run.call_args

        command = call_args[0][0]
        code = command.cmd


        # Verify it uses standalone approach (fallback)

        assert "theorem validation_theorem : True := by" in code
        assert "trivial" in code

        # Should NOT use import-based approach
        assert "import" not in code

        assert "example" not in code


    def test_validate_proof_partial_context_uses_fallback(self):

        """Test that validate_proof uses fallback if only file_path OR theorem_id provided."""

        # Arrange
        mock_server_manager = Mock()
        mock_server = Mock()
        mock_server_manager.get_server.return_value = mock_server

        mock_response = Mock()

        mock_response.messages = []

        mock_response.sorries = []

        mock_response.goals = []

        mock_server.run.return_value = mock_response

        validator = LeanInteractProofValidator(server_manager=mock_server_manager)


        # Act - only file_path provided

        validator.validate_proof(

            theorem_statement="True",

            proof_attempt="trivial",

            timeout_s=10.0,

            file_path="Test.lean",

            # Note: NOT providing theorem_id

        )


        # Act - only theorem_id provided

        validator.validate_proof(

            theorem_statement="True",

            proof_attempt="trivial",

            timeout_s=10.0,

            theorem_id="test_theorem",

            # Note: NOT providing file_path

        )


        # Assert both use fallback

        for call_args in mock_server.run.call_args_list:

            command = call_args[0][0]
            code = command.cmd
            assert "theorem validation_theorem" in code
            assert "import" not in code

