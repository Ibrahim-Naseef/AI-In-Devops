"""Writes happen ONLY here, and only as pull requests (never direct pushes to main)."""
import base64, io, time
import httpx
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import DoubleQuotedScalarString
from . import config


def configured() -> bool:
    return bool(config.GITHUB_TOKEN and config.GITHUB_REPO)


def _c():
    return httpx.Client(base_url="https://api.github.com", timeout=20, headers={
        "Authorization": f"Bearer {config.GITHUB_TOKEN}", "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"})


def read_file(path, ref=None):
    with _c() as c:
        r = c.get(f"/repos/{config.GITHUB_REPO}/contents/{path}", params={"ref": ref or config.GITHUB_BASE_BRANCH})
        r.raise_for_status()
        j = r.json()
        return base64.b64decode(j["content"]).decode(), j["sha"]


def existing_ai_pr():
    with _c() as c:
        r = c.get(f"/repos/{config.GITHUB_REPO}/pulls", params={"state": "open", "per_page": 50})
        r.raise_for_status()
        for pr in r.json():
            if pr["head"]["ref"].startswith("ai-sre/"):
                return pr["html_url"]
    return None


def set_key(text: str, key_path: str, value):
    y = YAML()
    y.preserve_quotes = True
    data = y.load(text)
    cur, parts = data, key_path.split(".")
    for p in parts[:-1]:
        cur = cur[p]
    old = cur[parts[-1]]
    cur[parts[-1]] = DoubleQuotedScalarString(value) if isinstance(value, str) else value
    buf = io.StringIO()
    y.dump(data, buf)
    return buf.getvalue(), old


def open_values_pr(key_path, value, title, explanation, confidence):
    """Returns (pr_url, already_existed). One open AI PR at a time to avoid PR spam."""
    if not configured():
        raise RuntimeError("GITHUB_TOKEN / GITHUB_REPO not configured")
    existing = existing_ai_pr()
    if existing:
        return existing, True
    repo = config.GITHUB_REPO
    text, file_sha = read_file(config.VALUES_PATH)
    new_text, old = set_key(text, key_path, value)
    branch = f"ai-sre/fix-{int(time.time())}"
    with _c() as c:
        base = c.get(f"/repos/{repo}/git/ref/heads/{config.GITHUB_BASE_BRANCH}")
        base.raise_for_status()
        c.post(f"/repos/{repo}/git/refs", json={"ref": f"refs/heads/{branch}", "sha": base.json()["object"]["sha"]}).raise_for_status()
        c.put(f"/repos/{repo}/contents/{config.VALUES_PATH}", json={
            "message": f"[AI-SRE] {title}", "branch": branch, "sha": file_sha,
            "content": base64.b64encode(new_text.encode()).decode()}).raise_for_status()
        body = (f"## Automated proposal by AI-SRE agent\n\n**Change:** `{key_path}`: `{old}` -> `{value}`\n"
                f"**Confidence:** {confidence}\n\n### Why\n{explanation}\n\n"
                "### Safety\n- Opened by a read-only agent; only allow-listed keys with bounded values can change.\n"
                "- The `pr-verify` workflow deploys a preview of this PR and reports back below.\n"
                "- **A human must review and merge.** ArgoCD applies it after merge.\n")
        pr = c.post(f"/repos/{repo}/pulls", json={"title": f"[AI-SRE] {title}", "head": branch,
                                                  "base": config.GITHUB_BASE_BRANCH, "body": body})
        pr.raise_for_status()
        return pr.json()["html_url"], False
