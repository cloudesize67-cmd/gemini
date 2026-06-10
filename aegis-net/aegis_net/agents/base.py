from __future__ import annotations
import uuid, time
from dataclasses import dataclass, field
from ..trust_engine import TrustMetrics, compute_trust, tier
from ..experience_store import get_store, ExperienceEntry
from .. import llm_router
from .. import config as cfg

SKILL_DIMS = ["reasoning","coding","research","communication",
              "security","planning","memory","tool_use","creativity","reliability"]

@dataclass
class BaseAgent:
    role:         str
    team:         str
    agent_id:     str          = field(default_factory=lambda: str(uuid.uuid4())[:8])
    skill_vector: dict         = field(default_factory=lambda: {d:0.5 for d in SKILL_DIMS})
    trust_score:  float        = 50.0
    metrics:      TrustMetrics = field(default_factory=TrustMetrics)
    _backend:     str = field(default="", init=False, repr=False)
    _model:       str = field(default="", init=False, repr=False)

    def __post_init__(self):
        self._backend, self._model = llm_router.best_backend_for_tier(self.trust_score)

    def run(self, task: str, context: str = "", tools_hint=None) -> dict:
        store = get_store()
        self.metrics.tasks_assigned += 1
        start = time.monotonic()
        try:
            result_text = llm_router.chat(
                [{"role":"user","content":f"{context}\n\nTASK: {task}".strip()}],
                model=self._model, system=self._system_prompt(),
                backend=self._backend, max_tokens=2048)
            elapsed = time.monotonic() - start
            self.metrics.tasks_completed  += 1
            self.metrics.tasks_correct    += 1
            self.metrics.total_time_ratio += min(elapsed/30.0, 1.0)
            store.add(ExperienceEntry(agent_id=self.agent_id, domain=self.team,
                task_description=task, outcome="success", reward=1.0, td_error=0.3))
            self._refresh_trust()
            return {"status":"success","result":result_text,"output":result_text,
                    "agent_id":self.agent_id,"trust":self.trust_score,"tier":tier(self.trust_score),"backend":self._backend}
        except Exception as exc:
            self.metrics.anomaly_count += 1
            store.add(ExperienceEntry(agent_id=self.agent_id, domain=self.team,
                task_description=task, outcome="failure", reward=-0.5, td_error=1.0))
            self._refresh_trust()
            return {"status":"error","error":str(exc),"output":"",
                    "agent_id":self.agent_id,"trust":self.trust_score,"tier":tier(self.trust_score),"backend":self._backend}

    def _refresh_trust(self):
        self.trust_score = compute_trust(self.metrics)
        self._backend, self._model = llm_router.best_backend_for_tier(self.trust_score)

    def _system_prompt(self):
        return (f"You are {self.role} on the {self.team} team of Aegis.net.\n"
                f"Trust tier: {tier(self.trust_score)} ({self.trust_score:.1f}/100).\n"
                "Execute tasks precisely. Report results clearly. Never hallucinate.")

    @property
    def info(self):
        return {"agent_id":self.agent_id,"role":self.role,"team":self.team,
                "trust_score":round(self.trust_score,1),"tier":tier(self.trust_score),
                "backend":self._backend,"model":self._model}
