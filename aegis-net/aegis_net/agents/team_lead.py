from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from .base import BaseAgent

class TeamLead:
    def __init__(self, team_name: str, workers: list):
        self.team_name = team_name
        self.workers   = workers
        self.agent_id  = f"lead-{team_name[:3].lower()}"

    def dispatch(self, task: str, context: str = "") -> dict:
        best = max(self.workers, key=lambda w: w.trust_score)
        return best.run(task, context)

    def dispatch_parallel(self, tasks: list, context: str = "") -> list:
        results = []
        with ThreadPoolExecutor(max_workers=min(len(tasks),5)) as ex:
            futures = {ex.submit(self.dispatch, t, context): t for t in tasks}
            for f in as_completed(futures):
                results.append(f.result())
        return results
