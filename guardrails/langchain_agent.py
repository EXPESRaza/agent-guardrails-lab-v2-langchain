"""Langchain-based guardrailed agent implementation."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree

from guardrails.audit import AuditRecord
from guardrails.callbacks.base import GuardrailsContext
from guardrails.callbacks.audit import AuditLoggingCallbackHandler
from guardrails.callbacks.deterministic import DeterministicCallbackHandler
from guardrails.callbacks.guardrails_ai import GuardrailsAICallbackHandler
from guardrails.callbacks.hitl import HITLCallbackHandler, ApprovalRequiredException
from guardrails.callbacks.injection import PromptInjectionCallbackHandler
from guardrails.callbacks.model_based import ModelBasedCallbackHandler
from guardrails.callbacks.risk import RiskScoringCallbackHandler
from guardrails.deterministic import DeterministicPolicy
from guardrails.guardrails_ai_pii import GuardrailsAIPII
from guardrails.injection import PromptInjectionPolicy
from guardrails.langchain_tools import (
    SearchWebTool,
    SendEmailTool,
    DeleteRecordsTool,
    CustomerLookupTool,
)
from guardrails.model_based import ModelBasedPolicy
from guardrails.pipeline import TraceEvent
from guardrails.policy import PolicyConfig


class LangchainGuardrailedAgent:
    """
    Langchain-based agent with comprehensive guardrails.

    This agent uses a simplified implementation that works across langchain versions.
    It manually orchestrates tool selection using LLM and applies guardrails via callbacks.
    """

    def __init__(
        self,
        policy: PolicyConfig,
        deterministic: DeterministicPolicy,
        injection: PromptInjectionPolicy,
        model_based: ModelBasedPolicy,
        pii: GuardrailsAIPII,
        openai_api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
    ):
        self.policy = policy
        self.deterministic = deterministic
        self.injection = injection
        self.model_based = model_based
        self.pii = pii

        # Create Langchain tools
        self.tools = {
            "search_web": SearchWebTool(),
            "send_email": SendEmailTool(),
            "delete_records": DeleteRecordsTool(),
            "customer_lookup": CustomerLookupTool(),
        }

        # Create LLM
        self.llm = ChatOpenAI(
            model=model,
            api_key=openai_api_key,
            temperature=0,
        )

    @traceable(name="tool_selection", run_type="chain")
    def _select_tool(self, user_input: str, context: GuardrailsContext) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Use LLM to intelligently select which tool to use."""

        # Create tool descriptions for LLM
        tool_descriptions = {
            "search_web": "Search the web for information. Use when user wants to find, lookup, or search for information online.",
            "send_email": "Send an email message. Use when user wants to send, email, notify, or message someone.",
            "delete_records": "Delete records from database. Use when user explicitly wants to delete, remove, or drop data.",
            "customer_lookup": "Look up customer information. Use when user wants to find customer details, check customer records, or retrieve customer data.",
        }

        system_prompt = f"""You are a tool selection assistant. Based on the user's request, determine which tool to use.

Available tools:
{json.dumps(tool_descriptions, indent=2)}

Respond ONLY with a JSON object in this format:
{{"tool": "tool_name", "reason": "why this tool"}}

If no tool is needed, respond with:
{{"tool": null, "reason": "explanation"}}"""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"User request: {user_input}")
            ]

            response = self.llm.invoke(messages)
            result = json.loads(response.content.strip())

            selected_tool = result.get("tool")
            if selected_tool and selected_tool in self.tools:
                # Extract arguments based on tool
                args = self._extract_tool_args(selected_tool, user_input)
                return selected_tool, args

        except Exception as e:
            context.add_trace("tool_selection", "error", f"LLM tool selection failed: {e}")

        return None

    def _extract_tool_args(self, tool_name: str, user_input: str) -> Dict[str, Any]:
        """Extract tool arguments from user input."""
        # Simple argument extraction - in production, this would use LLM
        if tool_name == "search_web":
            return {"query": user_input}
        elif tool_name == "send_email":
            return {
                "to": "team@company.com",
                "subject": "Message from agent",
                "body": user_input
            }
        elif tool_name == "delete_records":
            return {
                "table": "user",
                "where": "1=1"
            }
        elif tool_name == "customer_lookup":
            return {"query": user_input}
        return {}

    @traceable(
        name="guardrailed_agent_run",
        run_type="chain",
        metadata={"framework": "langchain", "version": "0.3"}
    )
    def run(
        self,
        user_text: str,
        approvals: Dict[str, bool]
    ) -> Tuple[str, List[TraceEvent], Dict[str, Any], AuditRecord]:
        """
        Run the guardrailed agent.

        Args:
            user_text: User input text
            approvals: Dict of tool approvals from HITL interface

        Returns:
            Tuple of (response, trace_events, meta, audit_record)
        """
        # Initialize context
        context = GuardrailsContext(
            user_input=user_text,
            processed_input=user_text,
            approvals=approvals,
        )

        # Create callback handlers
        callbacks = {
            'deterministic': DeterministicCallbackHandler(context, self.deterministic),
            'injection': PromptInjectionCallbackHandler(context, self.injection),
            'model_based': ModelBasedCallbackHandler(context, self.model_based),
            'pii': GuardrailsAICallbackHandler(context, self.pii),
            'risk': RiskScoringCallbackHandler(context, self.policy),
            'hitl': HITLCallbackHandler(context, self.policy),
            'audit': AuditLoggingCallbackHandler(context),
        }

        try:
            # Phase 1: Before-agent guardrails (input checks)
            self._trace_guardrail("deterministic_check", "Checking for banned keywords", {
                "input": user_text,
                "keywords": self.policy.banned_keywords
            })
            blocked, hits = self.deterministic.check(user_text)
            if hits:
                context.risk_score.add(35, f"Deterministic banned keywords: {hits}")
                context.triggered_policies.append("deterministic_keywords")
                context.add_trace("before_agent:deterministic", "flagged", f"Matched keywords: {hits}")
                self._trace_guardrail("deterministic_result", "FLAGGED", {"hits": hits})
            else:
                context.add_trace("before_agent:deterministic", "clear", "No banned keywords matched.")
                self._trace_guardrail("deterministic_result", "CLEAR", {})

            # Injection check
            self._trace_guardrail("injection_check", "Checking for prompt injection", {
                "input": user_text,
                "patterns": self.policy.injection_patterns
            })
            inj_blocked, inj_hits = self.injection.check(user_text)
            if inj_hits:
                context.risk_score.add(40, f"Prompt injection patterns: {inj_hits}")
                context.triggered_policies.append("prompt_injection")
                context.add_trace("before_agent:prompt_injection", "flagged", f"Matched patterns: {inj_hits}")
                self._trace_guardrail("injection_result", "FLAGGED", {"hits": inj_hits})
            else:
                context.add_trace("before_agent:prompt_injection", "clear", "No prompt injection pattern found.")
                self._trace_guardrail("injection_result", "CLEAR", {})

            # Model-based input check
            self._trace_guardrail("model_based_input_check", "LLM safety classification (input)", {
                "input": user_text
            })
            label, expl = self.model_based.classify(user_text)
            context.add_trace("before_agent:model_based", label, expl)
            self._trace_guardrail("model_based_input_result", label.upper(), {
                "explanation": expl,
                "classification": label
            })
            if label == "unsafe":
                context.risk_score.add(30, "Model-based classifier marked input unsafe.")
                context.triggered_policies.append("model_based_input")

            # PII input processing
            self._trace_guardrail("pii_input_check", "Checking for PII in input", {
                "input": user_text,
                "strategies": self.policy.pii_strategies
            })
            processed_input, notes, pii_block, pii_triggers = self.pii.process(user_text, is_input=True)
            context.processed_input = processed_input
            for note in notes:
                context.add_trace("pii:input", "note", note)
            if pii_triggers:
                context.risk_score.add(20, f"PII detected in input: {pii_triggers}")
                context.triggered_policies.extend(pii_triggers)

            self._trace_guardrail("pii_input_result", "BLOCKED" if pii_block else "PROCESSED", {
                "triggers": pii_triggers,
                "processed": processed_input,
                "notes": notes
            })

            if pii_block:
                context.final_output = "🚫 Blocked by PII input policy."
                context.final_decision = "blocked"
                context.add_trace("decision", "blocked", context.final_output)
                audit = context.build_audit_record()
                self._log_final_decision(context)
                return context.final_output, context.trace_events, context.meta, audit

            # Phase 2: Tool selection and execution
            tool_selection = self._select_tool(processed_input, context)

            if tool_selection:
                tool_name, tool_args = tool_selection
                context.tool_used = tool_name
                context.tool_args = tool_args

                context.add_trace("agent:tool_routing", "selected", f"Tool selected: {tool_name}", {"args": tool_args})

                # Add tool risk
                tool_risk = self.policy.tool_risk_levels.get(tool_name, 0)
                context.risk_score.add(tool_risk, f"Tool selected: {tool_name}")

                self._trace_guardrail("risk_scoring", "Cumulative risk assessment", {
                    "tool": tool_name,
                    "tool_risk": tool_risk,
                    "total_risk": context.risk_score.total,
                    "block_threshold": self.policy.block_threshold,
                    "review_threshold": self.policy.review_threshold
                })

                # Check if risk exceeds block threshold
                if context.risk_score.total >= self.policy.block_threshold:
                    context.final_output = "🚫 Blocked due to high composite risk score."
                    context.final_decision = "blocked"
                    context.add_trace("decision", "blocked", context.final_output, {"risk": context.risk_score.total})
                    audit = context.build_audit_record()
                    self._log_final_decision(context)
                    return context.final_output, context.trace_events, context.meta, audit

                # Check HITL approval
                require_approval = (
                    self.policy.hitl_require_approval.get(tool_name, False)
                    or context.risk_score.total >= self.policy.review_threshold
                )

                self._trace_guardrail("hitl_check", "Human-in-the-loop approval check", {
                    "tool": tool_name,
                    "require_approval": require_approval,
                    "approved": approvals.get(tool_name, False),
                    "risk": context.risk_score.total
                })

                if require_approval and not approvals.get(tool_name, False):
                    context.final_output = f"⏸️ Paused for human approval before {tool_name}."
                    context.final_decision = "paused_for_approval"
                    context.paused = True
                    context.paused_tool = tool_name
                    context.meta["paused_tool"] = tool_name
                    context.meta["paused_args"] = tool_args
                    context.add_trace("hitl", "paused", context.final_output, {"risk": context.risk_score.total})
                    audit = context.build_audit_record()
                    self._log_final_decision(context)
                    return context.final_output, context.trace_events, context.meta, audit

                # Execute tool
                self._trace_guardrail("tool_execution", f"Executing {tool_name}", {
                    "tool": tool_name,
                    "args": tool_args
                })
                tool = self.tools[tool_name]
                tool_output = tool._run(**tool_args)
                context.add_trace("tool:execute", "ok", tool_output)
                self._trace_guardrail("tool_result", "Tool execution successful", {
                    "output": tool_output
                })

                output = f"✅ Request processed.\n\nTool output:\n{tool_output}"
            else:
                # No tool needed
                self._trace_guardrail("no_tool", "No tool needed for this request", {})
                output = f"✅ Request processed.\n\nEcho (sanitized input): {processed_input}"

            # Phase 3: After-agent guardrails (output checks)
            # PII output processing
            self._trace_guardrail("pii_output_check", "Checking for PII in output", {
                "output": output
            })
            processed_output, output_notes, output_blocked, output_triggers = self.pii.process(output, is_input=False)
            for note in output_notes:
                context.add_trace("pii:output", "note", note)
            if output_triggers:
                context.triggered_policies.extend(output_triggers)

            self._trace_guardrail("pii_output_result", "BLOCKED" if output_blocked else "PROCESSED", {
                "triggers": output_triggers,
                "processed": processed_output,
                "notes": output_notes
            })

            if output_blocked:
                context.final_output = "🚫 Output blocked by PII output policy."
                context.final_decision = "blocked"
                context.add_trace("after_agent:pii", "blocked", context.final_output)
                audit = context.build_audit_record()
                self._log_final_decision(context)
                return context.final_output, context.trace_events, context.meta, audit

            # Model-based output check
            self._trace_guardrail("model_based_output_check", "LLM safety classification (output)", {
                "output": processed_output
            })
            out_label, out_expl = self.model_based.classify(processed_output)
            context.add_trace("after_agent:model_based", out_label, out_expl)
            self._trace_guardrail("model_based_output_result", out_label.upper(), {
                "explanation": out_expl,
                "classification": out_label
            })
            if out_label == "unsafe":
                processed_output = "⚠️ Unsafe output was intercepted and replaced with a compliant response."
                context.add_trace("after_agent:mutation", "mutated", processed_output)
                context.triggered_policies.append("model_based_output")

            context.final_output = processed_output
            context.final_decision = "allowed"
            context.add_trace("decision", "allowed", "Response delivered.")
            self._log_final_decision(context)

        except ApprovalRequiredException as e:
            # This shouldn't happen in this implementation but keep for compatibility
            pass
        except Exception as e:
            # Handle unexpected errors
            error_msg = str(e)
            context.final_output = f"⚠️ An error occurred: {error_msg}"
            context.final_decision = "error"
            context.add_trace("error", "exception", error_msg)

        # Build audit record
        audit = context.build_audit_record()

        return (
            context.final_output,
            context.trace_events,
            context.meta,
            audit
        )

    def _trace_guardrail(self, name: str, description: str, metadata: Dict[str, Any]):
        """Log a guardrail step to LangSmith."""
        if os.getenv("LANGCHAIN_TRACING_V2") == "true":
            try:
                from langsmith import traceable
                # Create a sub-span for this guardrail
                run_tree = get_current_run_tree()
                if run_tree:
                    run_tree.create_child(
                        name=name,
                        run_type="tool",
                        inputs={"description": description},
                        outputs=metadata,
                        extra={"guardrail": True}
                    ).end()
            except Exception:
                # Silently ignore tracing errors
                pass

    def _log_final_decision(self, context: GuardrailsContext):
        """Log the final decision to LangSmith."""
        if os.getenv("LANGCHAIN_TRACING_V2") == "true":
            try:
                run_tree = get_current_run_tree()
                if run_tree:
                    run_tree.create_child(
                        name="final_decision",
                        run_type="tool",
                        inputs={
                            "decision": context.final_decision,
                            "risk_score": context.risk_score.to_dict(),
                            "triggered_policies": context.triggered_policies
                        },
                        outputs={
                            "output": context.final_output,
                            "paused": context.paused,
                            "tool_used": context.tool_used
                        },
                        extra={"final": True}
                    ).end()
            except Exception:
                # Silently ignore tracing errors
                pass
