"""PII guard. Runs first, before logging, retrieval or any model call.

Only the *type* of PII found is returned; the matched text is never kept.
"""
from __future__ import annotations

import re

_PATTERNS: dict[str, re.Pattern] = {
    "PAN": re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.I),
    "Aadhaar": re.compile(r"\b[2-9]\d{3}[\s-]?\d{4}[\s-]?\d{4}\b"),
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "phone number": re.compile(r"(?<!\d)(?:\+?91[\s-]?|0)?[6-9]\d{9}(?!\d)"),
    "OTP": re.compile(r"\b(?:otp|one[\s-]?time[\s-]?password|pin|password)\b\D{0,15}\d{4,8}\b", re.I),
    "account or folio number": re.compile(
        r"\b(?:folio|account|a/c|acct|bank)\b(?:\s*(?:no\.?|number|#|is|:))*\s*[\w/-]*\d{6,18}\b", re.I
    ),
    "card number": re.compile(r"\b(?:\d{4}[\s-]?){3}\d{4}\b"),
}


def detect_pii(text: str) -> list[str]:
    """Return the kinds of PII present in `text` (empty list if none)."""
    return [kind for kind, pat in _PATTERNS.items() if pat.search(text or "")]
