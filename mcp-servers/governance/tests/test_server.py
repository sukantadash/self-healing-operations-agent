from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from governance_mcp.audit import record_audit_event
from governance_mcp.maturity import (
    DEFAULT_THRESHOLD,
    MAX_SCORE,
    MIN_SCORE,
    TrackRecord,
    apply_outcome,
    is_mature,
)
from governance_mcp.policy import (
    DEFAULT_DENY_LIST,
    check_deny_list,
    check_kb_access,
)
from governance_mcp.server import (
    check_content_safety as tool_check_content_safety,
    check_deny_list as tool_check_deny_list,
    check_kb_access as tool_check_kb_access,
    check_self_heal_gate as tool_check_self_heal_gate,
    get_maturity as tool_get_maturity,
    get_track_record as tool_get_track_record,
    record_audit_event as tool_record_audit_event,
    update_maturity as tool_update_maturity,
)


# ---------- policy: check_kb_access ----------

def test_kb_access_same_app_allowed():
    result = check_kb_access("creditcard-app", "creditcard-app")
    assert result["allowed"] is True


def test_kb_access_platform_scoped_allowed():
    result = check_kb_access("platform-scoped", "any-app")
    assert result["allowed"] is True


def test_kb_access_different_app_denied():
    result = check_kb_access("app-a", "app-b")
    assert result["allowed"] is False


# ---------- policy: check_deny_list ----------

def test_deny_list_allowed_operation():
    result = check_deny_list("rollout_restart", {})
    assert result["allowed"] is True
    assert result["matched_rule"] is None


def test_deny_list_blocked_operation():
    for op in DEFAULT_DENY_LIST:
        result = check_deny_list(op, {})
        assert result["allowed"] is False, f"{op} should be denied"
        assert result["matched_rule"] == op


def test_deny_list_response_has_allowed_key_not_denied():
    result = check_deny_list("delete_namespace", {})
    assert "allowed" in result
    assert "denied" not in result


# ---------- maturity scoring ----------

def test_apply_outcome_success():
    assert apply_outcome(50, "success") == 60


def test_apply_outcome_failure():
    assert apply_outcome(50, "failure") == 30


def test_apply_outcome_clamped_at_max():
    assert apply_outcome(95, "success") == MAX_SCORE


def test_apply_outcome_clamped_at_min():
    assert apply_outcome(10, "failure") == MIN_SCORE


def test_apply_outcome_invalid():
    with pytest.raises(ValueError):
        apply_outcome(50, "unknown")


def test_is_mature_at_threshold():
    assert is_mature(80) is True


def test_is_mature_below_threshold():
    assert is_mature(79) is False


# ---------- DESIGN.md §9.2 lifecycle ----------

def test_full_maturity_lifecycle():
    score = 0
    successes_to_graduate = 0
    while score < DEFAULT_THRESHOLD:
        score = apply_outcome(score, "success")
        successes_to_graduate += 1
    assert successes_to_graduate == 8
    assert score == 80
    assert is_mature(score) is True

    score = apply_outcome(score, "failure")
    assert score == 60
    assert is_mature(score) is False


# ---------- TrackRecord ----------

def test_track_record_roundtrip():
    tr = TrackRecord(applied=5, succeeded=3, failed=2)
    d = tr.to_dict()
    assert d == {"applied": 5, "succeeded": 3, "failed": 2}
    restored = TrackRecord.from_dict(d)
    assert restored == tr


# ---------- audit ----------

def test_audit_event(capsys):
    import json
    event = record_audit_event("self_heal", "executor", {"action": "restart"})
    assert event["event_type"] == "self_heal"
    assert event["agent"] == "executor"
    captured = capsys.readouterr()
    parsed = json.loads(captured.out.strip())
    assert parsed["event_type"] == "self_heal"


# ---------- server tool wrappers (with mocked rag client) ----------

def _mock_rag_doc(score: int = 50, track: dict | None = None) -> AsyncMock:
    doc = {"doc_id": "doc-1", "maturity_score": score, "track_record": track or {}}
    mock = AsyncMock()
    mock.get_document = AsyncMock(return_value=doc)
    mock.update_metadata = AsyncMock(return_value=doc)
    return mock


@pytest.mark.asyncio
async def test_tool_check_kb_access_same():
    result = await tool_check_kb_access("myapp", "myapp")
    assert result["allowed"] is True


@pytest.mark.asyncio
async def test_tool_check_kb_access_different():
    result = await tool_check_kb_access("app-a", "app-b")
    assert result["allowed"] is False


@pytest.mark.asyncio
async def test_tool_check_self_heal_gate_mature():
    with patch("governance_mcp.server._rag", _mock_rag_doc(score=90)):
        result = await tool_check_self_heal_gate("doc-1")
    assert result["approved"] is True


@pytest.mark.asyncio
async def test_tool_check_self_heal_gate_immature():
    with patch("governance_mcp.server._rag", _mock_rag_doc(score=30)):
        result = await tool_check_self_heal_gate("doc-1")
    assert result["approved"] is False


@pytest.mark.asyncio
async def test_tool_check_deny_list_allowed():
    result = await tool_check_deny_list("rollout_restart", {})
    assert result["allowed"] is True


@pytest.mark.asyncio
async def test_tool_check_deny_list_blocked():
    result = await tool_check_deny_list("delete_namespace", {})
    assert result["allowed"] is False


@pytest.mark.asyncio
async def test_tool_update_maturity_success():
    mock_rag = _mock_rag_doc(score=50, track={"applied": 1, "succeeded": 1, "failed": 0})
    with patch("governance_mcp.server._rag", mock_rag):
        result = await tool_update_maturity("doc-1", "success")
    assert result["maturity_score"] == 60
    assert result["track_record"]["succeeded"] == 2


@pytest.mark.asyncio
async def test_tool_update_maturity_failure():
    mock_rag = _mock_rag_doc(score=50, track={"applied": 1, "succeeded": 1, "failed": 0})
    with patch("governance_mcp.server._rag", mock_rag):
        result = await tool_update_maturity("doc-1", "failure")
    assert result["maturity_score"] == 30
    assert result["track_record"]["failed"] == 1


@pytest.mark.asyncio
async def test_tool_get_maturity():
    with patch("governance_mcp.server._rag", _mock_rag_doc(score=75)):
        result = await tool_get_maturity("doc-1")
    assert result["maturity_score"] == 75


@pytest.mark.asyncio
async def test_tool_get_track_record():
    tr = {"applied": 3, "succeeded": 2, "failed": 1}
    with patch("governance_mcp.server._rag", _mock_rag_doc(track=tr)):
        result = await tool_get_track_record("doc-1")
    assert result["applied"] == 3
    assert result["succeeded"] == 2
    assert result["failed"] == 1


@pytest.mark.asyncio
async def test_tool_record_audit():
    result = await tool_record_audit_event("test_event", "test_agent", {"key": "val"})
    assert result["event_type"] == "test_event"


@pytest.mark.asyncio
async def test_tool_content_safety_default_safe():
    result = await tool_check_content_safety("hello world")
    assert result["safe"] is True
