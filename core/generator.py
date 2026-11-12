"""Answer generation for questions the fact store does not cover (W2).

If an LLM is configured, it answers ONLY from the retrieved chunks and returns
the id of the chunk it used; code maps that id to a URL, so the model can never
invent a link. Without an LLM, an extractive fallback picks the most relevant
sentences from the top chunk.
"""
from __future__ import annotations

import json
import os
import re

import requests

from . import config
from .retriever import Chunk, tokenize

NOT_FOUND = "I couldn't find this in the official sources I use."

SYSTEM_PROMPT = f"""You are a facts-only assistant for {config.AMC_NAME} schemes.
Answer ONLY from the CONTEXT chunks. If the answer is not in them, set "answer" to exactly: "{NOT_FOUND}"

Rules:
- At most 3 short sentences. Lead with the fact. Copy figures exactly as written in the chunk.
- Mention the scheme name, and the plan (Direct/Regular) when the fact differs by plan.
- Never give opinions, recommendations, comparisons of merit, predictions or return figures.
- Do not write URLs or document names; the system adds the citation.
- Reply with JSON only, no markdown: {{"answer": "...", "chunk_id": "<id of the single chunk you used>"}}"""


def _format_context(chunks: list[Chunk]) -> str:
    return "\n\n".join(f"[{c.id} | {c.doc_type} | scheme={c.scheme}]\n{c.text}" for c in chunks)


def _call_llm(query: str, chunks: list[Chunk]) -> dict | None:
    provider = config.LLM_PROVIDER
    user = f"CONTEXT:\n{_format_context(chunks)}\n\nQUESTION: {query}"
    try:
        if provider == "anthropic":
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": os.environ["ANTHROPIC_API_KEY"],
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": config.LLM_MODEL or "claude-haiku-5-5",
                    "max_tokens": 300,
                    "temperature": 0,
                    "system": SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": user}],
                },
                timeout=30,
            )
            r.raise_for_status()
            text = "".join(b.get("text", "") for b in r.json()["content"])
        elif provider == "openai":
            r = requests.post(
                f"{config.LLM_BASE_URL.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {os.environ['LLM_API_KEY']}"},
                json={
                    "model": config.LLM_MODEL,
                    "temperature": 0,
                    "max_tokens": 300,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user},
                    ],
                },
                timeout=30,
            )
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"]
        else:
            return None
        text = re.sub(r"^```(?:json)?|```$", "", text.strip()).strip()
        return json.loads(text)
    except Exception:  # network, auth, or malformed JSON -> fall back to extractive
        return None


_STOP = set("""what which who whom whose when where why how the and for are was were is does did can could
would should with from that this these those about into hdfc fund funds scheme schemes mutual flexi large mid cap
elss tax saver plan direct regular please tell know""".split())
_SENT_SPLIT = re.compile(r"(?<=[.;])\s+(?=[A-Z(•-])|\s+•\s+")


_JUNK = re.compile(r"\$\$|\||\.{4,}|\bPage \d|\(An open[- ]ended|Mutual Fund Investments are subject", re.I)


_OUR_SCHEMES = [m["name"].lower() for m in config.SCHEMES.values()]
_HDFC_NAME = re.compile(r"HDFC(?: [A-Z][\w&-]*){1,4}", re.I)


def _mentions_other_scheme(sentence: str) -> bool:
    for m in _HDFC_NAME.finditer(sentence):
        name = m.group(0).lower()
        if name not in ("hdfc mutual fund", "hdfc amc", "hdfc asset management company") and not any(
            name.startswith(o) or o.startswith(name) for o in _OUR_SCHEMES
        ):
            return True
    return False


def _is_clean(sentence: str) -> bool:
    if _mentions_other_scheme(sentence):
        return False
    toks = sentence.split()
    if not sentence[:1].isupper() and not sentence[:1].isdigit():
        return False  # fragment cut mid-sentence by chunking
    if len(toks) < 6 or len(toks) > 60 or _JUNK.search(sentence):
        return False
    numeric = sum(any(ch.isdigit() for ch in t) for t in toks) / len(toks)
    short = sum(len(t) <= 2 for t in toks) / len(toks)
    return numeric <= 0.3 and short <= 0.45


def _extractive(query: str, chunks: list[Chunk]) -> dict:
    """Pick up to two clean, on-topic sentences from ONE of the top chunks."""
    q_toks = tokenize(query)
    q = {t for t in q_toks if len(t) > 2 and t not in _STOP}
    q_bigrams = {b for b in zip(q_toks, q_toks[1:]) if not (b[0] in _STOP and b[1] in _STOP)}
    if not q:
        return {"answer": NOT_FOUND, "chunk_id": chunks[0].id}

    def score(sent: str) -> float:
        toks = tokenize(sent)
        return len(q & set(toks)) + 2 * len(q_bigrams & set(zip(toks, toks[1:])))

    best_chunk, best_pick, best_total = None, [], 0.0
    for c in chunks[:3]:
        sentences = [x.strip(" •-") for x in _SENT_SPLIT.split(c.text)]
        scored = sorted(
            ((score(x), i, x) for i, x in enumerate(sentences) if _is_clean(x)), key=lambda t: (-t[0], t[1])
        )
        pick = [t for t in scored[:2] if t[0] >= max(2, len(q) * 0.5)]
        total = sum(t[0] for t in pick)
        if total > best_total:
            best_chunk, best_pick, best_total = c, pick, total
    if not best_pick:
        return {"answer": NOT_FOUND, "chunk_id": chunks[0].id}
    text = " ".join(x if x.endswith(".") else x + "." for _, _, x in sorted(best_pick, key=lambda t: t[1]))
    return {"answer": text, "chunk_id": best_chunk.id}


def generate(query: str, chunks: list[Chunk]) -> dict:
    """Return {"answer", "chunk_id", "mode"}."""
    if not chunks:
        return {"answer": NOT_FOUND, "chunk_id": None, "mode": "none"}
    out = _call_llm(query, chunks) if config.LLM_PROVIDER else None
    if out and out.get("answer"):
        out["mode"] = "llm"
        return out
    out = _extractive(query, chunks)
    out["mode"] = "extractive"
    return out
