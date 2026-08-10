"""Frozen event calendars (versioned JSON)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Literal, Optional

Decision = Literal["hike", "cut", "hold"]

_CALENDARS_DIR = Path(__file__).resolve().parent / "calendars"


@dataclass(frozen=True)
class CalendarEvent:
    date: str  # YYYY-MM-DD
    decision: Decision


@dataclass(frozen=True)
class EventCalendar:
    calendar_id: str
    timezone: str
    events: List[CalendarEvent]


def load_calendar(calendar_id: str = "fomc_v1") -> EventCalendar:
    path = _CALENDARS_DIR / f"{calendar_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Unknown calendar_id={calendar_id!r} ({path})")
    raw = json.loads(path.read_text(encoding="utf-8"))
    events = [
        CalendarEvent(date=e["date"], decision=e["decision"])
        for e in raw["events"]
    ]
    events.sort(key=lambda e: e.date)
    return EventCalendar(
        calendar_id=raw["calendar_id"],
        timezone=raw.get("timezone", "America/New_York"),
        events=events,
    )


def events_up_to(calendar: EventCalendar, as_of: Optional[str]) -> List[CalendarEvent]:
    if not as_of:
        return list(calendar.events)
    return [e for e in calendar.events if e.date <= as_of]
