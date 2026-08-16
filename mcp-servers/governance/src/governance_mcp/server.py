from __future__ import annotations

import os
from typing import Any

from fastmcp import FastMCP

from . import audit as audit_mod
from . import nemo_guardrails_client
from . import policy as policy_mod
from .maturity import DEFAULT_THRESHOLD, TrackRecord, apply_outcome, is_mature
from .rag_client import RagClient

MATURITY_THRESHOLD = int(os.getenv("MATURITY_THRESHOLD", str(DEFAULT_THRESHOLD)))
PORT = int(os.getenv("MCP_GOVERNANCE_PORT", "8000"))

mcp = FastMCP("governance-mcp-server")
_rag = RagClient()


@mcp.tool()
async def check_kb_access(agent_app: str, target_app: str) -> dict[str, Any]:
    """Check whether an agent scoped to one application may access another app's KB."""
    return policy_mod.check_kb_access(agent_app, target_app)


@mcp.tool()
async def check_self_heal_gate(doc_id: str) -> dict[str, Any]:
    """Determine whether a resolution is mature enough for autonomous self-heal."""
    doc = await _rag.get_document(doc_id)
    score = int(doc.get("maturity_score", 0) if isinstance(doc, dict) else 0)
    approved = is_mature(score, MATURITY_THRESHOLD)
    return {"approved": approved, "maturity_score": score, "threshold": MATURITY_THRESHOLD}


@mcp.tool()
async def check_deny_list(operation: str, params: dict[str, Any]) -> dict[str, Any]:
    """Validate an operation against the deny-list policy."""
    return dict(policy_mod.check_deny_list(operation, params))


@mcp.tool()
async def check_content_safety(text: str) -> dict[str, Any]:
    """Run content through NeMo Guardrails safety checks (if enabled)."""
    return await nemo_guardrails_client.check_content_safety(text)


@mcp.tool()
async def record_audit_event(event_type: str, agent: str, details: dict[str, Any]) -> dict[str, Any]:
    """Emit a structured audit event to the log."""
    return audit_mod.record_audit_event(event_type, agent, details)


@mcp.tool()
async def get_maturity(doc_id: str) -> dict[str, Any]:
    """Retrieve the current maturity score for a resolution document."""
    doc = await _rag.get_document(doc_id)
    score = int(doc.get("maturity_score", 0) if isinstance(doc, dict) else 0)
    return {"doc_id": doc_id, "maturity_score": score}


@mcp.tool()
async def update_maturity(doc_id: str, outcome: str) -> dict[str, Any]:
    """Update maturity score based on a self-heal outcome ('success' or 'failure')."""
    doc = await _rag.get_document(doc_id)
    current = int(doc.get("maturity_score", 0) if isinstance(doc, dict) else 0)
    new_score = apply_outcome(current, outcome)

    track = TrackRecord.from_dict(doc.get("track_record", {}) if isinstance(doc, dict) else {})
    track.applied += 1
    if outcome == "success":
        track.succeeded += 1
    else:
        track.failed += 1

    await _rag.update_metadata(doc_id, {
        "maturity_score": new_score,
        "track_record": track.to_dict(),
    })
    return {"doc_id": doc_id, "maturity_score": new_score, "track_record": track.to_dict()}


@mcp.tool()
async def get_track_record(doc_id: str) -> dict[str, Any]:
    """Retrieve the track record for a resolution document."""
    doc = await _rag.get_document(doc_id)
    raw = doc.get("track_record", {}) if isinstance(doc, dict) else {}
    track = TrackRecord.from_dict(raw)
    return {"doc_id": doc_id, **track.to_dict()}


if __name__ == "__main__":
    mcp.run(transport="sse", port=PORT)
