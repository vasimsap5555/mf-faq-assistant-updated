"""Central configuration: paths, scheme catalogue, attribute vocabulary, fixed links."""
from __future__ import annotations

import csv
import os
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW_DIR = DATA / "raw"
SNAPSHOT_DIR = DATA / "snapshots"
INDEX_PATH = DATA / "index" / "chunks.jsonl"
FACTS_PATH = DATA / "facts.json"
SOURCES_PATH = DATA / "sources.csv"
LOG_PATH = ROOT / "logs" / "events.jsonl"

AMC_NAME = "HDFC Mutual Fund"

# Canonical scheme keys -> display name + aliases users actually type.
SCHEMES: dict[str, dict] = {
    "flexi": {
        "name": "HDFC Flexi Cap Fund",
        "aliases": ["flexi cap", "flexicap", "flexi-cap", "flexi", "hdfc equity fund"],
    },
    "large": {
        "name": "HDFC Large Cap Fund",
        "aliases": ["large cap", "largecap", "large-cap", "top 100", "top100", "bluechip"],
    },
    "mid": {
        "name": "HDFC Mid Cap Fund",
        "aliases": ["mid cap", "midcap", "mid-cap", "mid cap opportunities", "mid-cap opportunities"],
    },
    "elss": {
        "name": "HDFC ELSS Tax Saver",
        "aliases": ["elss", "tax saver", "taxsaver", "tax-saver", "tax saving", "80c"],
    },
}

# Attribute keys -> trigger phrases. Order matters: first match wins in entity resolution.
ATTRIBUTES: dict[str, list[str]] = {
    "capital_gains_statement": ["capital gains", "capital gain", "capital-gain", "capital-gains", "realised gain", "realized gain", "tax statement"],
    "account_statement": ["account statement", "statement", "cas", "consolidated account"],
    "expense_ratio": ["cheaper", "costlier", "expense ratio", "ter", "total expense", "expense", "fees", "charges", "cost of the fund"],
    "exit_load": ["exit load", "exit-load", "redemption charge", "load"],
    "min_redemption": ["minimum redemption", "min redemption", "redemption amount", "minimum withdrawal",
                       "minimum switch out", "minimum switch-out"],
    "min_sip": ["minimum sip", "min sip", "sip amount", "minimum investment", "minimum amount",
                "minimum", "least amount", "start sip", "sip"],
    "lock_in": ["lock-in", "lock in", "lockin", "locked", "lock period", "before 3 years", "before three years",
                "redeem before", "withdraw before", "sell before"],
    "riskometer": ["riskometer", "risk-o-meter", "risk level", "risk category", "how risky", "risk"],
    "benchmark": ["benchmark", "benchmarked", "index it tracks", "compared against"],
    "cut_off": ["today's nav", "todays nav", "same day nav", "same-day nav", "cut-off", "cut off", "cutoff", "applicable nav", "which nav", "time to invest", "nav applicable"],
    "nav": ["nav", "net asset value"],
    "fund_manager": ["fund manager", "fund managers", "manager", "managed by", "who manages", "who runs"],
    "objective": ["objective", "investment objective", "aim of the fund", "goal of the fund", "invests in", "strategy"],
    "inception_date": ["inception", "launched", "launch date", "launch", "allotment date", "how old", "started"],
    "plans_options": ["plans", "plan options", "options", "idcw", "growth option", "dividend option", "direct plan or regular"],
}

SCHEME_FREE_ATTRIBUTES = {"capital_gains_statement", "account_statement"}

ATTRIBUTE_LABELS = {
    "expense_ratio": "expense ratio",
    "exit_load": "exit load",
    "min_sip": "minimum SIP",
    "lock_in": "lock-in",
    "riskometer": "riskometer",
    "benchmark": "benchmark",
    "capital_gains_statement": "capital-gains statement",
    "account_statement": "account statement",
    "min_redemption": "minimum redemption",
    "fund_manager": "fund manager",
    "cut_off": "cut-off time",
    "nav": "NAV",
    "objective": "investment objective",
    "inception_date": "inception date",
    "plans_options": "plans and options",
}

# Fixed links used by refusals and clarifications (all present in sources.csv).
LINK_EDU = "S22"          # AMFI investor booklet
LINK_FACTSHEETS = "S20"   # HDFC MF factsheets page (performance questions)
LINK_FUND_DOCS = "S21"    # HDFC MF KIM/SID listing (clarifications)
LINK_NAV = "S24"          # HDFC MF NAV page (daily NAV values)

MAX_SENTENCES = 3

# Optional LLM. Leave unset to run fully offline (facts + extractive answers).
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "").lower()  # "anthropic" | "openai" (any OpenAI-compatible, e.g. Groq)
LLM_MODEL = os.getenv("LLM_MODEL", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")


@lru_cache(maxsize=1)
def load_sources() -> dict[str, dict]:
    with open(SOURCES_PATH, newline="", encoding="utf-8") as fh:
        return {row["id"]: row for row in csv.DictReader(fh)}


def source(sid: str) -> dict:
    return load_sources()[sid]
