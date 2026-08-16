"""Diagnosis Agent (DESIGN.md Section 4.2).

Calls mcp_clients.rag.query_kb to search the application's KnowledgeBase for
a matching historical resolution. Always hands off to Governance.
"""

from __future__ import annotations

from typing import Any

from langgraph.runtime import Runtime

from ..context import AppContext
from ..models import ErrorReport, Resolution, TrackRecord
from ..state import OrchestratorState


def _build_query(report: ErrorReport | None) -> str:
    if not report or not report.error_entries:
        return "unknown error"
    top = report.error_entries[0]
    return f"{top.error_type}: {top.description}"


def _extract_candidate(result: Any) -> dict[str, Any] | None:
    """`rag-mcp-server.query_kb` returns a list of `{"resolution": {...}, "score":
    ...}` hits (SearchHit shape), ranked best-first."""
    if isinstance(result, list):
        if not result:
            return None
        top = result[0]
        if isinstance(top, dict):
            if isinstance(top.get("resolution"), dict):
                return top["resolution"]
            return top
        return None
    if isinstance(result, dict):
        matches = result.get("matches") or result.get("results")
        if isinstance(matches, list) and matches:
            return _extract_candidate(matches)
        if result.get("doc_id") or result.get("title"):
            return result
        return None
    return None


def _to_resolution(candidate: dict[str, Any], app: str) -> Resolution:
    """Map rag-mcp-server wire dict onto orchestrator's Resolution model."""
    track_record = candidate.get("track_record") or {}
    return Resolution(
        document_id=candidate.get("doc_id") or candidate.get("document_id"),
        title=candidate.get("title", "Untitled resolution"),
        root_cause=candidate.get("root_cause", ""),
        fix_steps=candidate.get("fix_steps", []),
        verification=candidate.get("verification", ""),
        owning_application=candidate.get("owning_app") or candidate.get("owning_application", app),
        maturity_score=int(candidate.get("maturity_score", 0) or 0),
        origin=candidate.get("origin", "ai_generated"),
        track_record=TrackRecord.model_validate(track_record) if track_record else TrackRecord(),
        confluence_url=candidate.get("human_readable_reference") or candidate.get("confluence_url"),
    )


async def run(state: OrchestratorState, runtime: Runtime[AppContext]) -> dict[str, Any]:
    ctx = runtime.context
    report = state.get("error_report")
    query = _build_query(report)

    raw_result = await ctx.rag.query_kb(app=ctx.app_name, query=query)
    candidate = _extract_candidate(raw_result)
    resolution = _to_resolution(candidate, ctx.app_name) if candidate else None

    return {
        "resolution": resolution,
        "resolution_found": resolution is not None,
    }
