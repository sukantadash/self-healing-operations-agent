from __future__ import annotations

from dataclasses import dataclass, field

SUCCESS_INCREMENT = 10
FAILURE_DECREMENT = -20
MIN_SCORE = 0
MAX_SCORE = 100
DEFAULT_THRESHOLD = 80


@dataclass
class TrackRecord:
    applied: int = 0
    succeeded: int = 0
    failed: int = 0

    def to_dict(self) -> dict:
        return {"applied": self.applied, "succeeded": self.succeeded, "failed": self.failed}

    @classmethod
    def from_dict(cls, data: dict) -> TrackRecord:
        return cls(
            applied=int(data.get("applied", 0)),
            succeeded=int(data.get("succeeded", 0)),
            failed=int(data.get("failed", 0)),
        )


def apply_outcome(current_score: int, outcome: str) -> int:
    if outcome == "success":
        delta = SUCCESS_INCREMENT
    elif outcome == "failure":
        delta = FAILURE_DECREMENT
    else:
        raise ValueError(f"Unknown outcome: {outcome!r}; expected 'success' or 'failure'")
    return max(MIN_SCORE, min(MAX_SCORE, current_score + delta))


def is_mature(score: int, threshold: int = DEFAULT_THRESHOLD) -> bool:
    return score >= threshold
