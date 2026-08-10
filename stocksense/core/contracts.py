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


# ---------------------------------------------------------------------------
# Phase 2 — Event Study (typed experiment contracts)
# ---------------------------------------------------------------------------


class EventFilter(str, Enum):
    ALL = "all"
    HIKE = "hike"
    CUT = "cut"
    HOLD = "hold"


class EventSource(str, Enum):
    FOMC = "fomc"


class EventStudySpec(BaseModel):
    """Validated experiment definition. Models propose; code owns computation."""

    ticker: str
    event_source: EventSource = EventSource.FOMC
    event_filter: EventFilter = EventFilter.ALL
    pre_window: int = Field(default=1, ge=0)
    post_window: int = Field(default=1, ge=0)
    metric: Literal["simple_return"] = "simple_return"
    calendar_id: str = "fomc_v1"
    as_of: Optional[str] = Field(
        default=None,
        description="ISO date YYYY-MM-DD; calendar events after this are ignored",
    )

    @model_validator(mode="after")
    def normalize_ticker(self) -> "EventStudySpec":
        object.__setattr__(self, "ticker", self.ticker.strip().upper())
        return self


class WindowStats(BaseModel):
    mean: Optional[float] = None
    median: Optional[float] = None
    positive_rate: Optional[float] = None
    n: int = 0


class EventObservation(BaseModel):
    event_date: str
    classification: str
    pre_return: float
    event_return: float
    post_return: float
    cumulative_window_return: float


class EventExclusion(BaseModel):
    date: str
    reason: str


class ReproducibilityMeta(BaseModel):
    calendar_id: str
    engine_version: str
    price_source: str
    price_mode: str
    price_start: Optional[str] = None
    price_end: Optional[str] = None
    price_data_hash: str
    as_of: Optional[str] = None


class EventStudyResult(BaseModel):
    """Pure engine output. No evidence IDs / wall-clock timestamps."""

    spec: EventStudySpec
    calendar_events: int
    eligible_events: int
    events_analyzed: int
    excluded_events: int
    exclusions: List[EventExclusion] = Field(default_factory=list)
    pre_stats: WindowStats = Field(default_factory=WindowStats)
    event_stats: WindowStats = Field(default_factory=WindowStats)
    post_stats: WindowStats = Field(default_factory=WindowStats)
    observations: List[EventObservation] = Field(default_factory=list)
    reproducibility: ReproducibilityMeta


# ---------------------------------------------------------------------------
# Phase 3 — Strategy Lab (typed SMA backtest; no exec / no free params dict)
# ---------------------------------------------------------------------------


class StrategyKind(str, Enum):
    SMA_CROSSOVER = "sma_crossover"


class SmaCrossoverParams(BaseModel):
    fast_window: int = Field(default=20, ge=1)
    slow_window: int = Field(default=50, ge=2)

    @model_validator(mode="after")
    def fast_lt_slow(self) -> "SmaCrossoverParams":
        if self.fast_window >= self.slow_window:
            raise ValueError("fast_window must be < slow_window")
        return self


class StrategySpec(BaseModel):
    ticker: str
    kind: StrategyKind = StrategyKind.SMA_CROSSOVER
    strategy: SmaCrossoverParams = Field(default_factory=SmaCrossoverParams)
    start: str  # YYYY-MM-DD
    end: Optional[str] = None
    commission_bps: float = Field(default=0.0, ge=0.0)
    slippage_bps: float = Field(default=0.0, ge=0.0)
    initial_cash: float = Field(default=10_000.0, gt=0.0)
    price_mode: Literal["adjusted_close"] = "adjusted_close"

    @model_validator(mode="after")
    def normalize_ticker(self) -> "StrategySpec":
        object.__setattr__(self, "ticker", self.ticker.strip().upper())
        if self.kind != StrategyKind.SMA_CROSSOVER:
            raise ValueError("Phase 3 supports only sma_crossover")
        return self


class BacktestTrade(BaseModel):
    entry_signal_date: str
    entry_exec_date: str
    entry_market_price: float
    entry_effective_price: float
    entry_commission: float
    shares: float
    exit_signal_date: Optional[str] = None
    exit_exec_date: Optional[str] = None
    exit_market_price: Optional[float] = None
    exit_effective_price: Optional[float] = None
    exit_commission: Optional[float] = None
    pnl: Optional[float] = None
    trade_return: Optional[float] = None
    forced_end_close: bool = False


class EquityPoint(BaseModel):
    date: str
    equity: float
    in_position: bool
    cash: float


class BacktestMetrics(BaseModel):
    total_return: float  # net
    gross_return: float
    commission_only_return: float
    commission_impact: float
    slippage_impact: float
    max_drawdown: float
    hit_rate: Optional[float] = None
    n_trades: int = 0


class BacktestReproducibility(BaseModel):
    engine_version: str
    price_source: str
    price_mode: str
    price_start: Optional[str] = None
    price_end: Optional[str] = None
    price_data_hash: str


class BacktestResult(BaseModel):
    """Pure engine output. No evidence IDs / wall-clock timestamps."""

    spec: StrategySpec
    trades: List[BacktestTrade] = Field(default_factory=list)
    equity_curve: List[EquityPoint] = Field(default_factory=list)
    metrics: BacktestMetrics
    reproducibility: BacktestReproducibility


# Resolve forward refs for Pydantic v2
Claim.model_rebuild()
ThesisAssumption.model_rebuild()
Thesis.model_rebuild()
ThesisDiff.model_rebuild()
Alert.model_rebuild()
AnalysisEvent.model_rebuild()
EventStudySpec.model_rebuild()
EventStudyResult.model_rebuild()
StrategySpec.model_rebuild()
BacktestResult.model_rebuild()
