from __future__ import annotations
import httpx
from . import config as cfg

_client = None

def _get_anthropic():
    global _client
    if _client is None:
        import anthropic
        key = cfg.ANTHROPIC_KEY
        if not key:
            raise RuntimeError("No Anthropic key. Set ANTHROPIC_API_KEY in .env")
        if key.startswith("sk-ant") and len(key) > 200:
            _client = anthropic.Anthropic(auth_token=key)
        else:
            _client = anthropic.Anthropic(api_key=key)
    return _client

def chat(messages, *, model=None, system="", max_tokens=1024, backend="anthropic") -> str:
    if backend == "groq":
        return _groq(messages, model=model or cfg.MODEL_WORKER_GROQ, system=system, max_tokens=max_tokens)
    if backend == "gemini":
        return _gemini(messages, model=model or cfg.MODEL_WORKER_GEMINI, system=system, max_tokens=max_tokens)
    m = model or cfg.MODEL_WORKER_API
    resp = _get_anthropic().messages.create(
        model=m, max_tokens=max_tokens, system=system,
        messages=[{"role": r["role"], "content": r["content"]} for r in messages],
    )
    return resp.content[0].text

def _groq(messages, *, model, system, max_tokens):
    if not cfg.GROQ_KEY: raise RuntimeError("GROQ_API_KEY not set")
    msgs = ([{"role":"system","content":system}] if system else []) + messages
    r = httpx.post("https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization":f"Bearer {cfg.GROQ_KEY}","Content-Type":"application/json"},
        json={"model":model,"messages":msgs,"max_tokens":max_tokens}, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def _gemini(messages, *, model, system, max_tokens):
    if not cfg.GEMINI_KEY: raise RuntimeError("GEMINI_API_KEY not set")
    contents = []
    if system:
        contents += [{"role":"user","parts":[{"text":f"[System]: {system}"}]},
                     {"role":"model","parts":[{"text":"Understood."}]}]
    for m in messages:
        contents.append({"role":"user" if m["role"]=="user" else "model","parts":[{"text":m["content"]}]})
    r = httpx.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        params={"key":cfg.GEMINI_KEY},
        json={"contents":contents,"generationConfig":{"maxOutputTokens":max_tokens}}, timeout=60)
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]

def detect_available_backends():
    available = []
    if cfg.GROQ_KEY: available.append("groq")
    if cfg.GEMINI_KEY: available.append("gemini")
    available.append("anthropic")
    return available

def best_backend_for_tier(trust_score):
    available = detect_available_backends()
    if trust_score >= cfg.TRUST_ELITE:
        return "anthropic", cfg.MODEL_TEAM_LEAD
    if trust_score >= cfg.TRUST_TRUSTED:
        if "groq" in available: return "groq", cfg.MODEL_WORKER_GROQ
        if "gemini" in available: return "gemini", cfg.MODEL_WORKER_GEMINI
        return "anthropic", cfg.MODEL_WORKER_API
    if "groq" in available: return "groq", cfg.MODEL_WORKER_GROQ
    if "gemini" in available: return "gemini", cfg.MODEL_WORKER_GEMINI
    return "anthropic", cfg.MODEL_WORKER_API
