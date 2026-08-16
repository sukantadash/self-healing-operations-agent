from __future__ import annotations

from typing import Any

from .llama_stack_client import LlamaStackClient


class CollectionRouter:
    def __init__(self, client: LlamaStackClient) -> None:
        self._client = client
        self._created: set[str] = set()
        self._store_ids: dict[str, str] = {}

    @staticmethod
    def collection_name(app_slug: str) -> str:
        return f"kb-{app_slug}"

    @staticmethod
    def doc_id(app_slug: str, file_id: str) -> str:
        return f"{app_slug}::{file_id}"

    @staticmethod
    def parse_doc_id(doc_id: str) -> tuple[str, str]:
        parts = doc_id.split("::", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid doc_id format: {doc_id}")
        return parts[0], parts[1]

    async def ensure_collection(self, app_slug: str) -> str:
        name = self.collection_name(app_slug)
        if name in self._created:
            return self._store_ids[name]

        existing = await self._client.list_vector_stores()
        for store in existing:
            if store.get("name") == name:
                store_id = store.get("id", name)
                self._store_ids[name] = store_id
                self._created.add(name)
                return store_id

        result = await self._client.create_vector_store(name)
        store_id = result.get("id", name)
        self._store_ids[name] = store_id
        self._created.add(name)
        return store_id

    async def get_store_id(self, app_slug: str) -> str:
        return await self.ensure_collection(app_slug)
