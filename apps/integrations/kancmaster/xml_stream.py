"""Low-memory streaming parse for large Kancmaster YML feeds."""

from __future__ import annotations

from collections.abc import Iterator
from io import BytesIO
from pathlib import Path
from xml.etree.ElementTree import Element

from defusedxml import ElementTree as ET

from .yml_parse import parse_item_element


def _local_tag(el: Element) -> str:
    return el.tag.rsplit("}", 1)[-1]


def _iterparse_end(source: bytes | Path):
    if isinstance(source, Path):
        return ET.iterparse(str(source), events=("end",))
    return ET.iterparse(BytesIO(source), events=("end",))


def build_category_map(source: bytes | Path) -> dict[str, str]:
    category_map: dict[str, str] = {}
    for _event, el in _iterparse_end(source):
        if _local_tag(el) == "category":
            cat_id = (el.get("id") or "").strip()
            name = (el.text or "").strip()
            if cat_id and name:
                category_map[cat_id] = name
            el.clear()
    return category_map


def feed_uses_items(source: bytes | Path) -> bool:
    for _event, el in _iterparse_end(source):
        if _local_tag(el) == "item":
            return True
    return False


def iter_products(
    source: bytes | Path,
    *,
    category_map: dict[str, str] | None = None,
) -> Iterator[dict]:
    """Yield one parsed product dict at a time; clears each product node after parse."""
    category_map = category_map if category_map is not None else build_category_map(source)
    use_items = feed_uses_items(source)
    target_tag = "item" if use_items else "offer"
    is_offer = target_tag == "offer"

    for _event, el in _iterparse_end(source):
        if _local_tag(el) != target_tag:
            continue
        parsed = parse_item_element(el, is_offer=is_offer, category_map=category_map)
        el.clear()
        if parsed["id"] and parsed["name"]:
            yield parsed
