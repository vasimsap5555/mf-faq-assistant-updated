# HDFC Mutual Fund Facts Desk

 **Live demo:** https://mf-faq-assistant-updated-j4hvywtrboetubmdm5cmhl.streamlit.app/

A facts-only FAQ assistant for four HDFC Mutual Fund schemes, built for the "Mutual Fund FAQs (Facts-Only Q&A)" milestone. Product context: **Groww**. Every answer is at most 3 sentences, cites exactly one official source, and shows "Last updated from sources". Opinion, portfolio and performance questions are politely refused with an educational link. Messages containing personal details are blocked before any processing.

## Scope

| | |
|---|---|
| Product | Groww |
| AMC | HDFC Mutual Fund |
| Schemes | HDFC Flexi Cap Fund, HDFC Large Cap Fund, HDFC Mid Cap Fund, HDFC ELSS Tax Saver |
| Sources | 24 official URLs from HDFC AMC and AMFI (`data/sources.csv`) |
| Facts answered | Expense ratio, exit load, minimum SIP, lock-in, riskometer, benchmark, fund manager, investment objective, inception date, plans and options, minimum redemption, cut-off time, NAV (where to find it), how to download account and capital-gains statements, and definitions of TER, exit load, SIP, ELSS and NAV |

## Setup

Requires Python 3.10 or newer.

```bash
pip install -r requirements.txt

# Optional: rebuild the corpus from the official URLs (the index is already included)
python -m ingest.fetch          # downloads PDFs into data/raw/
python -m ingest.build_index    # writes data/index/chunks.jsonl

streamlit run app.py
```

The app works fully offline with no API key. Optionally, an LLM can phrase answers for questions outside the fact store:

```bash
# Anthropic
export LLM_PROVIDER=anthropic ANTHROPIC_API_KEY=... LLM_MODEL=claude-haiku-5-5
# or any OpenAI-compatible endpoint (OpenAI, Groq, etc.)
export LLM_PROVIDER=openai LLM_API_KEY=... LLM_MODEL=<model> LLM_BASE_URL=https://api.groq.com/openai/v1
```

**Deploying (Streamlit Community Cloud or Hugging Face Spaces):** push the repo with `data/index/chunks.jsonl` committed, set `app.py` as the entry point, and add any LLM keys as secrets.

## How it works

```
question
  -> PII guard            blocks PAN, Aadhaar, email, phone, OTP, folio/account, card numbers; text is never stored
  -> intent router        ADVICE / PERFORMANCE / OUT_OF_SCOPE -> refusal template with an educational link
  -> entity resolver      which scheme + which fact (e.g. {elss, lock_in})
  -> clarify              asks for the scheme if a scheme-specific fact has none, or more than one
  -> fact store           50+ hand-verified answers in data/facts.json, each with source id and as-on date
  -> hybrid retrieval     BM25 + character TF-IDF, fused with reciprocal-rank fusion, filtered to the scheme
  -> generator            LLM grounded on retrieved chunks (optional) or extractive fallback with a quality gate
  -> validator            <= 3 sentences, no advice words, no return figures, every number must appear in the source
  -> response             text + one source link + "Last updated from sources: <date>"
```

Design choices worth noting:

- **Fact store first.** The high-frequency questions get deterministic, human-verified answers. This removes hallucination for the cases that matter most and makes the citation exact.
- **The model never writes URLs.** The LLM returns the id of the chunk it used; code maps that id to the URL from `sources.csv`.
- **Mixed questions are refused.** "What's the TER, and is it a good fund?" is treated as advice, so the bot never answers half of an advice question.
- **Freshness prior.** Monthly documents (Fund Facts, factsheet, scheme summary) outrank the November 2025 KIM/SID on ties, which keeps answers such as fund managers current.
- **Privacy.** PII is checked before logging or retrieval. `logs/events.jsonl` records only intent, scheme, attribute, source id and latency, never question text. The UI also hides blocked messages from the chat history.

## Project layout

```
app.py                  Streamlit UI
core/                   pipeline: pii, router, entities, facts, retriever, generator, validator, pipeline
ingest/                 fetch.py (downloads sources), build_index.py (parses and chunks)
data/sources.csv        source list (deliverable)
data/facts.json         verified fact store
data/snapshots/         text snapshots of HDFC web pages that block automated fetching
data/index/chunks.jsonl retrieval index (1,791 chunks)
eval/                   golden_set.csv (56 queries) and run_eval.py
samples/sample_qa.md    sample Q&A generated from the live pipeline (deliverable)
DISCLAIMER.md           disclaimer used in the UI (deliverable)
```

## Evaluation

`python -m eval.run_eval` checks each golden-set query for the right response type, the right cited source, the required fact text, at most 3 sentences, and a valid link.

| Check | Result (56 queries) |
|---|---|
| Correct response type (answer / refusal / PII block / clarify) | 56/56 |
| Correct cited source | 56/56 |
| Required fact present | 56/56 |
| 3 sentences or fewer | 56/56 |
| Link present | 56/56 |

These numbers are optimistic, because the golden set was written while the rules were being tuned. As an honest check, 18 new phrasings were run before any fixes and 13 were handled correctly. The 5 misses were "how is NAV calculated" refused as performance, a cut-off-time question refused as advice, "is Direct cheaper" not mapped to expense ratio, an ELSS 80C question answered with a sentence fragment, and "tell me about the fund" returning not-found. All five were then fixed and added to the golden set. Expect a similar miss rate on new phrasings; add failures to the golden set as you find them.

## Known limits

- **Four schemes, one AMC.** Other HDFC schemes and other AMCs get an out-of-scope reply.
- **Facts are only as current as the last refresh.** Expense ratios are as of 30 Sep 2026, riskometers as of 31 Aug 2026, and KIM/SID details as of 21 Nov 2025.
- **Minimum SIP for Large Cap and Mid Cap.** The scheme summary documents for these two could not be located, so their answers cite the KIM's Rs. 100 minimum purchase instead of SIP-frequency minimums. Flexi Cap has full SIP-frequency figures from its scheme summary document.
- **Riskometer levels are images in the PDFs.** They were read visually from the Fund Facts and the Flexi Cap scheme summary and entered by hand.
- **HDFC web pages block automated fetching.** Four pages (statements, capital-gains guide, SIP FAQ, AMFI glossary) are stored as short text snapshots written from the live pages on 12 Nov 2026. Re-check them when refreshing.
- **One fact per answer.** A question asking for two facts gets the first one only.
- **Fallback quality.** Without an LLM, questions outside the fact store use extractive answers from KIM/SID text, which is table-heavy. A quality gate returns "not found" rather than messy text, so some answerable long-tail questions will get "not found".
- **English only.** Hindi and other languages are not supported.
- **Rule-based routing.** Unusual phrasing can be misrouted. The router errs toward refusing when advice words appear.

## Refreshing data (monthly)

1. Update the Fund Facts and factsheet URLs in `data/sources.csv` to the latest month (the URL pattern is visible in the existing rows).
2. Run `python -m ingest.fetch --force` and `python -m ingest.build_index`.
3. Re-check and update the expense ratio, riskometer and fund manager entries in `data/facts.json` against the new documents, including their `as_on` dates.
4. Run `python -m eval.run_eval` and `python -m samples.make_samples`.

## Deliverables

| Deliverable | Where |
|---|---|
| Working prototype | `app.py` (deploy as above, or record a 3-minute demo) |
| Source list | `data/sources.csv` |
| README | this file |
| Sample Q&A | `samples/sample_qa.md` |
| Disclaimer snippet | `DISCLAIMER.md` |
