"""Canonical analysis entry — HTTP, SSE, and scheduler should all call this.

Phase 0: wraps existing ReAct analysis and emits progress events so SSE can
become transport-only. Debate remains a separate challenge stage for now.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Optional

from stocksense.core.contracts import AnalysisEvent
from stocksense.core.evidence_ledger import ledger_from_analysis_payload
from stocksense.orchestration.react_flow import run_react_analysis

logger = logging.getLogger("stocksense.pipeline")

EmitFn = Callable[[AnalysisEvent], Awaitable[None]]


async def _noop_emit(event: AnalysisEvent) -> None:
    return None


async def run_analysis(
    ticker: str,
    *,
    force: bool = False,
    emit: Optional[EmitFn] = None,
    thesis_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Single brain for stock analysis.

    Returns the analysis dict (same shape as run_react_analysis today) plus:
      - evidence_ledger: serialized Evidence list
      - thesis_id: optional context for later Diff (Phase 1)
    """
    emit = emit or _noop_emit
    t = ticker.upper().strip()

    await emit(
        AnalysisEvent(
            type="started",
            step="pipeline",
            message=f"Starting canonical analysis for {t}",
            progress=0.0,
            data={"ticker": t, "thesis_id": thesis_id},
        )
    )

    await emit(
        AnalysisEvent(
            type="tool_started",
            step="react_gather",
            message="Gathering evidence via ReAct tools",
            progress=0.1,
        )
    )

    # Existing production path (sync) — run off the event loop
    result = await asyncio.to_thread(run_react_analysis, t)

    await emit(
        AnalysisEvent(
            type="tool_completed",
            step="react_gather",
            message="Evidence gather complete",
            progress=0.7,
            data={"tools_used": result.get("tools_used", [])},
        )
    )

    # Normalize into Evidence Ledger (foundation for Thesis Diff / replay)
    price = result.get("price_data") or {}
    change = None
    if isinstance(price, dict):
        change = price.get("percent_change") or price.get("change_percent")
        if change is None and price.get("previous_close") and price.get("current_price"):
            try:
                prev = float(price["previous_close"])
                cur = float(price["current_price"])
                if prev:
                    change = (cur - prev) / prev
            except (TypeError, ValueError, ZeroDivisionError):
                change = None

    ledger = ledger_from_analysis_payload(
        t,
        price_change_pct=float(change) if change is not None else None,
        fundamentals=result.get("fundamental_data"),
        news_articles=result.get("news_articles") or [],
        as_of=datetime.now(timezone.utc),
    )

    result["evidence_ledger"] = [e.model_dump(mode="json") for e in ledger]
    result["pipeline"] = "canonical_v0"
    result["thesis_id"] = thesis_id

    await emit(
        AnalysisEvent(
            type="completed",
            step="pipeline",
            message="Analysis complete",
            progress=1.0,
            data={
                "evidence_count": len(ledger),
                "ticker": t,
            },
        )
    )

    return result
