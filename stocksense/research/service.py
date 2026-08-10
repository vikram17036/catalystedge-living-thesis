"""Application orchestration for Event Study (I/O + evidence + interpret)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from stocksense.core.contracts import EventStudySpec
from stocksense.core.evidence_ledger import from_event_study_result
from stocksense.research.event_calendar import events_up_to, load_calendar
from stocksense.research.event_study import run_event_study
from stocksense.research.event_study_interpret import interpret_event_study
from stocksense.research.event_study_parse import ParseError, parse_event_study_question
from stocksense.research.prices import fetch_adjusted_closes


def run_event_study_request(
    question: str,
    prior_spec: Optional[EventStudySpec] = None,
    *,
    use_llm: bool = True,
) -> Dict[str, Any]:
    spec, diff = parse_event_study_question(question, prior_spec)

    calendar = load_calendar(spec.calendar_id)
    cal_events = events_up_to(calendar, spec.as_of)
    if not cal_events:
        raise ValueError("No calendar events available for as_of / calendar_id")

    prices = fetch_adjusted_closes(
        spec.ticker,
        cal_events,
        pre_window=spec.pre_window,
        post_window=spec.post_window,
    )

    result = run_event_study(spec, cal_events, prices)

    evidence = from_event_study_result(
        result, observed_at=datetime.now(timezone.utc)
    )
    interpretation = interpret_event_study(
        result, evidence.id, use_llm=use_llm
    )

    return {
        "prior_spec": prior_spec.model_dump() if prior_spec else None,
        "spec": spec.model_dump(),
        "spec_diff": diff,
        "result": result.model_dump(),
        "interpretation": interpretation,
        "evidence_ledger": [evidence.model_dump(mode="json")],
    }


__all__ = ["run_event_study_request", "ParseError"]
