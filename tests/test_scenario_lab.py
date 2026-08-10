"""Golden tests for scenario_lab_v1 four-way criteria buckets."""

from stocksense.core.contracts import ScenarioKind, ScenarioSpec
from stocksense.research.scenario_lab import criteria_fingerprint, run_scenario


def _kills():
    return [
        {
            "id": "kc_drop",
            "kind": "deterministic",
            "label": "One-day return <= -5%",
            "metric": "one_day_return",
            "op": "lte",
            "threshold": -0.05,
        },
        {
            "id": "kc_margin",
            "kind": "deterministic",
            "label": "Gross margin < 65%",
            "metric": "gross_margin",
            "op": "lt",
            "threshold": 0.65,
        },
        {
            "id": "kc_qual",
            "kind": "qualitative",
            "label": "Management loses major customer",
            "description": "Narrative kill",
        },
    ]


def test_minus_10_triggers_drop_skips_others():
    spec = ScenarioSpec(
        ticker="NVDA",
        kind=ScenarioKind.ONE_DAY_RETURN_SHOCK,
        shock_value=-0.10,
    )
    result = run_scenario(
        spec, kill_criteria_raw=_kills(), thesis_id="t1", thesis_version=1
    )
    assert result.material is True
    assert result.criteria_triggered == 1
    assert result.triggered_criteria[0].id == "kc_drop"
    assert result.criteria_skipped_unaffected == 1
    assert result.skipped_unaffected_metric[0].id == "kc_margin"
    assert result.criteria_skipped_qualitative == 1
    assert result.not_triggered_criteria == []
    assert result.reproducibility.engine_version == "scenario_lab_v1"
    assert result.reproducibility.shock_value == -0.10
    assert result.reproducibility.criteria_hash.startswith("sha256:")


def test_minus_5_exact_triggers_lte():
    spec = ScenarioSpec(ticker="NVDA", shock_value=-0.05)
    result = run_scenario(spec, kill_criteria_raw=_kills(), thesis_id="t1")
    assert result.material is True
    assert result.triggered_criteria[0].id == "kc_drop"


def test_minus_4_not_triggered():
    spec = ScenarioSpec(ticker="NVDA", shock_value=-0.04)
    result = run_scenario(spec, kill_criteria_raw=_kills(), thesis_id="t1")
    assert result.material is False
    assert result.criteria_triggered == 0
    assert result.not_triggered_criteria[0].id == "kc_drop"
    assert result.criteria_skipped_unaffected == 1
    assert result.criteria_skipped_qualitative == 1


def test_criteria_hash_stable():
    a = criteria_fingerprint(
        __import__("stocksense.core.thesis_diff", fromlist=["parse_structured_kill_criteria"]).parse_structured_kill_criteria(
            _kills()
        )
    )
    b = criteria_fingerprint(
        __import__("stocksense.core.thesis_diff", fromlist=["parse_structured_kill_criteria"]).parse_structured_kill_criteria(
            _kills()
        )
    )
    assert a == b
