"""Kancmaster XML import client."""

from __future__ import annotations

import logging
import tempfile
from collections.abc import Iterator
from pathlib import Path

import httpx
from django.conf import settings

from .xml_stream import build_category_map, iter_products as _iter_products

logger = logging.getLogger(__name__)


class KancmasterXMLClient:
    def __init__(self) -> None:
        self._url = settings.KANCMASTER_XML_URL
        self._login = settings.KANCMASTER_LOGIN
        self._password = settings.KANCMASTER_PASSWORD

    def fetch_xml(self) -> bytes | None:
        path = self.fetch_xml_path()
        if path is None:
            return None
        try:
            return path.read_bytes()
        finally:
            path.unlink(missing_ok=True)

    def fetch_xml_path(self) -> Path | None:
        """Download feed to a temp file (avoids holding ~50MB in Python heap)."""
        params: dict[str, str] = {}
        if self._login:
            params["login"] = self._login
        if self._password:
            params["password"] = self._password
        try:
            with httpx.stream(
                "GET",
                self._url,
                params=params or None,
                timeout=300,
                follow_redirects=True,
            ) as resp:
                if resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After", "unknown")
                    logger.warning(
                        "Kancmaster XML rate-limited (429); Retry-After: %s. Skipping sync.",
                        retry_after,
                    )
                    return None
                resp.raise_for_status()
                with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp:
                    for chunk in resp.iter_bytes(65536):
                        tmp.write(chunk)
                    return Path(tmp.name)
        except httpx.HTTPStatusError as exc:
            logger.error("Kancmaster XML HTTP error %s: %s", exc.response.status_code, exc)
            return None
        except Exception as exc:
            logger.error("Kancmaster XML fetch error: %s", exc)
            return None

    def iter_products(self, source: bytes | Path) -> Iterator[dict]:
        try:
            yield from _iter_products(source)
        except Exception as exc:
            logger.error("Kancmaster XML stream parse error: %s", exc)

    def parse_products(self, xml_bytes: bytes) -> list[dict]:
        try:
            category_map = build_category_map(xml_bytes)
            return list(_iter_products(xml_bytes, category_map=category_map))
        except Exception as exc:
            logger.error("Kancmaster XML parse error: %s", exc)
            return []
