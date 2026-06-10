from ..base import BaseAgent
class ArchivistWorker(BaseAgent):
    def __init__(self):
        super().__init__(role="Memory manager and knowledge consolidator", team="ARCHIVIST")
        self.skill_vector.update({"memory":0.95,"reasoning":0.8})
    def _system_prompt(self):
        return super()._system_prompt() + "\n\nARCHIVIST: Consolidate knowledge. Extract transferable lessons."
    def consolidate(self):
        return self.run("Consolidate recent experiences into transferable lessons.")
