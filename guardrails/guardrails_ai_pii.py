"""Guardrails-AI integration for PII detection and handling."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

# Note: Guardrails-AI library integration
# For now, we'll use regex-based detection as a fallback since Guardrails-AI
# DetectPII validator may require additional configuration and API keys.
# This can be enhanced to use actual Guardrails-AI validators when available.

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
CC_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
APIKEY_RE = re.compile(r"\b[A-Za-z0-9_\-]{24,}\b")


@dataclass
class GuardrailsAIConfig:
    """Configuration for Guardrails-AI PII detection."""
    pii_strategies: Dict[str, str]
    apply_to_input: bool = True
    apply_to_output: bool = True


def _mask(s: str, keep_last: int = 4) -> str:
    """Mask string keeping only last N characters."""
    if len(s) <= keep_last:
        return "*" * len(s)
    return "*" * (len(s) - keep_last) + s[-keep_last:]


def _hash(s: str) -> str:
    """Hash string using SHA256."""
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:12]


class GuardrailsAIPII:
    """
    PII detection and handling using Guardrails-AI patterns.

    This class provides the same interface as the original PIIMiddleware
    but is designed to integrate with Guardrails-AI validators.

    Strategies:
    - redact: Replace with [REDACTED_TYPE]
    - mask: Show only last 4 characters
    - hash: Replace with SHA256 hash
    - block: Block the entire request
    """

    def __init__(self, config: GuardrailsAIConfig):
        self.config = config
        self.detectors: Dict[str, re.Pattern] = {
            "email": EMAIL_RE,
            "credit_card": CC_RE,
            "ip": IP_RE,
            "api_key": APIKEY_RE,
        }

    def _apply_strategy(self, value: str, strategy: str, pii_type: str) -> Tuple[str, bool]:
        """
        Apply PII handling strategy to detected value.

        Returns:
            Tuple of (transformed_value, should_block)
        """
        if strategy == "redact":
            return f"[REDACTED_{pii_type.upper()}]", False
        if strategy == "mask":
            return _mask(value), False
        if strategy == "hash":
            return f"[HASH_{pii_type.upper()}:{_hash(value)}]", False
        if strategy == "block":
            return value, True
        return value, False

    def process(self, text: str, *, is_input: bool) -> Tuple[str, List[str], bool, List[str]]:
        """
        Process text for PII detection and handling.

        Args:
            text: Input text to process
            is_input: True if processing input, False if processing output

        Returns:
            Tuple of (processed_text, notes, blocked, triggers)
            - processed_text: Text with PII handling applied
            - notes: List of processing notes
            - blocked: True if request should be blocked
            - triggers: List of triggered PII policies (format: "pii:type:strategy")
        """
        if not text:
            return text, [], False, []

        notes: List[str] = []
        triggered: List[str] = []
        blocked = False
        out = text

        # Check configuration applicability
        if is_input and not self.config.apply_to_input:
            return text, [], False, []
        if not is_input and not self.config.apply_to_output:
            return text, [], False, []

        # Process each PII type
        for pii_type, strategy in self.config.pii_strategies.items():
            detector = self.detectors.get(pii_type)
            if not detector:
                continue

            matches = list(detector.finditer(out))
            if not matches:
                continue

            # Process matches in reverse order to preserve indices
            for m in reversed(matches):
                found = m.group(0)
                transformed, should_block = self._apply_strategy(found, strategy, pii_type)
                triggered.append(f"pii:{pii_type}:{strategy}")

                if should_block:
                    blocked = True
                    notes.append(f"Blocked due to {pii_type}.")
                else:
                    notes.append(f"Applied {strategy} to {pii_type}.")
                    out = out[:m.start()] + transformed + out[m.end():]

        return out, notes, blocked, triggered
