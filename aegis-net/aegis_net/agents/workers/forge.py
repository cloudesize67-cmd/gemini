from ..base import BaseAgent
class ForgeWorker(BaseAgent):
    def __init__(self):
        super().__init__(role="Python engineer and GitHub specialist", team="FORGE")
        self.skill_vector.update({"coding":0.95,"planning":0.85,"tool_use":0.9})
    def _system_prompt(self):
        return super()._system_prompt() + "\n\nFORGE: Write clean, tested Python. Use git best practices."
