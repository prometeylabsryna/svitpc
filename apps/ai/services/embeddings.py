"""pgvector embeddings for semantic product search."""

from __future__ import annotations

import logging

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


def get_embedding(text: str) -> list[float] | None:
    """Get text embedding via OpenAI API."""
    if not settings.LLM_API_KEY:
        return None
    try:
        resp = httpx.post(
            f"{settings.LLM_BASE_URL}/embeddings",
            headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"},
            json={"model": "text-embedding-3-small", "input": text[:8192]},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]
    except Exception as exc:
        logger.error("Embedding failed: %s", exc)
        return None


def semantic_search(query: str, limit: int = 10):
    """Search products by semantic similarity using pgvector."""
    from apps.catalog.models import Product

    embedding = get_embedding(query)
    if embedding is None:
        return Product.objects.none()

    # pgvector cosine distance — requires vector column on Product
    # Product.embedding = VectorField(dimensions=1536) — add via migration when needed
    try:
        from pgvector.django import CosineDistance
        products = Product.objects.annotate(
            distance=CosineDistance("embedding", embedding)
        ).filter(is_visible=True).order_by("distance")[:limit]
        return products
    except Exception:
        return Product.objects.none()
