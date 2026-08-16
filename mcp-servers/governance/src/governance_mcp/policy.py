from __future__ import annotations

from typing import Any, TypedDict

DEFAULT_DENY_LIST: list[str] = [
    "delete_namespace",
    "scale_to_zero",
    "modify_rbac",
    "access_secret",
]


class DenyListDecision(TypedDict):
    allowed: bool
    reason: str
    matched_rule: str | None


def check_deny_list(
    operation: str,
    params: dict[str, Any] | None = None,
    deny_list: list[str] | None = None,
) -> DenyListDecision:
    rules = deny_list if deny_list is not None else DEFAULT_DENY_LIST
    if operation in rules:
        return DenyListDecision(
            allowed=False,
            reason=f"Operation '{operation}' is on the deny list.",
            matched_rule=operation,
        )
    return DenyListDecision(
        allowed=True,
        reason="Operation is permitted.",
        matched_rule=None,
    )


def check_kb_access(agent_app: str, target_app: str) -> dict[str, Any]:
    if agent_app == target_app or agent_app == "platform-scoped":
        return {"allowed": True, "reason": "Access granted (same application or platform-scoped)."}
    return {
        "allowed": False,
        "reason": f"Agent app '{agent_app}' is not allowed to access KB for '{target_app}'.",
    }
