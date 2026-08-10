"""Scenario Lab API — Phase 6."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from stocksense.api.auth_routes import get_current_user
from stocksense.core.contracts import ScenarioSpec
from stocksense.research.scenario_parse import ScenarioParseError
from stocksense.research.scenario_service import run_scenario_request

router = APIRouter(prefix="/api", tags=["Scenarios"])


class ScenarioRequest(BaseModel):
    question: str = Field(..., min_length=1)
    prior_spec: Optional[Dict[str, Any]] = None


@router.post("/scenario")
async def scenario(
    body: ScenarioRequest,
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    prior: Optional[ScenarioSpec] = None
    if body.prior_spec:
        try:
            prior = ScenarioSpec.model_validate(body.prior_spec)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid prior_spec: {e}") from e
    try:
        return run_scenario_request(
            body.question,
            user_id=user["id"],
            access_token=user["access_token"],
            prior_spec=prior,
        )
    except ScenarioParseError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scenario failed: {e}") from e


@router.get("/scenario-ping")
async def scenario_ping():
    return {"scenarios": True, "routes": ["scenario"]}
