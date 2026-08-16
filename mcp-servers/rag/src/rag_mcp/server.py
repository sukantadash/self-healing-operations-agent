from __future__ import annotations

import json
import os
import uuid
from typing import Any

from fastmcp import FastMCP

from .collections import CollectionRouter
from .llama_stack_client import LlamaStackClient
from .models import Resolution, SearchHit, TrackRecord

mcp = FastMCP("rag-mcp-server")

_client: LlamaStackClient | None = None
_router: CollectionRouter | None = None


def _get_client() -> LlamaStackClient:
    global _client
    if _client is None:
        _client = LlamaStackClient()
    return _client


def _get_router() -> CollectionRouter:
    global _router
    if _router is None:
        _router = CollectionRouter(_get_client())
    return _router


def _resolution_from_dict(data: dict[str, Any], app: str, doc_id: str) -> Resolution:
    tr = data.get("track_record")
    track_record = TrackRecord.model_validate(tr) if isinstance(tr, dict) else TrackRecord()
    return Resolution(
        doc_id=doc_id,
        owning_app=app,
        title=data.get("title", "Untitled"),
        root_cause=data.get("root_cause", ""),
        fix_steps=data.get("fix_steps", []),
        verification=data.get("verification", ""),
        maturity_score=int(data.get("maturity_score", 0) or 0),
        origin=data.get("origin", "ai_generated"),
        track_record=track_record,
        human_readable_reference=data.get("human_readable_reference"),
    )


@mcp.tool()
async def query_kb(app: str, query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Search the application's KnowledgeBase for matching resolutions."""
    router = _get_router()
    client = _get_client()
    store_id = await router.ensure_collection(app)
    raw_results = await client.search(store_id, query, max_results=top_k)

    hits: list[dict[str, Any]] = []
    for r in raw_results:
        score = float(r.get("score", 0.0))
        content = r.get("content", r.get("metadata", {}))
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except (json.JSONDecodeError, TypeError):
                content = {"title": content}
        file_id = r.get("id", r.get("file_id", str(uuid.uuid4())))
        doc_id = router.doc_id(app, file_id)
        resolution = _resolution_from_dict(content, app, doc_id)
        hit = SearchHit(resolution=resolution, score=score)
        hits.append(hit.model_dump())
    return hits


@mcp.tool()
async def ingest_document(app: str, resolution: dict[str, Any]) -> dict[str, Any]:
    """Ingest a resolution document into the application's KnowledgeBase."""
    router = _get_router()
    client = _get_client()
    store_id = await router.ensure_collection(app)

    file_id = str(uuid.uuid4())
    doc_id = router.doc_id(app, file_id)

    content_str = json.dumps(resolution)
    metadata = {
        "doc_id": doc_id,
        "owning_app": app,
        "maturity_score": resolution.get("maturity_score", 0),
        "origin": resolution.get("origin", "ai_generated"),
    }
    await client.create_file(store_id, content_str, metadata=metadata)

    stored = _resolution_from_dict(resolution, app, doc_id)
    return stored.model_dump()


@mcp.tool()
async def get_document(doc_id: str) -> dict[str, Any]:
    """Retrieve a document by its composite doc_id (app_slug::file_id)."""
    router = _get_router()
    client = _get_client()
    app_slug, file_id = router.parse_doc_id(doc_id)
    store_id = await router.ensure_collection(app_slug)

    raw = await client.get_file(store_id, file_id)
    content = raw.get("content", raw.get("metadata", {}))
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            content = {"title": content}

    resolution = _resolution_from_dict(content, app_slug, doc_id)
    return resolution.model_dump()


@mcp.tool()
async def update_metadata(doc_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    """Update metadata fields on a document."""
    router = _get_router()
    client = _get_client()
    app_slug, file_id = router.parse_doc_id(doc_id)
    store_id = await router.ensure_collection(app_slug)

    result = await client.update_file_metadata(store_id, file_id, fields)
    return {"doc_id": doc_id, **fields, "status": "updated", "raw": result}


if __name__ == "__main__":
    port = int(os.environ.get("MCP_RAG_PORT", "8000"))
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
