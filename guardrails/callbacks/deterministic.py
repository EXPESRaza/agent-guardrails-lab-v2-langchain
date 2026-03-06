"""Deterministic guardrails callback handler."""
from __future__ import annotations

from typing import Any, Dict

from langchain_core.agents import AgentAction

from guardrails.callbacks.base import BaseGuardrailCallback, GuardrailsContext
from guardrails.deterministic import DeterministicPolicy


class DeterministicCallbackHandler(BaseGuardrailCallback):
    """
    Callback handler for deterministic keyword-based guardrails.

    Checks user input against banned keywords before agent execution.
    """

    def __init__(self, context: GuardrailsContext, policy: DeterministicPolicy):
        super().__init__(context)
        self.policy = policy

    def on_agent_action(
        self,
        action: AgentAction,
        **kwargs: Any,
    ) -> Any:
        """Run before tool execution to check for banned keywords."""
        # Check the original user input (stored in context)
        if not self.context.user_input:
            return

        blocked, hits = self.policy.check(self.context.user_input)

        if hits:
            self.context.risk_score.add(35, f"Deterministic banned keywords: {hits}")
            self.context.triggered_policies.append("deterministic_keywords")
            self.context.add_trace(
                "before_agent:deterministic",
                "flagged",
                f"Matched keywords: {hits}"
            )
        else:
            self.context.add_trace(
                "before_agent:deterministic",
                "clear",
                "No banned keywords matched."
            )
