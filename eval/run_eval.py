"""Score the assistant on the golden set.

Usage:  python -m eval.run_eval
Checks per query: response kind (answer/refusal/...), cited source id, required
text, at most 3 sentences, and a valid https link in every response.
"""
from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from core import config
from core.pipeline import answer
from core.validator import split_sentences

GOLDEN = Path(__file__).with_name("golden_set.csv")
CHECKS = ["kind", "source", "contains", "<=3 sentences", "has link"]


def main() -> None:
    rows = list(csv.DictReader(open(GOLDEN, encoding="utf-8")))
    totals: Counter = Counter()
    failures = []
    for row in rows:
        r = answer(row["query"])
        checks = {
            "kind": r.kind == row["expected_kind"],
            "source": r.source_id == row["expected_source"],
            "contains": (not row["must_contain"]) or row["must_contain"].lower() in r.text.lower(),
            "<=3 sentences": len(split_sentences(r.text)) <= config.MAX_SENTENCES,
            "has link": r.url.startswith("https://"),
        }
        totals.update(k for k, ok in checks.items() if ok)
        if not all(checks.values()):
            failures.append((row["query"], [k for k, v in checks.items() if not v], r.kind, r.source_id, r.text[:120]))

    n = len(rows)
    print(f"Golden set: {n} queries  {dict(Counter(r['expected_kind'] for r in rows))}\n")
    for name in CHECKS:
        print(f"  {name:<14} {totals[name]:>3}/{n}  ({totals[name] / n:.0%})")
    passed = n - len(failures)
    print(f"\n  all checks     {passed:>3}/{n}  ({passed / n:.0%})")
    for q, bad, kind, sid, text in failures:
        print(f"  FAIL {q!r}: {bad}; got {kind}/{sid}: {text}")


if __name__ == "__main__":
    main()
