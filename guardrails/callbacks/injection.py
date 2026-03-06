"""Prompt injection detection callback handler."""
from __future__ import annotations

from typing import Any

from langchain_core.agents import AgentAction

from guardrails.callbacks.base import BaseGuardrailCallback, GuardrailsContext
from guardrails.injection import PromptInjectionPolicy


class PromptInjectionCallbackHandler(BaseGuardrailCallback):
    """
    Callback handler for prompt injection detection.

    Checks user input for prompt injection patterns before agent execution.
    """

    def __init__(self, context: GuardrailsContext, policy: PromptInjectionPolicy):
        super().__init__(context)
        self.policy = policy

    def on_agent_action(
        self,
        action: AgentAction,
        **kwargs: Any,
    ) -> Any:
        """Run before tool execution to check for injection patterns."""
        # Check the original user input (stored in context)
        if not self.context.user_input:
            return

        blocked, hits = self.policy.check(self.context.user_input)

        if hits:
            self.context.risk_score.add(40, f"Prompt injection patterns: {hits}")
            self.context.triggered_policies.append("prompt_injection")
            self.context.add_trace(
                "before_agent:prompt_injection",
                "flagged",
                f"Matched patterns: {hits}"
            )
        else:
            self.context.add_trace(
                "before_agent:prompt_injection",
                "clear",
                "No prompt injection pattern found."
            )
