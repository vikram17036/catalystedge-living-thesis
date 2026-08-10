"""Rule-first NL → AnalogSpec. Hero demo needs zero Gemini."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

from stocksense.core.contracts import AnalogSpec

_KNOWN_TICKERS = {
    "NVDA",
    "AAPL",
    "MSFT",
    "GOOGL",
    "GOOG",
    "AMZN",
    "META",
    "TSLA",
    "AMD",
    "INTC",
    "SPY",
    "QQQ",
}


class AnalogParseError(ValueError):
    """User-facing parse failure (maps to HTTP 400)."""


def _word_to_int(s: str) -> int:
    words = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "twenty": 20,
    }
    s = s.lower().strip()
    if s.isdigit():
        return int(s)
    if s in words:
        return words[s]
    raise AnalogParseError(f"Cannot parse number: {s}")


def _extract_ticker(text: str, prior: Optional[AnalogSpec]) -> Optional[str]:
    upper = text.upper()
    for t in sorted(_KNOWN_TICKERS, key=len, reverse=True):
        if re.search(rf"\b{t}\b", upper):
            return t
    m = re.search(r"\b(?:to|for|on)\s+([A-Za-z]{1,5})\b", text, re.IGNORECASE)
    if m:
        cand = m.group(1).upper()
        if cand not in {"LAST", "NEXT", "DAYS", "DAY", "WHAT", "THE", "PAST", "OVER"}:
            return cand
    if prior:
        return prior.ticker
    return None


def _detect_lookback(text: str) -> Optional[int]:
    t = text.lower()
    m = re.search(
        r"last\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten|twenty)\s*"
        r"(?:trading\s+)?days?",
        t,
    )
    if m:
        return _word_to_int(m.group(1))
    m2 = re.search(r"lookback\s*(?:of\s*)?(\d+)", t)
    if m2:
        return int(m2.group(1))
    if "last 20" in t or "past 20" in t:
        return 20
    return None


def _detect_post_window(text: str) -> Optional[int]:
    t = text.lower()
    m = re.search(
        r"(?:next|following|over the next|forward)\s+"
        r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten|twenty)\s*"
        r"(?:trading\s+)?days?",
        t,
    )
    if m:
        return _word_to_int(m.group(1))
    m2 = re.search(r"(\d+)\s*d\b", t)
    if m2 and ("next" in t or "forward" in t or "happened" in t or "over" in t):
        return int(m2.group(1))
    return None


def _detect_top_k(text: str) -> Optional[int]:
    t = text.lower()
    m = re.search(r"top\s+(\d+|five|three|ten)", t)
    if m:
        return _word_to_int(m.group(1))
    return None


def spec_diff(prior: AnalogSpec, new: AnalogSpec) -> Dict[str, Any]:
    diff: Dict[str, Any] = {}
    for field in ("ticker", "lookback", "post_window", "top_k", "as_of"):
        a, b = getattr(prior, field), getattr(new, field)
        if a != b:
            diff[field] = {"from": a, "to": b}
    return diff


def parse_analog_question(
    question: str, prior_spec: Optional[AnalogSpec] = None
) -> Tuple[AnalogSpec, Dict[str, Any]]:
    q = (question or "").strip()
    if not q and not prior_spec:
        raise AnalogParseError("Empty question")

    ticker = _extract_ticker(q, prior_spec)
    if not ticker:
        raise AnalogParseError("Could not detect ticker (e.g. NVDA)")

    lookback = _detect_lookback(q)
    post_window = _detect_post_window(q)
    top_k = _detect_top_k(q)

    if prior_spec:
        lookback = lookback if lookback is not None else prior_spec.lookback
        post_window = post_window if post_window is not None else prior_spec.post_window
        top_k = top_k if top_k is not None else prior_spec.top_k
        as_of = prior_spec.as_of
    else:
        lookback = lookback if lookback is not None else 20
        post_window = post_window if post_window is not None else 5
        top_k = top_k if top_k is not None else 5
        as_of = None

    new = AnalogSpec(
        ticker=ticker,
        lookback=lookback,
        post_window=post_window,
        top_k=top_k,
        as_of=as_of,
    )
    diff = spec_diff(prior_spec, new) if prior_spec else {}
    return new, diff


__all__ = ["AnalogParseError", "parse_analog_question", "spec_diff"]
