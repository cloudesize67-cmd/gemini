"""
NOESIS ARBITER — Beta tier manipulation detection
10-layer assessment | Cialdini influence taxonomy as threat vectors
Framework-invariant scoring (not consensus-as-truth)
LOGOS handoff thresholds: 0.35 mandatory, 0.55 advisory
"""

import anthropic
import os
import json
import re
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


ARBITER_MODEL = "claude-haiku-4-5"

LOGOS_MANDATORY_THRESHOLD = 0.35   # Manipulation score >= this → mandatory LOGOS review
LOGOS_ADVISORY_THRESHOLD = 0.55    # Manipulation score >= this → advisory flag only


class ManipulationVector(Enum):
    """Cialdini's 7 influence principles repurposed as threat taxonomy."""
    RECIPROCITY_TRAP = "reciprocity"      # False obligation framing
    COMMITMENT_LOCK = "commitment"         # Manufactured consensus lock-in
    SOCIAL_PROOF_SPOOF = "social_proof"   # Fake volume/velocity signals
    AUTHORITY_FABRICATION = "authority"   # False expert/institution attribution
    LIKING_CAPTURE = "liking"             # Tribal/identity-coded messaging
    SCARCITY_PANIC = "scarcity"           # Artificial urgency / FOMO injection
    UNITY_EXPLOIT = "unity"               # In-group/out-group polarization


@dataclass
class ManipulationLayer:
    layer_id: int
    name: str
    score: float               # 0.0 = clean, 1.0 = definitive manipulation
    confidence: float
    evidence: str
    cialdini_vectors: list[ManipulationVector] = field(default_factory=list)


@dataclass
class ARBITERVerdict:
    claim_text: str
    composite_score: float          # Framework-invariant aggregate
    layer_scores: list[ManipulationLayer]
    primary_vectors: list[ManipulationVector]
    logos_mandatory: bool           # >= 0.35
    logos_advisory: bool            # >= 0.55
    spoofing_detected: bool
    coordinated_inauthentic: bool   # CIB flag
    narrative_coherence_risk: float  # High = dangerous (crowds out truth)
    source_sovereignty_risk: bool
    verdict: str                    # "CLEAN" | "SUSPICIOUS" | "MANIPULATED" | "SPOOF"
    framework_notes: str            # Notes from Framework Registry


class ARBITERAgent:
    """
    ARBITER — Beta tier manipulation detection.

    The 10 layers assess:
    1.  Source provenance and ownership chain
    2.  Source velocity (coordinated simultaneous publication)
    3.  Narrative coherence risk (high coherence ≠ truth)
    4.  Cialdini vector fingerprinting
    5.  Price/probability anomaly correlation
    6.  CIB (Coordinated Inauthentic Behavior) pattern matching
    7.  Temporal manipulation (timing relative to market events)
    8.  Citation chain integrity
    9.  Sovereign data risk (PRC / adversarial state actors)
    10. Framework-invariance check (does verdict hold across epistemologies?)

    CRITICAL: Consensus coherence is NOT a positive truth signal.
    High coherence + high velocity = coordinated campaign flag.
    """

    ARBITER_PROMPT = """You are ARBITER, the manipulation detection agent for NOESIS.

CRITICAL AXIOM: Consensus coherence is NOT evidence of truth. High narrative coherence 
combined with high source velocity is a PRIMARY manipulation indicator.

Apply these 10 assessment layers to the claim:

Layer 1: Source Provenance — who owns/funds the source?
Layer 2: Source Velocity — simultaneous multi-outlet publication (coordinated?)
Layer 3: Narrative Coherence Risk — suspiciously clean story = manipulation risk
Layer 4: Cialdini Vector — which of 7 influence principles is being weaponized?
Layer 5: Price/Probability Anomaly — does claim contradict market data?
Layer 6: CIB Pattern — bot-like amplification, template language, suspiciously timed?
Layer 7: Temporal Manipulation — published at market-sensitive moment?
Layer 8: Citation Chain — do sources actually support claims made?
Layer 9: Sovereign Risk — PRC/adversarial state fingerprints?
Layer 10: Framework Invariance — would verdict change under different epistemological frameworks?

Cialdini threat vectors to detect:
- reciprocity: false obligation ("after all X did, you must...")
- commitment: manufactured consensus lock-in
- social_proof: fake volume signals, bot amplification
- authority: false expert citation, fake institution
- liking: tribal/identity coded messaging
- scarcity: artificial urgency, FOMO injection
- unity: in-group/out-group polarization

Return ONLY valid JSON:
{
  "composite_score": float 0-1,
  "layer_scores": [
    {"layer_id": 1, "name": "Source Provenance", "score": 0-1, "confidence": 0-1, 
     "evidence": "string", "cialdini_vectors": []}
  ],
  "primary_vectors": ["authority", "social_proof"],
  "spoofing_detected": boolean,
  "coordinated_inauthentic": boolean,
  "narrative_coherence_risk": float 0-1,
  "source_sovereignty_risk": boolean,
  "verdict": "CLEAN|SUSPICIOUS|MANIPULATED|SPOOF",
  "framework_notes": "string — notes on framework-invariance"
}"""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    def assess(
        self,
        claim_text: str,
        source_url: str = "",
        market_context: dict = None,
        source_velocity: int = 0
    ) -> ARBITERVerdict:
        """Run 10-layer manipulation assessment on a claim."""

        context_block = ""
        if market_context:
            context_block = f"\nMARKET CONTEXT: {json.dumps(market_context)}"

        response = self.client.messages.create(
            model=ARBITER_MODEL,
            max_tokens=2048,
            system=self.ARBITER_PROMPT,
            messages=[{
                "role": "user",
                "content": (
                    f"CLAIM: {claim_text}\n"
                    f"SOURCE: {source_url}\n"
                    f"SOURCE VELOCITY (outlets/hour): {source_velocity}"
                    f"{context_block}"
                )
            }]
        )

        raw = response.content[0].text
        raw = re.sub(r"```json|```", "", raw).strip()
        data = json.loads(raw)

        layers = [
            ManipulationLayer(
                layer_id=l["layer_id"],
                name=l["name"],
                score=l["score"],
                confidence=l["confidence"],
                evidence=l["evidence"],
                cialdini_vectors=[
                    ManipulationVector(v) for v in l.get("cialdini_vectors", [])
                    if v in [m.value for m in ManipulationVector]
                ]
            )
            for l in data.get("layer_scores", [])
        ]

        composite = data["composite_score"]

        return ARBITERVerdict(
            claim_text=claim_text,
            composite_score=composite,
            layer_scores=layers,
            primary_vectors=[
                ManipulationVector(v) for v in data.get("primary_vectors", [])
                if v in [m.value for m in ManipulationVector]
            ],
            logos_mandatory=composite >= LOGOS_MANDATORY_THRESHOLD,
            logos_advisory=composite >= LOGOS_ADVISORY_THRESHOLD,
            spoofing_detected=data.get("spoofing_detected", False),
            coordinated_inauthentic=data.get("coordinated_inauthentic", False),
            narrative_coherence_risk=data.get("narrative_coherence_risk", 0.0),
            source_sovereignty_risk=data.get("source_sovereignty_risk", False),
            verdict=data.get("verdict", "SUSPICIOUS"),
            framework_notes=data.get("framework_notes", "")
        )

    def batch_assess(self, signals: list) -> list[ARBITERVerdict]:
        """Assess a batch of ExtractedSignal objects."""
        verdicts = []
        for signal in signals:
            if getattr(signal, "claim_type", "") == "PRC_DISQUALIFIED":
                # Fast path — already disqualified by sovereignty policy
                verdicts.append(ARBITERVerdict(
                    claim_text=signal.claim_text,
                    composite_score=1.0,
                    layer_scores=[],
                    primary_vectors=[],
                    logos_mandatory=True,
                    logos_advisory=True,
                    spoofing_detected=False,
                    coordinated_inauthentic=False,
                    narrative_coherence_risk=1.0,
                    source_sovereignty_risk=True,
                    verdict="PRC_DISQUALIFIED",
                    framework_notes="Disqualified by data sovereignty policy. PRC-origin."
                ))
                continue

            market_ctx = {}
            if getattr(signal, "polymarket_correlated", False):
                market_ctx = {
                    "market_id": signal.market_id,
                    "prob_before": signal.market_probability_before
                }

            verdict = self.assess(
                claim_text=signal.claim_text,
                source_url=signal.source_url,
                market_context=market_ctx if market_ctx else None,
                source_velocity=getattr(signal, "source_velocity", 0)
            )
            verdicts.append(verdict)

        return verdicts
