#!/usr/bin/env bash
# deploy.sh — end-to-end bootstrap + deploy for the Self-Healing OpenShift Operations Agent
# Mirrors the phased-overlay + wait-for-ready pattern from sukantadash/rhoai3 llm-d/llmd-script.sh
set -euo pipefail

NAMESPACE="${NAMESPACE:-ops-agent}"
SCOPE="${SCOPE:-app-scoped}"
IMAGE_REGISTRY="${IMAGE_REGISTRY:?Set IMAGE_REGISTRY, e.g. quay.io/yourorg}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
SKIP_CLUSTER_SETUP="${SKIP_CLUSTER_SETUP:-false}"
SKIP_BUILD="${SKIP_BUILD:-false}"

# ---- logging helpers -------------------------------------------------------
c_reset='\033[0m'; c_blue='\033[1;34m'; c_green='\033[1;32m'; c_red='\033[1;31m'
phase()  { echo -e "\n${c_blue}==> Phase: $*${c_reset}"; }
ok()     { echo -e "${c_green}✔ $*${c_reset}"; }
fail()   { echo -e "${c_red}✘ $*${c_reset}"; exit 1; }

wait_for() {
  local desc="$1" jsonpath="$2" expected="$3" timeout="${4:-300}"
  shift 4
  local waited=0
  until [[ "$(oc get "$@" -o jsonpath="${jsonpath}" 2>/dev/null)" == "${expected}" ]]; do
    ((waited >= timeout)) && fail "Timed out waiting for ${desc}"
    sleep 5; ((waited+=5))
  done
  ok "${desc} ready"
}

# ---- Phase 1: RHOAI operator ------------------------------------------------
if [[ "${SKIP_CLUSTER_SETUP}" != "true" ]]; then
  phase "1/7 RHOAI operator subscription"
  oc apply -k cluster-setup/overlays/00-operators
  wait_for "RHOAI operator CSV" \
    '{.items[0].status.phase}' 'Succeeded' 600 \
    csv -n openshift-operators -l operators.coreos.com/rhods-operator.openshift-operators

  # ---- Phase 2: DSCI + DataScienceCluster -----------------------------------
  phase "2/7 DSCInitialization + DataScienceCluster"
  oc apply -k cluster-setup/overlays/01-rhoai-instances
  wait_for "DSCInitialization" '{.status.phase}' 'Ready' 600 dsci default-dsci
  wait_for "DataScienceCluster" '{.status.phase}' 'Ready' 600 dsc default-dsc

  # ---- Phase 3: Llama Stack (RAG) + Guardrails (TrustyAI) -------------------
  phase "3/7 Llama Stack distribution (RAG backing store)"
  oc apply -k cluster-setup/overlays/02-llama-stack
  wait_for "LlamaStackDistribution" '{.status.phase}' 'Ready' 600 \
    llamastackdistribution -n "${NAMESPACE}" default

  phase "3b/7 NeMo Guardrails (optional content-safety layer)"
  oc apply -k cluster-setup/overlays/03-guardrails || echo "  (guardrails optional — continuing without it)"

  # ---- Phase 4: namespace + pull secret --------------------------------------
  phase "4/7 ops-agent namespace + image pull secret"
  oc apply -k cluster-setup/overlays/04-namespace
else
  phase "1-4/7 Cluster setup skipped (SKIP_CLUSTER_SETUP=true)"
fi

# ---- Phase 5: build & push custom images -----------------------------------
if [[ "${SKIP_BUILD}" != "true" ]]; then
  phase "5/7 Build & push custom images"
  for svc in orchestrator mcp-servers/rag mcp-servers/governance; do
    name="$(basename "${svc}")"
    podman build -t "${IMAGE_REGISTRY}/ops-agent-${name}:${IMAGE_TAG}" -f "${svc}/Containerfile" "${svc}"
    podman push "${IMAGE_REGISTRY}/ops-agent-${name}:${IMAGE_TAG}"
  done
  ok "Images pushed to ${IMAGE_REGISTRY}"
else
  phase "5/7 Image build skipped (SKIP_BUILD=true)"
fi

# ---- Phase 6: Helm install application chart -------------------------------
phase "6/7 Helm install: MCP servers + orchestrator CronJob"
helm upgrade --install ops-agent helm/ops-agent \
  --namespace "${NAMESPACE}" --create-namespace \
  -f "helm/ops-agent/values-${SCOPE}.yaml" \
  --set image.registry="${IMAGE_REGISTRY}" --set image.tag="${IMAGE_TAG}"

for dep in mcp-openshift-readonly mcp-openshift-executor mcp-atlassian mcp-rag mcp-governance; do
  oc rollout status "deployment/${dep}" -n "${NAMESPACE}" --timeout=300s
done
ok "All MCP server deployments ready"

# ---- Phase 7: end-to-end smoke test ----------------------------------------
phase "7/7 Trigger one Job run and verify it reaches DONE"
JOB_NAME="ops-agent-smoke-$(date -u +%Y%m%d%H%M%S 2>/dev/null || echo manual)"
oc create job "${JOB_NAME}" --from=cronjob/ops-agent-orchestrator -n "${NAMESPACE}"
oc wait --for=condition=complete "job/${JOB_NAME}" -n "${NAMESPACE}" --timeout=600s \
  || fail "Smoke-test job did not complete — check: oc logs job/${JOB_NAME} -n ${NAMESPACE}"
oc logs "job/${JOB_NAME}" -n "${NAMESPACE}" --tail=50
ok "Self-Healing Ops Agent deployed and smoke-tested successfully in namespace ${NAMESPACE}"
