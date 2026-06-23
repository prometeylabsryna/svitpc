import pytest

from apps.catalog.search_index import refresh_product_search_vectors
from apps.search.views import _fts_stem_root, _normalize_search_query, _search_qs, _search_variants

_VALID_IMAGE_URL = "https://cdn.example.com/product-photo.jpg"


@pytest.mark.django_db
class TestSearchByBrand:
    def test_finds_product_by_brand_name(self, product_factory, brand_factory):
        brand = brand_factory(name="RazerUniqueBrand")
        target = product_factory(
            name="Keyboard",
            brand=brand,
            slug="kb-razer",
            image_url=_VALID_IMAGE_URL,
        )
        product_factory(name="Other mouse", slug="other-mouse", image_url=_VALID_IMAGE_URL)
        refresh_product_search_vectors()

        results = _search_qs("RazerUniqueBrand")
        assert any(p.pk == target.pk for p in results)
        assert all(p.is_visible for p in results)

    def test_finds_product_by_sku(self, product_factory):
        target = product_factory(
            name="Cable",
            sku="SKU-UNIQUE-42",
            slug="cable-42",
            image_url=_VALID_IMAGE_URL,
        )
        product_factory(name="Other", sku="OTHER", slug="other-sku", image_url=_VALID_IMAGE_URL)
        refresh_product_search_vectors()

        results = _search_qs("SKU-UNIQUE-42")
        assert any(p.pk == target.pk for p in results)


class TestNormalizeSearchQuery:
    def test_strips_trailing_stray_quote(self):
        assert _normalize_search_query("комп'ютер'") == "комп'ютер"

    def test_unifies_apostrophe_variants(self):
        assert _normalize_search_query("комп\u2019ютер") == "комп'ютер"

    def test_unifies_macos_apostrophe(self):
        assert _normalize_search_query("комп\u02bcютер") == "комп'ютер"

    def test_variants_include_letter_swaps(self):
        variants = _search_variants("Монитор")
        assert "Монітор" in variants

    def test_variants_include_html_entity_form(self):
        variants = _search_variants("комп'ютер")
        assert "комп&#039;ютер" in variants

    def test_variants_include_capitalized_form(self):
        variants = _search_variants("комп'ютер")
        assert "Комп'ютер" in variants
        assert "Комп&#039;ютер" in variants

    def test_fts_stem_root_strips_plural_suffix(self):
        assert _fts_stem_root("термоси") == "термос"
        assert _fts_stem_root("монітор") is None or _fts_stem_root("моніторів") == "монітор"


@pytest.mark.django_db
class TestFuzzySearch:
    def test_finds_product_with_extra_trailing_quote(self, product_factory):
        target = product_factory(
            name="Ноутбук комп'ютер ASUS",
            slug="laptop-asus",
            image_url=_VALID_IMAGE_URL,
        )
        product_factory(name="Мишка Logitech", slug="mouse-lg", image_url=_VALID_IMAGE_URL)
        refresh_product_search_vectors()

        results = _search_qs("комп'ютер'")
        assert any(p.pk == target.pk for p in results)

    def test_finds_product_with_minor_typo(self, product_factory):
        target = product_factory(
            name="Монітор Samsung 27",
            slug="monitor-samsung",
            image_url=_VALID_IMAGE_URL,
        )
        product_factory(name="Клавіатура", slug="keyboard", image_url=_VALID_IMAGE_URL)
        refresh_product_search_vectors()

        results = _search_qs("Монитор")
        assert any(p.pk == target.pk for p in results)

    def test_russian_query_finds_ukrainian_spelling_products(self, product_factory):
        first = product_factory(
            name="Монітор Alpha Test",
            slug="monitor-alpha-test",
            image_url=_VALID_IMAGE_URL,
        )
        second = product_factory(
            name="Монітор Beta Test",
            slug="monitor-beta-test",
            image_url=_VALID_IMAGE_URL,
        )
        product_factory(
            name="Монитор Gamma Test",
            slug="monitor-gamma-test",
            image_url=_VALID_IMAGE_URL,
        )
        product_factory(name="Клавіатура", slug="keyboard-ru-uk", image_url=_VALID_IMAGE_URL)
        refresh_product_search_vectors()

        results = _search_qs("монитор")
        pks = {p.pk for p in results}
        assert first.pk in pks
        assert second.pk in pks

    def test_finds_opencart_html_entity_name(self, product_factory):
        target = product_factory(
            name="Комп&#039;ютер ASUS PN41 Test",
            slug="pc-asus-pn41",
            image_url=_VALID_IMAGE_URL,
        )
        product_factory(name="Мишка Logitech", slug="mouse-lg2", image_url=_VALID_IMAGE_URL)
        refresh_product_search_vectors()

        for query in ("комп'ютер", "комп\u02bcютер", "компютер"):
            results = _search_qs(query)
            assert any(p.pk == target.pk for p in results), f"failed for {query!r}"
