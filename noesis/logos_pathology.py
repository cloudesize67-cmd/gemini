"""
NOESIS LOGOS PATHOLOGY — Extended Lyapunov gate with pathological state detection
Three new stability conditions layered on top of the LOGOS Lyapunov gate:
  - PathologicalLoopDetector   (same tool + error repeating without correction)
  - CoordinationBottleneckDetector  (retry rate spikes per agent)
  - SelfEvolutionDetector      (context growth runaway)
"""

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Sub-reports
# ---------------------------------------------------------------------------

@dataclass
class LoopReport:
    loop_detected: bool
    loop_depth: int          # How many consecutive repetitions found
    stuck_tool: str          # Name of the tool stuck in the loop (empty if none)


@dataclass
class BottleneckReport:
    bottleneck_detected: bool
    retry_rate: float        # Retries per 60-second window
    bottleneck_agent: str    # Agent name with highest retry rate (empty if none)


@dataclass
class EvolutionReport:
    runaway_detected: bool
    growth_ratio: float      # current_context_size / baseline_context_size


# ---------------------------------------------------------------------------
# Combined report
# ---------------------------------------------------------------------------

@dataclass
class PathologyReport:
    any_pathology: bool
    graceful_degrade_trigger: bool   # True if any_pathology
    loop_report: LoopReport
    bottleneck_report: BottleneckReport
    evolution_report: EvolutionReport
    recommended_action: str          # "CONTINUE" | "THROTTLE" | "RESET" | "ESCALATE"


# ---------------------------------------------------------------------------
# Individual detectors
# ---------------------------------------------------------------------------

class PathologicalLoopDetector:
    """
    Detects when the same (tool_name, error_signature) pair repeats N times
    within a rolling window of the last `window_size` calls with no correction.

    Threshold: same pair 3+ times in 10 calls = pathological loop.
    """

    LOOP_THRESHOLD = 3
    WINDOW_SIZE = 10

    def __init__(self):
        # Deque of (tool_name, error_signature) tuples — rolling window
        self._window: deque[tuple[str, str]] = deque(maxlen=self.WINDOW_SIZE)

    def record(self, tool_name: str, error: str) -> None:
        """Record a tool call outcome."""
        # Normalise error to a short signature (first 80 chars, stripped)
        sig = error.strip()[:80] if error else ""
        self._window.append((tool_name, sig))

    def assess(self) -> LoopReport:
        """Assess whether the current window contains a pathological loop."""
        if not self._window:
            return LoopReport(loop_detected=False, loop_depth=0, stuck_tool="")

        # Count occurrences of each (tool, error) pair
        counts: dict[tuple[str, str], int] = {}
        for pair in self._window:
            counts[pair] = counts.get(pair, 0) + 1

        # Find the worst offender
        worst_pair = max(counts, key=lambda k: counts[k])
        worst_count = counts[worst_pair]

        if worst_count >= self.LOOP_THRESHOLD:
            return LoopReport(
                loop_detected=True,
                loop_depth=worst_count,
                stuck_tool=worst_pair[0],
            )

        return LoopReport(loop_detected=False, loop_depth=worst_count, stuck_tool="")


class CoordinationBottleneckDetector:
    """
    Detects retry rate spikes per agent within a 60-second rolling window.

    Threshold: >15 retries / 60s for any single agent = bottleneck detected.
    """

    WINDOW_SECONDS = 60
    RETRY_THRESHOLD = 15

    def __init__(self):
        # Maps agent_name → deque of timestamps (float)
        self._timestamps: dict[str, deque[float]] = {}

    def record(self, agent_name: str) -> None:
        """Record a retry event for an agent."""
        now = time.monotonic()
        if agent_name not in self._timestamps:
            self._timestamps[agent_name] = deque()
        self._timestamps[agent_name].append(now)

    def assess(self) -> BottleneckReport:
        """Return bottleneck assessment across all tracked agents."""
        now = time.monotonic()
        cutoff = now - self.WINDOW_SECONDS

        worst_agent = ""
        worst_rate = 0.0

        for agent, timestamps in self._timestamps.items():
            # Evict old entries
            while timestamps and timestamps[0] < cutoff:
                timestamps.popleft()
            rate = len(timestamps)
            if rate > worst_rate:
                worst_rate = rate
                worst_agent = agent

        detected = worst_rate > self.RETRY_THRESHOLD

        return BottleneckReport(
            bottleneck_detected=detected,
            retry_rate=round(worst_rate, 2),
            bottleneck_agent=worst_agent if detected else "",
        )


class SelfEvolutionDetector:
    """
    Detects context growth runaway.

    A baseline context size is established at session start (first call to
    `record`). If the context grows >3x baseline without SUPERVISOR
    authorization, runaway is flagged.
    """

    GROWTH_THRESHOLD = 3.0

    def __init__(self):
        self._baseline: Optional[int] = None
        self._current: int = 0
        self._supervisor_authorized: bool = False

    def authorize(self) -> None:
        """Called by SUPERVISOR to approve a large context expansion."""
        self._supervisor_authorized = True

    def record(self, context_size: int) -> None:
        """Record current context size (in tokens or characters — caller decides units)."""
        if self._baseline is None:
            self._baseline = max(context_size, 1)
        self._current = context_size

    def assess(self) -> EvolutionReport:
        """Return evolution assessment."""
        if self._baseline is None or self._baseline == 0:
            return EvolutionReport(runaway_detected=False, growth_ratio=1.0)

        ratio = self._current / self._baseline

        runaway = ratio > self.GROWTH_THRESHOLD and not self._supervisor_authorized

        return EvolutionReport(
            runaway_detected=runaway,
            growth_ratio=round(ratio, 4),
        )


# ---------------------------------------------------------------------------
# PathologyGate — unified interface
# ---------------------------------------------------------------------------

class PathologyGate:
    """
    Unified pathology detection gate extending the LOGOS Lyapunov stability
    framework with three runtime pathology detectors.

    Usage::

        gate = PathologyGate()
        gate.record_call('web_search', 'timeout', 'ARGUS', context_size=1000)
        report = gate.assess()
        if report.any_pathology:
            trigger_graceful_degrade(report.recommended_action)
    """

    def __init__(self):
        self._loop_detector = PathologicalLoopDetector()
        self._bottleneck_detector = CoordinationBottleneckDetector()
        self._evolution_detector = SelfEvolutionDetector()

    def record_call(
        self,
        tool_name: str,
        error: str,
        agent_name: str,
        context_size: int,
    ) -> None:
        """
        Log a single agent tool call for pathology tracking.

        Args:
            tool_name:    Name of the tool that was called.
            error:        Error string (empty string = success).
            agent_name:   Identifier of the calling agent (e.g. "ARGUS").
            context_size: Current context size in tokens or chars.
        """
        self._loop_detector.record(tool_name, error)
        if error:
            # Retries are error calls
            self._bottleneck_detector.record(agent_name)
        self._evolution_detector.record(context_size)

    def authorize_context_growth(self) -> None:
        """Signal SUPERVISOR approval for large context expansion."""
        self._evolution_detector.authorize()

    def assess(self) -> PathologyReport:
        """
        Assess current pathology state across all three detectors.

        Returns a PathologyReport with recommended action:
          CONTINUE  — no issues
          THROTTLE  — bottleneck detected, slow the retry rate
          RESET     — loop detected, reset the stuck agent
          ESCALATE  — context runaway or multiple issues, escalate to SUPERVISOR
        """
        loop_report = self._loop_detector.assess()
        bottleneck_report = self._bottleneck_detector.assess()
        evolution_report = self._evolution_detector.assess()

        any_pathology = (
            loop_report.loop_detected
            or bottleneck_report.bottleneck_detected
            or evolution_report.runaway_detected
        )

        # Determine recommended action (priority: ESCALATE > RESET > THROTTLE > CONTINUE)
        if evolution_report.runaway_detected:
            action = "ESCALATE"
        elif loop_report.loop_detected and bottleneck_report.bottleneck_detected:
            action = "ESCALATE"
        elif loop_report.loop_detected:
            action = "RESET"
        elif bottleneck_report.bottleneck_detected:
            action = "THROTTLE"
        else:
            action = "CONTINUE"

        return PathologyReport(
            any_pathology=any_pathology,
            graceful_degrade_trigger=any_pathology,
            loop_report=loop_report,
            bottleneck_report=bottleneck_report,
            evolution_report=evolution_report,
            recommended_action=action,
        )
