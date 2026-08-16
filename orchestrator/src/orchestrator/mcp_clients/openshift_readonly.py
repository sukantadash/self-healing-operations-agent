"""Client for the read-only OpenShift MCP server (Monitor Agent)."""

from __future__ import annotations

from typing import Any

from .base import BaseMCPClient

DEFAULT_URL = "http://mcp-openshift-readonly:8000/mcp"


class OpenShiftReadOnlyClient(BaseMCPClient):
    def __init__(self) -> None:
        super().__init__("MCP_OPENSHIFT_READONLY_URL", DEFAULT_URL)

    async def list_pods(self, namespace: str) -> Any:
        return await self.call_tool("list_pods", namespace=namespace)

    async def list_events(self, namespace: str) -> Any:
        return await self.call_tool("list_events", namespace=namespace)

    async def get_pod_logs(self, namespace: str, pod: str, container: str | None = None, tail_lines: int = 200) -> Any:
        kwargs: dict[str, Any] = {"namespace": namespace, "pod": pod, "tail_lines": tail_lines}
        if container:
            kwargs["container"] = container
        return await self.call_tool("get_pod_logs", **kwargs)
