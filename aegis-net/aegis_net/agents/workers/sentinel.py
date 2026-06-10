from ..base import BaseAgent
class SentinelWorker(BaseAgent):
    def __init__(self):
        super().__init__(role="Security analyst and threat monitor", team="SENTINEL")
        self.skill_vector.update({"security":0.95,"reasoning":0.85})
    def _system_prompt(self):
        return super()._system_prompt() + "\n\nSENTINEL: Identify threats, vulnerabilities, and risks precisely."
