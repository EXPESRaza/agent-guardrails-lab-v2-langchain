"""Guardrails-AI PII detection callback handler."""
from __future__ import annotations

from typing import Any

from langchain_core.agents import AgentAction, AgentFinish

from guardrails.callbacks.base import BaseGuardrailCallback, GuardrailsContext
from guardrails.guardrails_ai_pii import GuardrailsAIPII


class GuardrailsAICallbackHandler(BaseGuardrailCallback):
    """
    Callback handler for PII detection and handling using Guardrails-AI.

    Processes both input and output for PII, applying configured strategies.
    """

    def __init__(self, context: GuardrailsContext, pii_handler: GuardrailsAIPII):
        super().__init__(context)
        self.pii_handler = pii_handler
        self._input_processed = False

    def on_agent_action(
        self,
        action: AgentAction,
        **kwargs: Any,
    ) -> Any:
        """Process input for PII before tool execution (only once)."""
        # Only process input once
        if self._input_processed or not self.context.user_input:
            return

        self._input_processed = True

        processed_input, notes, pii_block, pii_triggers = self.pii_handler.process(
            self.context.user_input,
            is_input=True
        )

        # Store processed input
        self.context.processed_input = processed_input

        # Add trace notes
        for note in notes:
            self.context.add_trace("pii:input", "note", note)

        # Track triggers
        if pii_triggers:
            self.context.risk_score.add(20, f"PII detected in input: {pii_triggers}")
            self.context.triggered_policies.extend(pii_triggers)

        # Handle blocking
        if pii_block:
            self.context.paused = True
            self.context.final_output = "🚫 Blocked by PII input policy."
            self.context.final_decision = "blocked"
            self.context.add_trace("decision", "blocked", self.context.final_output)
            # Raise exception to stop execution
            raise Exception("Blocked by PII input policy")

    def on_agent_finish(
        self,
        finish: AgentFinish,
        **kwargs: Any,
    ) -> Any:
        """Process output for PII after agent completion."""
        # Get the output
        output = finish.return_values.get("output", "")
        if not output:
            return

        processed_output, notes, output_blocked, output_triggers = self.pii_handler.process(
            output,
            is_input=False
        )

        # Add trace notes
        for note in notes:
            self.context.add_trace("pii:output", "note", note)

        # Track triggers
        if output_triggers:
            self.context.triggered_policies.extend(output_triggers)

        # Handle blocking
        if output_blocked:
            blocked_msg = "🚫 Output blocked by PII output policy."
            self.context.add_trace("after_agent:pii", "blocked", blocked_msg)
            self.context.final_output = blocked_msg
            self.context.final_decision = "blocked"
            finish.return_values["output"] = blocked_msg
        else:
            # Update with processed output
            finish.return_values["output"] = processed_output
            self.context.final_output = processed_output
