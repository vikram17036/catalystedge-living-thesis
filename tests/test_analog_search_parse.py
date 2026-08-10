"""Parse tests for analog search NL."""

from stocksense.research.analog_search_parse import parse_analog_question


def test_hero_nvda_defaults():
    spec, diff = parse_analog_question(
        "Find past periods that look like the last 20 trading days for NVDA."
    )
    assert spec.ticker == "NVDA"
    assert spec.lookback == 20
    assert spec.post_window == 5
    assert spec.top_k == 5
    assert diff == {}


def test_chip_next_ten_days_refines_post_only():
    prior, _ = parse_analog_question(
        "Find past periods that look like the last 20 trading days for NVDA."
    )
    spec, diff = parse_analog_question(
        "What happened over the next 10 days?", prior
    )
    assert spec.ticker == "NVDA"
    assert spec.lookback == 20
    assert spec.post_window == 10
    assert "post_window" in diff
    assert "lookback" not in diff
