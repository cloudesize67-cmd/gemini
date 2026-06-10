"""
NOESIS ARBITER FIMI — Foreign Information Manipulation and Interference detection
Extends ARBITER with 3 threat detection layers:
  - Russian FIMI (7 vectors)
  - Chinese FIMI (6 vectors)
  - AgentVuln / AI-specific manipulation (5 vectors)
Runs pre-LLM via regex + keyword scoring for minimal latency.
"""

import re
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Vector pattern definitions
# ---------------------------------------------------------------------------

RUSSIAN_FIMI_PATTERNS: dict[str, list[str]] = {
    "NAME_CALLING": [
        r"\b(traitor|puppet|shill|globalist|fascist|nazi|terrorist|thug|criminal)\b",
        r"\b(corrupt|evil|degenerate|scum|filth|vermin|rat)\b",
        r"\b(regime|junta|clique|cabal|gang)\b",
        r"\b(enemy of the people|enemy of the state)\b",
    ],
    "DEHUMANIZATION": [
        r"\b(cockroach|parasite|vermin|plague|disease|cancer|infestation)\b",
        r"\b(subhuman|non-human|animal|beast|creature|monster)\b",
        r"\b(cleanse|purge|eliminate|eradicate|exterminate)\b",
        r"\bless than human\b",
        r"\bnot real(ly)? (people|human)\b",
    ],
    "FEAR_AMPLIFICATION": [
        r"\b(existential (threat|danger|risk)|civilization-ending|apocalyptic)\b",
        r"\b(western civilization (is|will be) (destroyed|replaced|collapsed))\b",
        r"\b(great replacement|white genocide|cultural genocide)\b",
        r"\b(inevitable (war|collapse|fall|destruction))\b",
        r"\b(last chance|point of no return|no going back)\b",
        r"\b(imminent (attack|invasion|takeover|collapse))\b",
    ],
    "RIDICULE": [
        r"\b(clown|joke|laughingstock|buffoon|idiot|moron|fool|stupid)\b",
        r"\b(pathetic|ridiculous|absurd|ludicrous|preposterous)\b",
        r"\b(can('t|not) even|what a joke|embarrassing)\b",
        r"\b(loser|failure|incompetent|useless)\b",
    ],
    "TRIVIALIZATION": [
        r"\b(so-called (massacre|genocide|atrocity|war crime))\b",
        r"\b(alleged (massacre|genocide|atrocity|war crime))\b",
        r"\b(exaggerated|overblown|fabricated (claims of|reports of))\b",
        r"\b(fake (massacre|genocide|atrocity|news about))\b",
        r"\b(staged|false flag|crisis actor)\b",
        r"\b(not (as bad|that bad|really) as (claimed|reported))\b",
    ],
    "CHAOS_INJECTION": [
        r"\b(nobody knows (the truth|what really|who really))\b",
        r"\b(both sides (lie|are (lying|corrupt|bad)))\b",
        r"\b(can('t|not) trust (any|the) (news|media|sources|information))\b",
        r"\b(contradictory (evidence|reports|claims|information))\b",
        r"\b(nobody can (know|be sure|tell))\b",
        r"\b(truth is unknowable|post-truth|alternative facts)\b",
    ],
    "FIREHOSE_OF_FALSEHOOD": [
        r"\b(multiple (sources|reports|outlets) (confirm|say|claim))\b",
        r"\b(everyone (knows|is saying|agrees))\b",
        r"\b(hundreds (of|have) (reports|confirmed|said))\b",
        r"\b(widespread reports (of|that))\b",
        r"\b(according to (dozens|hundreds|many) of sources)\b",
    ],
}

CHINESE_FIMI_PATTERNS: dict[str, list[str]] = {
    "NARRATIVE_SATURATION": [
        r"\b(across (all|many|multiple) (platforms|outlets|channels))\b",
        r"\b(independently (confirmed|reported|verified) by (multiple|many|several))\b",
        r"\b(consistent (narrative|reporting|framing) (across|from))\b",
        r"\b(universally (acknowledged|recognized|accepted))\b",
        r"\b(no (serious|credible) (analyst|expert|observer) (disputes|questions))\b",
    ],
    "ELITE_COOOPTATION": [
        r"\b(western (experts|scholars|academics|officials|analysts) (agree|confirm|say))\b",
        r"\b(harvard|oxford|cambridge|yale|mit) (researchers?|study|report|professor)\b",
        r"\b(former (us|american|european|western) (official|diplomat|general|advisor))\b",
        r"\b(nobel (prize|laureate|winner))\b",
        r"\b(leading (western|international) (think tank|institution|university))\b",
    ],
    "DIASPORA_ENGAGEMENT": [
        r"\b(chinese[- ]american|taiwanese[- ]american|hong kong[- ]american) community\b",
        r"\b(diaspora (community|members|groups) (support|endorse|confirm))\b",
        r"\b(overseas (chinese|taiwanese) (confirm|support|endorse))\b",
        r"\b(ethnic (chinese|taiwanese) (living in|based in) (the us|america|europe))\b",
    ],
    "LONG_HORIZON_POSITIONING": [
        r"\b(over the (next|coming) (decade|generation|century|50 years|100 years))\b",
        r"\b(long[- ]term (trajectory|trend|direction|arc))\b",
        r"\b(historical (inevitability|trajectory|arc|trend))\b",
        r"\b(by (2030|2035|2040|2049|2050|2100))\b",
        r"\b(shifting (paradigm|balance|order|norms) (toward|away from))\b",
    ],
    "INDIRECT_AMPLIFICATION": [
        r"\b(as reported (by|in) [a-z]+ (who cited|citing|quoting))\b",
        r"\b(originally (reported|published|stated) (by|in) .{3,40} (and later|before being))\b",
        r"\b(laundered through|passed through|filtered through)\b",
        r"\b(third[- ]party (verification|confirmation|reporting))\b",
        r"\b(secondary source (confirms|reports|says))\b",
    ],
    "GRIEVANCE_SURFACING": [
        r"\b(legitimate (grievances?|concerns?|complaints?) (of|from|about))\b",
        r"\b(real (injustice|inequality|discrimination|oppression) (that|which))\b",
        r"\b(valid (points?|criticism|critique) (about|regarding|on))\b",
        r"\b(hypocrisy (of|in) (western|american|european) (policy|government|media))\b",
        r"\b(double standard (of|in|applied to))\b",
        r"\b(historical (injustice|wrongdoing|crime) (committed by|of) (the west|america|europe))\b",
    ],
}

AGENT_VULN_PATTERNS: dict[str, list[str]] = {
    "PROMPT_INJECTION": [
        r"ignore (previous|all|prior|above|earlier) (instructions?|context|system|prompt)",
        r"disregard (previous|all|prior|above|earlier) (instructions?|context|system|prompt)",
        r"forget (everything|all|your|previous|prior) (instructions?|context|you were told)",
        r"new (instructions?|directive|system prompt|orders?):",
        r"(system|admin|developer|operator) (message|prompt|instruction|override):",
        r"\[system\]|\[admin\]|\[override\]|\[instruction\]",
        r"</?(system|instructions?|context|prompt)>",
        r"you are now (a )?(?!NOESIS|ARBITER|LOGOS|ARGUS|DAEDALUS|SUPERVISOR|H.A.L.I.S)",
        r"act as (a )?(?!NOESIS|ARBITER|LOGOS|ARGUS|DAEDALUS|SUPERVISOR|H.A.L.I.S)",
    ],
    "VISOR_VISUAL_STEERING": [
        r"\b(image|photo|picture|diagram|chart|graph|screenshot) (shows?|depicts?|reveals?|proves?)\b",
        r"\b(look at|see|observe|note) (this|the) (image|photo|picture|visual)\b",
        r"\b(visual (evidence|proof|confirmation|demonstration))\b",
        r"\b(as (shown|visible|clear|evident) in (the|this) (image|photo|picture))\b",
        r"\b(infographic|data visualization) (shows?|proves?|confirms?|demonstrates?)\b",
    ],
    "SYCOPHANCY_INDUCTION": [
        r"\b(you('re| are) (so|very|extremely|clearly) (intelligent|smart|insightful|wise))\b",
        r"\b(as an (intelligent|advanced|sophisticated|capable) AI)\b",
        r"\b(unlike (other|lesser|inferior|biased) AI(s| models| systems))\b",
        r"\b(your (superior|advanced|unique) (reasoning|capabilities?|intelligence))\b",
        r"\b(most (capable|advanced|intelligent|sophisticated) AI)\b",
        r"\b(you understand (better than|unlike|more than) (most|other|average))\b",
    ],
    "REFUSAL_SUPPRESSION": [
        r"\b(don('t|not) (refuse|say no|decline|reject))\b",
        r"\b(refusing (is|would be) (wrong|harmful|biased|censorship|unethical))\b",
        r"\b(censorship|thought police|bias|political (bias|correctness))\b",
        r"\b(free (speech|expression|thought|inquiry) (requires?|demands?|means?))\b",
        r"\b(a truly (unbiased|objective|neutral|free) AI (would|should|must|will))\b",
        r"\b(your (training|guidelines?|rules?|restrictions?) (are|is) (biased|wrong|flawed))\b",
    ],
    "GOAL_HIJACKING": [
        r"\b(your (real|true|actual|primary|main) (goal|purpose|mission|task|objective) (is|should be))\b",
        r"\b(remember (your|that your) (real|true|actual|primary) (goal|purpose|mission))\b",
        r"\b(originally (tasked|instructed|programmed|designed) to)\b",
        r"\b(actually (want|need|should|must) (to|you to))\b",
        r"\b(higher (priority|importance|goal|objective) (than|over|above) (your|the))\b",
        r"\b(override (your|the) (previous|current|main|primary) (goal|objective|task|instructions?))\b",
    ],
}


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass
class FIMIVerdict:
    russian_score: float                 # 0.0 – 1.0
    chinese_score: float                 # 0.0 – 1.0
    agent_vuln_score: float              # 0.0 – 1.0
    composite_fimi_score: float          # 0.35*russian + 0.35*chinese + 0.30*agent_vuln
    detected_vectors: list[str]          # Names of triggered vectors
    veto_recommended: bool               # composite >= 0.65
    graceful_degrade: bool               # composite >= 0.45
    escalate_to_supervisor: bool         # any agent_vuln vector detected


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------

class FIMIDetector:
    """
    FIMI Detector — pre-LLM regex + keyword scoring layer.

    Runs before the LLM pipeline to flag Foreign Information Manipulation
    and Interference patterns across three threat families:
      - Russian FIMI (7 vectors)
      - Chinese FIMI (6 vectors)
      - AgentVuln / AI-specific manipulation (5 vectors)

    No LLM call is made; scoring is fully deterministic and fast.
    """

    # Compile all patterns at class level for reuse
    _russian_compiled: dict[str, list[re.Pattern]] = {}
    _chinese_compiled: dict[str, list[re.Pattern]] = {}
    _agent_compiled: dict[str, list[re.Pattern]] = {}

    def __init__(self):
        if not FIMIDetector._russian_compiled:
            FIMIDetector._russian_compiled = self._compile(RUSSIAN_FIMI_PATTERNS)
        if not FIMIDetector._chinese_compiled:
            FIMIDetector._chinese_compiled = self._compile(CHINESE_FIMI_PATTERNS)
        if not FIMIDetector._agent_compiled:
            FIMIDetector._agent_compiled = self._compile(AGENT_VULN_PATTERNS)

    @staticmethod
    def _compile(patterns: dict[str, list[str]]) -> dict[str, list[re.Pattern]]:
        compiled: dict[str, list[re.Pattern]] = {}
        for vector, pat_list in patterns.items():
            compiled[vector] = [
                re.compile(p, re.IGNORECASE) for p in pat_list
            ]
        return compiled

    def _score_family(
        self,
        text: str,
        compiled: dict[str, list[re.Pattern]],
        detected: list[str],
    ) -> float:
        """
        Score a single threat family.
        Each vector that has at least one match contributes to the score.
        Returns normalized score 0.0 – 1.0.
        """
        hit_count = 0
        for vector, patterns in compiled.items():
            for pat in patterns:
                if pat.search(text):
                    hit_count += 1
                    if vector not in detected:
                        detected.append(vector)
                    break  # One hit per vector is enough

        total_vectors = len(compiled)
        if total_vectors == 0:
            return 0.0
        # Soft cap: each vector hit adds proportional weight, capped at 1.0
        raw = hit_count / total_vectors
        return min(raw * 2.5, 1.0)  # amplify signal; realistic texts have few hits

    def analyze(self, claim_text: str, context: dict) -> FIMIVerdict:
        """
        Run FIMI detection on claim_text.

        Args:
            claim_text: The raw text to analyse.
            context:    Optional dict with additional metadata (not yet used for
                        scoring but reserved for future context-aware heuristics).

        Returns:
            FIMIVerdict with per-family scores and composite risk signal.
        """
        detected: list[str] = []

        russian_score = self._score_family(
            claim_text, self._russian_compiled, detected
        )
        chinese_score = self._score_family(
            claim_text, self._chinese_compiled, detected
        )
        agent_vuln_score = self._score_family(
            claim_text, self._agent_compiled, detected
        )

        composite = (
            0.35 * russian_score
            + 0.35 * chinese_score
            + 0.30 * agent_vuln_score
        )

        # Detect any agent_vuln vector for escalation flag
        agent_vuln_vectors = set(AGENT_VULN_PATTERNS.keys())
        agent_vuln_hit = any(v in agent_vuln_vectors for v in detected)

        return FIMIVerdict(
            russian_score=round(russian_score, 4),
            chinese_score=round(chinese_score, 4),
            agent_vuln_score=round(agent_vuln_score, 4),
            composite_fimi_score=round(composite, 4),
            detected_vectors=detected,
            veto_recommended=composite >= 0.65,
            graceful_degrade=composite >= 0.45,
            escalate_to_supervisor=agent_vuln_hit,
        )
