"""Kancmaster XML import client."""

from __future__ import annotations

import logging
from io import BytesIO

import httpx
from defusedxml import ElementTree as ET
from django.conf import settings

logger = logging.getLogger(__name__)


def _to_https(url: str) -> str:
    u = url.strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http://"):
        return "https" + u[4:]
    return u


def _element_text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    text = (el.text or "").strip()
    if text:
        return text
    return "".join(el.itertext()).strip()


_DESC_PARAM_NAMES = frozenset(
    {
        "опис",
        "описание",
        "description",
        "аннотація",
        "аннотация",
        "annotation",
    }
)


def _parse_params(el: ET.Element) -> list[dict[str, str]]:
    params: list[dict[str, str]] = []
    for param_el in el.findall("param"):
        name = (param_el.get("name") or "").strip()
        value = _element_text(param_el)
        if not name or not value:
            continue
        unit = (param_el.get("unit") or "").strip()
        if unit:
            value = f"{value} {unit}"
        params.append({"name": name, "value": value})
    return params


def _description_from_params(params: list[dict[str, str]]) -> tuple[str, list[dict[str, str]]]:
    """Use a param as description when the <description> tag is empty."""
    for index, row in enumerate(params):
        if row["name"].strip().lower() in _DESC_PARAM_NAMES:
            remaining = params[:index] + params[index + 1 :]
            return row["value"], remaining
    return "", params


def _parse_description(el: ET.Element) -> str:
    return _element_text(el.find("description"))


def _picture_urls(el: ET.Element) -> list[str]:
    urls: list[str] = []
    for pic in el.findall("picture"):
        if pic.text and pic.text.strip():
            urls.append(_to_https(pic.text))
    return urls


def _resolve_quantity(el: ET.Element, *, is_offer: bool) -> str:
    qty_text = el.findtext("quantity")
    if qty_text is not None and str(qty_text).strip() != "":
        return str(qty_text).strip()
    if is_offer:
        available = (el.get("available") or "true").strip().lower()
        return "0" if available in ("false", "0", "no") else "1"
    return "0"


def _parse_item_element(
    el: ET.Element,
    *,
    is_offer: bool,
    category_map: dict[str, str],
) -> dict[str, str | list[str] | list[dict[str, str]]]:
    ext_id = (el.get("id") if is_offer else None) or el.findtext("id", "")
    ext_id = (ext_id or "").strip()

    cat_name = (el.findtext("category") or "").strip()
    if not cat_name:
        cat_id = (el.findtext("categoryId") or "").strip()
        if cat_id:
            cat_name = category_map.get(cat_id, "")

    image_urls = _picture_urls(el)
    raw_params = _parse_params(el)
    description = _parse_description(el)
    if not description:
        description, raw_params = _description_from_params(raw_params)

    # Kancmaster YML fields:
    #   <price>      — wholesale/purchase price (закупівельна)
    #   <msrp>       — recommended retail price (РРЦ)
    #   <pricetov>   — price for ТОВ (same as <price> usually)
    #   <pricefop>   — price for ФОП (slightly higher than <price>)
    msrp = (el.findtext("msrp") or "").strip()

    return {
        "id": ext_id,
        "name": (el.findtext("name") or "").strip(),
        "price": (el.findtext("price") or "0").strip(),
        "msrp": msrp,
        "quantity": _resolve_quantity(el, is_offer=is_offer),
        "category": cat_name,
        "brand": (el.findtext("vendor") or "").strip(),
        "sku": ((el.findtext("article") or el.findtext("barcode") or "")).strip(),
        "description": description,
        "params": raw_params,
        "image_url": image_urls[0] if image_urls else "",
        "image_urls": image_urls,
    }


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
                timeout=300,
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
        products: list[dict] = []
        try:
            tree = ET.parse(BytesIO(xml_bytes))
            root = tree.getroot()

            category_map: dict[str, str] = {}
            for cat_el in root.iter("category"):
                cat_id = (cat_el.get("id") or "").strip()
                name = (cat_el.text or "").strip()
                if cat_id and name:
                    category_map[cat_id] = name

            items = list(root.iter("item"))
            offers = list(root.iter("offer")) if not items else []
            elements: list[tuple[ET.Element, bool]] = [(el, False) for el in items]
            elements.extend((el, True) for el in offers)

            for el, is_offer in elements:
                parsed = _parse_item_element(el, is_offer=is_offer, category_map=category_map)
                if parsed["id"] and parsed["name"]:
                    products.append(parsed)
        except Exception as exc:
            logger.error("Kancmaster XML parse error: %s", exc)
        return products
