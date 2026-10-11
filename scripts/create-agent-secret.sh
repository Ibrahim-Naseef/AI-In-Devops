#!/usr/bin/env bash
# Streams agent/.env to the cluster as Secret ai-sre/ai-sre-secrets (never committed to git).
set -euo pipefail
cd "$(dirname "$0")/.."
KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519}"
IP="$(terraform -chdir=terraform output -raw "${HOST_OUTPUT:-public_ip}")"
[ -f agent/.env ] || { echo "Create agent/.env first (cp agent/.env.example agent/.env)"; exit 1; }
SSH=(ssh -i "$KEY" -o StrictHostKeyChecking=accept-new "ubuntu@$IP")
"${SSH[@]}" 'kubectl create namespace ai-sre --dry-run=client -o yaml | kubectl apply -f -'
grep -vE '^\s*(#|$)' agent/.env | "${SSH[@]}" 'kubectl -n ai-sre create secret generic ai-sre-secrets --from-env-file=/dev/stdin --dry-run=client -o yaml | kubectl apply -f -'
"${SSH[@]}" 'kubectl -n ai-sre rollout restart deploy/ai-sre-agent 2>/dev/null || echo "(agent not deployed yet - ArgoCD will start it and pick up the secret)"'
echo "Secret applied."
