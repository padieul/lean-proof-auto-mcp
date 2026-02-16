"""


Integration tests for LeanInteract Adapter Layer.



These tests verify that the adapter layer works correctly with real Lean files


and LeanInteract server instances.



Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 3.4, 10.6, 28.4
"""

from pathlib import Path

import pytest

from lean_proof_auto_mcp.lean.querier import LeanInteractQuerier
from lean_proof_auto_mcp.lean.server_manager import LeanInteractServerManager


@pytest.mark.integration
@pytest.mark.requires_lean
class TestLeanInteractIntegration:
    """Integration tests for LeanInteract adapter layer."""

    @pytest.fixture
    def test_file(self):
        """Path to test Lean file."""

        return str(Path(__file__).parent.parent / "fixtures" / "lean" / "valid_theorem.lean")

    @pytest.fixture
    def querier(self):
        """Create a LeanInteractQuerier instance."""

        from pathlib import Path

        from lean_proof_auto_mcp.lean.server_manager import LeanInteractServerManager

        server_manager = LeanInteractServerManager(workspace_path=Path.cwd())

        querier = LeanInteractQuerier(server_manager=server_manager)

        yield querier

        # Cleanup

        server_manager.shutdown_all()

    @pytest.fixture
    def server_manager(self):
        """Create a ServerManager instance."""

        manager = LeanInteractServerManager()

        yield manager

        # Cleanup

        manager.shutdown_all()

    def test_extract_declarations_from_real_file(self, querier, test_file):
        """


        Test extracting declarations from a real Lean file.



        Validates: Requirements 1.1, 1.2, 1.3
        """

        # Act

        declarations = querier.extract_declarations(test_file)

        # Assert

        assert len(declarations) > 0, "Should extract at least one declaration"

        # Verify each declaration has complete information

        for decl in declarations:
            assert decl.name, "Declaration should have a name"

            assert decl.full_name, "Declaration should have a full name"

            assert decl.type, "Declaration should have a type"

            assert isinstance(decl.attributes, list), "Attributes should be a list"

            assert decl.range.start_line >= 0, "Range should have valid start line"

            assert decl.namespace is not None, "Namespace should be present"

        # Verify specific theorems exist

        theorem_names = [d.name for d in declarations]

        assert "simple_add_comm" in theorem_names, "Should find simple_add_comm theorem"

        assert "simple_identity" in theorem_names, "Should find simple_identity theorem"

        assert "nat_zero_add" in theorem_names, "Should find nat_zero_add theorem"

    def test_get_proof_references_from_real_file(self, querier, test_file):
        """


        Test extracting proof references from a real Lean file.



        Validates: Requirements 2.1, 2.2, 2.3
        """

        # Act

        references = querier.get_proof_references(test_file, "simple_add_comm")

        # Assert

        assert isinstance(references, list), "Should return a list of references"

        # The proof uses Nat.add_comm, so it should be in the references

        assert "Nat.add_comm" in references, "Should extract Nat.add_comm reference"

    def test_get_theorem_context_from_real_file(self, querier, test_file):
        """


        Test extracting theorem context from a real Lean file.



        Validates: Requirements 3.1, 3.2, 3.3, 3.4
        """

        # Act

        context = querier.get_theorem_context(test_file, "simple_add_comm")

        # Assert

        assert context.theorem_statement, "Should have theorem statement"

        # theorem_statement is a DeclType object with pp field

        assert hasattr(context.theorem_statement, "pp"), "Statement should have pp field"

        assert context.original_proof, "Should have original proof"

        assert context.namespace is not None, "Should have namespace"

        assert isinstance(context.in_scope, list), "In-scope should be a list"

        assert isinstance(context.hypotheses, list), "Hypotheses should be a list"

    def test_server_reuse_across_operations(self, querier, test_file):
        """


        Test that server instances are reused across multiple operations.



        Validates: Requirements 10.6, 28.4
        """

        # Act: Perform multiple operations on the same file

        declarations1 = querier.extract_declarations(test_file)

        references1 = querier.get_proof_references(test_file, "simple_add_comm")

        context1 = querier.get_theorem_context(test_file, "simple_add_comm")

        # Verify operations succeeded

        assert len(declarations1) > 0

        assert len(references1) > 0

        assert context1.theorem_statement

        # Verify server was reused (only one server in cache)

        assert len(querier._server_cache) == 1

        assert test_file in querier._server_cache

    def test_server_manager_lifecycle(self, server_manager, test_file):
        """


        Test ServerManager lifecycle management.



        Validates: Requirements 28.4, 28.5, 28.6
        """

        # Act: Get server

        server1 = server_manager.get_server(test_file)

        assert server1 is not None

        # Get server again - should reuse

        server2 = server_manager.get_server(test_file)

        assert server2 is server1, "Should reuse same server instance"

        # Restart server

        server_manager.restart_server(test_file)

        server3 = server_manager.get_server(test_file)

        assert server3 is not server1, "Should create new server after restart"

        # Shutdown all

        server_manager.shutdown_all()

        assert len(server_manager._servers) == 0, "All servers should be shut down"

    def test_multiple_files_separate_servers(self, querier):
        """


        Test that different files get separate server instances.



        Validates: Requirements 10.6, 28.4
        """

        # Setup: Get paths to different test files

        fixtures_dir = Path(__file__).parent.parent / "fixtures" / "lean"

        file1 = str(fixtures_dir / "valid_theorem.lean")

        file2 = str(fixtures_dir / "probe_file_multi_theorem.lean")

        # Act: Extract declarations from both files

        declarations1 = querier.extract_declarations(file1)

        declarations2 = querier.extract_declarations(file2)

        # Assert: Both operations succeeded

        assert len(declarations1) > 0

        assert len(declarations2) > 0

        # Verify separate servers

        assert len(querier._server_cache) == 2

        assert file1 in querier._server_cache

        assert file2 in querier._server_cache

        assert querier._server_cache[file1] is not querier._server_cache[file2]

    def test_error_handling_with_invalid_theorem(self, querier, test_file):
        """


        Test error handling when theorem is not found.



        Validates: Requirements 11.3
        """

        # Act & Assert

        with pytest.raises(ValueError, match="Theorem not found"):
            querier.get_proof_references(test_file, "nonexistent_theorem")

        with pytest.raises(ValueError, match="Theorem not found"):
            querier.get_theorem_context(test_file, "nonexistent_theorem")

    def test_cleanup_closes_all_servers(self, querier, test_file):
        """


        Test that cleanup properly closes all servers.



        Validates: Requirements 28.6
        """

        # Setup: Create multiple server instances

        fixtures_dir = Path(__file__).parent.parent / "fixtures" / "lean"

        file1 = str(fixtures_dir / "valid_theorem.lean")

        file2 = str(fixtures_dir / "probe_file_multi_theorem.lean")

        querier.extract_declarations(file1)

        querier.extract_declarations(file2)

        assert len(querier._server_cache) == 2

        # Act: Close all servers

        querier.close()

        # Assert: All servers closed

        assert len(querier._server_cache) == 0
