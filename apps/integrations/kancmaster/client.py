"""Kancmaster XML import client."""

from __future__ import annotations

import logging
from io import BytesIO

import httpx
from defusedxml import ElementTree as ET
from django.conf import settings

logger = logging.getLogger(__name__)


class KancmasterXMLClient:
    def __init__(self) -> None:
        self._url = settings.KANCMASTER_XML_URL
        self._login = settings.KANCMASTER_LOGIN
        self._password = settings.KANCMASTER_PASSWORD

    def fetch_xml(self) -> bytes | None:
        # Send login/password only when configured; Kancmaster may instead provide
        # a unique per-customer URL with the token embedded in the path.
        params: dict[str, str] = {}
        if self._login:
            params["login"] = self._login
        if self._password:
            params["password"] = self._password
        try:
            resp = httpx.get(
                self._url,
                params=params or None,
                timeout=120,
                follow_redirects=True,
            )
            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After", "unknown")
                logger.warning(
                    "Kancmaster XML rate-limited (429); Retry-After: %s. Skipping sync.",
                    retry_after,
                )
                return None
            resp.raise_for_status()
            return resp.content
        except httpx.HTTPStatusError as exc:
            logger.error("Kancmaster XML HTTP error %s: %s", exc.response.status_code, exc)
            return None
        except Exception as exc:
            logger.error("Kancmaster XML fetch error: %s", exc)
            return None

    def parse_products(self, xml_bytes: bytes) -> list[dict]:
        products = []
        try:
            tree = ET.parse(BytesIO(xml_bytes))
            root = tree.getroot()
            for item in root.iter("item"):
                # Collect all <picture> elements; normalise to HTTPS to avoid mixed-content blocks.
                def _to_https(u: str) -> str:
                    u = u.strip()
                    if u.startswith("//"):
                        return "https:" + u
                    if u.startswith("http://"):
                        return "https" + u[4:]
                    return u

                image_urls = [_to_https(el.text) for el in item.findall("picture") if el.text and el.text.strip()]
                products.append({
                    "id": item.findtext("id", ""),
                    "name": item.findtext("name", ""),
                    "price": item.findtext("price", "0"),
                    "quantity": item.findtext("quantity", "0"),
                    "category": item.findtext("category", ""),
                    "brand": item.findtext("vendor", ""),
                    "sku": item.findtext("article", ""),
                    "description": item.findtext("description", ""),
                    "image_url": image_urls[0] if image_urls else "",
                    "image_urls": image_urls,
                })
        except Exception as exc:
            logger.error("Kancmaster XML parse error: %s", exc)
        return products
