"""Rule-first Event Study parser — hero turns without Gemini."""

import pytest

from stocksense.core.contracts import EventFilter
from stocksense.research.event_study_parse import ParseError, parse_event_study_question


def test_hero_first_turn_nvda_fomc():
    spec, diff = parse_event_study_question(
        "What happens to NVDA around FOMC decisions?"
    )
    assert spec.ticker == "NVDA"
    assert spec.event_filter == EventFilter.ALL
    assert spec.pre_window == 1
    assert spec.post_window == 1
    assert spec.calendar_id == "fomc_v1"
    assert "created" in diff


def test_followup_only_rate_hikes_mutates_filter_only():
    prior, _ = parse_event_study_question(
        "What happens to NVDA around FOMC decisions?"
    )
    spec, diff = parse_event_study_question("Only rate hikes.", prior)
    assert spec.ticker == "NVDA"
    assert spec.event_filter == EventFilter.HIKE
    assert spec.pre_window == 1 and spec.post_window == 1
    assert diff == {"event_filter": {"from": "all", "to": "hike"}}


def test_followup_five_day_windows():
    prior, _ = parse_event_study_question(
        "What happens to NVDA around FOMC decisions?"
    )
    prior2, _ = parse_event_study_question("Only rate hikes.", prior)
    spec, diff = parse_event_study_question(
        "Compare five days before with five days after.", prior2
    )
    assert spec.event_filter == EventFilter.HIKE
    assert spec.pre_window == 5 and spec.post_window == 5
    assert diff["pre_window"]["from"] == 1
    assert diff["pre_window"]["to"] == 5
    assert diff["post_window"]["to"] == 5


def test_no_ticker_without_prior_is_400():
    with pytest.raises(ParseError, match="Ticker required"):
        parse_event_study_question("What happens around FOMC meetings?")


def test_followup_without_ticker_keeps_prior():
    prior, _ = parse_event_study_question(
        "What happens to NVDA around FOMC decisions?"
    )
    spec, _ = parse_event_study_question("Only cuts.", prior)
    assert spec.ticker == "NVDA"
    assert spec.event_filter == EventFilter.CUT
