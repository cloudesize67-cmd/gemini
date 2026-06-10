"""
AEGIS.NET / NOESIS — Secrets Manager
======================================
Keys live in exactly two places:
  1. GitHub Secrets  (github.com/cloudesize67-cmd/gemini/settings/secrets/actions)
  2. Railway Variables (railway.app → project → Variables tab)

They are injected as environment variables at runtime.
This file reads them. It never reads a .env file. It never touches disk.

If a required key is missing, it raises a clear error telling you exactly
where to add it — not a cryptic AttributeError three layers deep.
"""
from __future__ import annotations
import os


class MissingSecretError(RuntimeError):
    pass


def _require(name: str, instructions: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        raise MissingSecretError(
            f"\n\n{'='*60}\n"
            f"  MISSING SECRET: {name}\n"
            f"{'='*60}\n"
            f"  {instructions}\n"
            f"{'='*60}\n"
        )
    return val


def _optional(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


# ── Required ──────────────────────────────────────────────────────────────────

def anthropic_key() -> str:
    return _require(
        "ANTHROPIC_API_KEY",
        "Add to GitHub Secrets: github.com/cloudesize67-cmd/gemini/settings/secrets/actions\n"
        "  AND to Railway Variables: railway.app → your project → Variables tab\n"
        "  Get key: console.anthropic.com/settings/keys"
    )

def noesis_hmac_secret() -> str:
    return _require(
        "NOESIS_HMAC_SECRET",
        "Generate a random 32-char string and add to GitHub Secrets + Railway Variables.\n"
        "  Example: python3 -c \"import secrets; print(secrets.token_hex(32))\""
    )

# ── Optional (degrade gracefully if missing) ──────────────────────────────────

def groq_key() -> str:
    return _optional("GROQ_API_KEY")

def gemini_key() -> str:
    return _optional("GEMINI_API_KEY")

def youtube_key() -> str:
    return _optional("YOUTUBE_API_KEY")

def github_token() -> str:
    return _optional("GITHUB_TOKEN")

def slack_webhook() -> str:
    return _optional("SLACK_WEBHOOK_URL")

def railway_token() -> str:
    return _optional("RAILWAY_TOKEN")

def litellm_master_key() -> str:
    return _optional("LITELLM_MASTER_KEY")

def port() -> int:
    return int(_optional("PORT", "8000"))
