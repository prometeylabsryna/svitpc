"""AI content generation: product descriptions, SEO, category short descriptions."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


PRODUCT_DESC_PROMPT = """Напиши продаючий опис товару для інтернет-магазину комп'ютерної техніки.
Товар: {name}
Характеристики: {attrs}
Вимоги: 150–250 слів, на основі характеристик, мова — українська, без перебільшень."""

PRODUCT_SHORT_DESC_PROMPT = """Напиши короткий продаючий опис товару для картки в каталозі.
Товар: {name}
Характеристики: {attrs}
Вимоги: 1–2 речення до 180 символів, мова — українська, акцент на головній перевазі."""

PRODUCT_SEO_PROMPT = """Створи SEO title (max 60 символів) та meta description (max 155 символів) для товару.
Товар: {name}
Відповідь у форматі JSON: {{"title": "...", "description": "..."}}"""

CATEGORY_DESC_PROMPT = """Напиши короткий (2–3 речення) SEO-опис категорії для інтернет-магазину комп'ютерної техніки.
Категорія: {name}
Мова: українська."""

ENHANCE_ATTRS_PROMPT = """Перетвори технічні характеристики товару на зрозумілий покупцю короткий текст.
Товар: {name}
Характеристики: {attrs}
Вимоги: 3–5 коротких пунктів (лише ключові переваги). Кожен пункт з нового рядка, починається з «•».
Мова — українська. Тільки пункти, без вступу і закінчення."""


def generate_category_description(category_id: int) -> str:
    """Generate SEO description for a catalog category using AI."""
    from apps.catalog.models import Category
    from .llm import get_llm

    try:
        category = Category.objects.get(pk=category_id)
        llm = get_llm()
        text = llm.complete(CATEGORY_DESC_PROMPT.format(name=category.name))
        category.description = text
        category.save(update_fields=["description"])
        return text
    except Exception as exc:
        logger.error("AI category description failed category_id=%s: %s", category_id, exc)
        return ""


def generate_product_description(product_id: int) -> str:
    from apps.catalog.models import Product
    from .llm import get_llm

    try:
        product = Product.objects.prefetch_related("attributes__attribute").get(pk=product_id)
        attrs = "; ".join(f"{pa.attribute.name}: {pa.value}" for pa in product.attributes.all()[:20])
        llm = get_llm()
        text = llm.complete(PRODUCT_DESC_PROMPT.format(name=product.name, attrs=attrs or "не вказано"))
        product.description = text
        product.save(update_fields=["description"])
        return text
    except Exception as exc:
        logger.error("AI description generation failed product_id=%s: %s", product_id, exc)
        return ""


def generate_product_short_description(product_id: int) -> str:
    from apps.catalog.models import Product
    from .llm import get_llm

    try:
        product = Product.objects.prefetch_related("attributes__attribute").get(pk=product_id)
        attrs = "; ".join(f"{pa.attribute.name}: {pa.value}" for pa in product.attributes.all()[:10])
        llm = get_llm()
        text = llm.complete(PRODUCT_SHORT_DESC_PROMPT.format(name=product.name, attrs=attrs or "не вказано"))
        product.short_description = text[:300]
        product.save(update_fields=["short_description"])
        return text
    except Exception as exc:
        logger.error("AI short description failed product_id=%s: %s", product_id, exc)
        return ""


def enhance_product_characteristics(product_id: int) -> str:
    """Rewrite raw attributes as bullet-point user-friendly text into short_description."""
    from apps.catalog.models import Product
    from .llm import get_llm

    try:
        product = Product.objects.prefetch_related("attributes__attribute").get(pk=product_id)
        attrs = "; ".join(f"{pa.attribute.name}: {pa.value}" for pa in product.attributes.all()[:20])
        if not attrs:
            return ""
        llm = get_llm()
        text = llm.complete(ENHANCE_ATTRS_PROMPT.format(name=product.name, attrs=attrs))
        product.short_description = text[:500]
        product.save(update_fields=["short_description"])
        return text
    except Exception as exc:
        logger.error("AI enhance characteristics failed product_id=%s: %s", product_id, exc)
        return ""


@shared_task
def generate_product_seo_bulk(product_ids: list[int]) -> None:
    import json
    from apps.catalog.models import Product
    from .llm import get_llm

    llm = get_llm()
    for pid in product_ids:
        try:
            product = Product.objects.get(pk=pid)
            response = llm.complete(PRODUCT_SEO_PROMPT.format(name=product.name))
            data = json.loads(response)
            product.seo_title = data.get("title", "")[:255]
            product.seo_description = data.get("description", "")[:500]
            product.save(update_fields=["seo_title", "seo_description"])
        except Exception as exc:
            logger.error("SEO gen failed product=%s: %s", pid, exc)


@shared_task
def generate_description_bulk(product_ids: list[int]) -> None:
    for pid in product_ids:
        generate_product_description(pid)


@shared_task
def generate_short_description_bulk(product_ids: list[int]) -> None:
    for pid in product_ids:
        generate_product_short_description(pid)


@shared_task
def enhance_characteristics_bulk(product_ids: list[int]) -> None:
    for pid in product_ids:
        enhance_product_characteristics(pid)
