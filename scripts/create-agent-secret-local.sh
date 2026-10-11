#!/usr/bin/env bash
# Single-EC2 mode: create the agent Secret directly (run on the box).
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f agent/.env ] || { echo "cp agent/.env.example agent/.env and fill it first"; exit 1; }
kubectl create namespace ai-sre --dry-run=client -o yaml | kubectl apply -f -
grep -vE '^\s*(#|$)' agent/.env | kubectl -n ai-sre create secret generic ai-sre-secrets --from-env-file=/dev/stdin --dry-run=client -o yaml | kubectl apply -f -
kubectl -n ai-sre rollout restart deploy/ai-sre-agent 2>/dev/null || echo "(agent will pick up the secret when ArgoCD starts it)"
