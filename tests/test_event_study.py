"""Phase 2 event-study kernel: correctness, determinism, sample accounting."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from stocksense.core.contracts import EventFilter, EventStudySpec
from stocksense.research.event_calendar import CalendarEvent, events_up_to, load_calendar
from stocksense.research.event_study import PriceSeries, run_event_study

FIXTURE = Path(__file__).parent / "fixtures" / "event_study" / "golden_three_events.json"


def _load_golden():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_golden_hand_calculated_returns_and_stats():
    g = _load_golden()
    events = [CalendarEvent(date=e["date"], decision=e["decision"]) for e in g["events"]]
    prices = PriceSeries.from_pairs([(d, c) for d, c in g["prices"]], source="fixture")
    spec = EventStudySpec.model_validate(g["spec"])

    result = run_event_study(spec, events, prices)

    assert result.calendar_events == 3
    assert result.eligible_events == 3
    assert result.events_analyzed == 3
    assert result.excluded_events == 0

    for obs, expected in zip(result.observations, g["expected_observations"]):
        assert obs.event_date == expected["event_date"]
        assert obs.classification == expected["classification"]
        assert obs.pre_return == pytest.approx(expected["pre_return"])
        assert obs.event_return == pytest.approx(expected["event_return"])
        assert obs.post_return == pytest.approx(expected["post_return"])
        assert obs.cumulative_window_return == pytest.approx(
            expected["cumulative_window_return"]
        )

    es = g["expected_stats"]
    assert result.pre_stats.mean == pytest.approx(es["pre"]["mean"])
    assert result.pre_stats.median == pytest.approx(es["pre"]["median"])
    assert result.pre_stats.positive_rate == pytest.approx(es["pre"]["positive_rate"])
    assert result.event_stats.mean == pytest.approx(es["event"]["mean"])
    assert result.event_stats.median == pytest.approx(es["event"]["median"])
    assert result.event_stats.positive_rate == pytest.approx(es["event"]["positive_rate"])
    assert result.post_stats.mean == pytest.approx(es["post"]["mean"])
    assert result.post_stats.median == pytest.approx(es["post"]["median"])
    assert result.post_stats.positive_rate == pytest.approx(es["post"]["positive_rate"])


def test_byte_equivalent_determinism():
    g = _load_golden()
    events = [CalendarEvent(date=e["date"], decision=e["decision"]) for e in g["events"]]
    prices = PriceSeries.from_pairs([(d, c) for d, c in g["prices"]], source="fixture")
    spec = EventStudySpec.model_validate(g["spec"])

    a = run_event_study(spec, events, prices)
    b = run_event_study(spec, events, prices)
    assert a.model_dump() == b.model_dump()
    assert a.reproducibility.price_data_hash == b.reproducibility.price_data_hash


def test_hike_filter_reduces_eligible_not_calendar():
    g = _load_golden()
    events = [CalendarEvent(date=e["date"], decision=e["decision"]) for e in g["events"]]
    prices = PriceSeries.from_pairs([(d, c) for d, c in g["prices"]], source="fixture")
    base = EventStudySpec.model_validate(g["spec"])
    hike = base.model_copy(update={"event_filter": EventFilter.HIKE})

    all_r = run_event_study(base, events, prices)
    hike_r = run_event_study(hike, events, prices)

    assert hike_r.calendar_events == all_r.calendar_events == 3
    assert hike_r.eligible_events == 1
    assert hike_r.events_analyzed == 1
    assert hike_r.observations[0].classification == "hike"


def test_window_change_mutates_returns():
    g = _load_golden()
    events = [CalendarEvent(date=e["date"], decision=e["decision"]) for e in g["events"]]
    # Need more pre history for window=5 — extend prices backward with flat closes
    pairs = [(d, c) for d, c in g["prices"]]
    # prepend synthetic sessions before first date for window=5
    extra = [
        ("2019-12-20", 95.0),
        ("2019-12-23", 96.0),
        ("2019-12-24", 97.0),
        ("2019-12-26", 98.0),
        ("2019-12-27", 99.0),
        ("2019-12-30", 99.5),
        ("2019-12-31", 99.8),
    ]
    prices = PriceSeries.from_pairs(extra + pairs, source="fixture")
    # Also need post buffer for last event — already have 01-31, 02-03; add more
    more_post = [
        ("2020-02-04", 111.0),
        ("2020-02-05", 112.0),
        ("2020-02-06", 113.0),
        ("2020-02-07", 114.0),
    ]
    prices = PriceSeries.from_pairs(
        list(zip(prices.dates, prices.closes)) + more_post, source="fixture"
    )

    w1 = EventStudySpec.model_validate(g["spec"])
    w5 = w1.model_copy(update={"pre_window": 5, "post_window": 5})
    r1 = run_event_study(w1, events, prices)
    r5 = run_event_study(w5, events, prices)
    assert r1.events_analyzed >= 1 and r5.events_analyzed >= 1
    assert r1.observations[0].pre_return != r5.observations[0].pre_return


def test_insufficient_pre_window_exclusion():
    events = [CalendarEvent(date="2020-01-03", decision="hold")]
    prices = PriceSeries.from_pairs(
        [("2020-01-02", 100.0), ("2020-01-03", 101.0), ("2020-01-06", 102.0)],
        source="fixture",
    )
    spec = EventStudySpec(
        ticker="TEST",
        pre_window=5,
        post_window=1,
        calendar_id="golden_v1",
    )
    result = run_event_study(spec, events, prices)
    assert result.events_analyzed == 0
    assert result.excluded_events == 1
    assert result.exclusions[0].reason == "insufficient_pre_window"


def test_fomc_v1_loads_and_filters_as_of():
    cal = load_calendar("fomc_v1")
    assert cal.calendar_id == "fomc_v1"
    assert len(cal.events) >= 40
    truncated = events_up_to(cal, "2022-12-31")
    assert all(e.date <= "2022-12-31" for e in truncated)
    assert len(truncated) < len(cal.events)
