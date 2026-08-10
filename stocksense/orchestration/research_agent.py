"""
Phase 7/8 Research Agent — constrained LangGraph over deterministic P2–P6 tools.

Auth is request-scoped (ContextVar), never checkpointed.
Checkpoint thread ids are user-namespaced.
Trace contract: research_trace_v1.
Working memory: InMemorySaver (process-local only).
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from stocksense.core.config import get_chat_llm

logger = logging.getLogger(__name__)

TRACE_VERSION = "research_trace_v1"

RESEARCH_TOOLS = ("find_analogs", "run_scenario", "run_event_study", "run_backtest")
SUPPORT_TOOLS = ("get_thesis", "retrieve_research_memory")
WRITE_TOOLS = ("attach_evidence",)


@dataclass(frozen=True)
class RequestAuth:
    user_id: str
    access_token: str


_request_auth: ContextVar[Optional[RequestAuth]] = ContextVar(
    "research_agent_auth", default=None
)


def get_request_auth() -> RequestAuth:
    auth = _request_auth.get()
    if auth is None:
        raise RuntimeError("Request auth not set for research agent turn")
    return auth


def checkpoint_thread_id(user_id: str, client_thread_id: str) -> str:
    return f"{user_id}:{client_thread_id}"


_WRITE_RE = re.compile(
    r"\b(attach|save|add to (my )?thesis|persist|write (this|it) (to|into))\b",
    re.I,
)
_ANALOG_RE = re.compile(
    r"\b("
    r"analog|analogs|similar|"
    r"historical period|historical periods|"
    r"historical momentum|historical movement|"
    r"look alike|same pattern|past periods|"
    r"look(?:ed|s)? like"
    r")\b",
    re.I,
)
_SCENARIO_RE = re.compile(
    r"\b(scenario|stress|what[- ]?if|drop|crash|shock|down\s+\d)\b", re.I
)
_BACKTEST_RE = re.compile(
    r"\b("
    r"sma|moving average|crossover|cross[- ]?over|"
    r"20\s*/\s*50|50\s*/\s*200|strategy lab|backtest"
    r")\b",
    re.I,
)
_EVENT_STUDY_RE = re.compile(
    r"\b("
    r"fomc|fed(?:eral)? reserve|fed decision|"
    r"rate hike|rate cut|interest rate|"
    r"event study"
    r")\b",
    re.I,
)
_PCT_RE = re.compile(r"(-?\d+(?:\.\d+)?)\s*%")


class ResearchState(TypedDict, total=False):
    messages: List[Dict[str, str]]
    user_id: str
    # access_token intentionally omitted — never checkpointed
    ticker: Optional[str]
    thesis_id: Optional[str]
    user_message: str
    write_intent: bool
    need_memory: bool
    research_plan: Dict[str, Any]
    prior_specs: Dict[str, Any]
    memory_refs: List[Dict[str, Any]]
    memory_available: bool
    memory_error: Optional[str]
    hydrated_context: List[Dict[str, Any]]
    thesis: Optional[Dict[str, Any]]
    tool_results: Dict[str, Any]
    citations: List[Dict[str, Any]]
    answer: str
    trace: Dict[str, Any]
    writes: int
    pending_attach: Optional[Dict[str, Any]]
    thread_id: str  # client-facing thread id


def _safe_error_message(exc: BaseException, limit: int = 240) -> str:
    msg = str(exc) or exc.__class__.__name__
    # scrub likely secrets
    msg = re.sub(r"Bearer\s+\S+", "Bearer [redacted]", msg, flags=re.I)
    msg = re.sub(r"eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+", "[jwt]", msg)
    if len(msg) > limit:
        return msg[: limit - 3] + "..."
    return msg


def _last_user_text(state: ResearchState) -> str:
    if state.get("user_message"):
        return state["user_message"]
    for m in reversed(state.get("messages") or []):
        if m.get("role") == "user":
            return m.get("content") or ""
    return ""


def _extract_ticker(text: str, fallback: Optional[str] = None) -> Optional[str]:
    known = ("NVDA", "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "AMD", "AVGO")
    upper = text.upper()
    for k in known:
        if re.search(rf"\b{k}\b", upper):
            return k
    m = re.search(r"\$([A-Za-z]{1,5})\b", text)
    if m:
        return m.group(1).upper()
    if fallback:
        return fallback.upper()
    return None


def _detect_write_intent(text: str) -> bool:
    return bool(_WRITE_RE.search(text))


def _shock_from_text(text: str, prior: Optional[float] = None) -> Optional[float]:
    m = _PCT_RE.search(text)
    if not m:
        return prior
    val = float(m.group(1))
    if re.search(r"\b(drop|down|crash|fall|decline)\b", text, re.I) and val > 0:
        return -val / 100.0
    if abs(val) > 1:
        return (-abs(val) if val > 0 and "drop" in text.lower() else val) / 100.0
    return val


def _split_tools(ordered: List[str]) -> Dict[str, List[str]]:
    research = [t for t in ordered if t in RESEARCH_TOOLS]
    support = [t for t in ordered if t in SUPPORT_TOOLS]
    not_selected = [t for t in RESEARCH_TOOLS if t not in research]
    return {
        "research_tools_selected": research,
        "support_tools_used": support,
        "not_selected": not_selected,
        "tools": ordered,  # backward-compatible full list
    }


def understand_request(state: ResearchState) -> Dict[str, Any]:
    text = _last_user_text(state)
    prior_ticker = state.get("ticker")
    ticker = _extract_ticker(text, prior_ticker)
    write_intent = _detect_write_intent(text)
    need_memory = True
    prior_specs = dict(state.get("prior_specs") or {})
    shock = _shock_from_text(text, (prior_specs.get("scenario") or {}).get("shock_value"))
    if shock is not None:
        scen = dict(prior_specs.get("scenario") or {})
        scen["shock_value"] = shock
        if ticker:
            scen["ticker"] = ticker
        prior_specs["scenario"] = scen

    return {
        "user_message": text,
        "ticker": ticker,
        "write_intent": write_intent,
        "need_memory": need_memory,
        "prior_specs": prior_specs,
        "trace": {
            **(state.get("trace") or {}),
            "intent": "evaluate_existing_thesis"
            if ticker
            else "research",
            "write_intent": write_intent,
        },
    }


def retrieve_memory_if_needed(state: ResearchState) -> Dict[str, Any]:
    auth = get_request_auth()
    if not state.get("need_memory"):
        return {
            "memory_refs": [],
            "memory_available": True,
            "hydrated_context": [],
            "memory_error": None,
        }
    from stocksense.memory.hydrate import retrieve_and_hydrate

    q = state.get("user_message") or ""
    if state.get("ticker"):
        q = f"{state['ticker']} {q}"
    result = retrieve_and_hydrate(
        q,
        user_id=auth.user_id,
        access_token=auth.access_token,
        ticker=state.get("ticker"),
        top_k=6,
    )
    support = list((state.get("research_plan") or {}).get("support_tools_used") or [])
    if "retrieve_research_memory" not in support:
        support = support + ["retrieve_research_memory"]
    plan = dict(state.get("research_plan") or {})
    plan["support_tools_used"] = support
    return {
        "memory_refs": result.get("refs") or [],
        "hydrated_context": result.get("hydrated") or [],
        "memory_available": bool(result.get("available")),
        "memory_error": (
            _safe_error_message(Exception(str(result.get("error"))))
            if result.get("error")
            else None
        ),
        "research_plan": plan,
        "trace": {
            **(state.get("trace") or {}),
            "memory_records": len(result.get("hydrated") or []),
            "memory_available": bool(result.get("available")),
            "support_tools_used": support,
        },
    }


def resolve_thesis(state: ResearchState) -> Dict[str, Any]:
    from stocksense.db.supabase_client import (
        get_active_thesis_for_ticker,
        get_user_theses,
    )

    auth = get_request_auth()
    ticker = state.get("ticker")
    thesis = None
    if state.get("thesis_id"):
        theses = get_user_theses(auth.user_id, auth.access_token, ticker)
        thesis = next(
            (t for t in theses if str(t.get("id")) == str(state["thesis_id"])),
            None,
        )
    if not thesis and ticker:
        thesis = get_active_thesis_for_ticker(
            auth.user_id, auth.access_token, ticker
        )
    return {
        "thesis": thesis,
        "thesis_id": str(thesis["id"]) if thesis else state.get("thesis_id"),
        "ticker": (thesis.get("ticker") if thesis else ticker),
        "trace": {
            **(state.get("trace") or {}),
            "thesis_resolved": bool(thesis),
        },
    }


def plan_research(state: ResearchState) -> Dict[str, Any]:
    text = state.get("user_message") or ""
    prior = state.get("prior_specs") or {}
    research: List[str] = []
    support: List[str] = list(
        (state.get("research_plan") or {}).get("support_tools_used") or []
    )

    follow_up_only = (
        prior.get("scenario")
        and _PCT_RE.search(text)
        and re.search(r"\b(make (it|that)|change|instead|now)\b", text, re.I)
        and not _ANALOG_RE.search(text)
        and not _BACKTEST_RE.search(text)
        and not _EVENT_STUDY_RE.search(text)
    )

    if follow_up_only:
        research = ["run_scenario"]
    else:
        if state.get("thesis") or state.get("ticker"):
            if "get_thesis" not in support:
                support.append("get_thesis")
        if _ANALOG_RE.search(text) or re.search(r"\bsimilar historical\b", text, re.I):
            research.append("find_analogs")
        if _SCENARIO_RE.search(text) or _PCT_RE.search(text):
            research.append("run_scenario")
        if _BACKTEST_RE.search(text):
            research.append("run_backtest")
        if _EVENT_STUDY_RE.search(text):
            research.append("run_event_study")
        if not research:
            if re.search(r"\b(reconsider|still make sense|thesis)\b", text, re.I):
                research.extend(["find_analogs", "run_scenario"])

    # de-dupe
    def uniq(xs: List[str]) -> List[str]:
        seen = set()
        out = []
        for x in xs:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out

    research = uniq(research)
    support = uniq(support)
    ordered = support + research
    split = _split_tools(ordered)
    split["support_tools_used"] = support
    split["research_tools_selected"] = research
    split["not_selected"] = [t for t in RESEARCH_TOOLS if t not in research]
    split["tools"] = ordered
    plan = {
        **split,
        "scenario_shock": (prior.get("scenario") or {}).get("shock_value"),
        "write_tools_used": [],
    }
    return {
        "research_plan": plan,
        "trace": {
            **(state.get("trace") or {}),
            "research_tools_selected": research,
            "support_tools_used": support,
            "not_selected": plan["not_selected"],
            "tools_selected": ordered,
        },
    }


def execute_tools(state: ResearchState) -> Dict[str, Any]:
    from stocksense.research.analog_service import run_analog_search_request
    from stocksense.research.scenario_service import run_scenario_request
    from stocksense.research.service import run_event_study_request
    from stocksense.research.strategy_service import run_strategy_request

    auth = get_request_auth()
    plan = state.get("research_plan") or {}
    tools = plan.get("tools") or []
    results: Dict[str, Any] = dict(state.get("tool_results") or {})
    prior_specs = dict(state.get("prior_specs") or {})
    ticker = state.get("ticker") or "NVDA"
    text = state.get("user_message") or ""

    if "get_thesis" in tools and state.get("thesis"):
        t = state["thesis"]
        results["get_thesis"] = {
            "id": t.get("id"),
            "ticker": t.get("ticker"),
            "thesis_summary": t.get("thesis_summary"),
            "conviction_level": t.get("conviction_level"),
            "kill_criteria": t.get("structured_kill_criteria")
            or t.get("kill_criteria"),
            "status": t.get("status"),
        }

    if "find_analogs" in tools:
        q = (
            text
            if _ANALOG_RE.search(text)
            else f"Find historical analogs for {ticker} similar return path periods"
        )
        try:
            prior = None
            if prior_specs.get("analog"):
                from stocksense.core.contracts import AnalogSpec

                prior = AnalogSpec.model_validate(prior_specs["analog"])
            out = run_analog_search_request(q, prior_spec=prior)
            results["find_analogs"] = {
                "spec": out.get("spec"),
                "interpretation": out.get("interpretation"),
                "result": out.get("result"),
                "result_summary": {
                    k: out.get("result", {}).get(k)
                    for k in ("n_matches", "matches", "forward_horizon_days")
                    if isinstance(out.get("result"), dict)
                },
                "evidence_ledger": out.get("evidence_ledger"),
            }
            if out.get("spec"):
                prior_specs["analog"] = out["spec"]
        except Exception as e:
            results["find_analogs"] = {
                "error": _safe_error_message(e),
                "error_code": e.__class__.__name__,
            }

    if "run_scenario" in tools:
        shock = (prior_specs.get("scenario") or {}).get("shock_value")
        if shock is None:
            shock = _shock_from_text(text, -0.08) or -0.08
        pct = abs(float(shock) * 100)
        direction = "drops" if shock < 0 else "rises"
        q = f"What if {ticker} {direction} {pct:g}% in one day?"
        try:
            prior = None
            if prior_specs.get("scenario"):
                from stocksense.core.contracts import ScenarioSpec

                try:
                    prior = ScenarioSpec.model_validate(prior_specs["scenario"])
                except Exception:
                    prior = None
            out = run_scenario_request(
                q,
                user_id=auth.user_id,
                access_token=auth.access_token,
                prior_spec=prior,
            )
            results["run_scenario"] = {
                "spec": out.get("spec"),
                "result": out.get("result"),
                "interpretation": out.get("interpretation"),
                "evidence_ledger": out.get("evidence_ledger"),
                "disclaimer": out.get("disclaimer"),
                "thesis_id": out.get("thesis_id"),
            }
            if out.get("spec"):
                prior_specs["scenario"] = out["spec"]
        except Exception as e:
            results["run_scenario"] = {
                "error": _safe_error_message(e),
                "error_code": e.__class__.__name__,
            }

    if "run_backtest" in tools:
        q = (
            text
            if _BACKTEST_RE.search(text) and re.search(r"\b\d+\s*/\s*\d+\b", text)
            else f"Backtest a 20/50 SMA crossover on {ticker} since 2020."
        )
        try:
            prior = None
            if prior_specs.get("strategy"):
                from stocksense.core.contracts import StrategySpec

                try:
                    prior = StrategySpec.model_validate(prior_specs["strategy"])
                except Exception:
                    prior = None
            out = run_strategy_request(q, prior_spec=prior)
            results["run_backtest"] = {
                "spec": out.get("spec"),
                "result": out.get("result"),
                "interpretation": out.get("interpretation"),
                "evidence_ledger": out.get("evidence_ledger"),
            }
            if out.get("spec"):
                prior_specs["strategy"] = out["spec"]
        except Exception as e:
            results["run_backtest"] = {
                "error": _safe_error_message(e),
                "error_code": e.__class__.__name__,
            }

    if "run_event_study" in tools:
        # Multi-intent sentences often only mention FOMC; keep a clean lab question.
        q = f"What happens to {ticker} around FOMC decisions?"
        try:
            prior = None
            if prior_specs.get("event_study"):
                from stocksense.core.contracts import EventStudySpec

                try:
                    prior = EventStudySpec.model_validate(prior_specs["event_study"])
                except Exception:
                    prior = None
            out = run_event_study_request(q, prior, use_llm=False)
            results["run_event_study"] = {
                "spec": out.get("spec"),
                "result": out.get("result"),
                "interpretation": out.get("interpretation"),
                "evidence_ledger": out.get("evidence_ledger"),
                "note": (
                    "Historical FOMC behavior only — no live upcoming-meeting calendar."
                ),
            }
            if out.get("spec"):
                prior_specs["event_study"] = out["spec"]
        except Exception as e:
            results["run_event_study"] = {
                "error": _safe_error_message(e),
                "error_code": e.__class__.__name__,
            }

    return {"tool_results": results, "prior_specs": prior_specs}


def collect_evidence(state: ResearchState) -> Dict[str, Any]:
    return {"tool_results": state.get("tool_results") or {}}


def hydrate_memory_sources(state: ResearchState) -> Dict[str, Any]:
    hydrated = [
        h
        for h in (state.get("hydrated_context") or [])
        if h.get("validated") and h.get("canonical")
    ]
    return {"hydrated_context": hydrated}


def validate_citations(state: ResearchState) -> Dict[str, Any]:
    citations: List[Dict[str, Any]] = []
    for h in state.get("hydrated_context") or []:
        citations.append(
            {
                "id": h.get("citation_id"),
                "source_type": h.get("source_type"),
                "source_id": h.get("source_id"),
                "hypothetical": h.get("hypothetical"),
                "validated": True,
            }
        )
    tools = state.get("tool_results") or {}
    if tools.get("get_thesis") and not tools["get_thesis"].get("error"):
        citations.append(
            {
                "id": f"thesis:{tools['get_thesis'].get('id')}",
                "source_type": "thesis",
                "source_id": tools["get_thesis"].get("id"),
                "hypothetical": False,
                "validated": True,
            }
        )
    for key, etype in (
        ("find_analogs", "analog_search"),
        ("run_scenario", "scenario"),
        ("run_event_study", "event_study"),
        ("run_backtest", "backtest"),
    ):
        block = tools.get(key) or {}
        ledger = block.get("evidence_ledger") or []
        for ev in ledger:
            citations.append(
                {
                    "id": ev.get("id") or f"{etype}:run",
                    "source_type": etype,
                    "source_id": ev.get("id"),
                    "hypothetical": etype == "scenario"
                    or bool(ev.get("hypothetical")),
                    "validated": True,
                }
            )
    seen = set()
    uniq = []
    for c in citations:
        cid = c.get("id")
        if cid in seen:
            continue
        seen.add(cid)
        uniq.append(c)
    return {
        "citations": uniq,
        "trace": {
            **(state.get("trace") or {}),
            "citations_validated": sum(1 for c in uniq if c.get("validated")),
            "citations_total": len(uniq),
        },
    }


def synthesize(state: ResearchState) -> Dict[str, Any]:
    tools = state.get("tool_results") or {}
    hydrated = state.get("hydrated_context") or []
    thesis = state.get("thesis")
    plan = state.get("research_plan") or {}

    lines = []
    ticker = state.get("ticker") or "?"
    lines.append(f"## Research assessment — {ticker}")
    if not state.get("memory_available"):
        lines.append(
            f"_Semantic memory unavailable:_ {state.get('memory_error') or 'unknown'}"
        )
    elif hydrated:
        lines.append(
            f"Retrieved **{len(hydrated)}** prior research record(s) "
            "(hydrated from Supabase)."
        )
    if thesis:
        lines.append(f"**Active thesis:** {thesis.get('thesis_summary')}")
    if tools.get("find_analogs") and not tools["find_analogs"].get("error"):
        interp = (tools["find_analogs"].get("interpretation") or {}).get("summary")
        lines.append(f"**Analogs:** {interp or 'completed'}")
    elif tools.get("find_analogs", {}).get("error"):
        lines.append(f"**Analogs error:** {tools['find_analogs']['error']}")
    if tools.get("run_scenario") and not tools["run_scenario"].get("error"):
        r = tools["run_scenario"].get("result") or {}
        lines.append(
            f"**Scenario (hypothetical):** triggered={r.get('criteria_triggered')}, "
            f"evaluated={r.get('criteria_evaluated')}, material={r.get('material')}"
        )
        lines.append("_This WHAT-IF does not modify the thesis._")
    elif tools.get("run_scenario", {}).get("error"):
        lines.append(f"**Scenario error:** {tools['run_scenario']['error']}")
    if tools.get("run_backtest") and not tools["run_backtest"].get("error"):
        interp = (tools["run_backtest"].get("interpretation") or {}).get("summary")
        lines.append(f"**Strategy Lab (SMA):** {interp or 'completed'}")
    elif tools.get("run_backtest", {}).get("error"):
        lines.append(f"**Strategy Lab error:** {tools['run_backtest']['error']}")
    if tools.get("run_event_study") and not tools["run_event_study"].get("error"):
        interp = (tools["run_event_study"].get("interpretation") or {}).get("summary")
        lines.append(f"**Event Study (FOMC, historical):** {interp or 'completed'}")
        note = tools["run_event_study"].get("note")
        if note:
            lines.append(f"_{note}_")
    elif tools.get("run_event_study", {}).get("error"):
        lines.append(f"**Event Study error:** {tools['run_event_study']['error']}")

    cite_ids = [c.get("id") for c in (state.get("citations") or []) if c.get("id")]
    if cite_ids:
        lines.append("**Citations:** " + ", ".join(str(x) for x in cite_ids))

    base = "\n\n".join(lines)

    try:
        llm = get_chat_llm(
            model="gemini-3.1-flash-lite", temperature=0.2, max_output_tokens=1024
        )
        prompt = (
            "You are CatalystEdge Research Agent. Ground every claim in the "
            "provided tool results and hydrated memory. Never invent numbers. "
            "Mark scenarios as hypothetical. Be concise. "
            "Event Study is historical FOMC behavior only — do not invent the next "
            "meeting date. If a lab was not in tool results, say it was not run.\n\n"
            f"User: {state.get('user_message')}\n\n"
            f"Plan: {json.dumps(plan, default=str)}\n"
            f"Thesis: {json.dumps(thesis, default=str)[:2000] if thesis else None}\n"
            f"Hydrated memory: {json.dumps(hydrated, default=str)[:3000]}\n"
            f"Tool results: {json.dumps(_sanitize_tool_results(tools), default=str)[:6000]}\n"
            f"Citations: {json.dumps(cite_ids)}\n\n"
            "Write a short grounded answer synthesizing only measured labs."
        )
        resp = llm.invoke(prompt)
        content = getattr(resp, "content", None) or str(resp)
        if isinstance(content, list):
            content = " ".join(
                (c.get("text") if isinstance(c, dict) else str(c)) for c in content
            )
        answer = str(content).strip() or base
    except Exception as e:
        logger.warning("synthesize LLM failed: %s", _safe_error_message(e))
        answer = base

    return {
        "answer": answer,
        "messages": (state.get("messages") or [])
        + [
            {"role": "user", "content": state.get("user_message") or ""},
            {"role": "assistant", "content": answer},
        ],
    }


def maybe_confirm_write(state: ResearchState) -> Dict[str, Any]:
    plan = dict(state.get("research_plan") or {})
    if not state.get("write_intent"):
        plan["write_tools_used"] = []
        return {
            "writes": 0,
            "pending_attach": None,
            "research_plan": plan,
            "trace": {**(state.get("trace") or {}), "writes": 0, "write_tools_used": []},
        }

    from stocksense.db.supabase_client import attach_thesis_evidence

    auth = get_request_auth()
    tools = state.get("tool_results") or {}
    thesis_id = state.get("thesis_id")
    writes = 0
    attached = []
    errors = []
    write_tools: List[str] = []

    for key in ("run_scenario", "find_analogs"):
        block = tools.get(key) or {}
        ledger = block.get("evidence_ledger") or []
        if not ledger or not thesis_id:
            continue
        evidence = ledger[0]
        try:
            out = attach_thesis_evidence(
                auth.user_id,
                auth.access_token,
                str(thesis_id),
                evidence,
            )
            writes += 1 if out.get("attached") or out.get("already_attached") else 0
            attached.append(
                {
                    "key": key,
                    "attached": bool(out.get("attached")),
                    "already_attached": bool(out.get("already_attached")),
                }
            )
            if "attach_evidence" not in write_tools:
                write_tools.append("attach_evidence")
        except Exception as e:
            errors.append(
                {
                    "tool": "attach_evidence",
                    "error_code": e.__class__.__name__,
                    "message": _safe_error_message(e),
                }
            )

    plan["write_tools_used"] = write_tools
    return {
        "writes": writes,
        "pending_attach": {"attached": attached, "errors": errors},
        "research_plan": plan,
        "trace": {
            **(state.get("trace") or {}),
            "writes": writes,
            "write_tools_used": write_tools,
        },
    }


def _timed_node(name: str, fn: Callable[[ResearchState], Dict[str, Any]]):
    def wrapped(state: ResearchState) -> Dict[str, Any]:
        t0 = time.perf_counter()
        try:
            out = fn(state) or {}
            ok = True
            note = ""
        except Exception as e:
            ms = int((time.perf_counter() - t0) * 1000)
            base_trace = dict(state.get("trace") or {})
            nodes = list(base_trace.get("nodes") or [])
            nodes.append(
                {
                    "name": name,
                    "ok": False,
                    "latency_ms": ms,
                    "note": _safe_error_message(e),
                }
            )
            base_trace["nodes"] = nodes
            raise
        ms = int((time.perf_counter() - t0) * 1000)
        base_trace = dict(state.get("trace") or {})
        out_trace = dict(out.get("trace") or {})
        merged = {**base_trace, **out_trace}
        nodes = list(base_trace.get("nodes") or [])
        if "nodes" in out_trace:
            nodes = list(out_trace.get("nodes") or nodes)
        nodes.append({"name": name, "ok": ok, "latency_ms": ms, "note": note})
        merged["nodes"] = nodes
        result = dict(out)
        result["trace"] = merged
        return result

    return wrapped


def _sanitize_tool_results(tool_results: Dict[str, Any]) -> Dict[str, Any]:
    clean: Dict[str, Any] = {}
    for k, v in (tool_results or {}).items():
        if not isinstance(v, dict):
            clean[k] = v
            continue
        clean[k] = {kk: vv for kk, vv in v.items() if kk != "evidence_ledger"}
    return clean


def _collect_tool_errors(tool_results: Dict[str, Any]) -> List[Dict[str, str]]:
    errors = []
    for k, v in (tool_results or {}).items():
        if isinstance(v, dict) and v.get("error"):
            errors.append(
                {
                    "tool": k,
                    "error_code": str(v.get("error_code") or "ToolError"),
                    "message": _safe_error_message(Exception(str(v.get("error")))),
                }
            )
    return errors


def _collect_engine_repro(tool_results: Dict[str, Any]) -> List[Dict[str, Any]]:
    repro: List[Dict[str, Any]] = []
    for tool, block in (tool_results or {}).items():
        if not isinstance(block, dict) or block.get("error"):
            continue
        result = block.get("result") if isinstance(block.get("result"), dict) else {}
        r = (
            result.get("reproducibility")
            if isinstance(result.get("reproducibility"), dict)
            else None
        )
        if not r:
            continue
        entry = {
            "tool": tool,
            "engine_version": r.get("engine_version"),
            "criteria_hash": r.get("criteria_hash"),
            "price_data_hash": r.get("price_data_hash"),
        }
        repro.append({k: v for k, v in entry.items() if v is not None})
    return repro


def build_research_trace(
    *,
    run_id: str,
    thread_id: str,
    latency_ms_total: int,
    final: Dict[str, Any],
) -> Dict[str, Any]:
    plan = final.get("research_plan") or {}
    prior = final.get("prior_specs") or {}
    raw_trace = final.get("trace") or {}
    citations = final.get("citations") or []
    tool_results = final.get("tool_results") or {}
    shock = plan.get("scenario_shock")
    if shock is None:
        shock = (prior.get("scenario") or {}).get("shock_value")

    research = list(
        plan.get("research_tools_selected")
        or raw_trace.get("research_tools_selected")
        or []
    )
    support = list(
        plan.get("support_tools_used") or raw_trace.get("support_tools_used") or []
    )
    write_tools = list(
        plan.get("write_tools_used") or raw_trace.get("write_tools_used") or []
    )
    not_selected = list(plan.get("not_selected") or raw_trace.get("not_selected") or [])
    validated = int(
        raw_trace.get("citations_validated")
        or sum(1 for c in citations if c.get("validated"))
    )
    total = int(raw_trace.get("citations_total") or len(citations))
    pending = final.get("pending_attach")
    if isinstance(pending, dict):
        pending = {
            "attached": pending.get("attached") or [],
            "errors": pending.get("errors") or [],
        }

    return {
        "trace_version": TRACE_VERSION,
        "run_id": run_id,
        "thread_id": thread_id,
        "latency_ms_total": latency_ms_total,
        "nodes": list(raw_trace.get("nodes") or []),
        "intent": raw_trace.get("intent"),
        "write_intent": bool(final.get("write_intent")),
        "ticker": final.get("ticker"),
        "thesis_id": final.get("thesis_id"),
        "research_tools_selected": research,
        "support_tools_used": support,
        "write_tools_used": write_tools,
        "not_selected": not_selected,
        # compat
        "tools_selected": list(plan.get("tools") or research),
        "scenario_shock": shock,
        "memory": {
            "available": bool(final.get("memory_available")),
            "records": int(
                raw_trace.get("memory_records")
                or len(final.get("hydrated_context") or [])
            ),
            "error": final.get("memory_error"),
        },
        "tool_errors": _collect_tool_errors(tool_results),
        "engine_repro": _collect_engine_repro(tool_results),
        "citations_validated": validated,
        "citations_total": total,
        "writes": int(final.get("writes") or 0),
        "pending_attach": pending,
    }


def build_research_agent():
    g = StateGraph(ResearchState)
    g.add_node("understand_request", _timed_node("understand_request", understand_request))
    g.add_node(
        "retrieve_memory_if_needed",
        _timed_node("retrieve_memory_if_needed", retrieve_memory_if_needed),
    )
    g.add_node("resolve_thesis", _timed_node("resolve_thesis", resolve_thesis))
    g.add_node("plan_research", _timed_node("plan_research", plan_research))
    g.add_node("execute_tools", _timed_node("execute_tools", execute_tools))
    g.add_node("collect_evidence", _timed_node("collect_evidence", collect_evidence))
    g.add_node(
        "hydrate_memory_sources",
        _timed_node("hydrate_memory_sources", hydrate_memory_sources),
    )
    g.add_node("validate_citations", _timed_node("validate_citations", validate_citations))
    g.add_node("synthesize", _timed_node("synthesize", synthesize))
    g.add_node(
        "maybe_confirm_write", _timed_node("maybe_confirm_write", maybe_confirm_write)
    )

    g.add_edge(START, "understand_request")
    g.add_edge("understand_request", "retrieve_memory_if_needed")
    g.add_edge("retrieve_memory_if_needed", "resolve_thesis")
    g.add_edge("resolve_thesis", "plan_research")
    g.add_edge("plan_research", "execute_tools")
    g.add_edge("execute_tools", "collect_evidence")
    g.add_edge("collect_evidence", "hydrate_memory_sources")
    g.add_edge("hydrate_memory_sources", "validate_citations")
    g.add_edge("validate_citations", "synthesize")
    g.add_edge("synthesize", "maybe_confirm_write")
    g.add_edge("maybe_confirm_write", END)

    return g.compile(checkpointer=InMemorySaver())


_app = None


def reset_research_agent_for_tests() -> None:
    global _app
    _app = None


def get_research_agent():
    global _app
    if _app is None:
        _app = build_research_agent()
    return _app


def run_research_turn(
    *,
    message: str,
    user_id: str,
    access_token: str,
    thread_id: Optional[str] = None,
    ticker: Optional[str] = None,
    thesis_id: Optional[str] = None,
) -> Dict[str, Any]:
    app = get_research_agent()
    client_tid = thread_id or str(uuid.uuid4())
    ck_tid = checkpoint_thread_id(user_id, client_tid)
    run_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": ck_tid}}

    prior_specs: Dict[str, Any] = {}
    prior_ticker = ticker
    prior_thesis = thesis_id
    prior_messages: List[Dict[str, str]] = []
    try:
        snap = app.get_state(config)
        if snap and snap.values:
            vals = snap.values
            if "access_token" in vals and vals.get("access_token"):
                logger.error("BUG: access_token found in checkpoint — wiping")
            prior_specs = dict(vals.get("prior_specs") or {})
            prior_ticker = prior_ticker or vals.get("ticker")
            prior_thesis = prior_thesis or vals.get("thesis_id")
            prior_messages = list(vals.get("messages") or [])
    except Exception:
        pass

    token = _request_auth.set(RequestAuth(user_id=user_id, access_token=access_token))
    try:
        incoming: ResearchState = {
            "user_message": message,
            "user_id": user_id,
            "ticker": prior_ticker,
            "thesis_id": prior_thesis,
            "prior_specs": prior_specs,
            "thread_id": client_tid,
            "messages": prior_messages,
            "tool_results": {},
            "trace": {"nodes": [], "run_id": run_id},
            "writes": 0,
            "write_intent": False,
            "pending_attach": None,
            "research_plan": {},
        }
        t0 = time.perf_counter()
        final = app.invoke(incoming, config)
        latency_ms = int((time.perf_counter() - t0) * 1000)

        # Drop heavy / sensitive fields from checkpoint (auth never stored)
        try:
            app.update_state(
                config,
                {
                    "thesis": None,
                    "hydrated_context": [],
                    "memory_refs": [],
                    "tool_results": {},
                },
            )
        except Exception as e:
            logger.warning("checkpoint slim failed: %s", _safe_error_message(e))

        # Verify no access_token in checkpoint
        try:
            snap2 = app.get_state(config)
            if snap2 and snap2.values and snap2.values.get("access_token"):
                app.update_state(config, {"access_token": ""})
        except Exception:
            pass

        trace = build_research_trace(
            run_id=run_id,
            thread_id=client_tid,
            latency_ms_total=latency_ms,
            final=final,
        )
        plan = final.get("research_plan") or {}
        return {
            "run_id": run_id,
            "thread_id": client_tid,
            "answer": final.get("answer") or "",
            "ticker": final.get("ticker"),
            "thesis_id": final.get("thesis_id"),
            "research_plan": plan,
            "trace": trace,
            "citations": final.get("citations") or [],
            "memory_available": final.get("memory_available"),
            "memory_error": final.get("memory_error"),
            "writes": final.get("writes") or 0,
            "pending_attach": trace.get("pending_attach"),
            "tool_results": _sanitize_tool_results(final.get("tool_results") or {}),
            "prior_specs": final.get("prior_specs") or {},
        }
    finally:
        _request_auth.reset(token)


__all__ = [
    "run_research_turn",
    "get_research_agent",
    "build_research_agent",
    "build_research_trace",
    "reset_research_agent_for_tests",
    "checkpoint_thread_id",
    "TRACE_VERSION",
    "_detect_write_intent",
    "_extract_ticker",
    "_shock_from_text",
    "understand_request",
    "plan_research",
]
