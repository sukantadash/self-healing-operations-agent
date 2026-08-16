REGISTRY ?=
TAG      ?= latest
NAMESPACE ?= ops-agent
SCOPE    ?= app-scoped

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-22s %s\n", $$1, $$2}'

.PHONY: build-all-images
build-all-images: ## Build all custom container images
	podman build -t $(REGISTRY)/ops-agent-orchestrator:$(TAG) -f orchestrator/Containerfile orchestrator
	podman build -t $(REGISTRY)/ops-agent-rag:$(TAG) -f mcp-servers/rag/Containerfile mcp-servers/rag
	podman build -t $(REGISTRY)/ops-agent-governance:$(TAG) -f mcp-servers/governance/Containerfile mcp-servers/governance

.PHONY: push-all-images
push-all-images: ## Push all custom container images
	podman push $(REGISTRY)/ops-agent-orchestrator:$(TAG)
	podman push $(REGISTRY)/ops-agent-rag:$(TAG)
	podman push $(REGISTRY)/ops-agent-governance:$(TAG)

.PHONY: test
test: ## Run all tests
	cd orchestrator && python -m pytest tests/ -v
	cd mcp-servers/rag && python -m pytest tests/ -v
	cd mcp-servers/governance && python -m pytest tests/ -v

.PHONY: helm-lint
helm-lint: ## Lint Helm chart
	helm lint helm/ops-agent
	helm lint helm/ops-agent -f helm/ops-agent/values-app-scoped.yaml
	helm lint helm/ops-agent -f helm/ops-agent/values-platform-scoped.yaml

.PHONY: helm-template
helm-template: ## Render Helm templates locally
	helm template ops-agent helm/ops-agent --set image.registry=example.com

.PHONY: cluster-setup
cluster-setup: ## Apply cluster prerequisites (RHOAI operator, DSC, Llama Stack)
	oc apply -k cluster-setup/overlays/00-operators
	oc apply -k cluster-setup/overlays/01-rhoai-instances
	oc apply -k cluster-setup/overlays/02-llama-stack
	oc apply -k cluster-setup/overlays/03-guardrails || true
	oc apply -k cluster-setup/overlays/04-namespace

.PHONY: deploy
deploy: ## Run full deployment (cluster-setup + build + helm install)
	IMAGE_REGISTRY=$(REGISTRY) IMAGE_TAG=$(TAG) NAMESPACE=$(NAMESPACE) SCOPE=$(SCOPE) scripts/deploy.sh

.PHONY: helm-uninstall
helm-uninstall: ## Uninstall Helm release
	helm uninstall ops-agent -n $(NAMESPACE)
