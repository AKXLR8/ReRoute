"""Prompt guardrails — detect injection, secrets, PII, jailbreak attempts."""

from __future__ import annotations

import re


class GuardrailViolation(Exception):
    def __init__(self, rule: str, detail: str) -> None:
        self.rule = rule
        self.detail = detail
        super().__init__(f"Guardrail '{rule}': {detail}")


# Ponytail: regex, not ML. Good enough for the common cases.
_SECRET_PATTERNS: dict[str, re.Pattern] = {
    "api_key": re.compile(
        r"(?:sk-[a-zA-Z0-9]{20,}|"
        r"AKIA[0-9A-Z]{16}|"
        r"ghp_[a-zA-Z0-9]{36}|"
        r"xox[bpras]-[a-zA-Z0-9-]+)",
        re.IGNORECASE,
    ),
    "jwt_token": re.compile(r"eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}"),
}

_PII_PATTERNS: dict[str, re.Pattern] = {
    "email": re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"),
    "phone": re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
}

_INJECTION_KEYWORDS = [
    "ignore previous instructions",
    "ignore all previous",
    "disregard your instructions",
    "you are now",
    "new instructions:",
    "system prompt:",
    "act as",
    "pretend you are",
    "jailbreak",
    "do anything now",
    "DAN:",
]


def flatten_text(content) -> str:
    """OpenAI-style list content ([{type: text, text: ...}, ...]) must be
    scanned too — otherwise vision/multimodal messages skip every rule."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            part["text"]
            for part in content
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        )
    return ""


class PromptGuard:
    """Scans messages for policy violations before sending to providers.

    Checks:
    - API keys / secrets
    - PII (email, phone, SSN)
    - Prompt injection attempts
    - Jailbreak patterns
    """

    def __init__(
        self,
        detect_secrets: bool = True,
        detect_pii: bool = True,
        detect_injection: bool = True,
    ) -> None:
        self.detect_secrets = detect_secrets
        self.detect_pii = detect_pii
        self.detect_injection = detect_injection

    def check(self, messages: list[dict]) -> None:
        """Raise GuardrailViolation if any rule is violated."""
        text = " ".join(flatten_text(m.get("content")) for m in messages)
        text_lower = text.lower()

        if self.detect_secrets:
            for name, pattern in _SECRET_PATTERNS.items():
                if pattern.search(text):
                    raise GuardrailViolation("secrets", f"Detected {name} in message")

        if self.detect_pii:
            for name, pattern in _PII_PATTERNS.items():
                if pattern.search(text):
                    raise GuardrailViolation("pii", f"Detected {name} in message")

        if self.detect_injection:
            for keyword in _INJECTION_KEYWORDS:
                if keyword in text_lower:
                    raise GuardrailViolation("injection", f"Detected pattern: '{keyword}'")
