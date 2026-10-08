#!/usr/bin/env bash
# Fault injection through Git (so the whole GitOps loop is exercised).
set -euo pipefail
cd "$(dirname "$0")/.."
F=gitops/charts/demo-app/values.yaml
git pull --rebase origin main
set_env() { sed -i.bak -E "s/^(  $1: ).*/\1\"$2\"/" "$F"; rm -f "$F.bak"; }
case "${1:-}" in
  bad-release) set_env ERROR_RATE 0.5 ;;
  oom)         set_env MEM_HOG_MB 150 ;;
  reset)       set_env ERROR_RATE 0; set_env MEM_HOG_MB 0 ;;
  *) echo "usage: $0 bad-release|oom|reset"; exit 1 ;;
esac
git add "$F"
git commit -m "demo: $1"
git push origin HEAD:main
echo "Pushed. Watch ArgoCD / Rollouts / agent: http://localhost:8800/incidents"
