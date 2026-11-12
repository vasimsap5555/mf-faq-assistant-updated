"""Streamlit UI for the HDFC Mutual Fund facts-only FAQ assistant.

Run:  streamlit run app.py
"""
from __future__ import annotations

import html

import streamlit as st

from core import config
from core.pipeline import answer

st.set_page_config(page_title="HDFC MF Facts Desk", page_icon="📄", layout="centered")

EXAMPLES = [
    "What is the expense ratio of HDFC Flexi Cap Fund?",
    "What is the lock-in period for HDFC ELSS Tax Saver?",
    "How do I download my capital gains statement?",
]
DISCLAIMER = (
    "This assistant shares facts drawn only from official HDFC Mutual Fund, AMFI and SEBI public documents. "
    "It does not give investment advice, recommendations or return comparisons. Mutual fund investments are "
    "subject to market risks; read all scheme-related documents carefully. Please don't enter personal details "
    "such as PAN, Aadhaar, account or folio numbers, OTPs, email addresses or phone numbers."
)

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;500;600&family=Source+Serif+4:opsz,wght@8..60,600&display=swap');
:root {
  --paper: #F5F7F6; --ink: #17252F; --muted: #5B6B73; --rule: #D5DDDA;
  --teal: #0B6E6E; --teal-soft: #E3F0EE; --amber: #A86B12; --amber-soft: #F7EEDF;
}
html, body, [class*="css"], .stMarkdown, .stChatInput textarea { font-family: 'Public Sans', system-ui, sans-serif; }
.stApp { background: var(--paper); color: var(--ink); }
.block-container { max-width: 760px; padding-top: 2.2rem; }
h1.desk { font-family: 'Source Serif 4', Georgia, serif; font-weight: 600; font-size: 2.1rem;
          letter-spacing: -0.01em; color: var(--ink); margin: 0 0 .35rem 0; line-height: 1.15; }
p.welcome { color: var(--muted); font-size: 1.02rem; margin: 0 0 1rem 0; max-width: 60ch; }
.banner { border: 1px solid var(--teal); background: var(--teal-soft); color: var(--teal);
          border-radius: 6px; padding: .55rem .85rem; font-weight: 600; font-size: .95rem; margin-bottom: 1.1rem; }
.slip { background: #FFFFFF; border: 1px solid var(--rule); border-left: 4px solid var(--teal);
        border-radius: 6px; padding: .9rem 1rem .75rem; margin: .2rem 0 .4rem; }
.slip.refusal { border-left-color: var(--amber); }
.slip.clarify, .slip.not_found, .slip.pii_block { border-left-color: var(--muted); }
.slip p.body { margin: 0 0 .7rem 0; line-height: 1.55; font-size: 1rem; color: var(--ink); }
.slip .src { border-top: 1px dashed var(--rule); padding-top: .55rem; font-size: .86rem; color: var(--muted); line-height: 1.5; }
.slip .src a { color: var(--teal); font-weight: 600; text-decoration: none; }
.slip .src a:hover, .slip .src a:focus { text-decoration: underline; }
.slip.refusal .src a { color: var(--amber); }
.tag { display: inline-block; font-size: .78rem; font-weight: 600; padding: .05rem .5rem; border-radius: 999px;
       margin-bottom: .5rem; background: var(--teal-soft); color: var(--teal); }
.slip.refusal .tag { background: var(--amber-soft); color: var(--amber); }
.slip.clarify .tag, .slip.not_found .tag, .slip.pii_block .tag { background: #ECEFEE; color: var(--muted); }
.ex-label { color: var(--muted); font-size: .9rem; margin: .2rem 0 .4rem; }
div.stButton > button { background: #FFFFFF; color: var(--ink); border: 1px solid var(--rule); border-radius: 6px;
                        text-align: left; font-size: .92rem; padding: .5rem .75rem; width: 100%; }
div.stButton > button:hover { border-color: var(--teal); color: var(--teal); }
div.stButton > button:focus-visible { outline: 2px solid var(--teal); outline-offset: 2px; }
.foot { color: var(--muted); font-size: .8rem; line-height: 1.5; margin-top: 2rem; border-top: 1px solid var(--rule); padding-top: .8rem; }
</style>
""",
    unsafe_allow_html=True,
)

TAGS = {
    "answer": "Fact",
    "refusal": "Facts only",
    "clarify": "Need a detail",
    "not_found": "Not in sources",
    "pii_block": "Personal details blocked",
}


def render_slip(r: dict) -> None:
    st.markdown(
        f"""<div class="slip {r['kind']}">
<span class="tag">{TAGS.get(r['kind'], 'Fact')}</span>
<p class="body">{html.escape(r['text'])}</p>
<div class="src">Source: <a href="{html.escape(r['url'])}" target="_blank" rel="noopener">{html.escape(r['source_title'])}</a><br>
Last updated from sources: {html.escape(r['last_updated'])}</div>
</div>""",
        unsafe_allow_html=True,
    )


# Sidebar: scope and privacy.
with st.sidebar:
    st.markdown("### Scope")
    st.markdown(f"**AMC:** {config.AMC_NAME}")
    for meta in config.SCHEMES.values():
        st.markdown(f"- {meta['name']}")
    st.markdown("### What I can answer")
    st.markdown(
        "Expense ratio, exit load, minimum SIP, lock-in, riskometer, benchmark, fund manager, objective, "
        "cut-off time, plans, and how to download statements."
    )
    st.markdown("### Privacy")
    st.markdown("Messages with personal details are blocked before processing. Question text is never logged.")
    if st.button("Clear conversation"):
        st.session_state.history = []
        st.rerun()

st.markdown('<h1 class="desk">HDFC Mutual Fund facts desk</h1>', unsafe_allow_html=True)
st.markdown(
    '<p class="welcome">Ask a factual question about four HDFC Mutual Fund schemes. '
    "Every answer cites one official document.</p>",
    unsafe_allow_html=True,
)
st.markdown('<div class="banner">Facts-only. No investment advice.</div>', unsafe_allow_html=True)

if "history" not in st.session_state:
    st.session_state.history = []

pending = None
if not st.session_state.history:
    st.markdown('<p class="ex-label">Try one of these:</p>', unsafe_allow_html=True)
    for q in EXAMPLES:
        if st.button(q, key=f"ex-{q}"):
            pending = q

typed = st.chat_input("Ask about expense ratio, exit load, minimum SIP, lock-in…")
pending = typed or pending

if pending:
    resp = answer(pending)
    # Never keep a message that contained personal details, not even in session state.
    shown_q = "Message hidden because it contained personal details." if resp.kind == "pii_block" else pending
    st.session_state.history.append({"q": shown_q, "r": resp.__dict__})

for turn in st.session_state.history:
    with st.chat_message("user"):
        st.markdown(html.escape(turn["q"]))
    with st.chat_message("assistant"):
        render_slip(turn["r"])

st.markdown(f'<div class="foot">{DISCLAIMER}</div>', unsafe_allow_html=True)
