"""Phase 4 attach validation — never mutates origin_evidence."""

from __future__ import annotations

from typing import Any, Dict, Set

ALLOWED_ATTACH_TYPES: Set[str] = {
    "event_study",
    "backtest",
    "analog_search",
    "scenario",
}


class AttachError(ValueError):
    pass


def validate_attach_payload(
    evidence: Dict[str, Any],
    thesis_ticker: str,
) -> Dict[str, Any]:
    """Validate evidence dict for attachment. Returns normalized evidence."""
    if not isinstance(evidence, dict):
        raise AttachError("evidence must be an object")
    eid = evidence.get("id")
    if not eid or not isinstance(eid, str):
        raise AttachError("evidence.id required")
    etype = str(evidence.get("type") or "").lower()
    if etype not in ALLOWED_ATTACH_TYPES:
        raise AttachError(
            f"evidence.type must be one of {sorted(ALLOWED_ATTACH_TYPES)}"
        )
    entity = str(evidence.get("entity") or "").upper()
    ticker = thesis_ticker.upper().strip()
    if entity != ticker:
        raise AttachError(
            f"evidence.entity ({entity}) must match thesis ticker ({ticker})"
        )
    out = dict(evidence)
    out["type"] = etype
    out["entity"] = entity
    return out
