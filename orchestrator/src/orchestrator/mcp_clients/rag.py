"""Client for our own rag-mcp-server (Diagnosis, Knowledge Curator, Feedback)."""

from __future__ import annotations

from typing import Any

from .base import BaseMCPClient

DEFAULT_URL = "http://mcp-rag:8000/mcp"


class RagClient(BaseMCPClient):
    def __init__(self) -> None:
        super().__init__("MCP_RAG_URL", DEFAULT_URL)

    async def query_kb(self, app: str, query: str, top_k: int = 5) -> Any:
        return await self.call_tool("query_kb", app=app, query=query, top_k=top_k)

    async def ingest_document(self, app: str, doc: dict[str, Any]) -> Any:
        return await self.call_tool("ingest_document", app=app, resolution=doc)

    async def get_document(self, doc_id: str) -> Any:
        return await self.call_tool("get_document", doc_id=doc_id)

    async def update_metadata(self, doc_id: str, fields: dict[str, Any]) -> Any:
        return await self.call_tool("update_metadata", doc_id=doc_id, fields=fields)
