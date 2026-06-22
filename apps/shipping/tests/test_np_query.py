"""Tests for NP Latin/English query helpers."""

from apps.shipping.np_query import city_search_variants, is_latin_query


def test_city_search_variants_kyiv():
    variants = city_search_variants("Kyiv")
    assert "Kyiv" in variants
    assert "Київ" in variants


def test_is_latin_query():
    assert is_latin_query("Kyiv")
    assert not is_latin_query("Київ")
