"""Living Thesis contracts — Evidence, Claim, Thesis, ThesisDiff, Alert.

Permanent rule: models interpret; tools calculate.
No factual claim may appear without evidence_ids.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, model_validator


class EvidenceType(str, Enum):
    MARKET = "market"
    FUNDAMENTAL = "fundamental"
    NEWS = "news"
    EVENT_STUDY = "event_study"
    BACKTEST = "backtest"
    DERIVED = "derived"


class Evidence(BaseModel):
    """One typed fact. available_at prevents look-ahead in replay/eval."""

    id: str
    type: EvidenceType
    entity: str = Field(description="Ticker or instrument, e.g. NVDA")
    observed_at: datetime
    available_at: datetime = Field(
        description="When this fact could have been known — for replay as-of"
    )
    source: str
    metric: Optional[str] = None
    value: Optional[Union[float, str, int, bool]] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    url: Optional[str] = None


class ClaimStatus(str, Enum):
    PROPOSED = "proposed"
    SUPPORTED = "supported"
    WEAKENED = "weakened"
    INVALIDATED = "invalidated"
    UNCHANGED = "unchanged"


class Claim(BaseModel):
    text: str
    status: ClaimStatus = ClaimStatus.PROPOSED
    evidence_ids: List[str] = Field(default_factory=list)
    contradicting_evidence_ids: List[str] = Field(default_factory=list)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def require_evidence_for_factual(self) -> "Claim":
        # Proposed drafts may be empty until grounded; supported/weakened/etc must cite.
        if self.status != ClaimStatus.PROPOSED and not self.evidence_ids:
            raise ValueError(
                f"Claim with status={self.status} must include evidence_ids"
            )
        return self


class KillCriterionKind(str, Enum):
    DETERMINISTIC = "deterministic"
    QUALITATIVE = "qualitative"


class KillCriterion(BaseModel):
    id: str
    kind: KillCriterionKind
    label: str
    # Deterministic: metric + op + threshold
    metric: Optional[str] = None
    op: Optional[Literal["lt", "lte", "gt", "gte", "eq"]] = None
    threshold: Optional[float] = None
    # Qualitative: natural language monitored by AI with citations
    description: Optional[str] = None


class ThesisAssumption(BaseModel):
    id: str
    text: str
    monitor: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)
    status: ClaimStatus = ClaimStatus.PROPOSED


class ThesisStatus(str, Enum):
    ACTIVE = "active"
    TRIGGERED = "triggered"
    CLOSED = "closed"
    DRAFT = "draft"


class Thesis(BaseModel):
    id: Optional[str] = None
    ticker: str
    central_claim: str
    assumptions: List[ThesisAssumption] = Field(default_factory=list)
    kill_criteria: List[KillCriterion] = Field(default_factory=list)
    origin_snapshot: Dict[str, Any] = Field(default_factory=dict)
    status: ThesisStatus = ThesisStatus.DRAFT
    version: int = 1
    created_at: Optional[datetime] = None
    user_id: Optional[str] = None


class DiffItem(BaseModel):
    text: str
    evidence_ids: List[str] = Field(default_factory=list)
    assumption_id: Optional[str] = None
    criterion_id: Optional[str] = None


class ThesisDiff(BaseModel):
    thesis_id: str
    ticker: str
    as_of: datetime
    compared_to: datetime
    strengthened: List[DiffItem] = Field(default_factory=list)
    unchanged: List[DiffItem] = Field(default_factory=list)
    weakened: List[DiffItem] = Field(default_factory=list)
    invalidated: List[DiffItem] = Field(default_factory=list)
    new_risks: List[DiffItem] = Field(default_factory=list)
    triggered_criteria: List[DiffItem] = Field(default_factory=list)

    def material(self) -> bool:
        return bool(
            self.weakened
            or self.invalidated
            or self.triggered_criteria
            or self.new_risks
        )


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    UNREAD = "unread"
    READ = "read"
    ACKNOWLEDGED = "acknowledged"
    DISMISSED = "dismissed"


class Alert(BaseModel):
    """Single alert representation for scheduler, replay, API, and dashboard."""

    id: Optional[str] = None
    user_id: str
    thesis_id: str
    ticker: str
    severity: AlertSeverity = AlertSeverity.WARNING
    status: AlertStatus = AlertStatus.UNREAD
    title: str
    message: str
    triggered_criteria: List[str] = Field(default_factory=list)
    diff: Optional[ThesisDiff] = None
    evidence_ids: List[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    data: Dict[str, Any] = Field(default_factory=dict)


class AnalysisEvent(BaseModel):
    """SSE / progress event from the canonical pipeline."""

    type: str
    step: Optional[str] = None
    message: Optional[str] = None
    progress: Optional[float] = None
    data: Dict[str, Any] = Field(default_factory=dict)


# Resolve forward refs for Pydantic v2
Claim.model_rebuild()
ThesisAssumption.model_rebuild()
Thesis.model_rebuild()
ThesisDiff.model_rebuild()
Alert.model_rebuild()
AnalysisEvent.model_rebuild()
