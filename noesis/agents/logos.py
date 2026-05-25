"""
NOESIS LOGOS — Gamma tier truth gating
Lyapunov stability analysis | Framework Registry
Correctly handles paradigm-shift cases without systematic veto
"""

import anthropic
import os
import json
import re
import math
from dataclasses import dataclass, field
from typing import Optional


LOGOS_MODEL = "claude-haiku-4-5"

# Lyapunov thresholds
MANDATORY_REVIEW_SCORE = 0.35   # From ARBITER — any above this enters LOGOS
STABILITY_PASS = 0.65            # LOGOS stability score needed to pass to DAEDALUS
PARADIGM_SHIFT_FLAG = 0.40      # Scores between 0.35-0.65 MAY be paradigm shifts


@dataclass
class FrameworkAssessment:
    """Assessment of a claim under a single epistemological framework."""
    framework_name: str      # e.g., "empiricist", "consensus_science", "bayesian"
    framework_verdict: str   # "SUPPORTS" | "CONTRADICTS" | "NEUTRAL" | "PARADIGM_SHIFT"
    confidence: float
    notes: str


@dataclass
class LyapunovGateResult:
    claim_text: str
    stability_score: float          # 0 = unstable, 1 = maximally stable
    framework_assessments: list[FrameworkAssessment]
    framework_invariant: bool       # True if verdict consistent across frameworks
    paradigm_shift_candidate: bool  # True if contradicts consensus but has coherent basis
    pass_to_daedalus: bool
    gate_reason: str
    lyapunov_derivative: float      # dV/dt — positive means destabilizing claim
    corrected_composite_score: float


class FrameworkRegistry:
    """
    Registry of epistemological frameworks used for invariance checking.
    Prevents LOGOS from systematically vetoing correct paradigm shifts.
    """
    FRAMEWORKS = [
        "empiricist",       # Evidence-based, reproducible
        "bayesian",         # Prior + likelihood updating
        "consensus_science", # Peer-reviewed mainstream
        "adversarial",      # Assumes hostile intent by default
        "de_broglie_bohm",  # Pilot wave — underlying deterministic reality
        "information_theoretic", # Signal/noise, entropy-based
    ]

    @staticmethod
    def is_paradigm_shift_coherent(
        assessments: list[FrameworkAssessment]
    ) -> bool:
        """
        A claim is a candidate paradigm shift (not manipulation) if:
        - It contradicts consensus_science
        - BUT has coherent support in ≥2 other frameworks
        This prevents LOGOS from vetoing correct heterodox claims.
        """
        consensus_verdict = next(
            (a.framework_verdict for a in assessments
             if a.framework_name == "consensus_science"), "NEUTRAL"
        )
        if consensus_verdict not in ("CONTRADICTS",):
            return False

        supporting_frameworks = [
            a for a in assessments
            if a.framework_verdict == "SUPPORTS"
            and a.framework_name != "consensus_science"
            and a.confidence >= 0.6
        ]
        return len(supporting_frameworks) >= 2


class LOGOSAgent:
    """
    LOGOS — Gamma tier Lyapunov stability gating.

    Models information dynamics as a Lyapunov system:
    V(x) = stability potential of the information environment.
    dV/dt > 0 means the claim is destabilizing — flag for ARBITER re-review.
    dV/dt < 0 means claim moves toward equilibrium — pass to DAEDALUS.

    Framework Registry prevents systematic veto of paradigm shifts.
    """

    LOGOS_PROMPT = """You are LOGOS, the Lyapunov stability gate for NOESIS.

Model the information environment as a dynamical system:
- V(x) = stability potential (higher = more stable epistemic state)
- dV/dt = rate of change (positive = destabilizing claim)

Assess the claim under these 6 frameworks:
1. empiricist — reproducible evidence standard
2. bayesian — prior + likelihood update
3. consensus_science — peer-reviewed mainstream
4. adversarial — assume hostile intent by default
5. de_broglie_bohm — pilot wave: deterministic underlying reality
6. information_theoretic — signal-to-noise, entropy

CRITICAL: If a claim contradicts consensus_science but has coherent support in 
≥2 other frameworks, it is a PARADIGM_SHIFT_CANDIDATE — do NOT veto it.
Only veto claims that are incoherent across ALL frameworks.

Return ONLY valid JSON:
{
  "stability_score": float 0-1,
  "lyapunov_derivative": float (negative=stabilizing, positive=destabilizing),
  "framework_assessments": [
    {
      "framework_name": string,
      "framework_verdict": "SUPPORTS|CONTRADICTS|NEUTRAL|PARADIGM_SHIFT",
      "confidence": float 0-1,
      "notes": string
    }
  ],
  "framework_invariant": boolean,
  "paradigm_shift_candidate": boolean,
  "pass_to_daedalus": boolean,
  "gate_reason": string,
  "corrected_composite_score": float 0-1
}"""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self.registry = FrameworkRegistry()

    def gate(
        self,
        claim_text: str,
        arbiter_composite_score: float,
        arbiter_verdict: str = "",
        market_context: dict = None
    ) -> LyapunovGateResult:
        """Apply Lyapunov stability gate to a claim."""

        context_str = ""
        if market_context:
            context_str = f"\nMARKET CONTEXT: {json.dumps(market_context)}"

        response = self.client.messages.create(
            model=LOGOS_MODEL,
            max_tokens=2048,
            system=self.LOGOS_PROMPT,
            messages=[{
                "role": "user",
                "content": (
                    f"CLAIM: {claim_text}\n"
                    f"ARBITER COMPOSITE SCORE: {arbiter_composite_score:.3f}\n"
                    f"ARBITER VERDICT: {arbiter_verdict}"
                    f"{context_str}"
                )
            }]
        )

        raw = response.content[0].text
        raw = re.sub(r"```json|```", "", raw).strip()
        data = json.loads(raw)

        assessments = [
            FrameworkAssessment(
                framework_name=fa["framework_name"],
                framework_verdict=fa["framework_verdict"],
                confidence=fa["confidence"],
                notes=fa["notes"]
            )
            for fa in data.get("framework_assessments", [])
        ]

        # Override paradigm_shift check with Registry logic
        paradigm_override = FrameworkRegistry.is_paradigm_shift_coherent(assessments)

        stability = data["stability_score"]
        lv_deriv = data.get("lyapunov_derivative", 0.0)

        # If paradigm shift candidate, don't let LOGOS veto
        pass_decision = data.get("pass_to_daedalus", stability >= STABILITY_PASS)
        if paradigm_override:
            pass_decision = True

        return LyapunovGateResult(
            claim_text=claim_text,
            stability_score=stability,
            framework_assessments=assessments,
            framework_invariant=data.get("framework_invariant", False),
            paradigm_shift_candidate=paradigm_override or data.get("paradigm_shift_candidate", False),
            pass_to_daedalus=pass_decision,
            gate_reason=data.get("gate_reason", ""),
            lyapunov_derivative=lv_deriv,
            corrected_composite_score=data.get("corrected_composite_score", arbiter_composite_score)
        )
