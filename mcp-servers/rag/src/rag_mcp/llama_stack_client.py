from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_URL = "http://llamastack:8321"


class LlamaStackClient:
    def __init__(self, base_url: str | None = None) -> None:
        self._base_url = (base_url or os.environ.get("LLAMA_STACK_URL", DEFAULT_URL)).rstrip("/")
        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=30.0)

    async def create_vector_store(self, name: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"name": name}
        if metadata:
            body["metadata"] = metadata
        resp = await self._client.post("/v1/vector_stores", json=body)
        resp.raise_for_status()
        return resp.json()

    async def list_vector_stores(self) -> list[dict[str, Any]]:
        resp = await self._client.get("/v1/vector_stores")
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            return data
        return data.get("data", [])

    async def create_file(
        self,
        vector_store_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "vector_store_id": vector_store_id,
            "content": content,
        }
        if metadata:
            body["metadata"] = metadata
        resp = await self._client.post(f"/v1/vector_stores/{vector_store_id}/files", json=body)
        resp.raise_for_status()
        return resp.json()

    async def search(
        self,
        vector_store_id: str,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, Any]]:
        body = {"query": query, "max_num_results": max_results}
        resp = await self._client.post(f"/v1/vector_stores/{vector_store_id}/search", json=body)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            return data
        return data.get("data", [])

    async def get_file(self, vector_store_id: str, file_id: str) -> dict[str, Any]:
        resp = await self._client.get(f"/v1/vector_stores/{vector_store_id}/files/{file_id}")
        resp.raise_for_status()
        return resp.json()

    async def update_file_metadata(
        self,
        vector_store_id: str,
        file_id: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        resp = await self._client.post(
            f"/v1/vector_stores/{vector_store_id}/files/{file_id}/metadata",
            json=metadata,
        )
        resp.raise_for_status()
        return resp.json()

    async def close(self) -> None:
        await self._client.aclose()
