"""Orchestrate analog search: parse → prices → pure engine → evidence → interpret."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, Optional

from stocksense.core.contracts import AnalogResult, AnalogSpec
from stocksense.core.evidence_ledger import from_analog_search_result
from stocksense.research.analog_search import run_analog_search
from stocksense.research.analog_search_parse import (
    AnalogParseError,
    parse_analog_question,
)
from stocksense.research.prices import fetch_adjusted_closes_range


def _deterministic_interpret(result: AnalogResult) -> Dict[str, Any]:
    spec = result.spec
    fwd = (
        f"{result.forward_mean*100:.2f}%"
        if result.forward_mean is not None
        else "n/a"
    )
    hit = (
        f"{result.positive_hit_rate*100:.1f}%"
        if result.positive_hit_rate is not None
        else "n/a"
    )
    summary = (
        f"{spec.ticker}: top {result.matches_returned} distinct analogs "
        f"(lookback {spec.lookback}d shape match). "
        f"Forward {spec.post_window}d mean {fwd}, positive hit rate {hit}. "
        f"Sample: {result.candidate_windows} candidates → {result.eligible_windows} eligible "
        f"(excluded overlap={result.excluded_overlap}, lookahead={result.excluded_lookahead}, "
        f"coverage={result.excluded_future_coverage})."
    )
    return {
        "mode": "deterministic",
        "summary": summary,
        "observations": [
            {
                "text": summary,
                "metrics": [
                    "forward_mean",
                    "forward_median",
                    "positive_hit_rate",
                    "matches_returned",
                ],
            }
        ],
        "caveats": [
            "Similarity uses within-window z-scored return paths (shape, not magnitude).",
            "Top-K episodes are non-overlapping lookbacks; forward outcomes use post_window only.",
            "Past analogs are not predictive.",
        ],
    }


def run_analog_search_request(
    question: str,
    prior_spec: Optional[AnalogSpec] = None,
) -> Dict[str, Any]:
    spec, diff = parse_analog_question(question, prior_spec)

    # Long history: ~15y calendar pad is enough for rolling search
    end = (date.today() + timedelta(days=1)).isoformat()
    start = (date.today() - timedelta(days=365 * 15)).isoformat()
    prices = fetch_adjusted_closes_range(spec.ticker, start, end)

    result = run_analog_search(spec, prices)
    evidence = from_analog_search_result(result)
    interpretation = _deterministic_interpret(result)

    return {
        "prior_spec": prior_spec.model_dump(mode="json") if prior_spec else None,
        "spec": result.spec.model_dump(mode="json"),
        "spec_diff": diff,
        "result": result.model_dump(mode="json"),
        "interpretation": interpretation,
        "evidence_ledger": [evidence.model_dump(mode="json")],
    }


__all__ = ["run_analog_search_request", "AnalogParseError"]
