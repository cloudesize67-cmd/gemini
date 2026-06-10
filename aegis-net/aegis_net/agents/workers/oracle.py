from ..base import BaseAgent
class OracleWorker(BaseAgent):
    def __init__(self):
        super().__init__(role="Research analyst and knowledge synthesizer", team="ORACLE")
        self.skill_vector.update({"research":0.9,"reasoning":0.85,"communication":0.8})
    def _system_prompt(self):
        return super()._system_prompt() + "\n\nORACLE: Synthesize accurately. Cite sources. Distinguish facts from inference."
