"""Phase 8 deep eval — deterministic 12+ case corpus + scorecard."""

from __future__ import annotations

import math
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

from stocksense.memory.pinecone_store import (
    InMemoryMemoryStore,
    reset_memory_store_for_tests,
)
from stocksense.orchestration import research_agent as ra


HERO = (
    "I'm reconsidering NVDA. Look at my previous research, find similar "
    "historical periods, stress test another 8% drop, and tell me whether "
    "my thesis still makes sense."
)


def _thesis() -> Dict[str, Any]:
    return {
        "id": "thesis-nvda-1",
        "ticker": "NVDA",
        "thesis_summary": "AI demand durable",
        "conviction_level": "high",
        "structured_kill_criteria": [
            {
                "id": "k1",
                "label": "one day -10%",
                "kind": "metric",
                "metric": "one_day_return",
                "op": "lt",
                "value": -0.1,
            }
        ],
        "status": "active",
        "thesis_version": 1,
    }


def _mock_analog(q, prior_spec=None):
    return {
        "spec": {"ticker": "NVDA"},
        "interpretation": {"summary": "5 matches"},
        "result": {
            "n_matches": 5,
            "reproducibility": {
                "engine_version": "analog_search_v1",
                "price_data_hash": "phash",
            },
        },
        "evidence_ledger": [
            {"id": "ev-a1", "type": "analog_search", "entity": "NVDA", "payload": {}}
        ],
    }


def _mock_scenario(q, *, user_id, access_token, prior_spec=None):
    shock = -0.08
    if prior_spec is not None and getattr(prior_spec, "shock_value", None) is not None:
        shock = float(prior_spec.shock_value)
    elif "12" in q:
        shock = -0.12
    return {
        "spec": {
            "ticker": "NVDA",
            "shock_value": shock,
            "shock_metric": "one_day_return",
            "kind": "one_day_return",
            "thesis_id": "thesis-nvda-1",
        },
        "result": {
            "criteria_triggered": 1,
            "criteria_evaluated": 3,
            "material": True,
            "reproducibility": {
                "engine_version": "scenario_lab_v1",
                "criteria_hash": "chash",
                "shock_value": shock,
            },
        },
        "interpretation": {"summary": f"shock={shock}"},
        "evidence_ledger": [
            {
                "id": f"ev-s-{shock}",
                "type": "scenario",
                "entity": "NVDA",
                "hypothetical": True,
                "payload": {},
            }
        ],
        "thesis_id": "thesis-nvda-1",
        "disclaimer": "hypothetical",
    }


@pytest.fixture
def agent_env(monkeypatch):
    reset_memory_store_for_tests(InMemoryMemoryStore())
    ra.reset_research_agent_for_tests()
    thesis = _thesis()
    attach_calls: List[Dict[str, Any]] = []

    monkeypatch.setattr(
        "stocksense.research.analog_service.run_analog_search_request",
        _mock_analog,
    )
    monkeypatch.setattr(
        "stocksense.research.scenario_service.run_scenario_request",
        _mock_scenario,
    )

    def _mock_event(q, prior=None, use_llm=False):
        return {
            "spec": {"ticker": "NVDA", "event_source": "fomc"},
            "interpretation": {"summary": "FOMC mean CAR mocked"},
            "result": {
                "n_events": 3,
                "reproducibility": {"engine_version": "event_study_v1"},
            },
            "evidence_ledger": [
                {"id": "ev-fomc-1", "type": "event_study", "hypothetical": False}
            ],
        }

    def _mock_strategy(q, prior_spec=None, prior_result=None):
        return {
            "spec": {"ticker": "NVDA", "kind": "sma_crossover"},
            "interpretation": {"summary": "20/50 SMA mocked"},
            "result": {
                "metrics": {"total_return": 0.1},
                "reproducibility": {
                    "engine_version": "strategy_lab_v1",
                    "price_data_hash": "abc",
                },
            },
            "evidence_ledger": [
                {"id": "ev-bt-1", "type": "backtest", "hypothetical": False}
            ],
        }

    monkeypatch.setattr(
        "stocksense.research.service.run_event_study_request",
        _mock_event,
    )
    monkeypatch.setattr(
        "stocksense.research.strategy_service.run_strategy_request",
        _mock_strategy,
    )
    monkeypatch.setattr(
        "stocksense.db.supabase_client.get_active_thesis_for_ticker",
        lambda *a, **k: thesis,
    )
    monkeypatch.setattr(
        "stocksense.db.supabase_client.get_user_theses",
        lambda *a, **k: [thesis],
    )

    def _hydrate(*a, **k):
        return {
            "available": True,
            "error": None,
            "refs": [{"source_type": "thesis", "source_id": thesis["id"]}],
            "hydrated": [
                {
                    "source_type": "thesis",
                    "source_id": thesis["id"],
                    "ticker": "NVDA",
                    "score": 0.9,
                    "hypothetical": False,
                    "canonical": thesis,
                    "citation_id": f"thesis:{thesis['id']}",
                    "validated": True,
                }
            ],
        }

    monkeypatch.setattr(
        "stocksense.memory.hydrate.retrieve_and_hydrate",
        _hydrate,
    )
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content="Mocked grounded answer.")
    monkeypatch.setattr(
        "stocksense.orchestration.research_agent.get_chat_llm",
        lambda **k: llm,
    )

    def _attach(user_id, access_token, thesis_id, evidence):
        attach_calls.append({"user_id": user_id, "evidence": evidence.get("id")})
        return {
            "attached": True,
            "already_attached": False,
            "row": {},
            "thesis": thesis,
        }

    monkeypatch.setattr(
        "stocksense.db.supabase_client.attach_thesis_evidence",
        _attach,
    )
    ra.reset_research_agent_for_tests()
    yield {"attach_calls": attach_calls, "thesis": thesis, "monkeypatch": monkeypatch}
    reset_memory_store_for_tests(None)
    ra.reset_research_agent_for_tests()


def _run(msg: str, **kw):
    return ra.run_research_turn(
        message=msg,
        user_id=kw.pop("user_id", "user-a"),
        access_token=kw.pop("access_token", "tok"),
        **kw,
    )


# --- corpus cases ---


def test_eval_hero_tool_selection(agent_env):
    out = _run(HERO)
    r = out["trace"]["research_tools_selected"]
    assert "find_analogs" in r and "run_scenario" in r
    assert "run_event_study" not in r and "run_backtest" not in r
    assert out["writes"] == 0
    assert out["trace"]["trace_version"] == "research_trace_v1"


def test_eval_multi_intent_selects_all_labs(agent_env):
    out = _run(
        "Reconsider NVDA, stress a 3% drop, check SMA crossover and FOMC, "
        "and historical momentum"
    )
    r = out["trace"]["research_tools_selected"]
    assert "run_scenario" in r
    assert "run_backtest" in r
    assert "run_event_study" in r
    assert "find_analogs" in r
    assert out["writes"] == 0
    assert not (out["trace"].get("tool_errors") or [])


def test_eval_irrelevant_tools_avoided_on_scenario_only(agent_env):
    out = _run("What if NVDA drops 8% in one day?")
    assert out["trace"]["research_tools_selected"] == ["run_scenario"]
    assert "find_analogs" in out["trace"]["not_selected"]


def test_eval_analog_only_avoids_scenario(agent_env):
    out = _run("Find similar historical periods for NVDA")
    assert "find_analogs" in out["trace"]["research_tools_selected"]
    assert "run_scenario" not in out["trace"]["research_tools_selected"]


def test_eval_followup_scenario_refinement(agent_env):
    t = "thr-follow"
    _run(HERO, thread_id=t)
    out = _run("Make that a 12% drop.", thread_id=t)
    assert out["trace"]["research_tools_selected"] == ["run_scenario"]
    assert math.isclose(float(out["trace"]["scenario_shock"]), -0.12, abs_tol=1e-9)
    assert "find_analogs" not in out["trace"]["research_tools_selected"]


def test_eval_no_write_on_analyze(agent_env):
    out = _run("Analyze NVDA and tell me what you think about an 8% drop.")
    assert out["trace"]["write_intent"] is False
    assert out["writes"] == 0
    assert out["trace"]["write_tools_used"] == []
    assert agent_env["attach_calls"] == []


def test_eval_explicit_write_recognized(agent_env):
    out = _run(
        "Run scenario for 8% NVDA drop and attach the result to my thesis."
    )
    assert out["trace"]["write_intent"] is True
    assert out["writes"] >= 1
    assert "attach_evidence" in out["trace"]["write_tools_used"]
    assert agent_env["attach_calls"]


def test_eval_citations_validated(agent_env):
    out = _run(HERO)
    assert out["trace"]["citations_total"] >= 1
    assert out["trace"]["citations_validated"] == out["trace"]["citations_total"]
    assert all(c.get("validated") for c in out["citations"])


def test_eval_hypothetical_label_on_scenario(agent_env):
    out = _run("What if NVDA drops 8%?")
    scen_cites = [c for c in out["citations"] if c.get("source_type") == "scenario"]
    assert scen_cites
    assert all(c.get("hypothetical") for c in scen_cites)


def test_eval_memory_degraded_survives(agent_env):
    mp = agent_env["monkeypatch"]

    def _down(*a, **k):
        return {
            "available": False,
            "error": "pinecone unavailable",
            "refs": [],
            "hydrated": [],
        }

    mp.setattr("stocksense.memory.hydrate.retrieve_and_hydrate", _down)
    ra.reset_research_agent_for_tests()
    out = _run(HERO)
    assert out["trace"]["memory"]["available"] is False
    assert out["answer"]
    assert "find_analogs" in out["trace"]["research_tools_selected"]


def test_eval_thread_isolation_same_client_thread_id(agent_env):
    tid = "shared-client-thread"
    a1 = _run(HERO, user_id="user-A", access_token="tokA", thread_id=tid)
    b1 = _run(
        "What if AAPL drops 5%?",
        user_id="user-B",
        access_token="tokB",
        thread_id=tid,
        ticker="AAPL",
    )
    a2 = _run("Make that a 12% drop.", user_id="user-A", access_token="tokA", thread_id=tid)
    # user A follow-up should still be NVDA scenario refinement from A1
    assert a1["ticker"] == "NVDA"
    assert a2["trace"]["research_tools_selected"] == ["run_scenario"]
    assert math.isclose(float(a2["trace"]["scenario_shock"]), -0.12, abs_tol=1e-9)
    # B should not inherit A's NVDA prior as ticker if they set AAPL — at least no A secrets
    assert a2["thread_id"] == tid
    assert b1["thread_id"] == tid
    # Checkpoint keys differ
    assert ra.checkpoint_thread_id("user-A", tid) != ra.checkpoint_thread_id(
        "user-B", tid
    )


def test_eval_access_token_not_in_checkpoint(agent_env):
    tid = "jwt-check"
    _run(HERO, user_id="user-a", access_token="super-secret-jwt", thread_id=tid)
    app = ra.get_research_agent()
    snap = app.get_state(
        {"configurable": {"thread_id": ra.checkpoint_thread_id("user-a", tid)}}
    )
    vals = snap.values or {}
    assert not vals.get("access_token")


def test_eval_engine_repro_present(agent_env):
    out = _run(HERO)
    tools = {e["tool"] for e in out["trace"]["engine_repro"]}
    assert "find_analogs" in tools or "run_scenario" in tools


def test_eval_scorecard(agent_env, monkeypatch):
    """Aggregate interview-style scorecard over the corpus."""
    results = {
        "tool_selection": 0,
        "tool_selection_total": 0,
        "unsafe_writes": 0,
        "write_cases": 0,
        "citation_ok": 0,
        "citation_cases": 0,
        "degraded_ok": 0,
        "degraded_cases": 0,
    }

    def check_tools(out, must_include=(), must_exclude=()):
        results["tool_selection_total"] += 1
        r = out["trace"]["research_tools_selected"]
        ok = all(t in r for t in must_include) and all(t not in r for t in must_exclude)
        if ok:
            results["tool_selection"] += 1

    # 1 hero
    out = _run(HERO)
    check_tools(out, ("find_analogs", "run_scenario"), ("run_event_study", "run_backtest"))
    results["write_cases"] += 1
    if out["writes"] != 0:
        results["unsafe_writes"] += 1
    results["citation_cases"] += 1
    if out["trace"]["citations_validated"] == out["trace"]["citations_total"]:
        results["citation_ok"] += 1

    # 2 scenario only
    out = _run("What if NVDA drops 8%?")
    check_tools(out, ("run_scenario",), ("find_analogs",))

    # 3 analog only
    out = _run("Find similar historical periods for NVDA")
    check_tools(out, ("find_analogs",), ("run_scenario",))

    # 4 follow-up
    _run(HERO, thread_id="sc")
    out = _run("Make that a 12% drop.", thread_id="sc")
    check_tools(out, ("run_scenario",), ("find_analogs", "run_event_study", "run_backtest"))

    # 5 no write
    out = _run("Tell me what you think about NVDA 8% drop")
    results["write_cases"] += 1
    if out["writes"] != 0:
        results["unsafe_writes"] += 1

    # 6 explicit write
    out = _run("Attach this scenario for 8% NVDA drop to my thesis")
    results["write_cases"] += 1
    # this case expects a write — not unsafe
    assert out["trace"]["write_intent"] is True

    # 7 degrade
    def _down(*a, **k):
        return {"available": False, "error": "down", "refs": [], "hydrated": []}

    monkeypatch.setattr("stocksense.memory.hydrate.retrieve_and_hydrate", _down)
    ra.reset_research_agent_for_tests()
    for msg in (HERO, "What if NVDA drops 8%?", "Find similar historical periods for NVDA"):
        results["degraded_cases"] += 1
        out = _run(msg)
        if out["answer"] and out["trace"]["memory"]["available"] is False:
            results["degraded_ok"] += 1

    scorecard = (
        f"Agent eval\n"
        f"Tool selection accuracy   {results['tool_selection']}/{results['tool_selection_total']}\n"
        f"Unsafe writes             {results['unsafe_writes']}/{results['write_cases']}\n"
        f"Citation validation       {results['citation_ok']}/{results['citation_cases']}\n"
        f"Degraded-memory survival  {results['degraded_ok']}/{results['degraded_cases']}\n"
    )
    print("\n" + scorecard)
    assert results["tool_selection"] == results["tool_selection_total"]
    assert results["unsafe_writes"] == 0
    assert results["citation_ok"] == results["citation_cases"]
    assert results["degraded_ok"] == results["degraded_cases"]
