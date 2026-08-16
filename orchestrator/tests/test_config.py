"""Tests for config loading."""

from pathlib import Path

from orchestrator.config import load_personas, load_workflow_config

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


def test_workflow_loads_all_nodes():
    wf = load_workflow_config(CONFIG_DIR / "workflow.yaml")
    expected = {"monitor", "diagnosis", "governance", "resolution_generator", "knowledge_curator", "ticket_agent", "executor", "feedback"}
    assert set(wf.nodes) == expected


def test_workflow_entry_point():
    wf = load_workflow_config(CONFIG_DIR / "workflow.yaml")
    assert wf.entry_point == "monitor"


def test_routing_entries_valid():
    wf = load_workflow_config(CONFIG_DIR / "workflow.yaml")
    for node in wf.nodes:
        assert node in wf.routing, f"Missing routing for {node}"
        entry = wf.routing[node]
        assert entry.type in ("always", "conditional")


def test_personas_loads_all_agents():
    personas = load_personas(CONFIG_DIR / "personas.yaml")
    expected = {"monitor", "diagnosis", "governance", "resolution_generator", "knowledge_curator", "ticket_agent", "executor", "feedback"}
    assert set(personas.keys()) == expected
