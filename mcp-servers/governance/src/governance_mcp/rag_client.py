from __future__ import annotations

import os
from typing import Any

from fastmcp import Client

RAG_MCP_URL = os.getenv("RAG_MCP_URL", "http://mcp-rag:8000/mcp")


class RagClient:
    def __init__(self, url: str | None = None) -> None:
        self._url = url or RAG_MCP_URL
        self._client = Client(self._url)

    async def get_document(self, doc_id: str) -> dict[str, Any]:
        async with self._client:
            result = await self._client.call_tool("get_document", {"doc_id": doc_id})
            if isinstance(result, dict):
                return result
            return {"doc_id": doc_id}

    async def update_metadata(self, doc_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        async with self._client:
            result = await self._client.call_tool(
                "update_metadata", {"doc_id": doc_id, "fields": fields}
            )
            if isinstance(result, dict):
                return result
            return {"doc_id": doc_id, **fields}
