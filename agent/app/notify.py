import logging
import httpx
from . import config

log = logging.getLogger("notify")


def send(text: str):
    log.info("NOTIFY: %s", text)
    if not config.SLACK_WEBHOOK_URL:
        return
    try:
        httpx.post(config.SLACK_WEBHOOK_URL, json={"text": text}, timeout=10)
    except Exception as e:
        log.warning("slack failed: %s", e)
