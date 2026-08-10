"""Strategy Lab API — typed SMA backtests (no exec)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from stocksense.api.auth_routes import get_current_user
from stocksense.core.contracts import StrategySpec
from stocksense.research.strategy_parse import StrategyParseError
from stocksense.research.strategy_service import run_strategy_request

router = APIRouter(prefix="/api", tags=["Lab"])


class BacktestRequest(BaseModel):
    question: str = Field(..., min_length=1)
    prior_spec: Optional[Dict[str, Any]] = None
    prior_result: Optional[Dict[str, Any]] = None


@router.post("/backtest")
async def backtest(
    body: BacktestRequest,
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    prior: Optional[StrategySpec] = None
    if body.prior_spec:
        try:
            prior = StrategySpec.model_validate(body.prior_spec)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid prior_spec: {e}") from e
    try:
        return run_strategy_request(body.question, prior, body.prior_result)
    except StrategyParseError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backtest failed: {e}") from e


@router.get("/lab-ping")
async def lab_ping():
    return {"lab": True, "routes": ["backtest"], "strategy": "sma_crossover"}
