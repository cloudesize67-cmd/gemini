from __future__ import annotations
import json, uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from .agents.team_lead import TeamLead
from .agents.workers   import ForgeWorker, OracleWorker, SentinelWorker, ArchivistWorker, HeraldWorker
from .trust_engine     import tier
from .experience_store import get_store
from . import llm_router
from . import config as cfg

class Supervisor:
    def __init__(self):
        self.store = get_store()
        self.teams = {
            "FORGE":     TeamLead("FORGE",     [ForgeWorker(), ForgeWorker()]),
            "ORACLE":    TeamLead("ORACLE",    [OracleWorker(), OracleWorker()]),
            "SENTINEL":  TeamLead("SENTINEL",  [SentinelWorker()]),
            "ARCHIVIST": TeamLead("ARCHIVIST", [ArchivistWorker()]),
            "HERALD":    TeamLead("HERALD",    [HeraldWorker()]),
        }
        self._print_boot()

    def run_goal(self, goal: str) -> dict:
        print(f"\n[SUPERVISOR] Goal: {goal[:100]}")
        routing   = self._decompose(goal)
        team_name = routing.get("team","ORACLE").upper()
        tasks     = routing.get("tasks",[goal])
        if team_name not in self.teams: team_name = "ORACLE"
        team = self.teams[team_name]

        def _run(task):
            r = team.dispatch(task, context=f"Parent goal: {goal}")
            print(f"  [{team_name}] {task[:60]!r} → {r['status'].upper()}")
            return r

        results = []
        with ThreadPoolExecutor(max_workers=min(len(tasks[:5]),5)) as ex:
            futures = {ex.submit(_run, t): t for t in tasks[:5]}
            for f in as_completed(futures):
                results.append(f.result())

        return {"goal":goal,"team":team_name,"tasks":tasks,"results":results,"swarm":self.swarm_status()}

    def swarm_status(self):
        return {name:{"lead":lead.agent_id,"workers":[w.info for w in lead.workers]}
                for name, lead in self.teams.items()}

    def consolidate(self):
        return self.teams["ARCHIVIST"].workers[0].consolidate()

    def _decompose(self, goal):
        system = (
            "You are the Aegis.net Supervisor. Decompose the goal into ≤5 atomic tasks and pick the best team.\n"
            "Teams: FORGE(code/GitHub) ORACLE(research) SENTINEL(security) ARCHIVIST(memory) HERALD(comms)\n"
            'Respond ONLY with valid JSON: {"team":"TEAM_NAME","tasks":["task 1","task 2"]}'
        )
        raw = llm_router.chat([{"role":"user","content":goal}],
            model=cfg.MODEL_SUPERVISOR, system=system, backend="anthropic", max_tokens=512)
        try:
            return json.loads(raw[raw.index("{"):raw.rindex("}")+1])
        except Exception:
            return {"team":"ORACLE","tasks":[goal]}

    def _print_boot(self):
        available = llm_router.detect_available_backends()
        total = sum(len(t.workers) for t in self.teams.values())
        print("\n" + "═"*52)
        print("  AEGIS.NET — COGNITIVE AGENT SWARM")
        print("  For the Benefit of Humankind")
        print("═"*52)
        print(f"  Teams    : {list(self.teams.keys())}")
        print(f"  Workers  : {total} agents spawned")
        print(f"  Backends : {available}")
        print(f"  Supervisor: {cfg.MODEL_SUPERVISOR}")
        print()
        print("  ┌─ SWARM ROSTER ──────────────────────────────")
        for name, lead in self.teams.items():
            for w in lead.workers:
                print(f"  │  {name:10} {w.agent_id}  [{tier(w.trust_score):12}]  {w._backend}/{w._model.split('-')[0]}")
        print("  └─────────────────────────────────────────────")
        print()
