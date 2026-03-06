"""Audit logging callback handler."""
from __future__ import annotations

from typing import Any, Dict, List

from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.outputs import LLMResult

from guardrails.callbacks.base import BaseGuardrailCallback, GuardrailsContext


class AuditLoggingCallbackHandler(BaseGuardrailCallback):
    """
    Callback handler for comprehensive audit logging.

    Collects all events during agent execution for audit trail.
    """

    def __init__(self, context: GuardrailsContext):
        super().__init__(context)

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        **kwargs: Any,
    ) -> Any:
        """Log LLM call start."""
        # Could add LLM call tracking if needed
        pass

    def on_llm_end(
        self,
        response: LLMResult,
        **kwargs: Any,
    ) -> Any:
        """Log LLM call completion."""
        # Could add LLM response tracking if needed
        pass

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        **kwargs: Any,
    ) -> Any:
        """Log tool execution start."""
        tool_name = serialized.get("name", "")
        if tool_name:
            self.context.add_trace(
                "tool:start",
                "executing",
                f"Executing tool: {tool_name}"
            )

    def on_tool_end(
        self,
        output: str,
        **kwargs: Any,
    ) -> Any:
        """Log tool execution completion."""
        self.context.add_trace(
            "tool:execute",
            "ok",
            output
        )

    def on_tool_error(
        self,
        error: Exception,
        **kwargs: Any,
    ) -> Any:
        """Log tool execution error."""
        self.context.add_trace(
            "tool:error",
            "failed",
            str(error)
        )

    def on_agent_action(
        self,
        action: AgentAction,
        **kwargs: Any,
    ) -> Any:
        """Log agent action."""
        # Already logged by other callbacks
        pass

    def on_agent_finish(
        self,
        finish: AgentFinish,
        **kwargs: Any,
    ) -> Any:
        """Log agent completion."""
        if self.context.final_decision == "allowed":
            self.context.add_trace(
                "decision",
                "allowed",
                "Response delivered."
            )
