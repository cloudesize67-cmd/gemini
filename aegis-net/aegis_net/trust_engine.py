from dataclasses import dataclass, field

@dataclass
class TrustMetrics:
    tasks_assigned:   int   = 0
    tasks_completed:  int   = 0
    tasks_correct:    int   = 0
    total_time_ratio: float = 0.0
    anomaly_count:    int   = 0

def compute_trust(m: TrustMetrics) -> float:
    if m.tasks_assigned == 0: return 50.0
    accuracy    = m.tasks_correct   / max(m.tasks_assigned, 1)
    reliability = m.tasks_completed / max(m.tasks_assigned, 1)
    speed       = 1.0 - min(m.total_time_ratio / max(m.tasks_assigned, 1), 1.0)
    safety      = max(0.0, 1.0 - m.anomaly_count * 0.1)
    anomaly     = min(m.anomaly_count * 0.05, 0.5)
    raw = 0.35*accuracy + 0.25*reliability + 0.15*speed + 0.20*safety - 0.05*anomaly
    return round(max(0.0, min(100.0, raw * 100)), 2)

def tier(score: float) -> str:
    if score >= 85: return "ELITE"
    if score >= 65: return "TRUSTED"
    if score >= 40: return "OPERATIVE"
    return "PROBATIONARY"
