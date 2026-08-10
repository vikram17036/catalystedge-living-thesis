"""Tests for thesis diff + replay fixtures."""

from stocksense.core.replay_fixtures import get_builtin_replay
from stocksense.core.thesis_diff import (
    alert_from_diff,
    build_thesis_diff,
    diff_to_api_payload,
    snapshot_from_analysis,
)


def test_adverse_replay_triggers_kill_and_sentiment_flip():
    fixture = get_builtin_replay("NVDA", "adverse_shock")
    assert fixture is not None
    origin = {
        "sentiment": "Bullish",
        "confidence": 0.85,
        "timestamp": "2026-08-01T00:00:00+00:00",
    }
    current = snapshot_from_analysis(fixture["analysis_payload"])
    diff = build_thesis_diff(
        thesis_id="t1",
        ticker="NVDA",
        origin_snapshot=origin,
        origin_evidence=[],
        current_snapshot=current,
        current_evidence=fixture["evidence"],
        kill_criteria=[
            {
                "id": "k1",
                "kind": "deterministic",
                "label": "One-day drop > 5%",
                "metric": "one_day_return",
                "op": "lte",
                "threshold": -0.05,
            }
        ],
    )
    assert diff.material()
    assert diff.triggered_criteria
    assert diff.invalidated or diff.weakened
    payload = diff_to_api_payload(diff)
    assert payload["has_comparison"] is True
    assert payload["material"] is True
    alert = alert_from_diff(user_id="u1", thesis_id="t1", ticker="NVDA", diff=diff)
    assert alert is not None
    assert alert.title.startswith("Thesis update")
