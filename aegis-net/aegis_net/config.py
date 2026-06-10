"""
Keys live in GitHub Secrets + Railway Variables only.
Never read from .env files. Never touch disk.
"""
import os

# Support standard API key OR Claude Code session Bearer token (local dev)
def _get_key():
    k = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if k: return k
    f = os.environ.get("CLAUDE_SESSION_INGRESS_TOKEN_FILE", "")
    if f and os.path.exists(f):
        return open(f).read().strip()
    return ""

ANTHROPIC_KEY   = _get_key()
GROQ_KEY        = os.environ.get("GROQ_API_KEY", "")
GEMINI_KEY      = os.environ.get("GEMINI_API_KEY", "")
YOUTUBE_KEY     = os.environ.get("YOUTUBE_API_KEY", "")

MODEL_SUPERVISOR    = os.environ.get("MODEL_SUPERVISOR",   "claude-opus-4-6")
MODEL_TEAM_LEAD     = os.environ.get("MODEL_TEAM_LEAD",    "claude-sonnet-4-6")
MODEL_WORKER_API    = os.environ.get("MODEL_WORKER_API",   "claude-haiku-4-5-20251001")
MODEL_WORKER_GROQ   = os.environ.get("MODEL_WORKER_GROQ",  "llama-3.3-70b-versatile")
MODEL_WORKER_GEMINI = os.environ.get("MODEL_WORKER_GEMINI","gemini-2.5-flash-lite")
MODEL_WORKER_LOCAL  = os.environ.get("MODEL_WORKER_LOCAL", "qwen2.5:7b")

TRUST_ELITE     = 85.0
TRUST_TRUSTED   = 65.0
TRUST_OPERATIVE = 40.0
TRUST_RESET     = 20.0

