"""Phase 4 attach validation — never mutates origin_evidence."""

import pytest

from stocksense.core.thesis_attach import AttachError, validate_attach_payload


def _ev(**kwargs):
    base = {
        "id": "ev_test123",
        "type": "event_study",
        "entity": "NVDA",
        "metric": "event_study_summary",
        "value": 10,
    }
    base.update(kwargs)
    return base


def test_valid_event_study():
    out = validate_attach_payload(_ev(), "NVDA")
    assert out["type"] == "event_study"
    assert out["entity"] == "NVDA"


def test_valid_backtest():
    out = validate_attach_payload(_ev(type="backtest"), "nvda")
    assert out["type"] == "backtest"


def test_rejects_news_type():
    with pytest.raises(AttachError, match="evidence.type"):
        validate_attach_payload(_ev(type="news"), "NVDA")


def test_rejects_ticker_mismatch():
    with pytest.raises(AttachError, match="must match"):
        validate_attach_payload(_ev(entity="AAPL"), "NVDA")


def test_rejects_missing_id():
    with pytest.raises(AttachError, match="evidence.id"):
        validate_attach_payload(_ev(id=""), "NVDA")
