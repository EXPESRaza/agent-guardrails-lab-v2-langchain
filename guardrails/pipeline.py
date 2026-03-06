"""Pipeline tracing utilities for guardrails."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class TraceEvent:
    """
    Represents a single trace event in the guardrail pipeline.

    Each trace event captures what happened at a specific stage
    of processing (e.g., input validation, tool execution, output filtering).
    """

    stage: str
    """The pipeline stage where this event occurred (e.g., 'before_agent:deterministic')"""

    decision: str
    """The decision made at this stage (e.g., 'allowed', 'blocked', 'flagged')"""

    details: str
    """Human-readable description of what happened"""

    payload: Dict[str, Any] = field(default_factory=dict)
    """Additional structured data about this event"""
