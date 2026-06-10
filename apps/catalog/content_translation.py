"""Batch translation of catalog content from Ukrainian to English."""

from __future__ import annotations

import json
import logging
import time
import urllib.parse
from dataclasses import dataclass
from typing import Callable, Sequence

import httpx
from django.db import transaction
from django.db.models import Model, Q, QuerySet

logger = logging.getLogger(__name__)

_GT_URL = "https://translate.googleapis.com/translate_a/single"
_GT_SEPARATOR = "\n\n||||\n\n"

_LLM_SYSTEM = (
    "You are a professional translator for an e-commerce computer and electronics store. "
    "Translate product catalog texts from Ukrainian or Russian to English. "
    "Keep brand names, model numbers, and technical abbreviations unchanged. "
    "Return ONLY a valid JSON array of strings — the same count as the input, in the same order. "
    "No extra text, no markdown, no commentary."
)


def missing_en_q(dst_field: str) -> Q:
    """Rows where the English field is unset or empty."""
    return Q(**{f"{dst_field}__isnull": True}) | Q(**{dst_field: ""})


def clear_en_if_uk_changed(obj: Model, field: str, new_uk: str) -> None:
    """Drop stale English when Ukrainian source text changes (re-translate later)."""
    uk_field = f"{field}_uk"
    en_field = f"{field}_en"
    if not hasattr(obj, uk_field):
        return
    old_uk = (getattr(obj, uk_field, None) or "").strip()
    if new_uk.strip() and new_uk.strip() != old_uk and hasattr(obj, en_field):
        setattr(obj, en_field, None)


def _google_translate_batch(texts: list[str], src: str = "uk", tgt: str = "en") -> list[str]:  # noqa: D401
    joined = _GT_SEPARATOR.join(t.strip() for t in texts)
    params = {
        "client": "gtx",
        "sl": src,
        "tl": tgt,
        "dt": "t",
        "q": joined,
    }
    resp = httpx.get(_GT_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    translated_full = "".join(part[0] for part in data[0] if part[0])
    parts = translated_full.split(_GT_SEPARATOR.strip())
    if len(parts) != len(texts):
        for sep in ("||||\n\n", "||||"):
            parts = translated_full.split(sep)
            if len(parts) == len(texts):
                break
        else:
            return [_google_translate_single(t, src, tgt) for t in texts]
    return [p.strip() for p in parts]


def _google_translate_single(text: str, src: str = "uk", tgt: str = "en") -> str:  # noqa: D401
    params = {"client": "gtx", "sl": src, "tl": tgt, "dt": "t", "q": text.strip()}
    resp = httpx.get(_GT_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return "".join(part[0] for part in data[0] if part[0]).strip()


def _llm_translate_batch(texts: list[str]) -> list[str]:
    from apps.ai.services.llm import get_llm

    llm = get_llm()
    raw = llm.complete(json.dumps(texts, ensure_ascii=False), system=_LLM_SYSTEM).strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    result = json.loads(raw)
    if len(result) != len(texts):
        raise ValueError(f"LLM returned {len(result)} items, expected {len(texts)}")
    return result


def translate_texts(
    texts: list[str],
    backend: str = "google",
    *,
    src: str = "uk",
    tgt: str = "en",
) -> list[str]:
    """Translate a batch of strings; falls back to per-item on failure."""
    if not texts:
        return []
    try:
        if backend == "llm":
            if src != "uk" or tgt != "en":
                raise ValueError("LLM backend supports uk→en only")
            return _llm_translate_batch(texts)
        return _google_translate_batch(texts, src=src, tgt=tgt)
    except Exception as exc:
        logger.warning("Batch translation failed (%s), retrying individually", exc)
        results: list[str] = []
        for text in texts:
            try:
                if backend == "llm":
                    results.append(_llm_translate_batch([text])[0])
                else:
                    results.append(_google_translate_single(text, src=src, tgt=tgt))
            except Exception:
                results.append(text)
            time.sleep(0.15)
        return results


@dataclass(frozen=True)
class TranslationJob:
    label: str
    model: type[Model]
    src_field: str
    dst_field: str
    batch_size: int = 40
    queryset_filter: Q | None = None
    require_src: bool = True


def _job_queryset(job: TranslationJob) -> QuerySet:
    qs = job.model.objects.filter(missing_en_q(job.dst_field))
    if job.queryset_filter is not None:
        qs = qs.filter(job.queryset_filter)
    if job.require_src:
        qs = qs.exclude(**{job.src_field: ""}).exclude(**{f"{job.src_field}__isnull": True})
    return qs.order_by("pk")


def process_translation_job(
    job: TranslationJob,
    *,
    backend: str = "google",
    limit: int = 0,
    on_progress: Callable[[str, int, int], None] | None = None,
) -> int:
    """Translate one job definition; returns number of rows updated."""
    items = list(_job_queryset(job)[:limit] if limit else _job_queryset(job))
    if not items:
        logger.info("%s: up to date", job.label)
        return 0

    saved = 0
    batch_size = job.batch_size
    for start in range(0, len(items), batch_size):
        chunk = items[start : start + batch_size]
        texts = [getattr(obj, job.src_field) or "" for obj in chunk]
        non_empty = [(i, t) for i, t in enumerate(texts) if t.strip()]
        if not non_empty:
            continue

        indices, raw_texts = zip(*non_empty)
        translations = translate_texts(list(raw_texts), backend=backend)

        to_update: list[Model] = []
        for idx, translation in zip(indices, translations):
            obj = chunk[idx]
            setattr(obj, job.dst_field, translation)
            to_update.append(obj)

        with transaction.atomic():
            job.model.objects.bulk_update(to_update, [job.dst_field])

        saved += len(to_update)
        if on_progress:
            on_progress(job.label, saved, len(items))
        time.sleep(0.2)

    logger.info("%s: translated %d rows", job.label, saved)
    return saved


def catalog_translation_jobs(
    *,
    with_descriptions: bool = True,
    with_attribute_values: bool = False,
) -> list[TranslationJob]:
    from apps.catalog.models import (
        Attribute,
        AttributeGroup,
        Brand,
        Category,
        Filter,
        FilterGroup,
        Product,
        ProductAttribute,
    )

    jobs: list[TranslationJob] = [
        TranslationJob("Categories › name", Category, "name_uk", "name_en"),
        TranslationJob(
            "Categories › description",
            Category,
            "description_uk",
            "description_en",
            batch_size=10,
            queryset_filter=~Q(description_uk="") & Q(description_uk__isnull=False),
            require_src=False,
        ),
        TranslationJob(
            "Categories › seo_title",
            Category,
            "seo_title_uk",
            "seo_title_en",
            queryset_filter=~Q(seo_title_uk=""),
            require_src=False,
        ),
        TranslationJob(
            "Categories › seo_description",
            Category,
            "seo_description_uk",
            "seo_description_en",
            batch_size=10,
            queryset_filter=~Q(seo_description_uk=""),
            require_src=False,
        ),
        TranslationJob("Brands › name", Brand, "name_uk", "name_en"),
        TranslationJob(
            "Brands › description",
            Brand,
            "description_uk",
            "description_en",
            batch_size=10,
            queryset_filter=~Q(description_uk=""),
            require_src=False,
        ),
        TranslationJob("FilterGroups › name", FilterGroup, "name_uk", "name_en"),
        TranslationJob("Filters › name", Filter, "name_uk", "name_en"),
        TranslationJob("AttributeGroups › name", AttributeGroup, "name_uk", "name_en"),
        TranslationJob("Attributes › name", Attribute, "name_uk", "name_en"),
        TranslationJob("Products › name", Product, "name_uk", "name_en"),
        TranslationJob(
            "Products › short_description",
            Product,
            "short_description_uk",
            "short_description_en",
            batch_size=20,
            queryset_filter=~Q(short_description_uk=""),
            require_src=False,
        ),
        TranslationJob(
            "Products › seo_title",
            Product,
            "seo_title_uk",
            "seo_title_en",
            queryset_filter=~Q(seo_title_uk=""),
            require_src=False,
        ),
        TranslationJob(
            "Products › seo_description",
            Product,
            "seo_description_uk",
            "seo_description_en",
            batch_size=10,
            queryset_filter=~Q(seo_description_uk=""),
            require_src=False,
        ),
    ]

    if with_attribute_values:
        jobs.append(
            TranslationJob(
                "Product attributes › value",
                ProductAttribute,
                "value_uk",
                "value_en",
                batch_size=30,
            ),
        )

    if with_descriptions:
        jobs.insert(
            -1,
            TranslationJob(
                "Products › description",
                Product,
                "description_uk",
                "description_en",
                batch_size=5,
                queryset_filter=~Q(description_uk="") & Q(description_uk__isnull=False),
                require_src=False,
            ),
        )

    return jobs


def site_content_translation_jobs() -> list[TranslationJob]:
    """Models with manual ``field`` / ``field_en`` columns (not modeltranslation)."""
    from apps.pages.models import InfoPage
    from apps.services.models import PriceItem, Service, ServiceCategory

    return [
        TranslationJob("Info pages › title", InfoPage, "title", "title_en"),
        TranslationJob(
            "Info pages › content",
            InfoPage,
            "content",
            "content_en",
            batch_size=3,
            queryset_filter=~Q(content=""),
            require_src=False,
        ),
        TranslationJob("Service categories › name", ServiceCategory, "name", "name_en"),
        TranslationJob("Services › name", Service, "name", "name_en"),
        TranslationJob(
            "Services › description",
            Service,
            "description",
            "description_en",
            batch_size=3,
            queryset_filter=~Q(description=""),
            require_src=False,
        ),
        TranslationJob("Price items › name", PriceItem, "name", "name_en"),
    ]


def run_catalog_translation(
    *,
    what: str = "all",
    backend: str = "google",
    with_descriptions: bool = True,
    with_attribute_values: bool = False,
    limit: int = 0,
    on_progress: Callable[[str, int, int], None] | None = None,
) -> int:
    """Run translation jobs. *what*: all | catalog | site | categories | products | …"""
    total = 0

    if what in ("all", "catalog", "categories", "filtergroups", "filters", "attributegroups", "attributes", "products", "brands"):
        jobs = catalog_translation_jobs(
            with_descriptions=with_descriptions,
            with_attribute_values=with_attribute_values or what == "productattrs",
        )
        subset = {
            "categories": ("Categories",),
            "brands": ("Brands",),
            "filtergroups": ("FilterGroups",),
            "filters": ("Filters",),
            "attributegroups": ("AttributeGroups",),
            "attributes": ("Attributes",),
            "products": ("Products",),
            "productattrs": ("Product attributes",),
        }
        if what not in ("all", "catalog"):
            prefixes = subset.get(what, set())
            jobs = [j for j in jobs if any(j.label.startswith(p) for p in prefixes)]

        for job in jobs:
            total += process_translation_job(job, backend=backend, limit=limit, on_progress=on_progress)

    if what in ("all", "site"):
        for job in site_content_translation_jobs():
            total += process_translation_job(job, backend=backend, limit=limit, on_progress=on_progress)

    return total
