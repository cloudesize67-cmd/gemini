"""
NOESIS Pipeline — Main orchestration entry point
Runs: SUPERVISOR → ARGUS → ARBITER → LOGOS → DAEDALUS
HMAC-verified inter-agent messaging | BRA governance throughout
"""

import os
import json
import time
import logging
from dataclasses import asdict
from agents.supervisor import NOESISSupervisor, IntelligenceTask, AwarenessLevel
from agents.argus import ARGUSAgent
from agents.arbiter import ARBITERAgent
from agents.logos import LOGOSAgent
from agents.daedalus import DAEDALUSAgent, SynthesisReport

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
log = logging.getLogger("NOESIS")


class NOESISPipeline:
    """
    Full 5-agent NOESIS pipeline.
    Input: raw claim + source + optional market ID
    Output: SynthesisReport with verdict, manipulation score, recommended actions
    """

    def __init__(self):
        self.supervisor = NOESISSupervisor()
        self.argus = ARGUSAgent()
        self.arbiter = ARBITERAgent()
        self.logos = LOGOSAgent()
        self.daedalus = DAEDALUSAgent()

    def run(
        self,
        raw_content: str,
        source_url: str = "",
        market_id: str = "",
        price_impact_claimed: float = 0.0,
        priority: int = 3
    ) -> SynthesisReport:
        """
        Execute full NOESIS pipeline on input content.
        Returns SynthesisReport with actionable intelligence.
        """

        start = time.time()
        log.info(f"NOESIS pipeline starting | source={source_url[:80]}")

        # ── SUPERVISOR: Route task through BRA governance ──
        task = IntelligenceTask(
            raw_claim=raw_content[:500],
            source_url=source_url,
            market_id=market_id,
            price_impact_claimed=price_impact_claimed,
            priority=priority
        )
        decision = self.supervisor.route(task)
        log.info(
            f"SUPERVISOR routed | task_id={decision.task_id} "
            f"routing={decision.routing} "
            f"awareness={decision.awareness_level.name}"
        )

        # Verify SUPERVISOR envelope signature
        if not decision.signed_envelope.verify(
            os.environ.get("NOESIS_HMAC_SECRET", "REPLACE_WITH_SECRET")
        ):
            log.error("SUPERVISOR envelope HMAC verification FAILED — aborting")
            raise SecurityError("HMAC verification failed on SUPERVISOR envelope")

        # ── ARGUS: Extract structured signals ──
        signals = []
        if "ARGUS" in decision.routing:
            log.info("ARGUS: extracting signals...")
            signals = self.argus.extract_signals(raw_content, source_url)
            signals = self.argus.scan_market_anomalies(signals)
            log.info(f"ARGUS: {len(signals)} signals extracted")

        # Fast path for high-awareness tasks — skip ARGUS, use raw claim
        if not signals:
            from agents.argus import ExtractedSignal
            signals = [ExtractedSignal(
                claim_text=raw_content[:1000],
                claim_type="direct_claim",
                quantified_value=price_impact_claimed or None,
                source_url=source_url,
                source_domain=source_url.split("/")[2] if "://" in source_url else "unknown",
                extraction_confidence=0.7
            )]

        # ── ARBITER: 10-layer manipulation detection ──
        arbiter_verdicts = []
        if "ARBITER" in decision.routing:
            log.info("ARBITER: running 10-layer manipulation assessment...")
            arbiter_verdicts = self.arbiter.batch_assess(signals)
            for v in arbiter_verdicts:
                log.info(
                    f"ARBITER verdict: {v.verdict} | "
                    f"score={v.composite_score:.3f} | "
                    f"spoof={v.spoofing_detected} | "
                    f"cib={v.coordinated_inauthentic}"
                )

        # ── LOGOS: Lyapunov stability gating ──
        logos_gates = []
        if "LOGOS" in decision.routing:
            log.info("LOGOS: Lyapunov gating...")
            for i, verdict in enumerate(arbiter_verdicts):
                if verdict.logos_mandatory or verdict.logos_advisory:
                    gate = self.logos.gate(
                        claim_text=verdict.claim_text,
                        arbiter_composite_score=verdict.composite_score,
                        arbiter_verdict=verdict.verdict
                    )
                    logos_gates.append(gate)
                    log.info(
                        f"LOGOS gate {i}: stability={gate.stability_score:.3f} | "
                        f"pass={gate.pass_to_daedalus} | "
                        f"dV/dt={gate.lyapunov_derivative:.3f}"
                    )

        # If no LOGOS gates run, pass all through
        if not logos_gates and arbiter_verdicts:
            from agents.logos import LyapunovGateResult
            logos_gates = [LyapunovGateResult(
                claim_text=v.claim_text,
                stability_score=0.7,
                framework_assessments=[],
                framework_invariant=True,
                paradigm_shift_candidate=False,
                pass_to_daedalus=True,
                gate_reason="No LOGOS gate required by routing",
                lyapunov_derivative=-0.1,
                corrected_composite_score=v.composite_score
            ) for v in arbiter_verdicts]

        # ── DAEDALUS: Synthesis ──
        log.info("DAEDALUS: synthesizing report...")
        report = self.daedalus.synthesize(
            arbiter_verdicts=arbiter_verdicts,
            logos_gates=logos_gates,
            original_task={
                "task_id": decision.task_id,
                "source_url": source_url,
                "market_id": market_id,
                "raw_claim_snippet": raw_content[:200]
            }
        )

        elapsed = time.time() - start
        log.info(
            f"NOESIS complete | task_id={decision.task_id} | "
            f"verdict={report.verdict} | "
            f"confidence={report.confidence:.2%} | "
            f"elapsed={elapsed:.2f}s"
        )

        return report


class SecurityError(Exception):
    pass


def run_analysis(
    content: str,
    source_url: str = "",
    market_id: str = "",
    price_impact: float = 0.0
) -> dict:
    """
    Public entry point for HTTP/MCP interface.
    Returns JSON-serializable dict.
    """
    pipeline = NOESISPipeline()
    report = pipeline.run(
        raw_content=content,
        source_url=source_url,
        market_id=market_id,
        price_impact_claimed=price_impact
    )

    return {
        "verdict": report.verdict,
        "confidence": round(report.confidence, 4),
        "manipulation_score": round(report.manipulation_score, 4),
        "executive_summary": report.executive_summary,
        "key_findings": report.key_findings,
        "market_impact": report.market_impact_assessment,
        "recommended_actions": report.recommended_actions,
        "spoof_pattern": report.spoof_pattern,
        "cib_assessment": report.cib_assessment,
        "sovereign_risk": report.sovereign_risk_flag,
        "evidence_chain": report.evidence_chain,
        "task_id": report.task_id,
        "timestamp": report.timestamp
    }


if __name__ == "__main__":
    # Quick smoke test
    result = run_analysis(
        content="BREAKING: Federal Reserve to emergency cut rates 100bps at 3PM today, sources say",
        source_url="https://example-news-source.com/fed-emergency-cut",
        price_impact=0.85
    )
    print(json.dumps(result, indent=2))
