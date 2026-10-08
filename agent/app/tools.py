"""Tool definitions the LLM can call. 8 read-only tools + 1 guarded write tool (opens a PR)."""
from . import config, github_ops, guardrails, kube, memory, prom


def _fn(name, desc, props, required):
    return {"type": "function", "function": {"name": name, "description": desc,
            "parameters": {"type": "object", "properties": props, "required": required}}}


NS = {"namespace": {"type": "string", "description": "Kubernetes namespace, e.g. demo"}}
TOOLS = [
    _fn("get_pods", "List pods with phase, restarts, waiting/last-terminated reason (e.g. OOMKilled).", NS, ["namespace"]),
    _fn("describe_pod", "Pod details: resource limits, env, recent events.", {**NS, "pod": {"type": "string"}}, ["namespace", "pod"]),
    _fn("get_pod_logs", "Tail pod logs. Use previous=true for a crashed container.",
        {**NS, "pod": {"type": "string"}, "previous": {"type": "boolean"}, "tail_lines": {"type": "integer"}}, ["namespace", "pod"]),
    _fn("get_events", "Recent events in the namespace.", NS, ["namespace"]),
    _fn("get_rollout_status", "Argo Rollouts phase/message for the namespace.", NS, ["namespace"]),
    _fn("query_promql", "Run an instant PromQL query against Prometheus.", {"query": {"type": "string"}}, ["query"]),
    _fn("read_gitops_values", "Read the current Helm values.yaml of the app from the GitOps repo.", {}, []),
    _fn("search_past_incidents", "Search incident memory for similar past incidents and what fixed them.",
        {"query": {"type": "string"}}, ["query"]),
    _fn("propose_values_change",
        "Open a pull request changing ONE allow-listed value in values.yaml. A human must merge it. "
        "Only call when evidence clearly supports the fix.",
        {"key_path": {"type": "string", "enum": sorted(guardrails.ALLOWED)},
         "new_value": {"type": "string"}, "title": {"type": "string"},
         "explanation": {"type": "string", "description": "Evidence-based reasoning for the PR body"},
         "confidence": {"type": "number", "description": "0..1"}},
        ["key_path", "new_value", "title", "explanation", "confidence"]),
]


def build_dispatch(ctx: dict):
    def read_values():
        text, _ = github_ops.read_file(config.VALUES_PATH)
        return text

    def search(query):
        return str(memory.search_similar(query)) or "none"

    def propose(key_path, new_value, title, explanation, confidence=0.5):
        if config.AGENT_MODE != "propose":
            return "REJECTED: agent is in observe-only mode"
        try:
            value = guardrails.validate(key_path, new_value)
            confidence = float(confidence)
        except (ValueError, TypeError) as e:
            return f"REJECTED by guardrails: {e}"
        if confidence < 0.6:
            return "REJECTED: confidence below 0.6 - gather more evidence first"
        url, existed = github_ops.open_values_pr(key_path, value, title, explanation, confidence)
        ctx["pr_url"], ctx["change"] = url, f"{key_path} -> {value}"
        return f"An open AI-SRE PR already exists: {url}" if existed else f"PR opened: {url}"

    return {
        "get_pods": kube.get_pods, "describe_pod": kube.describe_pod, "get_pod_logs": kube.get_pod_logs,
        "get_events": kube.get_events, "get_rollout_status": kube.get_rollout_status,
        "query_promql": prom.query_compact, "read_gitops_values": read_values,
        "search_past_incidents": search, "propose_values_change": propose,
    }
