"""Smoke tests for catalog admin configuration."""

import pytest
from django.contrib import admin

from apps.catalog.admin import ProductAdmin, ProductFilterInline
from apps.catalog.models import Product


def test_product_admin_has_filter_inline():
    inlines = [inline.model for inline in ProductAdmin.inlines]
    assert ProductFilterInline.model in inlines


def test_product_admin_autocomplete_brand():
    assert "brand" in ProductAdmin.autocomplete_fields


def test_product_admin_search_includes_translated_names():
    assert "name_uk" in ProductAdmin.search_fields
    assert "name_en" in ProductAdmin.search_fields


def test_product_registered_in_admin_site():
    assert admin.site.is_registered(Product)


def test_product_admin_fieldsets_use_two_languages_not_uk_duplicate():
    """Base fields are Ukrainian; *_en is English — no separate *_uk inputs."""
    all_fields: list[str] = []
    for _title, options in ProductAdmin.fieldsets:
        all_fields.extend(options["fields"])

    for base, en in (
        ("name", "name_en"),
        ("description", "description_en"),
        ("short_description", "short_description_en"),
        ("seo_title", "seo_title_en"),
        ("seo_description", "seo_description_en"),
    ):
        assert base in all_fields
        assert en in all_fields
        assert f"{base}_uk" not in all_fields
