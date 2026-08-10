"""Domain-aware memory chunks — no generic text splitter."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


def _json_brief(obj: Any, max_len: int = 1200) -> str:
    try:
        s = json.dumps(obj, default=str, ensure_ascii=False)
    except Exception:
        s = str(obj)
    if len(s) > max_len:
        return s[: max_len - 3] + "..."
    return s


def chunks_for_thesis(thesis: Dict[str, Any]) -> List[Dict[str, Any]]:
    ticker = str(thesis.get("ticker") or "").upper()
    kills = thesis.get("structured_kill_criteria") or thesis.get("kill_criteria") or []
    text = (
        f"THESIS {ticker}\n"
        f"Summary: {thesis.get('thesis_summary') or ''}\n"
        f"Conviction: {thesis.get('conviction_level')}\n"
        f"Horizon: {thesis.get('time_horizon')}\n"
        f"Type: {thesis.get('thesis_type')}\n"
        f"Kill criteria: {_json_brief(kills)}\n"
        f"Status: {thesis.get('status')}"
    )
    return [
        {
            "chunk_i": 0,
            "title": f"thesis:{ticker}",
            "chunk_text": text,
            "ticker": ticker,
            "source_type": "thesis",
            "source_id": str(thesis.get("id")),
            "hypothetical": False,
        }
    ]


def chunks_for_evidence_row(
    row: Dict[str, Any], *, ticker: str
) -> List[Dict[str, Any]]:
    evidence = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
    etype = str(
        row.get("evidence_type") or evidence.get("type") or "evidence"
    ).lower()
    eid = str(row.get("evidence_id") or evidence.get("id") or row.get("id") or "")
    hyp = bool(
        evidence.get("hypothetical")
        or (evidence.get("payload") or {}).get("hypothetical")
        or etype == "scenario"
    )
    interpretation = ""
    payload = evidence.get("payload") if isinstance(evidence.get("payload"), dict) else {}
    if isinstance(payload.get("interpretation"), dict):
        interpretation = str(payload["interpretation"].get("summary") or "")
    elif isinstance(evidence.get("interpretation"), dict):
        interpretation = str(evidence["interpretation"].get("summary") or "")

    if etype == "event_study":
        body = (
            f"EVENT STUDY {ticker}\n"
            f"Question/spec: {_json_brief(payload.get('spec') or evidence.get('spec'))}\n"
            f"Result: {_json_brief(payload.get('result') or evidence.get('result'))}\n"
            f"Interpretation: {interpretation}"
        )
    elif etype == "backtest":
        body = (
            f"BACKTEST {ticker}\n"
            f"Strategy/spec: {_json_brief(payload.get('spec') or evidence.get('spec'))}\n"
            f"Metrics: {_json_brief(payload.get('result') or evidence.get('result'))}\n"
            f"Interpretation: {interpretation}"
        )
    elif etype == "analog_search":
        body = (
            f"ANALOG SEARCH {ticker}\n"
            f"Target pattern: {_json_brief(payload.get('spec') or evidence.get('spec'))}\n"
            f"Matches/outcome: {_json_brief(payload.get('result') or evidence.get('result'))}\n"
            f"Interpretation: {interpretation}"
        )
    elif etype == "scenario":
        body = (
            f"SCENARIO WHAT-IF {ticker} (hypothetical)\n"
            f"Shock: {_json_brief(payload.get('spec') or evidence.get('spec'))}\n"
            f"Triggered: {_json_brief((payload.get('result') or {}).get('triggered_criteria'))}\n"
            f"Interpretation: {interpretation}"
        )
    else:
        body = f"EVIDENCE {etype} {ticker}\n{_json_brief(evidence)}"

    return [
        {
            "chunk_i": 0,
            "title": f"{etype}:{ticker}",
            "chunk_text": body,
            "ticker": ticker.upper(),
            "source_type": etype,
            "source_id": eid,
            "hypothetical": hyp,
        }
    ]


def chunks_for_alert(alert: Dict[str, Any]) -> List[Dict[str, Any]]:
    ticker = str(alert.get("ticker") or "").upper()
    text = (
        f"ALERT {ticker}\n"
        f"What changed: {alert.get('message') or alert.get('summary') or ''}\n"
        f"Criterion: {_json_brief(alert.get('criterion') or alert.get('kill_criterion'))}\n"
        f"Status: {alert.get('status')}"
    )
    return [
        {
            "chunk_i": 0,
            "title": f"alert:{ticker}",
            "chunk_text": text,
            "ticker": ticker,
            "source_type": "alert",
            "source_id": str(alert.get("id")),
            "hypothetical": False,
        }
    ]
