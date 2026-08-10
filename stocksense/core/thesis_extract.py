"""Propose a thesis structure from an analysis + evidence ledger.

LLM may propose language; deterministic rules always supply kill criteria.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from stocksense.core.thesis_diff import snapshot_from_analysis

logger = logging.getLogger("stocksense.thesis_extract")


def _evidence_ids(ledger: Optional[List[Dict[str, Any]]]) -> List[str]:
    ids = []
    for e in ledger or []:
        eid = e.get("id")
        if isinstance(eid, str) and eid:
            ids.append(eid)
    return ids


def propose_thesis_from_analysis(
    analysis: Dict[str, Any],
    *,
    evidence_ledger: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Build a proposed thesis payload (not persisted).

    Returns fields compatible with CreateThesisRequest plus assumptions.
    """
    ticker = str(analysis.get("ticker") or "").upper()
    ledger = evidence_ledger if evidence_ledger is not None else analysis.get("evidence_ledger") or []
    snap = snapshot_from_analysis(analysis)
    eids = _evidence_ids(ledger)

    summary = (analysis.get("summary") or "").strip()
    if len(summary) < 10:
        sentiment = snap.get("sentiment") or "Unknown"
        conf = float(snap.get("confidence") or 0)
        summary = (
            f"{ticker} living thesis: current catalyst read is {sentiment} "
            f"at {conf:.0%} confidence. Hold while evidence supports the claim; "
            f"exit if kill criteria fire."
        )

    assumptions: List[Dict[str, Any]] = []
    themes = snap.get("key_themes") or []
    for i, theme in enumerate(themes[:4]):
        text = theme if isinstance(theme, str) else str(theme)
        assumptions.append(
            {
                "id": f"asm_{i}",
                "text": text,
                "monitor": ["news", "sentiment"],
                "evidence_ids": eids[:3],
                "status": "proposed",
            }
        )
    if not assumptions:
        assumptions.append(
            {
                "id": "asm_0",
                "text": f"Primary claim tracks {snap.get('sentiment') or 'current'} catalyst narrative",
                "monitor": ["news", "price"],
                "evidence_ids": eids[:3],
                "status": "proposed",
            }
        )

    # Prefer LLM polish when available; never block on failure / tests
    import os

    if not os.getenv("PYTEST_CURRENT_TEST") and not os.getenv("STOCKSENSE_SKIP_LLM"):
        try:
            polished = _llm_polish_summary(ticker, summary, snap)
            if polished and len(polished) >= 10:
                summary = polished[:800]
        except Exception as e:
            logger.debug("thesis LLM polish skipped: %s", e)

    structured_kill = [
        {
            "id": "kc_day_drop",
            "kind": "deterministic",
            "label": "One-day drop greater than 5%",
            "metric": "one_day_return",
            "op": "lte",
            "threshold": -0.05,
        }
    ]
    # Add margin kill if we have grossMargins in ledger
    for e in ledger:
        if e.get("metric") == "grossMargins":
            try:
                gm = float(e.get("value"))
                structured_kill.append(
                    {
                        "id": "kc_gross_margin",
                        "kind": "deterministic",
                        "label": f"Gross margin falls below {max(gm - 0.05, 0.5):.0%}",
                        "metric": "grossMargins",
                        "op": "lt",
                        "threshold": round(max(gm - 0.05, 0.5), 4),
                    }
                )
            except (TypeError, ValueError):
                pass
            break

    kill_criteria = [k["label"] for k in structured_kill]
    conf = float(snap.get("confidence") or 0)
    conviction = "high" if conf >= 0.75 else "medium" if conf >= 0.45 else "low"

    return {
        "ticker": ticker,
        "thesis_summary": summary[:2000],
        "conviction_level": conviction,
        "kill_criteria": kill_criteria,
        "assumptions": assumptions,
        "structured_kill_criteria": structured_kill,
        "origin_analysis_snapshot": snap,
        "origin_evidence": ledger,
        "origin_analysis_id": analysis.get("id"),
        "time_horizon": "medium",
        "thesis_type": "growth",
    }


def _llm_polish_summary(ticker: str, summary: str, snap: Dict[str, Any]) -> Optional[str]:
    """Optional short rewrite via Gemini; returns None on skip/failure."""
    try:
        from stocksense.core.config import get_google_api_key
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage
    except Exception:
        return None

    get_google_api_key()
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.2)
    prompt = (
        f"Rewrite this investment thesis for {ticker} in 2-3 crisp sentences. "
        f"Keep factual; do not invent numbers. Sentiment={snap.get('sentiment')}, "
        f"confidence={snap.get('confidence')}.\n\nSource:\n{summary[:1200]}"
    )
    resp = llm.invoke([HumanMessage(content=prompt)])
    text = getattr(resp, "content", None) or str(resp)
    if isinstance(text, list):
        text = " ".join(str(x) for x in text)
    return str(text).strip() or None
