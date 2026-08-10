"""Thesis Diff — compare origin evidence/snapshot vs current evidence.

Deterministic kill criteria are evaluated here; LLM does not invent numbers.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from stocksense.core.contracts import (
    Alert,
    AlertSeverity,
    AlertStatus,
    DiffItem,
    KillCriterion,
    KillCriterionKind,
    ThesisDiff,
)
from stocksense.core.evidence_ledger import index_by_id


def validate_diff_evidence_ids(
    diff: ThesisDiff,
    ledger: Sequence[Dict[str, Any]],
) -> List[str]:
    """Return evidence ids cited in the diff that are missing from the ledger."""
    known = {e.get("id") for e in ledger if isinstance(e, dict) and e.get("id")}
    cited: List[str] = []
    for group in (
        diff.strengthened,
        diff.unchanged,
        diff.weakened,
        diff.invalidated,
        diff.new_risks,
        diff.triggered_criteria,
    ):
        for item in group:
            cited.extend(item.evidence_ids or [])
    return [eid for eid in cited if eid not in known]

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return _utcnow()


def evidence_metric_map(evidence: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Latest value per metric from evidence list (dicts or Evidence dumps)."""
    out: Dict[str, Any] = {}
    for e in evidence:
        metric = e.get("metric")
        if not metric:
            continue
        out[str(metric)] = e.get("value")
    return out


def eval_deterministic(
    criterion: KillCriterion,
    metrics: Dict[str, Any],
) -> Optional[DiffItem]:
    if criterion.kind != KillCriterionKind.DETERMINISTIC:
        return None
    if not criterion.metric or criterion.op is None or criterion.threshold is None:
        return None
    raw = metrics.get(criterion.metric)
    if raw is None:
        return None
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return None
    th = float(criterion.threshold)
    op = criterion.op
    hit = (
        (op == "lt" and val < th)
        or (op == "lte" and val <= th)
        or (op == "gt" and val > th)
        or (op == "gte" and val >= th)
        or (op == "eq" and val == th)
    )
    if not hit:
        return None
    return DiffItem(
        text=f"{criterion.label}: {criterion.metric}={val} {op} {th}",
        evidence_ids=[],
        criterion_id=criterion.id,
    )


def parse_structured_kill_criteria(
    raw: Any,
) -> List[KillCriterion]:
    if not raw:
        return []
    out: List[KillCriterion] = []
    if isinstance(raw, list):
        for i, item in enumerate(raw):
            if isinstance(item, dict) and item.get("kind"):
                try:
                    out.append(KillCriterion.model_validate(item))
                except Exception:
                    continue
            elif isinstance(item, str) and item.strip():
                # Heuristic: one-day crash style phrases → deterministic
                lower = item.lower()
                if "one-day" in lower or "1-day" in lower or "drop" in lower or "%" in item:
                    out.append(
                        KillCriterion(
                            id=f"kc_text_{i}",
                            kind=KillCriterionKind.DETERMINISTIC,
                            label=item.strip()[:120],
                            metric="one_day_return",
                            op="lte",
                            threshold=-0.05,
                        )
                    )
                else:
                    out.append(
                        KillCriterion(
                            id=f"kc_qual_{i}",
                            kind=KillCriterionKind.QUALITATIVE,
                            label=item.strip()[:120],
                            description=item.strip(),
                        )
                    )
    return out


def build_thesis_diff(
    *,
    thesis_id: str,
    ticker: str,
    origin_snapshot: Optional[Dict[str, Any]],
    origin_evidence: Optional[Sequence[Dict[str, Any]]],
    current_snapshot: Dict[str, Any],
    current_evidence: Optional[Sequence[Dict[str, Any]]] = None,
    kill_criteria: Optional[Any] = None,
    compared_to: Optional[datetime] = None,
    as_of: Optional[datetime] = None,
) -> ThesisDiff:
    """
    Build a ThesisDiff from origin vs current analysis/evidence.

    Rules:
    - Sentiment flip bullish→bearish → weakened / invalidated signal
    - Confidence drop > 0.15 → weakened
    - Deterministic kill criteria that fire → triggered_criteria
    - New bearish risks in current → new_risks
    """
    origin_evidence = list(origin_evidence or [])
    current_evidence = list(current_evidence or [])
    origin_snapshot = origin_snapshot or {}
    as_of = as_of or _utcnow()
    compared_to = compared_to or _parse_dt(origin_snapshot.get("timestamp"))

    strengthened: List[DiffItem] = []
    unchanged: List[DiffItem] = []
    weakened: List[DiffItem] = []
    invalidated: List[DiffItem] = []
    new_risks: List[DiffItem] = []
    triggered: List[DiffItem] = []

    o_sent = str(origin_snapshot.get("sentiment") or "").lower()
    c_sent = str(current_snapshot.get("sentiment") or "").lower()
    o_conf = float(origin_snapshot.get("confidence") or 0)
    c_conf = float(current_snapshot.get("confidence") or 0)

    if o_sent and c_sent and o_sent == c_sent:
        unchanged.append(
            DiffItem(text=f"Sentiment still {current_snapshot.get('sentiment')}")
        )
    elif o_sent and c_sent:
        if "bull" in o_sent and "bear" in c_sent:
            invalidated.append(
                DiffItem(
                    text=f"Sentiment flipped {origin_snapshot.get('sentiment')} → {current_snapshot.get('sentiment')}"
                )
            )
        elif "bear" in o_sent and "bull" in c_sent:
            strengthened.append(
                DiffItem(
                    text=f"Sentiment improved {origin_snapshot.get('sentiment')} → {current_snapshot.get('sentiment')}"
                )
            )
        else:
            weakened.append(
                DiffItem(
                    text=f"Sentiment shifted {origin_snapshot.get('sentiment')} → {current_snapshot.get('sentiment')}"
                )
            )

    conf_delta = c_conf - o_conf
    if abs(conf_delta) <= 0.15:
        unchanged.append(
            DiffItem(text=f"Confidence roughly stable ({o_conf:.0%} → {c_conf:.0%})")
        )
    elif conf_delta < -0.15:
        weakened.append(
            DiffItem(text=f"Confidence fell {o_conf:.0%} → {c_conf:.0%}")
        )
    else:
        strengthened.append(
            DiffItem(text=f"Confidence rose {o_conf:.0%} → {c_conf:.0%}")
        )

    # Evidence metric moves (one_day_return)
    o_metrics = evidence_metric_map(origin_evidence)
    c_metrics = evidence_metric_map(current_evidence)
    if "one_day_return" in c_metrics:
        try:
            ret = float(c_metrics["one_day_return"])
            eid = next(
                (
                    e.get("id")
                    for e in current_evidence
                    if e.get("metric") == "one_day_return"
                ),
                None,
            )
            ids = [eid] if eid else []
            if ret <= -0.05:
                weakened.append(
                    DiffItem(
                        text=f"One-day return {ret:.1%}",
                        evidence_ids=ids,
                    )
                )
            elif ret >= 0.03:
                strengthened.append(
                    DiffItem(
                        text=f"One-day return {ret:.1%}",
                        evidence_ids=ids,
                    )
                )
        except (TypeError, ValueError):
            pass

    # Risks from current snapshot
    for risk in current_snapshot.get("risks_identified") or []:
        if isinstance(risk, str) and risk.strip():
            new_risks.append(DiffItem(text=risk.strip()[:200]))

    criteria = parse_structured_kill_criteria(kill_criteria)
    # Also accept structured_kill_criteria already as list of dicts
    metrics_for_kill = {**o_metrics, **c_metrics}
    for crit in criteria:
        hit = eval_deterministic(crit, metrics_for_kill)
        if hit:
            triggered.append(hit)

    return ThesisDiff(
        thesis_id=thesis_id,
        ticker=ticker.upper(),
        as_of=as_of,
        compared_to=compared_to,
        strengthened=strengthened,
        unchanged=unchanged,
        weakened=weakened,
        invalidated=invalidated,
        new_risks=new_risks[:5],
        triggered_criteria=triggered,
    )


def diff_to_api_payload(diff: ThesisDiff) -> Dict[str, Any]:
    """Map ThesisDiff into the legacy ThesisComparison-ish UI shape + full diff."""
    changes: List[Dict[str, Any]] = []
    for item in diff.invalidated:
        changes.append(
            {
                "field": "invalidated",
                "from": "valid",
                "to": item.text,
                "direction": "changed",
            }
        )
    for item in diff.weakened:
        changes.append(
            {
                "field": "weakened",
                "from": "stable",
                "to": item.text,
                "direction": "decreased",
            }
        )
    for item in diff.strengthened:
        changes.append(
            {
                "field": "strengthened",
                "from": "stable",
                "to": item.text,
                "direction": "increased",
            }
        )
    for item in diff.triggered_criteria:
        changes.append(
            {
                "field": "kill_criteria",
                "from": "ok",
                "to": item.text,
                "direction": "decreased",
            }
        )

    material = diff.material()
    summary_bits = []
    if diff.triggered_criteria:
        summary_bits.append(f"{len(diff.triggered_criteria)} kill criteria triggered")
    if diff.invalidated:
        summary_bits.append(f"{len(diff.invalidated)} invalidated")
    if diff.weakened:
        summary_bits.append(f"{len(diff.weakened)} weakened")
    if diff.strengthened:
        summary_bits.append(f"{len(diff.strengthened)} strengthened")
    if not summary_bits:
        summary_bits.append("No material change")

    return {
        "has_comparison": True,
        "thesis_id": diff.thesis_id,
        "ticker": diff.ticker,
        "changes": changes,
        "change_summary": "; ".join(summary_bits),
        "material": material,
        "thesis_diff": diff.model_dump(mode="json"),
    }


def alert_from_diff(
    *,
    user_id: str,
    thesis_id: str,
    ticker: str,
    diff: ThesisDiff,
) -> Optional[Alert]:
    if not diff.material():
        return None
    severity = (
        AlertSeverity.CRITICAL
        if diff.triggered_criteria or diff.invalidated
        else AlertSeverity.WARNING
    )
    title = f"Thesis update: {ticker.upper()}"
    parts = []
    if diff.triggered_criteria:
        parts.append(diff.triggered_criteria[0].text)
    elif diff.invalidated:
        parts.append(diff.invalidated[0].text)
    elif diff.weakened:
        parts.append(diff.weakened[0].text)
    message = parts[0] if parts else "Material thesis change detected"
    return Alert(
        user_id=user_id,
        thesis_id=thesis_id,
        ticker=ticker.upper(),
        severity=severity,
        status=AlertStatus.UNREAD,
        title=title,
        message=message,
        triggered_criteria=[t.text for t in diff.triggered_criteria],
        diff=diff,
        evidence_ids=[],
        data={"source": "thesis_diff"},
    )


def snapshot_from_analysis(analysis: Dict[str, Any]) -> Dict[str, Any]:
    themes = analysis.get("key_themes") or []
    theme_names = []
    for t in themes:
        if isinstance(t, dict):
            theme_names.append(t.get("theme") or str(t))
        else:
            theme_names.append(str(t))
    return {
        "sentiment": analysis.get("overall_sentiment")
        or analysis.get("sentiment")
        or "",
        "confidence": float(analysis.get("overall_confidence") or analysis.get("confidence") or 0),
        "skeptic_verdict": analysis.get("skeptic_sentiment")
        or analysis.get("skeptic_verdict")
        or "",
        "key_themes": theme_names[:8],
        "risks_identified": analysis.get("risks_identified") or [],
        "timestamp": analysis.get("timestamp") or _utcnow().isoformat(),
    }
