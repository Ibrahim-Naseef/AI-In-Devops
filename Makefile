.RECIPEPREFIX := >
SHELL    := /bin/bash
SSH_KEY  ?= $(HOME)/.ssh/id_ed25519
HOST_OUTPUT ?= public_ip
export HOST_OUTPUT
TF       := terraform -chdir=terraform
IP        = $(shell $(TF) output -raw $(HOST_OUTPUT) 2>/dev/null)
SSH       = ssh -i $(SSH_KEY) -o StrictHostKeyChecking=accept-new ubuntu@$(IP)

.DEFAULT_GOAL := help
.PHONY: help init up wait runner secrets tunnel argocd-pass status test-alert break-bad-release break-oom reset-faults down

help: ## Show this help
> @grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-20s %s\n", $$1, $$2}'

init: ## Replace placeholders: make init GH_USER=you DH_USER=you [GH_REPO=ai-sre-gitops]
> GH_USER=$(GH_USER) DH_USER=$(DH_USER) GH_REPO=$(GH_REPO) ./scripts/init-repo.sh

up: ## terraform init + apply (EC2 + kind + ArgoCD)
> $(TF) init
> $(TF) apply

wait: ## Wait until the EC2 bootstrap finished
> until $(SSH) 'test -f /var/lib/ai-sre-bootstrap.done' 2>/dev/null; do echo "bootstrapping (this takes ~5-8 min)..."; sleep 20; done; echo "bootstrap done"

runner: ## Register the EC2 box as a GitHub self-hosted runner
> SSH_KEY=$(SSH_KEY) ./scripts/register-runner.sh

secrets: ## Push agent/.env into the cluster as a Secret and restart the agent
> SSH_KEY=$(SSH_KEY) ./scripts/create-agent-secret.sh

tunnel: ## Open SSH tunnel: ArgoCD:8080 Grafana:3000 Prometheus:9090 app:8081 agent:8800
> @echo "ArgoCD http://localhost:8080 | Grafana http://localhost:3000 (admin/admin) | Prometheus http://localhost:9090 | App http://localhost:8081 | Agent http://localhost:8800/incidents"
> ssh -N -i $(SSH_KEY) -o StrictHostKeyChecking=accept-new -L 8080:127.0.0.1:30080 -L 3000:127.0.0.1:30030 -L 9090:127.0.0.1:30090 -L 8081:127.0.0.1:30081 -L 8800:127.0.0.1:30800 ubuntu@$(IP)

argocd-pass: ## Print the ArgoCD admin password
> @$(SSH) "kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d; echo"

status: ## ArgoCD apps + non-running pods
> $(SSH) 'kubectl get applications -n argocd; echo; kubectl get pods -A | grep -v -E "Running|Completed" || true'

test-alert: ## Send a fake Alertmanager payload to the agent (needs `make tunnel`)
> curl -s -X POST http://localhost:8800/alert -H 'content-type: application/json' -d @scripts/test-alert.json; echo

break-bad-release: ## Demo 1: push a release with 50% errors -> AI canary analysis aborts it
> ./scripts/break.sh bad-release

break-oom: ## Demo 2: push a config that OOMs pods -> alert -> agent opens a fix PR
> ./scripts/break.sh oom

reset-faults: ## Turn fault injection off again
> ./scripts/break.sh reset

down: ## terraform destroy (stop paying!)
> $(TF) destroy
