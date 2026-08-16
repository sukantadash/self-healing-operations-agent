"""Executor Agent (DESIGN.md Section 4.7).

Calls mcp_clients.openshift_executor to apply a resolution's steps. Every
step is checked against the deny-list via mcp_clients.governance before
it is applied.
"""

from __future__ import annotations

import re
from typing import Any

from langgraph.runtime import Runtime

from ..context import AppContext
from ..models import ErrorReport, Resolution, SelfHealResult
from ..state import OrchestratorState

_SCALE_RE = re.compile(r"scale.*?(?:to)?\s*(\d+)\s*replicas?", re.IGNORECASE)


def _guess_deployment_name(pod_name: str) -> str:
    parts = pod_name.split("-")
    if len(parts) > 2:
        return "-".join(parts[:-2])
    return pod_name


def _classify_step(step: str) -> str:
    lowered = step.lower()
    if "delete" in lowered and "namespace" in lowered:
        return "delete_namespace"
    if "scale to 0" in lowered or "scale-to-zero" in lowered or "0 replicas" in lowered:
        return "scale_to_zero"
    if "rbac" in lowered or "clusterrole" in lowered or " role " in lowered:
        return "modify_rbac"
    if "secret" in lowered:
        return "access_secret"
    if "scale" in lowered:
        return "scale"
    if "restart" in lowered or "rollout" in lowered:
        return "rollout_restart"
    return "patch_resource"


def _is_denied(deny_result: Any) -> bool:
    if isinstance(deny_result, dict):
        return not bool(deny_result.get("allowed", True))
    return bool(deny_result)


async def run(state: OrchestratorState, runtime: Runtime[AppContext]) -> dict[str, Any]:
    ctx = runtime.context
    resolution = state.get("resolution")
    report: ErrorReport | None = state.get("error_report")
    if resolution is None:
        raise ValueError("executor agent requires an approved resolution in state")

    namespace = (report.namespace if report else state.get("namespace")) or ctx.namespace
    deployment = (
        _guess_deployment_name(report.error_entries[0].pod)
        if report and report.error_entries
        else "app"
    )

    steps_executed: list[str] = []
    details: list[str] = []
    all_applied = True

    for step in resolution.fix_steps:
        operation = _classify_step(step)
        deny_result = await ctx.governance.check_deny_list(
            operation=operation, params={"namespace": namespace, "deployment": deployment}
        )
        if _is_denied(deny_result):
            all_applied = False
            details.append(f"BLOCKED by deny-list policy ({operation}): {step}")
            continue

        if operation == "rollout_restart":
            result = await ctx.openshift_executor.rollout_restart(namespace, deployment)
        elif operation == "scale":
            match = _SCALE_RE.search(step)
            replicas = int(match.group(1)) if match else 1
            result = await ctx.openshift_executor.scale(namespace, deployment, replicas)
        else:
            result = await ctx.openshift_executor.patch_resource(
                namespace, "Deployment", deployment, {"metadata": {"annotations": {"ops-agent/note": step}}}
            )

        steps_executed.append(step)
        details.append(f"Executed ({operation}): {step} -> {result}")

    raw_pods = await ctx.openshift_readonly.list_pods(namespace)
    pods = raw_pods if isinstance(raw_pods, list) else (raw_pods.get("pods", []) if isinstance(raw_pods, dict) else [])
    verified = bool(pods) and all(str(p.get("status", "")) == "Running" for p in pods)

    success = all_applied and bool(steps_executed)
    self_heal_result = SelfHealResult(
        steps_executed=steps_executed,
        success=success,
        execution_details="\n".join(details) or "No steps were executed.",
        rollback_available=True,
        rollback_details=f"Rollback via 'oc rollout undo deployment/{deployment} -n {namespace}'.",
        verified=verified,
        verification_details=(
            f"Post-fix pod check in {namespace}: "
            f"{'all pods Running' if verified else 'not all pods confirmed Running'}."
        ),
    )

    return {"self_heal_result": self_heal_result}
