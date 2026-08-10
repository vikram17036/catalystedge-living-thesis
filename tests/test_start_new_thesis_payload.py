"""Validate start-new request/response shapes that have caused silent FE failures."""

from __future__ import annotations

from stocksense.api.auth_routes import StartNewThesisRequest, ThesisResponse, _as_thesis_response


def _payload(**overrides):
    base = {
        "ticker": "NVDA",
        "thesis_summary": "STOCK ANALYSIS SUMMARY FOR NVDA: AI demand remains durable.",
        "conviction_level": "high",
        "kill_criteria": ["One-day drop greater than 5%"],
        "origin_analysis_id": 123,
        "origin_analysis_snapshot": {
            "sentiment": "Bullish",
            "confidence": 0.85,
            "key_themes": ["AI"],
            "timestamp": "2026-08-10T00:00:00Z",
        },
        "structured_kill_criteria": [
            {
                "id": "kc_day_drop",
                "kind": "deterministic",
                "label": "One-day drop greater than 5%",
                "metric": "one_day_return",
                "op": "lte",
                "threshold": -0.05,
            }
        ],
        "change_reason": "Closed to start a new active thesis from the latest analysis",
    }
    base.update(overrides)
    return base


def test_start_new_payload_ok():
    req = StartNewThesisRequest.model_validate(_payload())
    assert req.ticker == "NVDA"
    dumped = req.model_dump(exclude={"change_reason"})
    assert "change_reason" not in dumped


def test_origin_analysis_id_coerces_bad_values():
    req = StartNewThesisRequest.model_validate(_payload(origin_analysis_id="not-an-int"))
    assert req.origin_analysis_id is None
    req2 = StartNewThesisRequest.model_validate(_payload(origin_analysis_id="42"))
    assert req2.origin_analysis_id == 42


def test_as_thesis_response_tolerates_null_kills():
    out = _as_thesis_response(
        {
            "id": "t1",
            "ticker": "NVDA",
            "thesis_summary": "hello world thesis",
            "kill_criteria": None,
            "created_at": None,
            "updated_at": None,
            "attached_evidence": None,
        }
    )
    ThesisResponse.model_validate(out)
    assert out["kill_criteria"] == []
    assert out["created_at"] == ""
