"""Application context threaded through the LangGraph runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AppContext:
    namespace: str
    app_name: str
    scope: str
    maturity_threshold: int = 80
    personas: dict[str, str] = field(default_factory=dict)
    llm: Any = None
    openshift_readonly: Any = None
    openshift_executor: Any = None
    atlassian: Any = None
    rag: Any = None
    governance: Any = None
