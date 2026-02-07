"""


LeanInteract Adapter Layer.



This module provides the adapter layer for all Lean interaction using LeanInteract.


It encapsulates LeanInteract behind abstract interfaces (ports) following hexagonal


architecture principles.



Components:


- ports: Abstract interfaces (protocols) for Lean interaction


- querier: Declaration and reference extraction


- proof_state: Proof state inspection and tactic application


- validator: Proof validation


- server_manager: Server lifecycle management
"""



from .ports import (


    Declaration,


    DeclValue,


    Querier,


    ProofState,


    ProofStateInspector,


    ProofValidator,


    Range,


    ServerManager,


    TacticResult,


    TheoremContext,


    ValidationResult,


)


from .proof_state import LeanInteractProofStateInspector


from .querier import LeanInteractQuerier


from .server_manager import LeanInteractServerManager


from .validator import LeanInteractProofValidator



__all__ = [

    # Ports (protocols)

    "Declaration",

    "DeclValue",

    "Querier",

    "ProofState",

    "ProofStateInspector",

    "ProofValidator",

    "Range",

    "ServerManager",

    "TacticResult",

    "TheoremContext",

    "ValidationResult",

    # Implementations
    "LeanInteractQuerier",
    "LeanInteractProofStateInspector",
    "LeanInteractProofValidator",
    "LeanInteractServerManager",
]


