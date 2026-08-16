"""Client for the write-scoped OpenShift MCP server (Executor Agent)."""

from __future__ import annotations

from typing import Any

from .base import BaseMCPClient

DEFAULT_URL = "http://mcp-openshift-executor:8000/mcp"


class OpenShiftExecutorClient(BaseMCPClient):
    def __init__(self) -> None:
        super().__init__("MCP_OPENSHIFT_EXECUTOR_URL", DEFAULT_URL)

    async def rollout_restart(self, namespace: str, deployment: str) -> Any:
        return await self.call_tool("rollout_restart", namespace=namespace, deployment=deployment)

    async def scale(self, namespace: str, deployment: str, replicas: int) -> Any:
        return await self.call_tool("scale", namespace=namespace, deployment=deployment, replicas=replicas)

    async def patch_resource(self, namespace: str, kind: str, name: str, patch: dict) -> Any:
        return await self.call_tool("patch_resource", namespace=namespace, kind=kind, name=name, patch=patch)
