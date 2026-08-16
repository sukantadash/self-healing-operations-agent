"""Base MCP client wrapping fastmcp.Client."""

from __future__ import annotations

import os
from typing import Any

from fastmcp import Client


class BaseMCPClient:
    def __init__(self, env_var: str, default_url: str) -> None:
        self._url = os.environ.get(env_var, default_url)
        self._client = Client(self._url)

    async def call_tool(self, name: str, **kwargs: Any) -> Any:
        async with self._client:
            return await self._client.call_tool(name, kwargs)
