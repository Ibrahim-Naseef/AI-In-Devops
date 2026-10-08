import logging, os, random, time
from flask import Flask, Response, g, jsonify, request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

VERSION = os.getenv("APP_VERSION", "dev")
ERROR_RATE = float(os.getenv("ERROR_RATE", "0"))   # fault injection: fraction of requests that 500
LATENCY_MS = int(os.getenv("LATENCY_MS", "20"))
MEM_HOG_MB = int(os.getenv("MEM_HOG_MB", "0"))     # fault injection: allocate memory at startup (OOM demo)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("demo-app")

_hog = [bytearray(b"x" * 1024 * 1024) for _ in range(MEM_HOG_MB)]
if MEM_HOG_MB:
    log.warning("allocated %s MB at startup", MEM_HOG_MB)

app = Flask(__name__)
REQS = Counter("http_requests_total", "HTTP requests", ["method", "path", "status"])
LAT = Histogram("http_request_duration_seconds", "Request latency", ["path"],
                buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5))


@app.before_request
def _start():
    g.t0 = time.perf_counter()


@app.after_request
def _record(resp):
    if request.path not in ("/metrics", "/healthz"):
        REQS.labels(request.method, request.path, str(resp.status_code)).inc()
        LAT.labels(request.path).observe(time.perf_counter() - g.t0)
    return resp


def _maybe_fail():
    if random.random() < ERROR_RATE:
        log.error("injected failure (ERROR_RATE=%s) version=%s", ERROR_RATE, VERSION)
        return jsonify(error="injected failure", version=VERSION), 500
    return None


@app.get("/")
def index():
    return _maybe_fail() or jsonify(service="demo-app", version=VERSION)


@app.get("/work")
def work():
    time.sleep(max(0, random.gauss(LATENCY_MS, LATENCY_MS / 4)) / 1000)
    return _maybe_fail() or jsonify(ok=True, version=VERSION)


@app.get("/healthz")
def healthz():
    return "ok"


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)
