"""Index research into Pinecone — delete_by_source then rebuild."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from stocksense.memory.chunks import chunks_for_evidence_row, chunks_for_thesis
from stocksense.memory.embeddings import embed_document
from stocksense.memory.pinecone_store import (
    PineconeUnavailable,
    get_memory_store,
    vector_id,
)

logger = logging.getLogger(__name__)


def _upsert_chunk_dicts(*, user_id: str, chunks: List[Dict[str, Any]]) -> int:
    if not chunks:
        return 0
    store = get_memory_store()
    source_type = chunks[0]["source_type"]
    source_id = str(chunks[0]["source_id"])
    store.delete_by_source(
        user_id=user_id, source_type=source_type, source_id=source_id
    )
    vectors = []
    for ch in chunks:
        values = embed_document(ch["chunk_text"], title=ch.get("title"))
        vectors.append(
            {
                "id": vector_id(
                    user_id, ch["source_type"], str(ch["source_id"]), int(ch["chunk_i"])
                ),
                "values": values,
                "metadata": {
                    "user_id": user_id,
                    "ticker": ch.get("ticker") or "",
                    "source_type": ch["source_type"],
                    "source_id": str(ch["source_id"]),
                    "chunk_i": int(ch["chunk_i"]),
                    "chunk_text": ch["chunk_text"],
                    "hypothetical": bool(ch.get("hypothetical")),
                },
            }
        )
    return store.upsert_chunks(user_id=user_id, vectors=vectors)


def index_thesis(user_id: str, thesis: Dict[str, Any]) -> int:
    """Best-effort index; never raises into thesis CRUD."""
    try:
        chunks = chunks_for_thesis(thesis)
        if not thesis.get("id"):
            return 0
        return _upsert_chunk_dicts(user_id=user_id, chunks=chunks)
    except PineconeUnavailable as e:
        logger.warning("index_thesis skipped (memory unavailable): %s", e)
        return 0
    except Exception as e:
        logger.error("index_thesis failed: %s", e)
        return 0


def index_evidence_row(
    user_id: str, row: Dict[str, Any], *, ticker: str
) -> int:
    try:
        chunks = chunks_for_evidence_row(row, ticker=ticker)
        return _upsert_chunk_dicts(user_id=user_id, chunks=chunks)
    except PineconeUnavailable as e:
        logger.warning("index_evidence skipped (memory unavailable): %s", e)
        return 0
    except Exception as e:
        logger.error("index_evidence failed: %s", e)
        return 0


def reindex_user_research(
    user_id: str,
    access_token: str,
    *,
    ticker: Optional[str] = None,
) -> Dict[str, Any]:
    """Backfill theses + attached evidence for a user."""
    from stocksense.db.supabase_client import get_user_theses, list_thesis_evidence

    indexed = 0
    sources = 0
    errors: List[str] = []
    theses = get_user_theses(user_id, access_token, ticker)
    for thesis in theses:
        n = index_thesis(user_id, thesis)
        indexed += n
        if n:
            sources += 1
        try:
            rows = list_thesis_evidence(user_id, access_token, thesis["id"])
        except Exception as e:
            errors.append(str(e)[:200])
            continue
        for row in rows:
            n = index_evidence_row(
                user_id, row, ticker=str(thesis.get("ticker") or "")
            )
            indexed += n
            if n:
                sources += 1
    return {
        "indexed_vectors": indexed,
        "chunks_indexed": indexed,
        "sources_indexed": sources,
        "theses": len(theses),
        "errors": errors,
        "ok": len(errors) == 0,
    }
