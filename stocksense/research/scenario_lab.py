"""Scenario Lab v1 — hypothetical metric shock vs structured kill criteria.

NOT ThesisDiff (no origin vs current / sentiment). Reuses eval_deterministic_status
for one definition of triggered.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional, Sequence

from stocksense.core.contracts import (
    KillCriterion,
    KillCriterionKind,
    ScenarioCriterionOutcome,
    ScenarioKind,
    ScenarioReproducibility,
    ScenarioResult,
    ScenarioSpec,
)
from stocksense.core.thesis_diff import (
    eval_deterministic_status,
    parse_structured_kill_criteria,
)

ENGINE_VERSION = "scenario_lab_v1"


def criteria_fingerprint(criteria: Sequence[KillCriterion]) -> str:
    payload = [
        {
            "id": c.id,
            "kind": c.kind.value if hasattr(c.kind, "value") else str(c.kind),
            "label": c.label,
            "metric": c.metric,
            "op": c.op,
            "threshold": c.threshold,
            "description": c.description,
        }
        for c in criteria
    ]
    raw = json.dumps(payload, sort_keys=True, default=str)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _outcome(c: KillCriterion, detail: Optional[str] = None) -> ScenarioCriterionOutcome:
    return ScenarioCriterionOutcome(
        id=c.id,
        label=c.label,
        kind=c.kind.value if hasattr(c.kind, "value") else str(c.kind),
        metric=c.metric,
        op=c.op,
        threshold=c.threshold,
        detail=detail,
    )


def run_scenario(
    spec: ScenarioSpec,
    *,
    kill_criteria_raw: Any,
    thesis_id: str,
    thesis_version: int = 1,
) -> ScenarioResult:
    """
    Overlay shock_metric=shock_value and classify each kill criterion.
    Does not call build_thesis_diff.
    """
    if spec.kind != ScenarioKind.ONE_DAY_RETURN_SHOCK:
        raise ValueError("Unsupported scenario kind")

    criteria = parse_structured_kill_criteria(kill_criteria_raw)
    metrics: Dict[str, Any] = {spec.shock_metric: float(spec.shock_value)}

    triggered: List[ScenarioCriterionOutcome] = []
    not_triggered: List[ScenarioCriterionOutcome] = []
    skipped_unaffected: List[ScenarioCriterionOutcome] = []
    skipped_qual: List[ScenarioCriterionOutcome] = []

    for c in criteria:
        if c.kind == KillCriterionKind.QUALITATIVE:
            skipped_qual.append(_outcome(c, "qualitative — not auto-triggered by price shock"))
            continue
        if c.kind != KillCriterionKind.DETERMINISTIC:
            skipped_qual.append(_outcome(c, "non-deterministic"))
            continue
        if (c.metric or "") != spec.shock_metric:
            skipped_unaffected.append(
                _outcome(c, f"metric {c.metric} unaffected by {spec.shock_metric} shock")
            )
            continue
        status = eval_deterministic_status(c, metrics)
        detail = f"{spec.shock_metric}={spec.shock_value} {c.op} {c.threshold}"
        if status == "triggered":
            triggered.append(_outcome(c, detail))
        elif status == "not_triggered":
            not_triggered.append(_outcome(c, detail))
        else:
            # incomplete criterion on shocked metric
            skipped_unaffected.append(_outcome(c, "incomplete deterministic criterion"))

    evaluated = len(triggered) + len(not_triggered)
    repro = ScenarioReproducibility(
        engine_version=ENGINE_VERSION,
        thesis_id=thesis_id,
        thesis_version=int(thesis_version or 1),
        criteria_hash=criteria_fingerprint(criteria),
        shock_metric=spec.shock_metric,
        shock_value=float(spec.shock_value),
        as_of=spec.as_of,
    )
    return ScenarioResult(
        spec=spec,
        triggered_criteria=triggered,
        not_triggered_criteria=not_triggered,
        skipped_unaffected_metric=skipped_unaffected,
        skipped_qualitative=skipped_qual,
        material=len(triggered) > 0,
        criteria_evaluated=evaluated,
        criteria_triggered=len(triggered),
        criteria_skipped_unaffected=len(skipped_unaffected),
        criteria_skipped_qualitative=len(skipped_qual),
        reproducibility=repro,
    )


__all__ = ["ENGINE_VERSION", "run_scenario", "criteria_fingerprint"]
