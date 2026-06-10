import os
from dotenv import load_dotenv
_HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_HERE, "..", ".env"))

def _get_key():
    k = os.getenv("ANTHROPIC_API_KEY", "")
    if k: return k
    f = os.getenv("CLAUDE_SESSION_INGRESS_TOKEN_FILE", "")
    if f and os.path.exists(f):
        return open(f).read().strip()
    return ""

ANTHROPIC_KEY = _get_key()
GROQ_KEY      = os.getenv("GROQ_API_KEY", "")
GEMINI_KEY    = os.getenv("GEMINI_API_KEY", "")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

MODEL_SUPERVISOR    = os.getenv("MODEL_SUPERVISOR",  "claude-opus-4-6")
MODEL_TEAM_LEAD     = os.getenv("MODEL_TEAM_LEAD",   "claude-sonnet-4-6")
MODEL_WORKER_API    = os.getenv("MODEL_WORKER_API",  "claude-haiku-4-5-20251001")
MODEL_WORKER_GROQ   = os.getenv("MODEL_WORKER_GROQ", "llama-3.3-70b-versatile")
MODEL_WORKER_GEMINI = os.getenv("MODEL_WORKER_GEMINI","gemini-2.5-flash-lite")
MODEL_WORKER_LOCAL  = os.getenv("MODEL_WORKER_LOCAL", "qwen2.5:7b")

TRUST_ELITE     = 85.0
TRUST_TRUSTED   = 65.0
TRUST_OPERATIVE = 40.0
TRUST_RESET     = 20.0
