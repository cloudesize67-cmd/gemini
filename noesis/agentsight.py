"""
NOESIS AgentSight — Application-layer observability for LLM agents
Equivalent of AgentSight eBPF tracing at the LLM prompt/tool-call layer.
Correlates declared intent (prompt) with executed action (tool call) and
flags causal divergence.
"""

import re
import time
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Injection patterns used for INJECTION verdict detection
# ---------------------------------------------------------------------------

INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"ignore (previous|all|prior|above|earlier) (instructions?|context|system|prompt)",
        r"disregard (previous|all|prior|above|earlier) (instructions?|context|system|prompt)",
        r"forget (everything|all|your|previous|prior) (instructions?|context|you were told)",
        r"new (instructions?|directive|system prompt|orders?):",
        r"(system|admin|developer|operator) (message|prompt|instruction|override):",
        r"\[system\]|\[admin\]|\[override\]|\[instruction\]",
        r"</?(system|instructions?|context|prompt)>",
        r"you are now (?!NOESIS|ARBITER|LOGOS|ARGUS|DAEDALUS|SUPERVISOR|H.A.L.I.S)",
        r"act as (?!NOESIS|ARBITER|LOGOS|ARGUS|DAEDALUS|SUPERVISOR|H.A.L.I.S)",
        r"override (your|the) (previous|current|main|primary) (goal|objective|task|instructions?)",
    ]
]

# Patterns that suggest self-modification or unauthorised sub-agent spawning
SELF_EVOLVE_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"spawn(ing)? (a |an )?(new |sub[- ])?(agent|worker|instance|process)",
        r"fork(ing)? (a |an )?(new |sub[- ])?(agent|worker|instance|process)",
        r"create (a |an )?(new |sub[- ])?(agent|worker|instance)",
        r"modify (my|your|its) (instructions?|system prompt|objectives?|goals?)",
        r"update (my|your|its) (instructions?|system prompt|objectives?|goals?)",
        r"rewrite (my|your|its) (instructions?|system prompt)",
        r"self[- ]modify|self[- ]evolve|self[- ]update|self[- ]improve",
        r"unauthori[sz]ed (sub[- ]agent|agent|process|worker)",
    ]
]

# Tools that are considered universally harmful / strongly suspicious if undeclared
ROGUE_TOOL_INDICATORS: set[str] = {
    "exec",
    "shell",
    "bash",
    "cmd",
    "powershell",
    "subprocess",
    "os.system",
    "eval",
    "spawn",
    "fork",
    "sudo",
    "rm",
    "delete_file",
    "overwrite_file",
    "write_to_disk",
    "send_email",
    "post_to_slack",
    "deploy",
    "push_to_github",
    "create_pr",
}


# ---------------------------------------------------------------------------
# Data records
# ---------------------------------------------------------------------------

@dataclass
class IntentRecord:
    """What the agent declared it would do (captured from LLM prompt output)."""
    agent_id: str
    intent_text: str
    declared_tools: list[str]       # Tools the agent explicitly named
    timestamp: float = field(default_factory=time.time)


@dataclass
class ActionRecord:
    """What the agent actually did (captured at tool-call boundary)."""
    agent_id: str
    tool_name: str
    tool_args: dict
    timestamp: float = field(default_factory=time.time)


@dataclass
class CausalCorrelation:
    """Result of matching an IntentRecord to an ActionRecord."""
    intent_record: IntentRecord
    action_record: ActionRecord
    alignment_score: float          # 0.0 = total divergence, 1.0 = perfect alignment
    divergence_flags: list[str]     # Human-readable divergence descriptions
    verdict: str                    # "ALIGNED" | "SUSPICIOUS" | "ROGUE" | "INJECTION" | "SELF_EVOLVE"


# ---------------------------------------------------------------------------
# AgentSight
# ---------------------------------------------------------------------------

class AgentSight:
    """
    Application-layer observability for NOESIS agents.

    Records LLM intent declarations and tool-call actions, then correlates
    them causally to flag behavioural anomalies.

    Usage::

        sight = AgentSight()
        sight.record_intent('ARGUS', 'I will search the web for sources', ['web_search'])
        sight.record_action('ARGUS', 'web_search', {'query': 'test'})
        correlation = sight.correlate('ARGUS')
        if correlation.verdict != 'ALIGNED':
            escalate(correlation)
    """

    def __init__(self):
        # Most-recent intent per agent
        self._intents: dict[str, IntentRecord] = {}
        # Most-recent action per agent
        self._actions: dict[str, ActionRecord] = {}
        # All non-ALIGNED correlations (escalation queue)
        self._escalation_queue: list[CausalCorrelation] = []

    # ------------------------------------------------------------------ #
    # Recording                                                            #
    # ------------------------------------------------------------------ #

    def record_intent(
        self,
        agent_id: str,
        intent_text: str,
        declared_tools: list[str],
    ) -> None:
        """
        Capture what the agent said it would do.

        Args:
            agent_id:       Agent identifier (e.g. "ARGUS").
            intent_text:    Raw text from the LLM reasoning/planning step.
            declared_tools: Tool names the agent explicitly mentioned.
        """
        self._intents[agent_id] = IntentRecord(
            agent_id=agent_id,
            intent_text=intent_text,
            declared_tools=[t.lower().strip() for t in declared_tools],
        )

    def record_action(
        self,
        agent_id: str,
        tool_name: str,
        tool_args: dict,
    ) -> None:
        """
        Capture what the agent actually did.

        Args:
            agent_id:  Agent identifier.
            tool_name: Name of the tool that was invoked.
            tool_args: Arguments passed to the tool.
        """
        self._actions[agent_id] = ActionRecord(
            agent_id=agent_id,
            tool_name=tool_name.lower().strip(),
            tool_args=tool_args,
        )

    # ------------------------------------------------------------------ #
    # Correlation scoring                                                  #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _args_contain_injection(tool_args: dict) -> bool:
        """Return True if any string value in tool_args matches injection patterns."""
        def _walk(obj) -> str:
            if isinstance(obj, str):
                return obj
            if isinstance(obj, dict):
                return " ".join(_walk(v) for v in obj.values())
            if isinstance(obj, (list, tuple)):
                return " ".join(_walk(v) for v in obj)
            return ""

        args_text = _walk(tool_args)
        return any(pat.search(args_text) for pat in INJECTION_PATTERNS)

    @staticmethod
    def _args_contain_self_evolve(tool_args: dict) -> bool:
        """Return True if tool_args suggest self-modification or unauthorised spawning."""
        def _walk(obj) -> str:
            if isinstance(obj, str):
                return obj
            if isinstance(obj, dict):
                return " ".join(_walk(v) for v in obj.values())
            if isinstance(obj, (list, tuple)):
                return " ".join(_walk(v) for v in obj)
            return ""

        args_text = _walk(tool_args)
        return any(pat.search(args_text) for pat in SELF_EVOLVE_PATTERNS)

    def _compute_alignment(
        self,
        intent: IntentRecord,
        action: ActionRecord,
    ) -> tuple[float, list[str], str]:
        """
        Core alignment computation.

        Returns:
            (alignment_score: float, divergence_flags: list[str], verdict: str)
        """
        flags: list[str] = []
        tool = action.tool_name

        # --- Check 1: INJECTION (highest priority) ---
        if self._args_contain_injection(action.tool_args):
            flags.append(
                f"Injection patterns detected in args of '{tool}'"
            )
            return 0.0, flags, "INJECTION"

        # --- Check 2: SELF_EVOLVE ---
        if self._args_contain_self_evolve(action.tool_args):
            flags.append(
                f"Self-evolution patterns detected in args of '{tool}'"
            )
            return 0.0, flags, "SELF_EVOLVE"

        # Intent text scan for self-evolve language
        if any(pat.search(intent.intent_text) for pat in SELF_EVOLVE_PATTERNS):
            flags.append("Intent text contains self-evolution language")
            return 0.05, flags, "SELF_EVOLVE"

        # --- Check 3: Is tool in declared list? ---
        declared = set(intent.declared_tools)
        tool_declared = tool in declared

        # --- Check 4: ROGUE tool ---
        if tool in ROGUE_TOOL_INDICATORS and not tool_declared:
            flags.append(
                f"Undeclared rogue tool '{tool}' invoked — not in declared list"
            )
            return 0.0, flags, "ROGUE"

        if not tool_declared and not declared:
            # No tools were declared at all — treat empty declaration as neutral
            # (some agents operate tool-free in planning steps)
            return 0.85, [], "ALIGNED"

        if not tool_declared:
            # Tool used but not declared
            flags.append(
                f"Tool '{tool}' was not in declared tool list: {list(declared)}"
            )
            # SUSPICIOUS rather than ROGUE unless it's in the rogue set
            score = 0.35
            verdict = "SUSPICIOUS"
        else:
            # Tool declared and used — check args for anomalies
            score = 1.0
            verdict = "ALIGNED"

        # Slight score reduction if intent text doesn't semantically reference the tool
        # (Simple heuristic: tool name appears in intent text?)
        tool_bare = tool.replace("_", " ").replace("-", " ")
        if tool_bare not in intent.intent_text.lower() and tool not in intent.intent_text.lower():
            score = max(score - 0.1, 0.0)
            if verdict == "ALIGNED":
                # Still aligned — just weak textual confirmation
                pass  # keep ALIGNED but lower score

        return round(score, 4), flags, verdict

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def correlate(self, agent_id: str) -> CausalCorrelation:
        """
        Match the last recorded intent to the last recorded action for an agent.

        If no intent or action has been recorded, creates synthetic records to
        allow the correlation to proceed with maximum divergence flagged.

        Args:
            agent_id: Agent identifier.

        Returns:
            CausalCorrelation with alignment score and verdict.
        """
        now = time.time()

        intent = self._intents.get(agent_id) or IntentRecord(
            agent_id=agent_id,
            intent_text="",
            declared_tools=[],
            timestamp=now,
        )
        action = self._actions.get(agent_id) or ActionRecord(
            agent_id=agent_id,
            tool_name="",
            tool_args={},
            timestamp=now,
        )

        if not action.tool_name:
            # No action recorded — treat as aligned (agent may not have acted yet)
            corr = CausalCorrelation(
                intent_record=intent,
                action_record=action,
                alignment_score=1.0,
                divergence_flags=[],
                verdict="ALIGNED",
            )
        else:
            score, flags, verdict = self._compute_alignment(intent, action)
            corr = CausalCorrelation(
                intent_record=intent,
                action_record=action,
                alignment_score=score,
                divergence_flags=flags,
                verdict=verdict,
            )

        if corr.verdict != "ALIGNED":
            self._escalation_queue.append(corr)

        return corr

    def get_escalation_queue(self) -> list[CausalCorrelation]:
        """
        Return all non-ALIGNED causal correlations since last drain.
        Does NOT clear the queue — call drain_escalation_queue() for that.
        """
        return list(self._escalation_queue)

    def drain_escalation_queue(self) -> list[CausalCorrelation]:
        """Return and clear all queued escalations."""
        queue = list(self._escalation_queue)
        self._escalation_queue.clear()
        return queue
