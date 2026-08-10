"""Rule-first NL → ScenarioSpec."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

from stocksense.core.contracts import ScenarioKind, ScenarioSpec

_KNOWN = {"NVDA", "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "TSLA", "AMD", "INTC", "SPY", "QQQ"}


class ScenarioParseError(ValueError):
    pass


def _ticker(text: str, prior: Optional[ScenarioSpec]) -> Optional[str]:
    upper = text.upper()
    for t in sorted(_KNOWN, key=len, reverse=True):
        if re.search(rf"\b{t}\b", upper):
            return t
    if prior:
        return prior.ticker
    return None


def _shock_value(text: str) -> Optional[float]:
    t = text.lower()
    # "drops 10%", "drop of 10 percent", "10% drop", "-10%"
    m = re.search(
        r"(?:drop|drops|down|fall|falls|decline|declines|crash|crashes)\s*"
        r"(?:of\s+|by\s+)?(\d+(?:\.\d+)?)\s*%",
        t,
    )
    if m:
        return -abs(float(m.group(1)) / 100.0)
    m2 = re.search(r"([+-]?\d+(?:\.\d+)?)\s*%\s*(?:drop|decline|fall|one[- ]?day)?", t)
    if m2:
        v = float(m2.group(1))
        if v > 0 and ("drop" in t or "decline" in t or "fall" in t or "what if" in t):
            return -abs(v / 100.0)
        return v / 100.0 if abs(v) > 1 else v
    m3 = re.search(r"make it an?\s+(\d+(?:\.\d+)?)\s*%", t)
    if m3:
        return -abs(float(m3.group(1)) / 100.0)
    m4 = re.search(r"(-?\d+(?:\.\d+)?)\s*%", t)
    if m4 and ("drop" in t or "what if" in t or "shock" in t or "make it" in t):
        v = float(m4.group(1))
        return -abs(v / 100.0) if v > 0 else v / 100.0
    return None


def spec_diff(prior: ScenarioSpec, new: ScenarioSpec) -> Dict[str, Any]:
    diff: Dict[str, Any] = {}
    for field in ("ticker", "kind", "shock_value", "shock_metric", "thesis_id", "as_of"):
        a, b = getattr(prior, field), getattr(new, field)
        if a != b:
            diff[field] = {"from": a if not hasattr(a, "value") else a.value, "to": b if not hasattr(b, "value") else b.value}
    return diff


def parse_scenario_question(
    question: str, prior_spec: Optional[ScenarioSpec] = None
) -> Tuple[ScenarioSpec, Dict[str, Any]]:
    q = (question or "").strip()
    if not q and not prior_spec:
        raise ScenarioParseError("Empty question")

    ticker = _ticker(q, prior_spec)
    if not ticker:
        raise ScenarioParseError("Could not detect ticker")

    shock = _shock_value(q)
    if shock is None:
        if prior_spec:
            shock = prior_spec.shock_value
        else:
            raise ScenarioParseError("Could not detect shock size (e.g. drops 10%)")

    new = ScenarioSpec(
        ticker=ticker,
        kind=ScenarioKind.ONE_DAY_RETURN_SHOCK,
        shock_value=float(shock),
        thesis_id=prior_spec.thesis_id if prior_spec else None,
        as_of=prior_spec.as_of if prior_spec else None,
    )
    diff = spec_diff(prior_spec, new) if prior_spec else {}
    return new, diff
