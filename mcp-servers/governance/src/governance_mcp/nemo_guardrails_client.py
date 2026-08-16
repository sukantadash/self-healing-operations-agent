from __future__ import annotations

import os
from typing import Any

import httpx

NEMO_GUARDRAILS_URL = os.getenv("NEMO_GUARDRAILS_URL", "http://nemo-guardrails:8000")
ENABLE_NEMO_GUARDRAILS = os.getenv("ENABLE_NEMO_GUARDRAILS", "false").lower() in ("true", "1", "yes")


async def check_content_safety(text: str) -> dict[str, Any]:
    if not ENABLE_NEMO_GUARDRAILS:
        return {"safe": True, "violations": []}

    async with httpx.AsyncClient(base_url=NEMO_GUARDRAILS_URL, timeout=30) as client:
        response = await client.post(
            "/v1/guardrail/checks",
            json={"input": text},
        )
        response.raise_for_status()
        data = response.json()

    violations = data.get("violations", [])
    return {
        "safe": len(violations) == 0,
        "violations": violations,
    }
