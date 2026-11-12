"""Resolve which scheme and which attribute a question is about (W1: identify the exact fact)."""
from __future__ import annotations

import re
from dataclasses import dataclass

from . import config


def _phrase(p: str) -> re.Pattern:
    return re.compile(r"(?<![a-z0-9])" + re.escape(p) + r"(?![a-z0-9])", re.I)


_SCHEME_PATTERNS = [(key, [_phrase(a) for a in meta["aliases"]]) for key, meta in config.SCHEMES.items()]
_REDEMPTION = re.compile(r"\b(redemption|redeem|withdraw(?:al)?|switch[- ]?out)\b", re.I)
_ATTR_PATTERNS = [(key, [_phrase(a) for a in phrases]) for key, phrases in config.ATTRIBUTES.items()]


@dataclass
class Entities:
    schemes: list[str]
    attribute: str | None

    @property
    def scheme(self) -> str | None:
        return self.schemes[0] if len(self.schemes) == 1 else None


def resolve(query: str) -> Entities:
    schemes = [key for key, pats in _SCHEME_PATTERNS if any(p.search(query) for p in pats)]
    attribute = next((key for key, pats in _ATTR_PATTERNS if any(p.search(query) for p in pats)), None)

    # "minimum redemption amount" is not a minimum-SIP question; let retrieval handle it.
    if attribute == "min_sip" and _REDEMPTION.search(query) and not re.search(r"\bsip\b", query, re.I):
        attribute = None

    # "entry load" is not an exit-load question.
    if attribute == "exit_load" and re.search(r"\bentry[- ]load\b", query, re.I):
        attribute = None

    # "ELSS lock-in?" and plain "lock-in" questions are about the ELSS scheme.
    if attribute == "lock_in" and not schemes:
        schemes = ["elss"]
    return Entities(schemes=schemes, attribute=attribute)
