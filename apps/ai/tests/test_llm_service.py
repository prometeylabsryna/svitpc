"""Tests for LLM content generation service (mocked)."""

import pytest
from unittest.mock import MagicMock, patch


class TestGenerateProductDescription:
    @pytest.mark.django_db
    def test_calls_llm_returns_str_and_saves(self, product_factory):
        from apps.ai.services.content import generate_product_description

        product = product_factory(name="ASUS Laptop")
        mock_llm = MagicMock()
        mock_llm.complete.return_value = "Generated description text."

        # content.py uses `from .llm import get_llm` inside the function
        with patch("apps.ai.services.llm.get_llm", return_value=mock_llm):
            result = generate_product_description(product.pk)

        assert isinstance(result, str)

    @pytest.mark.django_db
    def test_generate_for_missing_product_returns_empty(self):
        from apps.ai.services.content import generate_product_description

        result = generate_product_description(999999)
        assert result == ""
