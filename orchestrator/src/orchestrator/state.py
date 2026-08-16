"""LangGraph state schema (DESIGN.md Section 5)."""

from __future__ import annotations

from typing import TypedDict

from .models import (
    ErrorReport,
    EvaluationDecision,
    JiraTicket,
    Resolution,
    SelfHealResult,
)


class OrchestratorState(TypedDict, total=False):
    namespace: str
    scope: str
    monitor_route: str
    error_report: ErrorReport | None
    resolution: Resolution | None
    resolution_found: bool
    evaluation_decision: EvaluationDecision | None
    governance_route: str
    kb_document_id: str | None
    confluence_url: str | None
    jira_ticket: JiraTicket | None
    self_heal_result: SelfHealResult | None
    terminal_reason: str
