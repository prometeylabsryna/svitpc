"""Tests for LLM content generation service (mocked)."""

import json

import pytest
from unittest.mock import MagicMock, patch

from apps.ai.services.llm import LLMNotConfiguredError, is_llm_configured, parse_llm_json


class TestLLMConfiguration:
    def test_is_llm_configured_false_when_empty(self, settings):
        settings.LLM_API_KEY = ""
        assert is_llm_configured() is False

    def test_is_llm_configured_true_when_set(self, settings):
        settings.LLM_API_KEY = "sk-test"
        assert is_llm_configured() is True

    def test_get_llm_raises_when_not_configured(self, settings):
        settings.LLM_API_KEY = ""
        from apps.ai.services.llm import get_llm

        with pytest.raises(LLMNotConfiguredError):
            get_llm()


class TestParseLLMJson:
    def test_plain_json(self):
        data = parse_llm_json('{"title": "Test", "description": "Desc"}')
        assert data["title"] == "Test"

    def test_markdown_fenced_json(self):
        raw = '```json\n{"title": "T", "description": "D"}\n```'
        data = parse_llm_json(raw)
        assert data == {"title": "T", "description": "D"}


class TestGenerateProductDescription:
    @pytest.mark.django_db
    def test_calls_llm_returns_str_and_saves(self, product_factory):
        from apps.ai.services.content import generate_product_description

        product = product_factory(name="ASUS Laptop")
        mock_llm = MagicMock()
        mock_llm.complete.return_value = "Generated description text."
        mock_product = MagicMock()
        mock_product.name = "ASUS Laptop"
        mock_product.attributes.all.return_value = []
        mock_product.description = ""
        mock_product.save = MagicMock()

        with patch("apps.ai.services.llm.get_llm", return_value=mock_llm):
            with patch(
                "apps.catalog.models.Product.objects.prefetch_related",
                return_value=MagicMock(get=MagicMock(return_value=mock_product)),
            ):
                result = generate_product_description(product.pk)

        assert result == "Generated description text."
        mock_llm.complete.assert_called_once()

    @pytest.mark.django_db
    def test_generate_for_missing_product_returns_empty(self):
        from apps.ai.services.content import generate_product_description

        result = generate_product_description(999999)
        assert result == ""

    @pytest.mark.django_db
    def test_returns_empty_when_llm_not_configured(self, product_factory, settings):
        from apps.ai.services.content import generate_product_description

        settings.LLM_API_KEY = ""
        product = product_factory(name="Test")
        result = generate_product_description(product.pk)
        assert result == ""


class TestGenerateProductSeo:
    @pytest.mark.django_db
    def test_parses_fenced_json_and_saves(self, product_factory):
        from apps.ai.services.content import generate_product_seo_bulk

        product = product_factory(name="RTX 4070")
        mock_llm = MagicMock()
        mock_llm.complete.return_value = '```json\n{"title": "RTX 4070", "description": "GPU"}\n```'

        with patch("apps.ai.services.llm.get_llm", return_value=mock_llm):
            generate_product_seo_bulk([product.pk])

        product.refresh_from_db()
        assert product.seo_title == "RTX 4070"
        assert product.seo_description == "GPU"


class TestConsultant:
    def test_stream_yields_error_when_not_configured(self, settings):
        from apps.ai.services.consultant import stream_consultant

        settings.LLM_API_KEY = ""
        events = list(stream_consultant("Привіт"))
        assert any("error" in e for e in events)
        assert events[-1].strip() == "data: [DONE]"

    def test_compatibility_returns_message_when_not_configured(self, settings):
        from apps.ai.services.consultant import check_compatibility

        settings.LLM_API_KEY = ""
        mock_product = MagicMock()
        mock_product.name = "CPU"
        mock_product.attributes.all.return_value = []

        mock_qs = MagicMock()
        mock_qs.prefetch_related.return_value = mock_qs
        mock_qs.__len__ = MagicMock(return_value=2)
        mock_qs.__iter__ = MagicMock(return_value=iter([mock_product, mock_product]))

        with patch("apps.catalog.models.Product.objects.filter", return_value=mock_qs):
            result = check_compatibility([1, 2])

        assert "не налаштовано" in result.lower()
