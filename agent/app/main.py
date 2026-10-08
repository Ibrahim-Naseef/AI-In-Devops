import logging, time
from fastapi import BackgroundTasks, FastAPI, Request
from . import canary, config, investigator, llm, memory

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
app = FastAPI(title="AI-SRE agent")
STARTED = time.time()


@app.get("/healthz")
def healthz():
    return {"ok": True, "llm": llm.enabled(), "mode": config.AGENT_MODE, "model": config.LLM_MODEL}


@app.post("/alert")
async def alert(request: Request, bg: BackgroundTasks):
    """Alertmanager webhook receiver."""
    payload = await request.json()
    key = payload.get("groupKey", "unknown")
    if payload.get("status") == "resolved":
        return {"resolved": memory.resolve(key)}
    if memory.open_recent(key):
        return {"skipped": "incident already open for this alert group"}
    labels = payload.get("commonLabels", {}) or (payload.get("alerts") or [{}])[0].get("labels", {})
    ns = labels.get("namespace", "demo")
    text = investigator.summarize_alerts(payload)
    iid = memory.create(key, labels.get("alertname", "unknown"), ns, text)
    bg.add_task(investigator.investigate, iid, text, ns)
    return {"accepted": True, "incident_id": iid}


@app.post("/investigate")
async def investigate_now(request: Request):
    """Manual trigger: {"namespace": "demo", "description": "pods keep restarting"}"""
    body = await request.json()
    ns, desc = body.get("namespace", "demo"), body.get("description", "manual investigation")
    iid = memory.create(f"manual-{time.time()}", "Manual", ns, desc)
    return investigator.investigate(iid, desc, ns)


@app.get("/incidents")
def incidents(limit: int = 20):
    return memory.list_incidents(limit)


@app.get("/canary/analyze")
def canary_analyze(namespace: str = "demo", app: str = "demo-app"):
    return canary.analyze(namespace, app)


@app.get("/canary/history")
def canary_history():
    return list(canary.HISTORY)
