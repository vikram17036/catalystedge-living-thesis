"""Unified alert persistence — prefer thesis_alerts, fall back to alert_history."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from stocksense.core.contracts import Alert, AlertSeverity, AlertStatus

logger = logging.getLogger("stocksense.alerts")


def alert_to_thesis_row(alert: Alert) -> Dict[str, Any]:
    return {
        "user_id": alert.user_id,
        "thesis_id": alert.thesis_id,
        "ticker": alert.ticker.upper(),
        "severity": alert.severity.value,
        "status": alert.status.value,
        "title": alert.title,
        "message": alert.message,
        "triggered_criteria": alert.triggered_criteria,
        "diff": alert.diff.model_dump(mode="json") if alert.diff else None,
        "evidence_ids": alert.evidence_ids,
        "data": alert.data,
    }


def alert_to_legacy_row(alert: Alert) -> Dict[str, Any]:
    """Map to alert_history shape used by current frontend."""
    return {
        "user_id": alert.user_id,
        "thesis_id": alert.thesis_id,
        "ticker": alert.ticker.upper(),
        "alert_type": "kill_criteria",
        "message": alert.message,
        "data": {
            **alert.data,
            "title": alert.title,
            "severity": alert.severity.value,
            "triggered_criteria": alert.triggered_criteria,
            "evidence_ids": alert.evidence_ids,
            "status": alert.status.value,
        },
        "is_read": alert.status != AlertStatus.UNREAD,
    }


def insert_alert(
    client: Any,
    alert: Alert,
    *,
    prefer_unified: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Insert into thesis_alerts if the table exists; otherwise alert_history.
    Dual-writes when prefer_unified succeeds so old UI still works during migration.
    """
    row_unified = alert_to_thesis_row(alert)
    row_legacy = alert_to_legacy_row(alert)
    created: Optional[Dict[str, Any]] = None

    if prefer_unified:
        try:
            response = client.table("thesis_alerts").insert(row_unified).execute()
            created = response.data[0] if response.data else None
            logger.info("Inserted thesis_alerts for thesis %s", alert.thesis_id)
        except Exception as e:
            logger.warning("thesis_alerts insert failed, falling back: %s", e)

    try:
        response = client.table("alert_history").insert(row_legacy).execute()
        if not created:
            created = response.data[0] if response.data else None
        logger.info("Inserted alert_history for thesis %s", alert.thesis_id)
    except Exception as e:
        logger.error("alert_history insert failed: %s", e)
        if not created:
            return None

    return created


def list_unread_alerts(
    client: Any,
    user_id: str,
    *,
    ticker: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Prefer thesis_alerts; fall back to alert_history."""
    try:
        query = (
            client.table("thesis_alerts")
            .select("*")
            .eq("user_id", user_id)
            .eq("status", "unread")
        )
        if ticker:
            query = query.eq("ticker", ticker.upper())
        response = query.order("created_at", desc=True).execute()
        if response.data is not None:
            return response.data
    except Exception as e:
        logger.debug("thesis_alerts list failed: %s", e)

    try:
        query = (
            client.table("alert_history")
            .select("*")
            .eq("user_id", user_id)
            .eq("is_read", False)
        )
        if ticker:
            query = query.eq("ticker", ticker.upper())
        response = query.order("created_at", desc=True).execute()
        return response.data or []
    except Exception as e:
        logger.error("Failed to list alerts: %s", e)
        return []


def mark_alert_status(
    client: Any,
    user_id: str,
    alert_id: str,
    status: str,
) -> bool:
    """Update status on thesis_alerts and/or alert_history."""
    ok = False
    mapped = status if status in {s.value for s in AlertStatus} else "acknowledged"
    try:
        client.table("thesis_alerts").update(
            {
                "status": mapped,
                "resolved_at": datetime.now(timezone.utc).isoformat()
                if mapped != "unread"
                else None,
            }
        ).eq("id", alert_id).eq("user_id", user_id).execute()
        ok = True
    except Exception:
        pass

    try:
        client.table("alert_history").update(
            {
                "is_read": mapped != "unread",
                "data": {"status": mapped},
            }
        ).eq("id", alert_id).eq("user_id", user_id).execute()
        ok = True
    except Exception as e:
        if not ok:
            logger.error("Failed to update alert: %s", e)
    return ok


def build_kill_alert(
    *,
    user_id: str,
    thesis_id: str,
    ticker: str,
    criteria: str,
    signal: str,
    analysis_sentiment: str,
    analysis_confidence: float,
    analysis_summary: str,
) -> Alert:
    title = f"Kill criteria: {ticker.upper()}"
    message = f"Kill Criteria Triggered: {criteria}"
    return Alert(
        user_id=user_id,
        thesis_id=thesis_id,
        ticker=ticker.upper(),
        severity=AlertSeverity.CRITICAL,
        status=AlertStatus.UNREAD,
        title=title,
        message=message,
        triggered_criteria=[criteria],
        evidence_ids=[],
        data={
            "triggering_signal": signal,
            "analysis_sentiment": analysis_sentiment,
            "analysis_confidence": analysis_confidence,
            "analysis_summary": (analysis_summary or "")[:500],
        },
    )
