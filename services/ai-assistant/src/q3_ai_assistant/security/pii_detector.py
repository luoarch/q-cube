"""PII detection for Brazilian financial context.

Detects CPF, CNPJ, email addresses, phone numbers, and other PII
that should not appear in AI-generated content.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PIIMatch:
    pii_type: str
    value: str
    start: int
    end: int


# CPF: 000.000.000-00 or 00000000000
_CPF_PATTERN = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")

# CNPJ: 00.000.000/0000-00 or 00000000000000
_CNPJ_PATTERN = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")

# Email
_EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")

# Brazilian phone: (XX) XXXXX-XXXX or (XX) XXXX-XXXX
_PHONE_PATTERN = re.compile(r"\(\d{2}\)\s?\d{4,5}-?\d{4}")

# Credit card (basic: 4 groups of 4 digits)
_CARD_PATTERN = re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b")

_PATTERNS = [
    ("cpf", _CPF_PATTERN),
    ("cnpj", _CNPJ_PATTERN),
    ("email", _EMAIL_PATTERN),
    ("phone", _PHONE_PATTERN),
    ("credit_card", _CARD_PATTERN),
]


def detect_pii(text: str) -> list[PIIMatch]:
    """Scan text for PII patterns. Returns list of matches."""
    matches: list[PIIMatch] = []
    for pii_type, pattern in _PATTERNS:
        for m in pattern.finditer(text):
            # Filter out false positives for CPF/CNPJ
            raw = re.sub(r"[.\-/]", "", m.group())
            if pii_type == "cpf" and len(raw) != 11:
                continue
            if pii_type == "cnpj" and len(raw) != 14:
                continue
            matches.append(PIIMatch(
                pii_type=pii_type,
                value=m.group(),
                start=m.start(),
                end=m.end(),
            ))
    return matches


def contains_pii(text: str) -> bool:
    """Quick check — does the text contain any PII?"""
    return len(detect_pii(text)) > 0


def redact_pii(text: str) -> str:
    """Replace detected PII with redaction markers."""
    matches = detect_pii(text)
    if not matches:
        return text

    # Process in reverse order to preserve offsets
    result = text
    for m in sorted(matches, key=lambda x: x.start, reverse=True):
        replacement = f"[{m.pii_type.upper()}_REDACTED]"
        result = result[:m.start] + replacement + result[m.end:]
    return result
