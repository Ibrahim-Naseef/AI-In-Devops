import json, math
import httpx
from . import config


def _query(q: str):
    r = httpx.get(f"{config.PROMETHEUS_URL}/api/v1/query", params={"query": q}, timeout=15)
    r.raise_for_status()
    return r.json()["data"]["result"]


def query_compact(q: str) -> str:
    if len(q) > 600:
        raise ValueError("query too long")
    res = _query(q)[:8]
    return json.dumps([{"metric": {k: v for k, v in x["metric"].items() if k != "__name__"}, "value": x["value"][1]} for x in res])


def scalar(q: str):
    res = _query(q)
    if not res:
        return None
    v = float(res[0]["value"][1])
    return None if math.isnan(v) else v
