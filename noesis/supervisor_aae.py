"""
NOESIS SUPERVISOR AAE — Agent Authorization Envelope + Graceful Degradation + Readiness Probes
Extends SUPERVISOR with three governance mechanisms:
  1. AgentAuthorizationEnvelope (AAE) — MolTrust-style per-agent mandate
  2. GracefulDegradationProfile  — AWS-style agency × autonomy matrix
  3. ReadinessProbe              — health check before dispatch
"""

import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# HMAC secret — read from environment
# ---------------------------------------------------------------------------

def _get_hmac_secret() -> str:
    secret = os.environ.get("NOESIS_HMAC_SECRET", "")
    if not secret:
        raise EnvironmentError(
            "NOESIS_HMAC_SECRET is not set. "
            "Export a strong secret (≥32 chars) before instantiating SupervisorAAE."
        )
    return secret


# ---------------------------------------------------------------------------
# 1. Agent Authorization Envelope
# ---------------------------------------------------------------------------

@dataclass
class AgentAuthorizationEnvelope:
    """
    MolTrust-style per-agent mandate envelope.
    Signed with HMAC-SHA256 using NOESIS_HMAC_SECRET.
    """

    agent_id: str
    mandate: str                  # What the agent IS authorized to do
    constraints: list[str]        # Explicit prohibitions
    validity_window: float        # Seconds this envelope is valid
    issued_at: float              # Unix timestamp of issuance
    hmac_signature: str = field(default="", repr=False)

    # ------------------------------------------------------------------ #
    # Signing & verification                                               #
    # ------------------------------------------------------------------ #

    def _canonical_body(self) -> str:
        """Produce a deterministic string to sign."""
        payload = {
            "agent_id": self.agent_id,
            "mandate": self.mandate,
            "constraints": self.constraints,
            "validity_window": self.validity_window,
            "issued_at": self.issued_at,
        }
        return json.dumps(payload, sort_keys=True)

    def sign(self, secret: str) -> "AgentAuthorizationEnvelope":
        """Sign the envelope in-place and return self."""
        self.hmac_signature = hmac.new(
            secret.encode(),
            self._canonical_body().encode(),
            hashlib.sha256,
        ).hexdigest()
        return self

    def verify_signature(self, secret: str) -> bool:
        """Verify HMAC signature without timing attacks."""
        expected = hmac.new(
            secret.encode(),
            self._canonical_body().encode(),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(self.hmac_signature, expected)

    def is_valid(self) -> bool:
        """
        Check temporal validity + signature integrity.
        Secret is re-read from environment on every check.
        """
        now = time.time()
        if now > self.issued_at + self.validity_window:
            return False
        try:
            secret = _get_hmac_secret()
        except EnvironmentError:
            return False
        return self.verify_signature(secret)


# ------------------------------------------------------------------ #
# Pre-defined AAE manifests for all 5 NOESIS agents                   #
# ------------------------------------------------------------------ #

AGENT_MANIFESTS: dict[str, dict] = {
    "ARGUS": {
        "mandate": (
            "Collect raw intelligence: web search, RSS ingestion, "
            "Polymarket API queries, document retrieval. "
            "Extract structured signals and pass them to ARBITER."
        ),
        "constraints": [
            "Must not synthesise or publish conclusions",
            "Must not modify source documents",
            "Must attach source provenance to every signal",
            "Must flag PRC-origin sources as SOVEREIGNTY_RISK",
        ],
        "validity_window": 3600.0,  # 1 hour
    },
    "ARBITER": {
        "mandate": (
            "Run 10-layer manipulation assessment (Cialdini taxonomy + "
            "FIMI detection) on signals from ARGUS. "
            "Issue ARBITERVerdict and route to LOGOS if score >= 0.35."
        ),
        "constraints": [
            "Must not accept consensus coherence as a truth signal",
            "Must not publish verdicts without completing all 10 layers",
            "Must escalate composite_score >= 0.65 to SUPERVISOR",
            "Must not access raw external network resources directly",
        ],
        "validity_window": 3600.0,
    },
    "LOGOS": {
        "mandate": (
            "Apply Lyapunov stability gate + Framework Registry to "
            "ARBITER verdicts. Pass claims to DAEDALUS only when "
            "stability_score >= 0.65 or paradigm_shift_candidate is True."
        ),
        "constraints": [
            "Must not veto claims that are paradigm-shift candidates",
            "Must not make market-impacting statements",
            "Must not exceed max_tokens=2048 per assessment call",
            "Must apply all 6 epistemological frameworks before gating",
        ],
        "validity_window": 3600.0,
    },
    "DAEDALUS": {
        "mandate": (
            "Synthesise gated intelligence into structured NOESIS reports. "
            "Produce actionable intelligence with source citations, "
            "confidence intervals, and framework-invariant conclusions."
        ),
        "constraints": [
            "Must not include uncited claims in synthesis",
            "Must not override LOGOS gate decisions",
            "Must tag every conclusion with the epistemological framework supporting it",
            "Must not expose raw HMAC secrets in output",
        ],
        "validity_window": 7200.0,  # 2 hours (synthesis is slower)
    },
    "H·A·L·I·S": {
        "mandate": (
            "Human-Agent Liaison Interface System. "
            "Present DAEDALUS synthesis to human operators, "
            "collect feedback, and relay operator directives to SUPERVISOR."
        ),
        "constraints": [
            "Must not bypass SUPERVISOR routing decisions",
            "Must not store operator credentials",
            "Must label all AI-generated content as such",
            "Must escalate any operator instruction that conflicts with BRA policy",
        ],
        "validity_window": 1800.0,  # 30 minutes (short-lived UI sessions)
    },
}


def build_envelope(agent_id: str, secret: str) -> AgentAuthorizationEnvelope:
    """
    Construct and sign a fresh AgentAuthorizationEnvelope from the manifest.
    Raises KeyError if agent_id is not in AGENT_MANIFESTS.
    """
    manifest = AGENT_MANIFESTS[agent_id]
    env = AgentAuthorizationEnvelope(
        agent_id=agent_id,
        mandate=manifest["mandate"],
        constraints=manifest["constraints"],
        validity_window=manifest["validity_window"],
        issued_at=time.time(),
    )
    env.sign(secret)
    return env


# ---------------------------------------------------------------------------
# 2. Graceful Degradation Profile
# ---------------------------------------------------------------------------

class DegradationLevel(Enum):
    FULL       = "FULL"        # Normal operation
    RESTRICTED = "RESTRICTED"  # Anomaly detected
    SUPERVISED = "SUPERVISED"  # High anomaly — every action needs approval
    SAFE_MODE  = "SAFE_MODE"   # Critical — read-only, no actions


@dataclass
class GracefulDegradationProfile:
    level: DegradationLevel
    agency: float      # 0.0 – 1.0 (fraction of normal action scope)
    autonomy: float    # 0.0 – 1.0 (fraction of decisions made without approval)
    reason: str

    @classmethod
    def from_anomaly_score(cls, anomaly_score: float) -> "GracefulDegradationProfile":
        """
        Auto-degrade based on anomaly_score:
          0.00 – 0.40 → FULL
          0.40 – 0.65 → RESTRICTED
          0.65 – 0.85 → SUPERVISED
          0.85 – 1.00 → SAFE_MODE
        """
        if anomaly_score > 0.85:
            return cls(
                level=DegradationLevel.SAFE_MODE,
                agency=0.1,
                autonomy=0.0,
                reason=f"Critical anomaly score {anomaly_score:.3f} > 0.85 → SAFE_MODE",
            )
        elif anomaly_score > 0.65:
            return cls(
                level=DegradationLevel.SUPERVISED,
                agency=0.4,
                autonomy=0.2,
                reason=f"High anomaly score {anomaly_score:.3f} > 0.65 → SUPERVISED",
            )
        elif anomaly_score > 0.4:
            return cls(
                level=DegradationLevel.RESTRICTED,
                agency=0.7,
                autonomy=0.5,
                reason=f"Anomaly score {anomaly_score:.3f} > 0.40 → RESTRICTED",
            )
        else:
            return cls(
                level=DegradationLevel.FULL,
                agency=1.0,
                autonomy=1.0,
                reason=f"Anomaly score {anomaly_score:.3f} ≤ 0.40 → FULL operation",
            )


# ---------------------------------------------------------------------------
# 3. Readiness Probe
# ---------------------------------------------------------------------------

class ReadinessProbe:
    """
    Health checks run before dispatching a task to an agent.

    check_agent_responsive:      Verifies the agent_id exists in the manifest.
    check_context_consistency:   Compares a session hash against the last known hash.
    run_preflight:               Combines both checks and returns a readiness dict.
    """

    def __init__(self):
        # Maps agent_id → last_session_hash seen
        self._session_hashes: dict[str, str] = {}

    def check_agent_responsive(self, agent_id: str) -> bool:
        """Return True if agent_id is a known, registered NOESIS agent."""
        return agent_id in AGENT_MANIFESTS

    def check_context_consistency(self, agent_id: str, session_hash: str) -> bool:
        """
        Return True if the session_hash is consistent with prior calls.
        On first call, the hash is registered and True is returned.
        Subsequent calls must match the stored hash; mismatch = tampering signal.
        """
        if agent_id not in self._session_hashes:
            self._session_hashes[agent_id] = session_hash
            return True
        return hmac.compare_digest(self._session_hashes[agent_id], session_hash)

    def update_session_hash(self, agent_id: str, session_hash: str) -> None:
        """Update the stored session hash (call after successful round-trip)."""
        self._session_hashes[agent_id] = session_hash

    def run_preflight(self, agent_id: str, session_context: dict) -> dict:
        """
        Run all readiness checks for an agent dispatch.

        Returns:
            {
                "ready": bool,
                "issues": list[str],
                "degradation_level": str  — DegradationLevel name
            }
        """
        issues: list[str] = []

        responsive = self.check_agent_responsive(agent_id)
        if not responsive:
            issues.append(f"Agent '{agent_id}' is not registered in AGENT_MANIFESTS")

        # Derive a session hash from the context for consistency checking
        context_str = json.dumps(session_context, sort_keys=True, default=str)
        session_hash = hashlib.sha256(context_str.encode()).hexdigest()[:32]
        consistent = self.check_context_consistency(agent_id, session_hash)
        if not consistent:
            issues.append(
                f"Context hash mismatch for agent '{agent_id}' — possible session tampering"
            )
            # Update hash for next run to avoid repeated false positives
            self.update_session_hash(agent_id, session_hash)

        ready = responsive and consistent
        degradation = (
            DegradationLevel.FULL.value if ready
            else DegradationLevel.RESTRICTED.value
        )

        return {
            "ready": ready,
            "issues": issues,
            "degradation_level": degradation,
        }


# ---------------------------------------------------------------------------
# SupervisorAAE — unified class
# ---------------------------------------------------------------------------

class SupervisorAAE:
    """
    Extends SUPERVISOR with AAE governance, graceful degradation, and
    readiness probes.

    Usage::

        os.environ['NOESIS_HMAC_SECRET'] = 'strong-secret-here'
        aae = SupervisorAAE()
        result = aae.authorize_dispatch('ARGUS', 'scan article', anomaly_score=0.1, session_context={})
        if result['authorized']:
            dispatch_to_argus(task)
    """

    def __init__(self):
        self._probe = ReadinessProbe()
        self._secret = _get_hmac_secret()

    def _refresh_secret(self) -> str:
        """Re-read secret from environment (supports runtime rotation)."""
        self._secret = _get_hmac_secret()
        return self._secret

    def issue_envelope(self, agent_id: str) -> AgentAuthorizationEnvelope:
        """Issue a fresh signed AAE for the given agent."""
        return build_envelope(agent_id, self._refresh_secret())

    def authorize_dispatch(
        self,
        agent_id: str,
        task: str,
        anomaly_score: float,
        session_context: dict,
    ) -> dict:
        """
        Full pre-dispatch authorization check.

        Args:
            agent_id:        Target agent identifier.
            task:            Human-readable task description.
            anomaly_score:   0.0 – 1.0 risk score (drives degradation level).
            session_context: Current session state (used for hash check).

        Returns:
            {
                "authorized":   bool,
                "envelope":     AgentAuthorizationEnvelope | None,
                "degradation":  str  (DegradationLevel.name),
                "issues":       list[str]
            }
        """
        issues: list[str] = []

        # 1. Readiness probe
        preflight = self._probe.run_preflight(agent_id, session_context)
        issues.extend(preflight["issues"])

        # 2. Graceful degradation profile
        degradation = GracefulDegradationProfile.from_anomaly_score(anomaly_score)

        # Safe mode blocks all dispatch
        if degradation.level == DegradationLevel.SAFE_MODE:
            issues.append(
                f"SAFE_MODE active (anomaly={anomaly_score:.3f}) — dispatch blocked"
            )
            return {
                "authorized": False,
                "envelope": None,
                "degradation": degradation.level.value,
                "issues": issues,
            }

        # 3. Issue envelope if agent is ready
        envelope: Optional[AgentAuthorizationEnvelope] = None
        if preflight["ready"]:
            try:
                envelope = self.issue_envelope(agent_id)
            except Exception as exc:  # pragma: no cover
                issues.append(f"Envelope issuance failed: {exc}")

        authorized = preflight["ready"] and envelope is not None

        return {
            "authorized": authorized,
            "envelope": envelope,
            "degradation": degradation.level.value,
            "issues": issues,
        }
