"""Read-only Kubernetes helpers. RBAC (gitops/ai-sre/rbac.yaml) enforces read-only; WATCH_NAMESPACES limits scope."""
import json, re
from kubernetes import client, config as kconfig
from . import config

_loaded = False
SECRET_RE = re.compile(r"KEY|TOKEN|SECRET|PASSWORD", re.I)


def _api():
    global _loaded
    if not _loaded:
        try:
            kconfig.load_incluster_config()
        except Exception:
            kconfig.load_kube_config()
        _loaded = True
    return client.CoreV1Api()


def _ns_ok(ns: str):
    if ns not in config.WATCH_NAMESPACES:
        raise ValueError(f"namespace '{ns}' is not allowed; allowed: {config.WATCH_NAMESPACES}")


def _pod_info(p):
    cs = p.status.container_statuses or []
    c = cs[0] if cs else None
    waiting = c.state.waiting.reason if c and c.state and c.state.waiting else None
    last = c.last_state.terminated if c and c.last_state else None
    return {
        "name": p.metadata.name, "phase": p.status.phase, "ready": bool(c and c.ready),
        "restarts": c.restart_count if c else 0, "waiting_reason": waiting,
        "last_terminated_reason": last.reason if last else None,
        "last_exit_code": last.exit_code if last else None,
        "role": (p.metadata.labels or {}).get("role"), "image": c.image if c else None,
    }


def pods_by_role(namespace, role):
    _ns_ok(namespace)
    items = _api().list_namespaced_pod(namespace, label_selector=f"app=demo-app,role={role}").items
    return [_pod_info(p) for p in items]


def get_pods(namespace):
    _ns_ok(namespace)
    return json.dumps([_pod_info(p) for p in _api().list_namespaced_pod(namespace).items])


def describe_pod(namespace, pod):
    _ns_ok(namespace)
    api = _api()
    p = api.read_namespaced_pod(pod, namespace)
    containers = [{
        "name": c.name, "image": c.image,
        "limits": c.resources.limits if c.resources else None,
        "requests": c.resources.requests if c.resources else None,
        "env": {e.name: ("***" if SECRET_RE.search(e.name) else e.value) for e in (c.env or []) if e.value is not None},
    } for c in p.spec.containers]
    evs = api.list_namespaced_event(namespace, field_selector=f"involvedObject.name={pod}").items
    events = [f"{e.type} {e.reason}: {(e.message or '')[:160]}" for e in evs][-8:]
    return json.dumps({"pod": _pod_info(p), "containers": containers, "events": events}, default=str)


def get_pod_logs(namespace, pod, previous=False, tail_lines=40):
    _ns_ok(namespace)
    try:
        return _api().read_namespaced_pod_log(pod, namespace, previous=bool(previous), tail_lines=min(int(tail_lines), 80))
    except client.ApiException as e:
        return f"no logs available: {e.reason}"


def get_events(namespace):
    _ns_ok(namespace)
    evs = _api().list_namespaced_event(namespace).items
    evs.sort(key=lambda e: e.last_timestamp or e.event_time or e.metadata.creation_timestamp)
    return json.dumps([f"{e.type} {e.reason} {e.involved_object.kind}/{e.involved_object.name}: {(e.message or '')[:160]}"
                       for e in evs][-20:])


def get_rollout_status(namespace):
    _ns_ok(namespace)
    try:
        items = client.CustomObjectsApi().list_namespaced_custom_object("argoproj.io", "v1alpha1", namespace, "rollouts")["items"]
    except Exception as e:
        return f"rollouts unavailable: {e}"
    return json.dumps([{"name": r["metadata"]["name"], "phase": r.get("status", {}).get("phase"),
                        "message": r.get("status", {}).get("message"),
                        "step": r.get("status", {}).get("currentStepIndex"),
                        "aborted": r.get("status", {}).get("abort", False)} for r in items])
