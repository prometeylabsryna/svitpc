"""Map Brain product options / attributes to catalog Filter facets (CPU, RAM, etc.)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from django.db import transaction

from apps.catalog.ru_localization import localize_ru_to_uk

if TYPE_CHECKING:
    from apps.catalog.models import Product

# Canonical facet group → (sort_order, option-name needles).
SPEC_FILTER_GROUPS: tuple[tuple[str, int, tuple[str, ...]], ...] = (
    ("Діагональ", 10, ("діагонал", "diagonal", "екран", "display")),
    ("Процесор", 20, ("процесор", "processor", "cpu", "центральний проц")),
    ("Оперативна пам'ять", 30, ("оперативн", "озу", " ram", "ram ")),
    ("Відеокарта", 40, ("відеокарт", "видеокарт", "gpu", "графічн", "graphics")),
    ("SSD", 50, ("ssd", "твердотіл", "накопичувач", "накопичувача")),
    ("Колір", 60, ("колір", "цвет", "color", "colour", "корпусу")),
)

_SPEC_GROUP_NAMES = frozenset(name for name, _, _ in SPEC_FILTER_GROUPS)
_CANONICAL_BY_NEEDLE: list[tuple[str, str]] = []
for _canonical, _, _needles in SPEC_FILTER_GROUPS:
    for _needle in _needles:
        _CANONICAL_BY_NEEDLE.append((_needle, _canonical))

# Longer needles first so «оперативн» wins over bare «пам».
_CANONICAL_BY_NEEDLE.sort(key=lambda pair: len(pair[0]), reverse=True)

_GROUP_SORT = {name: order for name, order, _ in SPEC_FILTER_GROUPS}
_VALUE_WS = re.compile(r"\s+")


def normalize_spec_label(text: str) -> str:
    return _VALUE_WS.sub(" ", (text or "").strip())


def resolve_spec_group(option_name: str) -> str | None:
    """Return canonical filter group name for a Brain/OpenCart option label."""
    haystack = normalize_spec_label(localize_ru_to_uk(option_name)).casefold()
    if not haystack:
        return None
    for needle, canonical in _CANONICAL_BY_NEEDLE:
        if needle in haystack:
            return canonical
    return None


def _option_pairs(options: list[dict]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for opt in options:
        name = normalize_spec_label(
            localize_ru_to_uk((opt.get("OptionName") or opt.get("FilterName") or "").strip())
        )
        value = normalize_spec_label(
            localize_ru_to_uk((opt.get("ValueName") or "").strip())
        )
        if name and value:
            pairs.append((name, value))
    return pairs


def _get_or_create_spec_filter(group_name: str, value_name: str):
    from apps.catalog.models import Filter, FilterGroup

    group, _ = FilterGroup.objects.get_or_create(
        name=group_name,
        defaults={"sort_order": _GROUP_SORT.get(group_name, 100), "is_brand": False},
    )
    if group.sort_order != _GROUP_SORT.get(group_name, group.sort_order):
        FilterGroup.objects.filter(pk=group.pk).update(sort_order=_GROUP_SORT[group_name])

    filt, _ = Filter.objects.get_or_create(
        group=group,
        name=value_name,
        defaults={"sort_order": 0},
    )
    return filt


def _spec_filter_group_ids() -> list[int]:
    from apps.catalog.models import FilterGroup

    return list(FilterGroup.objects.filter(name__in=_SPEC_GROUP_NAMES).values_list("pk", flat=True))


def sync_spec_filters_from_options(product: Product, options: list[dict]) -> int:
    """Create ProductFilter rows for whitelisted specs. Returns links written."""
    from apps.catalog.models import ProductFilter

    pairs = _option_pairs(options)
    if not pairs:
        return 0

    target_filter_ids: set[int] = set()
    for option_name, value_name in pairs:
        group_name = resolve_spec_group(option_name)
        if not group_name:
            continue
        filt = _get_or_create_spec_filter(group_name, value_name)
        target_filter_ids.add(filt.pk)

    if not target_filter_ids:
        return 0

    group_ids = _spec_filter_group_ids()
    with transaction.atomic():
        ProductFilter.objects.filter(product=product, filter__group_id__in=group_ids).exclude(
            filter_id__in=target_filter_ids,
        ).delete()
        written = 0
        for filter_id in target_filter_ids:
            _, created = ProductFilter.objects.get_or_create(
                product=product,
                filter_id=filter_id,
            )
            if created:
                written += 1
    return written


def sync_spec_filters_from_attributes(product: Product) -> int:
    """Backfill spec filters from stored ProductAttribute rows."""
    options = [
        {"OptionName": row.attribute.name, "ValueName": row.value}
        for row in product.attributes.select_related("attribute").only(
            "value",
            "attribute__name",
        )
    ]
    return sync_spec_filters_from_options(product, options)


def is_spec_filter_group_name(name: str) -> bool:
    return name in _SPEC_GROUP_NAMES
