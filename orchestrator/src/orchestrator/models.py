"""Pydantic data models (DESIGN.md Section 6)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ErrorEntry(BaseModel):
    pod: str
    error_type: str = ""
    description: str = ""
    timestamp: str | None = None


class ErrorReport(BaseModel):
    namespace: str
    error_entries: list[ErrorEntry] = Field(default_factory=list)
    raw_pod_statuses: list[dict] = Field(default_factory=list)


class TrackRecord(BaseModel):
    applied: int = 0
    succeeded: int = 0
    failed: int = 0


class Resolution(BaseModel):
    document_id: str | None = None
    title: str = ""
    root_cause: str = ""
    fix_steps: list[str] = Field(default_factory=list)
    verification: str = ""
    owning_application: str = ""
    maturity_score: int = 0
    origin: str = "ai_generated"
    track_record: TrackRecord = Field(default_factory=TrackRecord)
    confluence_url: str | None = None


class EvaluationDecision(BaseModel):
    decision: str
    matured: bool
    self_heal_approved: bool
    maturity_score: int | None = None
    threshold: int = 80
    rationale: str = ""


class SelfHealResult(BaseModel):
    steps_executed: list[str] = Field(default_factory=list)
    success: bool = False
    execution_details: str = ""
    rollback_available: bool = False
    rollback_details: str = ""
    verified: bool = False
    verification_details: str = ""


class JiraTicket(BaseModel):
    key: str
    url: str
    summary: str
    maturity_score: int | None = None
