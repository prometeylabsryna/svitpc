"""Listing thumbnails — WebP cache for product cards (Brain CDN + local uploads)."""

from __future__ import annotations

import hashlib
import io
import logging
from pathlib import Path
from urllib.parse import urlparse

import requests
from django.conf import settings
from PIL import Image

from apps.catalog.gallery import resolve_product_image_url

logger = logging.getLogger(__name__)

LISTING_SIZE = 300
WEBP_QUALITY = 82
DOWNLOAD_TIMEOUT = 8
MAX_BYTES = 6 * 1024 * 1024

ALLOWED_IMAGE_HOSTS = frozenset(
    {
        "opt.brain.com.ua",
        "brain.com.ua",
        "www.brain.com.ua",
    }
)


def _cache_dir() -> Path:
    return Path(settings.MEDIA_ROOT) / "cache" / "listing"


def listing_source_key(product) -> str:
    """Changes when the display source changes (invalidates disk cache)."""
    if product.image:
        name = product.image.name
        modified = int(product.date_modified.timestamp()) if product.date_modified else 0
        return hashlib.sha256(f"local:{name}:{modified}".encode()).hexdigest()[:16]
    source = resolve_product_image_url(product)
    if not source:
        return ""
    return hashlib.sha256(source.encode()).hexdigest()[:16]


def listing_cache_path(product_pk: int, source_key: str) -> Path:
    return _cache_dir() / f"{product_pk}_{source_key}.webp"


def is_allowed_remote_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in ALLOWED_IMAGE_HOSTS


def _resize_to_webp(data: bytes, size: int = LISTING_SIZE) -> bytes:
    img = Image.open(io.BytesIO(data))
    img.load()
    if img.width > size or img.height > size:
        img.thumbnail((size, size), Image.Resampling.LANCZOS)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA" if "A" in img.getbands() else "RGB")
    out = io.BytesIO()
    if img.mode == "RGBA":
        img.save(out, format="WEBP", quality=WEBP_QUALITY, method=6)
    else:
        img.convert("RGB").save(out, format="WEBP", quality=WEBP_QUALITY, method=6)
    return out.getvalue()


def fetch_listing_webp(source_url: str, *, size: int = LISTING_SIZE) -> bytes:
    if not is_allowed_remote_url(source_url):
        raise ValueError(f"Remote host not allowed: {source_url}")

    response = requests.get(
        source_url,
        timeout=DOWNLOAD_TIMEOUT,
        headers={"User-Agent": "SvitPC-ListingThumb/1.0"},
        stream=True,
    )
    response.raise_for_status()
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_content(chunk_size=65536):
        if not chunk:
            continue
        total += len(chunk)
        if total > MAX_BYTES:
            raise ValueError("Image too large")
        chunks.append(chunk)
    return _resize_to_webp(b"".join(chunks), size=size)


def ensure_listing_webp(product) -> Path | None:
    """Return cached WebP path, generating it when missing."""
    source_key = listing_source_key(product)
    if not source_key:
        return None

    path = listing_cache_path(product.pk, source_key)
    if path.is_file():
        return path

    if product.image:
        with product.image.open("rb") as handle:
            data = _resize_to_webp(handle.read())
    else:
        source_url = resolve_product_image_url(product)
        if not source_url:
            return None
        data = fetch_listing_webp(source_url)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path
