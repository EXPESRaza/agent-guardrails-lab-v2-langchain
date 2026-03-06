"""Risk scoring callback handler."""
from __future__ import annotations

from typing import Any, Dict

from langchain_core.agents import AgentAction

from guardrails.callbacks.base import BaseGuardrailCallback, GuardrailsContext
from guardrails.policy import PolicyConfig


class RiskScoringCallbackHandler(BaseGuardrailCallback):
    """
    Callback handler for risk scoring.

    Tracks cumulative risk score and blocks execution if threshold exceeded.
    """

    def __init__(self, context: GuardrailsContext, policy: PolicyConfig):
        super().__init__(context)
        self.policy = policy

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        **kwargs: Any,
    ) -> Any:
        """Add tool risk to cumulative score."""
        tool_name = serialized.get("name", "")
        if not tool_name:
            return

        # Store tool info in context
        self.context.tool_used = tool_name
        self.context.add_trace(
            "agent:tool_routing",
            "selected",
            f"Tool selected: {tool_name}",
            {"tool": tool_name}
        )

        # Add tool risk
        tool_risk = self.policy.tool_risk_levels.get(tool_name, 0)
        self.context.risk_score.add(tool_risk, f"Tool selected: {tool_name}")

        # Check if risk exceeds block threshold
        if self.context.risk_score.total >= self.policy.block_threshold:
            blocked_msg = "🚫 Blocked due to high composite risk score."
            self.context.add_trace(
                "decision",
                "blocked",
                blocked_msg,
                {"risk": self.context.risk_score.total}
            )
            self.context.final_output = blocked_msg
            self.context.final_decision = "blocked"
            # Raise exception to stop execution
            raise Exception("Blocked due to high risk score")
