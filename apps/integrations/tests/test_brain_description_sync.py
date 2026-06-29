"""Tests for Brain description backfill cursor and re-queue logic."""

from __future__ import annotations

import pytest
from django.core.cache import cache

from apps.catalog.models import Product
from apps.integrations.brain.description_sync import (
    CURSOR_CACHE_KEY,
    advance_backfill_cursor,
    brain_products_needing_content_qs,
    fetch_backfill_chunk,
    should_requeue_backfill,
)


@pytest.mark.django_db
def test_fetch_backfill_chunk_respects_cursor() -> None:
    cache.delete(CURSOR_CACHE_KEY)
    p1 = Product.objects.create(
        name="A",
        slug="desc-a",
        price=10,
        source=Product.SOURCE_BRAIN,
        external_id="101",
        description_uk="",
    )
    Product.objects.create(
        name="B",
        slug="desc-b",
        price=10,
        source=Product.SOURCE_BRAIN,
        external_id="102",
        description_uk="",
    )
    advance_backfill_cursor([p1])
    chunk = fetch_backfill_chunk(reset_cursor=False)
    assert len(chunk) == 1
    assert chunk[0].external_id == "102"


@pytest.mark.django_db
def test_should_requeue_when_progress_made() -> None:
    assert should_requeue_backfill(
        before_remaining=100,
        after_remaining=50,
        last_pk=10,
    )


@pytest.mark.django_db
def test_should_requeue_when_more_pk_ahead() -> None:
    p1 = Product.objects.create(
        name="First",
        slug="desc-first",
        price=10,
        source=Product.SOURCE_BRAIN,
        external_id="201",
        description_uk="",
    )
    Product.objects.create(
        name="Later",
        slug="desc-later",
        price=10,
        source=Product.SOURCE_BRAIN,
        external_id="202",
        description_uk="",
    )
    assert should_requeue_backfill(
        before_remaining=2,
        after_remaining=2,
        last_pk=p1.pk,
    )


def test_should_not_requeue_when_done() -> None:
    assert not should_requeue_backfill(
        before_remaining=0,
        after_remaining=0,
        last_pk=0,
    )


@pytest.mark.django_db
def test_needing_content_includes_product_with_desc_but_no_warranty() -> None:
    from apps.catalog.models import Attribute, AttributeGroup, ProductAttribute

    p = Product.objects.create(
        name="Laptop",
        slug="laptop-warranty",
        price=100,
        source=Product.SOURCE_BRAIN,
        external_id="501",
        description_uk="Повний опис ноутбука",
    )
    assert brain_products_needing_content_qs().filter(pk=p.pk).exists()

    ag, _ = AttributeGroup.objects.get_or_create(name="Характеристики")
    attr, _ = Attribute.objects.get_or_create(group=ag, name="Гарантія, міс")
    ProductAttribute.objects.create(product=p, attribute=attr, value="36")
    assert not brain_products_needing_content_qs().filter(pk=p.pk).exists()
