"""Unit tests for Living Thesis contracts and evidence ledger."""

from datetime import datetime, timezone

import pytest

from stocksense.core.contracts import (
    Alert,
    AlertSeverity,
    Claim,
    ClaimStatus,
    Evidence,
    EvidenceType,
    KillCriterion,
    KillCriterionKind,
    Thesis,
    ThesisDiff,
    DiffItem,
)
from stocksense.core.evidence_ledger import (
    from_one_day_return,
    ledger_from_analysis_payload,
    validate_claim_evidence_ids,
    index_by_id,
)


def test_claim_supported_requires_evidence():
    with pytest.raises(ValueError):
        Claim(text="Margins expand", status=ClaimStatus.SUPPORTED, evidence_ids=[])


def test_claim_proposed_ok_without_evidence():
    c = Claim(text="Margins expand", status=ClaimStatus.PROPOSED)
    assert c.evidence_ids == []


def test_evidence_one_day_return():
    e = from_one_day_return("nvda", -0.042)
    assert e.type == EvidenceType.MARKET
    assert e.entity == "NVDA"
    assert e.metric == "one_day_return"
    assert e.id.startswith("ev_")


def test_ledger_from_payload():
    ledger = ledger_from_analysis_payload(
        "AAPL",
        price_change_pct=-0.01,
        fundamentals={"info": {"grossMargins": 0.44, "trailingPE": 28.0}},
        news_articles=[{"title": "Apple ships", "url": "https://example.com/a", "source": {"name": "Reuters"}}],
    )
    assert len(ledger) >= 3
    by_id = index_by_id(ledger)
    claim = Claim(
        text="Gross margin is healthy",
        status=ClaimStatus.SUPPORTED,
        evidence_ids=[next(e.id for e in ledger if e.metric == "grossMargins")],
    )
    assert validate_claim_evidence_ids(claim.evidence_ids, by_id) == []
    assert validate_claim_evidence_ids(["ev_fake"], by_id) == ["ev_fake"]


def test_thesis_diff_material():
    now = datetime.now(timezone.utc)
    d = ThesisDiff(
        thesis_id="t1",
        ticker="NVDA",
        as_of=now,
        compared_to=now,
        weakened=[DiffItem(text="Price down", evidence_ids=["ev_1"])],
    )
    assert d.material() is True

    empty = ThesisDiff(
        thesis_id="t1",
        ticker="NVDA",
        as_of=now,
        compared_to=now,
        unchanged=[DiffItem(text="Still valid")],
    )
    assert empty.material() is False


def test_alert_model():
    a = Alert(
        user_id="u1",
        thesis_id="th1",
        ticker="nvda",
        severity=AlertSeverity.CRITICAL,
        title="Kill",
        message="Triggered",
        triggered_criteria=["price drop > 5%"],
    )
    assert a.ticker == "nvda"
    assert a.status.value == "unread"


def test_kill_criterion_deterministic():
    k = KillCriterion(
        id="k1",
        kind=KillCriterionKind.DETERMINISTIC,
        label="One-day drop",
        metric="one_day_return",
        op="lte",
        threshold=-0.05,
    )
    assert k.op == "lte"
