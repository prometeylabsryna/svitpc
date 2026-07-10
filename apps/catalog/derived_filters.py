"""Derive shopper-facing facets (діагональ/CPU/RAM/відеокарта/SSD/колір) from ProductAttribute.

Brain і Kancmaster синки пишуть довільні характеристики у `ProductAttribute` (таблиця specs
на картці товару), але НЕ наповнюють `ProductFilter` (фасети сайдбару каталогу) — Brain API
не віддає стабільний `FilterID` у батчевому content-фіді, яким ми користуємось для синку, тож
покладатись на нього не можна. Натомість тут ми мапимо відомий набір назв характеристик на
`FilterGroup`, які вже імпортовані з OpenCart (назви нижче — точні збіги з існуючими рядками,
щоб `get_or_create` перевикористовував їх, а не створював дублікати груп).

Викликається:
  - одразу після запису ProductAttribute (Brain `content_sync.py`, Kancmaster `attributes.py`)
  - масово для вже синхронізованих товарів: `manage.py backfill_derived_filters`
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.catalog.models import Product


@dataclass(frozen=True)
class FacetRule:
    """Один канонічний фасет, що зіставляється з `Attribute.name` (casefolded, substring)."""

    group_name: str
    include: tuple[str, ...]
    exclude: tuple[str, ...] = ()


# group_name — точні назви існуючих `FilterGroup` (імпортовані з OpenCart) —
# перевикористовуються, нові групи не створюються.
FACET_RULES: tuple[FacetRule, ...] = (
    FacetRule(
        group_name="Діагональ",
        include=("діагональ",),
        exclude=("максимальна", "мінімальна", "максимальний", "мінімальний"),
    ),
    FacetRule(
        group_name="Серія процесора",
        include=("серія процесора", "модель процесора", "тип процесора"),
    ),
    FacetRule(
        group_name="Оперативна пам'ять",
        include=("об'єм оперативної пам'яті", "оперативна пам'ять"),
        exclude=("максимальн", "мінімальн", "кількість", "частота", "можливість", "слот", "роз'єм"),
    ),
    FacetRule(
        group_name="Модель відеокарти",
        include=("модель відеокарти", "тип відеокарти"),
    ),
    FacetRule(
        group_name="Об'єм SSD",
        include=("ssd",),
        exclude=("інтерфейс",),
    ),
    FacetRule(
        group_name="Колір",
        include=("колір",),
        exclude=("колір тексту", "колір підсвітки"),
    ),
)


def facet_rule_for_attribute_name(name: str) -> FacetRule | None:
    """Правило фасету для сирого `Attribute.name`, або None, якщо характеристика не мапиться."""
    lowered = (name or "").casefold()
    if not lowered:
        return None
    for rule in FACET_RULES:
        if any(term in lowered for term in rule.exclude):
            continue
        if any(term in lowered for term in rule.include):
            return rule
    return None


def _get_or_create_single(model, defaults: dict | None = None, /, **lookup):
    """`get_or_create` без крашу на вже наявних дублікатах у БД.

    OpenCart-імпорт залишив у `FilterGroup`/`Filter` рядки-дублікати (однакові
    group+name, різні `pk`) — звичайний `get_or_create` кидає `MultipleObjectsReturned`
    у такому разі. Тут детермінований вибір (найменший pk) замість краху; дублікати
    прибирає окрема команда `dedupe_catalog_filters`.
    """
    existing = model.objects.filter(**lookup).order_by("pk").first()
    if existing is not None:
        return existing
    return model.objects.create(**lookup, **(defaults or {}))


def sync_derived_filters_for_product(product: "Product") -> int:
    """Створити ProductFilter для `product` з уже записаних ProductAttribute.

    Ідемпотентно — безпечно викликати повторно (наприклад, після кожного content-синку).
    Повертає кількість нових ProductFilter (наявні зв'язки не чіпаються).
    """
    from apps.catalog.models import Filter, FilterGroup, ProductFilter

    rows = list(product.attributes.select_related("attribute").only("value", "attribute__name"))
    if not rows:
        return 0

    created = 0
    seen_values: set[tuple[str, str]] = set()
    group_cache: dict[str, FilterGroup] = {}

    for row in rows:
        rule = facet_rule_for_attribute_name(row.attribute.name)
        if rule is None:
            continue
        value = row.value.strip()
        if not value:
            continue

        # Один товар — одне значення на фасетну групу (напр. одна діагональ у ноутбука).
        dedupe_key = (rule.group_name, value.casefold())
        if dedupe_key in seen_values:
            continue
        seen_values.add(dedupe_key)

        group = group_cache.get(rule.group_name)
        if group is None:
            group = _get_or_create_single(FilterGroup, name=rule.group_name)
            group_cache[rule.group_name] = group

        filt = _get_or_create_single(Filter, group=group, name=value)

        # unique_together=("product","filter") — тут дублікатів у БД немає, get_or_create безпечний.
        _, was_created = ProductFilter.objects.get_or_create(product=product, filter=filt)
        if was_created:
            created += 1

    return created
