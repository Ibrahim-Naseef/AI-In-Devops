"""Incident memory: SQLite + TF-IDF cosine similarity (zero extra infra, fully free).
Upgrade path: swap search_similar() for embeddings + pgvector/Qdrant."""
import json, math, os, re, sqlite3, threading, time
from collections import Counter
from . import config

_lock = threading.Lock()
_conn = None


def _db():
    global _conn
    if _conn is None:
        os.makedirs(os.path.dirname(config.DB_PATH) or ".", exist_ok=True)
        _conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("""CREATE TABLE IF NOT EXISTS incidents(
            id INTEGER PRIMARY KEY AUTOINCREMENT, fingerprint TEXT, alertname TEXT, namespace TEXT,
            created REAL, resolved REAL, alert_text TEXT, root_cause TEXT, summary TEXT,
            pr_url TEXT, confidence REAL, trace TEXT)""")
        _conn.commit()
    return _conn


def open_recent(fingerprint, minutes=30) -> bool:
    with _lock:
        r = _db().execute("SELECT 1 FROM incidents WHERE fingerprint=? AND resolved IS NULL AND created>?",
                          (fingerprint, time.time() - minutes * 60)).fetchone()
        return r is not None


def create(fingerprint, alertname, namespace, alert_text) -> int:
    with _lock:
        cur = _db().execute("INSERT INTO incidents(fingerprint,alertname,namespace,created,alert_text) VALUES(?,?,?,?,?)",
                            (fingerprint, alertname, namespace, time.time(), alert_text))
        _db().commit()
        return cur.lastrowid


def finish(incident_id, root_cause, summary, pr_url, confidence, trace):
    with _lock:
        _db().execute("UPDATE incidents SET root_cause=?,summary=?,pr_url=?,confidence=?,trace=? WHERE id=?",
                      (root_cause, summary, pr_url, confidence, json.dumps(trace), incident_id))
        _db().commit()


def resolve(fingerprint) -> int:
    with _lock:
        cur = _db().execute("UPDATE incidents SET resolved=? WHERE fingerprint=? AND resolved IS NULL", (time.time(), fingerprint))
        _db().commit()
        return cur.rowcount


def list_incidents(limit=20):
    with _lock:
        rows = _db().execute("SELECT * FROM incidents ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["trace"] = json.loads(d["trace"]) if d.get("trace") else []
        d["mttr_seconds"] = round(d["resolved"] - d["created"]) if d.get("resolved") else None
        out.append(d)
    return out


def _tok(s):
    return [w for w in re.findall(r"[a-z0-9_]+", (s or "").lower()) if len(w) > 2]


def search_similar(text, k=3):
    with _lock:
        rows = _db().execute("SELECT * FROM incidents WHERE root_cause IS NOT NULL").fetchall()
    if not rows:
        return []
    docs = [_tok(f"{r['alertname']} {r['alert_text']} {r['root_cause']}") for r in rows]
    q = _tok(text)
    n = len(docs) + 1
    df = Counter(w for d in docs for w in set(d))
    idf = lambda w: math.log((n + 1) / (df.get(w, 0) + 1)) + 1

    def vec(tokens):
        c = Counter(tokens)
        return {w: f * idf(w) for w, f in c.items()}

    def cos(a, b):
        dot = sum(a[w] * b.get(w, 0) for w in a)
        na, nb = math.sqrt(sum(v * v for v in a.values())), math.sqrt(sum(v * v for v in b.values()))
        return dot / (na * nb) if na and nb else 0.0

    qv = vec(q)
    scored = sorted(((cos(qv, vec(d)), r) for d, r in zip(docs, rows)), key=lambda x: -x[0])
    return [{"similarity": round(s, 2), "alertname": r["alertname"], "root_cause": r["root_cause"], "pr_url": r["pr_url"]}
            for s, r in scored[:k] if s > 0.1]
