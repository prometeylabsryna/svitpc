"""Detect Russian catalog labels and normalize them to Ukrainian (with deduplication)."""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, TypeVar

from django.db import transaction
from django.db.models import Count, Model, QuerySet

from apps.catalog.content_translation import clear_en_if_uk_changed, translate_texts

logger = logging.getLogger(__name__)

RU_CHARS = frozenset("ыэъё")
# Endings typical for Russian, not shared Ukrainian genitive (-ого is both languages).
_RU_ENDING = re.compile(
    r"(?<![іїєґІЇЄҐ])(ия|ие|ый|ой|ость|ная|ное|ные)(?![а-яіїєґ])",
    re.IGNORECASE,
)
# Distinctive Russian roots / spellings (е vs є, акумулятор vs аккумулятор, …).
_RU_STEM = re.compile(
    r"(?i)"
    r"(производител\w*|цвет\w*|мощност\w*|размер\w*|гаранти\w*|количеств\w*|"
    r"объем\w*|\bвес\w*|материал\w*|особенност\w*|управлен\w*|скорост\w*|"
    r"аккумулятор\w*|морозил\w*|покрыти\w*|нагрев\w*|функци\w*|внутренн\w*|"
    r"охлажд\w*|объедин\w*|подключ\w*|совместим\w*)",
)
_CYRILLIC = re.compile(r"[а-яА-ЯіїєґІЇЄҐ]")

GLOSSARY_RU_UK: dict[str, str] = {
    "Производитель": "Виробник",
    "Производитель аккумулятора": "Виробник акумулятора",
    "Производитель чипсета": "Виробник чіпсета",
    "Страна производитель": "Країна виробник",
    "Страна-производитель": "Країна-виробник",
    "Страна-производитель товара": "Країна-виробник товару",
    "Вес": "Вага",
    "Аккумулятор": "Акумулятор",
    "Страна производства": "Країна виробництва",
    "Цвет": "Колір",
    "Цвет текста": "Колір тексту",
    "Гарантия, мес": "Гарантія, міс",
    "Гарантия": "Гарантія",
    "Мощность": "Потужність",
    "Тип продукта": "Тип продукту",
    "Размер": "Розмір",
    "Вес": "Вага",
    "Объем": "Об'єм",
    "Объем чаши": "Об'єм чаші",
    "Длина": "Довжина",
    "Ширина": "Ширина",
    "Высота": "Висота",
    "Глубина": "Глибина",
    "Материал": "Матеріал",
    "Особенности": "Особливості",
    "Управление": "Керування",
    "Скорость": "Швидкість",
    "Память": "Пам'ять",
    "Диагональ": "Діагональ",
    "Интерфейс": "Інтерфейс",
    "Комплектация": "Комплектація",
    "Назначение": "Призначення",
    "Характеристики": "Характеристики",
    "Также ищут": "Також шукають",
    "Количество": "Кількість",
    "Количество LAN  портов": "Кількість LAN-портів",
    "Количество LAN портов": "Кількість LAN-портів",
    "Количество USB портов": "Кількість USB-портів",
    "Серия": "Серія",
    "Язык меню": "Мова меню",
    "Функции": "Функції",
    "Тип нагрева": "Тип нагріву",
    "Тип внутреннего покрытия": "Тип внутрішнього покриття",
    "Полезный объем морозильной камеры": "Корисний об'єм морозильної камери",
    "Устройства ввода в комплекте": "Пристрої введення в комплекті",
    "Мощность и тип конфорок": "Потужність і тип конфорок",
    "Класс телефона": "Клас телефону",
    "Фокусное расстояние min, мм": "Фокусна відстань min, мм",
    "Модель корпуса": "Модель корпусу",
    "Производительность охлаждения": "Продуктивність охолодження",
    "Длина излива": "Довжина виливу",
    "Для создания": "Для створення",
    "Тип камеры сгорания": "Тип камери згоряння",
    "Обметывание петли": "Обметування петлі",
    "Месячный объем печати": "Місячний обсяг друку",
}


def needs_ru_to_uk(text: str) -> bool:
    """True when *text* is likely Russian catalog copy (not UK / Latin-only)."""
    t = (text or "").strip()
    if not t:
        return False
    if t in GLOSSARY_RU_UK and GLOSSARY_RU_UK[t] != t:
        return True
    if not _CYRILLIC.search(t):
        return False
    if any(c in "іїєґІЇЄҐ" for c in t):
        return False
    low = t.lower()
    if any(c in RU_CHARS for c in low):
        return True
    if _RU_ENDING.search(t):
        return True
    return bool(_RU_STEM.search(t))


_RUNTIME_CACHE: dict[str, str] = {}


def localize_ru_to_uk(
    text: str,
    *,
    cache: dict[str, str] | None = None,
    allow_api: bool = True,
) -> str:
    """Return Ukrainian text when *text* looks Russian; otherwise unchanged."""
    t = (text or "").strip()
    if not t or not needs_ru_to_uk(t):
        return t
    store = cache if cache is not None else _RUNTIME_CACHE
    if t in store:
        return store[t]
    if t in GLOSSARY_RU_UK:
        uk = GLOSSARY_RU_UK[t]
    elif allow_api:
        uk = translate_texts([t], src="ru", tgt="uk")[0].strip() or t
    else:
        return t
    store[t] = uk
    return uk


def build_ru_to_uk_map(texts: list[str], *, backend: str = "google") -> dict[str, str]:
    """Translate unique Russian strings in batches."""
    unique = sorted({t.strip() for t in texts if t and needs_ru_to_uk(t)})
    mapping: dict[str, str] = dict(GLOSSARY_RU_UK)
    todo = [t for t in unique if t not in mapping]
    batch_size = 40
    for start in range(0, len(todo), batch_size):
        chunk = todo[start : start + batch_size]
        translated = translate_texts(chunk, backend=backend, src="ru", tgt="uk")
        for src, dst in zip(chunk, translated, strict=True):
            mapping[src] = (dst or src).strip() or src
    return mapping


def _translation_save_fields(obj: Model, field: str) -> list[str]:
    fields = [field]
    if hasattr(obj, f"{field}_uk"):
        fields.append(f"{field}_uk")
    if hasattr(obj, f"{field}_en"):
        fields.append(f"{field}_en")
    return fields


def _set_uk_field(obj: Model, field: str, new_value: str) -> list[str]:
    clear_en_if_uk_changed(obj, field, new_value)
    setattr(obj, field, new_value)
    uk_field = f"{field}_uk"
    if hasattr(obj, uk_field):
        setattr(obj, uk_field, new_value)
    return _translation_save_fields(obj, field)


def _pick_canonical_pk(
    model: type[Model],
    pks: list[int],
    link_model: type[Model],
    fk_name: str,
) -> int:
    fk_col = fk_name if fk_name.endswith("_id") else f"{fk_name}_id"
    counts = (
        link_model.objects.filter(**{f"{fk_col}__in": pks})
        .values(fk_col)
        .annotate(_n=Count("pk"))
        .order_by("-_n", fk_col)
    )
    best = counts.first()
    if best:
        return int(best[fk_col])
    return min(pks)


def merge_scoped_records(
    model: type[Model],
    *,
    keep_pk: int,
    drop_pk: int,
    link_model: type[Model],
    fk_name: str,
) -> None:
    """Re-point link rows from *drop_pk* to *keep_pk*; delete *drop_pk*."""
    if keep_pk == drop_pk:
        return
    fk_col = fk_name if fk_name.endswith("_id") else f"{fk_name}_id"
    for row in link_model.objects.filter(**{fk_col: drop_pk}):
        conflict = link_model.objects.filter(
            product_id=row.product_id,
            **{fk_col: keep_pk},
        ).exists()
        if conflict:
            row.delete()
        else:
            setattr(row, fk_col, keep_pk)
            row.save(update_fields=[fk_col])
    model.objects.filter(pk=drop_pk).delete()


M = TypeVar("M", bound=Model)


@dataclass(frozen=True)
class ScopedRenameJob:
    label: str
    model: type[M]
    scope_field: str
    link_model: type[Model]
    link_fk: str
    name_field: str = "name"


def apply_scoped_renames(
    job: ScopedRenameJob,
    *,
    backend: str = "google",
    limit: int = 0,
    dry_run: bool = False,
    on_progress: Callable[[str, int, int], None] | None = None,
) -> tuple[int, int]:
    """Rename + merge duplicates within each (scope, target_name)."""
    model = job.model
    name_field = job.name_field
    scope_field = job.scope_field

    qs: QuerySet = model.objects.all().order_by("pk")
    if limit:
        qs = qs[:limit]

    rows = list(qs.only("pk", scope_field, name_field))
    russian = [r for r in rows if needs_ru_to_uk(getattr(r, name_field) or "")]
    if not russian:
        return 0, 0

    name_map = build_ru_to_uk_map([getattr(r, name_field) or "" for r in russian], backend=backend)
    planned: dict[int, str] = {}
    for row in russian:
        old = getattr(row, name_field) or ""
        new = name_map.get(old, old)
        if new != old:
            planned[row.pk] = new

    by_target: dict[tuple[int, str], set[int]] = defaultdict(set)
    for pk, new_name in planned.items():
        scope = model.objects.filter(pk=pk).values_list(scope_field, flat=True).first()
        by_target[(scope, new_name)].add(pk)

    for (scope, target) in list(by_target.keys()):
        existing = model.objects.filter(**{scope_field: scope, name_field: target}).values_list("pk", flat=True)
        by_target[(scope, target)].update(existing)

    renamed = 0
    merged = 0
    total = len(planned)

    with transaction.atomic():
        step = 0
        for (_scope, target_name), pks in by_target.items():
            pks_sorted = sorted(pks)
            keep_pk = _pick_canonical_pk(model, pks_sorted, job.link_model, job.link_fk)
            for drop_pk in pks_sorted:
                if drop_pk == keep_pk:
                    continue
                if dry_run:
                    merged += 1
                    continue
                merge_scoped_records(
                    model,
                    keep_pk=keep_pk,
                    drop_pk=drop_pk,
                    link_model=job.link_model,
                    fk_name=job.link_fk,
                )
                merged += 1

            keeper = model.objects.filter(pk=keep_pk).first()
            if keeper and (getattr(keeper, name_field) or "") != target_name:
                if dry_run:
                    renamed += 1
                else:
                    _set_uk_field(keeper, name_field, target_name)
                    keeper.save(update_fields=_translation_save_fields(keeper, name_field))
                    renamed += 1
            for pk in planned:
                if pk in pks_sorted and pk != keep_pk:
                    step += 1
            if keeper and keeper.pk in planned:
                step += 1
                if on_progress:
                    on_progress(job.label, min(step, total), total)

    logger.info("%s: renamed=%d merged=%d dry_run=%s", job.label, renamed, merged, dry_run)
    return renamed, merged


def apply_simple_renames(
    model: type[Model],
    *,
    label: str,
    name_field: str = "name",
    backend: str = "google",
    limit: int = 0,
    dry_run: bool = False,
) -> int:
    """Rename rows without scope merge (groups, attribute values)."""
    qs: QuerySet = model.objects.all().order_by("pk")
    if limit:
        qs = qs[:limit]
    rows = list(qs.only("pk", name_field))
    to_fix = [r for r in rows if needs_ru_to_uk(getattr(r, name_field) or "")]
    if not to_fix:
        return 0

    name_map = build_ru_to_uk_map([getattr(r, name_field) or "" for r in to_fix], backend=backend)
    updated = 0

    with transaction.atomic():
        for row in to_fix:
            old = getattr(row, name_field) or ""
            new = name_map.get(old, old)
            if new == old:
                continue
            if dry_run:
                updated += 1
                continue
            obj = model.objects.get(pk=row.pk)
            _set_uk_field(obj, name_field, new)
            obj.save(update_fields=_translation_save_fields(obj, name_field))
            updated += 1

    logger.info("%s: updated=%d dry_run=%s", label, updated, dry_run)
    return updated


def run_ru_localization(
    *,
    what: str = "all",
    backend: str = "google",
    limit: int = 0,
    dry_run: bool = False,
    on_progress: Callable[[str, int, int], None] | None = None,
) -> dict[str, int]:
    from apps.catalog.models import Attribute, AttributeGroup, Filter, FilterGroup, ProductAttribute, ProductFilter

    stats: dict[str, int] = {"renamed": 0, "merged": 0}

    steps: list[tuple[str, Callable[[], tuple[int, int] | int]]] = []

    if what in ("all", "attributegroups"):
        steps.append((
            "attributegroups",
            lambda: apply_simple_renames(
                AttributeGroup, label="AttributeGroups", backend=backend, limit=limit, dry_run=dry_run,
            ),
        ))
    if what in ("all", "filtergroups"):
        steps.append((
            "filtergroups",
            lambda: apply_simple_renames(
                FilterGroup, label="FilterGroups", backend=backend, limit=limit, dry_run=dry_run,
            ),
        ))
    if what in ("all", "attributes"):
        job = ScopedRenameJob(
            "Attributes",
            Attribute,
            "group_id",
            ProductAttribute,
            "attribute_id",
        )
        steps.append((
            "attributes",
            lambda: apply_scoped_renames(
                job, backend=backend, limit=limit, dry_run=dry_run, on_progress=on_progress,
            ),
        ))
    if what in ("all", "filters"):
        job = ScopedRenameJob("Filters", Filter, "group_id", ProductFilter, "filter_id")
        steps.append((
            "filters",
            lambda: apply_scoped_renames(
                job, backend=backend, limit=limit, dry_run=dry_run, on_progress=on_progress,
            ),
        ))
    if what in ("all", "productattrs"):
        steps.append((
            "productattrs",
            lambda: apply_simple_renames(
                ProductAttribute,
                label="ProductAttribute values",
                name_field="value",
                backend=backend,
                limit=limit,
                dry_run=dry_run,
            ),
        ))

    for _key, fn in steps:
        result = fn()
        if isinstance(result, tuple):
            r, m = result
            stats["renamed"] += r
            stats["merged"] += m
        else:
            stats["renamed"] += result

    return stats
