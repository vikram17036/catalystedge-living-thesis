"""
StockSense ReAct Agent API
AI-powered autonomous stock analysis using ReAct pattern
"""
import json
import logging
import os
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from stocksense.core.config import validate_configuration, ConfigurationError, get_google_api_key, get_newsapi_key
from stocksense.db.database import init_db, get_latest_analysis, get_all_cached_tickers_with_timestamps, delete_cached_analysis
from stocksense.orchestration.react_flow import run_react_analysis
from stocksense.orchestration.pipeline import run_analysis as run_canonical_analysis
from stocksense.core.validation import validate_ticker

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("stocksense.api")

# API Version - single source of truth
API_VERSION = "3.0.0"  # Stage 3: User Belief System + Supabase migration


# Simple in-memory rate limiter
class RateLimiter:
    """Simple token bucket rate limiter."""
    
    def __init__(self, requests_per_minute: int = 10):
        self.requests_per_minute = requests_per_minute
        self.requests: Dict[str, list] = defaultdict(list)
    
    def is_allowed(self, client_id: str) -> bool:
        """Check if request is allowed for given client."""
        now = time.time()
        minute_ago = now - 60
        
        # Clean old requests
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id] 
            if req_time > minute_ago
        ]
        
        # Check limit
        if len(self.requests[client_id]) >= self.requests_per_minute:
            return False
        
        # Record request
        self.requests[client_id].append(now)
        return True
    
    def get_remaining(self, client_id: str) -> int:
        """Get remaining requests for client."""
        now = time.time()
        minute_ago = now - 60
        recent = [r for r in self.requests[client_id] if r > minute_ago]
        return max(0, self.requests_per_minute - len(recent))


# Initialize rate limiter (10 analysis requests per minute per IP)
rate_limiter = RateLimiter(requests_per_minute=10)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting StockSense ReAct Agent API...")

    try:
        logger.info("Validating configuration...")
        validate_configuration()
        logger.info("Configuration validation successful")
    except ConfigurationError as e:
        logger.error(f"Configuration error: {str(e)}")
        raise

    logger.info("Initializing database...")
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise

    # Initialize Scheduler (Stage 5 Phase 2: The Watchman)
    try:
        from stocksense.scheduler import start_scheduler
        start_scheduler()
        logger.info("Background scheduler initialized")
    except Exception as e:
        logger.warning(f"Failed to start background scheduler: {e}")

    logger.info("StockSense ReAct Agent API ready to serve requests!")

    yield

    # Shutdown
    logger.info("Shutting down StockSense ReAct Agent API...")


app = FastAPI(
    title="StockSense ReAct Agent API",
    description="AI-powered autonomous stock analysis using ReAct pattern",
    version=API_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS configuration - use CORS_ORIGINS env var for production, defaults to permissive for dev
cors_origins_str = os.getenv("CORS_ORIGINS", "*")
cors_origins = cors_origins_str.split(",") if cors_origins_str != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_and_latency(request: Request, call_next):
    """Lightweight correlation: X-Request-Id + latency log (no OTel)."""
    import time as _time
    import uuid as _uuid

    rid = request.headers.get("X-Request-Id") or str(_uuid.uuid4())
    t0 = _time.perf_counter()
    response = await call_next(request)
    ms = int((_time.perf_counter() - t0) * 1000)
    response.headers["X-Request-Id"] = rid
    logger.info(
        "request_id=%s method=%s path=%s status=%s latency_ms=%s",
        rid,
        request.method,
        request.url.path,
        response.status_code,
        ms,
    )
    return response

# Register auth routes (Stage 3: User Belief System)
try:
    from stocksense.api.auth_routes import router as auth_router
    app.include_router(auth_router)
    logger.info("Auth routes registered successfully")
except ImportError as e:
    logger.warning(f"Auth routes not available: {e}")

# Phase 2 research routes (Event Study)
try:
    from stocksense.api.research_routes import router as research_router
    app.include_router(research_router)
    logger.info("Research routes registered successfully")
except ImportError as e:
    logger.warning(f"Research routes not available: {e}")

# Phase 3 Strategy Lab
try:
    from stocksense.api.lab_routes import router as lab_router
    app.include_router(lab_router)
    logger.info("Lab routes registered successfully")
except ImportError as e:
    logger.error(f"Lab routes not available: {e}")

# Phase 5 Historical Analog Search
try:
    from stocksense.api.analog_routes import router as analog_router
    app.include_router(analog_router)
    logger.info("Analog routes registered successfully")
except ImportError as e:
    logger.error(f"Analog routes not available: {e}")

# Phase 6 Scenario Lab
try:
    from stocksense.api.scenario_routes import router as scenario_router
    app.include_router(scenario_router)
    logger.info("Scenario routes registered successfully")
except ImportError as e:
    logger.error(f"Scenario routes not available: {e}")

# Phase 6 Thesis Dependency Graph
try:
    from stocksense.api.graph_routes import router as graph_router
    app.include_router(graph_router)
    logger.info("Thesis graph routes registered successfully")
except ImportError as e:
    logger.error(f"Thesis graph routes not available: {e}")

# Phase 7 Research Agent + Memory
try:
    from stocksense.api.research_agent_routes import router as research_agent_router
    app.include_router(research_agent_router)
    logger.info("Research agent routes registered successfully")
except ImportError as e:
    logger.error(f"Research agent routes not available: {e}")


def get_client_ip(request: Request) -> str:
    """Extract client IP from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Liveness — cheap, no outbound network.
    Config flags only (env presence). Use /api/ready for dependency probes.
    """
    google_ok = bool((os.getenv("GOOGLE_API_KEY") or "").strip())
    news_ok = bool((os.getenv("NEWSAPI_KEY") or "").strip())
    supabase_ok = bool(
        (os.getenv("SUPABASE_URL") or "").strip()
        and (os.getenv("SUPABASE_ANON_KEY") or "").strip()
    )
    pinecone_ok = bool(
        (os.getenv("PINECONE_API_KEY") or "").strip()
        and (os.getenv("PINECONE_INDEX") or "").strip()
    )
    status = "ok"
    if not google_ok or not supabase_ok:
        status = "degraded"
    return {
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": API_VERSION,
        "checks": {
            "google_api_key": {"configured": google_ok},
            "newsapi_key": {"configured": news_ok},
            "supabase": {"configured": supabase_ok},
            "pinecone": {"configured": pinecone_ok},
        },
    }


# Dependency probe cache for /api/ready (TTL seconds)
_ready_cache: Dict[str, Any] = {"at": 0.0, "payload": None}
_READY_TTL_SEC = 45.0


def _probe_dependencies() -> Dict[str, Any]:
    """Classify critical vs optional deps. Pinecone optional → degraded not dead."""
    deps: Dict[str, Any] = {}
    critical_ok = True
    degraded = False

    # Supabase (critical)
    url = (os.getenv("SUPABASE_URL") or "").strip()
    key = (os.getenv("SUPABASE_ANON_KEY") or "").strip()
    if not url or not key:
        deps["supabase"] = {"status": "error", "message": "not configured"}
        critical_ok = False
    else:
        try:
            from stocksense.db.supabase_client import get_supabase_client

            client = get_supabase_client()
            # cheap auth settings call or table head
            client.table("theses").select("id").limit(1).execute()
            deps["supabase"] = {"status": "ok"}
        except Exception as e:
            deps["supabase"] = {
                "status": "error",
                "message": str(e)[:200],
            }
            critical_ok = False

    # Pinecone (optional — memory degrade)
    pk = (os.getenv("PINECONE_API_KEY") or "").strip()
    pi = (os.getenv("PINECONE_INDEX") or "").strip()
    if not pk or not pi:
        deps["pinecone"] = {"status": "degraded", "message": "not configured"}
        degraded = True
    else:
        try:
            from pinecone import Pinecone

            stats = Pinecone(api_key=pk).Index(pi).describe_index_stats()
            dim = getattr(stats, "dimension", None)
            deps["pinecone"] = {"status": "ok", "dimension": dim}
        except Exception as e:
            deps["pinecone"] = {
                "status": "degraded",
                "message": str(e)[:200],
            }
            degraded = True

    # NewsAPI (optional — analysis degrade)
    if not (os.getenv("NEWSAPI_KEY") or "").strip():
        deps["newsapi"] = {"status": "degraded", "message": "not configured"}
        degraded = True
    else:
        deps["newsapi"] = {"status": "ok", "configured": True}

    # Google (critical for LLM paths)
    if not (os.getenv("GOOGLE_API_KEY") or "").strip():
        deps["google"] = {"status": "error", "message": "not configured"}
        critical_ok = False
    else:
        deps["google"] = {"status": "ok", "configured": True}

    if not critical_ok:
        ready_status = "unavailable"
        ready = False
    elif degraded:
        ready_status = "degraded"
        ready = True
    else:
        ready_status = "ok"
        ready = True

    return {
        "ready": ready,
        "status": ready_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": API_VERSION,
        "dependencies": deps,
    }


@app.get("/api/ready")
async def readiness() -> Dict[str, Any]:
    """Readiness with short TTL-cached dependency probes."""
    now = time.time()
    cached = _ready_cache.get("payload")
    if cached and (now - float(_ready_cache.get("at") or 0)) < _READY_TTL_SEC:
        return cached
    payload = _probe_dependencies()
    _ready_cache["at"] = now
    _ready_cache["payload"] = payload
    return payload


@app.get("/")
async def root() -> Dict[str, str]:
    """Root endpoint with API information."""
    return {
        "message": "Welcome to StockSense ReAct Agent API",
        "description": "AI-powered autonomous stock analysis using ReAct pattern",
        "docs": "/docs",
        "health": "/health"
    }


@app.post("/analyze/{ticker}")
async def analyze_stock(
    ticker: str,
    request: Request,
    force: bool = False,
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """
    Analyze stock using the ReAct Agent (Reasoning + Action) pattern.
    
    Args:
        ticker: Stock ticker symbol
        force: If True, bypass cache and run fresh analysis
        authorization: Optional Bearer token for authenticated features (kill criteria alerts)
    
    Includes ticker validation and rate limiting.
    """
    # Rate limiting
    client_ip = get_client_ip(request)
    if not rate_limiter.is_allowed(client_ip):
        remaining = rate_limiter.get_remaining(client_ip)
        logger.warning(f"Rate limit exceeded for {client_ip}")
        raise HTTPException(
            status_code=429, 
            detail=f"Rate limit exceeded. Please wait before making more requests. Remaining: {remaining}"
        )
    
    try:
        # Validate ticker format and existence
        ticker = ticker.upper().strip()
        is_valid, error_msg = validate_ticker(ticker)
        if not is_valid:
            logger.info(f"Invalid ticker rejected: {ticker} - {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)

        logger.info(f"Analysis request received for ticker: {ticker} from {client_ip} (force={force})")

        # Check for cached analysis first (unless force=True)
        if not force:
            logger.debug(f"Checking cache for existing analysis of {ticker}...")
            cached_analysis = get_latest_analysis(ticker)

            if cached_analysis:
                logger.info(f"Found cached analysis for {ticker}")
                
                # Calculate cache age
                cache_age_hours = None
                if cached_analysis.get("timestamp"):
                    try:
                        cached_time = datetime.fromisoformat(cached_analysis["timestamp"])
                        age_seconds = (datetime.now(timezone.utc) - (cached_time.replace(tzinfo=timezone.utc) if cached_time.tzinfo is None else cached_time)).total_seconds()
                        cache_age_hours = round(age_seconds / 3600, 1)
                    except (ValueError, TypeError):
                        pass
                
                return {
                    "message": "Analysis retrieved from cache",
                    "ticker": ticker,
                    "data": {
                        "id": cached_analysis["id"],
                        "ticker": cached_analysis["ticker"],
                        "summary": cached_analysis["analysis_summary"],
                        "sentiment_report": cached_analysis["sentiment_report"],
                        "timestamp": cached_analysis["timestamp"],
                        "cache_age_hours": cache_age_hours,
                        "source": "cache",
                        "agent_type": "ReAct",
                        "price_data": cached_analysis.get("price_data", []),
                        "headlines": cached_analysis.get("headlines", []),
                        "headlines_count": len(cached_analysis.get("headlines", [])),
                        "reasoning_steps": cached_analysis.get("reasoning_steps", []),
                        "tools_used": cached_analysis.get("tools_used", []),
                        "iterations": cached_analysis.get("iterations", 0)
                    }
                }
        else:
            logger.info(f"Force refresh requested for {ticker}, skipping cache")

        # No cached data found or force=True — canonical pipeline (wraps ReAct)
        logger.info(f"Running canonical analysis for {ticker}...")

        try:
            final_state = await run_canonical_analysis(ticker)

            # Check if the ReAct agent completed successfully
            if final_state.get("error"):
                error_msg = final_state["error"]
                logger.error(f"ReAct Agent error for {ticker}: {error_msg}")
                raise HTTPException(
                    status_code=500,
                    detail=f"ReAct Agent analysis failed: {error_msg}"
                )

            # Check if we have valid results
            summary = final_state.get("summary", "")
            sentiment_report = final_state.get("sentiment_report", "")

            if isinstance(summary, list):
                summary = "\n".join(str(item) for item in summary)

            if isinstance(sentiment_report, list):
                sentiment_report = "\n".join(str(item) for item in sentiment_report)

            if not isinstance(summary, str):
                summary = str(summary)

            if not isinstance(sentiment_report, str):
                sentiment_report = str(sentiment_report)

            if not summary or summary.startswith("Analysis failed"):
                raise HTTPException(
                    status_code=500,
                    detail="ReAct Agent completed but produced insufficient data"
                )

            # Save the analysis results to database with full data
            try:
                from stocksense.db.database import save_analysis
                save_analysis(
                    ticker=ticker,
                    summary=summary,
                    sentiment_report=sentiment_report,
                    price_data=final_state.get("price_data", []),
                    headlines=final_state.get("headlines", []),
                    news_articles=final_state.get("news_articles", []),
                    reasoning_steps=final_state.get("reasoning_steps", []),
                    tools_used=final_state.get("tools_used", []),
                    iterations=final_state.get("iterations", 0),
                    # Structured sentiment analysis
                    overall_sentiment=final_state.get("overall_sentiment", ""),
                    overall_confidence=final_state.get("overall_confidence", 0.0),
                    confidence_reasoning=final_state.get("confidence_reasoning", ""),
                    headline_analyses=final_state.get("headline_analyses", []),
                    key_themes=final_state.get("key_themes", []),
                    potential_impact=final_state.get("potential_impact", ""),
                    risks_identified=final_state.get("risks_identified", []),
                    information_gaps=final_state.get("information_gaps", []),
                    # Skeptic analysis
                    skeptic_report=final_state.get("skeptic_report", ""),
                    skeptic_sentiment=final_state.get("skeptic_sentiment", ""),
                    skeptic_confidence=final_state.get("skeptic_confidence", 0.0),
                    primary_disagreement=final_state.get("primary_disagreement", ""),
                    critiques=final_state.get("critiques", []),
                    bear_cases=final_state.get("bear_cases", []),
                    hidden_risks=final_state.get("hidden_risks", []),
                    would_change_mind=final_state.get("would_change_mind", []),
                    # Fundamentals
                    fundamental_data=final_state.get("fundamental_data", {}),
                )
                logger.info(f"Analysis results saved to database for {ticker}")
            except Exception as e:
                logger.warning(f"Failed to save analysis to database: {str(e)}")
                # Don't fail the request if database save fails

            logger.info(f"ReAct Agent analysis completed successfully for {ticker}")

            # Stage 4: Kill Criteria Monitoring
            # Check if user is authenticated and run kill criteria check
            kill_alerts_created = []
            if authorization:
                try:
                    from stocksense.db.supabase_client import verify_user_token
                    from stocksense.core.monitor import check_kill_criteria_for_ticker
                    
                    # Parse Bearer token
                    parts = authorization.split(" ")
                    if len(parts) == 2 and parts[0].lower() == "bearer":
                        access_token = parts[1]
                        user = verify_user_token(access_token)
                        
                        if user:
                            logger.info(f"Running kill criteria check for user {user['id']} on {ticker}")
                            kill_alerts_created = check_kill_criteria_for_ticker(
                                ticker=ticker,
                                analysis_result=final_state,
                                user_id=user["id"],
                                access_token=access_token
                            )
                            if kill_alerts_created:
                                logger.info(f"Created {len(kill_alerts_created)} kill alerts for {ticker}")
                except Exception as e:
                    logger.warning(f"Kill criteria check failed (non-fatal): {e}")

            return {
                "message": "ReAct Agent analysis complete and saved",
                "ticker": ticker,
                "kill_alerts": kill_alerts_created,  # Stage 4: Include triggered alerts
                "data": {
                    "ticker": final_state["ticker"],
                    "summary": final_state["summary"],
                    "sentiment_report": final_state["sentiment_report"],
                    "price_data": final_state.get("price_data", []),
                    "headlines": final_state.get("headlines", []),
                    "news_articles": final_state.get("news_articles", []),
                    "headlines_count": len(final_state.get("headlines", [])),
                    "reasoning_steps": final_state.get("reasoning_steps", []),
                    "tools_used": final_state.get("tools_used", []),
                    "iterations": final_state.get("iterations", 0),
                    "timestamp": final_state.get("timestamp"),
                    "cache_age_hours": 0,  # Fresh analysis
                    "source": "canonical_pipeline",
                    "agent_type": "ReAct",
                    "pipeline": final_state.get("pipeline", "canonical_v0"),
                    "evidence_ledger": final_state.get("evidence_ledger", []),
                    # Stage 1: Structured sentiment fields
                    "overall_sentiment": final_state.get("overall_sentiment", ""),
                    "overall_confidence": final_state.get("overall_confidence", 0.0),
                    "confidence_reasoning": final_state.get("confidence_reasoning", ""),
                    "headline_analyses": final_state.get("headline_analyses", []),
                    "key_themes": final_state.get("key_themes", []),
                    "potential_impact": final_state.get("potential_impact", ""),
                    "risks_identified": final_state.get("risks_identified", []),
                    "information_gaps": final_state.get("information_gaps", []),
                    # Stage 2: Skeptic analysis fields
                    "skeptic_report": final_state.get("skeptic_report", ""),
                    "skeptic_sentiment": final_state.get("skeptic_sentiment", ""),
                    "skeptic_confidence": final_state.get("skeptic_confidence", 0.0),
                    "primary_disagreement": final_state.get("primary_disagreement", ""),
                    "critiques": final_state.get("critiques", []),
                    "bear_cases": final_state.get("bear_cases", []),
                    "hidden_risks": final_state.get("hidden_risks", []),
                    "would_change_mind": final_state.get("would_change_mind", [])
                }
            }

        except HTTPException:
            raise
        except Exception as e:
            error_msg = f"ReAct Agent execution error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise HTTPException(status_code=500, detail=error_msg)

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Unexpected error analyzing {ticker}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise HTTPException(status_code=500, detail=error_msg)


@app.get("/results/{ticker}")
async def get_analysis_results(ticker: str) -> Dict[str, Any]:
    """Get cached analysis results for a ticker."""
    try:
        # Validate ticker format
        ticker = ticker.upper().strip()
        is_valid, error_msg = validate_ticker(ticker, check_exists=False)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)

        logger.debug(f"Results request for ticker: {ticker}")

        # Get the latest analysis from database
        analysis = get_latest_analysis(ticker)

        if not analysis:
            logger.debug(f"No analysis found for {ticker}")
            raise HTTPException(
                status_code=404,
                detail=f"No analysis found for ticker: {ticker}"
            )

        logger.debug(f"Analysis results retrieved for {ticker}")

        return {
            "message": "Analysis results retrieved successfully",
            "ticker": ticker,
            "data": {
                "id": analysis["id"],
                "ticker": analysis["ticker"],
                "summary": analysis["analysis_summary"],
                "sentiment_report": analysis["sentiment_report"],
                "price_data": analysis.get("price_data", []),
                "headlines": analysis.get("headlines", []),
                "headlines_count": len(analysis.get("headlines", [])),
                "reasoning_steps": analysis.get("reasoning_steps", []),
                "tools_used": analysis.get("tools_used", []),
                "iterations": analysis.get("iterations", 0),
                "timestamp": analysis["timestamp"],
                "source": "cache",
                "agent_type": "ReAct"
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error retrieving results for {ticker}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise HTTPException(status_code=500, detail=error_msg)


@app.delete("/results/{ticker}")
async def delete_analysis_results(ticker: str) -> Dict[str, str]:
    """Delete cached analysis results for a ticker."""
    try:
        # Validate ticker format
        ticker = ticker.upper().strip()
        is_valid, error_msg = validate_ticker(ticker, check_exists=False)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)

        logger.info(f"Delete request for ticker: {ticker}")

        deleted = delete_cached_analysis(ticker)

        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=f"No analysis found for ticker: {ticker}"
            )

        logger.info(f"Analysis deleted for {ticker}")
        return {
            "message": f"Analysis for {ticker} deleted successfully",
            "ticker": ticker
        }

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error deleting analysis for {ticker}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise HTTPException(status_code=500, detail=error_msg)


@app.get("/cached-tickers")
async def get_cached_tickers() -> Dict[str, Any]:
    """
    Get list of cached tickers with timestamps.
    Returns ticker symbols and when they were analyzed.
    """
    try:
        logger.debug("Retrieving list of cached tickers...")

        cached_tickers = get_all_cached_tickers_with_timestamps()

        logger.debug(f"Found {len(cached_tickers)} cached tickers")

        return {
            "message": "Cached tickers retrieved successfully",
            "count": len(cached_tickers),
            "tickers": cached_tickers
        }

    except Exception as e:
        error_msg = f"Error retrieving cached tickers: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise HTTPException(status_code=500, detail=error_msg)


@app.get("/analyze/{ticker}/stream")
async def analyze_stock_stream(ticker: str, request: Request):
    """
    Stream analysis using Server-Sent Events (SSE).
    
    Stage 4: Streaming Analysis with Progressive Rendering
    
    Yields events as each tool completes:
    - started: Analysis initiated
    - tool_started: Starting a specific tool
    - tool_completed: Tool finished with partial data
    - completed: Full analysis result
    - error: If something goes wrong
    """
    from stocksense.orchestration.streaming import run_streaming_analysis
    
    # Rate limiting
    client_ip = get_client_ip(request)
    if not rate_limiter.is_allowed(client_ip):
        async def error_response():
            yield f"data: {json.dumps({'type': 'error', 'message': 'Rate limit exceeded'})}\n\n"
        return StreamingResponse(
            error_response(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    
    # Validate ticker
    ticker = ticker.upper().strip()
    is_valid, error_msg = validate_ticker(ticker)
    if not is_valid:
        async def error_response():
            yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"
        return StreamingResponse(
            error_response(),
            media_type="text/event-stream"
        )
    
    logger.info(f"Streaming analysis request for {ticker} from {client_ip}")
    
    async def event_generator():
        """Generate SSE events from streaming analysis."""
        import json
        
        try:
            async for event in run_streaming_analysis(ticker):
                yield event.to_sse()
                
                # If completed, also save to cache
                if event.event_type.value == "completed" and event.data:
                    try:
                        from stocksense.db.database import save_analysis
                        save_analysis(
                            ticker=ticker,
                            summary=event.data.get("summary", ""),
                            sentiment_report=event.data.get("sentiment_report", ""),
                            price_data=event.data.get("price_data", []),
                            headlines=event.data.get("headlines", []),
                            news_articles=event.data.get("news_articles", []),
                            reasoning_steps=[],
                            tools_used=event.data.get("tools_used", []),
                            iterations=1,
                            # Structured sentiment
                            overall_sentiment=event.data.get("overall_sentiment", ""),
                            overall_confidence=event.data.get("overall_confidence", 0.0),
                            # Fundamentals
                            fundamental_data=event.data.get("fundamental_data", {}),
                        )
                        logger.info(f"Streaming analysis saved to cache for {ticker}")
                    except Exception as e:
                        logger.warning(f"Failed to save streaming analysis: {e}")
                        
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


# ============================================================================
# Phase 3: Adversarial Collaboration (Debate Analysis)
# ============================================================================

@app.get(
    "/analyze/debate/{ticker}",
    tags=["Adversarial Debate"],
    summary="Run adversarial Bull/Bear debate analysis",
    description="Phase 3 analysis using Bull and Bear agents with rebuttal rounds and probability-weighted synthesis."
)
async def analyze_stock_debate(ticker: str, request: Request) -> Dict[str, Any]:
    """
    Run adversarial collaboration analysis with Bull and Bear agents.
    
    Phase 3: The Debate Update
    
    Architecture:
    1. Phase 1 (Parallel): Bull and Bear agents analyze data concurrently
    2. Phase 2 (Rebuttal): Each agent critiques the other's draft
    3. Phase 3 (Synthesis): Impartial judge produces probability-weighted verdict
    
    Returns:
        SynthesizedVerdict with bull/base/bear scenario probabilities
    """
    from stocksense.orchestration.react_flow import run_debate_analysis
    
    # Rate limiting (debate is more expensive - stricter limit)
    client_ip = get_client_ip(request)
    # Use same rate limiter but counts towards quota
    if not rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Debate analysis is resource-intensive. Please wait."
        )
    
    # Validate ticker
    ticker = ticker.upper().strip()
    is_valid, error_msg = validate_ticker(ticker)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    
    logger.info(f"Debate analysis request for {ticker} from {client_ip}")
    
    try:
        # Run the adversarial analysis
        result = await run_debate_analysis(ticker)
        
        if result.get("error"):
            raise HTTPException(
                status_code=500,
                detail=f"Debate analysis failed: {result['error']}"
            )
        
        logger.info(f"Debate analysis completed for {ticker}")
        
        return {
            "message": "Adversarial debate analysis completed",
            "ticker": ticker,
            "analysis_type": "adversarial_debate",
            "data": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Debate analysis error for {ticker}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise HTTPException(status_code=500, detail=error_msg)


@app.get(
    "/analyze/debate/{ticker}/stream",
    tags=["Adversarial Debate"],
    summary="Stream debate analysis via SSE",
    description="Real-time streaming of Bull/Bear debate phases using Server-Sent Events."
)
async def analyze_stock_debate_stream(ticker: str, request: Request):
    """
    Stream adversarial debate analysis using Server-Sent Events (SSE).
    
    Phase 3: Streaming Debate with real-time progress events.
    
    Yields events as each phase completes:
    - debate_started: Analysis initiated
    - bull_drafting: Bull agent building case
    - bear_drafting: Bear agent building case
    - bull_complete: Bull case finished
    - bear_complete: Bear case finished
    - rebuttal_round: Agents cross-examining
    - synthesis_started: Final verdict being generated
    - debate_completed: Full debate result
    - error: If something goes wrong
    """
    from stocksense.orchestration.streaming import run_streaming_debate_analysis
    
    # Rate limiting
    client_ip = get_client_ip(request)
    if not rate_limiter.is_allowed(client_ip):
        async def error_response():
            yield f"data: {json.dumps({'type': 'error', 'message': 'Rate limit exceeded'})}\n\n"
        return StreamingResponse(
            error_response(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    
    # Validate ticker
    ticker = ticker.upper().strip()
    is_valid, error_msg = validate_ticker(ticker)
    if not is_valid:
        async def error_response():
            yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"
        return StreamingResponse(
            error_response(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    
    logger.info(f"Streaming debate analysis for {ticker} from {client_ip}")
    
    async def event_generator():
        """Generate SSE events from streaming debate analysis."""
        try:
            async for event in run_streaming_debate_analysis(ticker):
                yield event.to_sse()
        except Exception as e:
            logger.error(f"Streaming debate error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


if __name__ == "__main__":
    # Support Render / other PaaS dynamic port assignment
    port = int(os.getenv("PORT", "8000"))
    reload_flag = os.getenv("UVICORN_RELOAD", "false").lower() == "true"
    log_level = os.getenv("LOG_LEVEL", "info")
    logger.info(f"Starting StockSense ReAct Agent FastAPI server on 0.0.0.0:{port} (reload={reload_flag}) ...")
    uvicorn.run(
        "stocksense.main:app",
        host="0.0.0.0",
        port=port,
        reload=reload_flag,
        log_level=log_level
    )