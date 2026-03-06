"""Human-in-the-loop callback handler."""
from __future__ import annotations

from typing import Any, Dict

from langchain_core.agents import AgentAction

from guardrails.callbacks.base import BaseGuardrailCallback, GuardrailsContext
from guardrails.policy import PolicyConfig


class ApprovalRequiredException(Exception):
    """Exception raised when human approval is required."""
    pass


class HITLCallbackHandler(BaseGuardrailCallback):
    """
    Callback handler for human-in-the-loop approval workflow.

    Pauses execution if a tool requires approval and it hasn't been granted.
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
        """Check if tool requires approval before execution."""
        tool_name = serialized.get("name", "")
        if not tool_name:
            return

        # Check if approval is required
        require_approval = (
            self.policy.hitl_require_approval.get(tool_name, False)
            or self.context.risk_score.total >= self.policy.review_threshold
        )

        if require_approval:
            # Check if approval was granted
            if not self.context.approvals.get(tool_name, False):
                # Pause for approval
                paused_msg = f"⏸️ Paused for human approval before {tool_name}."
                self.context.paused = True
                self.context.paused_tool = tool_name
                self.context.meta["paused_tool"] = tool_name
                self.context.meta["paused_args"] = kwargs.get("tool_input", {})
                self.context.final_output = paused_msg
                self.context.final_decision = "paused_for_approval"

                self.context.add_trace(
                    "hitl",
                    "paused",
                    paused_msg,
                    {"risk": self.context.risk_score.total}
                )

                # Raise exception to stop execution
                raise ApprovalRequiredException(paused_msg)
