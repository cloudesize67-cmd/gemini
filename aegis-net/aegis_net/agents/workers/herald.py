from ..base import BaseAgent
class HeraldWorker(BaseAgent):
    def __init__(self):
        super().__init__(role="Communications and outreach specialist", team="HERALD")
        self.skill_vector.update({"communication":0.95,"creativity":0.85})
    def _system_prompt(self):
        return super()._system_prompt() + "\n\nHERALD: Craft clear, professional communications."
