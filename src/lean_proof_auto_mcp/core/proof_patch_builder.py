"""
ProofPatchBuilder service for generating Lean proof code.

This module implements the ProofPatchBuilder service that generates
ready-to-paste Lean proof code from hint sets and automation configurations.

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 15.1, 15.2, 15.3, 15.4, 15.5
"""

from lean_proof_auto_mcp.core.search_automated_proof_domain import (
    HintSet,
    HintType,
    ProofPatch,
    StyleConfig,
)

# ============================================================================
# Definitional Proofs (Preserved)
# ============================================================================

DEFINITIONAL_PROOFS = frozenset(["rfl", "Iff.rfl", "trivial"])


# ============================================================================
# ProofPatchBuilder Service
# ============================================================================


class ProofPatchBuilder:
    """
    Generate ready-to-paste Lean proof code from hint sets.

    The ProofPatchBuilder applies style preferences and automation-specific
    formatting to produce syntactically valid Lean code.

    Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 15.1, 15.2, 15.3, 15.4, 15.5
    """

    def build(
        self,
        hint_set: HintSet,
        automation: str,
        style: StyleConfig,
        original_proof: str | None = None,
    ) -> ProofPatch:
        """
        Generate proof patch from hint set and automation configuration.

        Args:
            hint_set: Set of hints to include in proof
            automation: Automation tool used (aesop, grind, simp)
            style: Style configuration for formatting
            original_proof: Original proof text (for preservation check)

        Returns:
            ProofPatch with ready-to-paste Lean code

        Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 15.1, 15.2, 15.3, 15.4, 15.5
        """
        # Check if original proof is definitional and should be preserved
        if original_proof and self._is_definitional_proof(original_proof):
            # Preserve definitional proofs
            lean_code = original_proof.strip()
            return ProofPatch(
                lean_code=lean_code, hint_set=hint_set, automation=automation, style=style
            )

        # Generate proof based on automation tool
        if automation == "simp" or (automation == "aesop" and style.prefer_simp_over_aesop):
            lean_code = self._build_simp_proof(hint_set, style)
        elif automation == "aesop":
            lean_code = self._build_aesop_proof(hint_set, style)
        elif automation == "grind":
            lean_code = self._build_grind_proof(hint_set, style)
        else:
            # Fallback: generic automation call
            lean_code = self._build_generic_proof(hint_set, automation, style)

        return ProofPatch(
            lean_code=lean_code, hint_set=hint_set, automation=automation, style=style
        )

    def _is_definitional_proof(self, proof: str) -> bool:
        """
        Check if proof is definitional and should be preserved.

        Args:
            proof: Proof text to check

        Returns:
            True if proof is definitional, False otherwise

        Requirements: 6.7, 15.1, 15.2, 15.3
        """
        proof_stripped = proof.strip()
        return proof_stripped in DEFINITIONAL_PROOFS

    def _build_simp_proof(self, hint_set: HintSet, style: StyleConfig) -> str:
        """
        Build simp-based proof.

        Args:
            hint_set: Set of hints to include
            style: Style configuration

        Returns:
            Lean code for simp proof

        Requirements: 6.2, 6.4, 6.5, 6.6
        """
        if hint_set.is_empty():
            # No hints: use plain simp
            return "simp"

        # Get sorted hints for deterministic output
        hints = hint_set.to_sorted_list()

        # Extract simp hints
        simp_hints = [h for h in hints if h.type == HintType.SIMP]

        if not simp_hints:
            # No simp hints: use plain simp
            return "simp"

        # Format hint names
        hint_names = [h.name for h in simp_hints]

        # Choose simp variant based on style
        simp_command = "simp only" if style.simp_only_list else "simp_all only"

        # Format hints based on compact style
        if style.emit_compact:
            hints_str = ", ".join(hint_names)
            return f"{simp_command} [{hints_str}]"
        else:
            # Multi-line format
            hints_lines = ",\n  ".join(hint_names)
            return f"{simp_command} [\n  {hints_lines}\n]"

    def _build_aesop_proof(self, hint_set: HintSet, style: StyleConfig) -> str:
        """
        Build aesop-based proof.

        Args:
            hint_set: Set of hints to include
            style: Style configuration

        Returns:
            Lean code for aesop proof

        Requirements: 6.3, 6.4, 6.5
        """
        if hint_set.is_empty():
            # No hints: use plain aesop
            return "aesop"

        # Get sorted hints for deterministic output
        hints = hint_set.to_sorted_list()

        # Categorize hints by type
        safe_hints = [h for h in hints if h.type == HintType.ADD_SAFE]
        unsafe_hints = [h for h in hints if h.type == HintType.ADD_UNSAFE]
        unfold_hints = [h for h in hints if h.type == HintType.UNFOLD]
        simp_hints = [h for h in hints if h.type == HintType.SIMP]

        # Build aesop configuration parts
        parts = []

        if safe_hints:
            safe_names = [h.name for h in safe_hints]
            if style.emit_compact:
                parts.append(f"add safe {', '.join(safe_names)}")
            else:
                parts.append(f"add safe {', '.join(safe_names)}")

        if unsafe_hints:
            unsafe_names = [h.name for h in unsafe_hints]
            if style.emit_compact:
                parts.append(f"add unsafe {', '.join(unsafe_names)}")
            else:
                parts.append(f"add unsafe {', '.join(unsafe_names)}")

        if unfold_hints:
            unfold_names = [h.name for h in unfold_hints]
            if style.emit_compact:
                parts.append(f"unfold {', '.join(unfold_names)}")
            else:
                parts.append(f"unfold {', '.join(unfold_names)}")

        if simp_hints:
            simp_names = [h.name for h in simp_hints]
            if style.emit_compact:
                parts.append(f"simp {', '.join(simp_names)}")
            else:
                parts.append(f"simp {', '.join(simp_names)}")

        if not parts:
            # No categorized hints: use plain aesop
            return "aesop"

        # Format based on compact style
        if style.emit_compact:
            config_str = " ".join(parts)
            return f"aesop ({config_str})"
        else:
            # Multi-line format
            config_lines = "\n  ".join(parts)
            return f"aesop (\n  {config_lines}\n)"

    def _build_grind_proof(self, hint_set: HintSet, style: StyleConfig) -> str:
        """
        Build grind-based proof.

        Args:
            hint_set: Set of hints to include
            style: Style configuration

        Returns:
            Lean code for grind proof

        Requirements: 6.1, 6.4, 6.5
        """
        if hint_set.is_empty():
            # No hints: use plain grind
            return "grind"

        # Get sorted hints for deterministic output
        hints = hint_set.to_sorted_list()
        hint_names = [h.name for h in hints]

        # Format hints based on compact style
        if style.emit_compact:
            hints_str = ", ".join(hint_names)
            return f"grind [{hints_str}]"
        else:
            # Multi-line format
            hints_lines = ",\n  ".join(hint_names)
            return f"grind [\n  {hints_lines}\n]"

    def _build_generic_proof(self, hint_set: HintSet, automation: str, style: StyleConfig) -> str:
        """
        Build generic automation proof (fallback).

        Args:
            hint_set: Set of hints to include
            automation: Automation tool name
            style: Style configuration

        Returns:
            Lean code for generic proof

        Requirements: 6.1, 6.4, 6.5
        """
        if hint_set.is_empty():
            # No hints: use plain automation
            return automation

        # Get sorted hints for deterministic output
        hints = hint_set.to_sorted_list()
        hint_names = [h.name for h in hints]

        # Format hints based on compact style
        if style.emit_compact:
            hints_str = ", ".join(hint_names)
            return f"{automation} [{hints_str}]"
        else:
            # Multi-line format
            hints_lines = ",\n  ".join(hint_names)
            return f"{automation} [\n  {hints_lines}\n]"
