"""Interpretation of EventStudyResult — Gemini optional; never blocks the study."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Set

from stocksense.core.contracts import EventStudyResult, WindowStats

logger = logging.getLogger(__name__)

_PCT_RE = re.compile(r"([-+]?\d+(?:\.\d+)?)\s*%")
_NUM_RE = re.compile(r"(?<![A-Za-z0-9_/])([-+]?\d+(?:\.\d+)?)(?![A-Za-z0-9_])")


def _fmt_pct(v: Optional[float]) -> str:
    if v is None:
        return "n/a"
    return f"{v * 100:+.2f}%"


def _fmt_rate(v: Optional[float]) -> str:
    if v is None:
        return "n/a"
    return f"{v * 100:.1f}%"


def deterministic_summary(result: EventStudyResult, evidence_id: str) -> Dict[str, Any]:
    spec = result.spec
    summary = (
        f"{spec.ticker} around FOMC ({spec.event_filter.value}): "
        f"analyzed {result.events_analyzed}/{result.eligible_events} eligible "
        f"({result.calendar_events} calendar). "
        f"Pre {spec.pre_window}d mean {_fmt_pct(result.pre_stats.mean)}; "
        f"event-day mean {_fmt_pct(result.event_stats.mean)}; "
        f"post {spec.post_window}d mean {_fmt_pct(result.post_stats.mean)}."
    )
    return {
        "mode": "deterministic",
        "summary": summary,
        "observations": [
            {
                "text": summary,
                "evidence_id": evidence_id,
                "metrics": ["pre.mean", "event.mean", "post.mean"],
            }
        ],
        "caveats": [
            "Deterministic summary (LLM unavailable or rejected).",
            "Past FOMC windows are not predictive of future returns.",
            f"Price fingerprint: {result.reproducibility.price_data_hash[:18]}…",
        ],
    }


def _allowed_number_tokens(result: EventStudyResult) -> Set[str]:
    """Canonical display tokens the model may quote."""
    allowed: Set[str] = {
        str(result.calendar_events),
        str(result.eligible_events),
        str(result.events_analyzed),
        str(result.excluded_events),
        str(result.spec.pre_window),
        str(result.spec.post_window),
    }

    def add_stats(s: WindowStats) -> None:
        for v in (s.mean, s.median, s.positive_rate):
            if v is None:
                continue
            allowed.add(f"{v * 100:.2f}")
            allowed.add(f"{v * 100:.1f}")
            allowed.add(f"{abs(v) * 100:.2f}")
            allowed.add(f"{abs(v) * 100:.1f}")
            allowed.add(f"{v:.4f}")
            allowed.add(f"{v:.6f}")

    add_stats(result.pre_stats)
    add_stats(result.event_stats)
    add_stats(result.post_stats)
    return allowed


def validate_interpretation(
    interp: Dict[str, Any],
    result: EventStudyResult,
    evidence_id: str,
) -> Optional[str]:
    """Return error string if invalid; None if OK."""
    if not isinstance(interp, dict):
        return "interpretation must be an object"
    obs = interp.get("observations") or []
    for item in obs:
        eid = item.get("evidence_id")
        if eid and eid != evidence_id:
            return f"unknown evidence_id {eid}"
        for path in item.get("metrics") or []:
            if path not in {
                "pre.mean",
                "pre.median",
                "pre.positive_rate",
                "event.mean",
                "event.median",
                "event.positive_rate",
                "post.mean",
                "post.median",
                "post.positive_rate",
            }:
                return f"unknown metric path {path}"

    allowed = _allowed_number_tokens(result)
    texts = [interp.get("summary") or ""]
    texts.extend(str(x.get("text") or "") for x in obs)
    blob = " ".join(texts)

    for m in _PCT_RE.finditer(blob):
        token = m.group(1)
        # normalize strip trailing zeros variants
        if token not in allowed and _normalize(token) not in allowed:
            return f"unsupported percent literal {token}%"

    return None


def _normalize(token: str) -> str:
    try:
        return f"{float(token):.2f}"
    except ValueError:
        return token


def _try_gemini(result: EventStudyResult, evidence_id: str) -> Optional[Dict[str, Any]]:
    try:
        from stocksense.core.config import get_google_api_key
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage
    except Exception as e:
        logger.info("Gemini interpret unavailable: %s", e)
        return None

    try:
        get_google_api_key()
    except Exception:
        return None

    payload = {
        "evidence_id": evidence_id,
        "ticker": result.spec.ticker,
        "events_analyzed": result.events_analyzed,
        "eligible_events": result.eligible_events,
        "calendar_events": result.calendar_events,
        "pre_window": result.spec.pre_window,
        "post_window": result.spec.post_window,
        "event_filter": result.spec.event_filter.value,
        "pre": result.pre_stats.model_dump(),
        "event": result.event_stats.model_dump(),
        "post": result.post_stats.model_dump(),
    }
    prompt = (
        "You interpret a completed event study. Use ONLY the numbers provided. "
        "Do not invent percentages. Reply with JSON only:\n"
        '{"summary":"...","observations":[{"text":"...","evidence_id":"'
        + evidence_id
        + '","metrics":["pre.mean","post.mean"]}],"caveats":["..."]}\n\n'
        f"DATA:\n{json.dumps(payload, default=str)}"
    )
    try:
        llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)
        raw = llm.invoke([HumanMessage(content=prompt)]).content
        if isinstance(raw, list):
            raw = "".join(str(x) for x in raw)
        text = str(raw).strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        data = json.loads(text)
        err = validate_interpretation(data, result, evidence_id)
        if err:
            logger.warning("Gemini interpretation rejected: %s", err)
            return None
        data["mode"] = "llm"
        return data
    except Exception as e:
        logger.warning("Gemini interpretation failed: %s", e)
        return None


def interpret_event_study(
    result: EventStudyResult,
    evidence_id: str,
    *,
    use_llm: bool = True,
) -> Dict[str, Any]:
    if use_llm:
        llm = _try_gemini(result, evidence_id)
        if llm is not None:
            return llm
    return deterministic_summary(result, evidence_id)
