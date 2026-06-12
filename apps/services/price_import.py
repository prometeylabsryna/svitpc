"""Parse and import service center price list from Excel."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.db import transaction
from django.utils.text import slugify

from .models import PriceItem, Service, ServiceCategory
from .i18n import (
    translate_category_name,
    translate_price_item_name,
    translate_service_description,
    translate_service_name,
)

DEFAULT_WORKBOOK = Path("ТЗ/Прейскурант цен .xlsx")
FOOTNOTE_CATEGORY = "* Вид робіт без урахування матеріалу"

CATEGORY_META: dict[str, dict[str, object]] = {
    "Види робіт загального призначення": {
        "service_name": "Загальні роботи",
        "description": (
            "Налаштування операційної системи, драйверів і програм, "
            "копіювання даних, активація Windows/Office, антивірусний контроль, виїзд майстра."
        ),
        "show_on_home": True,
        "sort_order": 1,
    },
    "Ноутбуки": {
        "service_name": "Ремонт ноутбуків",
        "description": (
            "Діагностика, заміна матриці, клавіатури, АКБ, технічне обслуговування, "
            "відновлення після залиття, BGA-пайка та інші роботи."
        ),
        "show_on_home": True,
        "sort_order": 2,
    },
    "Системні блоки": {
        "service_name": "Ремонт системних блоків",
        "description": "Діагностика, збирання ПК, заміна комплектуючих і технічне обслуговування.",
        "show_on_home": False,
        "sort_order": 3,
    },
    "Монітори": {
        "service_name": "Ремонт моніторів",
        "description": "Ремонт блоків живлення та заміна електронних плат моніторів.",
        "show_on_home": False,
        "sort_order": 4,
    },
    "Принтери та БФП": {
        "service_name": "Ремонт принтерів та БФП",
        "description": (
            "Діагностика, технічне обслуговування, заміна вузлів подачі паперу, "
            "прошивка, скидання лічильника абсорбера, заміна термоплівки."
        ),
        "show_on_home": True,
        "sort_order": 5,
    },
    "Картриджі": {
        "service_name": "Заправка та обслуговування картриджів",
        "description": "Заправка лазерних і струминних картриджів, чистка, перезбирання та заміна вузлів.",
        "show_on_home": True,
        "sort_order": 6,
    },
    "Локальні мережі": {
        "service_name": "Монтаж локальних мереж",
        "description": (
            "Монтаж кабелів, розеток, комутаторів і роутерів, налаштування MikroTik "
            "та мережевого принтера."
        ),
        "show_on_home": False,
        "sort_order": 7,
    },
}


@dataclass(frozen=True)
class ParsedPriceRow:
    name: str
    unit: str
    price: Decimal
    excludes_materials: bool
    sort_order: int


@dataclass(frozen=True)
class ParsedCategory:
    name: str
    sort_order: int
    items: tuple[ParsedPriceRow, ...]


def _cell_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _parse_price(value: object) -> Decimal | None:
    text = _cell_text(value).replace(",", ".")
    if not text:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def parse_price_workbook(path: Path) -> list[ParsedCategory]:
    try:
        import openpyxl
    except ImportError as exc:
        msg = "Для імпорту прейскуранта потрібен пакет openpyxl (uv sync)."
        raise ImportError(msg) from exc

    if not path.exists():
        msg = f"Файл прейскуранта не знайдено: {path}"
        raise FileNotFoundError(msg)

    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook["Лист1"]
        current_category: str | None = None
        category_sort = 0
        item_sort = 0
        buckets: dict[str, list[ParsedPriceRow]] = {}

        for row in sheet.iter_rows(values_only=True):
            col0 = row[0] if len(row) > 0 else None
            col2 = row[2] if len(row) > 2 else None
            col3 = row[3] if len(row) > 3 else None
            col4 = row[4] if len(row) > 4 else None

            label0 = _cell_text(col0)
            name = _cell_text(col2)
            unit = _cell_text(col3)
            price = _parse_price(col4)

            if label0 and label0 not in {"*", "Прейскурант Цін", FOOTNOTE_CATEGORY} and not name:
                current_category = label0
                category_sort += 1
                buckets.setdefault(current_category, [])
                item_sort = 0
                continue

            if not current_category or not name or price is None:
                continue

            item_sort += 1
            buckets[current_category].append(
                ParsedPriceRow(
                    name=name,
                    unit=unit,
                    price=price,
                    excludes_materials=label0 == "*",
                    sort_order=item_sort,
                )
            )

        return [
            ParsedCategory(
                name=category_name,
                sort_order=index,
                items=tuple(buckets[category_name]),
            )
            for index, category_name in enumerate(CATEGORY_META, start=1)
            if category_name in buckets
        ]
    finally:
        workbook.close()


@transaction.atomic
def import_service_prices(path: Path, *, replace: bool = True) -> dict[str, int]:
    parsed = parse_price_workbook(path)
    seen_price_ids: set[int] = set()
    stats = {"categories": 0, "services": 0, "price_items": 0}

    for category_data in parsed:
        meta = CATEGORY_META.get(category_data.name, {})
        category_slug = slugify(category_data.name, allow_unicode=True) or f"cat-{category_data.sort_order}"

        category, _created = ServiceCategory.objects.update_or_create(
            slug=category_slug,
            defaults={
                "name": category_data.name,
                "name_en": translate_category_name(category_data.name),
                "sort_order": int(meta.get("sort_order", category_data.sort_order)),
            },
        )
        stats["categories"] += 1

        service_name = str(meta.get("service_name", category_data.name))
        service_slug = slugify(service_name, allow_unicode=True) or f"{category_slug}-service"
        service, _created = Service.objects.update_or_create(
            slug=service_slug,
            defaults={
                "category": category,
                "name": service_name,
                "name_en": translate_service_name(category_data.name, service_name),
                "description": str(meta.get("description", "")),
                "description_en": translate_service_description(category_data.name),
                "is_active": True,
                "show_on_home": bool(meta.get("show_on_home", False)),
                "sort_order": 1,
            },
        )
        stats["services"] += 1

        imported_names: set[str] = set()
        for item in category_data.items:
            price_item, _created = PriceItem.objects.update_or_create(
                service=service,
                name=item.name,
                defaults={
                    "name_en": translate_price_item_name(item.name),
                    "unit": item.unit,
                    "price_from": item.price,
                    "price_to": None,
                    "price_text": "",
                    "excludes_materials": item.excludes_materials,
                    "sort_order": item.sort_order,
                },
            )
            seen_price_ids.add(price_item.pk)
            imported_names.add(item.name)
            stats["price_items"] += 1

        if replace:
            service.prices.exclude(name__in=imported_names).delete()

    if replace:
        PriceItem.objects.exclude(pk__in=seen_price_ids).delete()

    return stats
