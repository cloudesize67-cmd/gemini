# AEGIS-NET / NOESIS — Session Handoff Document
**Last updated:** 2026-06-10  
**Branch:** `claude/aegis-cognitive-framework-ic5Jo`  
**Repo:** `github.com/cloudesize67-cmd/gemini`

---

## What This System Is

Two interlocked systems in the same repo:

| System | Location | Purpose |
|--------|----------|---------|
| **AEGIS-NET** | `aegis-net/` | Commercial governed AI swarm — hierarchical agents for code, research, security, memory, comms |
| **NOESIS** | `noesis/` + root | Counter-disinformation + AI governance — FIMI detection, stability gating, causal observability |

**Core thesis:** Safety architecture IS the product. Build defensively first, commercialise into Finance / Defense / Legal / Government — markets where governed AI is non-negotiable.

---

## Repository Structure

```
/home/user/Gemini/
├── aegis-net/                   # AEGIS-NET swarm package
│   ├── aegis_net/
│   │   ├── supervisor.py        # Opus 4.6 — ThreadPoolExecutor parallel dispatch
│   │   ├── agents/
│   │   │   ├── base.py          # VerifierAgent integration, failure memory
│   │   │   ├── team_lead.py     # Sonnet 4.6 team leads (5 teams)
│   │   │   └── workers/
│   │   │       ├── oracle.py    # Research — YouTube + NVIDIA collectors
│   │   │       ├── forge.py     # Code generation
│   │   │       ├── sentinel.py  # Security scanning
│   │   │       ├── archivist.py # Memory / ChromaDB
│   │   │       └── herald.py    # Communications
│   │   ├── config.py            # os.environ only — no .env reads
│   │   ├── secrets.py           # MissingSecretError with exact fix instructions
│   │   ├── llm_router.py        # Groq → Gemini → Haiku → Sonnet → Opus cascade
│   │   ├── trust_engine.py      # T = 0.35·acc + 0.25·rel + 0.15·spd + 0.20·safe − 0.05·anomaly
│   │   ├── experience_store.py  # Prioritized Experience Replay (SQLite, PER)
│   │   └── security.py          # SPIFFE identity, mTLS, input sanitization, circuit breaker
│   ├── start.py                 # Quick-start smoke test
│   └── requirements.txt         # anthropic, groq, litellm, chromadb, sentence-transformers...
│
├── noesis/                      # NOESIS counter-disinfo + AI governance
│   ├── agents/
│   │   ├── supervisor.py        # NOESISSupervisor — HMAC signing, Schwartz Awareness Ladder
│   │   ├── arbiter.py           # ARBITERAgent — Cialdini 7 manipulation vectors
│   │   ├── logos.py             # LOGOSAgent — Lyapunov stability gate
│   │   ├── argus.py             # ARGUSAgent — data collection
│   │   └── daedalus.py          # DAEDALUSAgent — synthesis
│   ├── supervisor/
│   │   ├── __init__.py
│   │   └── scan_hardening.py    # HardenedScanOrchestrator + handle_scan_pattern ← KEY FILE
│   ├── arbiter_fimi.py          # FIMI detector — 18 vectors, Russian + Chinese + AgentVuln
│   ├── logos_pathology.py       # PathologyGate — loop/bottleneck/runaway detectors
│   ├── supervisor_aae.py        # AAE governance — HMAC-signed authorization envelopes
│   ├── agentsight.py            # Causal intent↔action correlation — 5 verdicts
│   ├── groq_router.py           # Behavioral pattern router — 12 patterns, Groq models
│   ├── supervisor_groq.py       # NOESISSupervisorGroq — LiteLLM failover + BRA state
│   ├── litellm_config.yaml      # LiteLLM proxy config — 8 model entries, Anthropic→Groq
│   ├── pipeline.py              # NOESIS pipeline
│   └── server.py                # FastAPI server
│
├── .github/workflows/
│   ├── deploy.yml               # Main CI — syntax check + Railway deploy
│   └── noesis-deploy.yml        # NOESIS CI — 4-job pipeline with Groq secrets
│
├── requirements.txt             # Root: anthropic, litellm, groq, openai, pyyaml...
├── .gitignore                   # Blocks .env, *.db, __pycache__, audit logs
└── AEGIS_SESSION_HANDOFF.md     # This file
```

---

## AEGIS-NET Architecture

### Agent Hierarchy
```
SUPERVISOR (Opus 4.6) — one LLM call per goal for HTN decomposition
    ↓ ThreadPoolExecutor(max_workers=5) — parallel dispatch
    ├── FORGE Team Lead (Sonnet 4.6) → Haiku workers — code generation
    ├── ORACLE Team Lead (Sonnet 4.6) → Haiku/Groq workers — research
    ├── SENTINEL Team Lead (Sonnet 4.6) → Haiku workers — security
    ├── ARCHIVIST Team Lead (Sonnet 4.6) → Haiku workers — memory
    └── HERALD Team Lead (Sonnet 4.6) → Haiku/Groq workers — comms
```

### LLM Routing (cost cascade)
```
Groq (free, 30 RPM) → Gemini (free, 1000/day) → Haiku (cheap) → Sonnet → Opus
```

### Trust Formula
```
T = 0.35·accuracy + 0.25·reliability + 0.15·speed + 0.20·safety − 0.05·anomaly_score
Tiers: PROBATIONARY (<40) → OPERATIVE (40-65) → TRUSTED (65-85) → ELITE (>85)
```

### Key Design Decisions
- **No .env files ever.** Keys live in GitHub Secrets + Railway Variables only.
- **VerifierAgent:** Every task checks ChromaDB failure memory before executing (SentenceTransformer `all-MiniLM-L6-v2`, cosine similarity > 0.55 = warning).
- **SecurityLayer:** SPIFFE RSA-2048 identity per agent, input sanitization (ASI01/02), CoT drift verifier, exfiltration detector, circuit breaker.
- **PER:** SQLite experience store, priority = (|td_error| + ε)^0.6.

---

## NOESIS Architecture

### Core Detection Pipeline
```
Input text
    ↓
1. FIMI Pre-Screen (regex, 0ms) — 18 vectors across Russian/Chinese/AgentVuln families
    ↓
2. Agent-Vuln Gate — PROMPT_INJECTION, GOAL_HIJACKING, SYCOPHANCY_INDUCTION etc.
    ↓
3. Pathology Gate — loop detection (3-in-10), bottleneck (>15 retries/60s), runaway (>3x context)
    ↓
4. AAE Authorization — HMAC-signed dispatch envelopes, mandate/constraints/validity
    ↓
5. AgentSight — causal intent↔action correlation → ALIGNED/SUSPICIOUS/ROGUE/INJECTION/SELF_EVOLVE
    ↓
ScanResult: composite_risk_score, veto_recommended, HMAC-signed
```

### Stage Weights (composite score)
| Stage | Weight | Rationale |
|-------|--------|-----------|
| AGENT_VULN | 0.30 | Injection is highest-priority threat |
| AGENTSIGHT | 0.20 | Behavioral divergence is critical |
| FIMI_PRE_SCREEN | 0.20 | Content-level threat |
| AAE_AUTH | 0.15 | Authorization control |
| PATHOLOGY | 0.15 | System stability |

### Recommendation Priority
```
VETO > ESCALATE > RESET > THROTTLE > CONTINUE
```

### Graceful Degradation Levels (BRA)
| Level | Anomaly Score | Agency | Autonomy |
|-------|--------------|--------|----------|
| FULL | ≤ 0.40 | 1.0 | 1.0 |
| RESTRICTED | 0.40–0.65 | 0.7 | 0.5 |
| SUPERVISED | 0.65–0.85 | 0.4 | 0.2 |
| SAFE_MODE | > 0.85 | 0.1 | 0.0 (read-only) |

### Key Import (works from `noesis/` directory)
```python
from supervisor.scan_hardening import (
    HardenedScanOrchestrator,
    handle_scan_pattern,
)
```

### Groq Router — 12 Behavioral Patterns
Security: `FIMI_RUSSIAN`, `FIMI_CHINESE`, `AGENT_VULN_SCAN`, `LOOP_DETECTION`, `OBSERVABILITY`, `GRACEFUL_DEGRADE`  
Agent roles: `ORCHESTRATION`, `EXTRACTION`, `MANIPULATION_SCAN`, `STABILITY_GATE`, `SYNTHESIS`, `DEFAULT`

---

## Secrets Required (GitHub Secrets + Railway Variables)

| Secret | Required | Purpose |
|--------|----------|---------|
| `ANTHROPIC_API_KEY` | **CRITICAL** | All Claude model calls |
| `GROQ_API_KEY` | High | Groq fallback + behavioral router |
| `NOESIS_HMAC_SECRET` | High | Output signing (generate: `python3 -c "import secrets; print(secrets.token_hex(32))"`) |
| `LITELLM_MASTER_KEY` | Medium | LiteLLM proxy auth |
| `RAILWAY_TOKEN` | Deploy | Railway CI/CD |
| `YOUTUBE_API_KEY` | Optional | YouTube Data API v3 for ORACLE |

**Add at:** `github.com/cloudesize67-cmd/gemini/settings/secrets/actions`

**SECURITY NOTE:** A previous API key (`sk-ant-api03-...-72MAAA`) was exposed in chat and must be rotated at `console.anthropic.com/settings/keys`.

---

## Deployment Status

| Component | Status |
|-----------|--------|
| AEGIS-NET core package | Built, not deployed (needs secrets) |
| NOESIS agents (5) | Built, syntax-verified |
| FIMI detector | Built + tested |
| Pathology gate | Built + tested |
| AAE governance | Built + tested |
| AgentSight | Built + tested |
| Groq router (12 patterns) | Built + tested |
| LiteLLM failover config | Built |
| HardenedScanOrchestrator | Built + tested (0.22ms clean path) |
| CI/CD pipeline | Built (triggers on push to branch) |
| Railway deploy | **Blocked — needs secrets added** |

---

## What To Build Next (Priority Order)

1. **`noesis/audit_ledger.py`** — append-only HMAC-chained SQLite log of every agent decision. Unlocks Finance / Defense / Legal / Government procurement. Single highest-leverage component.

2. **`noesis/red_team.py`** — automated OWASP LLM Top 10 injection probe suite. Runs in CI before deploy. Required for Defense/Government contracts.

3. **`--local-only` mode** — route all LLM calls to Groq/local models, remove Anthropic from data path. Required for Legal privilege protection and air-gapped Defense deployments.

4. **Explainability reports** — per-decision reasoning chain export (not just verdict — full chain). Required for EO 14110 compliance (Government market).

---

## How To Continue In A New Session

1. Read this file first: `cat /home/user/Gemini/AEGIS_SESSION_HANDOFF.md`
2. Check current branch: `git -C /home/user/Gemini log --oneline -5`
3. Run smoke tests: `cd /home/user/Gemini/noesis && python3 -c "from supervisor.scan_hardening import HardenedScanOrchestrator; print('OK')"`
4. Continue building from the **What To Build Next** list above.

---

## Cross-Session Research Notes

- Architecture grounded in arXiv papers: TAO supervisor mechanisms, Contextual Confidence Scoring, ODAR adaptive routing, SIMA-2 self-improvement, Oversight Game alignment guarantees.
- Year-long prior research thread with Grok (March 2025–March 2026) cross-validated ideas across multiple AI systems — intentional triangulation methodology.
- OWASP Agentic AI Top 10 and NIST Cyber AI Profile are the compliance frameworks embedded in the security layer.
- The competitive gap: nobody delivers a complete governed intelligence cycle (safety + capability + audit trail) as a single deployable product. That is the moat.
