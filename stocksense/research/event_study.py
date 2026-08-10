"""Deterministic event-study engine.

Pure: EventStudySpec + calendar events + PriceSeries → EventStudyResult.
No UUIDs, no datetime.now(), no evidence IDs, no LLM, no I/O.
"""

from __future__ import annotations

import hashlib
import statistics
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from stocksense.core.contracts import (
    EventExclusion,
    EventFilter,
    EventObservation,
    EventStudyResult,
    EventStudySpec,
    ReproducibilityMeta,
    WindowStats,
)
from stocksense.research.event_calendar import CalendarEvent

ENGINE_VERSION = "event_study_v1"


@dataclass(frozen=True)
class PriceSeries:
    """Adjusted closes keyed by YYYY-MM-DD. Must be sorted chronologically for index ops."""

    dates: Tuple[str, ...]
    closes: Tuple[float, ...]
    source: str = "fixture"
    mode: str = "adjusted_close"

    def __post_init__(self) -> None:
        if len(self.dates) != len(self.closes):
            raise ValueError("dates and closes length mismatch")
        if list(self.dates) != sorted(self.dates):
            raise ValueError("dates must be sorted ascending")

    @classmethod
    def from_pairs(
        cls,
        pairs: Sequence[Tuple[str, float]],
        *,
        source: str = "fixture",
        mode: str = "adjusted_close",
    ) -> "PriceSeries":
        ordered = sorted(pairs, key=lambda p: p[0])
        return cls(
            dates=tuple(p[0] for p in ordered),
            closes=tuple(float(p[1]) for p in ordered),
            source=source,
            mode=mode,
        )

    def index_map(self) -> Dict[str, int]:
        return {d: i for i, d in enumerate(self.dates)}

    def fingerprint(self) -> str:
        payload = "\n".join(f"{d}|{c:.10f}" for d, c in zip(self.dates, self.closes))
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return f"sha256:{digest}"

    @property
    def start(self) -> Optional[str]:
        return self.dates[0] if self.dates else None

    @property
    def end(self) -> Optional[str]:
        return self.dates[-1] if self.dates else None


def _resolve_event_index(date: str, index_map: Dict[str, int], dates: Tuple[str, ...]) -> Optional[int]:
    """Map calendar date to trading day index (exact or next available session)."""
    if date in index_map:
        return index_map[date]
    # Next trading day on/after calendar date
    for i, d in enumerate(dates):
        if d >= date:
            return i
    return None


def _stats(values: List[float]) -> WindowStats:
    if not values:
        return WindowStats(mean=None, median=None, positive_rate=None, n=0)
    return WindowStats(
        mean=float(statistics.mean(values)),
        median=float(statistics.median(values)),
        positive_rate=float(sum(1 for v in values if v > 0) / len(values)),
        n=len(values),
    )


def run_event_study(
    spec: EventStudySpec,
    calendar_events: Sequence[CalendarEvent],
    prices: PriceSeries,
) -> EventStudyResult:
    """Compute pre / event / post returns for eligible events with full price coverage.

    Return convention (event on trading index D, windows in trading days):
      pre_return   = close[D-1] / close[D - pre_window - 1] - 1
      event_return = close[D]   / close[D-1] - 1
      post_return  = close[D + post_window] / close[D] - 1
      cumulative   = close[D + post_window] / close[D - pre_window - 1] - 1
    """
    # calendar_events: already truncated to as_of by caller (or full set)
    cal_n = len(calendar_events)

    if spec.event_filter == EventFilter.ALL:
        eligible = list(calendar_events)
    else:
        want = spec.event_filter.value
        eligible = [e for e in calendar_events if e.decision == want]

    index_map = prices.index_map()
    observations: List[EventObservation] = []
    exclusions: List[EventExclusion] = []

    pre_w = spec.pre_window
    post_w = spec.post_window

    for ev in eligible:
        d_idx = _resolve_event_index(ev.date, index_map, prices.dates)
        if d_idx is None:
            exclusions.append(EventExclusion(date=ev.date, reason="missing_event_day"))
            continue

        pre_anchor = d_idx - pre_w - 1
        pre_end = d_idx - 1
        post_end = d_idx + post_w

        if pre_anchor < 0 or pre_end < 0:
            exclusions.append(EventExclusion(date=ev.date, reason="insufficient_pre_window"))
            continue
        if post_end >= len(prices.closes):
            exclusions.append(EventExclusion(date=ev.date, reason="insufficient_post_window"))
            continue

        c_pre_anchor = prices.closes[pre_anchor]
        c_pre_end = prices.closes[pre_end]
        c_event = prices.closes[d_idx]
        c_post = prices.closes[post_end]

        if c_pre_anchor == 0 or c_pre_end == 0 or c_event == 0:
            exclusions.append(EventExclusion(date=ev.date, reason="invalid_price"))
            continue

        pre_return = c_pre_end / c_pre_anchor - 1.0
        event_return = c_event / c_pre_end - 1.0
        post_return = c_post / c_event - 1.0
        cumulative = c_post / c_pre_anchor - 1.0

        observations.append(
            EventObservation(
                event_date=prices.dates[d_idx],
                classification=ev.decision,
                pre_return=pre_return,
                event_return=event_return,
                post_return=post_return,
                cumulative_window_return=cumulative,
            )
        )

    # Stable order by event_date
    observations.sort(key=lambda o: o.event_date)
    exclusions.sort(key=lambda e: e.date)

    pre_stats = _stats([o.pre_return for o in observations])
    event_stats = _stats([o.event_return for o in observations])
    post_stats = _stats([o.post_return for o in observations])

    repro = ReproducibilityMeta(
        calendar_id=spec.calendar_id,
        engine_version=ENGINE_VERSION,
        price_source=prices.source,
        price_mode=prices.mode,
        price_start=prices.start,
        price_end=prices.end,
        price_data_hash=prices.fingerprint(),
        as_of=spec.as_of,
    )

    return EventStudyResult(
        spec=spec,
        calendar_events=cal_n,
        eligible_events=len(eligible),
        events_analyzed=len(observations),
        excluded_events=len(exclusions),
        exclusions=exclusions,
        pre_stats=pre_stats,
        event_stats=event_stats,
        post_stats=post_stats,
        observations=observations,
        reproducibility=repro,
    )
