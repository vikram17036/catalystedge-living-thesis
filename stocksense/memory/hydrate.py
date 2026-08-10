"""Hydrate Pinecone source refs from Supabase (system of record)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from stocksense.memory.pinecone_store import MemoryHit

logger = logging.getLogger(__name__)


def hydrate_memory_hits(
    hits: List[MemoryHit],
    *,
    user_id: str,
    access_token: str,
) -> List[Dict[str, Any]]:
    """
    Resolve each hit to a canonical Supabase object + ownership check.
    Citations must use these hydrated records, not raw chunk_text alone.
    """
    from stocksense.db.supabase_client import _authed_supabase, list_thesis_evidence

    if not hits:
        return []

    client = _authed_supabase(access_token)
    out: List[Dict[str, Any]] = []
    seen = set()

    for hit in hits:
        key = (hit.source_type, hit.source_id)
        if key in seen:
            continue
        seen.add(key)

        if str(hit.user_id) != str(user_id):
            logger.warning("Dropped cross-user memory hit %s", hit.id)
            continue

        record: Optional[Dict[str, Any]] = None
        st = hit.source_type

        try:
            if st == "thesis":
                resp = (
                    client.table("theses")
                    .select("*")
                    .eq("id", hit.source_id)
                    .eq("user_id", user_id)
                    .limit(1)
                    .execute()
                )
                record = resp.data[0] if resp.data else None
            elif st == "alert":
                resp = (
                    client.table("kill_alerts")
                    .select("*")
                    .eq("id", hit.source_id)
                    .eq("user_id", user_id)
                    .limit(1)
                    .execute()
                )
                record = resp.data[0] if resp.data else None
            else:
                # thesis_evidence by evidence_id
                resp = (
                    client.table("thesis_evidence")
                    .select("*")
                    .eq("evidence_id", hit.source_id)
                    .eq("user_id", user_id)
                    .limit(1)
                    .execute()
                )
                record = resp.data[0] if resp.data else None
                if record is None:
                    # fallback: row id
                    resp2 = (
                        client.table("thesis_evidence")
                        .select("*")
                        .eq("id", hit.source_id)
                        .eq("user_id", user_id)
                        .limit(1)
                        .execute()
                    )
                    record = resp2.data[0] if resp2.data else None
        except Exception as e:
            logger.error("hydrate failed for %s/%s: %s", st, hit.source_id, e)
            record = None

        if not record:
            continue

        out.append(
            {
                "source_type": st,
                "source_id": hit.source_id,
                "ticker": hit.ticker,
                "score": hit.score,
                "hypothetical": hit.hypothetical
                or bool((record.get("evidence") or {}).get("hypothetical"))
                if isinstance(record.get("evidence"), dict)
                else hit.hypothetical,
                "chunk_preview": hit.chunk_text[:240],
                "canonical": record,
                "citation_id": f"{st}:{hit.source_id}",
                "validated": True,
            }
        )

    return out


def retrieve_and_hydrate(
    query: str,
    *,
    user_id: str,
    access_token: str,
    ticker: Optional[str] = None,
    top_k: int = 8,
) -> Dict[str, Any]:
    """Pinecone refs → hydrate. Degrades if Pinecone down."""
    from stocksense.memory.embeddings import embed_query
    from stocksense.memory.pinecone_store import PineconeUnavailable, get_memory_store

    try:
        store = get_memory_store()
        vector = embed_query(query)
        hits = store.query(
            user_id=user_id, vector=vector, top_k=top_k, ticker=ticker
        )
    except PineconeUnavailable as e:
        return {
            "available": False,
            "error": str(e),
            "refs": [],
            "hydrated": [],
        }
    except Exception as e:
        logger.error("retrieve_and_hydrate error: %s", e)
        return {
            "available": False,
            "error": str(e),
            "refs": [],
            "hydrated": [],
        }

    refs = [
        {
            "source_type": h.source_type,
            "source_id": h.source_id,
            "ticker": h.ticker,
            "score": h.score,
            "chunk_i": h.chunk_i,
            "hypothetical": h.hypothetical,
        }
        for h in hits
    ]
    hydrated = hydrate_memory_hits(hits, user_id=user_id, access_token=access_token)
    return {
        "available": True,
        "error": None,
        "refs": refs,
        "hydrated": hydrated,
    }
