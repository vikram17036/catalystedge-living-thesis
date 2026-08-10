"""Orchestrate scenario lab against active thesis kills."""

from __future__ import annotations

from typing import Any, Dict, Optional

from stocksense.core.contracts import ScenarioSpec
from stocksense.core.evidence_ledger import from_scenario_result
from stocksense.db.supabase_client import get_active_thesis_for_ticker, get_user_theses
from stocksense.research.scenario_lab import run_scenario
from stocksense.research.scenario_parse import ScenarioParseError, parse_scenario_question


def _interpret(result) -> Dict[str, Any]:
    spec = result.spec
    pct = abs(spec.shock_value) * 100
    summary = (
        f"WHAT-IF: {spec.ticker} one_day_return={spec.shock_value} ({pct:.1f}% move). "
        f"Evaluated {result.criteria_evaluated} kill criteria on shocked metric; "
        f"triggered {result.criteria_triggered}; "
        f"skipped unaffected {result.criteria_skipped_unaffected}; "
        f"skipped qualitative {result.criteria_skipped_qualitative}. "
        f"{'MATERIAL — kill(s) would fire.' if result.material else 'No kill fired on this shock.'} "
        f"This simulation does not modify the thesis."
    )
    return {
        "mode": "deterministic",
        "summary": summary,
        "caveats": [
            "Hypothetical — not observed market data.",
            "Only criteria on the shocked metric were evaluated for trigger/not-trigger.",
            "Does not run ThesisDiff (origin vs current).",
        ],
    }


def run_scenario_request(
    question: str,
    *,
    user_id: str,
    access_token: str,
    prior_spec: Optional[ScenarioSpec] = None,
) -> Dict[str, Any]:
    spec, diff = parse_scenario_question(question, prior_spec)

    thesis = None
    if spec.thesis_id:
        theses = get_user_theses(user_id, access_token, spec.ticker)
        thesis = next((t for t in theses if str(t.get("id")) == str(spec.thesis_id)), None)
    if not thesis:
        thesis = get_active_thesis_for_ticker(user_id, access_token, spec.ticker)
    if not thesis:
        raise ValueError(
            f"Create a thesis for {spec.ticker} first before running Scenario Lab."
        )

    spec = spec.model_copy(update={"thesis_id": str(thesis["id"])})
    kills = thesis.get("structured_kill_criteria") or thesis.get("kill_criteria") or []
    result = run_scenario(
        spec,
        kill_criteria_raw=kills,
        thesis_id=str(thesis["id"]),
        thesis_version=int(thesis.get("thesis_version") or 1),
    )
    evidence = from_scenario_result(result)

    return {
        "prior_spec": prior_spec.model_dump(mode="json") if prior_spec else None,
        "spec": result.spec.model_dump(mode="json"),
        "spec_diff": diff,
        "result": result.model_dump(mode="json"),
        "interpretation": _interpret(result),
        "evidence_ledger": [evidence.model_dump(mode="json")],
        "thesis_id": str(thesis["id"]),
        "disclaimer": "This simulation does not modify the thesis.",
    }


__all__ = ["run_scenario_request", "ScenarioParseError"]
