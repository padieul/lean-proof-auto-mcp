from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    server_name: str
    api_version: str
    working_directory: str

    @staticmethod
    def from_env() -> Config:
        # Default to current working directory if not specified
        default_cwd = os.getcwd()

        return Config(
            server_name=os.getenv("LPAMCP_SERVER_NAME", "lean-proof-auto-mcp"),
            api_version=os.getenv("LPAMCP_API_VERSION", "0.1.0"),
            working_directory=os.getenv("LPAMCP_WORKING_DIR", default_cwd),
        )
