"""Monitor Agent (DESIGN.md Section 4.1).

Calls mcp_clients.openshift_readonly to list pods, events, and logs.
Builds an ErrorReport and routes to Diagnosis or terminates if healthy.
"""

from __future__ import annotations

from typing import Any

from langgraph.runtime import Runtime

from ..context import AppContext
from ..models import ErrorEntry, ErrorReport
from ..state import OrchestratorState

UNHEALTHY_STATUSES = {"CrashLoopBackOff", "Error", "ImagePullBackOff", "ErrImagePull", "OOMKilled", "Pending"}


async def run(state: OrchestratorState, runtime: Runtime[AppContext]) -> dict[str, Any]:
    ctx = runtime.context
    namespace = state.get("namespace") or ctx.namespace

    raw_pods = await ctx.openshift_readonly.list_pods(namespace)
    pods = raw_pods if isinstance(raw_pods, list) else (raw_pods.get("pods", []) if isinstance(raw_pods, dict) else [])

    raw_events = await ctx.openshift_readonly.list_events(namespace)
    events = raw_events if isinstance(raw_events, list) else []

    error_entries: list[ErrorEntry] = []
    for pod in pods:
        status = str(pod.get("status", ""))
        if status in UNHEALTHY_STATUSES or int(pod.get("restart_count", 0)) > 3:
            logs = await ctx.openshift_readonly.get_pod_logs(namespace, pod["name"])
            log_text = str(logs) if logs else ""
            error_entries.append(
                ErrorEntry(
                    pod=pod["name"],
                    error_type=status,
                    description=log_text[:500],
                )
            )

    if not error_entries:
        return {
            "error_report": None,
            "monitor_route": "no_errors",
            "terminal_reason": "no_errors_detected",
        }

    report = ErrorReport(namespace=namespace, error_entries=error_entries, raw_pod_statuses=pods)
    return {
        "error_report": report,
        "monitor_route": "errors_found",
    }
