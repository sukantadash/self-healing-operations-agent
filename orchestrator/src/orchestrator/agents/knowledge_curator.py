"""Knowledge Curator Agent (DESIGN.md Section 4.5).

Calls mcp_clients.atlassian to create a Confluence page and
mcp_clients.rag.ingest_document to index the resolution into the RAG
KnowledgeBase with an initial maturity score of 0.
"""

from __future__ import annotations

from typing import Any

from langgraph.runtime import Runtime

from ..context import AppContext
from ..models import Resolution
from ..state import OrchestratorState


def _render_confluence_body(resolution: Resolution) -> str:
    steps = "\n".join(f"{i + 1}. {step}" for i, step in enumerate(resolution.fix_steps))
    return (
        f"h1. {resolution.title}\n\n"
        f"h2. Root Cause\n{resolution.root_cause}\n\n"
        f"h2. Fix Steps\n{steps}\n\n"
        f"h2. Verification\n{resolution.verification}\n"
    )


def _extract_url(page_result: Any) -> str:
    if isinstance(page_result, dict):
        return str(page_result.get("url") or page_result.get("page_url") or "")
    return str(page_result) if page_result else ""


def _extract_doc_id(ingest_result: Any) -> str:
    """rag-mcp-server returns doc_id, not document_id."""
    if isinstance(ingest_result, dict):
        return str(ingest_result.get("doc_id") or ingest_result.get("document_id") or "")
    return str(ingest_result) if ingest_result else ""


async def run(state: OrchestratorState, runtime: Runtime[AppContext]) -> dict[str, Any]:
    ctx = runtime.context
    resolution = state.get("resolution")
    if resolution is None:
        raise ValueError("knowledge_curator agent requires a resolution in state")

    page_result = await ctx.atlassian.create_confluence_page(
        space_key=ctx.app_name.upper(),
        title=resolution.title,
        body=_render_confluence_body(resolution),
    )
    confluence_url = _extract_url(page_result)

    ingest_result = await ctx.rag.ingest_document(
        app=resolution.owning_application,
        doc={
            "title": resolution.title,
            "root_cause": resolution.root_cause,
            "fix_steps": resolution.fix_steps,
            "verification": resolution.verification,
            "maturity_score": 0,
            "origin": resolution.origin,
            "human_readable_reference": confluence_url,
        },
    )
    doc_id = _extract_doc_id(ingest_result)

    updated_resolution = resolution.model_copy(
        update={"confluence_url": confluence_url or resolution.confluence_url, "document_id": doc_id or resolution.document_id}
    )

    return {
        "resolution": updated_resolution,
        "confluence_url": confluence_url,
        "kb_document_id": doc_id,
    }
