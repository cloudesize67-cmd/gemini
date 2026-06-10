from __future__ import annotations
import sqlite3, uuid, time, os
from dataclasses import dataclass, field
from typing import Optional

DB_PATH = os.environ.get("AEGIS_DB_PATH", "aegis_experience.db")

@dataclass
class ExperienceEntry:
    agent_id:         str
    domain:           str
    task_description: str
    tools_used:       list = field(default_factory=list)
    outcome:          str  = "success"
    reward:           float = 1.0
    td_error:         float = 0.5
    transferable_skill: str = ""
    entry_id:         str  = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp:        float = field(default_factory=time.time)

class ExperienceStore:
    def __init__(self, db_path=DB_PATH):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init()

    def _init(self):
        self.conn.execute("""CREATE TABLE IF NOT EXISTS experiences (
            entry_id TEXT PRIMARY KEY, agent_id TEXT, domain TEXT,
            task_description TEXT, outcome TEXT, reward REAL,
            td_error REAL, priority REAL, timestamp REAL)""")
        self.conn.commit()

    def add(self, e: ExperienceEntry):
        priority = (abs(e.td_error) + 0.01) ** 0.6
        self.conn.execute("INSERT OR REPLACE INTO experiences VALUES (?,?,?,?,?,?,?,?,?)",
            (e.entry_id, e.agent_id, e.domain, e.task_description,
             e.outcome, e.reward, e.td_error, priority, e.timestamp))
        self.conn.commit()

    def sample(self, n=32):
        cur = self.conn.execute(
            "SELECT * FROM experiences ORDER BY priority DESC LIMIT ?", (n,))
        return cur.fetchall()

_store: Optional[ExperienceStore] = None
def get_store() -> ExperienceStore:
    global _store
    if _store is None: _store = ExperienceStore()
    return _store
