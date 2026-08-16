"""Feedback Agent (DESIGN.md Section 4.8).

Calls mcp_clients.governance to update the resolution's maturity score
based on the Executor Agent's self-heal result (DESIGN.md Section 9.1:
success -> +10, failure -> -20).
"""

from __future__ import annotations

from typing import Any

from langgraph.runtime import Runtime

from ..context import AppContext
from ..state import OrchestratorState

SUCCESS_INCREMENT = 10
FAILURE_DECREMENT = -20
MIN_SCORE = 0
MAX_SCORE = 100


async def run(state: OrchestratorState, runtime: Runtime[AppContext]) -> dict[str, Any]:
    ctx = runtime.context
    resolution = state.get("resolution")
    result = state.get("self_heal_result")

    if resolution is None or result is None:
        return {"terminal_reason": "feedback_skipped_missing_data"}

    healed = bool(result.success and result.verified)
    outcome = "success" if healed else "failure"

    update_result = await ctx.governance.update_maturity(
        doc_id=resolution.document_id or "", outcome=outcome
    )

    new_score = update_result.get("maturity_score") if isinstance(update_result, dict) else None
    if new_score is None:
        delta = SUCCESS_INCREMENT if healed else FAILURE_DECREMENT
        new_score = max(MIN_SCORE, min(MAX_SCORE, resolution.maturity_score + delta))

    updated_resolution = resolution.model_copy(update={"maturity_score": int(new_score)})

    return {
        "resolution": updated_resolution,
        "terminal_reason": "self_heal_succeeded" if healed else "self_heal_failed_flagged_for_review",
    }
