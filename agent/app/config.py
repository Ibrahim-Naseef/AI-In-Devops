import os

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "40"))

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://kube-prometheus-stack-prometheus.monitoring.svc.cluster.local:9090")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "")
GITHUB_BASE_BRANCH = os.getenv("GITHUB_BASE_BRANCH", "main")
VALUES_PATH = os.getenv("VALUES_PATH", "gitops/charts/demo-app/values.yaml")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")

AGENT_MODE = os.getenv("AGENT_MODE", "propose")  # propose | observe
MAX_STEPS = int(os.getenv("MAX_STEPS", "6"))
WATCH_NAMESPACES = [n for n in os.getenv("WATCH_NAMESPACES", "demo").split(",") if n]
DB_PATH = os.getenv("DB_PATH", "/data/incidents.db")
