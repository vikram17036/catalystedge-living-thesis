"""Pinecone vector store — namespace-per-user + metadata.user_id filter."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)

CHUNK_TEXT_MAX = 3500


class PineconeUnavailable(Exception):
    """Semantic memory unavailable; caller should degrade gracefully."""


def user_namespace(user_id: str) -> str:
    """Deterministic Pinecone namespace from user id (safe charset)."""
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "_", (user_id or "").strip())
    if not cleaned:
        raise ValueError("user_id required for namespace")
    return f"u_{cleaned}"[:64]


def vector_id(user_id: str, source_type: str, source_id: str, chunk_i: int) -> str:
    return f"{user_id}:{source_type}:{source_id}:{chunk_i}"


def truncate_chunk_text(text: str) -> str:
    t = (text or "").strip()
    if len(t) <= CHUNK_TEXT_MAX:
        return t
    return t[: CHUNK_TEXT_MAX - 3] + "..."


@dataclass
class MemoryHit:
    id: str
    score: float
    user_id: str
    ticker: str
    source_type: str
    source_id: str
    chunk_i: int
    chunk_text: str
    hypothetical: bool


class MemoryStore(Protocol):
    def upsert_chunks(
        self,
        *,
        user_id: str,
        vectors: List[Dict[str, Any]],
    ) -> int: ...

    def query(
        self,
        *,
        user_id: str,
        vector: List[float],
        top_k: int = 8,
        ticker: Optional[str] = None,
    ) -> List[MemoryHit]: ...

    def delete_by_source(
        self,
        *,
        user_id: str,
        source_type: str,
        source_id: str,
    ) -> None: ...


class PineconeMemoryStore:
    def __init__(self, api_key: str, index_name: str):
        from pinecone import Pinecone

        self._pc = Pinecone(api_key=api_key)
        self._index_name = index_name
        self._index = self._pc.Index(index_name)

    def upsert_chunks(self, *, user_id: str, vectors: List[Dict[str, Any]]) -> int:
        if not vectors:
            return 0
        ns = user_namespace(user_id)
        payload = []
        for v in vectors:
            meta = dict(v["metadata"])
            meta["user_id"] = user_id
            meta["chunk_text"] = truncate_chunk_text(str(meta.get("chunk_text") or ""))
            payload.append(
                {
                    "id": v["id"],
                    "values": v["values"],
                    "metadata": meta,
                }
            )
        self._index.upsert(vectors=payload, namespace=ns)
        return len(payload)

    def query(
        self,
        *,
        user_id: str,
        vector: List[float],
        top_k: int = 8,
        ticker: Optional[str] = None,
    ) -> List[MemoryHit]:
        ns = user_namespace(user_id)
        flt: Dict[str, Any] = {"user_id": {"$eq": user_id}}
        if ticker:
            flt["ticker"] = {"$eq": ticker.upper()}
        try:
            res = self._index.query(
                vector=vector,
                top_k=top_k,
                namespace=ns,
                filter=flt,
                include_metadata=True,
            )
        except Exception as e:
            msg = str(e).lower()
            if "namespace not found" in msg:
                return []
            raise PineconeUnavailable(str(e)) from e
        raw_matches = (
            res.get("matches")
            if isinstance(res, dict)
            else getattr(res, "matches", None)
        ) or []
        hits: List[MemoryHit] = []
        for m in raw_matches:
            if isinstance(m, dict):
                meta = m.get("metadata") or {}
                mid = m.get("id")
                score = m.get("score")
            else:
                meta = getattr(m, "metadata", None) or {}
                if not isinstance(meta, dict):
                    meta = dict(meta) if meta else {}
                mid = getattr(m, "id", "")
                score = getattr(m, "score", 0.0)
            if str(meta.get("user_id") or "") != str(user_id):
                continue
            hits.append(
                MemoryHit(
                    id=str(mid or ""),
                    score=float(score or 0.0),
                    user_id=str(meta.get("user_id") or ""),
                    ticker=str(meta.get("ticker") or ""),
                    source_type=str(meta.get("source_type") or ""),
                    source_id=str(meta.get("source_id") or ""),
                    chunk_i=int(meta.get("chunk_i") or 0),
                    chunk_text=str(meta.get("chunk_text") or ""),
                    hypothetical=bool(meta.get("hypothetical")),
                )
            )
        return hits

    def delete_by_source(
        self,
        *,
        user_id: str,
        source_type: str,
        source_id: str,
    ) -> None:
        ns = user_namespace(user_id)
        flt = {
            "user_id": {"$eq": user_id},
            "source_type": {"$eq": source_type},
            "source_id": {"$eq": str(source_id)},
        }
        def _ns_missing(err: Exception) -> bool:
            msg = str(err).lower()
            return "namespace not found" in msg or "404" in msg

        try:
            self._index.delete(filter=flt, namespace=ns)
        except Exception as e:
            if _ns_missing(e):
                return  # nothing to delete yet
            logger.warning("Pinecone delete by filter failed, trying id sweep: %s", e)
            ids = [
                vector_id(user_id, source_type, str(source_id), i) for i in range(32)
            ]
            try:
                self._index.delete(ids=ids, namespace=ns)
            except Exception as e2:
                if _ns_missing(e2):
                    return
                logger.error("Pinecone delete_by_source failed: %s", e2)
                raise PineconeUnavailable(str(e2)) from e2


class InMemoryMemoryStore:
    """Test double — same isolation rules as Pinecone store."""

    def __init__(self):
        self._ns: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def upsert_chunks(self, *, user_id: str, vectors: List[Dict[str, Any]]) -> int:
        ns = user_namespace(user_id)
        bucket = self._ns.setdefault(ns, {})
        for v in vectors:
            meta = dict(v["metadata"])
            meta["user_id"] = user_id
            meta["chunk_text"] = truncate_chunk_text(str(meta.get("chunk_text") or ""))
            bucket[v["id"]] = {"values": v["values"], "metadata": meta}
        return len(vectors)

    def query(
        self,
        *,
        user_id: str,
        vector: List[float],
        top_k: int = 8,
        ticker: Optional[str] = None,
    ) -> List[MemoryHit]:
        import math

        ns = user_namespace(user_id)
        bucket = self._ns.get(ns, {})
        scored: List[MemoryHit] = []
        for vid, row in bucket.items():
            meta = row["metadata"]
            if str(meta.get("user_id") or "") != str(user_id):
                continue
            if ticker and str(meta.get("ticker") or "").upper() != ticker.upper():
                continue
            a = row["values"]
            # cosine similarity
            dot = sum(x * y for x, y in zip(a, vector))
            na = math.sqrt(sum(x * x for x in a)) or 1.0
            nb = math.sqrt(sum(x * x for x in vector)) or 1.0
            score = dot / (na * nb)
            scored.append(
                MemoryHit(
                    id=vid,
                    score=score,
                    user_id=str(meta.get("user_id") or ""),
                    ticker=str(meta.get("ticker") or ""),
                    source_type=str(meta.get("source_type") or ""),
                    source_id=str(meta.get("source_id") or ""),
                    chunk_i=int(meta.get("chunk_i") or 0),
                    chunk_text=str(meta.get("chunk_text") or ""),
                    hypothetical=bool(meta.get("hypothetical")),
                )
            )
        scored.sort(key=lambda h: h.score, reverse=True)
        return scored[:top_k]

    def delete_by_source(
        self,
        *,
        user_id: str,
        source_type: str,
        source_id: str,
    ) -> None:
        ns = user_namespace(user_id)
        bucket = self._ns.get(ns, {})
        drop = [
            vid
            for vid, row in bucket.items()
            if row["metadata"].get("source_type") == source_type
            and str(row["metadata"].get("source_id")) == str(source_id)
            and str(row["metadata"].get("user_id")) == str(user_id)
        ]
        for vid in drop:
            del bucket[vid]


_store: Optional[MemoryStore] = None
_force_memory: Optional[MemoryStore] = None


def reset_memory_store_for_tests(store: Optional[MemoryStore] = None) -> None:
    global _store, _force_memory
    _force_memory = store
    _store = store


def get_memory_store() -> MemoryStore:
    global _store
    if _force_memory is not None:
        return _force_memory
    if _store is not None:
        return _store
    api_key = (os.getenv("PINECONE_API_KEY") or "").strip()
    index_name = (os.getenv("PINECONE_INDEX") or "").strip()
    if not api_key or not index_name:
        raise PineconeUnavailable(
            "PINECONE_API_KEY / PINECONE_INDEX not configured"
        )
    try:
        _store = PineconeMemoryStore(api_key, index_name)
    except Exception as e:
        raise PineconeUnavailable(str(e)) from e
    return _store
