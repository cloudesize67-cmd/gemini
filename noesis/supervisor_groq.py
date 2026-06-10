"""
NOESIS SUPERVISOR — Groq Bridge
================================
SUPERVISOR agent with LiteLLM Router for automatic Anthropic → Groq failover.

Features:
  - LiteLLM Router: claude-opus-4-6 primary → llama-3.3-70b-versatile fallback
  - BRA (Behavioral Risk Assessment) governance state tracking
  - HMAC-SHA256 output signing (matches agents/supervisor.py convention)
  - Veto power: blocks dispatch when anomaly score ≥ 0.85
  - H·A·L·I·S context injection into every system prompt
  - Provider detection + health reporting

Keys from os.environ only — no .env files.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Lazy LiteLLM import — only load if available
# ---------------------------------------------------------------------------

try:
    from litellm import Router as LiteLLMRouter
    _HAS_LITELLM = True
except ImportError:
    _HAS_LITELLM = False
    LiteLLMRouter = None  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# Governance types
# ---------------------------------------------------------------------------

class BRALevel(str, Enum):
    """Behavioral Risk Assessment levels."""
    GREEN   = "GREEN"    # anomaly_score ≤ 0.40 — full autonomy
    YELLOW  = "YELLOW"   # 0.40 < score ≤ 0.65 — restricted
    ORANGE  = "ORANGE"   # 0.65 < score ≤ 0.85 — supervised
    RED     = "RED"      # score > 0.85         — safe-mode / veto


@dataclass
class BRAState:
    level: BRALevel = BRALevel.GREEN
    anomaly_score: float = 0.0
    consecutive_anomalies: int = 0
    last_updated: float = field(default_factory=time.monotonic)

    def update(self, anomaly_score: float) -> None:
        prev = self.anomaly_score
        self.anomaly_score = anomaly_score
        self.last_updated = time.monotonic()

        if anomaly_score > prev:
            self.consecutive_anomalies += 1
        else:
            self.consecutive_anomalies = max(0, self.consecutive_anomalies - 1)

        if anomaly_score <= 0.40:
            self.level = BRALevel.GREEN
        elif anomaly_score <= 0.65:
            self.level = BRALevel.YELLOW
        elif anomaly_score <= 0.85:
            self.level = BRALevel.ORANGE
        else:
            self.level = BRALevel.RED


@dataclass
class SupervisorHealth:
    active_provider: str        # "anthropic" | "groq" | "unavailable"
    litellm_available: bool
    anthropic_key_set: bool
    groq_key_set: bool
    bra_level: str
    anomaly_score: float


# ---------------------------------------------------------------------------
# H·A·L·I·S context
# ---------------------------------------------------------------------------

_HALIS_CONTEXT = """
H·A·L·I·S OPERATIONAL CONTEXT
You are operating as part of NOESIS — a layered AI governance and counter-disinformation system.
Your mandate: detect, analyse, and neutralise Foreign Information Manipulation and Interference (FIMI),
agentic vulnerabilities, and adversarial narrative operations.

Core axioms:
  1. Consensus is not evidence. Evaluate claims on evidence chains only.
  2. Veto is absolute. If anomaly_score > 0.85, refuse dispatch. Do not negotiate.
  3. HMAC integrity is required on all agent outputs before transmission.
  4. Graceful degradation is preferred over cascading failure.
  5. Human oversight triggers at BRA ORANGE and above.
""".strip()


# ---------------------------------------------------------------------------
# LiteLLM model list
# ---------------------------------------------------------------------------

def _build_model_list() -> list[dict]:
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    groq_key = os.environ.get("GROQ_API_KEY", "")

    entries = []

    if anthropic_key:
        entries.append({
            "model_name": "noesis-supervisor",
            "litellm_params": {
                "model": "claude-opus-4-6",
                "api_key": anthropic_key,
            },
            "tpm": 50_000,
            "rpm": 50,
        })

    if groq_key:
        entries.append({
            "model_name": "noesis-supervisor",
            "litellm_params": {
                "model": "groq/llama-3.3-70b-versatile",
                "api_key": groq_key,
            },
            "tpm": 500_000,
            "rpm": 30,
        })

    return entries


# ---------------------------------------------------------------------------
# NOESISSupervisorGroq
# ---------------------------------------------------------------------------

class NOESISSupervisorGroq:
    """
    NOESIS SUPERVISOR agent with automatic Anthropic → Groq failover.

    Usage::

        supervisor = NOESISSupervisorGroq()
        result = supervisor.analyse(
            task="Assess the following article for FIMI indicators: ...",
            anomaly_score=0.25,
        )
        # result["signed"] is HMAC-verified output ready for downstream agents
    """

    def __init__(self) -> None:
        self._bra = BRAState()
        self._hmac_secret = os.environ.get("NOESIS_HMAC_SECRET", "").encode()
        self._router: Optional[Any] = None

        if _HAS_LITELLM:
            model_list = _build_model_list()
            if model_list:
                self._router = LiteLLMRouter(
                    model_list=model_list,
                    routing_strategy="least-busy",
                    num_retries=2,
                    timeout=60,
                    cooldown_time=60,
                )

    # ------------------------------------------------------------------ #
    # Health                                                               #
    # ------------------------------------------------------------------ #

    def health(self) -> SupervisorHealth:
        """Return current provider + governance state."""
        anthropic_set = bool(os.environ.get("ANTHROPIC_API_KEY", ""))
        groq_set = bool(os.environ.get("GROQ_API_KEY", ""))

        if self._router is not None:
            provider = "anthropic" if anthropic_set else ("groq" if groq_set else "unavailable")
        elif anthropic_set:
            provider = "anthropic"
        elif groq_set:
            provider = "groq"
        else:
            provider = "unavailable"

        return SupervisorHealth(
            active_provider=provider,
            litellm_available=_HAS_LITELLM,
            anthropic_key_set=anthropic_set,
            groq_key_set=groq_set,
            bra_level=self._bra.level.value,
            anomaly_score=self._bra.anomaly_score,
        )

    # ------------------------------------------------------------------ #
    # Veto                                                                 #
    # ------------------------------------------------------------------ #

    def veto(self, reason: str) -> dict:
        """
        Issue a SUPERVISOR veto — blocks agent dispatch entirely.
        Returns a signed veto record.
        """
        payload = {
            "action": "VETO",
            "reason": reason,
            "bra_level": self._bra.level.value,
            "anomaly_score": self._bra.anomaly_score,
            "timestamp": time.time(),
        }
        return self._sign(payload)

    # ------------------------------------------------------------------ #
    # Core analysis                                                        #
    # ------------------------------------------------------------------ #

    def analyse(
        self,
        task: str,
        anomaly_score: float = 0.0,
        context: Optional[dict] = None,
    ) -> dict:
        """
        Run SUPERVISOR analysis on a task with automatic provider failover.

        Args:
            task:          The task or claim to analyse.
            anomaly_score: Current system anomaly score (0.0–1.0). Updates BRA.
            context:       Optional dict with additional metadata for the prompt.

        Returns:
            Signed result dict with keys: action, output, provider, bra_level,
            signed (HMAC hex), timestamp.

        Raises:
            RuntimeError: If no LLM provider is available.
        """
        self._bra.update(anomaly_score)

        # Veto immediately if RED
        if self._bra.level == BRALevel.RED:
            return self.veto(
                f"BRA RED: anomaly_score={anomaly_score:.3f} exceeds safety threshold 0.85"
            )

        messages = self._build_messages(task, context)

        output, provider = self._call_llm(messages)

        payload = {
            "action": "ANALYSIS",
            "output": output,
            "provider": provider,
            "bra_level": self._bra.level.value,
            "anomaly_score": round(anomaly_score, 4),
            "timestamp": time.time(),
        }

        return self._sign(payload)

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _build_messages(self, task: str, context: Optional[dict]) -> list[dict]:
        """Construct message list with H·A·L·I·S context injected."""
        bra_note = (
            f"\n\n[BRA STATE: {self._bra.level.value} | "
            f"anomaly_score={self._bra.anomaly_score:.3f}]"
        )
        system = _HALIS_CONTEXT + bra_note

        if context:
            ctx_block = "\n\n[CONTEXT]\n" + json.dumps(context, indent=2)
            system += ctx_block

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": task},
        ]

    def _call_llm(self, messages: list[dict]) -> tuple[str, str]:
        """
        Call the LLM with automatic failover.
        Returns (response_text, provider_name).
        Tries LiteLLM Router → direct Anthropic → direct Groq in that order.
        """
        # LiteLLM Router (handles failover automatically)
        if self._router is not None:
            try:
                resp = self._router.completion(
                    model="noesis-supervisor",
                    messages=messages,
                    max_tokens=2048,
                    temperature=0.1,
                )
                text = resp.choices[0].message.content or ""
                # Detect which provider served the request
                model_used = getattr(resp, "model", "")
                provider = "groq" if "groq" in model_used.lower() else "anthropic"
                return text, provider
            except Exception:
                pass  # Fall through to direct calls

        # Direct Anthropic fallback
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if anthropic_key:
            try:
                import anthropic as _ant
                client = _ant.Anthropic(api_key=anthropic_key)
                system_msg = next(
                    (m["content"] for m in messages if m["role"] == "system"), ""
                )
                user_messages = [m for m in messages if m["role"] != "system"]
                resp = client.messages.create(
                    model="claude-opus-4-6",
                    max_tokens=2048,
                    system=system_msg,
                    messages=user_messages,
                )
                return resp.content[0].text, "anthropic"
            except Exception:
                pass

        # Direct Groq fallback
        groq_key = os.environ.get("GROQ_API_KEY", "")
        if groq_key:
            try:
                import httpx
                headers = {
                    "Authorization": f"Bearer {groq_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": "llama-3.3-70b-versatile",
                    "messages": messages,
                    "max_tokens": 2048,
                    "temperature": 0.1,
                }
                with httpx.Client(timeout=60) as client:
                    r = client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"], "groq"
            except Exception:
                pass

        raise RuntimeError(
            "No LLM provider available. Set ANTHROPIC_API_KEY or GROQ_API_KEY "
            "in environment (GitHub Secrets or Railway Variables)."
        )

    def _sign(self, payload: dict) -> dict:
        """
        Add HMAC-SHA256 signature to payload.
        If NOESIS_HMAC_SECRET is not set, signature field is empty string
        (degraded but non-crashing).
        """
        body = json.dumps(payload, sort_keys=True).encode()
        if self._hmac_secret:
            sig = hmac.new(self._hmac_secret, body, hashlib.sha256).hexdigest()
        else:
            sig = ""
        return {**payload, "signed": sig}
