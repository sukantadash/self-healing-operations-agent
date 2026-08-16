from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any


def record_audit_event(event_type: str, agent: str, details: dict[str, Any]) -> dict[str, Any]:
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "agent": agent,
        "details": details,
    }
    print(json.dumps(event), file=sys.stdout, flush=True)
    return event
