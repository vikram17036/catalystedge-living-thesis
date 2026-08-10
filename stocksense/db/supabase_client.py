"""
Supabase client and authentication utilities.

Stage 3: User Belief System
"""

import os
import logging
from functools import lru_cache
from typing import Optional, Dict, Any

logger = logging.getLogger("stocksense.supabase")

from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()


class SupabaseAuthError(Exception):
    """Custom exception for Supabase auth errors."""
    pass


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    """
    Get a cached Supabase client instance.
    
    Uses the anon/publishable key for client-safe operations.
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")
    
    if not url or not key:
        raise SupabaseAuthError(
            "Missing Supabase credentials. Set SUPABASE_URL and SUPABASE_ANON_KEY in .env"
        )
    
    return create_client(url, key)


def get_supabase_admin_client() -> Client:
    """
    Get a Supabase client with service role (admin) privileges.
    
    Use only for server-side operations that need to bypass RLS.
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    
    if not url or not key:
        raise SupabaseAuthError(
            "Missing Supabase admin credentials. Set SUPABASE_URL and SUPABASE_SERVICE_KEY in .env"
        )
    
    return create_client(url, key)


def verify_user_token(access_token: str) -> Optional[Dict[str, Any]]:
    """
    Verify a user's JWT access token and return user info.
    
    Args:
        access_token: The JWT from the Authorization header
        
    Returns:
        User data dict if valid, None if invalid
    """
    try:
        client = get_supabase_client()
        # Get user from token
        user_response = client.auth.get_user(access_token)
        
        if user_response and user_response.user:
            return {
                "id": str(user_response.user.id),
                "email": user_response.user.email,
                "created_at": str(user_response.user.created_at) if user_response.user.created_at else None,
            }
        return None
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        return None


def get_user_profile(user_id: str, access_token: str) -> Optional[Dict[str, Any]]:
    """
    Get user profile from profiles table.
    
    Args:
        user_id: The user's UUID
        access_token: User's JWT for RLS
        
    Returns:
        Profile data or None
    """
    try:
        client = get_supabase_client()
        # Set auth header for RLS
        client.postgrest.auth(access_token)
        
        response = client.table("profiles").select("*").eq("id", user_id).single().execute()
        return response.data
    except Exception as e:
        logger.error(f"Profile fetch error: {e}")
        return None


# ============================================
# Position Operations
# ============================================

def get_user_positions(user_id: str, access_token: str) -> list:
    """Get all positions for a user."""
    try:
        client = get_supabase_client()
        client.postgrest.auth(access_token)
        
        response = client.table("positions").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        return response.data or []
    except Exception as e:
        logger.error(f"Positions fetch error: {e}")
        return []


def create_position(user_id: str, access_token: str, position_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Create a new position for a user."""
    try:
        client = get_supabase_client()
        client.postgrest.auth(access_token)
        
        data = {
            "user_id": user_id,
            "ticker": position_data["ticker"].upper(),
            "position_type": position_data.get("position_type", "watching"),
            "entry_date": position_data.get("entry_date"),
            "entry_price": position_data.get("entry_price"),
            "current_shares": position_data.get("current_shares"),
            "notes": position_data.get("notes"),
        }
        
        response = client.table("positions").insert(data).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        logger.error(f"Position create error: {e}")
        return None


def delete_position(user_id: str, access_token: str, position_id: str) -> bool:
    """Delete a position."""
    try:
        client = get_supabase_client()
        client.postgrest.auth(access_token)
        
        client.table("positions").delete().eq("id", position_id).eq("user_id", user_id).execute()
        return True
    except Exception as e:
        logger.error(f"Position delete error: {e}")
        return False


# ============================================
# Thesis Operations
# ============================================

def get_user_theses(user_id: str, access_token: str, ticker: Optional[str] = None) -> list:
    """Get theses for a user, optionally filtered by ticker."""
    try:
        client = get_supabase_client()
        client.postgrest.auth(access_token)
        
        query = client.table("theses").select("*").eq("user_id", user_id)
        if ticker:
            query = query.eq("ticker", ticker.upper())
        
        response = query.order("created_at", desc=True).execute()
        return response.data or []
    except Exception as e:
        logger.error(f"Theses fetch error: {e}")
        return []


def create_thesis(user_id: str, access_token: str, thesis_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Create a new thesis with kill criteria and optional analysis linkage."""
    try:
        client = get_supabase_client()
        client.postgrest.auth(access_token)
        
        data = {
            "user_id": user_id,
            "ticker": thesis_data["ticker"].upper(),
            "position_id": thesis_data.get("position_id"),
            "thesis_summary": thesis_data["thesis_summary"],
            "conviction_level": thesis_data.get("conviction_level", "medium"),
            "kill_criteria": thesis_data.get("kill_criteria", []),
            "time_horizon": thesis_data.get("time_horizon", "medium"),
            "thesis_type": thesis_data.get("thesis_type", "growth"),
            "status": "active",
        }
        
        # Stage 4 / Phase 1: Analysis-Thesis Linkage + evidence freeze
        if thesis_data.get("origin_analysis_id"):
            data["origin_analysis_id"] = thesis_data["origin_analysis_id"]
        if thesis_data.get("origin_analysis_snapshot"):
            data["origin_analysis_snapshot"] = thesis_data["origin_analysis_snapshot"]
        if thesis_data.get("origin_evidence") is not None:
            data["origin_evidence"] = thesis_data["origin_evidence"]
        if thesis_data.get("structured_kill_criteria") is not None:
            data["structured_kill_criteria"] = thesis_data["structured_kill_criteria"]
        
        response = client.table("theses").insert(data).execute()
        thesis = response.data[0] if response.data else None
        
        # Create history entry
        if thesis:
            _create_thesis_history(user_id, access_token, thesis["id"], thesis, "created")
            try:
                from stocksense.memory.indexer import index_thesis

                index_thesis(user_id, thesis)
            except Exception as idx_err:
                logger.warning(f"thesis memory index skipped: {idx_err}")
        
        return thesis
    except Exception as e:
        logger.error(f"Thesis create error: {e}")
        return None



def update_thesis(user_id: str, access_token: str, thesis_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update a thesis and log history."""
    try:
        client = get_supabase_client()
        client.postgrest.auth(access_token)

        # History-only fields — not columns on public.theses
        payload = dict(updates)
        change_reason = payload.pop("change_reason", None)
        row_updates = {k: v for k, v in payload.items() if v is not None}
        if not row_updates:
            return None

        # Get current thesis for history
        current = client.table("theses").select("*").eq("id", thesis_id).eq("user_id", user_id).single().execute()
        if not current.data:
            return None

        # Determine change type
        change_type = "updated"
        if "conviction_level" in row_updates and row_updates["conviction_level"] != current.data.get("conviction_level"):
            change_type = "conviction_changed"
        if row_updates.get("status") == "invalidated":
            change_type = "invalidated"
        if row_updates.get("status") == "exited":
            change_type = "exited"

        # Update thesis
        response = (
            client.table("theses")
            .update(row_updates)
            .eq("id", thesis_id)
            .eq("user_id", user_id)
            .execute()
        )
        thesis = response.data[0] if response.data else None

        # Create history entry
        if thesis:
            _create_thesis_history(
                user_id,
                access_token,
                thesis_id,
                thesis,
                change_type,
                change_reason,
            )
            try:
                from stocksense.memory.indexer import index_thesis

                index_thesis(user_id, thesis)
            except Exception as idx_err:
                logger.warning(f"thesis memory index skipped: {idx_err}")

        return thesis
    except Exception as e:
        logger.error(f"Thesis update error: {e}")
        return None


def _create_thesis_history(
    user_id: str, 
    access_token: str, 
    thesis_id: str, 
    thesis: Dict[str, Any],
    change_type: str,
    change_reason: Optional[str] = None
) -> None:
    """Create a thesis history entry."""
    try:
        client = get_supabase_client()
        client.postgrest.auth(access_token)
        
        data = {
            "thesis_id": thesis_id,
            "user_id": user_id,
            "thesis_summary": thesis["thesis_summary"],
            "conviction_level": thesis.get("conviction_level"),
            "kill_criteria": thesis.get("kill_criteria"),
            "change_type": change_type,
            "change_reason": change_reason,
        }
        
        client.table("thesis_history").insert(data).execute()
    except Exception as e:
        logger.error(f"Thesis history error: {e}")


def get_thesis_history(user_id: str, access_token: str, thesis_id: str) -> list:
    """Get history for a specific thesis."""
    try:
        client = get_supabase_client()
        client.postgrest.auth(access_token)
        
        response = client.table("thesis_history").select("*").eq("thesis_id", thesis_id).eq("user_id", user_id).order("created_at", desc=True).execute()
        return response.data or []
    except Exception as e:
        logger.error(f"Thesis history fetch error: {e}")
        return []


def _authed_supabase(access_token: str) -> Client:
    """Fresh client + user JWT so RLS auth.uid() is reliable (avoid singleton race)."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")
    if not url or not key:
        raise SupabaseAuthError(
            "Missing Supabase credentials. Set SUPABASE_URL and SUPABASE_ANON_KEY in .env"
        )
    client = create_client(url, key)
    client.postgrest.auth(access_token)
    return client


def list_thesis_evidence(user_id: str, access_token: str, thesis_id: str) -> list:
    """List attached research evidence for a thesis (not origin_evidence)."""
    try:
        client = _authed_supabase(access_token)
        response = (
            client.table("thesis_evidence")
            .select("*")
            .eq("thesis_id", thesis_id)
            .eq("user_id", user_id)
            .order("attached_at", desc=False)
            .execute()
        )
        return response.data or []
    except Exception as e:
        logger.error(f"thesis_evidence list error: {e}")
        # Surface missing-table / RLS failures instead of pretending there are zero rows
        raise


def attach_thesis_evidence(
    user_id: str,
    access_token: str,
    thesis_id: str,
    evidence: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Insert attached evidence row. Idempotent on (thesis_id, evidence_id).
    Never writes theses.origin_evidence.
    Returns { attached: bool, already_attached: bool, row, thesis }.
    """
    from stocksense.core.thesis_attach import AttachError, validate_attach_payload

    client = _authed_supabase(access_token)

    thesis_resp = (
        client.table("theses")
        .select("*")
        .eq("id", thesis_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not thesis_resp.data:
        raise AttachError("Thesis not found")
    thesis = thesis_resp.data[0]

    normalized = validate_attach_payload(evidence, thesis["ticker"])
    eid = normalized["id"]
    etype = normalized["type"]

    existing = (
        client.table("thesis_evidence")
        .select("*")
        .eq("thesis_id", thesis_id)
        .eq("evidence_id", eid)
        .limit(1)
        .execute()
    )
    if existing.data:
        return {
            "attached": False,
            "already_attached": True,
            "row": existing.data[0],
            "thesis": thesis,
        }

    insert = {
        "thesis_id": thesis_id,
        "user_id": user_id,
        "evidence_id": eid,
        "evidence_type": etype,
        "evidence": normalized,
    }
    try:
        inserted = client.table("thesis_evidence").insert(insert).execute()
    except Exception as e:
        raise AttachError(
            f"thesis_evidence insert failed (table/RLS/grants?): {e}"
        ) from e

    if not inserted.data:
        raise AttachError(
            "thesis_evidence insert returned no row — check RLS policies and "
            "GRANT for authenticated on public.thesis_evidence"
        )

    row = inserted.data[0]
    try:
        from stocksense.memory.indexer import index_evidence_row

        index_evidence_row(user_id, row, ticker=str(thesis.get("ticker") or ""))
    except Exception as idx_err:
        logger.warning(f"evidence memory index skipped: {idx_err}")
    return {
        "attached": True,
        "already_attached": False,
        "row": row,
        "thesis": thesis,
    }


def get_active_thesis_for_ticker(
    user_id: str, access_token: str, ticker: str
) -> Optional[Dict[str, Any]]:
    """Newest active thesis for ticker, or None."""
    theses = get_user_theses(user_id, access_token, ticker)
    for t in theses:
        if (t.get("status") or "active") == "active":
            return t
    return None


def enrich_thesis_with_attachments(
    user_id: str, access_token: str, thesis: Dict[str, Any]
) -> Dict[str, Any]:
    out = dict(thesis)
    try:
        rows = list_thesis_evidence(user_id, access_token, thesis["id"])
    except Exception as e:
        logger.error(f"enrich attachments failed for {thesis.get('id')}: {e}")
        out["attached_evidence"] = []
        out["attached_evidence_rows"] = []
        out["attached_evidence_error"] = str(e)
        return out
    out["attached_evidence"] = [r.get("evidence") for r in rows if r.get("evidence")]
    out["attached_evidence_rows"] = rows
    return out


class ThesisDependencyError(ValueError):
    pass


def _owned_thesis(
    user_id: str, access_token: str, thesis_id: str
) -> Optional[Dict[str, Any]]:
    client = _authed_supabase(access_token)
    resp = (
        client.table("theses")
        .select("id,ticker,thesis_summary,status,user_id")
        .eq("id", thesis_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None


def create_thesis_dependency(
    user_id: str,
    access_token: str,
    *,
    from_thesis_id: str,
    to_thesis_id: str,
    link_type: str,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    allowed = {"depends_on", "related_ticker", "shared_kill_metric"}
    if link_type not in allowed:
        raise ThesisDependencyError(f"link_type must be one of {sorted(allowed)}")
    if from_thesis_id == to_thesis_id:
        raise ThesisDependencyError("Cannot link a thesis to itself")
    src = _owned_thesis(user_id, access_token, from_thesis_id)
    dst = _owned_thesis(user_id, access_token, to_thesis_id)
    if not src or not dst:
        raise ThesisDependencyError("Both theses must exist and belong to you")

    client = _authed_supabase(access_token)
    row = {
        "user_id": user_id,
        "from_thesis_id": from_thesis_id,
        "to_thesis_id": to_thesis_id,
        "link_type": link_type,
        "meta": meta or {},
    }
    inserted = client.table("thesis_dependencies").insert(row).execute()
    if not inserted.data:
        raise ThesisDependencyError(
            "Dependency insert returned no row — check RLS/grants on thesis_dependencies"
        )
    return inserted.data[0]


def delete_thesis_dependency(
    user_id: str, access_token: str, dependency_id: str
) -> bool:
    client = _authed_supabase(access_token)
    resp = (
        client.table("thesis_dependencies")
        .delete()
        .eq("id", dependency_id)
        .eq("user_id", user_id)
        .execute()
    )
    return bool(resp.data)


def get_thesis_graph(
    user_id: str, access_token: str, ticker: Optional[str] = None
) -> Dict[str, Any]:
    theses = get_user_theses(user_id, access_token, ticker)
    ids = {str(t["id"]) for t in theses}
    client = _authed_supabase(access_token)
    edges_resp = (
        client.table("thesis_dependencies")
        .select("*")
        .eq("user_id", user_id)
        .execute()
    )
    edges = []
    for e in edges_resp.data or []:
        if str(e["from_thesis_id"]) in ids or str(e["to_thesis_id"]) in ids:
            if ticker:
                # keep edge if either endpoint is in filtered thesis set
                if str(e["from_thesis_id"]) in ids and str(e["to_thesis_id"]) in ids:
                    edges.append(e)
            else:
                edges.append(e)
    nodes = [
        {
            "id": t["id"],
            "ticker": t.get("ticker"),
            "thesis_summary": (t.get("thesis_summary") or "")[:160],
            "status": t.get("status"),
        }
        for t in theses
    ]
    return {"nodes": nodes, "edges": edges, "count_nodes": len(nodes), "count_edges": len(edges)}
