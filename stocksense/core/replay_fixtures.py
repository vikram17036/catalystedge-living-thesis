"""Replay fixtures — adverse / recovery scenarios for thesis demo."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from stocksense.core.evidence_ledger import (
    from_fundamental_metric,
    from_news_article,
    from_one_day_return,
)

logger = logging.getLogger("stocksense.replay")

_FIXTURE_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "replay"


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def load_json_fixture(label: str) -> Optional[Dict[str, Any]]:
    """Load frozen fixture from tests/fixtures/replay/{label}.json"""
    path = _FIXTURE_DIR / f"{label}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if "label" not in data:
            data["label"] = label
        return data
    except Exception as e:
        logger.warning("Failed to load fixture %s: %s", path, e)
        return None


def build_adverse_nvda_replay(
    *,
    as_of: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Hard shock scenario: -7% day, margin pressure headlines, bearish sentiment.
    Prefer frozen nvda_t1.json when present.
    """
    frozen = load_json_fixture("nvda_t1")
    if frozen:
        frozen = dict(frozen)
        frozen["label"] = "adverse_shock"
        return frozen

    as_of = as_of or datetime.now(timezone.utc)
    evidence = [
        from_one_day_return("NVDA", -0.07, observed_at=as_of, available_at=as_of),
        from_fundamental_metric(
            "NVDA", "grossMargins", 0.72, observed_at=as_of, available_at=as_of
        ),
        from_news_article(
            "NVDA",
            {
                "title": "Chip demand fears spark NVIDIA selloff",
                "url": "https://example.com/nvda-adverse",
                "source": {"name": "replay_fixture"},
                "publishedAt": _iso(as_of),
                "description": "Investors worry about AI capex digestion.",
            },
            available_at=as_of,
        ),
    ]
    analysis_payload = {
        "ticker": "NVDA",
        "overall_sentiment": "Bearish",
        "overall_confidence": 0.78,
        "skeptic_sentiment": "Agree",
        "summary": "Replay fixture: sharp one-day drop and demand-fear headlines weaken the growth thesis.",
        "sentiment_report": "Bearish — selloff on demand fears.",
        "risks_identified": [
            "AI capex digestion",
            "One-day drawdown > 5%",
            "Narrative shift from growth to valuation risk",
        ],
        "key_themes": [
            {
                "theme": "Demand Digestion",
                "sentiment_direction": "Bearish",
                "headline_count": 3,
                "summary": "Capex pause fears",
            },
        ],
        "timestamp": _iso(as_of),
        "price_data": {
            "percent_change": -0.07,
            "current_price": 200.0,
            "previous_close": 215.0,
        },
        "tools_used": ["replay_fixture"],
        "pipeline": "replay_v1",
    }
    return {
        "ticker": "NVDA",
        "label": "adverse_shock",
        "as_of": as_of,
        "evidence": [e.model_dump(mode="json") for e in evidence],
        "analysis_payload": analysis_payload,
    }


def list_builtin_replays(ticker: str) -> List[Dict[str, Any]]:
    t = ticker.upper()
    out: List[Dict[str, Any]] = []

    for label in ("nvda_t0", "nvda_t1"):
        fx = load_json_fixture(label)
        if fx and str(fx.get("ticker", "")).upper() in (t, "NVDA") and t == "NVDA":
            out.append(fx)

    if t == "NVDA":
        out.append(build_adverse_nvda_replay())

    as_of = datetime.now(timezone.utc)
    evidence = [
        from_one_day_return(t, -0.06, observed_at=as_of, available_at=as_of),
        from_news_article(
            t,
            {
                "title": f"{t} slides on risk-off session",
                "url": f"https://example.com/{t.lower()}-adverse",
                "source": {"name": "replay_fixture"},
                "publishedAt": _iso(as_of),
            },
            available_at=as_of,
        ),
    ]
    out.append(
        {
            "ticker": t,
            "label": "adverse_shock",
            "as_of": as_of,
            "evidence": [e.model_dump(mode="json") for e in evidence],
            "analysis_payload": {
                "ticker": t,
                "overall_sentiment": "Bearish",
                "overall_confidence": 0.72,
                "skeptic_sentiment": "Agree",
                "summary": f"Replay fixture: adverse shock for {t}.",
                "sentiment_report": "Bearish",
                "risks_identified": ["Sharp one-day drawdown", "Risk-off tape"],
                "key_themes": [],
                "timestamp": _iso(as_of),
                "price_data": {"percent_change": -0.06},
                "pipeline": "replay_v1",
            },
        }
    )

    seen = set()
    unique = []
    for r in out:
        key = r.get("label")
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)
    return unique


def get_builtin_replay(ticker: str, label: str = "adverse_shock") -> Optional[Dict[str, Any]]:
    fx = load_json_fixture(label)
    if fx:
        fx_ticker = str(fx.get("ticker") or "").upper()
        if not fx_ticker or fx_ticker == ticker.upper():
            return fx

    for r in list_builtin_replays(ticker):
        if r["label"] == label:
            return r
    return None
