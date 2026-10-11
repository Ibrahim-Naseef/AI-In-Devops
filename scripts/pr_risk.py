#!/usr/bin/env python3
"""Deployment risk score for PRs touching gitops/ or terraform/. Heuristics + optional LLM review. Prints markdown."""
import datetime, json, os, subprocess

base = os.environ.get("BASE_REF", "main")
run = lambda *a: subprocess.run(a, capture_output=True, text=True).stdout
diff = run("git", "diff", f"origin/{base}...HEAD", "--", "gitops", "terraform")
files = [f for f in run("git", "diff", "--name-only", f"origin/{base}...HEAD").split() if f]
added = sum(1 for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++"))
removed = sum(1 for l in diff.splitlines() if l.startswith("-") and not l.startswith("---"))

score, why = 0, []
def bump(n, reason):
    global score
    score += n
    why.append(f"+{n} {reason}")

if any(f.startswith("terraform/") for f in files): bump(25, "touches Terraform (infrastructure)")
if "resources:" in diff or "memory:" in diff or "cpu:" in diff: bump(15, "changes resource requests/limits")
if "replicas:" in diff: bump(10, "changes replica count")
if "tag:" in diff: bump(10, "changes image tag")
if "ERROR_RATE" in diff or "MEM_HOG_MB" in diff: bump(20, "touches fault-injection settings")
if added + removed > 100: bump(15, f"large diff ({added}+/{removed}-)")
elif added + removed > 30: bump(8, f"medium diff ({added}+/{removed}-)")
if len(files) > 5: bump(10, f"{len(files)} files changed")
wd = datetime.datetime.utcnow().weekday()
if wd == 4: bump(15, "deploying on a Friday (UTC)")
if wd >= 5: bump(20, "deploying on a weekend (UTC)")
score = min(score, 100)
level = "LOW" if score < 30 else "MEDIUM" if score < 60 else "HIGH"

review = ""
if os.environ.get("LLM_API_KEY") and diff.strip():
    try:
        from openai import OpenAI
        c = OpenAI(base_url=os.environ.get("LLM_BASE_URL") or "https://api.groq.com/openai/v1",
                   api_key=os.environ["LLM_API_KEY"], timeout=45)
        r = c.chat.completions.create(
            model=os.environ.get("LLM_MODEL") or "llama-3.3-70b-versatile", temperature=0,
            messages=[
                {"role": "system", "content": "You are a senior SRE reviewing a GitOps/Terraform diff. Reply with at most 5 short bullet points: concrete risks (security groups, missing limits, blast radius, rollback difficulty) and one-line recommendation. No preamble."},
                {"role": "user", "content": diff[:6000]},
            ])
        review = r.choices[0].message.content.strip()
    except Exception as e:  # never block a PR because the LLM is down/rate-limited
        review = f"_AI review unavailable: {type(e).__name__}_"

print(f"### Deployment risk: **{level}** ({score}/100)")
print("\n".join(f"- {w}" for w in why) or "- no risk factors detected")
if level == "HIGH": print("\n> High risk: require a second reviewer and avoid merging outside business hours.")
if review: print(f"\n#### AI review\n{review}")
print("\n_Heuristic score + LLM review; advisory only._")
