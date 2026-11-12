"""Intent router (W1: decide answer vs. refuse).

Rules run first and are the safety floor. They are ordered so that a question
mixing a fact with an opinion ("what's the TER, and is it a good fund?") is
treated as ADVICE: the bot never answers half of an advice question.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from . import config

FACT, PROCESS, ADVICE, PERFORMANCE, OUT_OF_SCOPE, GREETING = (
    "FACT", "PROCESS", "ADVICE", "PERFORMANCE", "OUT_OF_SCOPE", "GREETING"
)

_ADVICE = re.compile(
    r"\b((?:should|shall|must) i (?:buy|sell|invest in|hold|switch|redeem|exit|stay|continue|start|stop|choose|pick|go for|put)|should i invest(?=\W*$)|do you (?:recommend|suggest)|recommend|suggest|advise|advice|"
    r"is it (?:a )?(?:good|bad|safe|worth|right)|good (?:fund|choice|option|investment|time)|"
    r"worth (?:it|investing|buying)|better|best|vs\.?|versus|compare|comparison|"
    r"buy|sell|hold on|switch to|exit now|where (?:should|to) i? ?invest|which (?:fund|one|scheme)|"
    r"right for me|suitable for me|my portfolio|how (?:much|should) .{0,20}allocate|my allocation|rebalance|"
    r"will it (?:go up|grow|rise|fall)|predict|forecast|future|target)\b",
    re.I,
)
_PERFORMANCE = re.compile(
    r"\b(returns?|cagr|xirr|performance|performed|(?:current|latest|today'?s?) nav(?! in| for| if)|nav (?:history|on \d|of \d)|grow(?:th)? of|how much (?:will|would)|"
    r"made money|profit|gains? (?:last|in|over)|1y|3y|5y|10y|yearly return|annuali[sz]ed|"
    r"beat(?:en|s)? (?:the|its) (?:index|benchmark)|outperform|underperform|alpha|sharpe)\b",
    re.I,
)
_PROCESS = re.compile(r"\b(how (?:do|can|to)|download|get (?:my|a|the)|where (?:do|can) i (?:get|find))\b", re.I)
DEFINITION = re.compile(
    r"^\s*(?:what\s+(?:is|are|does)\s+(?:a|an|the)?\s*\w[\w\s-]{0,30}(?:mean)?\??\s*$|define\b|meaning of\b|explain\b)", re.I
)
_GREETING = re.compile(r"^\s*(hi|hello|hey|namaste|thanks|thank you|ok|okay)\W*\s*$", re.I)
_OTHER_AMC = re.compile(
    r"\b(sbi|icici|axis|kotak|nippon|aditya birla|uti|parag parikh|ppfas|mirae|dsp|quant|tata|"
    r"motilal|franklin|canara|edelweiss|bandhan|hsbc|invesco|sundaram|groww mutual)\b",
    re.I,
)
_OTHER_HDFC = re.compile(
    r"\b(large\s*(?:and|&)\s*mid|small\s*cap|smallcap|focused|balanced advantage|hybrid|multi\s*cap|multi[- ]asset|"
    r"liquid fund|index fund|nifty 50 index|etf|gold|silver|defence|infrastructure|value fund|children|"
    r"retirement|dividend yield|arbitrage|overnight|debt fund|gilt)\b",
    re.I,
)
_OFF_TOPIC = re.compile(r"\b(stock|share price|crypto|bitcoin|gold price|fd rate|loan|insurance policy|ipo)\b", re.I)


@dataclass
class Route:
    intent: str
    reason: str


def route(query: str) -> Route:
    q = query.strip()
    if _GREETING.match(q):
        return Route(GREETING, "greeting")
    if _ADVICE.search(q):
        return Route(ADVICE, "advice/opinion keywords")
    if _PERFORMANCE.search(q):
        return Route(PERFORMANCE, "returns/performance keywords")
    if _OTHER_AMC.search(q):
        return Route(OUT_OF_SCOPE, "other AMC")
    if _OTHER_HDFC.search(q):
        return Route(OUT_OF_SCOPE, "HDFC scheme outside the corpus")
    if _OFF_TOPIC.search(q):
        return Route(OUT_OF_SCOPE, "not a mutual-fund scheme fact")
    if _PROCESS.search(q):
        return Route(PROCESS, "how-to question")
    return Route(FACT, "default")
