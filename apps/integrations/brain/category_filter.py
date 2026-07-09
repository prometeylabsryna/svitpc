"""Brain catalog whitelist — only sync products from allowed top-level category trees."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import TYPE_CHECKING

from django.conf import settings
from django.utils.text import slugify

if TYPE_CHECKING:
    from apps.catalog.models import Category, Product
    from apps.integrations.brain.client import BrainAPIClient

logger = logging.getLogger(__name__)

# Top-level Brain/OpenCart slugs (Kancmaster is a separate source — not listed here).
DEFAULT_BRAIN_ALLOWED_CATEGORY_SLUGS: tuple[str, ...] = (
    "ноутбуки-планшети",
    "компютери-аксесуари",
    "комплектуючі-до-пк",
    "тб-аудіо-відео-фото",
    "периферія-оргтехніка",
    "мережеве-обладнання",
    "канцтовари",
    "товари-для-школи",
)


def get_brain_allowed_category_slugs() -> tuple[str, ...]:
    """Return configured whitelist of local top-level category slugs."""
    raw = getattr(settings, "BRAIN_ALLOWED_CATEGORY_SLUGS", None)
    if not raw:
        return DEFAULT_BRAIN_ALLOWED_CATEGORY_SLUGS
    if isinstance(raw, str):
        slugs = tuple(s.strip() for s in raw.split(",") if s.strip())
        return slugs or DEFAULT_BRAIN_ALLOWED_CATEGORY_SLUGS
    return tuple(raw)


def _brain_category_slug(name: str, category_id: int) -> str:
    from apps.catalog.ru_localization import localize_ru_to_uk

    localized = localize_ru_to_uk(name.strip())
    return slugify(localized, allow_unicode=True) or f"brain-cat-{category_id}"


def _brain_top_categories(all_brain_cats: list[dict]) -> list[dict]:
    return [c for c in all_brain_cats if c.get("parentID") == 1 and c.get("realcat", 0) == 0]


def allowed_brain_top_categories(
    client: BrainAPIClient,
    *,
    lang: str = "ua",
) -> list[dict]:
    """Brain API top-level categories that match the configured slug whitelist."""
    allowed_slugs = set(get_brain_allowed_category_slugs())
    all_brain_cats = client.get_all_categories(lang=lang)
    tops = _brain_top_categories(all_brain_cats)

    matched: dict[int, dict] = {}
    for bc in tops:
        cat_id = int(bc["categoryID"])
        slug = _brain_category_slug(bc.get("name") or "", cat_id)
        if slug in allowed_slugs:
            matched[cat_id] = bc

    # Fallback: map via existing local Category rows when Brain slug differs slightly.
    from apps.catalog.models import Category

    for local in Category.objects.filter(slug__in=allowed_slugs, is_active=True).only("pk", "slug", "name"):
        if any(
            _brain_category_slug(bc.get("name") or "", int(bc["categoryID"])) == local.slug
            for bc in matched.values()
        ):
            continue
        for bc in tops:
            cat_id = int(bc["categoryID"])
            if cat_id in matched:
                continue
            brain_name = (bc.get("name") or "").strip()
            if not brain_name:
                continue
            from apps.catalog.ru_localization import localize_ru_to_uk

            if localize_ru_to_uk(brain_name).casefold() == local.name.casefold():
                matched[cat_id] = bc

    resolved_slugs = {
        _brain_category_slug(bc.get("name") or "", int(bc["categoryID"])) for bc in matched.values()
    }
    missing = allowed_slugs - resolved_slugs
    if missing:
        logger.warning(
            "Brain category whitelist: no top-level Brain category matched slugs %s",
            sorted(missing),
        )

    return list(matched.values())


def build_allowed_brain_category_id_set(
    client: BrainAPIClient,
    *,
    lang: str = "ua",
) -> frozenset[int]:
    """All Brain categoryIDs in allowed top-level subtrees (tops + descendants)."""
    allowed_tops = allowed_brain_top_categories(client, lang=lang)
    if not allowed_tops:
        return frozenset()

    top_ids = {int(c["categoryID"]) for c in allowed_tops}
    all_brain_cats = client.get_all_categories(lang=lang)
    children_by_parent: dict[int, list[int]] = defaultdict(list)
    for bc in all_brain_cats:
        if bc.get("realcat", 0) > 0:
            continue
        parent_id = int(bc.get("parentID") or 0)
        children_by_parent[parent_id].append(int(bc["categoryID"]))

    allowed: set[int] = set()
    stack = list(top_ids)
    while stack:
        cat_id = stack.pop()
        if cat_id in allowed:
            continue
        allowed.add(cat_id)
        stack.extend(children_by_parent.get(cat_id, []))
    return frozenset(allowed)


def is_brain_category_allowed(
    category_id: int | str | None,
    allowed_ids: frozenset[int],
) -> bool:
    if not category_id or not allowed_ids:
        return False
    try:
        return int(category_id) in allowed_ids
    except (TypeError, ValueError):
        return False


def is_brain_detail_allowed(detail: dict, allowed_ids: frozenset[int]) -> bool:
    """True when Brain product payload categoryID is inside the whitelist subtree."""
    if not detail or not allowed_ids:
        return False
    return is_brain_category_allowed(detail.get("categoryID"), allowed_ids)


def allowed_local_category_subtree_pks() -> frozenset[int]:
    """Local Category PKs for all descendants of whitelisted top-level slugs."""
    from apps.catalog.models import Category

    pks: set[int] = set()
    for slug in get_brain_allowed_category_slugs():
        cat = Category.objects.filter(slug=slug, is_active=True).only("pk", "tree_id", "lft", "rght").first()
        if not cat:
            continue
        pks.update(
            cat.get_descendants(include_self=True).values_list("pk", flat=True),
        )
    return frozenset(pks)


def brain_product_in_allowed_local_categories(product: Product) -> bool:
    """True when a local Product is linked to at least one allowed category subtree."""
    subtree = allowed_local_category_subtree_pks()
    if not subtree:
        return False
    return product.categories.filter(pk__in=subtree).exists()


def brain_product_allowed_for_sync(
    product: Product | None,
    detail: dict | None,
    allowed_brain_ids: frozenset[int],
) -> bool:
    """Gate incremental Brain sync: allow by API category or local category link."""
    if detail and is_brain_detail_allowed(detail, allowed_brain_ids):
        return True
    if product is not None and brain_product_in_allowed_local_categories(product):
        return True
    return False


def filter_brain_products_queryset(qs):
    """Restrict a Product queryset to Brain items in allowed local category subtrees."""
    subtree = allowed_local_category_subtree_pks()
    if not subtree:
        return qs.none()
    return qs.filter(categories__in=subtree).distinct()


def brain_category_allowed_for_tree_sync(
    brain_category_id: int,
    allowed_ids: frozenset[int],
) -> bool:
    return brain_category_id in allowed_ids


def catalog_products_to_keep_queryset(qs=None):
    """Products that stay on the site: all Kancmaster + items in allowed category subtrees."""
    from django.db.models import Q

    from apps.catalog.models import Product

    if qs is None:
        qs = Product.objects.all()
    subtree = allowed_local_category_subtree_pks()
    if not subtree:
        return qs.filter(source=Product.SOURCE_KANCMASTER)
    return qs.filter(
        Q(source=Product.SOURCE_KANCMASTER) | Q(categories__in=subtree),
    ).distinct()


def catalog_products_to_prune_queryset(qs=None):
    """Products safe to delete: not Kancmaster and not linked to any allowed subtree."""
    from apps.catalog.models import Product

    if qs is None:
        qs = Product.objects.all()
    return qs.exclude(pk__in=catalog_products_to_keep_queryset().values("pk")).distinct()

