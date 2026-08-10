"""Analog Search API — Phase 5."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from stocksense.api.auth_routes import get_current_user
from stocksense.core.contracts import AnalogSpec
from stocksense.research.analog_search_parse import AnalogParseError
from stocksense.research.analog_service import run_analog_search_request

router = APIRouter(prefix="/api", tags=["Analogs"])


class AnalogSearchRequest(BaseModel):
    question: str = Field(..., min_length=1)
    prior_spec: Optional[Dict[str, Any]] = None


@router.post("/analog-search")
async def analog_search(
    body: AnalogSearchRequest,
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Find historical return-path analogs; compute forward outcomes in code."""
    prior: Optional[AnalogSpec] = None
    if body.prior_spec:
        try:
            prior = AnalogSpec.model_validate(body.prior_spec)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid prior_spec: {e}") from e

    try:
        return run_analog_search_request(body.question, prior)
    except AnalogParseError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analog search failed: {e}") from e


@router.get("/analogs-ping")
async def analogs_ping():
    return {"analogs": True, "routes": ["analog-search"]}
