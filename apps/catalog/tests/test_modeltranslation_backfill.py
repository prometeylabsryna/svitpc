"""Tests for modeltranslation UK column backfill."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.db import connection

from apps.catalog.models import Attribute, AttributeGroup, Brand, Product, ProductAttribute
from apps.core.modeltranslation_sync import backfill_uk_from_legacy


@pytest.mark.django_db
def test_backfill_copies_legacy_value_to_value_uk(product_factory):
    product = product_factory(name="Товар", slug="backfill-product", price=Decimal("100"))
    group = AttributeGroup.objects.create(name="Група", name_uk="Група")
    attribute = Attribute.objects.create(group=group, name="Тип", name_uk="Тип")
    pa = ProductAttribute.objects.create(product=product, attribute=attribute, value="колонки")

    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE catalog_productattribute SET value_uk = NULL, value = %s WHERE id = %s",
            ["з legacy колонки", pa.pk],
        )

    assert ProductAttribute.objects.get(pk=pa.pk).value == ""

    stats = backfill_uk_from_legacy()
    assert stats["catalog_productattribute.value_uk"] >= 1
    assert ProductAttribute.objects.get(pk=pa.pk).value == "з legacy колонки"


@pytest.mark.django_db
def test_backfill_copies_legacy_brand_name_to_name_uk(brand_factory):
    brand = brand_factory(name="LegacyBrand", slug="legacy-brand-backfill")

    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE catalog_brand SET name_uk = NULL, name = %s WHERE id = %s",
            ["З legacy", brand.pk],
        )

    assert Brand.objects.get(pk=brand.pk).name == ""

    stats = backfill_uk_from_legacy()
    assert stats["catalog_brand.name_uk"] >= 1
    assert Brand.objects.get(pk=brand.pk).name == "З legacy"


@pytest.mark.django_db
def test_product_attribute_formset_valid_after_backfill(product_factory):
    from django.contrib.admin.sites import AdminSite
    from django.test import RequestFactory
    from apps.catalog.admin import ProductAdmin

    product = product_factory(name="Акустика", slug="formset-backfill-product", price=Decimal("100"))
    group = AttributeGroup.objects.create(name="Характеристики", name_uk="Характеристики")
    attribute = Attribute.objects.create(group=group, name="Тип", name_uk="Тип")
    pa = ProductAttribute.objects.create(product=product, attribute=attribute, value="колонки")

    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE catalog_productattribute SET value_uk = NULL, value = %s WHERE id = %s",
            ["портативні", pa.pk],
        )

    backfill_uk_from_legacy()

    site = AdminSite()
    admin = ProductAdmin(Product, site)
    inline = admin.inlines[1](Product, site)
    from apps.customers.models import Customer

    user = Customer.objects.create_superuser(
        email="inline-test@example.com",
        password="secret123",
        first_name="Admin",
    )
    req = RequestFactory().get("/admin/")
    req.user = user
    FormSet = inline.get_formset(req, product)

    formset_after = FormSet(
        instance=product,
        data={
            "attributes-TOTAL_FORMS": "1",
            "attributes-INITIAL_FORMS": "1",
            "attributes-MIN_NUM_FORMS": "0",
            "attributes-MAX_NUM_FORMS": "1000",
            "attributes-0-id": str(pa.pk),
            "attributes-0-product": str(product.pk),
            "attributes-0-attribute": str(attribute.pk),
            "attributes-0-value_uk": "",
            "attributes-0-value_en": "",
        },
        prefix="attributes",
    )
    assert formset_after.is_valid(), formset_after.errors
