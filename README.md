# Self-Healing OpenShift Operations Agent

A multi-agent system that monitors OpenShift applications, diagnoses failures via RAG KnowledgeBases, and self-heals known issues autonomously once their maturity scores graduate past a trust threshold.

Built on RHOAI 3.4 (Red Hat OpenShift AI) with Llama Stack for RAG and TrustyAI for guardrails.

## Architecture

- **8 Agent Roles**: Monitor, Diagnosis, Governance, Resolution Generator, Knowledge Curator, Ticket Agent, Executor, Feedback
- **LangGraph Orchestrator**: Config-driven graph (workflow.yaml + personas.yaml), runs as an OpenShift CronJob
- **5 MCP Servers**: OpenShift (read-only + executor), Atlassian (Jira/Confluence), RAG (custom), Governance (custom)
- **Maturity Scoring**: 0-100 scale, +10 success / -20 failure, graduation threshold (default 80)
- **No Database**: State lives in OpenShift (live), RAG/Milvus doc metadata (maturity), Jira (tickets)

## Prerequisites

- OpenShift 4.14+
- RHOAI 3.4+ operator installed
- Access to an LLM inference endpoint (URL + API key)
- `oc`, `helm`, `podman` CLI tools
- Jira/Confluence instance with API credentials

## Quickstart

```bash
# 1. Clone and configure
git clone <this-repo>
cd intelligent-operations-agent
export IMAGE_REGISTRY=quay.io/yourorg

# 2. Full deployment (cluster setup + build + deploy + smoke test)
make deploy REGISTRY=$IMAGE_REGISTRY

# 3. Or step by step:
make cluster-setup                    # one-time RHOAI bootstrap
make build-all-images REGISTRY=$IMAGE_REGISTRY
make push-all-images REGISTRY=$IMAGE_REGISTRY
helm upgrade --install ops-agent helm/ops-agent \
  --namespace ops-agent --create-namespace \
  -f helm/ops-agent/values-app-scoped.yaml \
  --set image.registry=$IMAGE_REGISTRY
```

## Repository Layout

```
orchestrator/           # LangGraph orchestrator (custom image)
  src/orchestrator/     # graph.py, agents/, mcp_clients/
  config/               # workflow.yaml, personas.yaml
  tests/                # pytest suite
  Containerfile

mcp-servers/
  rag/                  # RAG MCP server wrapping Llama Stack (custom image)
  governance/           # Governance MCP server - policies + maturity (custom image)

helm/ops-agent/         # Helm chart for all components
  templates/            # CronJob, Deployments, RBAC, Services
  values*.yaml          # app-scoped, platform-scoped, test

cluster-setup/          # One-time cluster admin bootstrap (kustomize overlays)
  operators/            # RHOAI operator subscription
  instances/            # DSC, Llama Stack, Guardrails CRs
  overlays/             # 00-04 numbered apply order

scripts/deploy.sh       # End-to-end phased deployment script
Makefile                # Build, test, deploy targets
```

## Design Documents

- [DESIGN.md](DESIGN.md) — Conceptual architecture (agent roles, workflow graph, data model)
- [IMPLEMENTATION.md](IMPLEMENTATION.md) — Component inventory, deployment blueprint, resolved decisions
