"""Ticket Agent (DESIGN.md Section 4.6).

Creates a Jira issue for human review via mcp_clients.atlassian.
"""

from __future__ import annotations

from typing import Any

from langgraph.runtime import Runtime

from ..context import AppContext
from ..models import JiraTicket
from ..state import OrchestratorState


async def run(state: OrchestratorState, runtime: Runtime[AppContext]) -> dict[str, Any]:
    ctx = runtime.context
    resolution = state.get("resolution")
    decision = state.get("evaluation_decision")

    summary = f"[ops-agent] {resolution.title}" if resolution else "[ops-agent] Review required"
    description_parts = [f"Application: {ctx.app_name}", f"Namespace: {ctx.namespace}"]
    if resolution:
        description_parts.append(f"Root cause: {resolution.root_cause}")
        description_parts.append(f"Maturity: {resolution.maturity_score}")
    if decision:
        description_parts.append(f"Decision: {decision.decision} — {decision.rationale}")

    result = await ctx.atlassian.create_jira_issue(
        project_key="OPS",
        summary=summary,
        description="\n".join(description_parts),
    )

    ticket = JiraTicket(
        key=result.get("key", "UNKNOWN") if isinstance(result, dict) else str(result),
        url=result.get("url", "") if isinstance(result, dict) else "",
        summary=summary,
        maturity_score=resolution.maturity_score if resolution else None,
    )

    return {
        "jira_ticket": ticket,
        "terminal_reason": "ticket_created_awaiting_approval",
    }
