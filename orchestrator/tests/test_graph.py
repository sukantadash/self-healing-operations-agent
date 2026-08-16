"""Builds the graph from config/workflow.yaml with all mcp_clients + llm
mocked, and drives it through the three execution paths from DESIGN.md
Section 5.2, asserting each reaches the matching terminal state and that
routing follows the Section 5.3 table.

Path A -- Monitor -> Diagnosis -> Governance -> Resolution Generator ->
          Knowledge Curator -> Ticket Agent -> DONE   (no resolution found)
Path B -- Monitor -> Diagnosis -> Governance -> Ticket Agent -> DONE
          (resolution found but immature)
Path C -- Monitor -> Diagnosis -> Governance -> Executor -> Feedback -> DONE
          (resolution found and mature)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from orchestrator.config import load_workflow_config
from orchestrator.context import AppContext
from orchestrator.graph import build_graph

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"

FAILING_POD = {"name": "creditcard-app-7d9f8c6b5d-abcde", "status": "CrashLoopBackOff", "restart_count": 5}
HEALTHY_POD = {"name": "creditcard-app-7d9f8c6b5d-abcde", "status": "Running", "restart_count": 0}


class FakeOpenShiftReadOnly:
    def __init__(self, pods: list[dict[str, Any]]) -> None:
        self._pods = pods
        self.calls: list[str] = []

    async def list_pods(self, namespace: str) -> Any:
        self.calls.append("list_pods")
        return self._pods

    async def list_events(self, namespace: str) -> Any:
        self.calls.append("list_events")
        return []

    async def get_pod_logs(self, namespace: str, pod: str, container: str | None = None, tail_lines: int = 200) -> Any:
        self.calls.append("get_pod_logs")
        return "CrashLoopBackOff: exit code 137 (OOMKilled)"


class FakeOpenShiftExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []

    async def rollout_restart(self, namespace: str, deployment: str) -> Any:
        self.calls.append(("rollout_restart", (namespace, deployment), {}))
        return {"status": "patched"}

    async def scale(self, namespace: str, deployment: str, replicas: int) -> Any:
        self.calls.append(("scale", (namespace, deployment, replicas), {}))
        return {"status": "scaled", "replicas": replicas}

    async def patch_resource(self, namespace: str, kind: str, name: str, patch: dict) -> Any:
        self.calls.append(("patch_resource", (namespace, kind, name), {"patch": patch}))
        return {"status": "patched"}


class FakeAtlassian:
    def __init__(self) -> None:
        self.jira_issues: list[dict[str, Any]] = []
        self.confluence_pages: list[dict[str, Any]] = []

    async def create_jira_issue(self, project_key, summary, description, issue_type="Task", **extra):
        ticket = {"key": f"OPS-{len(self.jira_issues) + 1}", "url": "https://jira.example.com/OPS-1", "summary": summary}
        self.jira_issues.append(ticket)
        return ticket

    async def create_confluence_page(self, space_key, title, body, parent_id=None):
        page = {"url": "https://confluence.example.com/pages/1", "title": title}
        self.confluence_pages.append(page)
        return page


class FakeRag:
    def __init__(self, kb_match: dict[str, Any] | None) -> None:
        self._kb_match = kb_match
        self.ingested: list[dict[str, Any]] = []

    async def query_kb(self, app: str, query: str, top_k: int = 5) -> Any:
        if self._kb_match is None:
            return {"matches": []}
        return {"matches": [self._kb_match]}

    async def ingest_document(self, app: str, doc: dict[str, Any]) -> Any:
        doc_id = f"doc-{len(self.ingested) + 1}"
        self.ingested.append(doc)
        return {"document_id": doc_id}

    async def get_document(self, doc_id: str) -> Any:
        return {"document_id": doc_id}

    async def update_metadata(self, doc_id: str, fields: dict[str, Any]) -> Any:
        return {"document_id": doc_id, **fields}


class FakeGovernance:
    def __init__(self, threshold: int, self_heal_approved: bool, deny: bool = False) -> None:
        self.threshold = threshold
        self.self_heal_approved = self_heal_approved
        self.deny = deny
        self.maturity_updates: list[str] = []

    async def check_kb_access(self, agent_app: str, target_app: str) -> Any:
        return {"allowed": True}

    async def check_self_heal_gate(self, doc_id: str) -> Any:
        return {"approved": self.self_heal_approved}

    async def check_deny_list(self, operation: str, params: dict[str, Any]) -> Any:
        return {"allowed": not self.deny}

    async def get_maturity(self, doc_id: str) -> Any:
        return {"maturity_score": 0}

    async def update_maturity(self, doc_id: str, outcome: str) -> Any:
        self.maturity_updates.append(outcome)
        delta = 10 if outcome == "success" else -20
        return {"maturity_score": max(0, min(100, 50 + delta))}

    async def get_track_record(self, doc_id: str) -> Any:
        return {"applied": 1, "succeeded": 1, "failed": 0}


class FakeLLM:
    async def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        return (
            '{"title": "Increase connection pool size", '
            '"root_cause": "Database connection pool exhausted under load.", '
            '"fix_steps": ["Restart the deployment"], '
            '"verification": "Confirm error rate drops to zero."}'
        )


def make_app_context(
    *,
    pods: list[dict[str, Any]],
    kb_match: dict[str, Any] | None,
    threshold: int = 80,
    self_heal_approved: bool = False,
    deny: bool = False,
) -> AppContext:
    return AppContext(
        namespace="creditcard-application",
        app_name="creditcard-application",
        scope="app-scoped",
        maturity_threshold=threshold,
        personas={},
        llm=FakeLLM(),
        openshift_readonly=FakeOpenShiftReadOnly(pods),
        openshift_executor=FakeOpenShiftExecutor(),
        atlassian=FakeAtlassian(),
        rag=FakeRag(kb_match),
        governance=FakeGovernance(threshold, self_heal_approved, deny),
    )


@pytest.fixture
def workflow():
    return load_workflow_config(CONFIG_DIR / "workflow.yaml")


@pytest.fixture
def compiled_graph(workflow):
    return build_graph(workflow)


async def _run(compiled_graph, app_context: AppContext) -> dict:
    initial_state = {"namespace": app_context.namespace, "scope": app_context.scope}
    return await compiled_graph.ainvoke(initial_state, context=app_context)


@pytest.mark.asyncio
async def test_path_a_no_resolution_found(compiled_graph):
    ctx = make_app_context(pods=[FAILING_POD], kb_match=None)

    final_state = await _run(compiled_graph, ctx)

    assert final_state["monitor_route"] == "errors_found"
    assert final_state["governance_route"] == "no_resolution"
    assert final_state["evaluation_decision"].decision == "no_resolution"
    assert final_state["resolution"] is not None
    assert final_state["resolution"].origin == "ai_generated"
    assert final_state["kb_document_id"]
    assert final_state["confluence_url"]
    assert final_state["jira_ticket"] is not None
    assert final_state["terminal_reason"] == "ticket_created_awaiting_approval"


@pytest.mark.asyncio
async def test_path_b_immature_resolution(compiled_graph):
    kb_match = {
        "document_id": "doc-42",
        "title": "Known OOMKilled fix",
        "root_cause": "Memory limit too low",
        "fix_steps": ["Increase memory limit"],
        "verification": "Pod stays Running for 10 minutes",
        "owning_application": "creditcard-application",
        "maturity_score": 30,
        "origin": "ai_generated",
    }
    ctx = make_app_context(pods=[FAILING_POD], kb_match=kb_match, threshold=80, self_heal_approved=False)

    final_state = await _run(compiled_graph, ctx)

    assert final_state["monitor_route"] == "errors_found"
    assert final_state["governance_route"] == "immature"
    assert final_state["evaluation_decision"].decision == "immature"
    assert final_state["evaluation_decision"].self_heal_approved is False
    assert final_state["jira_ticket"] is not None
    assert final_state["jira_ticket"].maturity_score == 30
    assert final_state["terminal_reason"] == "ticket_created_awaiting_approval"
    assert final_state.get("self_heal_result") is None


@pytest.mark.asyncio
async def test_path_c_mature_resolution(compiled_graph):
    kb_match = {
        "document_id": "doc-99",
        "title": "Known CrashLoopBackOff fix",
        "root_cause": "Stale config after deploy",
        "fix_steps": ["Restart the deployment"],
        "verification": "Pod reaches Running and stays healthy",
        "owning_application": "creditcard-application",
        "maturity_score": 90,
        "origin": "ai_generated",
    }
    ctx = make_app_context(
        pods=[HEALTHY_POD], kb_match=kb_match, threshold=80, self_heal_approved=True
    )
    failing_then_healthy = FakeOpenShiftReadOnly([FAILING_POD])
    ctx.openshift_readonly = failing_then_healthy

    call_count = {"n": 0}

    async def list_pods_toggle(namespace: str):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return [FAILING_POD]
        return [HEALTHY_POD]

    failing_then_healthy.list_pods = list_pods_toggle  # type: ignore[method-assign]

    final_state = await _run(compiled_graph, ctx)

    assert final_state["monitor_route"] == "errors_found"
    assert final_state["governance_route"] == "mature"
    assert final_state["evaluation_decision"].decision == "mature"
    assert final_state["evaluation_decision"].self_heal_approved is True
    assert final_state["self_heal_result"] is not None
    assert final_state["self_heal_result"].success is True
    assert final_state["self_heal_result"].verified is True
    assert final_state["resolution"].maturity_score != 90
    assert final_state["terminal_reason"] == "self_heal_succeeded"
    assert final_state.get("jira_ticket") is None


@pytest.mark.asyncio
async def test_monitor_no_errors_ends_immediately(compiled_graph):
    ctx = make_app_context(pods=[HEALTHY_POD], kb_match=None)

    final_state = await _run(compiled_graph, ctx)

    assert final_state["monitor_route"] == "no_errors"
    assert final_state["terminal_reason"] == "no_errors_detected"
    assert final_state.get("resolution") is None
    assert final_state.get("jira_ticket") is None
    assert final_state.get("self_heal_result") is None


def test_routing_table_matches_design_md_section_5_3(workflow):
    assert workflow.routing["monitor"].routes == {"no_errors": "END", "errors_found": "diagnosis"}
    assert workflow.routing["diagnosis"].next == "governance"
    assert workflow.routing["governance"].routes == {
        "no_resolution": "resolution_generator",
        "immature": "ticket_agent",
        "mature": "executor",
    }
    assert workflow.routing["resolution_generator"].next == "knowledge_curator"
    assert workflow.routing["knowledge_curator"].next == "ticket_agent"
    assert workflow.routing["ticket_agent"].next == "END"
    assert workflow.routing["executor"].next == "feedback"
    assert workflow.routing["feedback"].next == "END"
