import logging, threading
from . import config, kube, llm, memory, notify
from .tools import TOOLS, build_dispatch

log = logging.getLogger("investigator")
_one_at_a_time = threading.Lock()  # protects free-tier rate limits

SYSTEM = """You are an SRE agent for a Kubernetes cluster managed with GitOps (ArgoCD) and Argo Rollouts.
You CANNOT change the cluster. The only way to fix anything is propose_values_change, which opens a pull request that a human must review.
Method: 1) get_pods, 2) describe_pod / get_pod_logs (previous=true for crashed pods) / get_events, 3) optionally query_promql,
4) read_gitops_values, 5) only if evidence is clear, propose ONE fix. Keep tool calls minimal (max %d).
Typical causes: OOMKilled -> raise memory limit (e.g. 96Mi -> 256Mi); injected errors -> set env.ERROR_RATE to "0".
Do not guess. If the cause is unclear, say so and do not open a PR.
Finish with ONLY this JSON:
{"root_cause": "...", "evidence": ["..."], "severity": "low|medium|high", "confidence": 0.0, "action": "pr_opened|none", "summary": "one or two sentences"}"""


def summarize_alerts(payload: dict) -> str:
    lines = []
    for a in payload.get("alerts", [])[:15]:
        l, an = a.get("labels", {}), a.get("annotations", {})
        lines.append(f"- {l.get('alertname')} severity={l.get('severity')} ns={l.get('namespace')} "
                     f"pod={l.get('pod', '-')} {an.get('summary') or an.get('description', '')}")
    return "\n".join(lines)


def _basic(namespace):
    """No-LLM fallback: collect facts so a human gets something useful."""
    try:
        pods = kube.get_pods(namespace)
        events = kube.get_events(namespace)
    except Exception as e:
        pods, events = f"error: {e}", ""
    return {"root_cause": "LLM not configured - raw facts only", "evidence": [pods[:600], events[:600]],
            "severity": "unknown", "confidence": 0.0, "action": "none",
            "summary": "Set LLM_API_KEY to enable AI diagnosis."}


def investigate(incident_id: int, alert_text: str, namespace: str) -> dict:
    with _one_at_a_time:
        ctx, trace = {}, []
        similar = memory.search_similar(alert_text)
        past = "\n".join(f"- ({s['similarity']}) {s['alertname']}: {s['root_cause']} PR={s['pr_url']}" for s in similar) or "none"
        result = None
        if llm.enabled():
            try:
                out, trace = llm.run_tool_loop(SYSTEM % config.MAX_STEPS,
                    f"Namespace: {namespace}\nAlerts:\n{alert_text}\n\nSimilar past incidents from memory:\n{past}\n\nInvestigate now.",
                    TOOLS, build_dispatch(ctx), config.MAX_STEPS)
                result = llm.extract_json(out) or {"root_cause": "unparsed", "summary": (out or "")[:500],
                                                   "evidence": [], "severity": "unknown", "confidence": 0.0, "action": "none"}
            except Exception as e:
                log.exception("agent loop failed")
                result = {"root_cause": f"agent error: {e}", "summary": "Investigation failed; see logs.",
                          "evidence": [], "severity": "unknown", "confidence": 0.0, "action": "none"}
        else:
            result = _basic(namespace)

        pr_url = ctx.get("pr_url")
        memory.finish(incident_id, result.get("root_cause"), result.get("summary"), pr_url, result.get("confidence"), trace)
        ev = "\n".join(f"  • {e}" for e in (result.get("evidence") or [])[:5])
        notify.send(
            f":rotating_light: *AI-SRE incident #{incident_id}* in `{namespace}` (severity {result.get('severity')})\n"
            f"*Root cause:* {result.get('root_cause')}\n*Evidence:*\n{ev}\n"
            f"*Confidence:* {result.get('confidence')}   *Similar past incidents:* {len(similar)}\n"
            + (f"*Proposed fix (needs human review):* {pr_url}" if pr_url else "*No PR opened.*"))
        result["pr_url"] = pr_url
        return result
