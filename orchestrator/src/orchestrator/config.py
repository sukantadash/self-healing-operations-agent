"""Load workflow and persona configuration from YAML files."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class RoutingEntry:
    type: str  # "always" | "conditional"
    next: str | None = None
    key: str | None = None
    routes: dict[str, str] = field(default_factory=dict)


@dataclass
class WorkflowConfig:
    nodes: list[str] = field(default_factory=list)
    entry_point: str = "monitor"
    routing: dict[str, RoutingEntry] = field(default_factory=dict)


def load_workflow_config(path: Path) -> WorkflowConfig:
    raw = yaml.safe_load(path.read_text())
    routing = {}
    for node_name, entry in raw.get("routing", {}).items():
        routing[node_name] = RoutingEntry(
            type=entry["type"],
            next=entry.get("next"),
            key=entry.get("key"),
            routes=entry.get("routes", {}),
        )
    return WorkflowConfig(
        nodes=raw.get("nodes", []),
        entry_point=raw.get("entry_point", "monitor"),
        routing=routing,
    )


def load_personas(path: Path) -> dict[str, str]:
    return yaml.safe_load(path.read_text()) or {}
