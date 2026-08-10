"""Single thesis evaluator — live cache or replay fixtures share this path."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from stocksense.core.contracts import Alert, ThesisDiff
from stocksense.core.evidence_ledger import ledger_from_analysis_payload
from stocksense.core.thesis_diff import (
    alert_from_diff,
    build_thesis_diff,
    diff_to_api_payload,
    snapshot_from_analysis,
    validate_diff_evidence_ids,
)


def evaluate_thesis(
    *,
    thesis: Dict[str, Any],
    current_snapshot: Dict[str, Any],
    current_evidence: Sequence[Dict[str, Any]],
    user_id: Optional[str] = None,
    create_alert: bool = False,
) -> Dict[str, Any]:
    """
    Run production ThesisDiff against a thesis row + new evidence/snapshot.
    """
    thesis_id = str(thesis.get("id") or "")
    ticker = str(thesis.get("ticker") or "").upper()
    kill_src = thesis.get("structured_kill_criteria") or thesis.get("kill_criteria") or []

    thesis_diff = build_thesis_diff(
        thesis_id=thesis_id,
        ticker=ticker,
        origin_snapshot=thesis.get("origin_analysis_snapshot") or {},
        origin_evidence=thesis.get("origin_evidence") or [],
        current_snapshot=current_snapshot,
        current_evidence=list(current_evidence),
        kill_criteria=kill_src,
    )

    fabricated = validate_diff_evidence_ids(
        thesis_diff,
        list(thesis.get("origin_evidence") or []) + list(current_evidence),
    )
    payload = diff_to_api_payload(thesis_diff)
    payload["origin"] = thesis.get("origin_analysis_snapshot")
    payload["current"] = current_snapshot
    payload["fabricated_evidence_ids"] = fabricated
    payload["thesis_created_at"] = thesis.get("created_at")

    alert_row: Optional[Alert] = None
    if create_alert and user_id:
        alert_row = alert_from_diff(
            user_id=user_id,
            thesis_id=thesis_id,
            ticker=ticker,
            diff=thesis_diff,
        )
    payload["alert_model"] = alert_row
    return payload


def evaluate_from_analysis_cache(
    *,
    thesis: Dict[str, Any],
    analysis: Dict[str, Any],
    user_id: Optional[str] = None,
    create_alert: bool = False,
) -> Dict[str, Any]:
    """Build evidence from a cached/live analysis row, then evaluate."""
    analysis_like = {
        "overall_sentiment": analysis.get("overall_sentiment")
        or analysis.get("sentiment")
        or "",
        "overall_confidence": analysis.get("overall_confidence")
        or analysis.get("confidence")
        or 0,
        "skeptic_sentiment": analysis.get("skeptic_sentiment")
        or analysis.get("skeptic_verdict")
        or "",
        "risks_identified": analysis.get("risks_identified") or [],
        "key_themes": analysis.get("key_themes") or [],
        "timestamp": analysis.get("timestamp")
        or datetime.now(timezone.utc).isoformat(),
        "summary": analysis.get("summary") or analysis.get("analysis_summary") or "",
    }
    current_snap = snapshot_from_analysis(analysis_like)

    if analysis.get("evidence_ledger"):
        current_evidence = list(analysis["evidence_ledger"])
    else:
        price = analysis.get("price_data") or {}
        change = None
        if isinstance(price, dict):
            change = price.get("percent_change") or price.get("change_percent")
        ledger = ledger_from_analysis_payload(
            str(thesis.get("ticker") or ""),
            price_change_pct=float(change) if change is not None else None,
            fundamentals=analysis.get("fundamental_data"),
            news_articles=analysis.get("news_articles") or [],
        )
        current_evidence = [e.model_dump(mode="json") for e in ledger]

    return evaluate_thesis(
        thesis=thesis,
        current_snapshot=current_snap,
        current_evidence=current_evidence,
        user_id=user_id,
        create_alert=create_alert,
    )


def evaluate_from_fixture(
    *,
    thesis: Dict[str, Any],
    fixture: Dict[str, Any],
    user_id: Optional[str] = None,
    create_alert: bool = False,
) -> Dict[str, Any]:
    analysis_payload = fixture.get("analysis_payload") or {}
    current_snap = snapshot_from_analysis(analysis_payload)
    current_evidence = fixture.get("evidence") or []
    result = evaluate_thesis(
        thesis=thesis,
        current_snapshot=current_snap,
        current_evidence=current_evidence,
        user_id=user_id,
        create_alert=create_alert,
    )
    result["replay_label"] = fixture.get("label")
    result["evidence_count"] = len(current_evidence)
    return result
