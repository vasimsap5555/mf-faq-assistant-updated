"""End-to-end query pipeline. `answer(query)` is the only function the UI calls."""
from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import date

from . import config, entities, facts, generator, router, validator
from .pii import detect_pii
from .retriever import get_index


@dataclass
class Response:
    kind: str                 # answer | refusal | pii_block | clarify | not_found
    text: str
    source_id: str
    source_title: str
    url: str
    last_updated: str         # human-readable as-on date of the cited source
    intent: str = ""
    scheme: str | None = None
    attribute: str | None = None
    mode: str = ""            # fact | llm | extractive | template

    def to_markdown(self) -> str:
        return f"{self.text}\n\nSource: {self.url}\nLast updated from sources: {self.last_updated}"


def _fmt_date(iso: str) -> str:
    try:
        return date.fromisoformat(iso).strftime("%d %b %Y")
    except ValueError:
        return iso


def _cite(sid: str, as_on: str | None = None) -> dict:
    s = config.source(sid)
    return {
        "source_id": sid,
        "source_title": s["title"],
        "url": s["url"],
        "last_updated": _fmt_date(as_on or s["as_on"]),
    }


def _scheme_list() -> str:
    names = [m["name"] for m in config.SCHEMES.values()]
    return ", ".join(names[:-1]) + " and " + names[-1]


def _log(resp: Response, started: float) -> None:
    """Privacy-safe log: no query text, only routing metadata."""
    try:
        config.LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "ts": int(time.time()),
            "kind": resp.kind,
            "intent": resp.intent,
            "scheme": resp.scheme,
            "attribute": resp.attribute,
            "source_id": resp.source_id,
            "mode": resp.mode,
            "ms": int((time.time() - started) * 1000),
        }
        with open(config.LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(event) + "\n")
    except OSError:
        pass


def answer(query: str) -> Response:
    started = time.time()
    resp = _answer(query or "")
    _log(resp, started)
    return resp


def _answer(query: str) -> Response:
    # 1. PII guard: block before anything else touches the text.
    found = detect_pii(query)
    if found:
        return Response(
            kind="pii_block",
            text=(
                f"For your security, please don't share personal details such as your {', '.join(found)}. "
                "Your message was not processed or stored. You can ask the same question without them."
            ),
            intent="PII", mode="template", **_cite(config.LINK_EDU),
        )

    # 2. Route.
    r = router.route(query)
    ent = entities.resolve(query)

    if r.intent == router.GREETING:
        return Response(
            kind="clarify",
            text=f"Hi! Ask me a factual question about {_scheme_list()}, such as an expense ratio, exit load, minimum SIP or benchmark.",
            intent=r.intent, mode="template", **_cite(config.LINK_FUND_DOCS),
        )
    if r.intent == router.ADVICE:
        return Response(
            kind="refusal",
            text=(
                "I can only share factual information about these schemes, not advice on whether to buy, sell, hold "
                "or choose between funds. AMFI's investor booklet explains how to read and evaluate a mutual fund scheme."
            ),
            intent=r.intent, scheme=ent.scheme, attribute=ent.attribute, mode="template", **_cite(config.LINK_EDU),
        )
    if r.intent == router.PERFORMANCE:
        return Response(
            kind="refusal",
            text=(
                "I don't calculate, quote or compare returns. "
                "The official performance figures for each scheme are published in HDFC Mutual Fund's monthly factsheets."
            ),
            intent=r.intent, scheme=ent.scheme, attribute=ent.attribute, mode="template", **_cite(config.LINK_FACTSHEETS),
        )
    if r.intent == router.OUT_OF_SCOPE:
        return Response(
            kind="refusal",
            text=f"I only cover factual questions about {_scheme_list()}. For the full list of HDFC Mutual Fund scheme documents, see the link below.",
            intent=r.intent, mode="template", **_cite(config.LINK_FUND_DOCS),
        )

    # 3a. General definitions ("What is a TER?") with no scheme: answer from AMFI/AMC-wide material.
    generic_elss = ent.schemes == ["elss"] and not re.search(r"\bhdfc\b|tax saver fund", query, re.I)
    is_definition = router.DEFINITION.search(query) or (
        generic_elss and re.search(r"\b80c\b|tax (?:deduction|benefit)", query, re.I)
    ) or (ent.attribute == "nav" and re.search(r"\bhow\b.*\b(calculated|computed|works?)\b", query, re.I))
    nav_how = ent.attribute == "nav" and re.search(r"\bhow\b.*\b(calculated|computed|works?)\b|\bwhat is (?:a |the )?nav\W*$|meaning", query, re.I)
    if ent.attribute == "nav" and ent.schemes and not nav_how:
        return Response(
            kind="answer",
            text="NAVs change every business day, so I don't quote them here. HDFC Mutual Fund publishes the latest NAV of each scheme on its NAV page.",
            intent=r.intent, scheme=ent.scheme, attribute="nav", mode="template", **_cite(config.LINK_NAV),
        )
    if (not ent.schemes or generic_elss or nav_how) and is_definition:
        def_attr = ent.attribute or ("elss" if generic_elss else None)
        fact = facts.lookup("all", f"def_{def_attr}") if def_attr else None
        if fact:
            return Response(
                kind="answer", text=fact["answer"], intent=r.intent, attribute=ent.attribute,
                mode="fact", **_cite(fact["source_id"], fact["as_on"]),
            )
        return _rag(query, r.intent, ent, scheme_filter="all")

    # 3b. Broad "tell me about X": list what can be answered instead of guessing.
    if ent.scheme and not ent.attribute and re.search(
        r"\b(tell me about|details (?:of|on|about)|info(?:rmation)? (?:on|about)|overview|everything about)\b", query, re.I
    ):
        name = config.SCHEMES[ent.scheme]["name"]
        return Response(
            kind="clarify",
            text=f"I can answer specific facts about {name}: expense ratio, exit load, minimum SIP, lock-in, riskometer, benchmark, fund manager, objective, cut-off time or plans. Which one would you like?",
            intent=r.intent, scheme=ent.scheme, mode="template", **_cite(config.LINK_FUND_DOCS),
        )

    # 3c. Clarify when a scheme-specific fact has no single scheme.
    needs_scheme = ent.attribute and ent.attribute not in config.SCHEME_FREE_ATTRIBUTES
    if needs_scheme and ent.scheme is None:
        label = config.ATTRIBUTE_LABELS[ent.attribute]
        which = "one scheme at a time" if len(ent.schemes) > 1 else "which scheme you mean"
        return Response(
            kind="clarify",
            text=f"Please tell me {which} for the {label}: {_scheme_list()}.",
            intent=r.intent, attribute=ent.attribute, mode="template", **_cite(config.LINK_FUND_DOCS),
        )

    # 4. Fact store (deterministic, human-verified).
    fact = facts.lookup(ent.scheme, ent.attribute)
    if fact:
        return Response(
            kind="answer", text=fact["answer"], intent=r.intent, scheme=ent.scheme, attribute=ent.attribute,
            mode="fact", **_cite(fact["source_id"], fact["as_on"]),
        )

    # 5. Retrieval + generation for everything else.
    return _rag(query, r.intent, ent, scheme_filter=ent.scheme)


def _rag(query: str, intent: str, ent, scheme_filter: str | None) -> Response:
    hits = get_index().search(query, scheme=scheme_filter, k=4)
    chunks = [c for c, _ in hits]
    gen = generator.generate(query, chunks)
    chunk = next((c for c in chunks if c.id == gen.get("chunk_id")), chunks[0] if chunks else None)

    if chunk is None or gen["answer"] == generator.NOT_FOUND:
        return Response(
            kind="not_found", text=generator.NOT_FOUND + " The scheme documents are linked below.",
            intent=intent, scheme=ent.scheme, attribute=ent.attribute, mode=gen["mode"],
            **_cite(config.LINK_FUND_DOCS),
        )

    check = validator.validate(gen["answer"], chunk.text)
    if not check.ok and gen["mode"] == "llm":
        # One retry without the LLM: extractive text is copied from the source, so numbers always match.
        gen = generator._extractive(query, chunks)
        gen["mode"] = "extractive"
        chunk = next((c for c in chunks if c.id == gen["chunk_id"]), chunk)
        check = validator.validate(gen["answer"], chunk.text)
    if not check.ok:
        return Response(
            kind="not_found", text=generator.NOT_FOUND + " The scheme documents are linked below.",
            intent=intent, scheme=ent.scheme, attribute=ent.attribute, mode=gen["mode"],
            **_cite(config.LINK_FUND_DOCS),
        )

    return Response(
        kind="answer", text=check.text, intent=intent, scheme=ent.scheme, attribute=ent.attribute,
        mode=gen["mode"], **_cite(chunk.source_id),
    )


def as_dict(resp: Response) -> dict:
    return asdict(resp)
