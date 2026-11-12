"""Parse raw sources and snapshots into overlapping text chunks: data/index/chunks.jsonl."""
from __future__ import annotations

import json
import re

import pdfplumber
from bs4 import BeautifulSoup

from core import config

WINDOW, OVERLAP = 140, 35  # words

# Pages of the 140-page AMC factsheet that belong to our schemes (header match).
FACTSHEET_HEADS = {
    "HDFC Flexi Cap Fund": "flexi",
    "HDFC Large Cap Fund": "large",
    "HDFC Mid Cap Fund": "mid",
    "HDFC ELSS - Tax Saver Fund": "elss",
}


def _clean(text: str) -> str:
    """Drop lines garbled by rotated PDF text (mostly 1-2 letter fragments)."""
    keep = []
    for line in text.splitlines():
        toks = line.split()
        if not toks:
            continue
        short = sum(len(t) <= 2 for t in toks) / len(toks)
        if len(toks) >= 4 and short > 0.5:
            continue
        keep.append(line.strip())
    return re.sub(r"\s+", " ", " ".join(keep)).strip()


def _windows(text: str) -> list[str]:
    words = text.split()
    if len(words) <= WINDOW:
        return [text] if words else []
    out, step = [], WINDOW - OVERLAP
    for start in range(0, len(words), step):
        out.append(" ".join(words[start:start + WINDOW]))
        if start + WINDOW >= len(words):
            break
    return out


def _pdf_pages(path) -> list[str]:
    with pdfplumber.open(path) as pdf:
        return [p.extract_text() or "" for p in pdf.pages]


def main() -> None:
    rows: list[dict] = []
    for sid, src in config.load_sources().items():
        mode = src["fetch_mode"]
        units: list[tuple[str, str]] = []  # (scheme, text)

        if mode == "pdf":
            path = config.RAW_DIR / f"{sid}.pdf"
            if not path.exists():
                print(f"{sid}  missing raw file, run ingest.fetch first")
                continue
            pages = _pdf_pages(path)
            if src["doc_type"] == "factsheet":
                for page in pages:
                    head = page.strip().split("\n", 1)[0].strip()
                    scheme = FACTSHEET_HEADS.get(head)
                    if scheme:
                        units.append((scheme, page))
            else:
                units = [(src["scheme"], p) for p in pages]
        elif mode == "html":
            path = config.RAW_DIR / f"{sid}.html"
            if path.exists():
                soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="ignore"), "html.parser")
                for tag in soup(["script", "style", "nav", "header", "footer"]):
                    tag.decompose()
                units = [(src["scheme"], soup.get_text("\n"))]
        elif mode == "snapshot":
            path = config.SNAPSHOT_DIR / f"{sid}.md"
            if path.exists():
                units = [(src["scheme"], path.read_text(encoding="utf-8"))]

        n = 0
        for u_i, (scheme, text) in enumerate(units):
            for w in _windows(_clean(text)):
                if len(w.split()) < 12:
                    continue
                rows.append({
                    "id": f"{sid}-{u_i:03d}-{n:03d}",
                    "source_id": sid,
                    "scheme": scheme,
                    "doc_type": src["doc_type"],
                    "text": w,
                })
                n += 1
        print(f"{sid}  {n} chunks")

    config.INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(config.INDEX_PATH, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\n{len(rows)} chunks -> {config.INDEX_PATH}")


if __name__ == "__main__":
    main()
