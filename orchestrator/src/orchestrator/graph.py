"""Build a LangGraph StateGraph from config/workflow.yaml."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from .agents import (
    diagnosis,
    executor,
    feedback,
    governance,
    knowledge_curator,
    monitor,
    resolution_generator,
    ticket_agent,
)
from .config import WorkflowConfig
from .context import AppContext
from .state import OrchestratorState

NODE_REGISTRY: dict[str, object] = {
    "monitor": monitor,
    "diagnosis": diagnosis,
    "governance": governance,
    "resolution_generator": resolution_generator,
    "knowledge_curator": knowledge_curator,
    "ticket_agent": ticket_agent,
    "executor": executor,
    "feedback": feedback,
}


def build_graph(config: WorkflowConfig):
    graph = StateGraph(OrchestratorState, context_schema=AppContext)

    for node_name in config.nodes:
        module = NODE_REGISTRY[node_name]
        graph.add_node(node_name, module.run)

    graph.set_entry_point(config.entry_point)

    for node_name in config.nodes:
        entry = config.routing.get(node_name)
        if entry is None:
            continue

        if entry.type == "always":
            target = END if entry.next == "END" else entry.next
            graph.add_edge(node_name, target)
        elif entry.type == "conditional":
            route_key = entry.key
            mapping = {k: (END if v == "END" else v) for k, v in entry.routes.items()}

            def _router(state: OrchestratorState, _key=route_key, _map=mapping) -> str:
                return _map.get(state.get(_key, ""), END)

            graph.add_conditional_edges(node_name, _router)

    return graph.compile()
