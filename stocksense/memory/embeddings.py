"""Gemini Embedding 2 — asymmetric retrieval formatting, 768 dims."""

from __future__ import annotations

import logging
from typing import List, Optional

from stocksense.core.config import get_google_api_key

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "gemini-embedding-2"
EMBEDDING_DIM = 768


def prepare_query(text: str) -> str:
    return f"task: search result | query: {text.strip()}"


def prepare_document(content: str, title: Optional[str] = None) -> str:
    t = title if title else "none"
    return f"title: {t} | text: {content.strip()}"


def _client():
    from google import genai

    return genai.Client(api_key=get_google_api_key())


def _embed_raw(formatted: str) -> List[float]:
    from google.genai import types

    client = _client()
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=formatted,
        config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM),
    )
    values = result.embeddings[0].values
    if len(values) != EMBEDDING_DIM:
        raise RuntimeError(
            f"Expected {EMBEDDING_DIM}-dim embedding, got {len(values)}"
        )
    return list(values)


def embed_document(content: str, title: Optional[str] = None) -> List[float]:
    return _embed_raw(prepare_document(content, title=title))


def embed_query(query: str) -> List[float]:
    return _embed_raw(prepare_query(query))
