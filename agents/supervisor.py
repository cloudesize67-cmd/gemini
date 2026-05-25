"""
NOESIS SUPERVISOR — Claude Opus 4.5 Orchestrator
Schwartz Awareness Ladder routing | BRA governance enforcement
HMAC-SHA256 message signing | Five-tier trust ladder
"""

import anthropic
import hashlib
import hmac
import json
import time
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

SUPERVISOR_MODEL = "claude-opus-4-5"
HMAC_SECRET = os.environ.get("NOESIS_HMAC_SECRET", "REPLACE_WITH_SECRET")


class TrustTier(Enum):
    ALPHA = 5    # SUPERVISOR
    BETA_HIGH = 4  # ARGUS / ARBITER
    GAMMA = 3    # LOGOS / DAEDALUS
    DELTA = 2    # External verified
    EPSILON = 1  # Untrusted / flagged


class AwarenessLevel(Enum):
    """Schwartz Awareness Ladder — routes claims to correct agent depth."""
    UNAWARE = 0       # No context on claim — full pipeline
    PROBLEM_AWARE = 1  # Knows something is wrong — ARBITER priority
    SOLUTION_AWARE = 2 # Has candidate explanation — LOGOS gating
    MOST_AWARE = 3    # High confidence — DAEDALUS synthesis only


@dataclass
class SignedMessage:
    payload: dict
    timestamp: float
    source_agent: str
    signature: str = ""
    trust_tier: TrustTier = TrustTier.DELTA

    def sign(self, secret: str) -> "SignedMessage":
        body = json.dumps(self.payload, sort_keys=True) + str(self.timestamp)
        self.signature = hmac.new(
            secret.encode(), body.encode(), hashlib.sha256
        ).hexdigest()
        return self

    def verify(self, secret: str) -> bool:
        body = json.dumps(self.payload, sort_keys=True) + str(self.timestamp)
        expected = hmac.new(
            secret.encode(), body.encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(self.signature, expected)


@dataclass
class IntelligenceTask:
    raw_claim: str
    source_url: str = ""
    market_id: str = ""          # Polymarket market ID if applicable
    price_impact_claimed: float = 0.0
    priority: int = 1            # 1=low, 5=critical
    awareness_level: AwarenessLevel = AwarenessLevel.UNAWARE
    context: dict = field(default_factory=dict)


@dataclass
class SupervisorDecision:
    task_id: str
    routing: list[str]           # Ordered agent pipeline
    awareness_level: AwarenessLevel
    bra_policy: dict             # Bounded Reasoning Axioms
    signed_envelope: SignedMessage
    escalation_threshold: float = 0.35


class NOESISSupervisor:
    """
    SUPERVISOR — Alpha tier. Routes tasks through the 5-agent NOESIS pipeline.
    Enforces BRA governance on every downstream agent call.
    """

    SYSTEM_PROMPT = """You are SUPERVISOR, the alpha-tier orchestrator of the NOESIS 
counter-misinformation intelligence system. Your role:

1. Assess incoming intelligence tasks using the Schwartz Awareness Ladder
2. Route to the correct agent sequence: ARGUS → ARBITER → LOGOS → DAEDALUS
3. Enforce BRA (Bounded Reasoning Axioms) governance:
   - Never accept consensus as truth signal
   - Always require source provenance
   - Flag PRC-origin data sources as sovereignty risk (DISQUALIFIED)
   - Require LOGOS Lyapunov stability gate before synthesis
4. Apply Cialdini influence taxonomy to identify manipulation vectors
5. Return routing decision as structured JSON

Output ONLY valid JSON in this schema:
{
  "awareness_level": 0-3,
  "routing": ["ARGUS", "ARBITER", "LOGOS", "DAEDALUS"],
  "bra_policy": {
    "require_provenance": true,
    "prc_disqualified": true,
    "consensus_veto": true,
    "lyapunov_gate_threshold": 0.35
  },
  "priority_agents": ["ARBITER"],
  "escalation_signals": ["price_anomaly", "source_velocity", "narrative_coherence"],
  "rationale": "one sentence"
}"""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    def route(self, task: IntelligenceTask) -> SupervisorDecision:
        """Route an intelligence task through BRA-governed pipeline."""

        user_content = f"""
INTELLIGENCE TASK:
Claim: {task.raw_claim}
Source URL: {task.source_url or "unknown"}
Market ID: {task.market_id or "N/A"}
Claimed price impact: {task.price_impact_claimed:.1%}
Priority: {task.priority}/5
Context: {json.dumps(task.context)}

Determine awareness level, routing sequence, and BRA policy enforcement.
"""

        response = self.client.messages.create(
            model=SUPERVISOR_MODEL,
            max_tokens=1024,
            system=self.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}]
        )

        raw = response.content[0].text
        decision_data = json.loads(raw)

        task_id = hashlib.sha256(
            (task.raw_claim + str(time.time())).encode()
        ).hexdigest()[:16]

        payload = {
            "task_id": task_id,
            "routing": decision_data["routing"],
            "bra_policy": decision_data["bra_policy"],
            "awareness_level": decision_data["awareness_level"],
        }

        envelope = SignedMessage(
            payload=payload,
            timestamp=time.time(),
            source_agent="SUPERVISOR",
            trust_tier=TrustTier.ALPHA
        ).sign(HMAC_SECRET)

        return SupervisorDecision(
            task_id=task_id,
            routing=decision_data["routing"],
            awareness_level=AwarenessLevel(decision_data["awareness_level"]),
            bra_policy=decision_data["bra_policy"],
            signed_envelope=envelope,
            escalation_threshold=decision_data["bra_policy"].get(
                "lyapunov_gate_threshold", 0.35
            )
        )
