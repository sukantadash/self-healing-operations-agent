"""Client for our own governance-mcp-server.

Signatures match mcp-servers/governance/src/governance_mcp/server.py exactly.
"""

from __future__ import annotations

from typing import Any

from .base import BaseMCPClient

DEFAULT_URL = "http://mcp-governance:8000/mcp"


class GovernanceClient(BaseMCPClient):
    def __init__(self) -> None:
        super().__init__("MCP_GOVERNANCE_URL", DEFAULT_URL)

    async def check_kb_access(self, agent_app: str, target_app: str) -> Any:
        return await self.call_tool("check_kb_access", agent_app=agent_app, target_app=target_app)

    async def check_self_heal_gate(self, doc_id: str) -> Any:
        return await self.call_tool("check_self_heal_gate", doc_id=doc_id)

    async def check_deny_list(self, operation: str, params: dict[str, Any]) -> Any:
        return await self.call_tool("check_deny_list", operation=operation, params=params)

    async def get_maturity(self, doc_id: str) -> Any:
        return await self.call_tool("get_maturity", doc_id=doc_id)

    async def update_maturity(self, doc_id: str, outcome: str) -> Any:
        return await self.call_tool("update_maturity", doc_id=doc_id, outcome=outcome)

    async def get_track_record(self, doc_id: str) -> Any:
        return await self.call_tool("get_track_record", doc_id=doc_id)
