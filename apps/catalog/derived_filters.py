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
    # Якщо задано — правило застосовується ЛИШЕ коли товар належить одній з цих
    # категорій (за slug). Потрібно для назв атрибутів, які Brain перевикористовує
    # з ІНШИМ значенням в інших категоріях (напр. "Об'єм пам'яті" — і модуль RAM
    # (16 ГБ), і картка пам'яті/флешка (256 ГБ) — без цього обмеження модуль
    # SD-картки помилково потрапив би у фасет "Оперативна пам'ять").
    category_slugs: tuple[str, ...] = ()


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
        # Brain віддає CPU по-різному залежно від категорії: у ноутбуках —
        # просто "Процесор" (повна назва моделі одним значенням), у окремих
        # процесорах — "Сімейство процесора" (напр. "AMD Ryzen 9"). Жодна з
        # них не збігалася зі старими вузькими include-термінами нижче, тож
        # фасет CPU НІКОЛИ не наповнювався — сайдбар мовчки лишався без нього
        # на всіх категоріях. "процесор" як самостійний підрядок ловить усі
        # варіанти; exclude відсікає технічні непридатні для фасету значення
        # (кількість ядер, покоління, тактові частоти, вбудована графіка).
        include=("серія процесора", "модель процесора", "тип процесора", "сімейство процесора", "процесор"),
        exclude=(
            "кількість ядер процесора",
            "покоління процесора",
            "тактова частота",
            "графічного процесора",
            # Материнські плати: "Підтримка процесорів" — речення-опис сумісності
            # ("AMD Socket AM5 for AMD Ryzen 7000 Series/ 8000 Series Desktop
            # Processors"), а не назва конкретної моделі CPU. Без цього excludе
            # такі речення потрапляли у фасет "Серія процесора" — довгий текст
            # ламав верстку списку чекбоксів (рядки наїжджали один на одного).
            "підтримка процесорів",
        ),
    ),
    FacetRule(
        group_name="Оперативна пам'ять",
        include=("об'єм оперативної пам'яті", "оперативна пам'ять"),
        exclude=("максимальн", "мінімальн", "кількість", "частота", "можливість", "слот", "роз'єм"),
    ),
    # Окремі модулі RAM (не ноутбук/ПК у зборі) Brain називає просто
    # "Об'єм пам'яті" — той самий рядок, що й обсяг SD-картки/флешки
    # ("Об'єм пам'яті" = 256 ГБ на картці пам'яті). Розрізняємо за категорією
    # товару, а не за назвою атрибута — інша назва тут не допоможе.
    FacetRule(
        group_name="Оперативна пам'ять",
        include=("об'єм пам'яті",),
        exclude=("кеш", "вбудованої", "gb"),
        category_slugs=(
            "модулі-памяті-для-компютера",
            "модулі-памяті-до-серверів",
            "модулі-памяті-до-ноутбуків",
        ),
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


def facet_rule_for_attribute_name(
    name: str,
    category_slugs: frozenset[str] | None = None,
) -> FacetRule | None:
    """Правило фасету для сирого `Attribute.name`, або None, якщо характеристика не мапиться.

    `category_slugs` — slug-и категорій товару; потрібні лише для правил з
    `category_slugs` (неоднозначні назви атрибутів). Без цього аргументу такі
    правила ніколи не спрацьовують (безпечний дефолт — краще не показати
    фасет, ніж показати його зі сторонніми значеннями).
    """
    lowered = (name or "").casefold()
    if not lowered:
        return None
    for rule in FACET_RULES:
        if any(term in lowered for term in rule.exclude):
            continue
        if not any(term in lowered for term in rule.include):
            continue
        if rule.category_slugs and not (category_slugs and category_slugs & set(rule.category_slugs)):
            continue
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
    """Синхронізувати ProductFilter для `product` з ProductAttribute.

    Ідемпотентно. Створює відсутні зв'язки і ВИДАЛЯЄ застарілі в керованих
    групах (Діагональ/CPU/RAM/…) — інакше після зміни атрибута (8→16 ГБ)
    товар лишався б під обома значеннями фасету.
    Повертає кількість нових ProductFilter.
    """
    from apps.catalog.models import Filter, FilterGroup, ProductFilter

    managed_names = {rule.group_name for rule in FACET_RULES}
    rows = list(product.attributes.select_related("attribute").only("value", "attribute__name"))
    # Лише для правил з category_slugs (неоднозначні назви атрибутів) — інакше
    # зайвий запит на кожен товар без потреби.
    needs_category = any(rule.category_slugs for rule in FACET_RULES)
    category_slugs = (
        frozenset(product.categories.values_list("slug", flat=True)) if needs_category else None
    )

    created = 0
    seen_values: set[tuple[str, str]] = set()
    group_cache: dict[str, FilterGroup] = {}
    desired_filter_ids: set[int] = set()

    for row in rows:
        rule = facet_rule_for_attribute_name(row.attribute.name, category_slugs)
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
        desired_filter_ids.add(filt.pk)

        # unique_together=("product","filter") — тут дублікатів у БД немає, get_or_create безпечний.
        _, was_created = ProductFilter.objects.get_or_create(product=product, filter=filt)
        if was_created:
            created += 1

    managed_group_ids = set(
        FilterGroup.objects.filter(name__in=managed_names).values_list("pk", flat=True),
    )
    managed_group_ids |= {g.pk for g in group_cache.values()}
    if managed_group_ids:
        ProductFilter.objects.filter(
            product=product,
            filter__group_id__in=managed_group_ids,
        ).exclude(filter_id__in=desired_filter_ids).delete()

    return created
