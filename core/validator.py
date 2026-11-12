"""Deterministic checks on every generated answer before it reaches the user."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import config

_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
_ADVICE_WORDS = re.compile(
    r"\b(recommend|you should|should invest|good (?:choice|fund|option)|better than|worth investing|"
    r"ideal for you|suitable for you|i suggest|consider investing)\b",
    re.I,
)
_RETURN_CLAIM = re.compile(r"\b(returns?|cagr|xirr|delivered|grew|growth of)\b[^.]{0,40}\d", re.I)
_URL = re.compile(r"https?://\S+")
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


@dataclass
class Check:
    ok: bool
    text: str
    problems: list[str] = field(default_factory=list)


def _norm_num(n: str) -> str:
    return n.replace(",", "").rstrip(".")


def split_sentences(text: str) -> list[str]:
    # Protect "Rs. 100" and "No. 5" from being treated as sentence ends.
    # Protect "Rs. 100", "Mr. X", "p.m." etc. from being treated as sentence ends (placeholder is not whitespace).
    protected = re.sub(r"\b(Rs|No|Re|Mr|Ms|Dr|viz|i\.e|e\.g|p\.m|a\.m)\.\s", lambda m: m.group(0)[:-1] + "\u2063", text)
    return [s.replace("\u2063", " ") for s in _SENTENCE.split(protected.strip()) if s.strip()]


def validate(answer: str, evidence: str, check_numbers: bool = True) -> Check:
    problems: list[str] = []
    text = _URL.sub("", answer).strip()

    sentences = split_sentences(text)
    if len(sentences) > config.MAX_SENTENCES:
        sentences = sentences[: config.MAX_SENTENCES]
        text = " ".join(sentences)
        problems.append("trimmed to 3 sentences")

    if _ADVICE_WORDS.search(text):
        problems.append("advice language")
    if _RETURN_CLAIM.search(text):
        problems.append("return/performance figure")
    if check_numbers:
        ev = {_norm_num(n) for n in _NUMBER.findall(evidence)}
        missing = [n for n in _NUMBER.findall(text) if _norm_num(n) not in ev]
        if missing:
            problems.append(f"numbers not in source: {missing}")

    hard = [p for p in problems if p != "trimmed to 3 sentences"]
    return Check(ok=not hard, text=text, problems=problems)
