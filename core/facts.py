"""Structured fact store: deterministic answers for the high-frequency attributes."""
from __future__ import annotations

import json
from functools import lru_cache

from . import config


@lru_cache(maxsize=1)
def _facts() -> dict[tuple[str, str], dict]:
    data = json.loads(config.FACTS_PATH.read_text(encoding="utf-8"))
    return {(f["scheme"], f["attribute"]): f for f in data["facts"]}


def lookup(scheme: str | None, attribute: str | None) -> dict | None:
    if not attribute:
        return None
    if scheme == "all" or attribute in config.SCHEME_FREE_ATTRIBUTES:
        return _facts().get(("all", attribute))
    if scheme:
        return _facts().get((scheme, attribute))
    return None
