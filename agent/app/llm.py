"""Provider-agnostic LLM access (any OpenAI-compatible API) + a small tool-calling loop."""
import json, logging, time
from openai import OpenAI
from . import config

log = logging.getLogger("llm")
_client = None


def enabled() -> bool:
    return bool(config.LLM_API_KEY)


def client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY,
                         timeout=config.LLM_TIMEOUT, max_retries=1)
    return _client


def _create(**kw):
    for attempt in range(3):
        try:
            return client().chat.completions.create(model=config.LLM_MODEL, **kw)
        except Exception as e:  # rate limits on free tiers are common
            log.warning("LLM call failed (attempt %s/3): %s", attempt + 1, e)
            if attempt == 2:
                raise
            time.sleep(15)


def extract_json(text: str):
    if not text:
        return None
    s, e = text.find("{"), text.rfind("}")
    if s == -1 or e <= s:
        return None
    try:
        return json.loads(text[s:e + 1])
    except json.JSONDecodeError:
        return None


def chat_json(system: str, user: str):
    r = _create(messages=[{"role": "system", "content": system}, {"role": "user", "content": user}], temperature=0)
    return extract_json(r.choices[0].message.content)


def run_tool_loop(system, user, tools, dispatch, max_steps):
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    trace = []
    for _ in range(max_steps):
        r = _create(messages=messages, tools=tools, tool_choice="auto", temperature=0)
        msg = r.choices[0].message
        assistant = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            assistant["tool_calls"] = [
                {"id": t.id, "type": "function", "function": {"name": t.function.name, "arguments": t.function.arguments}}
                for t in msg.tool_calls]
        messages.append(assistant)
        if not msg.tool_calls:
            return msg.content, trace
        for t in msg.tool_calls:
            args = {}
            try:
                args = json.loads(t.function.arguments or "{}")
                out = dispatch[t.function.name](**args)
            except Exception as e:
                out = f"ERROR: {type(e).__name__}: {e}"
            out = str(out)[:3500]  # keep prompts small (free-tier token limits)
            trace.append({"tool": t.function.name, "args": args, "result_preview": out[:300]})
            messages.append({"role": "tool", "tool_call_id": t.id, "content": out})
    messages.append({"role": "user", "content": "Tool budget exhausted. Output the final JSON now."})
    r = _create(messages=messages, temperature=0)
    return r.choices[0].message.content, trace
