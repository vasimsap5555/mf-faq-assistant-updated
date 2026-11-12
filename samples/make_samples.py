"""Regenerate samples/sample_qa.md from live pipeline output.  Usage: python -m samples.make_samples"""
from pathlib import Path

from core.pipeline import answer

QUERIES = [
    "What is the expense ratio of HDFC Flexi Cap Fund?",
    "ELSS lock-in?",
    "Minimum SIP for HDFC Flexi Cap Fund?",
    "Exit load of HDFC Mid Cap Fund?",
    "What is the benchmark of HDFC Large Cap Fund?",
    "How do I download my capital gains statement?",
    "Who manages HDFC ELSS Tax Saver?",
    "Should I buy HDFC Flexi Cap Fund?",
    "What were the 5-year returns of HDFC Mid Cap Fund?",
    "My PAN is ABCDE1234F, what is the exit load?",
]


def main() -> None:
    out = ["# Sample Q&A", "", "Generated from the live pipeline by `python -m samples.make_samples`.",
           "Each answer shows the response type, the single cited source and the as-on date.", ""]
    for i, q in enumerate(QUERIES, 1):
        r = answer(q)
        shown_q = "My PAN is [redacted], what is the exit load?" if r.kind == "pii_block" else q
        out += [
            f"## {i}. {shown_q}",
            "",
            f"**Type:** {r.kind}",
            "",
            r.text,
            "",
            f"Source: [{r.source_title}]({r.url})  ",
            f"Last updated from sources: {r.last_updated}",
            "",
        ]
    Path(__file__).with_name("sample_qa.md").write_text("\n".join(out), encoding="utf-8")
    print("wrote samples/sample_qa.md")


if __name__ == "__main__":
    main()
