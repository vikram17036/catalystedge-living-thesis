"""Rule-first NL → EventStudySpec parser. Hero demo needs zero Gemini."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from stocksense.core.contracts import EventFilter, EventSource, EventStudySpec

_TICKER_RE = re.compile(
    r"\b(?:to|for|on)\s+([A-Za-z]{1,5})\b|\b([A-Z]{1,5})\b(?:\s+around|\s+stock|\s+shares)?",
    re.IGNORECASE,
)
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


class ParseError(ValueError):
    """User-facing parse failure (maps to HTTP 400)."""


def _extract_ticker(text: str, prior: Optional[EventStudySpec]) -> Optional[str]:
    upper = text.upper()
    for t in sorted(_KNOWN_TICKERS, key=len, reverse=True):
        if re.search(rf"\b{t}\b", upper):
            return t
    # Generic "to XXX" / "for XXX"
    m = re.search(r"\b(?:to|for)\s+([A-Za-z]{1,5})\b", text, re.IGNORECASE)
    if m:
        cand = m.group(1).upper()
        if cand not in {"FOMC", "ONLY", "RATE", "RATES", "DAYS", "DAY", "WHAT", "THE"}:
            return cand
    if prior:
        return prior.ticker
    return None


def _detect_fomc(text: str) -> bool:
    t = text.lower()
    return "fomc" in t or "fed decision" in t or "fed meeting" in t or "federal open market" in t


def _detect_filter(text: str) -> Optional[EventFilter]:
    t = text.lower()
    if re.search(r"\bonly\s+(rate\s+)?hikes?\b", t) or re.search(r"\bhikes?\s+only\b", t):
        return EventFilter.HIKE
    if re.search(r"\bonly\s+(rate\s+)?cuts?\b", t) or re.search(r"\bcuts?\s+only\b", t):
        return EventFilter.CUT
    if re.search(r"\bonly\s+holds?\b", t):
        return EventFilter.HOLD
    if re.search(r"\b(only|just|filter).{0,20}\bhikes?\b", t):
        return EventFilter.HIKE
    if re.search(r"\b(only|just|filter).{0,20}\bcuts?\b", t):
        return EventFilter.CUT
    return None


def _detect_windows(text: str) -> Optional[Tuple[int, int]]:
    t = text.lower()
    # "five days before with five days after" / "5 days before ... 5 days after"
    m = re.search(
        r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*days?\s+before"
        r".{0,40}?"
        r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*days?\s+after",
        t,
    )
    if m:
        return _word_to_int(m.group(1)), _word_to_int(m.group(2))
    m2 = re.search(r"[±+-]?\s*(\d+)\s*d\b", t)
    if m2 and ("window" in t or "compare" in t or "before" in t or "after" in t):
        n = int(m2.group(1))
        return n, n
    if re.search(r"five\s+days\s+before", t) and re.search(r"five\s+days\s+after", t):
        return 5, 5
    return None


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
    }
    s = s.lower()
    if s in words:
        return words[s]
    return int(s)


def spec_diff(prior: Optional[EventStudySpec], new: EventStudySpec) -> Dict[str, Any]:
    if prior is None:
        return {"created": new.model_dump()}
    changes: Dict[str, Any] = {}
    a, b = prior.model_dump(), new.model_dump()
    for k in b:
        if a.get(k) != b.get(k):
            changes[k] = {"from": a.get(k), "to": b.get(k)}
    return changes


def parse_event_study_question(
    question: str,
    prior_spec: Optional[EventStudySpec] = None,
) -> Tuple[EventStudySpec, Dict[str, Any]]:
    """Parse NL into EventStudySpec. Raises ParseError on missing ticker etc."""
    q = (question or "").strip()
    if not q:
        raise ParseError("Question required.")

    ticker = _extract_ticker(q, prior_spec)
    if not ticker:
        raise ParseError(
            'Ticker required. Example: "What happens to NVDA around FOMC decisions?"'
        )

    is_fomc = _detect_fomc(q) or (
        prior_spec is not None and prior_spec.event_source == EventSource.FOMC
    )
    if not is_fomc and prior_spec is None:
        # Allow if question clearly FOMC; else require FOMC cue on first turn
        if "fomc" not in q.lower() and "fed" not in q.lower():
            raise ParseError(
                'Event source required. Example: "What happens to NVDA around FOMC decisions?"'
            )
        is_fomc = True

    if prior_spec is None:
        # Hero defaults: ±1 day, all decisions
        filt = _detect_filter(q) or EventFilter.ALL
        windows = _detect_windows(q) or (1, 1)
        spec = EventStudySpec(
            ticker=ticker,
            event_source=EventSource.FOMC,
            event_filter=filt,
            pre_window=windows[0],
            post_window=windows[1],
            metric="simple_return",
            calendar_id="fomc_v1",
        )
    else:
        data = prior_spec.model_dump()
        data["ticker"] = ticker
        filt = _detect_filter(q)
        if filt is not None:
            data["event_filter"] = filt
        windows = _detect_windows(q)
        if windows is not None:
            data["pre_window"], data["post_window"] = windows
        spec = EventStudySpec.model_validate(data)

    return spec, spec_diff(prior_spec, spec)
