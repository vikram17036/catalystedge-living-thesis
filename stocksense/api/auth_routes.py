"""
Authentication and user data API routes.

Stage 3: User Belief System
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Header, BackgroundTasks
from pydantic import BaseModel, Field, field_validator

from stocksense.db.supabase_client import (
    verify_user_token,
    get_user_profile,
    get_user_positions,
    create_position,
    delete_position,
    get_user_theses,
    create_thesis,
    update_thesis,
    get_thesis_history,
    attach_thesis_evidence,
    get_active_thesis_for_ticker,
    enrich_thesis_with_attachments,
)

router = APIRouter(prefix="/api", tags=["User"])


def _schedule_thesis_index(
    background_tasks: BackgroundTasks, user_id: str, thesis: Optional[dict]
) -> None:
    """Best-effort Pinecone refresh after the HTTP response (never blocks UI)."""
    if not thesis or not thesis.get("id"):
        return

    def _run() -> None:
        try:
            from stocksense.memory.indexer import index_thesis

            index_thesis(user_id, thesis)
        except Exception:
            pass

    background_tasks.add_task(_run)


@router.get("/phase1-ping")
async def phase1_ping():
    """Health marker to confirm latest auth_routes is loaded."""
    return {"phase1": True, "routes": ["from-analysis", "evaluate", "start-new"]}


# ============================================
# Request/Response Models
# ============================================

class UserResponse(BaseModel):
    id: str
    email: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None


class PositionCreate(BaseModel):
    ticker: str
    position_type: str = "watching"  # long, short, watching
    entry_date: Optional[str] = None
    entry_price: Optional[float] = None
    current_shares: Optional[float] = None
    notes: Optional[str] = None


class PositionResponse(BaseModel):
    id: str
    ticker: str
    position_type: str
    entry_date: Optional[str] = None
    entry_price: Optional[float] = None
    current_shares: Optional[float] = None
    notes: Optional[str] = None
    created_at: str


class ThesisCreate(BaseModel):
    ticker: str
    thesis_summary: str = Field(..., min_length=10, description="Why you own/want to own this")
    conviction_level: str = "medium"  # high, medium, low
    kill_criteria: List[str] = Field(default_factory=list, description="Conditions that would trigger exit")
    time_horizon: str = "medium"  # short, medium, long
    thesis_type: str = "growth"  # growth, value, income, turnaround, special_situation
    position_id: Optional[str] = None
    # Coerce bad ids to None — never 422 the whole start-new/create on id shape.
    origin_analysis_id: Optional[int] = Field(None, description="Supabase cache ID of the analysis that informed this thesis")
    origin_analysis_snapshot: Optional[dict] = Field(None, description="Snapshot of key analysis metrics at thesis creation")
    origin_evidence: Optional[List[dict]] = Field(None, description="Frozen Evidence ledger at thesis creation")
    structured_kill_criteria: Optional[List[dict]] = Field(
        None, description="Typed kill criteria (deterministic + qualitative)"
    )

    @field_validator("origin_analysis_id", mode="before")
    @classmethod
    def _coerce_origin_analysis_id(cls, v: Any) -> Optional[int]:
        if v is None or v == "":
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            return None


class ThesisUpdate(BaseModel):
    thesis_summary: Optional[str] = None
    conviction_level: Optional[str] = None
    kill_criteria: Optional[List[str]] = None
    status: Optional[str] = None  # active, validated, invalidated, exited
    invalidation_reason: Optional[str] = None
    change_reason: Optional[str] = None


class ThesisResponse(BaseModel):
    id: str
    ticker: str
    thesis_summary: str
    conviction_level: str
    kill_criteria: List[str] = Field(default_factory=list)
    time_horizon: str = "medium"
    thesis_type: str = "growth"
    status: str = "active"
    origin_analysis_id: Optional[int] = None
    origin_analysis_snapshot: Optional[dict] = None
    origin_evidence: Optional[List[dict]] = None
    structured_kill_criteria: Optional[List[dict]] = None
    attached_evidence: Optional[List[dict]] = None
    created_at: str = ""
    updated_at: str = ""

    class Config:
        extra = "ignore"


def _as_thesis_response(row: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize Supabase row so response_model never 500s after a successful write."""
    kills = row.get("kill_criteria")
    if not isinstance(kills, list):
        kills = []
    kills = [str(k) if not isinstance(k, str) else k for k in kills]
    return {
        "id": str(row.get("id") or ""),
        "ticker": str(row.get("ticker") or ""),
        "thesis_summary": str(row.get("thesis_summary") or ""),
        "conviction_level": str(row.get("conviction_level") or "medium"),
        "kill_criteria": kills,
        "time_horizon": str(row.get("time_horizon") or "medium"),
        "thesis_type": str(row.get("thesis_type") or "growth"),
        "status": str(row.get("status") or "active"),
        "origin_analysis_id": row.get("origin_analysis_id"),
        "origin_analysis_snapshot": row.get("origin_analysis_snapshot"),
        "origin_evidence": row.get("origin_evidence"),
        "structured_kill_criteria": row.get("structured_kill_criteria"),
        "attached_evidence": row.get("attached_evidence") or [],
        "created_at": str(row.get("created_at") or ""),
        "updated_at": str(row.get("updated_at") or ""),
    }


# ============================================
# Auth Dependency
# ============================================

async def get_current_user(authorization: Optional[str] = Header(None)):
    """
    Extract and verify user from Authorization header.
    
    Expected format: "Bearer <access_token>"
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization format. Use: Bearer <token>")
    
    access_token = parts[1]
    user = verify_user_token(access_token)
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    # Attach token for downstream RLS operations
    user["access_token"] = access_token
    return user


# ============================================
# User Routes
# ============================================

@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(user = Depends(get_current_user)):
    """Get the current user's profile."""
    profile = get_user_profile(user["id"], user["access_token"])
    
    if not profile:
        # Profile might not exist yet, return basic info
        return UserResponse(
            id=user["id"],
            email=user["email"],
            display_name=user["email"].split("@")[0] if user["email"] else None,
        )
    
    return UserResponse(
        id=profile["id"],
        email=profile.get("email") or user["email"],
        display_name=profile.get("display_name"),
        avatar_url=profile.get("avatar_url"),
    )


# ============================================
# Position Routes
# ============================================

@router.get("/positions")
async def list_positions(user = Depends(get_current_user)):
    """Get all positions for the current user."""
    positions = get_user_positions(user["id"], user["access_token"])
    return {"positions": positions, "count": len(positions)}


@router.post("/positions", response_model=PositionResponse)
async def add_position(position: PositionCreate, user = Depends(get_current_user)):
    """Add a new position to track."""
    result = create_position(user["id"], user["access_token"], position.model_dump())
    
    if not result:
        raise HTTPException(status_code=400, detail="Failed to create position. Ticker may already exist.")
    
    return result


@router.delete("/positions/{position_id}")
async def remove_position(position_id: str, user = Depends(get_current_user)):
    """Remove a position."""
    success = delete_position(user["id"], user["access_token"], position_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Position not found or already deleted")
    
    return {"message": "Position deleted successfully"}


# ============================================
# Thesis Routes
# ============================================

@router.get("/theses")
async def list_theses(ticker: Optional[str] = None, user = Depends(get_current_user)):
    """Get all theses, optionally filtered by ticker. Includes attached_evidence."""
    theses = get_user_theses(user["id"], user["access_token"], ticker)
    enriched = [
        enrich_thesis_with_attachments(user["id"], user["access_token"], t)
        for t in theses
    ]
    return {"theses": enriched, "count": len(enriched)}


@router.post("/theses", response_model=ThesisResponse)
async def add_thesis(
    thesis: ThesisCreate,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user),
):
    """Create a new investment thesis with kill criteria."""
    try:
        result = create_thesis(user["id"], user["access_token"], thesis.model_dump())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create thesis: {e}") from e

    if not result:
        raise HTTPException(status_code=400, detail="Failed to create thesis")

    _schedule_thesis_index(background_tasks, user["id"], result)
    enriched = enrich_thesis_with_attachments(user["id"], user["access_token"], result)
    return _as_thesis_response(enriched)


class StartNewThesisRequest(ThesisCreate):
    change_reason: Optional[str] = (
        "Closed to start a new active thesis from the latest analysis"
    )


@router.post("/theses/start-new", response_model=ThesisResponse)
async def start_new_thesis(
    body: StartNewThesisRequest,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user),
):
    """
    Close all active/validated theses for the ticker, then create a new active one.
    Attachments/history/graph on the old thesis stay put. Pinecone is deferred.
    """
    ticker = body.ticker.upper().strip()
    reason = body.change_reason or (
        "Closed to start a new active thesis from the latest analysis"
    )
    existing = get_user_theses(user["id"], user["access_token"], ticker)
    for t in existing:
        status = (t.get("status") or "active").lower()
        if status in ("active", "validated"):
            try:
                closed = update_thesis(
                    user["id"],
                    user["access_token"],
                    str(t["id"]),
                    {"status": "exited", "change_reason": reason},
                )
            except Exception as e:
                raise HTTPException(
                    status_code=400, detail=f"Failed to close current thesis: {e}"
                ) from e
            if closed:
                _schedule_thesis_index(background_tasks, user["id"], closed)

    create_payload = body.model_dump(exclude={"change_reason"})
    create_payload["ticker"] = ticker
    try:
        result = create_thesis(user["id"], user["access_token"], create_payload)
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Failed to create replacement thesis: {e}"
        ) from e
    if not result:
        raise HTTPException(status_code=400, detail="Failed to create replacement thesis")

    _schedule_thesis_index(background_tasks, user["id"], result)
    enriched = enrich_thesis_with_attachments(user["id"], user["access_token"], result)
    return _as_thesis_response(enriched)


class FromAnalysisRequest(BaseModel):
    ticker: str
    analysis: Optional[dict] = None
    use_cache: bool = True


class AttachEvidenceBody(BaseModel):
    evidence: dict


class AttachByTickerBody(BaseModel):
    ticker: str
    evidence: dict


@router.post("/theses/from-analysis")
async def propose_thesis_from_analysis_route(
    body: FromAnalysisRequest,
    user=Depends(get_current_user),
):
    """
    Propose a thesis structure from analysis (not saved).
    Client edits then POST /api/theses to persist.
    Must be registered before /theses/{thesis_id} routes.
    """
    from stocksense.db.database import get_latest_analysis
    from stocksense.core.thesis_extract import propose_thesis_from_analysis
    from stocksense.core.evidence_ledger import ledger_from_analysis_payload

    ticker = body.ticker.upper().strip()
    analysis = body.analysis
    if not analysis and body.use_cache:
        cached = get_latest_analysis(ticker)
        if not cached:
            raise HTTPException(status_code=404, detail=f"No analysis for {ticker}")
        analysis = {
            "id": cached.get("id"),
            "ticker": ticker,
            "summary": cached.get("analysis_summary") or cached.get("summary") or "",
            "overall_sentiment": cached.get("overall_sentiment") or "",
            "overall_confidence": cached.get("overall_confidence") or 0,
            "skeptic_sentiment": cached.get("skeptic_sentiment") or "",
            "key_themes": cached.get("key_themes") or [],
            "risks_identified": cached.get("risks_identified") or [],
            "timestamp": cached.get("timestamp"),
            "price_data": cached.get("price_data") or {},
            "fundamental_data": cached.get("fundamental_data") or {},
            "news_articles": cached.get("news_articles") or [],
            "evidence_ledger": cached.get("evidence_ledger"),
        }

    if not analysis:
        raise HTTPException(status_code=400, detail="analysis payload required")

    analysis["ticker"] = ticker
    ledger = analysis.get("evidence_ledger")
    if not ledger:
        price = analysis.get("price_data") or {}
        change = None
        if isinstance(price, dict):
            change = price.get("percent_change") or price.get("change_percent")
        built = ledger_from_analysis_payload(
            ticker,
            price_change_pct=float(change) if change is not None else None,
            fundamentals=analysis.get("fundamental_data"),
            news_articles=analysis.get("news_articles") or [],
        )
        ledger = [e.model_dump(mode="json") for e in built]

    proposal = propose_thesis_from_analysis(analysis, evidence_ledger=ledger)
    return {"proposal": proposal, "persisted": False}


@router.post("/theses/attach-by-ticker")
async def attach_evidence_by_ticker(
    body: AttachByTickerBody,
    user=Depends(get_current_user),
):
    """Attach Event Study / Backtest evidence to active thesis for ticker."""
    from stocksense.core.thesis_attach import AttachError

    ticker = body.ticker.upper().strip()
    thesis = get_active_thesis_for_ticker(user["id"], user["access_token"], ticker)
    if not thesis:
        raise HTTPException(
            status_code=400,
            detail=f'Create a thesis for {ticker} first (Analysis → PROPOSE_AND_CREATE_THESIS).',
        )
    try:
        result = attach_thesis_evidence(
            user["id"], user["access_token"], thesis["id"], body.evidence
        )
    except AttachError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Attach failed: {e}") from e

    enriched = enrich_thesis_with_attachments(
        user["id"], user["access_token"], result["thesis"]
    )
    return {**result, "thesis": enriched}


@router.post("/theses/{thesis_id}/attach-evidence")
async def attach_evidence_to_thesis(
    thesis_id: str,
    body: AttachEvidenceBody,
    user=Depends(get_current_user),
):
    """Append research evidence to thesis_evidence (never origin_evidence)."""
    from stocksense.core.thesis_attach import AttachError

    try:
        result = attach_thesis_evidence(
            user["id"], user["access_token"], thesis_id, body.evidence
        )
    except AttachError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Attach failed: {e}") from e

    enriched = enrich_thesis_with_attachments(
        user["id"], user["access_token"], result["thesis"]
    )
    return {**result, "thesis": enriched}


@router.patch("/theses/{thesis_id}", response_model=ThesisResponse)
async def modify_thesis(
    thesis_id: str,
    updates: ThesisUpdate,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user),
):
    """Update a thesis. Changes are tracked in history."""
    # Filter out None values
    update_data = {k: v for k, v in updates.model_dump().items() if v is not None}

    if not update_data:
        raise HTTPException(status_code=400, detail="No updates provided")

    try:
        result = update_thesis(user["id"], user["access_token"], thesis_id, update_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update thesis: {e}") from e

    if not result:
        raise HTTPException(status_code=404, detail="Thesis not found")

    # Refresh semantic memory after content OR status changes (best-effort, async)
    _schedule_thesis_index(background_tasks, user["id"], result)
    return _as_thesis_response(result)


@router.get("/theses/{thesis_id}/history")
async def get_thesis_evolution(thesis_id: str, user = Depends(get_current_user)):
    """Get the history of changes for a thesis (belief evolution)."""
    history = get_thesis_history(user["id"], user["access_token"], thesis_id)
    return {"history": history, "count": len(history)}


class EvaluateRequest(BaseModel):
    create_alert: bool = True


@router.post("/theses/{thesis_id}/evaluate")
async def evaluate_thesis_route(
    thesis_id: str,
    body: EvaluateRequest,
    user=Depends(get_current_user),
):
    """Evaluate thesis against latest cached analysis (same evaluator as replay)."""
    from stocksense.db.supabase_client import get_supabase_client, get_supabase_admin_client
    from stocksense.db.database import get_latest_analysis
    from stocksense.core.thesis_evaluate import evaluate_from_analysis_cache
    from stocksense.core.alerts_store import insert_alert

    client = get_supabase_client()
    client.postgrest.auth(user["access_token"])
    response = (
        client.table("theses")
        .select("*")
        .eq("id", thesis_id)
        .eq("user_id", user["id"])
        .single()
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Thesis not found")

    thesis = response.data
    analysis = get_latest_analysis(thesis["ticker"])
    if not analysis:
        raise HTTPException(
            status_code=404,
            detail=f"No current analysis for {thesis['ticker']}",
        )

    # Normalize cache row
    analysis_like = {
        "id": analysis.get("id"),
        "ticker": thesis["ticker"],
        "summary": analysis.get("analysis_summary") or analysis.get("summary") or "",
        "overall_sentiment": analysis.get("overall_sentiment") or "",
        "overall_confidence": analysis.get("overall_confidence") or 0,
        "skeptic_sentiment": analysis.get("skeptic_sentiment") or "",
        "key_themes": analysis.get("key_themes") or [],
        "risks_identified": analysis.get("risks_identified") or [],
        "timestamp": analysis.get("timestamp"),
        "price_data": analysis.get("price_data") or {},
        "fundamental_data": analysis.get("fundamental_data") or {},
        "news_articles": analysis.get("news_articles") or [],
        "evidence_ledger": analysis.get("evidence_ledger"),
    }

    result = evaluate_from_analysis_cache(
        thesis=thesis,
        analysis=analysis_like,
        user_id=user["id"],
        create_alert=body.create_alert,
    )
    alert_model = result.pop("alert_model", None)
    alert_row = None
    if alert_model:
        try:
            svc = get_supabase_admin_client()
            alert_row = insert_alert(svc, alert_model)
        except Exception:
            alert_row = insert_alert(client, alert_model)
    result["alert"] = alert_row
    return result


@router.get("/theses/{thesis_id}/compare")
async def compare_thesis_with_current(thesis_id: str, user = Depends(get_current_user)):
    """
    Compare thesis origin analysis/evidence with current analysis.
    Phase 1: returns ThesisDiff + legacy change list for the banner UI.
    """
    from stocksense.db.supabase_client import get_supabase_client
    from stocksense.db.database import get_latest_analysis
    from stocksense.core.thesis_diff import (
        build_thesis_diff,
        diff_to_api_payload,
        snapshot_from_analysis,
    )
    from stocksense.core.evidence_ledger import ledger_from_analysis_payload

    try:
        client = get_supabase_client()
        client.postgrest.auth(user["access_token"])

        response = (
            client.table("theses")
            .select("*")
            .eq("id", thesis_id)
            .eq("user_id", user["id"])
            .single()
            .execute()
        )

        if not response.data:
            raise HTTPException(status_code=404, detail="Thesis not found")

        thesis = response.data
        ticker = thesis["ticker"]
        origin_snapshot = thesis.get("origin_analysis_snapshot")

        if not origin_snapshot:
            return {
                "has_comparison": False,
                "message": "No origin analysis linked to this thesis",
                "thesis_id": thesis_id,
                "ticker": ticker,
            }

        current_analysis = get_latest_analysis(ticker)
        if not current_analysis:
            return {
                "has_comparison": False,
                "message": f"No current analysis available for {ticker}",
                "thesis_id": thesis_id,
                "ticker": ticker,
                "origin": origin_snapshot,
            }

        # Normalize cache row into analysis-shaped dict
        analysis_like = {
            "overall_sentiment": current_analysis.get("overall_sentiment")
            or current_analysis.get("sentiment_report", "")[:80],
            "overall_confidence": current_analysis.get("overall_confidence", 0),
            "skeptic_sentiment": current_analysis.get("skeptic_sentiment", ""),
            "risks_identified": current_analysis.get("risks_identified") or [],
            "key_themes": current_analysis.get("key_themes") or [],
            "timestamp": current_analysis.get("timestamp"),
            "price_data": current_analysis.get("price_data") or {},
            "fundamental_data": current_analysis.get("fundamental_data") or {},
            "news_articles": current_analysis.get("news_articles") or [],
        }
        current_snap = snapshot_from_analysis(analysis_like)

        price = analysis_like.get("price_data") or {}
        change = None
        if isinstance(price, dict):
            change = price.get("percent_change") or price.get("change_percent")
        current_evidence = ledger_from_analysis_payload(
            ticker,
            price_change_pct=float(change) if change is not None else None,
            fundamentals=analysis_like.get("fundamental_data"),
            news_articles=analysis_like.get("news_articles") or [],
        )
        current_evidence_dicts = [e.model_dump(mode="json") for e in current_evidence]

        kill_src = thesis.get("structured_kill_criteria") or thesis.get("kill_criteria") or []
        thesis_diff = build_thesis_diff(
            thesis_id=thesis_id,
            ticker=ticker,
            origin_snapshot=origin_snapshot,
            origin_evidence=thesis.get("origin_evidence") or [],
            current_snapshot=current_snap,
            current_evidence=current_evidence_dicts,
            kill_criteria=kill_src,
        )
        payload = diff_to_api_payload(thesis_diff)
        payload["thesis_created_at"] = thesis.get("created_at")
        payload["origin"] = origin_snapshot
        payload["current"] = {
            "sentiment": current_snap.get("sentiment"),
            "confidence": current_snap.get("confidence"),
            "timestamp": current_snap.get("timestamp"),
        }
        return payload

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Comparison failed: {e}")


class ReplayRequest(BaseModel):
    label: str = "adverse_shock"
    create_alert: bool = True


@router.post("/theses/{thesis_id}/replay")
async def replay_thesis_scenario(
    thesis_id: str,
    body: ReplayRequest,
    user=Depends(get_current_user),
):
    """
    Phase 1 Replay: run a built-in (or stored) scenario against a thesis,
    produce ThesisDiff, optionally write an Alert.
    """
    from stocksense.db.supabase_client import get_supabase_client, get_supabase_admin_client
    from stocksense.core.replay_fixtures import get_builtin_replay
    from stocksense.core.thesis_evaluate import evaluate_from_fixture
    from stocksense.core.alerts_store import insert_alert

    try:
        client = get_supabase_client()
        client.postgrest.auth(user["access_token"])

        response = (
            client.table("theses")
            .select("*")
            .eq("id", thesis_id)
            .eq("user_id", user["id"])
            .single()
            .execute()
        )
        if not response.data:
            raise HTTPException(status_code=404, detail="Thesis not found")

        thesis = response.data
        ticker = thesis["ticker"]
        if not thesis.get("origin_analysis_snapshot"):
            raise HTTPException(
                status_code=400,
                detail="Thesis has no origin snapshot — create from an analysis first",
            )

        fixture = get_builtin_replay(ticker, body.label)
        if not fixture:
            try:
                rows = (
                    client.table("replay_snapshots")
                    .select("*")
                    .eq("ticker", ticker.upper())
                    .eq("label", body.label)
                    .limit(1)
                    .execute()
                )
                if rows.data:
                    fixture = rows.data[0]
            except Exception:
                fixture = None
        if not fixture:
            raise HTTPException(
                status_code=404,
                detail=f"No replay fixture '{body.label}' for {ticker}",
            )

        result = evaluate_from_fixture(
            thesis=thesis,
            fixture=fixture,
            user_id=user["id"],
            create_alert=body.create_alert,
        )
        alert_model = result.pop("alert_model", None)
        alert_row = None
        if alert_model:
            try:
                svc = get_supabase_admin_client()
                alert_row = insert_alert(svc, alert_model)
            except Exception:
                alert_row = insert_alert(client, alert_model)
        result["alert"] = alert_row
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Replay failed: {e}")


# ============================================
# Kill Alerts Routes (Stage 4)
# ============================================

class AlertStatusUpdate(BaseModel):
    status: str  # pending, dismissed, acknowledged, acted
    user_action: Optional[str] = None


class KillAlertResponse(BaseModel):
    id: str
    thesis_id: str
    ticker: str
    triggered_criteria: str
    triggering_signal: str
    match_confidence: float
    analysis_sentiment: Optional[str] = None
    analysis_confidence: Optional[float] = None
    status: str
    created_at: str


@router.get("/kill-alerts")
async def list_kill_alerts(
    ticker: Optional[str] = None,
    status: str = "pending",
    user = Depends(get_current_user)
):
    """Get alerts for the current user (thesis_alerts with legacy fallback)."""
    from stocksense.db.supabase_client import get_supabase_client
    from stocksense.core.alerts_store import list_unread_alerts

    client = get_supabase_client()
    client.postgrest.auth(user["access_token"])

    if status in ("pending", "unread"):
        alerts = list_unread_alerts(client, user["id"], ticker=ticker)
    else:
        # Prefer unified table for all statuses
        try:
            query = client.table("thesis_alerts").select("*").eq("user_id", user["id"])
            if ticker:
                query = query.eq("ticker", ticker.upper())
            if status != "all":
                mapped = "acknowledged" if status in ("acknowledged", "acted") else status
                query = query.eq("status", mapped)
            alerts = query.order("created_at", desc=True).execute().data or []
        except Exception:
            alerts = list_unread_alerts(client, user["id"], ticker=ticker)

    # Normalize for KillAlertBanner / frontend
    normalized = []
    for a in alerts:
        data = a.get("data") or {}
        triggered = a.get("triggered_criteria") or data.get("triggered_criteria") or []
        if isinstance(triggered, list):
            triggered_str = triggered[0] if triggered else (a.get("message") or "")
        else:
            triggered_str = str(triggered)
        normalized.append(
            {
                "id": a.get("id"),
                "thesis_id": a.get("thesis_id"),
                "ticker": a.get("ticker"),
                "triggered_criteria": triggered_str,
                "triggering_signal": data.get("triggering_signal") or a.get("title") or "",
                "match_confidence": float(data.get("match_confidence") or data.get("analysis_confidence") or 0.8),
                "analysis_sentiment": data.get("analysis_sentiment"),
                "analysis_confidence": data.get("analysis_confidence"),
                "status": a.get("status") or ("pending" if not a.get("is_read") else "acknowledged"),
                "created_at": a.get("created_at"),
                "message": a.get("message") or a.get("title"),
                "title": a.get("title"),
            }
        )

    return {"alerts": normalized, "count": len(normalized)}


@router.get("/kill-alerts/{alert_id}")
async def get_kill_alert(alert_id: str, user = Depends(get_current_user)):
    """Get a specific alert from thesis_alerts or alert_history."""
    from stocksense.db.supabase_client import get_supabase_client

    client = get_supabase_client()
    client.postgrest.auth(user["access_token"])

    for table in ("thesis_alerts", "alert_history"):
        try:
            response = (
                client.table(table)
                .select("*")
                .eq("id", alert_id)
                .eq("user_id", user["id"])
                .single()
                .execute()
            )
            if response.data:
                return response.data
        except Exception:
            continue
    raise HTTPException(status_code=404, detail="Alert not found")


@router.patch("/kill-alerts/{alert_id}")
async def update_kill_alert(
    alert_id: str,
    update: AlertStatusUpdate,
    user = Depends(get_current_user)
):
    """Update a kill alert status (dismiss, acknowledge, or mark as acted upon)."""
    from stocksense.core.monitor import update_alert_status
    
    valid_statuses = ["pending", "dismissed", "acknowledged", "acted"]
    if update.status not in valid_statuses:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid status. Must be one of: {valid_statuses}"
        )
    
    success = update_alert_status(
        user["id"],
        user["access_token"],
        alert_id,
        update.status,
        update.user_action
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Alert not found or update failed")
    
    return {"message": "Alert updated successfully", "status": update.status}


@router.delete("/kill-alerts/{alert_id}")
async def delete_kill_alert(alert_id: str, user = Depends(get_current_user)):
    """Delete a kill alert."""
    from stocksense.db.supabase_client import get_supabase_client
    
    try:
        client = get_supabase_client()
        client.postgrest.auth(user["access_token"])
        
        client.table("kill_alerts").delete().eq("id", alert_id).eq("user_id", user["id"]).execute()
        return {"message": "Alert deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to delete alert: {e}")

