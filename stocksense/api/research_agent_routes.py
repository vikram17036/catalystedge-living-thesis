"""Phase 7 Research Agent API."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from stocksense.api.auth_routes import get_current_user

router = APIRouter(prefix="/api", tags=["ResearchAgent"])


class ResearchAgentRequest(BaseModel):
    message: str = Field(..., min_length=1)
    thread_id: Optional[str] = None
    ticker: Optional[str] = None
    thesis_id: Optional[str] = None


@router.post("/research-agent")
async def research_agent(
    body: ResearchAgentRequest,
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    from stocksense.orchestration.research_agent import run_research_turn

    try:
        return run_research_turn(
            message=body.message,
            user_id=user["id"],
            access_token=user["access_token"],
            thread_id=body.thread_id,
            ticker=body.ticker,
            thesis_id=body.thesis_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Research agent failed: {e}") from e


@router.post("/research-memory/reindex")
async def research_memory_reindex(
    ticker: Optional[str] = None,
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    from stocksense.memory.indexer import reindex_user_research
    from stocksense.memory.pinecone_store import PineconeUnavailable

    try:
        return reindex_user_research(
            user["id"], user["access_token"], ticker=ticker
        )
    except PineconeUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/research-agent-ping")
async def research_agent_ping():
    import os

    pinecone_configured = bool(
        (os.getenv("PINECONE_API_KEY") or "").strip()
        and (os.getenv("PINECONE_INDEX") or "").strip()
    )
    return {
        "research_agent": True,
        "routes": ["research-agent", "research-memory/reindex"],
        "pinecone_configured": pinecone_configured,
        "embedding_model": "gemini-embedding-2",
        "embedding_dim": 768,
    }
