"""AI canary analysis, called by an Argo Rollouts AnalysisTemplate (web provider).
Rules compute hard facts; the LLM can only make the verdict STRICTER (veto), never override a rule failure."""
import json, logging, time
from collections import deque
from . import kube, llm, prom

log = logging.getLogger("canary")
HISTORY = deque(maxlen=30)

JUDGE = """You judge a canary release of a web service. You get canary-vs-stable metrics and canary logs.
Missing data is NOT a failure. Fail ONLY if there is a clear regression (errors, latency, crashes, error logs).
Reply ONLY JSON: {"verdict": "pass|fail", "reason": "one sentence"}"""


def _queries(role, ns):
    sel = f'namespace="{ns}",role="{role}"'
    return {
        "req_rate": f"sum(rate(http_requests_total{{{sel}}}[2m]))",
        "err_rate": f'sum(rate(http_requests_total{{{sel},status=~"5.."}}[2m])) / sum(rate(http_requests_total{{{sel}}}[2m]))',
        "p95_s": f"histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket{{{sel}}}[2m])))",
    }


def decide(canary: dict, stable: dict, restarts: int):
    """Pure rule engine (unit-testable)."""
    reasons = []
    if restarts > 0:
        reasons.append(f"canary pods restarted {restarts}x")
    ce, se = canary.get("err_rate"), stable.get("err_rate") or 0
    if ce is not None and ce - se > 0.05:
        reasons.append(f"canary error rate {ce:.1%} vs stable {se:.1%}")
    cp, sp = canary.get("p95_s"), stable.get("p95_s")
    if cp is not None and sp is not None and cp > max(1.5 * sp, sp + 0.2):
        reasons.append(f"canary p95 {cp:.3f}s vs stable {sp:.3f}s")
    return ("fail" if reasons else "pass"), reasons


def analyze(namespace: str, app: str = "demo-app") -> dict:
    pods = kube.pods_by_role(namespace, "canary")
    if not pods:
        res = {"verdict": "pass", "reason": "no canary pods present", "metrics": {}, "ai": None}
    else:
        m = {r: {k: prom.scalar(q) for k, q in _queries(r, namespace).items()} for r in ("canary", "stable")}
        restarts = sum(p["restarts"] for p in pods)
        verdict, reasons = decide(m["canary"], m["stable"], restarts)
        ai = None
        if llm.enabled():
            try:
                logs = kube.get_pod_logs(namespace, pods[0]["name"], False, 15)
                ai = llm.chat_json(JUDGE, json.dumps({"metrics": m, "canary_restarts": restarts, "canary_log_tail": logs[-1500:]}))
                if ai and ai.get("verdict") == "fail" and verdict == "pass":
                    verdict = "fail"
                    reasons.append("AI veto: " + str(ai.get("reason", ""))[:200])
            except Exception as e:
                log.warning("LLM judge unavailable, using rules only: %s", e)
        res = {"verdict": verdict, "reason": "; ".join(reasons) or "metrics within thresholds",
               "metrics": m, "canary_restarts": restarts, "ai": ai}
    HISTORY.appendleft({"ts": time.strftime("%H:%M:%S"), "namespace": namespace, **{k: res[k] for k in ("verdict", "reason")}})
    return res
