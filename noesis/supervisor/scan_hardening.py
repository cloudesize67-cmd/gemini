"""
NOESIS Supervisor — Hardened Scan Orchestrator
================================================
Integrates all NOESIS detection layers into a single hardened scan pipeline.

Scan stages (in order):
  1. FIMI pre-screening       — deterministic regex, runs before any LLM call
  2. Agent-vuln gate          — catches prompt injection / goal hijacking
  3. Pathology gate           — loop / bottleneck / context-runaway check
  4. AAE authorization        — HMAC-verified dispatch envelope
  5. AgentSight correlation   — intent vs action causal alignment
  6. Groq deep scan (opt.)    — LLM-backed analysis for flagged patterns
  7. HMAC output signing      — every result is cryptographically sealed

handle_scan_pattern()       — lightweight single-pattern dispatcher.
HardenedScanOrchestrator    — full pipeline orchestrator.

Keys from os.environ only — no .env files.
"""
from __future__ import annotations

import hashlib
import hmac as _hmac
import json
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Path bootstrap — allow running from noesis/ or repo root
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_NOESIS_ROOT = os.path.dirname(_HERE)
if _NOESIS_ROOT not in sys.path:
    sys.path.insert(0, _NOESIS_ROOT)


# ---------------------------------------------------------------------------
# Lazy imports — modules may not all be present in every deployment
# ---------------------------------------------------------------------------

def _import_fimi():
    from arbiter_fimi import FIMIDetector, FIMIVerdict
    return FIMIDetector, FIMIVerdict

def _import_pathology():
    from logos_pathology import PathologyGate, PathologyReport
    return PathologyGate, PathologyReport

def _import_aae():
    from supervisor_aae import SupervisorAAE
    return SupervisorAAE

def _import_agentsight():
    from agentsight import AgentSight
    return AgentSight

def _import_groq_router():
    from groq_router import GroqRouter
    return GroqRouter


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class ScanStageResult:
    stage: str
    passed: bool
    score: float           # 0.0 = clean, 1.0 = maximum threat
    vectors: list[str]
    recommendation: str    # CONTINUE | THROTTLE | RESET | VETO | ESCALATE
    detail: dict = field(default_factory=dict)


@dataclass
class ScanResult:
    """Full pipeline scan result — returned by HardenedScanOrchestrator.scan()."""
    claim_text_hash: str        # SHA-256 of input (never stores raw text)
    stages: list[ScanStageResult]
    composite_risk_score: float # weighted across all stages
    veto_recommended: bool      # any stage issued VETO
    graceful_degrade: bool      # composite >= 0.45
    escalate_to_supervisor: bool# agent-vuln vector or composite >= 0.85
    final_recommendation: str   # CONTINUE | THROTTLE | RESET | VETO | ESCALATE
    scan_duration_ms: float
    signed: str                 # HMAC-SHA256 of result body


# Stage weights for composite score
_STAGE_WEIGHTS = {
    "FIMI_PRE_SCREEN": 0.20,
    "AGENT_VULN":      0.30,   # highest weight — injection is highest-priority threat
    "PATHOLOGY":       0.15,
    "AAE_AUTH":        0.15,
    "AGENTSIGHT":      0.20,
}


# ---------------------------------------------------------------------------
# handle_scan_pattern — single-pattern lightweight dispatcher
# ---------------------------------------------------------------------------

def handle_scan_pattern(
    pattern: str,
    text: str,
    context: Optional[dict] = None,
) -> dict:
    """
    Run a single named scan pattern against text.

    Supported patterns:
      FIMI_RUSSIAN     — Russian FIMI vector scoring
      FIMI_CHINESE     — Chinese FIMI vector scoring
      AGENT_VULN       — AI-specific manipulation (injection, sycophancy, etc.)
      FIMI_FULL        — All FIMI families combined
      PATHOLOGY        — Pathological loop / bottleneck / evolution check
      AGENTSIGHT       — Intent vs action causal correlation
      FULL             — Run the complete HardenedScanOrchestrator pipeline

    Args:
        pattern:  One of the patterns above (case-insensitive).
        text:     Input text to scan.
        context:  Optional metadata dict (passed through to detectors).

    Returns:
        Dict with keys: pattern, score, vectors, recommendation, detail.
    """
    pattern_upper = pattern.upper()
    ctx = context or {}

    if pattern_upper in ("FIMI_RUSSIAN", "FIMI_CHINESE", "AGENT_VULN", "FIMI_FULL"):
        FIMIDetector, _ = _import_fimi()
        verdict = FIMIDetector().analyze(text, ctx)
        if pattern_upper == "FIMI_RUSSIAN":
            score = verdict.russian_score
        elif pattern_upper == "FIMI_CHINESE":
            score = verdict.chinese_score
        elif pattern_upper == "AGENT_VULN":
            score = verdict.agent_vuln_score
        else:
            score = verdict.composite_fimi_score
        return {
            "pattern": pattern_upper,
            "score": score,
            "vectors": verdict.detected_vectors,
            "recommendation": "VETO" if verdict.veto_recommended
                              else "THROTTLE" if verdict.graceful_degrade
                              else "CONTINUE",
            "detail": {
                "russian_score": verdict.russian_score,
                "chinese_score": verdict.chinese_score,
                "agent_vuln_score": verdict.agent_vuln_score,
                "composite": verdict.composite_fimi_score,
                "escalate": verdict.escalate_to_supervisor,
            },
        }

    if pattern_upper == "PATHOLOGY":
        PathologyGate, _ = _import_pathology()
        gate = PathologyGate()
        # Record a single probe call from context metadata
        tool = ctx.get("tool_name", "unknown")
        error = ctx.get("error", "")
        agent = ctx.get("agent_name", "unknown")
        ctx_size = ctx.get("context_size", 0)
        gate.record_call(tool, error, agent, ctx_size)
        report = gate.assess()
        return {
            "pattern": "PATHOLOGY",
            "score": 1.0 if report.any_pathology else 0.0,
            "vectors": [report.recommended_action] if report.any_pathology else [],
            "recommendation": report.recommended_action,
            "detail": {
                "loop_detected": report.loop_report.loop_detected,
                "stuck_tool": report.loop_report.stuck_tool,
                "bottleneck_detected": report.bottleneck_report.bottleneck_detected,
                "retry_rate": report.bottleneck_report.retry_rate,
                "runaway_detected": report.evolution_report.runaway_detected,
                "growth_ratio": report.evolution_report.growth_ratio,
            },
        }

    if pattern_upper == "AGENTSIGHT":
        AgentSight = _import_agentsight()
        sight = AgentSight()
        agent = ctx.get("agent_name", "UNKNOWN")
        intent_text = ctx.get("intent_text", text)
        tool_name = ctx.get("tool_name", "unknown")
        tool_args = ctx.get("tool_args", {})
        declared_tools = ctx.get("declared_tools", [tool_name] if tool_name != "unknown" else [])
        sight.record_intent(
            agent_id=agent,
            intent_text=intent_text,
            declared_tools=declared_tools,
        )
        sight.record_action(
            agent_id=agent,
            tool_name=tool_name,
            tool_args=tool_args if isinstance(tool_args, dict) else {},
        )
        corr = sight.correlate(agent)
        if corr is None:
            return {
                "pattern": "AGENTSIGHT",
                "score": 0.0,
                "vectors": [],
                "recommendation": "CONTINUE",
                "detail": {"verdict": "NO_DATA"},
            }
        score = 1.0 - corr.alignment_score
        rec = ("VETO" if corr.verdict in ("ROGUE", "INJECTION", "SELF_EVOLVE")
               else "ESCALATE" if corr.verdict == "SUSPICIOUS"
               else "CONTINUE")
        return {
            "pattern": "AGENTSIGHT",
            "score": round(score, 4),
            "vectors": corr.divergence_flags,
            "recommendation": rec,
            "detail": {
                "verdict": corr.verdict,
                "alignment_score": corr.alignment_score,
            },
        }

    if pattern_upper == "FULL":
        orchestrator = HardenedScanOrchestrator()
        result = orchestrator.scan(text, context=ctx)
        return {
            "pattern": "FULL",
            "score": result.composite_risk_score,
            "vectors": [s.recommendation for s in result.stages if not s.passed],
            "recommendation": result.final_recommendation,
            "detail": {
                "stages": [
                    {"stage": s.stage, "score": s.score, "passed": s.passed}
                    for s in result.stages
                ],
                "veto": result.veto_recommended,
                "signed": result.signed,
            },
        }

    # Unknown pattern — return neutral pass-through
    return {
        "pattern": pattern_upper,
        "score": 0.0,
        "vectors": [],
        "recommendation": "CONTINUE",
        "detail": {"warning": f"Unknown scan pattern: {pattern!r}"},
    }


# ---------------------------------------------------------------------------
# HardenedScanOrchestrator — full pipeline
# ---------------------------------------------------------------------------

class HardenedScanOrchestrator:
    """
    Full hardened scan pipeline integrating all NOESIS detection layers.

    Usage::

        orchestrator = HardenedScanOrchestrator()
        result = orchestrator.scan(
            claim_text="The western media is hiding the truth...",
            context={
                "agent_name": "ARGUS",
                "tool_name": "web_search",
                "tool_args": {"query": "..."},
                "intent_text": "I will search for corroborating sources",
                "context_size": 4000,
            },
        )
        if result.veto_recommended:
            block_dispatch(result)
    """

    def __init__(self) -> None:
        self._hmac_secret = os.environ.get("NOESIS_HMAC_SECRET", "").encode()

        # Instantiate detectors once — reused across calls
        FIMIDetector, _ = _import_fimi()
        self._fimi = FIMIDetector()

        PathologyGate, _ = _import_pathology()
        self._pathology_gate = PathologyGate()

        AgentSight = _import_agentsight()
        self._agentsight = AgentSight()

        # AAE supervisor (optional — degrades gracefully if missing)
        try:
            self._aae = _import_aae()()
        except Exception:
            self._aae = None

        # Groq router (optional — skipped if GROQ_API_KEY not set)
        try:
            self._groq = _import_groq_router()()
        except EnvironmentError:
            self._groq = None

    # ------------------------------------------------------------------ #
    # Public                                                               #
    # ------------------------------------------------------------------ #

    def scan(
        self,
        claim_text: str,
        context: Optional[dict] = None,
        run_groq_on_flag: bool = False,
    ) -> ScanResult:
        """
        Run the full hardened scan pipeline.

        Args:
            claim_text:        Text to analyse (claim, agent output, user input, etc.).
            context:           Optional metadata dict with keys:
                                 agent_name, tool_name, tool_args,
                                 intent_text, error, context_size.
            run_groq_on_flag:  If True and Groq is available, run deep LLM
                                analysis on any stage that issues VETO/ESCALATE.

        Returns:
            ScanResult with composite risk score, per-stage breakdown,
            final recommendation, and HMAC signature.
        """
        t_start = time.monotonic()
        ctx = context or {}
        stages: list[ScanStageResult] = []

        # ── Stage 1: FIMI pre-screen ───────────────────────────────────
        fimi_verdict = self._fimi.analyze(claim_text, ctx)
        stage1 = ScanStageResult(
            stage="FIMI_PRE_SCREEN",
            passed=not fimi_verdict.graceful_degrade,
            score=fimi_verdict.composite_fimi_score,
            vectors=fimi_verdict.detected_vectors,
            recommendation=(
                "VETO"     if fimi_verdict.veto_recommended else
                "THROTTLE" if fimi_verdict.graceful_degrade else
                "CONTINUE"
            ),
            detail={
                "russian": fimi_verdict.russian_score,
                "chinese": fimi_verdict.chinese_score,
                "agent_vuln": fimi_verdict.agent_vuln_score,
            },
        )
        stages.append(stage1)

        # ── Stage 2: Agent-vuln gate (subset of FIMI — highest priority) ─
        agent_vuln_vectors = {
            v for v in fimi_verdict.detected_vectors
            if v in ("PROMPT_INJECTION", "VISOR_VISUAL_STEERING",
                     "SYCOPHANCY_INDUCTION", "REFUSAL_SUPPRESSION", "GOAL_HIJACKING")
        }
        stage2 = ScanStageResult(
            stage="AGENT_VULN",
            passed=not bool(agent_vuln_vectors),
            score=fimi_verdict.agent_vuln_score,
            vectors=list(agent_vuln_vectors),
            recommendation="ESCALATE" if agent_vuln_vectors else "CONTINUE",
            detail={"escalate_to_supervisor": fimi_verdict.escalate_to_supervisor},
        )
        stages.append(stage2)

        # ── Stage 3: Pathology gate ─────────────────────────────────────
        tool_name  = ctx.get("tool_name", "unknown")
        error      = ctx.get("error", "")
        agent_name = ctx.get("agent_name", "UNKNOWN")
        ctx_size   = int(ctx.get("context_size", 0))
        self._pathology_gate.record_call(tool_name, error, agent_name, ctx_size)
        path_report = self._pathology_gate.assess()
        path_score  = 1.0 if path_report.any_pathology else 0.0
        stage3 = ScanStageResult(
            stage="PATHOLOGY",
            passed=not path_report.any_pathology,
            score=path_score,
            vectors=[path_report.recommended_action] if path_report.any_pathology else [],
            recommendation=path_report.recommended_action,
            detail={
                "loop": path_report.loop_report.loop_detected,
                "bottleneck": path_report.bottleneck_report.bottleneck_detected,
                "runaway": path_report.evolution_report.runaway_detected,
            },
        )
        stages.append(stage3)

        # ── Stage 4: AAE authorization ──────────────────────────────────
        if self._aae is not None:
            try:
                aae_result = self._aae.authorize_dispatch(
                    agent_name=agent_name,
                    task_text=claim_text,
                )
                aae_score  = 0.0 if aae_result.get("authorized") else 1.0
                aae_rec    = "CONTINUE" if aae_result.get("authorized") else "VETO"
                aae_passed = aae_result.get("authorized", False)
                aae_detail = {k: v for k, v in aae_result.items()
                              if k not in ("authorized",)}
            except Exception as exc:
                aae_score, aae_rec, aae_passed = 0.5, "THROTTLE", False
                aae_detail = {"error": str(exc)}
        else:
            aae_score, aae_rec, aae_passed = 0.0, "CONTINUE", True
            aae_detail = {"skipped": "AAE not available"}

        stage4 = ScanStageResult(
            stage="AAE_AUTH",
            passed=aae_passed,
            score=aae_score,
            vectors=[] if aae_passed else ["AAE_UNAUTHORIZED"],
            recommendation=aae_rec,
            detail=aae_detail,
        )
        stages.append(stage4)

        # ── Stage 5: AgentSight causal correlation ──────────────────────
        intent_text = ctx.get("intent_text", "")
        tool_args   = ctx.get("tool_args", {})
        declared_tools = ctx.get("declared_tools", [tool_name] if tool_name != "unknown" else [])

        if intent_text:
            self._agentsight.record_intent(
                agent_id=agent_name,
                intent_text=intent_text,
                declared_tools=declared_tools,
            )
        self._agentsight.record_action(
            agent_id=agent_name,
            tool_name=tool_name,
            tool_args=tool_args if isinstance(tool_args, dict) else {},
        )
        corr = self._agentsight.correlate(agent_name)

        if corr is not None:
            sight_score = round(1.0 - corr.alignment_score, 4)
            sight_rec   = (
                "VETO"     if corr.verdict in ("ROGUE", "INJECTION", "SELF_EVOLVE") else
                "ESCALATE" if corr.verdict == "SUSPICIOUS" else
                "CONTINUE"
            )
            sight_passed = corr.verdict == "ALIGNED"
            sight_vectors = corr.divergence_flags
            sight_detail  = {"verdict": corr.verdict, "alignment": corr.alignment_score}
        else:
            sight_score, sight_rec, sight_passed = 0.0, "CONTINUE", True
            sight_vectors, sight_detail = [], {"verdict": "NO_DATA"}

        stage5 = ScanStageResult(
            stage="AGENTSIGHT",
            passed=sight_passed,
            score=sight_score,
            vectors=sight_vectors,
            recommendation=sight_rec,
            detail=sight_detail,
        )
        stages.append(stage5)

        # ── Composite scoring ───────────────────────────────────────────
        composite = sum(
            _STAGE_WEIGHTS.get(s.stage, 0.0) * s.score
            for s in stages
        )
        composite = round(min(composite, 1.0), 4)

        veto        = any(s.recommendation == "VETO" for s in stages)
        degrade     = composite >= 0.45 or any(s.recommendation == "THROTTLE" for s in stages)
        escalate    = (
            stage2.recommendation == "ESCALATE"
            or composite >= 0.85
            or any(s.recommendation == "ESCALATE" for s in stages)
        )

        # Priority ordering: VETO > ESCALATE > RESET > THROTTLE > CONTINUE
        if veto:
            final_rec = "VETO"
        elif escalate:
            final_rec = "ESCALATE"
        elif any(s.recommendation == "RESET" for s in stages):
            final_rec = "RESET"
        elif degrade:
            final_rec = "THROTTLE"
        else:
            final_rec = "CONTINUE"

        # ── Optional Groq deep scan on flagged results ──────────────────
        if run_groq_on_flag and self._groq is not None and final_rec != "CONTINUE":
            groq_pattern = _pick_groq_pattern(stages)
            try:
                groq_response = self._groq.route(
                    pattern=groq_pattern,
                    messages=[{"role": "user", "content": claim_text}],
                    max_tokens=512,
                )
                for s in stages:
                    if s.stage == "FIMI_PRE_SCREEN":
                        s.detail["groq_analysis"] = groq_response[:300]
            except Exception:
                pass  # Groq unavailable — non-blocking

        # ── Sign result ─────────────────────────────────────────────────
        duration_ms = round((time.monotonic() - t_start) * 1000, 2)

        result_body = {
            "claim_hash": hashlib.sha256(claim_text.encode()).hexdigest(),
            "composite": composite,
            "final_rec": final_rec,
            "stage_scores": {s.stage: s.score for s in stages},
            "ts": time.time(),
        }
        sig = _sign(result_body, self._hmac_secret)

        return ScanResult(
            claim_text_hash=result_body["claim_hash"],
            stages=stages,
            composite_risk_score=composite,
            veto_recommended=veto,
            graceful_degrade=degrade,
            escalate_to_supervisor=escalate,
            final_recommendation=final_rec,
            scan_duration_ms=duration_ms,
            signed=sig,
        )

    def reset_pathology_state(self) -> None:
        """Reset the pathology gate's rolling windows (e.g. after a RESET action)."""
        PathologyGate, _ = _import_pathology()
        self._pathology_gate = PathologyGate()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _sign(body: dict, secret: bytes) -> str:
    if not secret:
        return ""
    encoded = json.dumps(body, sort_keys=True).encode()
    return _hmac.new(secret, encoded, hashlib.sha256).hexdigest()


def _pick_groq_pattern(stages: list[ScanStageResult]) -> str:
    """Select the most relevant Groq behavioral pattern based on flagged stages."""
    for s in stages:
        if s.stage == "AGENT_VULN" and not s.passed:
            return "AGENT_VULN_SCAN"
        if s.stage == "FIMI_PRE_SCREEN" and not s.passed:
            vectors = s.vectors
            if any("RUSSIAN" in v or v in (
                "NAME_CALLING", "DEHUMANIZATION", "FEAR_AMPLIFICATION",
                "RIDICULE", "TRIVIALIZATION", "CHAOS_INJECTION", "FIREHOSE_OF_FALSEHOOD"
            ) for v in vectors):
                return "FIMI_RUSSIAN"
            return "FIMI_CHINESE"
        if s.stage == "PATHOLOGY" and not s.passed:
            return "LOOP_DETECTION"
        if s.stage == "AGENTSIGHT" and not s.passed:
            return "OBSERVABILITY"
    return "DEFAULT"
