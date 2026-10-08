"""The ONLY things the agent may change, with hard bounds. Everything else is rejected before any PR is opened."""
import re


def _mem_mi(v: str) -> float:
    m = re.fullmatch(r"(\d+)(Mi|Gi)", v)
    if not m:
        raise ValueError("memory must look like 256Mi or 1Gi")
    return int(m[1]) * (1024 if m[2] == "Gi" else 1)


def _memory(v):
    mi = _mem_mi(str(v))
    if not 32 <= mi <= 1024:
        raise ValueError("memory must be between 32Mi and 1024Mi")
    return str(v)


def _cpu(v):
    v = str(v)
    m = re.fullmatch(r"(\d+)m", v)
    millis = int(m[1]) if m else (int(v) * 1000 if v.isdigit() else None)
    if millis is None or not 10 <= millis <= 1000:
        raise ValueError("cpu must be between 10m and 1000m")
    return v


def _replicas(v):
    n = int(v)
    if not 1 <= n <= 6:
        raise ValueError("replicas must be 1..6")
    return n


def _error_rate(v):
    f = float(v)
    if not 0 <= f <= 1:
        raise ValueError("ERROR_RATE must be 0..1")
    return str(v)


def _tag(v):
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", str(v)):
        raise ValueError("invalid image tag")
    return str(v)


ALLOWED = {
    "resources.limits.memory": _memory,
    "resources.requests.memory": _memory,
    "resources.limits.cpu": _cpu,
    "replicas": _replicas,
    "env.ERROR_RATE": _error_rate,
    "image.tag": _tag,
}


def validate(key_path: str, value):
    if key_path not in ALLOWED:
        raise ValueError(f"'{key_path}' is not an allowed key; allowed: {sorted(ALLOWED)}")
    return ALLOWED[key_path](value)
