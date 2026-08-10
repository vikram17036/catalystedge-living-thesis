"""Phase 1 invariant tests: Analyze snapshot → evaluate T0→T1 → Diff + Alert."""

from __future__ import annotations

import json
from pathlib import Path

from stocksense.core.replay_fixtures import get_builtin_replay, load_json_fixture
from stocksense.core.thesis_evaluate import evaluate_from_fixture
from stocksense.core.thesis_extract import propose_thesis_from_analysis
from stocksense.core.thesis_diff import validate_diff_evidence_ids
from stocksense.core.contracts import ThesisDiff

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "replay"


def _load(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_fixtures_exist_and_load():
    t0 = load_json_fixture("nvda_t0")
    t1 = load_json_fixture("nvda_t1")
    assert t0 and t1
    assert t0["label"] == "nvda_t0"
    assert t1["label"] == "nvda_t1"
    assert len(t0["evidence"]) >= 2
    assert len(t1["evidence"]) >= 2


def test_propose_thesis_from_t0():
    t0 = _load("nvda_t0.json")
    analysis = {
        **t0["analysis_payload"],
        "evidence_ledger": t0["evidence"],
        "id": 1,
    }
    proposal = propose_thesis_from_analysis(analysis, evidence_ledger=t0["evidence"])
    assert proposal["ticker"] == "NVDA"
    assert len(proposal["thesis_summary"]) >= 10
    assert proposal["structured_kill_criteria"]
    assert proposal["origin_analysis_snapshot"]["sentiment"] == "Bullish"
    # All cited assumption evidence ids exist in ledger
    known = {e["id"] for e in t0["evidence"]}
    for asm in proposal["assumptions"]:
        for eid in asm.get("evidence_ids") or []:
            assert eid in known


def test_t0_to_t1_evaluate_loop_invariants():
    t0 = _load("nvda_t0.json")
    t1 = get_builtin_replay("NVDA", "nvda_t1")
    assert t1 is not None

    thesis = {
        "id": "thesis-test-1",
        "ticker": "NVDA",
        "created_at": t0["as_of"],
        "origin_analysis_snapshot": t0["origin_analysis_snapshot"],
        "origin_evidence": t0["evidence"],
        "structured_kill_criteria": [
            {
                "id": "kc_day_drop",
                "kind": "deterministic",
                "label": "One-day drop greater than 5%",
                "metric": "one_day_return",
                "op": "lte",
                "threshold": -0.05,
            }
        ],
        "kill_criteria": ["One-day drop greater than 5%"],
    }

    result = evaluate_from_fixture(
        thesis=thesis,
        fixture=t1,
        user_id="user-test",
        create_alert=True,
    )

    assert result["has_comparison"] is True
    assert result["material"] is True
    assert result["fabricated_evidence_ids"] == []
    assert result["alert_model"] is not None

    diff = ThesisDiff.model_validate(result["thesis_diff"])
    assert diff.triggered_criteria, "kill criteria must fire on -7% day"
    assert diff.invalidated or diff.weakened

    fabricated = validate_diff_evidence_ids(
        diff, list(t0["evidence"]) + list(t1["evidence"])
    )
    assert fabricated == []


def test_replay_reproducibility():
    t0 = _load("nvda_t0.json")
    thesis = {
        "id": "thesis-test-2",
        "ticker": "NVDA",
        "origin_analysis_snapshot": t0["origin_analysis_snapshot"],
        "origin_evidence": t0["evidence"],
        "structured_kill_criteria": [
            {
                "id": "kc_day_drop",
                "kind": "deterministic",
                "label": "One-day drop greater than 5%",
                "metric": "one_day_return",
                "op": "lte",
                "threshold": -0.05,
            }
        ],
    }
    a = evaluate_from_fixture(thesis=thesis, fixture=get_builtin_replay("NVDA", "nvda_t1"))
    b = evaluate_from_fixture(thesis=thesis, fixture=get_builtin_replay("NVDA", "nvda_t1"))
    assert a["thesis_diff"]["triggered_criteria"] == b["thesis_diff"]["triggered_criteria"]
    assert a["thesis_diff"]["invalidated"] == b["thesis_diff"]["invalidated"]
    assert a["material"] == b["material"]
