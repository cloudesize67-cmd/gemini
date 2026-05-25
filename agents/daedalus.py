"""
NOESIS DAEDALUS — Gamma tier swarm synthesis
Hormozi Value Equation in content strategy output
Anti-AI style filter | XML envelope inter-agent protocol
"""

import anthropic
import os
import json
import re
from dataclasses import dataclass, field
from typing import Optional


DAEDALUS_MODEL = "claude-sonnet-4-5"


@dataclass
class SynthesisReport:
    """Final NOESIS intelligence output after full pipeline."""
    verdict: str                    # "CLEAN" | "SUSPICIOUS" | "MISINFORMATION" | "MARKET_SPOOF"
    confidence: float
    manipulation_score: float
    executive_summary: str          # Hormozi Value: Dream Outcome framing
    key_findings: list[str]
    market_impact_assessment: str
    recommended_actions: list[str]
    evidence_chain: list[dict]      # Cite trail
    spoof_pattern: Optional[str]    # Described spoof technique if detected
    cib_assessment: str             # Coordinated Inauthentic Behavior analysis
    sovereign_risk_flag: bool
    timestamp: float = 0.0
    task_id: str = ""


class DAEDALUSAgent:
    """
    DAEDALUS — Gamma tier synthesis.
    Applies Hormozi's Value Equation: Dream Outcome / (Perceived Likelihood × Time × Effort)
    Anti-AI style filter ensures output reads as authored intelligence, not AI summary.
    XML envelope protocol for inter-agent messaging.
    """

    # Hormozi Value Equation applied to intelligence output framing:
    # Dream Outcome = What the analyst actually needs to act
    # Perceived Likelihood = Calibrated confidence
    # Time delay = Urgency signal
    # Effort = Actionability (zero friction actions first)

    DAEDALUS_PROMPT = """You are DAEDALUS, the synthesis agent for NOESIS.

You receive verified intelligence from ARBITER + LOGOS. Your job:
1. Synthesize into actionable intelligence reports
2. Apply Hormozi Value Equation: lead with Dream Outcome (what analyst needs to act NOW),
   followed by calibrated confidence, urgency, and zero-friction actions
3. Apply anti-AI style filter: write like a senior intelligence analyst, not an AI summary.
   Use specific numbers. Name patterns. Call out actors. No hedging language.
4. Structure output for market operators: what does this mean for positions?

Anti-AI rules:
- Never say "it's worth noting" / "it's important to" / "as we can see"
- No bullet soup — use narrative paragraphs with hard numbers
- Name the manipulation technique precisely (e.g., "Layer-2 social proof spoof via bot amplification")
- State confidence as a number, not "high" or "low"

Hormozi framing for executive summary:
"[WHAT HAPPENED] costs/risks [SPECIFIC DOLLAR/% IMPACT] if [SPECIFIC ACTION] is not taken 
within [TIME WINDOW]. Confidence: [X%]."

Return ONLY valid JSON:
{
  "verdict": "CLEAN|SUSPICIOUS|MISINFORMATION|MARKET_SPOOF",
  "confidence": float 0-1,
  "manipulation_score": float 0-1,
  "executive_summary": string (Hormozi framing),
  "key_findings": [string],
  "market_impact_assessment": string,
  "recommended_actions": [string],
  "evidence_chain": [{"source": string, "claim": string, "verdict": string}],
  "spoof_pattern": string | null,
  "cib_assessment": string,
  "sovereign_risk_flag": boolean
}"""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    def synthesize(
        self,
        arbiter_verdicts: list,
        logos_gates: list,
        original_task: dict = None
    ) -> SynthesisReport:
        """Synthesize full pipeline output into actionable intelligence."""

        import time

        # Build XML envelope (inter-agent protocol standard)
        envelope = self._build_xml_envelope(arbiter_verdicts, logos_gates)

        response = self.client.messages.create(
            model=DAEDALUS_MODEL,
            max_tokens=4096,
            system=self.DAEDALUS_PROMPT,
            messages=[{
                "role": "user",
                "content": (
                    f"PIPELINE OUTPUT:\n{envelope}\n\n"
                    f"ORIGINAL TASK: {json.dumps(original_task or {})}"
                )
            }]
        )

        raw = response.content[0].text
        raw = re.sub(r"```json|```", "", raw).strip()
        data = json.loads(raw)

        return SynthesisReport(
            verdict=data["verdict"],
            confidence=data["confidence"],
            manipulation_score=data["manipulation_score"],
            executive_summary=data["executive_summary"],
            key_findings=data.get("key_findings", []),
            market_impact_assessment=data.get("market_impact_assessment", ""),
            recommended_actions=data.get("recommended_actions", []),
            evidence_chain=data.get("evidence_chain", []),
            spoof_pattern=data.get("spoof_pattern"),
            cib_assessment=data.get("cib_assessment", ""),
            sovereign_risk_flag=data.get("sovereign_risk_flag", False),
            timestamp=time.time(),
            task_id=str(original_task.get("task_id", "")) if original_task else ""
        )

    def _build_xml_envelope(self, arbiter_verdicts: list, logos_gates: list) -> str:
        """Build XML inter-agent message envelope from pipeline results."""
        lines = ["<noesis_pipeline_output>"]

        for i, verdict in enumerate(arbiter_verdicts):
            lines.append(f"  <arbiter_signal index='{i}'>")
            lines.append(f"    <claim>{getattr(verdict, 'claim_text', '')[:200]}</claim>")
            lines.append(f"    <composite_score>{getattr(verdict, 'composite_score', 0):.3f}</composite_score>")
            lines.append(f"    <verdict>{getattr(verdict, 'verdict', 'UNKNOWN')}</verdict>")
            lines.append(f"    <spoofing>{getattr(verdict, 'spoofing_detected', False)}</spoofing>")
            lines.append(f"    <cib>{getattr(verdict, 'coordinated_inauthentic', False)}</cib>")
            lines.append(f"    <sovereignty_risk>{getattr(verdict, 'source_sovereignty_risk', False)}</sovereignty_risk>")
            lines.append(f"  </arbiter_signal>")

        for i, gate in enumerate(logos_gates):
            lines.append(f"  <logos_gate index='{i}'>")
            lines.append(f"    <stability_score>{getattr(gate, 'stability_score', 0):.3f}</stability_score>")
            lines.append(f"    <pass>{getattr(gate, 'pass_to_daedalus', False)}</pass>")
            lines.append(f"    <lyapunov_dv_dt>{getattr(gate, 'lyapunov_derivative', 0):.3f}</lyapunov_dv_dt>")
            lines.append(f"    <paradigm_shift>{getattr(gate, 'paradigm_shift_candidate', False)}</paradigm_shift>")
            lines.append(f"    <reason>{getattr(gate, 'gate_reason', '')}</reason>")
            lines.append(f"  </logos_gate>")

        lines.append("</noesis_pipeline_output>")
        return "\n".join(lines)
