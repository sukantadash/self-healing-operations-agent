from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from rag_mcp.collections import CollectionRouter
from rag_mcp.llama_stack_client import LlamaStackClient
from rag_mcp.models import Resolution, SearchHit, TrackRecord
from rag_mcp.server import (
    _get_client,
    _get_router,
    get_document,
    ingest_document,
    query_kb,
    update_metadata,
)
import rag_mcp.server as server_mod


@pytest.fixture(autouse=True)
def reset_singletons():
    server_mod._client = None
    server_mod._router = None
    yield
    server_mod._client = None
    server_mod._router = None


def _mock_client() -> AsyncMock:
    client = AsyncMock(spec=LlamaStackClient)
    client.list_vector_stores = AsyncMock(return_value=[])
    client.create_vector_store = AsyncMock(return_value={"id": "store-1", "name": "kb-test-app"})
    return client


def _patch_client(client: AsyncMock):
    router = CollectionRouter(client)
    server_mod._client = client
    server_mod._router = router
    return router


class TestQueryKb:
    async def test_returns_search_hits(self):
        client = _mock_client()
        resolution_data = {
            "title": "Fix OOM",
            "root_cause": "Memory limit too low",
            "fix_steps": ["Increase memory"],
            "verification": "Pod stays running",
            "maturity_score": 50,
            "origin": "ai_generated",
        }
        client.search = AsyncMock(return_value=[
            {"id": "file-1", "score": 0.95, "content": json.dumps(resolution_data)},
            {"id": "file-2", "score": 0.80, "content": json.dumps({**resolution_data, "title": "Fix OOM v2"})},
        ])
        _patch_client(client)

        result = await query_kb("test-app", "OOMKilled error", top_k=5)

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["score"] == 0.95
        assert result[0]["resolution"]["title"] == "Fix OOM"
        assert result[0]["resolution"]["doc_id"] == "test-app::file-1"
        assert result[0]["resolution"]["owning_app"] == "test-app"

    async def test_empty_results(self):
        client = _mock_client()
        client.search = AsyncMock(return_value=[])
        _patch_client(client)

        result = await query_kb("test-app", "unknown error")
        assert result == []

    async def test_metadata_fallback(self):
        client = _mock_client()
        client.search = AsyncMock(return_value=[
            {"id": "file-1", "score": 0.7, "metadata": {"title": "From metadata", "root_cause": "test"}},
        ])
        _patch_client(client)

        result = await query_kb("test-app", "some error")
        assert result[0]["resolution"]["title"] == "From metadata"


class TestIngestDocument:
    async def test_creates_document_with_generated_doc_id(self):
        client = _mock_client()
        client.create_file = AsyncMock(return_value={"id": "file-new"})
        _patch_client(client)

        doc = {
            "title": "New Fix",
            "root_cause": "Config drift",
            "fix_steps": ["Restart pod"],
            "verification": "Check logs",
            "maturity_score": 0,
            "origin": "ai_generated",
        }
        result = await ingest_document("my-app", doc)

        assert result["owning_app"] == "my-app"
        assert result["title"] == "New Fix"
        assert "::" in result["doc_id"]
        assert result["doc_id"].startswith("my-app::")
        assert result["maturity_score"] == 0

        client.create_file.assert_called_once()
        call_args = client.create_file.call_args
        assert call_args[0][0] == "store-1"

    async def test_preserves_all_fields(self):
        client = _mock_client()
        client.create_file = AsyncMock(return_value={"id": "file-new"})
        _patch_client(client)

        doc = {
            "title": "Complex Fix",
            "root_cause": "Multiple causes",
            "fix_steps": ["Step 1", "Step 2", "Step 3"],
            "verification": "Multi-step verify",
            "maturity_score": 42,
            "origin": "human_authored",
            "human_readable_reference": "https://confluence.example.com/page/123",
        }
        result = await ingest_document("app-x", doc)

        assert result["fix_steps"] == ["Step 1", "Step 2", "Step 3"]
        assert result["origin"] == "human_authored"
        assert result["human_readable_reference"] == "https://confluence.example.com/page/123"
        assert result["maturity_score"] == 42


class TestGetDocument:
    async def test_retrieves_by_doc_id(self):
        client = _mock_client()
        stored = {
            "title": "Stored Fix",
            "root_cause": "Known issue",
            "fix_steps": ["Apply patch"],
            "verification": "Run tests",
            "maturity_score": 75,
        }
        client.get_file = AsyncMock(return_value={"content": json.dumps(stored)})
        _patch_client(client)

        result = await get_document("my-app::file-42")

        assert result["doc_id"] == "my-app::file-42"
        assert result["title"] == "Stored Fix"
        assert result["maturity_score"] == 75
        client.get_file.assert_called_once_with("store-1", "file-42")

    async def test_invalid_doc_id_raises(self):
        client = _mock_client()
        _patch_client(client)

        with pytest.raises(ValueError, match="Invalid doc_id"):
            await get_document("no-separator-here")


class TestUpdateMetadata:
    async def test_updates_fields(self):
        client = _mock_client()
        client.update_file_metadata = AsyncMock(return_value={"status": "ok"})
        _patch_client(client)

        result = await update_metadata("app-z::file-99", {"maturity_score": 80, "origin": "hybrid"})

        assert result["doc_id"] == "app-z::file-99"
        assert result["maturity_score"] == 80
        assert result["origin"] == "hybrid"
        assert result["status"] == "updated"
        client.update_file_metadata.assert_called_once_with("store-1", "file-99", {"maturity_score": 80, "origin": "hybrid"})


class TestCollectionRouting:
    async def test_different_apps_get_different_collections(self):
        client = _mock_client()
        client.create_vector_store = AsyncMock(side_effect=[
            {"id": "store-app1", "name": "kb-app1"},
            {"id": "store-app2", "name": "kb-app2"},
        ])
        router = CollectionRouter(client)

        id1 = await router.ensure_collection("app1")
        id2 = await router.ensure_collection("app2")

        assert id1 != id2
        assert id1 == "store-app1"
        assert id2 == "store-app2"

    async def test_same_app_reuses_collection(self):
        client = _mock_client()
        router = CollectionRouter(client)

        id1 = await router.ensure_collection("app1")
        id2 = await router.ensure_collection("app1")

        assert id1 == id2
        assert client.create_vector_store.call_count == 1

    async def test_existing_collection_not_recreated(self):
        client = _mock_client()
        client.list_vector_stores = AsyncMock(return_value=[
            {"id": "existing-store", "name": "kb-legacy-app"},
        ])
        router = CollectionRouter(client)

        store_id = await router.ensure_collection("legacy-app")

        assert store_id == "existing-store"
        client.create_vector_store.assert_not_called()


class TestMultiTenancy:
    async def test_query_scoped_to_app_collection(self):
        client = _mock_client()
        client.create_vector_store = AsyncMock(side_effect=[
            {"id": "store-a", "name": "kb-app-a"},
            {"id": "store-b", "name": "kb-app-b"},
        ])
        client.search = AsyncMock(return_value=[])
        _patch_client(client)
        server_mod._router = CollectionRouter(client)

        await query_kb("app-a", "test query")
        await query_kb("app-b", "test query")

        calls = client.search.call_args_list
        assert calls[0][0][0] == "store-a"
        assert calls[1][0][0] == "store-b"

    def test_doc_id_format(self):
        assert CollectionRouter.doc_id("myapp", "file-1") == "myapp::file-1"

    def test_parse_doc_id(self):
        app, file_id = CollectionRouter.parse_doc_id("myapp::file-1")
        assert app == "myapp"
        assert file_id == "file-1"

    def test_collection_name(self):
        assert CollectionRouter.collection_name("creditcard") == "kb-creditcard"
