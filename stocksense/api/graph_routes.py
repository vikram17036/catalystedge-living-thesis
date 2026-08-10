"""Thesis Dependency Graph API — dedicated prefixes (no /theses/{id} collision)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from stocksense.api.auth_routes import get_current_user
from stocksense.db.supabase_client import (
    ThesisDependencyError,
    create_thesis_dependency,
    delete_thesis_dependency,
    get_thesis_graph,
)

router = APIRouter(prefix="/api", tags=["ThesisGraph"])


class DependencyCreate(BaseModel):
    from_thesis_id: str
    to_thesis_id: str
    link_type: str = Field(default="depends_on")
    meta: Optional[Dict[str, Any]] = None


@router.get("/thesis-graph")
async def thesis_graph(
    ticker: Optional[str] = None,
    user=Depends(get_current_user),
):
    return get_thesis_graph(user["id"], user["access_token"], ticker)


@router.post("/thesis-dependencies")
async def add_dependency(body: DependencyCreate, user=Depends(get_current_user)):
    try:
        row = create_thesis_dependency(
            user["id"],
            user["access_token"],
            from_thesis_id=body.from_thesis_id,
            to_thesis_id=body.to_thesis_id,
            link_type=body.link_type,
            meta=body.meta,
        )
        return {"dependency": row}
    except ThesisDependencyError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dependency create failed: {e}") from e


@router.delete("/thesis-dependencies/{dependency_id}")
async def remove_dependency(dependency_id: str, user=Depends(get_current_user)):
    ok = delete_thesis_dependency(user["id"], user["access_token"], dependency_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Dependency not found")
    return {"deleted": True}


@router.get("/thesis-graph-ping")
async def thesis_graph_ping():
    return {"thesis_graph": True, "routes": ["thesis-graph", "thesis-dependencies"]}
