"""Research API — Event Study and future experiment tools.

Separate from auth_routes / thesis lifecycle.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from stocksense.api.auth_routes import get_current_user
from stocksense.core.contracts import EventStudySpec
from stocksense.research.event_study_parse import ParseError
from stocksense.research.service import run_event_study_request

router = APIRouter(prefix="/api", tags=["Research"])


class EventStudyRequest(BaseModel):
    question: str = Field(..., min_length=1)
    prior_spec: Optional[Dict[str, Any]] = None
    use_llm: bool = True


@router.post("/event-study")
async def event_study(
    body: EventStudyRequest,
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Run a typed historical event study from a natural-language question."""
    prior: Optional[EventStudySpec] = None
    if body.prior_spec:
        try:
            prior = EventStudySpec.model_validate(body.prior_spec)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid prior_spec: {e}") from e

    try:
        return run_event_study_request(
            body.question, prior, use_llm=body.use_llm
        )
    except ParseError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Event study failed: {e}") from e


@router.get("/research-ping")
async def research_ping():
    return {"research": True, "routes": ["event-study"]}
