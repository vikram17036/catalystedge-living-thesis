"""Interpretation grounding: unsupported numbers rejected."""

from stocksense.core.contracts import (
    EventStudyResult,
    EventStudySpec,
    ReproducibilityMeta,
    WindowStats,
)
from stocksense.research.event_study_interpret import (
    deterministic_summary,
    interpret_event_study,
    validate_interpretation,
)


def _tiny_result() -> EventStudyResult:
    return EventStudyResult(
        spec=EventStudySpec(ticker="NVDA"),
        calendar_events=10,
        eligible_events=10,
        events_analyzed=8,
        excluded_events=2,
        pre_stats=WindowStats(mean=0.01, median=0.008, positive_rate=0.625, n=8),
        event_stats=WindowStats(mean=-0.002, median=0.0, positive_rate=0.5, n=8),
        post_stats=WindowStats(mean=0.007, median=0.005, positive_rate=0.55, n=8),
        reproducibility=ReproducibilityMeta(
            calendar_id="fomc_v1",
            engine_version="event_study_v1",
            price_source="fixture",
            price_mode="adjusted_close",
            price_data_hash="sha256:abc",
        ),
    )


def test_unsupported_percent_rejected():
    result = _tiny_result()
    bad = {
        "summary": "NVDA rose 8.7% on average",
        "observations": [
            {"text": "NVDA rose 8.7%", "evidence_id": "ev_x", "metrics": ["pre.mean"]}
        ],
        "caveats": [],
    }
    err = validate_interpretation(bad, result, "ev_x")
    assert err is not None
    assert "8.7" in err


def test_deterministic_fallback_when_llm_off():
    result = _tiny_result()
    out = interpret_event_study(result, "ev_test", use_llm=False)
    assert out["mode"] == "deterministic"
    assert "NVDA" in out["summary"]
    assert deterministic_summary(result, "ev_test")["summary"] == out["summary"]
