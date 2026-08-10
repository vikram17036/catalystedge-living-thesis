"""Normalize raw market/news/fundamental payloads into Evidence records."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from stocksense.core.contracts import Evidence, EvidenceType, EventStudyResult


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _eid(*parts: str) -> str:
    raw = "|".join(str(p) for p in parts)
    return "ev_" + hashlib.sha256(raw.encode()).hexdigest()[:16]


def from_one_day_return(
    ticker: str,
    value: float,
    *,
    observed_at: Optional[datetime] = None,
    available_at: Optional[datetime] = None,
) -> Evidence:
    ts = observed_at or _utcnow()
    return Evidence(
        id=_eid(ticker, "one_day_return", ts.isoformat()),
        type=EvidenceType.MARKET,
        entity=ticker.upper(),
        observed_at=ts,
        available_at=available_at or ts,
        source="yahoo_finance",
        metric="one_day_return",
        value=value,
        data={"one_day_return": value},
    )


def from_fundamental_metric(
    ticker: str,
    metric: str,
    value: float,
    *,
    period: Optional[str] = None,
    observed_at: Optional[datetime] = None,
    available_at: Optional[datetime] = None,
    source: str = "yahoo_finance",
) -> Evidence:
    ts = observed_at or _utcnow()
    return Evidence(
        id=_eid(ticker, metric, period or "", str(value), ts.date().isoformat()),
        type=EvidenceType.FUNDAMENTAL,
        entity=ticker.upper(),
        observed_at=ts,
        available_at=available_at or ts,
        source=source,
        metric=metric,
        value=value,
        data={"period": period} if period else {},
        provenance={"provider": source},
    )


def from_news_article(
    ticker: str,
    article: Dict[str, Any],
    *,
    available_at: Optional[datetime] = None,
) -> Evidence:
    headline = article.get("title") or article.get("headline") or ""
    url = article.get("url") or article.get("link")
    published = article.get("publishedAt") or article.get("published_at")
    try:
        obs = (
            datetime.fromisoformat(str(published).replace("Z", "+00:00"))
            if published
            else _utcnow()
        )
    except ValueError:
        obs = _utcnow()
    return Evidence(
        id=_eid(ticker, "news", url or headline),
        type=EvidenceType.NEWS,
        entity=ticker.upper(),
        observed_at=obs,
        available_at=available_at or obs,
        source=article.get("source", {}).get("name")
        if isinstance(article.get("source"), dict)
        else str(article.get("source") or "newsapi"),
        metric="headline",
        value=headline,
        data={"description": article.get("description"), "url": url},
        url=url,
    )


def ledger_from_analysis_payload(
    ticker: str,
    *,
    price_change_pct: Optional[float] = None,
    fundamentals: Optional[Dict[str, Any]] = None,
    news_articles: Optional[Iterable[Dict[str, Any]]] = None,
    as_of: Optional[datetime] = None,
) -> List[Evidence]:
    """Build an Evidence list from collector / analysis outputs."""
    as_of = as_of or _utcnow()
    out: List[Evidence] = []
    t = ticker.upper()

    if price_change_pct is not None:
        out.append(
            from_one_day_return(t, float(price_change_pct), observed_at=as_of, available_at=as_of)
        )

    info = (fundamentals or {}).get("info") if fundamentals else None
    if isinstance(info, dict):
        for metric in (
            "grossMargins",
            "profitMargins",
            "revenueGrowth",
            "trailingPE",
            "forwardPE",
            "debtToEquity",
        ):
            raw = info.get(metric)
            if raw is None:
                continue
            try:
                out.append(
                    from_fundamental_metric(
                        t, metric, float(raw), observed_at=as_of, available_at=as_of
                    )
                )
            except (TypeError, ValueError):
                continue

    for article in news_articles or []:
        if isinstance(article, dict):
            out.append(from_news_article(t, article, available_at=as_of))

    return out


def from_event_study_result(
    result: EventStudyResult,
    *,
    evidence_id: Optional[str] = None,
    observed_at: Optional[datetime] = None,
) -> Evidence:
    """Single EVENT_STUDY evidence summarizing the experiment (not per-observation)."""
    ts = observed_at or _utcnow()
    spec = result.spec
    repro = result.reproducibility
    eid = evidence_id or _eid(
        spec.ticker,
        "event_study",
        spec.calendar_id,
        spec.event_filter.value,
        str(spec.pre_window),
        str(spec.post_window),
        repro.price_data_hash,
    )
    data = {
        "ticker": spec.ticker,
        "calendar_id": spec.calendar_id,
        "event_filter": spec.event_filter.value,
        "pre_window": spec.pre_window,
        "post_window": spec.post_window,
        "calendar_events": result.calendar_events,
        "eligible_events": result.eligible_events,
        "events_analyzed": result.events_analyzed,
        "excluded_events": result.excluded_events,
        "pre": {
            "window": spec.pre_window,
            "mean": result.pre_stats.mean,
            "median": result.pre_stats.median,
            "positive_rate": result.pre_stats.positive_rate,
        },
        "event": {
            "mean": result.event_stats.mean,
            "median": result.event_stats.median,
            "positive_rate": result.event_stats.positive_rate,
        },
        "post": {
            "window": spec.post_window,
            "mean": result.post_stats.mean,
            "median": result.post_stats.median,
            "positive_rate": result.post_stats.positive_rate,
        },
        "engine_version": repro.engine_version,
        "price_data_hash": repro.price_data_hash,
    }
    return Evidence(
        id=eid,
        type=EvidenceType.EVENT_STUDY,
        entity=spec.ticker,
        observed_at=ts,
        available_at=ts,
        source="catalystedge:event-study",
        metric="event_study_summary",
        value=result.events_analyzed,
        data=data,
        provenance={
            "calendar_id": repro.calendar_id,
            "engine_version": repro.engine_version,
            "price_source": repro.price_source,
            "price_mode": repro.price_mode,
            "price_data_hash": repro.price_data_hash,
        },
    )


def index_by_id(evidence: List[Evidence]) -> Dict[str, Evidence]:
    return {e.id: e for e in evidence}


def validate_claim_evidence_ids(
    evidence_ids: List[str], ledger: Dict[str, Evidence]
) -> List[str]:
    """Return fabricated ids (present in claim but missing from ledger)."""
    return [eid for eid in evidence_ids if eid not in ledger]
