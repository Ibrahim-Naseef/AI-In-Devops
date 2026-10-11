#!/usr/bin/env bash
# Verify-before-merge: deploy the PR's chart into a throw-away namespace, load it, print a markdown report.
# Runs on the EC2 self-hosted runner (which has kubectl access to the kind cluster).
set -uo pipefail
PR="${1:?pr number}"
NS="preview-pr-$PR"
CHART="gitops/charts/demo-app"
FAIL=0
trap 'kubectl delete ns "$NS" --wait=false >/dev/null 2>&1' EXIT

kubectl delete ns "$NS" --ignore-not-found >/dev/null 2>&1
kubectl create ns "$NS" >/dev/null

helm upgrade --install demo-app "$CHART" -n "$NS" \
  --set service.type=ClusterIP --set monitoring.enabled=false \
  --set loadgen.enabled=false --set analysis.enabled=false >&2 || FAIL=1

PHASE="unknown"
for _ in $(seq 1 30); do
  PHASE="$(kubectl -n "$NS" get rollout demo-app -o jsonpath='{.status.phase}' 2>/dev/null || true)"
  [ "$PHASE" = "Healthy" ] && break
  sleep 5
done
[ "$PHASE" = "Healthy" ] || FAIL=1

RESTARTS="$(kubectl -n "$NS" get pods -o jsonpath='{range .items[*]}{.status.containerStatuses[0].restartCount}{"\n"}{end}' 2>/dev/null | awk '{s+=$1} END{print s+0}')"
REASON="$(kubectl -n "$NS" get pods -o jsonpath='{range .items[*]}{.status.containerStatuses[0].lastState.terminated.reason}{" "}{.status.containerStatuses[0].state.waiting.reason}{"\n"}{end}' 2>/dev/null | tr -s ' \n' ' ')"
[ "$RESTARTS" = "0" ] || FAIL=1

LOAD="skipped (rollout not healthy)"
if [ "$PHASE" = "Healthy" ]; then
  LOAD="$(kubectl -n "$NS" run loadtest --rm -i --restart=Never --image=curlimages/curl:8.10.1 -- \
    sh -c 'ok=0;bad=0;i=0;while [ $i -lt 200 ]; do c=$(curl -s -o /dev/null -w "%{http_code}" http://demo-app:8080/work); if [ "$c" = 200 ]; then ok=$((ok+1)); else bad=$((bad+1)); fi; i=$((i+1)); done; echo "ok=$ok bad=$bad"' 2>/dev/null | grep -E 'ok=[0-9]+ bad=[0-9]+' | tail -1)"
  BAD="$(echo "$LOAD" | sed -E 's/.*bad=([0-9]+).*/\1/')"
  [ "${BAD:-999}" -le 4 ] || FAIL=1   # <=2% errors tolerated
fi

VERDICT="PASS"; [ "$FAIL" = "0" ] || VERDICT="FAIL"
cat <<EOF
### Preview verification: **$VERDICT**
Deployed this PR's chart into namespace \`$NS\` on the kind cluster and load-tested it.

| Check | Result |
|---|---|
| Rollout phase | \`$PHASE\` |
| Container restarts | $RESTARTS |
| Last termination / waiting reason | ${REASON:-none} |
| 200 requests to /work | ${LOAD:-no output} |

_Posted automatically by the pr-verify workflow._
EOF
exit "$FAIL"
