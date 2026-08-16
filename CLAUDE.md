# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Self-Healing OpenShift Operations Agent — a multi-agent system that monitors OpenShift applications, diagnoses failures via RAG KnowledgeBases, and autonomously remediates known issues once their resolution maturity scores pass a trust threshold (default 80). Built on RHOAI 3.4 with Llama Stack for RAG and TrustyAI for guardrails.

## Build and Test Commands

```bash
# Run all tests (orchestrator + both MCP servers)
make test

# Run tests for a single component
cd orchestrator && python -m pytest tests/ -v
cd mcp-servers/rag && python -m pytest tests/ -v
cd mcp-servers/governance && python -m pytest tests/ -v

# Run a single test file or test
cd orchestrator && python -m pytest tests/test_graph.py -v
cd orchestrator && python -m pytest tests/test_graph.py::test_path_c_mature_resolution -v

# Lint Helm chart (validates against all values variants)
make helm-lint

# Render Helm templates locally
make helm-template

# Build all container images (requires podman)
make build-all-images REGISTRY=<registry>

# Full end-to-end deploy (requires oc, helm, podman)
make deploy REGISTRY=<registry> SCOPE=app-scoped
```

All Python projects use `hatchling` as the build backend. Tests use `pytest` with `pytest-asyncio` in auto mode — async test functions are detected automatically without markers.

## Architecture

### Three-Layer Structure

- **`orchestrator/`** — LangGraph state machine that coordinates 8 agent roles. Runs as an OpenShift CronJob (every 15 min). Entry point: `python -m orchestrator.main`.
- **`mcp-servers/`** — Two custom FastMCP servers (RAG and Governance) that expose tools over HTTP. Three additional MCP servers (OpenShift readonly, OpenShift executor, Atlassian) use upstream images and are not implemented in this repo.
- **`helm/ops-agent/`** + **`cluster-setup/`** — Deployment layer. Helm chart deploys the app workloads; Kustomize overlays provision platform prerequisites (RHOAI operator, Llama Stack, NeMo Guardrails, namespace).

### Config-Driven Workflow

The orchestrator graph is defined declaratively in `orchestrator/config/workflow.yaml`. Agent personas live in `orchestrator/config/personas.yaml`. Adding a new agent requires: (1) creating a module in `orchestrator/src/orchestrator/agents/` with `async def run(state, runtime)`, (2) registering it in `NODE_REGISTRY` in `graph.py`, (3) adding the node and routing to `workflow.yaml`.

### Three Execution Paths

All paths start with Monitor detecting unhealthy pods:
- **Path A** (no resolution in KB): Monitor → Diagnosis → Governance → Resolution Generator → Knowledge Curator → Ticket Agent → END
- **Path B** (immature resolution, maturity < 80): Monitor → Diagnosis → Governance → Ticket Agent → END
- **Path C** (mature resolution, maturity >= 80): Monitor → Diagnosis → Governance → Executor → Feedback → END

If Monitor finds no errors, the graph exits immediately.

### MCP Communication

The orchestrator talks to all 5 MCP servers via `fastmcp.Client` over HTTP. Each MCP client in `orchestrator/src/orchestrator/mcp_clients/` wraps `BaseMCPClient` which opens a new session per `call_tool` invocation. The governance MCP server also calls the RAG MCP server internally to read/write maturity scores stored as document metadata.

### State Management

No database — state is distributed across: OpenShift (live cluster state), Milvus vector store via Llama Stack (resolution documents + maturity as metadata), and Jira (tickets). The orchestrator's `OrchestratorState` TypedDict is ephemeral per run.

### RBAC Separation

The orchestrator has no direct cluster RBAC. It operates exclusively through two OpenShift MCP servers: one with read-only permissions (`get`, `list`, `watch`) and one with write permissions (`get`, `list`, `watch`, `patch`, `update`). A deny-list blocks dangerous operations: `delete_namespace`, `scale_to_zero`, `modify_rbac`, `access_secret`.

## Key Conventions

- **Python 3.12+**, fully async (`async/await` throughout, `asyncio.run()` at top level)
- **Pydantic v2** for all data models
- **FastMCP >=2.0** for MCP server and client implementations
- **OpenAI-compatible LLM client** (`orchestrator/src/orchestrator/llm.py`) — thin httpx wrapper against `/v1/chat/completions`; default model is `meta-llama/Llama-3.1-70B-Instruct`
- **Container images** use `registry.access.redhat.com/ubi9/python-312:latest` base with `uv` for dependency installation
- **Helm values variants**: `values.yaml` (defaults), `values-app-scoped.yaml` (single app), `values-platform-scoped.yaml` (all apps), `values-test.yaml` (local dev with localhost URLs)
