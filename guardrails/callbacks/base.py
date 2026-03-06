"""Base callback infrastructure for guardrails."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from langchain_core.callbacks import BaseCallbackHandler

from guardrails.audit import AuditRecord
from guardrails.pipeline import TraceEvent
from guardrails.risk import RiskScore


@dataclass
class GuardrailsContext:
    """
    Shared context across all guardrail callbacks.

    This object is passed to all callbacks and stores state that accumulates
    during agent execution (risk score, trace events, triggered policies, etc).
    """

    # Risk tracking
    risk_score: RiskScore = field(default_factory=RiskScore)

    # Trace events for audit log
    trace_events: List[TraceEvent] = field(default_factory=list)

    # Triggered policy names
    triggered_policies: List[str] = field(default_factory=list)

    # Execution state
    paused: bool = False
    paused_tool: Optional[str] = None
    paused_args: Optional[Dict[str, Any]] = None

    # Input/output tracking
    user_input: str = ""
    processed_input: str = ""
    tool_used: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    final_output: str = ""
    final_decision: str = "allowed"

    # User approvals
    approvals: Dict[str, bool] = field(default_factory=dict)

    # Metadata
    meta: Dict[str, Any] = field(default_factory=dict)

    def add_trace(self, stage: str, decision: str, details: str, payload: Optional[Dict[str, Any]] = None):
        """Add a trace event."""
        self.trace_events.append(
            TraceEvent(
                stage=stage,
                decision=decision,
                details=details,
                payload=payload or {}
            )
        )

    def build_audit_record(self) -> AuditRecord:
        """Build final audit record from context."""
        from dataclasses import asdict
        return AuditRecord(
            timestamp_utc=AuditRecord.now(),
            user_input=self.user_input,
            processed_input=self.processed_input,
            final_output=self.final_output,
            final_decision=self.final_decision,
            risk_score=self.risk_score.to_dict(),
            triggered_policies=self.triggered_policies,
            trace=[asdict(t) for t in self.trace_events],
            tool_used=self.tool_used,
            tool_args=self.tool_args,
        )


class BaseGuardrailCallback(BaseCallbackHandler):
    """
    Base class for guardrail callbacks.

    Provides access to shared GuardrailsContext and common utilities.
    """

    def __init__(self, context: GuardrailsContext):
        super().__init__()
        self.context = context
