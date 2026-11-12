"""Hybrid retrieval over the chunk index (W3).

BM25 catches exact domain terms (TER, exit load, ELSS); TF-IDF cosine with
character n-grams catches spelling and phrasing variants. Results are fused with
reciprocal-rank fusion. A metadata filter keeps retrieval inside the scheme the
user asked about, plus AMC-wide documents.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from . import config

FRESH_TYPES = {"fund_facts", "factsheet", "ssd", "service_page", "guide", "faq"}
_TOKEN = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?%?")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


@dataclass
class Chunk:
    id: str
    source_id: str
    scheme: str
    doc_type: str
    text: str


class _BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.docs = [Counter(d) for d in docs]
        self.lens = np.array([len(d) for d in docs], dtype=float)
        self.avg = self.lens.mean() if len(docs) else 0.0
        df: Counter = Counter()
        for d in self.docs:
            df.update(d.keys())
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: list[str]) -> np.ndarray:
        out = np.zeros(len(self.docs))
        for i, d in enumerate(self.docs):
            norm = self.k1 * (1 - self.b + self.b * self.lens[i] / (self.avg or 1))
            s = 0.0
            for t in query:
                tf = d.get(t)
                if tf:
                    s += self.idf.get(t, 0.0) * tf * (self.k1 + 1) / (tf + norm)
            out[i] = s
        return out


class Index:
    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        self.bm25 = _BM25([tokenize(c.text) for c in chunks])
        self.tfidf = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, min_df=1)
        self.matrix = self.tfidf.fit_transform([c.text for c in chunks])

    def search(self, query: str, scheme: str | None = None, k: int = 4) -> list[tuple[Chunk, float]]:
        allowed = np.array([scheme is None or c.scheme in (scheme, "all") for c in self.chunks])
        if not allowed.any():
            return []
        bm = self.bm25.scores(tokenize(query))
        cos = (self.matrix @ self.tfidf.transform([query]).T).toarray().ravel()
        bm[~allowed] = -1
        cos[~allowed] = -1

        fused = np.zeros(len(self.chunks))
        for scores in (bm, cos):
            for rank, idx in enumerate(np.argsort(-scores)[:50]):
                if allowed[idx]:
                    fused[idx] += 1.0 / (60 + rank)
        # Freshness prior: monthly/recent documents beat the Nov-2025 KIM/SID on ties.
        for i, c in enumerate(self.chunks):
            if fused[i] > 0 and c.doc_type in FRESH_TYPES:
                fused[i] += 0.004
        order = [i for i in np.argsort(-fused)[:k] if fused[i] > 0 and bm[i] > 0]
        return [(self.chunks[i], float(fused[i])) for i in order]


@lru_cache(maxsize=1)
def get_index() -> Index:
    if not config.INDEX_PATH.exists():
        raise FileNotFoundError(
            f"No index at {config.INDEX_PATH}. Run: python -m ingest.fetch && python -m ingest.build_index"
        )
    rows = [json.loads(line) for line in config.INDEX_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    return Index([Chunk(**r) for r in rows])
