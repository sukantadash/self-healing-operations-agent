from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Origin(str, Enum):
    HUMAN_AUTHORED = "human_authored"
    AI_GENERATED = "ai_generated"
    HYBRID = "hybrid"


class TrackRecord(BaseModel):
    applied: int = 0
    succeeded: int = 0
    failed: int = 0


class Resolution(BaseModel):
    doc_id: str | None = None
    owning_app: str
    title: str
    root_cause: str
    fix_steps: list[str] = Field(default_factory=list)
    verification: str = ""
    maturity_score: int = 0
    origin: str = Origin.AI_GENERATED.value
    track_record: TrackRecord = Field(default_factory=TrackRecord)
    human_readable_reference: str | None = None


class SearchHit(BaseModel):
    resolution: Resolution
    score: float
