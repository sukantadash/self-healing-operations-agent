"""Entry point for the orchestrator Job."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from .config import load_personas, load_workflow_config
from .context import AppContext
from .graph import build_graph
from .llm import LLMClient
from .mcp_clients.atlassian import AtlassianClient
from .mcp_clients.governance import GovernanceClient
from .mcp_clients.openshift_executor import OpenShiftExecutorClient
from .mcp_clients.openshift_readonly import OpenShiftReadOnlyClient
from .mcp_clients.rag import RagClient


async def _run() -> None:
    config_dir = Path(os.environ.get("CONFIG_DIR", "./config"))
    namespace = os.environ.get("NAMESPACE", "ops-agent")
    scope = os.environ.get("SCOPE", "app-scoped")
    app_name = os.environ.get("APP_NAME", namespace)

    workflow = load_workflow_config(config_dir / "workflow.yaml")
    personas = load_personas(config_dir / "personas.yaml")

    ctx = AppContext(
        namespace=namespace,
        app_name=app_name,
        scope=scope,
        personas=personas,
        llm=LLMClient(),
        openshift_readonly=OpenShiftReadOnlyClient(),
        openshift_executor=OpenShiftExecutorClient(),
        atlassian=AtlassianClient(),
        rag=RagClient(),
        governance=GovernanceClient(),
    )

    graph = build_graph(workflow)
    initial_state = {"namespace": namespace, "scope": scope}
    result = await graph.ainvoke(initial_state, context=ctx)
    print(f"Orchestrator finished: terminal_reason={result.get('terminal_reason', 'unknown')}")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
