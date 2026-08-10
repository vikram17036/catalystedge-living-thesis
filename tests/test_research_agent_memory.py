"""Phase 7 memory + agent unit tests (no live Pinecone required)."""

from __future__ import annotations

import math

import pytest

from stocksense.memory.chunks import chunks_for_thesis, chunks_for_evidence_row
from stocksense.memory.embeddings import prepare_document, prepare_query
from stocksense.memory.pinecone_store import (
    InMemoryMemoryStore,
    reset_memory_store_for_tests,
    user_namespace,
    vector_id,
)
from stocksense.orchestration.research_agent import (
    _detect_write_intent,
    _extract_ticker,
    _shock_from_text,
    plan_research,
    understand_request,
)


@pytest.fixture(autouse=True)
def _reset_store():
    reset_memory_store_for_tests(None)
    yield
    reset_memory_store_for_tests(None)


def test_embedding_asymmetric_format():
    assert prepare_query("NVDA thesis").startswith("task: search result | query:")
    assert prepare_document("body", title="thesis:NVDA").startswith("title: thesis:NVDA")


def test_domain_chunks_thesis_and_scenario():
    thesis = {
        "id": "t1",
        "ticker": "NVDA",
        "thesis_summary": "AI demand",
        "kill_criteria": [{"metric": "one_day_return", "op": "lt", "value": -0.1}],
        "status": "active",
    }
    ch = chunks_for_thesis(thesis)
    assert len(ch) == 1
    assert "THESIS NVDA" in ch[0]["chunk_text"]
    assert ch[0]["source_type"] == "thesis"

    row = {
        "evidence_id": "ev1",
        "evidence_type": "scenario",
        "evidence": {
            "id": "ev1",
            "type": "scenario",
            "hypothetical": True,
            "payload": {
                "spec": {"shock_value": -0.08},
                "result": {"triggered_criteria": [{"id": "k1"}]},
                "interpretation": {"summary": "material"},
            },
        },
    }
    ech = chunks_for_evidence_row(row, ticker="NVDA")
    assert ech[0]["hypothetical"] is True
    assert "SCENARIO" in ech[0]["chunk_text"]


def test_cross_user_isolation_in_memory_store():
    store = InMemoryMemoryStore()
    reset_memory_store_for_tests(store)

    def fake_vec(seed: float):
        # 8-dim stand-in
        return [seed + i * 0.01 for i in range(8)]

    store.upsert_chunks(
        user_id="user_A",
        vectors=[
            {
                "id": vector_id("user_A", "thesis", "ta", 0),
                "values": fake_vec(1.0),
                "metadata": {
                    "ticker": "NVDA",
                    "source_type": "thesis",
                    "source_id": "ta",
                    "chunk_i": 0,
                    "chunk_text": "A secret thesis",
                    "hypothetical": False,
                },
            }
        ],
    )
    store.upsert_chunks(
        user_id="user_B",
        vectors=[
            {
                "id": vector_id("user_B", "thesis", "tb", 0),
                "values": fake_vec(1.02),
                "metadata": {
                    "ticker": "NVDA",
                    "source_type": "thesis",
                    "source_id": "tb",
                    "chunk_i": 0,
                    "chunk_text": "B secret thesis",
                    "hypothetical": False,
                },
            }
        ],
    )

    hits = store.query(user_id="user_A", vector=fake_vec(1.0), top_k=10)
    assert hits
    assert all(h.user_id == "user_A" for h in hits)
    assert all(h.source_id != "tb" for h in hits)
    assert user_namespace("user_A") != user_namespace("user_B")


def test_delete_by_source_removes_orphan_chunks():
    store = InMemoryMemoryStore()
    uid = "user_A"
    for i in range(3):
        store.upsert_chunks(
            user_id=uid,
            vectors=[
                {
                    "id": vector_id(uid, "thesis", "t1", i),
                    "values": [float(i + 1)] * 4,
                    "metadata": {
                        "ticker": "NVDA",
                        "source_type": "thesis",
                        "source_id": "t1",
                        "chunk_i": i,
                        "chunk_text": f"chunk {i}",
                        "hypothetical": False,
                    },
                }
            ],
        )
    assert len(store.query(user_id=uid, vector=[1, 1, 1, 1], top_k=10)) == 3
    store.delete_by_source(user_id=uid, source_type="thesis", source_id="t1")
    # rebuild with 2 chunks
    for i in range(2):
        store.upsert_chunks(
            user_id=uid,
            vectors=[
                {
                    "id": vector_id(uid, "thesis", "t1", i),
                    "values": [float(i + 1)] * 4,
                    "metadata": {
                        "ticker": "NVDA",
                        "source_type": "thesis",
                        "source_id": "t1",
                        "chunk_i": i,
                        "chunk_text": f"new {i}",
                        "hypothetical": False,
                    },
                }
            ],
        )
    hits = store.query(user_id=uid, vector=[1, 1, 1, 1], top_k=10)
    assert len(hits) == 2
    assert all(h.chunk_i < 2 for h in hits)


def test_write_intent_gated():
    assert _detect_write_intent("Analyze and tell me what you think.") is False
    assert _detect_write_intent("Run this and attach the result to my thesis") is True
    assert _detect_write_intent("Please save this to my thesis") is True


def test_plan_hero_and_followup():
    hero = understand_request(
        {
            "user_message": (
                "I'm reconsidering NVDA. Look at my previous research, find similar "
                "historical periods, stress test another 8% drop, and tell me whether "
                "my thesis still makes sense."
            ),
            "messages": [],
            "prior_specs": {},
            "trace": {},
        }
    )
    assert hero["ticker"] == "NVDA"
    assert hero["write_intent"] is False
    assert math.isclose(hero["prior_specs"]["scenario"]["shock_value"], -0.08, abs_tol=1e-9)

    plan = plan_research(
        {
            **hero,
            "thesis": {"id": "t1", "ticker": "NVDA"},
            "research_plan": {},
            "trace": hero.get("trace") or {},
        }
    )
    tools = plan["research_plan"]["research_tools_selected"]
    assert "find_analogs" in tools
    assert "run_scenario" in tools
    assert "run_event_study" in tools
    assert "run_backtest" in tools
    assert "get_market_regime" in tools
    assert plan["research_plan"]["not_selected"] == []

    follow = understand_request(
        {
            "user_message": "Make that a 12% drop.",
            "messages": [],
            "ticker": "NVDA",
            "prior_specs": {"scenario": {"shock_value": -0.08, "ticker": "NVDA"}},
            "trace": {},
        }
    )
    assert math.isclose(
        follow["prior_specs"]["scenario"]["shock_value"], -0.12, abs_tol=1e-9
    )
    fplan = plan_research(
        {
            **follow,
            "thesis": {"id": "t1"},
            "trace": {},
        }
    )
    assert fplan["research_plan"]["research_tools_selected"] == ["run_scenario"]


def test_extract_ticker():
    assert _extract_ticker("reconsider NVDA please") == "NVDA"
    assert _extract_ticker("look at $amd") == "AMD"


def test_shock_from_text():
    assert math.isclose(_shock_from_text("another 8% drop"), -0.08, abs_tol=1e-9)
    assert math.isclose(_shock_from_text("Make that a 12% drop."), -0.12, abs_tol=1e-9)


def test_plan_multi_intent_routes_all_labs():
    plan = plan_research(
        {
            "user_message": (
                "Reconsider NVDA thesis, shock test against 3% drop, "
                "historical momentum, SMA crossover, and any FOMC upcoming"
            ),
            "ticker": "NVDA",
            "thesis": {"id": "t1", "ticker": "NVDA"},
            "prior_specs": {},
            "research_plan": {},
            "trace": {},
        }
    )
    selected = plan["research_plan"]["research_tools_selected"]
    assert "run_scenario" in selected
    assert "run_backtest" in selected
    assert "run_event_study" in selected
    assert "find_analogs" in selected
    assert "get_market_regime" in selected


def test_plan_evaluate_thesis_selects_full_pack():
    plan = plan_research(
        {
            "user_message": "Does my NVDA thesis still make sense?",
            "ticker": "NVDA",
            "thesis": {"id": "t1", "ticker": "NVDA"},
            "prior_specs": {},
            "research_plan": {},
            "trace": {},
        }
    )
    selected = plan["research_plan"]["research_tools_selected"]
    for t in (
        "get_market_regime",
        "find_analogs",
        "run_scenario",
        "run_event_study",
        "run_backtest",
    ):
        assert t in selected


def test_plan_upcoming_fomc_typo_still_selects_event_study():
    plan = plan_research(
        {
            "user_message": (
                "I'm reconsidering NVDA. Look at my previous research, find similar "
                "historical periods, stress test another 8% drop, and tell me whether "
                "my thesis still makes sense. an also think about any upcoming focmc "
                "how it could effect"
            ),
            "ticker": "NVDA",
            "thesis": {"id": "t1", "ticker": "NVDA"},
            "prior_specs": {},
            "research_plan": {},
            "trace": {},
        }
    )
    selected = plan["research_plan"]["research_tools_selected"]
    assert "find_analogs" in selected
    assert "run_scenario" in selected
    assert "run_event_study" in selected
    assert "run_backtest" in selected
    assert "get_market_regime" in selected


def test_compact_event_study_brief_keeps_means():
    from stocksense.orchestration.research_agent import _compact_tool_briefs

    briefs = _compact_tool_briefs(
        {
            "run_event_study": {
                "note": "Historical FOMC behavior only",
                "interpretation": {"summary": "NVDA around FOMC analyzed 64"},
                "spec": {
                    "ticker": "NVDA",
                    "event_source": "fomc",
                    "pre_window": 1,
                    "post_window": 1,
                },
                "result": {
                    "calendar_events": 80,
                    "eligible_events": 70,
                    "events_analyzed": 64,
                    "pre_stats": {"mean": 0.01, "median": 0.009, "positive_rate": 0.55},
                    "event_stats": {"mean": -0.002, "median": 0.0, "positive_rate": 0.48},
                    "post_stats": {"mean": 0.004, "median": 0.003, "positive_rate": 0.52},
                    "observations": [{"event_date": "2020-01-01"}] * 64,
                },
            }
        }
    )
    es = briefs["event_study"]
    assert es["events_analyzed"] == 64
    assert es["post_mean"] == 0.004
    assert "0.40%" in es["post_mean_pct"] or es["post_mean_pct"].endswith("%")
    assert "observations" not in es
