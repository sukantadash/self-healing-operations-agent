"""Governance Agent (DESIGN.md Section 4.3).

Calls mcp_clients.governance for guardrails + evaluation checks and performs
the three-way routing described in DESIGN.md Section 5.3:
  - no resolution found      -> Resolution Generator
  - resolution exists, immature -> Ticket Agent
  - resolution exists, mature   -> Executor Agent
"""

from __future__ import annotations

from typing import Any

from langgraph.runtime import Runtime

from ..context import AppContext
from ..models import EvaluationDecision
from ..state import OrchestratorState


def _truthy(value: Any, key: str, default: bool = True) -> bool:
    if isinstance(value, dict):
        return bool(value.get(key, default))
    if isinstance(value, bool):
        return value
    return default


async def run(state: OrchestratorState, runtime: Runtime[AppContext]) -> dict[str, Any]:
    ctx = runtime.context
    resolution = state.get("resolution")
    threshold = ctx.maturity_threshold

    if resolution is None:
        decision = EvaluationDecision(
            decision="no_resolution",
            matured=False,
            self_heal_approved=False,
            maturity_score=None,
            threshold=threshold,
            rationale="No matching resolution found in the KnowledgeBase.",
        )
        return {"evaluation_decision": decision, "governance_route": "no_resolution"}

    access_result = await ctx.governance.check_kb_access(
        agent_app=ctx.app_name, target_app=resolution.owning_application
    )
    gate_result = await ctx.governance.check_self_heal_gate(
        doc_id=resolution.document_id or ""
    )

    access_allowed = _truthy(access_result, "allowed", default=True)
    gate_approved = _truthy(gate_result, "approved", default=resolution.maturity_score >= threshold)
    matured = access_allowed and gate_approved and resolution.maturity_score >= threshold

    if matured:
        decision = EvaluationDecision(
            decision="mature",
            matured=True,
            self_heal_approved=True,
            maturity_score=resolution.maturity_score,
            threshold=threshold,
            rationale=(
                f"Maturity score {resolution.maturity_score} meets/exceeds threshold "
                f"{threshold}; self-heal gate approved."
            ),
        )
        route = "mature"
    else:
        reason = "below threshold" if resolution.maturity_score < threshold else "gate denied"
        decision = EvaluationDecision(
            decision="immature",
            matured=False,
            self_heal_approved=False,
            maturity_score=resolution.maturity_score,
            threshold=threshold,
            rationale=(
                f"Maturity score {resolution.maturity_score} vs threshold {threshold} "
                f"({reason}); human review required via Jira."
            ),
        )
        route = "immature"

    return {"evaluation_decision": decision, "governance_route": route}
