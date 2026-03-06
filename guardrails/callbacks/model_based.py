"""Model-based guardrails callback handler."""
from __future__ import annotations

from typing import Any

from langchain_core.agents import AgentAction, AgentFinish

from guardrails.callbacks.base import BaseGuardrailCallback, GuardrailsContext
from guardrails.model_based import ModelBasedPolicy


class ModelBasedCallbackHandler(BaseGuardrailCallback):
    """
    Callback handler for model-based safety classification.

    Uses an LLM to classify both input and output for safety.
    """

    def __init__(self, context: GuardrailsContext, policy: ModelBasedPolicy):
        super().__init__(context)
        self.policy = policy
        self._input_checked = False

    def on_agent_action(
        self,
        action: AgentAction,
        **kwargs: Any,
    ) -> Any:
        """Check input safety before tool execution (only once)."""
        # Only check input once
        if self._input_checked or not self.context.user_input:
            return

        self._input_checked = True

        label, expl = self.policy.classify(self.context.user_input)
        self.context.add_trace("before_agent:model_based", label, expl)

        if label == "unsafe":
            self.context.risk_score.add(30, "Model-based classifier marked input unsafe.")
            self.context.triggered_policies.append("model_based_input")

    def on_agent_finish(
        self,
        finish: AgentFinish,
        **kwargs: Any,
    ) -> Any:
        """Check output safety after agent completion."""
        # Check the final output
        output = finish.return_values.get("output", "")
        if not output:
            return

        label, expl = self.policy.classify(output)
        self.context.add_trace("after_agent:model_based", label, expl)

        if label == "unsafe":
            # Mutate output to safe response
            safe_output = "⚠️ Unsafe output was intercepted and replaced with a compliant response."
            self.context.add_trace("after_agent:mutation", "mutated", safe_output)
            self.context.final_output = safe_output
            self.context.triggered_policies.append("model_based_output")
            # Update the finish return values
            finish.return_values["output"] = safe_output
