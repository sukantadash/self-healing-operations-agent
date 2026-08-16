"""Resolution Generator Agent (DESIGN.md Section 4.4).

Uses the LLM to generate a new resolution from the error report when no
matching resolution exists in the KnowledgeBase (Path A).
"""

from __future__ import annotations

import json
from typing import Any

from langgraph.runtime import Runtime

from ..context import AppContext
from ..models import Resolution
from ..state import OrchestratorState


async def run(state: OrchestratorState, runtime: Runtime[AppContext]) -> dict[str, Any]:
    ctx = runtime.context
    report = state.get("error_report")

    error_summary = "Unknown error"
    if report and report.error_entries:
        top = report.error_entries[0]
        error_summary = f"{top.error_type}: {top.description}"

    messages = [
        {
            "role": "system",
            "content": ctx.personas.get("resolution_generator", "You are an SRE resolution generator."),
        },
        {
            "role": "user",
            "content": (
                f"Application: {ctx.app_name}\n"
                f"Namespace: {state.get('namespace', ctx.namespace)}\n"
                f"Error: {error_summary}\n\n"
                "Generate a resolution as JSON with keys: title, root_cause, fix_steps (list), verification."
            ),
        },
    ]

    raw = await ctx.llm.chat(messages)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {"title": "Auto-generated resolution", "root_cause": raw, "fix_steps": [], "verification": ""}

    resolution = Resolution(
        title=data.get("title", "Auto-generated resolution"),
        root_cause=data.get("root_cause", ""),
        fix_steps=data.get("fix_steps", []),
        verification=data.get("verification", ""),
        owning_application=ctx.app_name,
        maturity_score=0,
        origin="ai_generated",
    )

    return {"resolution": resolution, "resolution_found": True}
